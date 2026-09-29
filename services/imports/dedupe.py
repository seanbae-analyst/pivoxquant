"""Duplicate detection for imported fills.

``dedupe_key = sha256(user|ticker-or-name|action|shares|price|traded_at 분)``
(design §데이터). A candidate is a duplicate when the same key already
sits in ``pending_trades`` (any status) or when ``trade_history`` already
holds the same fill — same ticker + side, shares within 1e-6, price within
1e-4, on the same **KST** calendar day (:func:`kst_day`).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from extensions import db
from models import TradeHistory
from models.import_batch import PendingTrade
from services.imports import KST_OFFSET

SHARES_TOL = 1e-6
PRICE_TOL = 1e-4


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
    ident = (ticker_or_name or "").strip().upper()
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
    for r in rows:
        if r.shares is None or r.price_per_share is None:
            continue
        if abs(float(r.shares) - float(shares)) <= SHARES_TOL and \
           abs(float(r.price_per_share) - float(price)) <= PRICE_TOL:
            return True
    return False


class DedupeIndex:
    """One-shot prefetch for a whole batch (review 2026-09-14).

    ``is_duplicate`` costs 2 queries per row; a 2,000-row CSV through the
    Supabase pooler was ~6,000 round trips. This loads the user's existing
    pending keys and the trade_history rows in the batch's date/ticker
    window once, then answers in memory.
    """

    def __init__(self, user_id: int, keys: set[str], tickers: set[str],
                 start: datetime | None, end: datetime | None):
        self.user_id = user_id
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

    def is_duplicate(self, key: str, ticker: str | None, action: str,
                     shares: float, price: float, traded_at: datetime) -> bool:
        if key in self.keys:
            return True
        if not ticker:
            return False
        for s, p in self.history.get((ticker, action, kst_day(traded_at)), []):
            if abs(s - float(shares)) <= SHARES_TOL and abs(p - float(price)) <= PRICE_TOL:
                return True
        return False


__all__ = ["make_key", "is_duplicate", "kst_day", "DedupeIndex", "SHARES_TOL", "PRICE_TOL"]
