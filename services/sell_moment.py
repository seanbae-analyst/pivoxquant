"""매도 순간의 거울 — at the sell, what the user wrote before it.

2026-10-15. The loop is 멈춤 → 기록 → 거울 (docs/claude/product-premise.md).
The pause depends on the user remembering to open the app before buying, and
the disposition-effect mirror (services/behavior/profit_loss_mirror.py) is a
statistic read long after the fact. The one moment that reliably reaches the
user is the fill itself (routes/imports.py::webhook_import →
services/fill_memo.py) or the sell they are typing into the portfolio. This
module moves the mirror to that moment: when a 매도 arrives, put next to it

  * ``words`` — what the user themselves wrote about this ticker *before* the
    sell: the 멈춤 rationale, the reason written when a 매수 fill was approved
    (and the position's own reason), their research note's theses + "틀렸다고
    볼 신호", observation notes tagged with the ticker;
  * ``held_days`` — how long the FIFO lots this sell closes were held;
  * ``vs_cost_pct`` — where the sell price sits against those lots' own cost.

Facts from the user's own rows only. No market data, no FX service, no
network, no clock inside :func:`build_sell_moment` (``now`` is passed in) —
the same discipline as ``services/behavior/*`` and
``services/pre_trade/friction_outcome.py``. No score, no verdict, no
direction: the user reads their own words and decides nothing here.

FIFO is ``services/profile/fifo_util.py`` — reused, never re-implemented.
Holding-registration seeds stay in the lot queue (their quantity and cost are
real) but their ``traded_at`` is the registration time, so a sell that closes
only seed lots has no ``held_days`` (``collapse_pairs_by_sell`` flags it).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, NamedTuple

from services.profile.fifo_util import (
    collapse_pairs_by_sell,
    fifo_match_closed_trades_with_pnl,
)

# Where a quote came from — the frontend labels them 멈춤 / 체결 이유 /
# 리서치 / 관찰 노트. Data values, not copy.
SOURCE_PAUSE = "pause"
SOURCE_FILL_REASON = "fill_reason"
SOURCE_RESEARCH = "research"
SOURCE_NOTE = "note"

# A few quotes, not an archive: the sell moment is a glance. Per-source cap so
# five observation notes cannot push the buy-time reason off the block.
MAX_WORDS = 4
MAX_PER_SOURCE = 2
MAX_QUOTE_CHARS = 280

# Rows read per source before the in-memory filter — enough for the caps
# above even after the before-the-sell cut.
_LOAD_LIMIT = 20

_BUY = "BUY"    # // legal-ok — trade action data value (TradeHistory / PendingTrade)
_SELL = "SELL"  # // legal-ok — trade action data value


@dataclass(frozen=True)
class SellInput:
    """The sell being looked at — a pending fill, or one being typed."""
    ticker: str
    shares: float
    price: float
    currency: str
    traded_at: datetime


class Written(NamedTuple):
    """A reason written at a 매수 fill — (text, written_at)."""
    text: str | None
    at: datetime | None


class _SyntheticSell(NamedTuple):
    """The sell under look, shaped like a TradeHistory row for fifo_util."""
    ticker: str
    action: str
    shares: float
    price_per_share: float
    traded_at: datetime
    id: int
    pnl: float = 0.0
    pnl_pct: float = 0.0
    source: str | None = None


# ── Pure core ────────────────────────────────────────────────────────

def build_sell_moment(
    sell: SellInput,
    *,
    trades: Iterable = (),
    reflections: Iterable = (),
    fill_reasons: Iterable[Written] = (),
    research: Iterable = (),
    notes: Iterable = (),
    now: datetime,
    words_before: datetime | None = None,
) -> dict:
    """The sell-moment mirror for one sell. Pure — no I/O, no clock.

    ``trades`` are the user's ``TradeHistory``-shaped rows (any ticker; the
    other tickers are ignored). ``words_before`` is the cut for quotes —
    defaults to the sell time; a date-grain manual sell passes the end of
    that day so a note written this morning still counts. Never later than
    ``now``.
    """
    ticker = (sell.ticker or "").strip().upper()
    cut = min(words_before or sell.traded_at or now, now)
    held_days, vs_cost_pct, matched = _closed_lots(sell, ticker, trades)
    words = _words(
        ticker, cut,
        reflections=reflections, fill_reasons=fill_reasons,
        research=research, notes=notes,
    )
    return {
        "ticker": ticker,
        "words": words,
        "held_days": held_days,
        "vs_cost_pct": vs_cost_pct,
        "matched_shares": round(matched, 6),
    }


def _closed_lots(sell: SellInput, ticker: str, trades: Iterable) -> tuple[int | None, float | None, float]:
    """(held_days, vs_cost_pct, matched_shares) for the lots this sell closes.

    Rows after the sell cannot change which lots it closes (FIFO is
    chronological), so only rows up to the sell are replayed. The sell goes
    last among same-time rows (largest id) — a sell typed today closes
    after anything already recorded today. The pairs it adds are the
    difference between a replay with it and one without it.
    """
    if not ticker or sell.traded_at is None or not (sell.shares > 0):
        return None, None, 0.0
    rows = [
        t for t in trades
        if (getattr(t, "ticker", None) or "").upper() == ticker
        and getattr(t, "traded_at", None) is not None
        and t.traded_at <= sell.traded_at
    ]
    synthetic = _SyntheticSell(
        ticker=ticker, action=_SELL, shares=float(sell.shares),
        price_per_share=float(sell.price), traded_at=sell.traded_at,
        id=max((int(getattr(t, "id", 0) or 0) for t in rows), default=0) + 1,
    )
    before = fifo_match_closed_trades_with_pnl(rows)
    after = fifo_match_closed_trades_with_pnl([*rows, synthetic])
    mine = after[len(before):]
    if not mine:
        return None, None, 0.0
    merged, _pct = collapse_pairs_by_sell(mine)[0]
    held = None if merged.buy_is_seed else int(round(merged.hold_days))
    return held, _vs_cost(sell, ticker, rows, mine, merged.buy_price), float(merged.quantity)


def _vs_cost(sell: SellInput, ticker: str, rows: list, mine: list, cost: float) -> float | None:
    """Percent of the sell price over the closed lots' share-weighted cost.

    Same currency only — no FX here: when any 매수 row feeding these lots is
    in another currency than the sell (or a lot has no price) → ``None``.
    """
    if any(p.buy_price <= 0 for p, _ in mine) or cost <= 0 or not (sell.price > 0):
        return None
    currency = (sell.currency or "").upper()
    buys = [t for t in rows if (getattr(t, "action", "") or "").upper() == _BUY]
    if not currency or any((getattr(t, "currency", "") or "").upper() != currency for t in buys):
        return None
    return round((float(sell.price) - cost) / cost * 100.0, 2)


def _words(ticker: str, cut: datetime, *, reflections, fill_reasons, research, notes) -> list[dict]:
    """The user's own text about ``ticker`` written before ``cut``, newest
    first, at most ``MAX_PER_SOURCE`` per source and ``MAX_WORDS`` in all."""
    picked = [
        *_pause_quotes(ticker, cut, reflections),
        *_fill_quotes(ticker, cut, fill_reasons),
        *_research_quotes(ticker, cut, research),
        *_note_quotes(ticker, cut, notes),
    ]
    picked.sort(key=lambda q: q["_at"], reverse=True)
    out = []
    for q in picked[:MAX_WORDS]:
        at = q.pop("_at")
        q["at"] = at.isoformat()
        out.append(q)
    return out


def _quote(source: str, ticker: str, text: str, at: datetime, invalidation: str | None = None) -> dict:
    return {
        "source": source,
        "ticker": ticker,
        "text": _clip(text),
        "invalidation": _clip(invalidation) if invalidation else None,
        "_at": at,
    }


def _clip(text: str) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= MAX_QUOTE_CHARS else s[: MAX_QUOTE_CHARS - 1].rstrip() + "…"


def _before(at, cut: datetime) -> bool:
    return at is not None and at < cut


def _pause_quotes(ticker: str, cut: datetime, reflections) -> list[dict]:
    """멈춤 rationale for a 매수 (or unspecified) of this ticker. A pause the
    user went through with comes first — that is the one they acted on."""
    rows = [
        r for r in reflections
        if (getattr(r, "intended_ticker", "") or "").upper() == ticker
        and (getattr(r, "intended_side", None) or _BUY).upper() == _BUY
        and (getattr(r, "rationale", None) or "").strip()
        and _before(getattr(r, "created_at", None), cut)
    ]
    rows.sort(key=lambda r: (r.proceeded_at is not None, r.created_at), reverse=True)
    return [_quote(SOURCE_PAUSE, ticker, r.rationale, r.created_at) for r in rows[:MAX_PER_SOURCE]]


def _fill_quotes(ticker: str, cut: datetime, fill_reasons: Iterable[Written]) -> list[dict]:
    """Reasons written at a 매수 fill. The first approved reason also fills
    ``Position.thesis`` (services/imports/ledger.py) — the same words twice
    are one quote."""
    seen: set[str] = set()
    out = []
    for w in sorted((w for w in fill_reasons if w.at is not None), key=lambda w: w.at, reverse=True):
        text = (w.text or "").strip()
        key = " ".join(text.split())
        if not text or key in seen or not _before(w.at, cut):
            continue
        seen.add(key)
        out.append(_quote(SOURCE_FILL_REASON, ticker, text, w.at))
    return out[:MAX_PER_SOURCE]


def _research_quotes(ticker: str, cut: datetime, research) -> list[dict]:
    rows = [
        n for n in research
        if (getattr(n, "ticker", "") or "").upper() == ticker
        and _before(getattr(n, "created_at", None), cut)
        and n.theses_list()
    ]
    rows.sort(key=lambda n: n.created_at, reverse=True)
    return [
        _quote(SOURCE_RESEARCH, ticker, " · ".join(n.theses_list()), n.created_at,
               invalidation=(n.invalidation or "").strip() or None)
        for n in rows[:MAX_PER_SOURCE]
    ]


def _note_quotes(ticker: str, cut: datetime, notes) -> list[dict]:
    rows = [
        n for n in notes
        if ticker in [str(t).upper() for t in n.tickers_list()]
        and (getattr(n, "body", None) or "").strip()
        and _before(getattr(n, "created_at", None), cut)
    ]
    rows.sort(key=lambda n: n.created_at, reverse=True)
    return [_quote(SOURCE_NOTE, ticker, n.body, n.created_at) for n in rows[:MAX_PER_SOURCE]]


# ── Loader (DB → pure core) ──────────────────────────────────────────

def load_sell_moment(
    user_id: int,
    sell: SellInput,
    *,
    now: datetime,
    words_before: datetime | None = None,
) -> dict:
    """Read the caller's own rows for ``sell.ticker`` and build the mirror.

    Every query filters on ``user_id`` — nobody else's rows can reach the
    pure core. Reads only; no market data.
    """
    from sqlalchemy import func

    from models import ObservationNote, Position, PreTradeReflection, ResearchNote, TradeHistory
    from models.import_batch import STATUS_APPROVED, PendingTrade
    from services.observation_notes.service import _filter_json_element

    uid = int(user_id)
    ticker = (sell.ticker or "").strip().upper()
    cut = min(words_before or sell.traded_at or now, now)

    trades = TradeHistory.query.filter(
        TradeHistory.user_id == uid, func.upper(TradeHistory.ticker) == ticker,
    ).all()
    reflections = (
        PreTradeReflection.query.filter(
            PreTradeReflection.user_id == uid,
            func.upper(PreTradeReflection.intended_ticker) == ticker,
            PreTradeReflection.created_at < cut,
        ).order_by(PreTradeReflection.created_at.desc()).limit(_LOAD_LIMIT).all()
    )
    approved = (
        PendingTrade.query.filter(
            PendingTrade.user_id == uid,
            PendingTrade.ticker == ticker,
            PendingTrade.action == _BUY,
            PendingTrade.status == STATUS_APPROVED,
            PendingTrade.approved_thesis.isnot(None),
        ).order_by(PendingTrade.approved_at.desc()).limit(_LOAD_LIMIT).all()
    )
    fill_reasons = [Written(p.approved_thesis, p.approved_at) for p in approved]
    position = Position.query.filter_by(user_id=uid, ticker=ticker).first()
    if position is not None and position.thesis:
        # Legacy rows have a thesis but no thesis_created_at — the position's
        # own open time is the closest honest date.
        fill_reasons.append(Written(
            position.thesis, position.thesis_created_at or position.added_at,
        ))
    research = (
        ResearchNote.query.filter(
            ResearchNote.user_id == uid,
            ResearchNote.ticker == ticker,
            ResearchNote.created_at < cut,
        ).order_by(ResearchNote.created_at.desc()).limit(_LOAD_LIMIT).all()
    )
    notes = (
        _filter_json_element(
            ObservationNote.query.filter(
                ObservationNote.user_id == uid, ObservationNote.created_at < cut,
            ),
            ObservationNote.tickers_json,
            ticker,
        ).order_by(ObservationNote.created_at.desc()).limit(_LOAD_LIMIT).all()
    )
    return build_sell_moment(
        sell, trades=trades, reflections=reflections, fill_reasons=fill_reasons,
        research=research, notes=notes, now=now, words_before=cut,
    )


def pending_sell_input(row) -> SellInput | None:
    """A waiting 매도 ``PendingTrade`` as a :class:`SellInput`, else ``None``
    (매수 rows, rows without a ticker, rows already approved/rejected — an
    approved sell is in the ledger already and would be counted twice)."""
    from models.import_batch import STATUS_PENDING

    if row is None or (row.action or "").upper() != _SELL or row.status != STATUS_PENDING:
        return None
    ticker = (row.ticker or "").strip().upper()
    if not ticker or row.needs_ticker or row.traded_at is None:
        return None
    return SellInput(
        ticker=ticker, shares=float(row.shares or 0), price=float(row.price or 0),
        currency=(row.currency or "").upper(), traded_at=row.traded_at,
    )


def empty_moment(ticker: str | None = None) -> dict:
    return {
        "ticker": (ticker or "").strip().upper(),
        "words": [],
        "held_days": None,
        "vs_cost_pct": None,
        "matched_shares": 0.0,
    }


def end_of_day(day_start: datetime) -> datetime:
    """A date-grain sell's quote cut — the end of that (UTC-midnight) day."""
    return day_start + timedelta(days=1)


# ── Push sentence ────────────────────────────────────────────────────

def push_sentence(moment: dict) -> str:
    """One short sentence for the fill push, or ``""``.

    Pointer + facts only. **The user's own words never go on the lock
    screen** — the push says they exist; the words are behind the link.
    No direction word (the existing fill push carries none), no judgement.
    Only when there are words or a computable ``held_days``.
    """
    words = moment.get("words") or []
    held = moment.get("held_days")
    if not words and held is None:
        return ""
    parts = []
    if words:
        parts.append("이 종목에 적어 둔 말이 있어요")
    if held is not None:
        parts.append("하루 미만 보유" if held == 0 else f"{held}일 보유")
    pct = moment.get("vs_cost_pct")
    if pct is not None:
        parts.append(f"산 값 대비 {_signed_pct(pct)}")
    return " · ".join(parts) + "."


def _signed_pct(pct: float) -> str:
    sign = "+" if pct > 0 else ("−" if pct < 0 else "")
    return f"{sign}{abs(pct):.1f}%"
