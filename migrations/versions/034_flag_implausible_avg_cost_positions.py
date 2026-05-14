"""Flag implausibly-low avg_cost positions for manual review (Bug #4).

Revision ID: 034_flag_implausible_avg_cost
Revises: 033_normalize_kr_position_tickers
Create Date: 2026-05-14

Why this migration
------------------
A test/typo position polluted production: an AAPL row carried
``avg_cost = 30.0``. AAPL has not traded near $30 since 2013, so the
portfolio equity-curve calculation produced a +593,259% six-month
return (live bug-hunt 2026-05-14, Bug #4). The position-write paths in
``routes/portfolio.py`` had no sanity check on ``avg_cost``.

The route-level guard (``_avg_cost_implausible`` in routes/portfolio.py,
landed in this same branch) stops *future* bad writes by validating
against the ticker's live 52-week low. This migration addresses the
rows already in the table.

Why detection-only (no auto-mutation)
-------------------------------------
This migration deliberately does NOT rewrite avg_cost values. A
migration cannot reach a live price API to learn the *correct* cost
basis, and inventing a plausible-looking number (e.g. "$180") would be
data fabrication — a worse outcome than the visible bug, because it
silently destroys the only record of what the user actually entered.

Instead it *detects* implausibly-low rows against a conservative,
hardcoded multi-year-low floor map for a set of well-known, highly
liquid large-caps (values that are historically stable and need no
live lookup) and logs each match with full identifying detail. An
operator then makes the correction (or contacts the user) manually —
a human decision, which is the safe default for destructive data
changes (same rationale as 033's collision guard).

For the AAPL=$30 pollution specifically: AAPL's multi-year low floor
here is $120 (well below any realistic recent cost basis, well above
the $30 typo). The row is flagged, not touched.

Idempotency
-----------
This migration only reads + logs. It performs no writes. Re-running is
a pure no-op and is always safe.

Reversibility
-------------
``downgrade()`` is a no-op — there is nothing to undo because
``upgrade()`` mutates no rows.

NOT run against production here
-------------------------------
Created and locally verified only. Production (Railway PostgreSQL)
execution is gated on CEO approval per the PR workflow. Because this
migration is read-only, running it in production is risk-free — it
only emits a log report an operator can act on.
"""
from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")

revision = "034_flag_implausible_avg_cost"
down_revision = "033_normalize_kr_position_tickers"
branch_labels = None
depends_on = None


# Conservative multi-year-low floors for well-known, highly liquid
# large-caps. These are intentionally set WELL BELOW any realistic
# recent cost basis (so a legitimate deep-discount holder is never
# flagged) but WELL ABOVE the order-of-magnitude typo this guards
# against (e.g. AAPL $30). Values are historically stable — no live
# lookup needed. Extend the map as new pollution patterns surface.
_MULTI_YEAR_LOW_FLOOR: dict[str, float] = {
    "AAPL": 120.0,
    "MSFT": 200.0,
    "GOOGL": 80.0,
    "GOOG": 80.0,
    "AMZN": 80.0,
    "META": 80.0,
    "NVDA": 100.0,
    "TSLA": 100.0,
    "NFLX": 150.0,
}


def upgrade() -> None:
    conn = op.get_bind()
    positions = sa.table(
        "positions",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("ticker", sa.String),
        sa.column("avg_cost", sa.Float),
    )

    rows = conn.execute(
        sa.select(
            positions.c.id,
            positions.c.user_id,
            positions.c.ticker,
            positions.c.avg_cost,
        )
    ).fetchall()

    flagged = 0
    for row in rows:
        ticker = (row.ticker or "").strip().upper()
        floor = _MULTI_YEAR_LOW_FLOOR.get(ticker)
        if floor is None:
            continue
        avg_cost = row.avg_cost
        if avg_cost is None or avg_cost <= 0:
            continue
        if avg_cost < floor:
            flagged += 1
            logger.warning(
                "034 migration: IMPLAUSIBLE avg_cost — position id=%s "
                "user_id=%s ticker=%s avg_cost=%.4f is below the "
                "multi-year-low floor %.2f. NOT auto-corrected; manual "
                "review required (likely a data-entry typo / test "
                "pollution — see Bug #4).",
                row.id, row.user_id, ticker, avg_cost, floor,
            )

    if flagged:
        logger.warning(
            "034 migration: %s implausible-avg_cost position(s) flagged "
            "for manual review. No rows were modified.",
            flagged,
        )
    else:
        logger.info(
            "034 migration: no implausible-avg_cost positions found "
            "(scanned %s rows). No-op.",
            len(rows),
        )


def downgrade() -> None:
    """No-op — upgrade() mutates no rows, so there is nothing to revert."""
    logger.info("034 downgrade: no-op (upgrade was read-only).")
