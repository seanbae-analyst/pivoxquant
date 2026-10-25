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

from services.imports import is_date_only
from services.pre_trade.friction_outcome import ticker_key
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

# Stored times are naive UTC; a date-only row is its KST date at 00:00
# (services/imports — is_date_only).
_KST = timedelta(hours=9)

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
    cut = quote_cut(sell, now=now, words_before=words_before)
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


def quote_cut(sell: SellInput, *, now: datetime, words_before: datetime | None = None) -> datetime:
    """The cut for quotes. A date-only sell (a typed date, a CSV row) has no
    time of day, so anything written that KST day still came before it —
    the same calendar-day rule as ``ledger._reflection_ceiling``."""
    if words_before is None and sell.traded_at is not None and is_date_only(sell.traded_at):
        words_before = end_of_day(sell.traded_at)
    return min(words_before or sell.traded_at or now, now)


def _same(ticker: str | None, key: str) -> bool:
    """Same stock — .KS / .KQ / .KRX / bare code are one (``ticker_key``)."""
    return bool(ticker) and ticker_key(ticker) == key


def _kst_date(at: datetime):
    """The KST calendar date of a stored time (date-only rows already are)."""
    return at.date() if is_date_only(at) else (at + _KST).date()


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
    key = ticker_key(ticker)
    rows = [
        t for t in trades
        if _same(getattr(t, "ticker", None), key)
        and getattr(t, "traded_at", None) is not None
        and t.traded_at <= sell.traded_at
    ]
    # fifo_util keys lots by the exact ticker — replay copies under one key
    # so a 매수 on 035720.KQ is a lot for a 매도 on 035720.KS (ORM rows untouched).
    lots = [
        _SyntheticSell(
            ticker=key, action=getattr(t, "action", None) or "",
            shares=float(getattr(t, "shares", 0) or 0),
            price_per_share=float(getattr(t, "price_per_share", 0) or 0),
            traded_at=t.traded_at, id=int(getattr(t, "id", 0) or 0),
            pnl=float(getattr(t, "pnl", 0) or 0), pnl_pct=float(getattr(t, "pnl_pct", 0) or 0),
            source=getattr(t, "source", None),
        )
        for t in rows
    ]
    synthetic = _SyntheticSell(
        ticker=key, action=_SELL, shares=float(sell.shares),
        price_per_share=float(sell.price), traded_at=sell.traded_at,
        id=max((t.id for t in lots), default=0) + 1,
    )
    before = fifo_match_closed_trades_with_pnl(lots)
    after = fifo_match_closed_trades_with_pnl([*lots, synthetic])
    mine = after[len(before):]
    if not mine:
        return None, None, 0.0
    merged, _pct = collapse_pairs_by_sell(mine)[0]
    held = None if merged.buy_is_seed else _held_days([p for p, _ in mine], sell.traded_at)
    return held, _vs_cost(sell, rows, mine, merged.buy_price), float(merged.quantity)


def _held_days(slices: list, sold_at: datetime) -> int | None:
    """Whole KST calendar days from the closed lots' buys to the sell,
    share-weighted over the dated (non-seed) lots. Bought and sold on the
    same KST day is 0 (하루 미만) — elapsed hours rounded used to read a
    date-only buy sold that night as "1일" (2026-10-21)."""
    dated = [p for p in slices if not p.buy_is_seed and p.quantity > 0]
    qty = sum(p.quantity for p in dated)
    if not dated or qty <= 0:
        return None
    sold = _kst_date(sold_at)
    days = sum(max(0, (sold - _kst_date(p.buy_time)).days) * p.quantity for p in dated) / qty
    return int(days + 0.5)


def _vs_cost(sell: SellInput, rows: list, mine: list, cost: float) -> float | None:
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
    key = ticker_key(ticker)
    sources = [
        _pause_quotes(ticker, key, cut, reflections),
        _fill_quotes(ticker, cut, fill_reasons),
        _research_quotes(ticker, key, cut, research),
        _note_quotes(ticker, key, cut, notes),
    ]
    # Each source's first quote before any source's second — otherwise two
    # notes + two research notes, all newer, pushed the buy-time reason off
    # the block the per-source cap exists to keep (2026-10-21).
    picked: list[dict] = []
    for rank in range(MAX_PER_SOURCE):
        tier = sorted((qs[rank] for qs in sources if len(qs) > rank),
                      key=lambda q: q["_at"], reverse=True)
        picked.extend(tier[: MAX_WORDS - len(picked)])
    picked.sort(key=lambda q: q["_at"], reverse=True)
    out = []
    for q in picked:
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


