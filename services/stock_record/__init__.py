"""종목별 내 기록 — one stock, everything the user wrote down about it.

2026-10-25 (CEO "토스처럼 … 종목별로 정리", "적어야 할게 너무 많다"). Toss
explains why a stock moved; we cannot (no vendor price on screen — FMP
§2.2.2 — and per-stock interpretation is the 유사투자자문 line). What only
this app has is the user's own trail on a name: what they bought and sold
and at what price, the pauses before it (and the trades that never
happened), the research they wrote cold and how they scored it, the notes
they left. This module lines those up on one timeline.

Rules
-----
* **The user's own records only.** Fills, pauses, research notes and
  observation notes, read with an owner filter. No quote, no news, no
  score, no label, no line we draw about the stock.
* **One holding, any spelling.** Fills and pauses match by
  ``friction_outcome.ticker_key`` (005930 / 005930.KS / 005930.KQ are one),
  like the rebuy mirror; so are research and notes (2026-11-03 — they were
  read by the exact normalised spelling, so a note on ``035720.KQ`` was
  missing from ``035720.KS``). Notes are read whole, not the 365-day /
  50-note window /pre-trade uses — up to ``NOTE_ROW_CAP``.
* **A date-only fill is its KST day, not 00:00.** "Bought after the pause"
  uses ``friction_outcome._at_or_after`` (the calendar-day rule), and on the
  timeline such a fill sits at the end of its day (``rebuy_mirror._order_at``)
  — before 2026-11-03 a same-day buy fell before a morning pause and the
  pause counted as not taken.
* **Registration is not a fill.** A holding-registration seed shows as
  "보유 등록" (it carries the shares and average cost the user typed);
  adjust rows are bookkeeping and are left out.
* **Counts, never rates.** The summary is how many of each — and how many
  pauses ended without a buy of the same name afterwards (the 일어나지 않은
  거래, read straight from ``reflection_id`` links and later fills).
* **Company filings, behind a flag.** With ``FILINGS_ENABLED`` on, the
  company's filings — SEC EDGAR for a US name, OpenDART for a KR name (needs
  ``DART_API_KEY``) — are laid between the user's records by their official
  filing date, with a link to the original — facts, not a reading
  (services/filing_timeline). On by default since 2026-10-25 (CEO).

The route wraps it in the legal scrub, keeping the user's own words verbatim.
Reads only — except that an enabled filing sync may store new public filing
rows (no user data).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from extensions import db
from models import ObservationNote, Position, PreTradeReflection, TradeHistory
from services.behavior.rebuy_mirror import _order_at
from services.imports import is_date_only
from services.pre_trade.friction_outcome import _at_or_after, ticker_key
from services.profile.fifo_util import is_holding_seed, is_registration_row
from services.research_notes.service import research_list_for_ticker
from services.ticker_normalizer import normalize_ticker

logger = logging.getLogger(__name__)

_KR_SUFFIXES = (".KS", ".KQ", ".KRX")
_SHARE_EPSILON = 1e-9
# Filings start a month before the user's first record on the name.
FILING_LEAD_DAYS = 30
# Notes read for one name — a bound on the read, not a window (research_notes
# OVERVIEW_ROW_CAP is the same number).
NOTE_ROW_CAP = 1000


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _side(action: str | None) -> str | None:
    a = (action or "").upper()
    if a == "BUY":  # // legal-ok — TradeHistory.action value, compared only
        return "buy"
    if a == "SELL":  # // legal-ok — TradeHistory.action value, compared only
        return "sell"
    return None


def _currency_for(ticker: str, fills: list) -> str:
    for t in reversed(fills):
        if getattr(t, "currency", None):
            return str(t.currency).upper()
    return "KRW" if ticker.upper().endswith(_KR_SUFFIXES) else "USD"


def _pause_side(raw: str | None) -> str | None:
    s = (raw or "").upper()
    if s in ("BUY", "ENTRY", "LONG"):  # // legal-ok — stored side codes, compared only
        return "entry"
    if s in ("SELL", "EXIT", "SHORT"):  # // legal-ok — stored side codes, compared only
        return "exit"
    return None


def _notes_for(user_id: int, key: str) -> list[dict]:
    """The caller's observation notes naming this holding in any spelling,
    newest first. SQL narrows on the quoted code's start (``"035720`` covers
    035720 / .KS / .KQ); ``ticker_key`` then decides."""
    head = json.dumps(key, ensure_ascii=False)[:-1]
    escaped = head.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = (
        ObservationNote.query.filter(
            ObservationNote.user_id == user_id,
            ObservationNote.tickers_json.like(f"%{escaped}%", escape="\\"),
        )
        .order_by(ObservationNote.id.desc())
        .limit(NOTE_ROW_CAP)
        .all()
    )
    return [
        r.to_dict() for r in rows
        if any(ticker_key(t) == key for t in r.tickers_list())
    ]


def _first_day(events: list[dict[str, Any]]) -> date | None:
    days = []
    for e in events:
        try:
            days.append(datetime.fromisoformat(str(e.get("at") or "")[:19]).date())
        except ValueError:
            continue
    return min(days) if days else None


def _filing_block(key: str, normalized: str, fills: list, events: list[dict[str, Any]]) -> dict | None:
    """The company's filings (SEC / DART), when on and the user has records on it."""
    from services.filing_timeline import (
        FillPoint, filing_timeline, filings_enabled, market_of, source_available,
    )
    from services.imports import is_date_only

    market = market_of(normalized)
    if not filings_enabled() or not source_available(market):
        logger.info("stock_record: filings skipped for %s — enabled=%s market=%s source_available=%s",
                    key, filings_enabled(), market, source_available(market))
        return None
    first = _first_day(events)
    if first is None:
        logger.info("stock_record: filings skipped for %s — no dated record yet", key)
        return None
    points = [
        FillPoint(t.traded_at, _side(t.action) or "", untimed=is_date_only(t.traded_at))
        for t in fills
    ]
    try:
        return filing_timeline(
            key, fills=points, since=first - timedelta(days=FILING_LEAD_DAYS), market=market,
        )
    except Exception as exc:  # the page shows without filings rather than failing
        db.session.rollback()
        logger.warning("stock_record: filings unavailable for %s: %s", key, exc)
        return None


