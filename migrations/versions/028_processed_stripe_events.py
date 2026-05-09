"""Stripe webhook idempotency — processed_stripe_events table.

Revision ID: 028_processed_stripe_events
Revises: 027_position_unique_user_ticker
Create Date: 2026-05-09

Why this migration
------------------
Stripe retries failed webhook deliveries for up to 3 days with exponential
backoff (https://docs.stripe.com/webhooks/best-practices). Without an
idempotency record keyed on `event["id"]`, the same delivery can be
processed multiple times:

- ``checkout.session.completed`` — current handler does
  ``user.subscription_tier = ...`` (idempotent at the DB level) and
  ``logger.info("User %s subscribed ...", ...)`` (NOT idempotent — duplicate
  audit lines confuse ops dashboards and drift revenue counters).
- ``customer.subscription.updated`` — ordering is not guaranteed across
  retries; a duplicate "active" event arriving after a "canceled" event
  silently re-upgrades the tier.
- ``invoice.paid`` — duplicate revenue logger entries.

The handler in ``routes/billing.py:stripe_webhook`` already verifies the
HMAC signature and never returns 5xx (catches and ACKs 200 to stop retries).
This migration adds the missing dedupe layer:

    INSERT INTO processed_stripe_events (event_id, event_type, status, ...)

with a UNIQUE constraint on ``event_id``. The handler uses
``ProcessedStripeEvent.already_processed(event_id)`` as a fast-path check
before dispatching, and falls back to catching ``IntegrityError`` on the
INSERT to close the race window between two concurrent deliveries.

Why no retention/cleanup in this migration
------------------------------------------
The table grows ~1k rows/day at our forecast scale (Pro+Premium combined),
so a 90-day retention sweep is sufficient and can run as an ops cron later.
We deliberately ship the table without TTL automation — premature scheduling
risks losing audit evidence during incident triage. Add the cleanup job in
a separate revision once we have the first month of prod traffic.

Idempotency
-----------
Mirrors 021/024/025/026/027: every ``op.create_table`` is gated by an
inspector check, and the unique index is created with ``IF NOT EXISTS``
semantics via the same guard. Re-running on a DB that already has the
table is a clean no-op.

Chaining
--------
``down_revision = "027_position_unique_user_ticker"`` — single head.
"""
from alembic import op
import sqlalchemy as sa


revision = "028_processed_stripe_events"
down_revision = "027_position_unique_user_ticker"
branch_labels = None
depends_on = None


_TABLE_NAME = "processed_stripe_events"
_UNIQUE_NAME = "uq_processed_stripe_events_event_id"


def _table_exists(inspector, name: str) -> bool:
    try:
        return name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _table_exists(inspector, _TABLE_NAME):
        # Idempotent re-run — table already present (e.g. post-rollback retry).
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'success'"),
        ),
        sa.Column("error_message", sa.String(length=200), nullable=True),
        sa.UniqueConstraint("event_id", name=_UNIQUE_NAME),
    )
    # Explicit indexes — model declares index=True on event_id (already
    # covered by UNIQUE) and processed_at (used by retention sweep).
    op.create_index(
        "ix_processed_stripe_events_processed_at",
        _TABLE_NAME,
        ["processed_at"],
        unique=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not _table_exists(inspector, _TABLE_NAME):
        return

    try:
        op.drop_index(
            "ix_processed_stripe_events_processed_at",
            table_name=_TABLE_NAME,
        )
    except Exception:
        # Index may not exist on older partial-rollback states.
        pass
    op.drop_table(_TABLE_NAME)