def _pause_quotes(ticker: str, key: str, cut: datetime, reflections) -> list[dict]:
    """멈춤 rationale for a 매수 (or unspecified) of this ticker. A pause the
    user went through with comes first — that is the one they acted on."""
    rows = [
        r for r in reflections
        if _same(getattr(r, "intended_ticker", None), key)
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


def _research_quotes(ticker: str, key: str, cut: datetime, research) -> list[dict]:
    rows = [
        n for n in research
        if _same(getattr(n, "ticker", None), key)
        and _before(getattr(n, "created_at", None), cut)
        and n.theses_list()
    ]
    rows.sort(key=lambda n: n.created_at, reverse=True)
    return [
        _quote(SOURCE_RESEARCH, ticker, " · ".join(n.theses_list()), n.created_at,
               invalidation=(n.invalidation or "").strip() or None)
        for n in rows[:MAX_PER_SOURCE]
    ]


def _note_quotes(ticker: str, key: str, cut: datetime, notes) -> list[dict]:
    rows = [
        n for n in notes
        if any(_same(str(t), key) for t in n.tickers_list())
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
    from services.imports.ledger import _ticker_variants
    from services.observation_notes.service import _filter_json_element

    uid = int(user_id)
    ticker = (sell.ticker or "").strip().upper()
    cut = quote_cut(sell, now=now, words_before=words_before)
    # Every spelling of the same stock (.KS / .KQ / .KRX / bare code) —
    # one same-stock rule with the ledger (2026-10-21).
    variants = _ticker_variants(ticker)

    trades = TradeHistory.query.filter(
        TradeHistory.user_id == uid, func.upper(TradeHistory.ticker).in_(variants),
    ).all()
    reflections = (
        PreTradeReflection.query.filter(
            PreTradeReflection.user_id == uid,
            func.upper(PreTradeReflection.intended_ticker).in_(variants),
            PreTradeReflection.created_at < cut,
        ).order_by(PreTradeReflection.created_at.desc()).limit(_LOAD_LIMIT).all()
    )
    approved = (
        PendingTrade.query.filter(
            PendingTrade.user_id == uid,
            PendingTrade.ticker.in_(variants),
            PendingTrade.action == _BUY,
            PendingTrade.status == STATUS_APPROVED,
            PendingTrade.approved_thesis.isnot(None),
        ).order_by(PendingTrade.approved_at.desc()).limit(_LOAD_LIMIT).all()
    )
    fill_reasons = [Written(p.approved_thesis, p.approved_at) for p in approved]
    for position in Position.query.filter(
        Position.user_id == uid, Position.ticker.in_(variants),
    ).all():
        if position.thesis:
            # Legacy rows have a thesis but no thesis_created_at — the position's
            # own open time is the closest honest date.
            fill_reasons.append(Written(
                position.thesis, position.thesis_created_at or position.added_at,
            ))
    research = (
        ResearchNote.query.filter(
            ResearchNote.user_id == uid,
            ResearchNote.ticker.in_(variants),
            ResearchNote.created_at < cut,
        ).order_by(ResearchNote.created_at.desc()).limit(_LOAD_LIMIT).all()
    )
    by_id = {}
    for v in variants:
        for n in (
            _filter_json_element(
                ObservationNote.query.filter(
                    ObservationNote.user_id == uid, ObservationNote.created_at < cut,
                ),
                ObservationNote.tickers_json,
                v,
            ).order_by(ObservationNote.created_at.desc()).limit(_LOAD_LIMIT).all()
        ):
            by_id[n.id] = n
    notes = sorted(by_id.values(), key=lambda n: n.created_at, reverse=True)[:_LOAD_LIMIT]
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
    """A date-grain sell's quote cut — the end of that KST day.

    A date-only time is the KST date at 00:00 (unshifted), so that day ends
    at ``+1 day − 9h`` in naive UTC (``ledger._reflection_ceiling``). Without
    the −9h a note written 00:00–09:00 KST the next day read as "before the
    sell" (2026-10-21)."""
    return day_start + timedelta(days=1) - _KST


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
    # Sign from the shown value — −0.04 is "0.0%", not "−0.0%".
    shown = round(pct, 1)
    sign = "+" if shown > 0 else ("−" if shown < 0 else "")
    return f"{sign}{abs(shown):.1f}%"
