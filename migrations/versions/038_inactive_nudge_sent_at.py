"""Add ``users.inactive_nudge_sent_at`` for Wave G C-S2 24h onboarding nudge.

Revision ID: 038_inactive_nudge_sent_at
Revises: 038_checkout_expirations, 038_scheduled_emails
Create Date: 2026-05-19

Wave G C-S2 — 24-hour onboarding nudge idempotency column
=========================================================

The hourly cron ``scripts/nightly/inactive_nudge_dispatcher.py`` scans
the rolling [now-25h, now-24h) signup window and sends a 5-minute
getting-started guide to users who have no activity (no artefacts,
positions, or trades). To prevent double-nudging on cron overlap, the
dispatcher writes ``inactive_nudge_sent_at = now()`` after a
successful send and filters ``IS NULL`` on the next pass.

Why a dedicated column instead of a join-table?
-----------------------------------------------
Single per-user write, single per-user read, no growth over time —
the column scales linearly with user count and matches the existing
audit-trail pattern on ``users`` (cf. ``email_opt_out_at`` etc.). A
side table would add an LEFT JOIN to a query that already does
nothing fancier than a 1h time-window slice.

Feature-flag relationship
-------------------------
The column is *unconditionally* added by this migration — it costs
nothing when unused (NULL on every row). The dispatcher itself is
gated by ``PIVOX_INACTIVE_NUDGE_ENABLED`` AND
``PIVOX_CS1_CONSENT_ENABLED`` so the column stays NULL until both
flags are flipped.

Idempotency
-----------
Inspector-pattern (mirrors 023 / 037) — skips ADD COLUMN if the
column already exists. Re-running this migration is a safe no-op.
"""
from alembic import op
import sqlalchemy as sa


revision = "038_inactive_nudge_sent_at"
# Wave G concurrency: three migrations forked off
# ``037_marketing_consent_split`` in parallel (C-M1 checkout_expirations,
# S5 scheduled_emails, C-S2 this one). To collapse the divergent heads
# without an extra merge revision, we declare a tuple ``down_revision``
# so this migration is the joining child of all three predecessors.
# Alembic treats tuples as multi-parent merge points — see
# https://alembic.sqlalchemy.org/en/latest/branches.html#working-with-multiple-bases
down_revision = (
    "038_checkout_expirations",
    "038_scheduled_emails",
)
branch_labels = None
depends_on = None


_NEW_COL = "inactive_nudge_sent_at"


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("users")}

    if _NEW_COL not in existing:
        op.add_column(
            "users",
            sa.Column(_NEW_COL, sa.DateTime(), nullable=True),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("users")}

    if _NEW_COL in existing:
        op.drop_column("users", _NEW_COL)
