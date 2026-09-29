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

    NEW-D (2026-05-09): the race-safe upsert shared with add_position. See the
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
