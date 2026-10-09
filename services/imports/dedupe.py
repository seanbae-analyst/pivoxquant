"""Duplicate detection for imported fills.

``dedupe_key = sha256(user|ticker-or-name|action|shares|price|traded_at 분)``
(design §데이터). A candidate is a duplicate when the same key already
sits in ``pending_trades`` (any status) or when ``trade_history`` already
holds the same fill — same ticker + side, shares within 1e-6, price within
1e-4, on the same **KST** calendar day (:func:`kst_day`).

Time-less fills (2026-10-09). A webhook row with no ``traded_at`` is stamped
with the server's arrival time, so a phone automation re-sending the same
post a minute later produced a different minute in the key and a second
pending row. The payload carries no idempotency / order id to key on, so
such a row is compared with the user's other time-less rows by everything
but the time — same ticker-or-name, side, shares, price — within
:data:`UNTIMED_RETRY_WINDOW` (:meth:`DedupeIndex.is_untimed_retry`). A
time-less row is recognisable in the table without a new column: the route
stamps ``traded_at`` and ``created_at`` with the same ``now``.

Approval re-check: :func:`already_recorded` runs at approve time, so a row
that was not flagged at intake (a manual entry or another approval landed
since) never writes the same fill to ``trade_history`` twice.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from extensions import db
from models import TradeHistory
from models.import_batch import STATUS_APPROVED, PendingTrade
from services.imports import KST_OFFSET

SHARES_TOL = 1e-6
PRICE_TOL = 1e-4
# Automation retries (MacroDroid, iOS Shortcuts) re-send within seconds to a
# few minutes. 10 minutes covers that while keeping two genuinely separate,
# identical time-less fills of the same day apart when they are further
# apart than a retry would be. Identical fills inside the window collapse —
# the same trade-off the minute key already makes for timed fills.
UNTIMED_RETRY_WINDOW = timedelta(minutes=10)


def kst_day(traded_at: datetime) -> date:
    """The user's (Asia/Seoul) calendar day of a stored ``traded_at``.

    Timed fills are stored in UTC; date-only ones are stamped with the KST
    date at 00:00, unshifted (``services.imports.kst_to_utc``). ``+9h`` gives
    the KST day for both: a 00:00 stamp stays on its own date. Bucketing by
    the UTC day split a 00:00–09:00 KST fill (UTC: the day before) from the
    same fill arriving date-only (2026-09-29)."""
    return (traded_at + KST_OFFSET).date()


def _kst_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Stored-``traded_at`` range ``[start, end)`` whose :func:`kst_day` is ``day``."""
    start = datetime(day.year, day.month, day.day) - KST_OFFSET
    return start, start + timedelta(days=1)


def make_key(user_id: int, ticker_or_name: str, action: str, shares: float,
             price: float, traded_at: datetime) -> str:
    ident = _ident(ticker_or_name)
    minute = traded_at.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
    raw = f"{user_id}|{ident}|{action}|{float(shares):.6f}|{float(price):.4f}|{minute}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_duplicate(user_id: int, key: str, ticker: str | None, action: str,
                 shares: float, price: float, traded_at: datetime,
                 exclude_id: int | None = None) -> bool:
    # A row the user REJECTED must not block the same fill from coming back
    # (mistaken reject → re-upload); every other status still counts.
    q = PendingTrade.query.filter_by(user_id=user_id, dedupe_key=key).filter(
        PendingTrade.status != "rejected"
    )
    if exclude_id is not None:
        q = q.filter(PendingTrade.id != exclude_id)
    if db.session.query(q.exists()).scalar():
        return True

    return history_has_fill(user_id, ticker, action, shares, price, traded_at)


def _same_amounts(s1: float, p1: float, s2: float, p2: float) -> bool:
    return abs(float(s1) - float(s2)) <= SHARES_TOL and abs(float(p1) - float(p2)) <= PRICE_TOL


def history_has_fill(user_id: int, ticker: str | None, action: str,
                     shares: float, price: float, traded_at: datetime) -> bool:
    """``trade_history`` already holds this fill (same KST day, ticker, side,
    shares and price within tolerance)."""
    if not ticker:
        return False
    day_start, day_end = _kst_day_bounds(kst_day(traded_at))
    rows = (
        TradeHistory.query
        .filter(
            TradeHistory.user_id == user_id,
            TradeHistory.ticker == ticker,
            TradeHistory.action == action,
            TradeHistory.traded_at >= day_start,
            TradeHistory.traded_at < day_end,
        )
        .all()
    )
    return any(
        _same_amounts(r.shares, r.price_per_share, shares, price)
        for r in rows
        if r.shares is not None and r.price_per_share is not None
    )