def stock_record(user_id: int, ticker: str, now: datetime | None = None) -> dict[str, Any]:
    """Everything the caller recorded on one stock → summary + timeline.

    Raises ``ValueError`` on an empty ticker. ``events`` are newest first;
    each has ``kind`` (fill · registered · pause · research · note · filing),
    ``at`` (naive-UTC ISO; a date-only value is that date's 00:00) and the
    fields of its kind. ``filing_reaction`` is None unless filings are on and
    an earnings release fell in the record's span.
    """
    normalized = normalize_ticker(str(ticker or "").strip())
    if not normalized:
        raise ValueError("ticker is required")
    key = ticker_key(normalized)
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    uid = int(user_id)

    rows = [
        t for t in TradeHistory.query.filter(TradeHistory.user_id == uid).all()
        if t.ticker and t.traded_at and ticker_key(t.ticker) == key
    ]
    rows.sort(key=lambda t: (t.traded_at, t.id or 0))
    fills = [t for t in rows if not is_registration_row(t) and _side(t.action)]
    seeds = [t for t in rows if is_holding_seed(t)]

    pauses = [
        r for r in PreTradeReflection.query.filter(PreTradeReflection.user_id == uid).all()
        if r.intended_ticker and ticker_key(r.intended_ticker) == key
    ]
    linked = {int(t.reflection_id) for t in fills if getattr(t, "reflection_id", None)}

    research = research_list_for_ticker(uid, normalized)
    notes = _notes_for(uid, key)

    name = next((t.name for t in reversed(rows) if (t.name or "").strip()), None)
    if not name:
        try:
            from services.name_resolver import resolve_stock_name
            name = resolve_stock_name(normalized) or None
        except Exception:  # best-effort label only
            name = None

    held = [
        p for p in Position.query.filter(Position.user_id == uid).all()
        if p.ticker and ticker_key(p.ticker) == key and (p.shares or 0) > _SHARE_EPSILON
    ]
    holding = None
    if held:
        shares = sum(float(p.shares or 0) for p in held)
        cost = sum(float(p.shares or 0) * float(p.avg_cost or 0) for p in held)
        holding = {
            "shares": shares,
            "avg_cost": (cost / shares) if shares > _SHARE_EPSILON else None,
            "currency": _currency_for(normalized, fills),
        }

    events: list[dict[str, Any]] = []
    # Timeline order for a date-only fill: the end of its KST day (``at``
    # itself stays the stored date).
    order_at: dict[int, str] = {}
    for t in fills:
        e = {
            "kind": "fill",
            "at": _iso(t.traded_at),
            "side": _side(t.action),
            "shares": float(t.shares or 0),
            "price": float(t.price_per_share or 0),
            "currency": (t.currency or "").upper() or None,
            "after_pause": bool(getattr(t, "reflection_id", None)),
        }
        events.append(e)
        if is_date_only(t.traded_at):
            order_at[id(e)] = _iso(_order_at(t.traded_at))
    for t in seeds:
        events.append({
            "kind": "registered",
            "at": _iso(t.traded_at),
            "shares": float(t.shares or 0),
            "price": float(t.price_per_share or 0),
            "currency": (t.currency or "").upper() or None,
        })

    not_taken = 0
    for r in pauses:
        d = r.to_dict(now=now)
        side = _pause_side(r.intended_side)
        started = r.cooldown_started_at or r.created_at
        # A pause before buying that no buy of this name followed — the trade
        # that did not happen. Linked fills count; so does any later buy.
        bought_after = int(r.id) in linked or (
            side == "entry" and started is not None and any(
                _side(t.action) == "buy" and _at_or_after(t.traded_at, started) for t in fills
            )
        )
        if side == "entry" and not bought_after:
            not_taken += 1
        events.append({
            "kind": "pause",
            "at": _iso(r.proceeded_at or r.cancelled_at or started),
            "side": side,
            "rationale": r.rationale,
            "status": d.get("status"),
            "bought_after": bought_after if side == "entry" else None,
        })

    for n in research:
        events.append({
            "kind": "research",
            "at": n.get("created_at"),
            "id": n.get("id"),
            "theses": n.get("theses") or [],
            "invalidation": n.get("invalidation"),
            "verdicts": n.get("verdicts") or [],
            "review_on": n.get("review_on"),
            "reviewed_at": n.get("reviewed_at"),
            "due": n.get("due"),
        })

    for n in notes:
        events.append({
            "kind": "note",
            "at": n.get("created_at"),
            "id": n.get("id"),
            "body": n.get("body"),
            "tags": n.get("tags") or [],
        })

    filings = _filing_block(key, normalized, fills, events)
    if filings:
        events.extend(filings["events"])

    events.sort(key=lambda e: order_at.get(id(e)) or e.get("at") or "", reverse=True)

    return {
        "ticker": normalized,
        "name": name,
        "holding": holding,
        "counts": {
            "fills": len(fills),
            "buys": sum(1 for t in fills if _side(t.action) == "buy"),
            "sells": sum(1 for t in fills if _side(t.action) == "sell"),
            "pauses": len(pauses),
            "not_taken": not_taken,
            "research": len(research),
            "notes": len(notes),
            "filings": len(filings["events"]) if filings else 0,
        },
        "filing_reaction": filings["reaction"] if filings else None,
        "events": events,
    }


__all__ = ["stock_record"]
