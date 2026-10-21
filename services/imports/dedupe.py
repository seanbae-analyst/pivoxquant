"""Duplicate detection for imported fills.

``dedupe_key = sha256(user|ticker-or-name|action|shares|price|traded_at 분)``
(design §데이터). A candidate is a duplicate when the same key already
sits in ``pending_trades`` (any status) or when ``trade_history`` already
holds the same fill — same ticker + side, shares within 1e-6, price within
1e-4, on the same **KST** calendar day (:func:`kst_day`), at a compatible
time (:func:`_same_time`, below).

Times (2026-10-15). The day alone made two genuine fills of one size and
price — 1주 at 09:05 and again at 10:30 — one fill: both arrived pending
(different minute keys) and approving the second was refused. A time is
now compared by how precise each side is (:func:`_precision`):

* ``day`` — no fill time is known: a date-only row (``services.imports
  .is_date_only``), or a ``trade_history`` row no import wrote (a manual
  entry carries a typed date, or the moment it was typed when the date was
  missing; a holding seed carries its registration time). Any time that day
  matches — a manual "2026-09-01" and the same fill imported at 09:05 stay
  one fill.
* ``arrival`` — a time-less webhook row stamped on arrival (below). Its
  stamp only says the fill came no later — a shortcut run at lunch for a
  09:20 fill — so it matches any printed time up to the stamp, and another
  arrival stamp within :data:`UNTIMED_RETRY_WINDOW`.
* ``read`` — a time printed by the source. Within :data:`FILL_TIME_TOLERANCE`.

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

from sqlalchemy import and_

from extensions import db
from models import TradeHistory
from models.import_batch import STATUS_APPROVED, PendingTrade
from services.imports import KST_OFFSET, is_date_only
from services.pre_trade.friction_outcome import _KR_SUFFIXES, ticker_key

SHARES_TOL = 1e-6
PRICE_TOL = 1e-4
# Automation retries (MacroDroid, iOS Shortcuts) re-send within seconds to a
# few minutes. 10 minutes covers that while keeping two genuinely separate,
# identical time-less fills of the same day apart when they are further
# apart than a retry would be. Identical fills inside the window collapse —
# the same trade-off the minute key already makes for timed fills.
UNTIMED_RETRY_WINDOW = timedelta(minutes=10)
# Two readings of one fill, by source precision: notification texts and most
# app screens print HH:MM (text paste, the token webhook's text, /image OCR,
# AI read), broker files and webhook ISO rows usually HH:MM:SS. A minute is
# the clock's wall minute — the seconds are dropped — so a minute reading
# trails the second reading of the same fill by 0–59 s (and a source that
# rounded would sit within ±30 s). Under a minute apart is one fill; two
# identical genuine fills inside one minute collapse — the trade-off the
# minute key already makes.
FILL_TIME_TOLERANCE = timedelta(seconds=60)

DAY, ARRIVAL, READ = "day", "arrival", "read"


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
                 exclude_id: int | None = None, arrival: bool = False) -> bool:
    # A row the user REJECTED must not block the same fill from coming back
    # (mistaken reject → re-upload); every other status still counts.
    q = PendingTrade.query.filter_by(user_id=user_id, dedupe_key=key).filter(
        PendingTrade.status != "rejected"
    )
    if exclude_id is not None:
        q = q.filter(PendingTrade.id != exclude_id)
    if db.session.query(q.exists()).scalar():
        return True

    return history_has_fill(user_id, ticker, action, shares, price, traded_at,
                            arrival=arrival)


def _same_amounts(s1: float, p1: float, s2: float, p2: float) -> bool:
    return abs(float(s1) - float(s2)) <= SHARES_TOL and abs(float(p1) - float(p2)) <= PRICE_TOL


def _precision(traded_at: datetime, *, arrival: bool) -> str:
    """How precise a fill time is (module doc). ``arrival``: stamped on arrival."""
    if is_date_only(traded_at):
        return DAY
    return ARRIVAL if arrival else READ


def _same_time(p1: str, t1: datetime, p2: str, t2: datetime) -> bool:
    """Two same-day times of the same size and price can be one fill."""
    if DAY in (p1, p2):
        return True
    if p1 == p2 == ARRIVAL:
        return abs(t1 - t2) <= UNTIMED_RETRY_WINDOW
    if ARRIVAL in (p1, p2):
        # An arrival stamp only bounds the fill from above: the shortcut ran
        # at or after the fill — at lunch, for a 09:20 fill. Any printed time
        # up to the arrival can be that fill (review 2026-10-15: a 10-minute
        # window let the 09:20 file row of a fill sent at 13:00 in twice).
        arrival, read = (t1, t2) if p1 == ARRIVAL else (t2, t1)
        return read < arrival + FILL_TIME_TOLERANCE
    return abs(t1 - t2) < FILL_TIME_TOLERANCE


def _spellings(tickers) -> list[str]:
    """Every spelling of each ticker (``ticker_key``: ``035720`` · ``.KS`` ·
    ``.KQ`` are one stock — 2026-10-21, the same-stock rule the pause match
    and holdings resync already use). A manual ``035720.KQ`` entry blocked
    nothing when the same fill was imported as ``035720.KS``."""
    out: set[str] = set()
    for t in tickers:
        key = ticker_key(t)
        out.update({t, key, *(key + s for s in _KR_SUFFIXES)})
    return sorted(out)


def _history_fills(user_id: int, tickers: list[str], day_start: datetime,
                   day_end: datetime, action: str | None = None):
    """``trade_history`` rows in ``[day_start, day_end)`` with their time
    precision: ``(ticker, action, shares, price, traded_at, precision)``.
    Only a row an import approval wrote (``pending_trades.approved_trade_id``)
    carries a fill time; every other row is ``day`` (module doc). ``tickers``
    match under every spelling (:func:`_spellings`)."""
    q = (
        db.session.query(TradeHistory.ticker, TradeHistory.action, TradeHistory.shares,
                         TradeHistory.price_per_share, TradeHistory.traded_at,
                         PendingTrade.id, PendingTrade.traded_at, PendingTrade.created_at)
        .outerjoin(PendingTrade, and_(PendingTrade.approved_trade_id == TradeHistory.id,
                                      PendingTrade.user_id == user_id,
                                      PendingTrade.status == STATUS_APPROVED))
        .filter(TradeHistory.user_id == user_id,
                TradeHistory.ticker.in_(_spellings(tickers)),
                TradeHistory.traded_at >= day_start,
                TradeHistory.traded_at < day_end)
    )
    if action is not None:
        q = q.filter(TradeHistory.action == action)
    out = []
    for ticker, act, shares, price, at, pid, p_at, p_created in q.all():
        if shares is None or price is None or at is None:
            continue
        precision = DAY if pid is None else _precision(at, arrival=p_at == p_created)
        out.append((ticker, act, float(shares), float(price), at, precision))
    return out


def history_has_fill(user_id: int, ticker: str | None, action: str,
                     shares: float, price: float, traded_at: datetime,
                     arrival: bool = False) -> bool:
    """``trade_history`` already holds this fill: same ticker, side, KST day,
    shares and price within tolerance, at a compatible time (module doc).
    ``arrival``: ``traded_at`` is a time-less row's arrival stamp."""
    if not ticker:
        return False
    day_start, day_end = _kst_day_bounds(kst_day(traded_at))
    mine = _precision(traded_at, arrival=arrival)
    return any(
        _same_amounts(s, p, shares, price) and _same_time(mine, traded_at, prec, at)
        for _t, _a, s, p, at, prec in _history_fills(user_id, [ticker], day_start, day_end, action)
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
                            row.shares, row.price, row.traded_at,
                            arrival=is_arrival_stamped(row))


