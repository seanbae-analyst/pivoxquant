"""Normalize bare 6-digit KR position tickers to .KS / .KQ (FINDING-010).

Revision ID: 033_normalize_kr_position_tickers
Revises: 032_users_is_simulated
Create Date: 2026-05-14

Why this migration
------------------
``routes/portfolio.py`` decides KR vs US treatment with
``ticker.upper().endswith(".KS") or .endswith(".KQ")``. A position row
stored as a bare 6-digit code (e.g. ``"005930"``) fails that probe →
``is_kr = False`` → the position is valued in USD, the FX divide is
skipped, and a Samsung holding surfaces as a multi-million-dollar NAV
(FINDING-010 / FINDING-021).

The ``normalize_ticker`` input-boundary fix landed 2026-05-13, but it
only canonicalises *new* writes. Rows inserted before that fix still
carry bare codes. This migration backfills them.

KOSPI vs KOSDAQ
---------------
A blind ``ticker || '.KS'`` is wrong for KOSDAQ names (035760 CJ ENM is
``.KQ``). We reuse ``services.ticker_normalizer.normalize_ticker`` —
the single source of truth — which probes the curated + full KRX
registries to pick the correct suffix, falling back to ``.KS`` only
when neither registry has the code.

Unique-constraint safety
------------------------
``positions`` has ``uq_positions_user_ticker (user_id, ticker)``. If a
user somehow already holds *both* ``005930`` and ``005930.KS``, renaming
the bare row would violate the constraint. We detect that collision and
**skip** the bare row (left untouched, logged) rather than fail the
whole migration or silently destroy data — a manual merge decision is
safer than an automatic one. In practice this collision is not expected
(the bare form predates the suffixed form), but the guard makes the
migration safe to run unconditionally.

Idempotency
-----------
Only rows matching ``^[0-9]{6}$`` are touched. After a successful run no
such rows remain, so a re-run is a no-op. Re-running is also safe if new
bare rows somehow appear later.

Reversibility
-------------
``downgrade()`` strips the ``.KS`` / ``.KQ`` suffix from 6-digit KR
tickers, returning them to the bare form. This is a faithful inverse for
rows this migration touched. Note it also affects any *correctly*
suffixed KR rows created after the upgrade — that is the unavoidable
cost of a data migration with no per-row provenance marker, and is
acceptable because downgrade is an emergency-rollback path only.

NOT run against production here
-------------------------------
This file is created and locally verified only. Production (Railway
PostgreSQL) execution is gated on CEO approval per the PR workflow.
"""
from __future__ import annotations

import logging
import re

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")

revision = "033_normalize_kr_position_tickers"
down_revision = "032_users_is_simulated"
branch_labels = None
depends_on = None

_SIX_DIGIT = re.compile(r"^[0-9]{6}$")


def _normalize(code: str) -> str:
    """Resolve a bare 6-digit code to its canonical .KS/.KQ form.

    Delegates to the project's single source of truth. Falls back to
    ``.KS`` (the legacy default) if the normalizer module cannot be
    imported in the migration context for any reason.
    """
    try:
        from services.ticker_normalizer import normalize_ticker
        norm = normalize_ticker(code)
        if norm.endswith(".KS") or norm.endswith(".KQ"):
            return norm
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "033 migration: normalize_ticker unavailable for %s (%s); "
            "defaulting to .KS",
            code, exc,
        )
    return f"{code}.KS"


def upgrade() -> None:
    conn = op.get_bind()
    positions = sa.table(
        "positions",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("ticker", sa.String),
    )

    rows = conn.execute(
        sa.select(positions.c.id, positions.c.user_id, positions.c.ticker)
    ).fetchall()

    renamed = 0
    skipped = 0
    for row in rows:
        ticker = (row.ticker or "").strip()
        if not _SIX_DIGIT.match(ticker):
            continue

        target = _normalize(ticker)
        if target == ticker:  # pragma: no cover - normalizer guarantees suffix
            continue

        # uq_positions_user_ticker collision guard: does this user already
        # hold the suffixed form?
        collision = conn.execute(
            sa.select(positions.c.id).where(
                sa.and_(
                    positions.c.user_id == row.user_id,
                    positions.c.ticker == target,
                )
            )
        ).first()
        if collision is not None:
            logger.warning(
                "033 migration: skipping position id=%s user=%s — bare "
                "ticker %r would collide with existing %r; manual merge "
                "required",
                row.id, row.user_id, ticker, target,
            )
            skipped += 1
            continue

        conn.execute(
            positions.update()
            .where(positions.c.id == row.id)
            .values(ticker=target)
        )
        renamed += 1

    logger.info(
        "033 migration: normalized %s bare KR position ticker(s), "
        "skipped %s due to collision",
        renamed, skipped,
    )


def downgrade() -> None:
    """Strip .KS/.KQ from 6-digit KR tickers, restoring the bare form.

    Emergency-rollback path only. Collision against an existing bare row
    for the same user is skipped (same guard rationale as upgrade()).
    """
    conn = op.get_bind()
    positions = sa.table(
        "positions",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("ticker", sa.String),
    )

    rows = conn.execute(
        sa.select(positions.c.id, positions.c.user_id, positions.c.ticker)
    ).fetchall()

    reverted = 0
    skipped = 0
    suffixed = re.compile(r"^([0-9]{6})\.(KS|KQ)$")
    for row in rows:
        ticker = (row.ticker or "").strip().upper()
        m = suffixed.match(ticker)
        if not m:
            continue
        bare = m.group(1)

        collision = conn.execute(
            sa.select(positions.c.id).where(
                sa.and_(
                    positions.c.user_id == row.user_id,
                    positions.c.ticker == bare,
                )
            )
        ).first()
        if collision is not None:
            logger.warning(
                "033 downgrade: skipping position id=%s — %r would "
                "collide with existing %r",
                row.id, ticker, bare,
            )
            skipped += 1
            continue

        conn.execute(
            positions.update()
            .where(positions.c.id == row.id)
            .values(ticker=bare)
        )
        reverted += 1

    logger.info(
        "033 downgrade: reverted %s KR position ticker(s) to bare form, "
        "skipped %s",
        reverted, skipped,
    )