def already_recorded(row: PendingTrade) -> bool:
    """Approve-time re-check for ``row``: another approved row with the same
    key, or the fill already in ``trade_history``. Other *pending* rows with
    the key do not count — refusing on them would leave neither approvable."""
    approved = PendingTrade.query.filter(
        PendingTrade.user_id == row.user_id,
        PendingTrade.dedupe_key == row.dedupe_key,
        PendingTrade.status == STATUS_APPROVED,
        PendingTrade.id != row.id,
    )
    if db.session.query(approved.exists()).scalar():
        return True
    return history_has_fill(row.user_id, row.ticker, row.action,
                            row.shares, row.price, row.traded_at)


class DedupeIndex:
    """One-shot prefetch for a whole batch (review 2026-09-14).

    ``is_duplicate`` costs 2 queries per row; a 2,000-row CSV through the
    Supabase pooler was ~6,000 round trips. This loads the user's existing
    pending keys and the trade_history rows in the batch's date/ticker
    window once, then answers in memory.
    """

    def __init__(self, user_id: int, keys: set[str], tickers: set[str],
                 start: datetime | None, end: datetime | None,
                 untimed_since: datetime | None = None):
        """``untimed_since``: load the user's time-less rows created since
        then for :meth:`is_untimed_retry` (None = the batch has none)."""
        self.user_id = user_id
        self.untimed: dict[tuple[str, str], list[tuple[float, float]]] = {}
        if untimed_since is not None:
            self._load_untimed(untimed_since)
        self.keys: set[str] = set()
        if keys:
            rows = (
                db.session.query(PendingTrade.dedupe_key)
                .filter(PendingTrade.user_id == user_id,
                        PendingTrade.dedupe_key.in_(list(keys)),
                        PendingTrade.status != "rejected")
                .all()
            )
            self.keys = {r[0] for r in rows}
        self.history: dict[tuple[str, str, date], list[tuple[float, float]]] = {}
        if tickers and start is not None and end is not None:
            day_start = _kst_day_bounds(kst_day(start))[0]
            day_end = _kst_day_bounds(kst_day(end))[1]
            hist = (
                TradeHistory.query
                .filter(TradeHistory.user_id == user_id,
                        TradeHistory.ticker.in_(list(tickers)),
                        TradeHistory.traded_at >= day_start,
                        TradeHistory.traded_at < day_end)
                .all()
            )
            for r in hist:
                if r.shares is None or r.price_per_share is None or r.traded_at is None:
                    continue
                k = (r.ticker, r.action, kst_day(r.traded_at))
                self.history.setdefault(k, []).append((float(r.shares), float(r.price_per_share)))

    def _load_untimed(self, since: datetime) -> None:
        rows = (
            db.session.query(PendingTrade.ticker, PendingTrade.name, PendingTrade.action,
                             PendingTrade.shares, PendingTrade.price)
            .filter(PendingTrade.user_id == self.user_id,
                    PendingTrade.status != "rejected",
                    PendingTrade.created_at >= since,
                    # server-stamped: the route set both from one ``now``
                    PendingTrade.traded_at == PendingTrade.created_at)
            .all()
        )
        for ticker, name, action, shares, price in rows:
            k = (_ident(ticker or name), action)
            self.untimed.setdefault(k, []).append((float(shares), float(price)))

    def is_duplicate(self, key: str, ticker: str | None, action: str,
                     shares: float, price: float, traded_at: datetime) -> bool:
        if key in self.keys:
            return True
        if not ticker:
            return False
        return any(
            _same_amounts(s, p, shares, price)
            for s, p in self.history.get((ticker, action, kst_day(traded_at)), [])
        )

    def is_untimed_retry(self, ticker_or_name: str, action: str,
                         shares: float, price: float) -> bool:
        """A time-less row matching an earlier time-less row in the window."""
        return any(
            _same_amounts(s, p, shares, price)
            for s, p in self.untimed.get((_ident(ticker_or_name), action), [])
        )


def _ident(ticker_or_name: str | None) -> str:
    return (ticker_or_name or "").strip().upper()


__all__ = [
    "make_key", "is_duplicate", "history_has_fill", "already_recorded", "kst_day",
    "DedupeIndex", "SHARES_TOL", "PRICE_TOL", "UNTIMED_RETRY_WINDOW",
]