def is_arrival_stamped(row: PendingTrade) -> bool:
    """A time-less row: the route stamped ``traded_at`` with its ``created_at``."""
    return row.traded_at is not None and row.traded_at == row.created_at


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
        # (ticker_key, side, KST day) → [(shares, price, traded_at, precision)]
        self.history: dict[tuple[str, str, date], list[tuple[float, float, datetime, str]]] = {}
        if tickers and start is not None and end is not None:
            day_start = _kst_day_bounds(kst_day(start))[0]
            day_end = _kst_day_bounds(kst_day(end))[1]
            for t, a, s, p, at, prec in _history_fills(user_id, list(tickers), day_start, day_end):
                self.history.setdefault((ticker_key(t), a, kst_day(at)), []).append((s, p, at, prec))

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
                     shares: float, price: float, traded_at: datetime,
                     arrival: bool = False) -> bool:
        """Same rule as :func:`is_duplicate` / :func:`history_has_fill`."""
        if key in self.keys:
            return True
        if not ticker:
            return False
        mine = _precision(traded_at, arrival=arrival)
        return any(
            _same_amounts(s, p, shares, price) and _same_time(mine, traded_at, prec, at)
            for s, p, at, prec in self.history.get((ticker_key(ticker), action, kst_day(traded_at)), [])
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
    "make_key", "is_duplicate", "history_has_fill", "already_recorded", "is_arrival_stamped",
    "kst_day", "DedupeIndex", "SHARES_TOL", "PRICE_TOL", "UNTIMED_RETRY_WINDOW",
    "FILL_TIME_TOLERANCE",
]
