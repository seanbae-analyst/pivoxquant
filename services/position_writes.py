"""Shared position-write primitives.

Extracted from ``routes.portfolio.create_position_alias`` so the holdings
capture import (``services/imports/holdings_import.py``) applies exactly the
same user-row lock, free-plan cap and duplicate-merge arithmetic instead of a
second copy. Behaviour is unchanged for the original caller.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db

FREE_POSITION_CAP = 3


def lock_user_row(user_id: int):
    """``SELECT … FOR UPDATE`` on the User row (lock order User→Position, the
    same on every buy/sell/add path → deadlock-free). SQLite no-ops the lock.
    Plain column query — no joined eager loads, so Postgres accepts it."""
    return lock_user_row_query(user_id).one()


def lock_user_row_query(user_id: int):
    """The query ``lock_user_row`` runs (exposed for the PG-dialect compile test)."""
    from models import User
    return db.session.query(User).filter(User.id == user_id).with_for_update()


def is_capped_tier(user) -> bool:
    """True when the free-plan position cap applies to ``user``."""
    return getattr(user, "effective_tier", None) in (None, "free")


def active_position_count(user_id: int) -> int:
    from models import Position
    return Position.query.filter_by(user_id=user_id).filter(Position.shares > 0).count()


def holds_ticker(user_id: int, ticker: str) -> bool:
    """True when ``user_id`` already holds ``ticker`` with shares > 0.

    2026-09-29: the free-plan cap limits the number of *symbols*. Adding shares
    to a symbol already held does not raise that number, so every add path
    checks this first and applies the cap only to a new symbol (the holdings
    import already exempted merges)."""
    from models import Position
    return (
        Position.query.filter_by(user_id=user_id, ticker=ticker)
        .filter(Position.shares > 0)
        .first()
        is not None
    )


def merge_buy_into(ex_row, quantity: float, price: float, *, is_kr: bool,
                   fx_rate: float, note: str | None = None) -> None:
    """Merge a new lot into an existing position: weighted-average cost,
    cost-weighted FX (USD only), thesis filled only if empty.

    NEW-D (2026-05-09): the race-safe upsert. See the
    uq_positions_user_ticker rationale on Position.__table_args__."""
    total = ex_row.shares * ex_row.avg_cost + quantity * price
    if not is_kr and ex_row.buy_fx_rate and fx_rate:
        ex_row.buy_fx_rate = (
            ex_row.buy_fx_rate * ex_row.shares * ex_row.avg_cost
            + fx_rate * quantity * price
        ) / total
    elif not is_kr and not ex_row.buy_fx_rate and fx_rate:
        # Initialize FX on a null/zero existing USD row (see _merge_into).
        ex_row.buy_fx_rate = fx_rate
    ex_row.shares += quantity
    ex_row.avg_cost = total / ex_row.shares
    if note and not ex_row.thesis:
        ex_row.thesis = note
        ex_row.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        ex_row.thesis_status = "pending"


# ── holding-registration seeds ────────────────────────────────────────
# 2026-09-29: registering a holding (POST /positions, the holdings capture
# import) used to write only ``positions``. Every mirror rebuilds FIFO
# lots from ``trade_history`` alone, so selling a registered holding hit an
# empty queue (the 매도 was dropped) and a later add counted as a fresh open.
# A full 매도 deletes the Position row, so the lot cannot be recovered from
# ``positions`` either. Each registration that adds shares therefore writes one
# 매수 row marked ``source="holding_seed"`` — see models/trade_history.py and
# services/profile/fifo_util.is_holding_seed for how consumers treat it.

_SEED_EPSILON = 1e-9


def add_holding_seed(user_id: int, ticker: str, shares: float, price: float,
                     currency: str, name: str | None = None, traded_at=None):
    """Add (not commit) a holding-seed 매수 row for ``shares`` at ``price``.

    ``traded_at`` defaults to now (registration time). No row for a
    non-positive quantity. Returns the row or ``None``."""
    from models.trade_history import HOLDING_SEED_SOURCE

    return _add_registration_row(
        "BUY", HOLDING_SEED_SOURCE,  # // legal-ok — trade action data value, not user copy
        user_id, ticker, shares, price, currency, name, traded_at,
    )


def add_holding_adjust(user_id: int, ticker: str, shares: float, price: float,
                       currency: str, name: str | None = None, traded_at=None):
    """Add (not commit) a holding-adjust 매도 row for ``shares`` at ``price``.

    2026-09-29: written when a registration path (holdings capture
    ``replace`` to a lower count) lowers a holding without a recorded 매도. ``price`` is the position's
    average cost at that moment and ``pnl`` is 0 — it realises nothing. The
    row consumes FIFO lots so they stay in sync with the holding; consumers
    never read it as an observed 매도 (services/profile/fifo_util
    .is_holding_adjust, MatchedPair.sell_is_adjust). No row for a
    non-positive quantity. Returns the row or ``None``."""
    from models.trade_history import HOLDING_ADJUST_SOURCE

    return _add_registration_row(
        "SELL", HOLDING_ADJUST_SOURCE,  # // legal-ok — trade action data value, not user copy
        user_id, ticker, shares, price, currency, name, traded_at,
    )


def _add_registration_row(action: str, source: str, user_id: int, ticker: str,
                          shares, price, currency: str, name, traded_at):
    from models import TradeHistory

    try:
        shares = float(shares or 0.0)
        price = float(price or 0.0)
    except (TypeError, ValueError):
        return None
    if shares <= _SEED_EPSILON:
        return None
    row = TradeHistory(
        user_id=user_id,
        ticker=ticker,
        name=(name or "")[:100],
        action=action,
        shares=shares,
        price_per_share=price,
        total_value=round(shares * price, 2),
        pnl=0.0,
        pnl_pct=0.0,
        currency=currency,
        source=source,
        traded_at=traded_at or datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(row)
    return row
