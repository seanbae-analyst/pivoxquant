"""Wave I C-1 — ``auth_events`` table for OAuth failure detection.

Revision ID: 040_auth_events
Revises: 039_nps_feedback
Create Date: 2026-05-19

Wave I C-1 — OAuth 반복 실패 감지 + 알림
========================================

The OAuth callback paths (``routes/auth.py:google_callback`` /
``kakao_callback``) silently redirect to ``/login?error=...`` on
provisioning / state failures. Without a server-side trail we can't
tell that the *same email* failed 3+ times in the last hour — the
single most actionable early-warning signal for a misconfigured
provider, an expired client secret, or a user stuck in a redirect
loop because their birthdate interstitial 500'd.

Schema rationale
----------------
* ``email`` — lowercased and length-bounded; nullable=False because
  every event we care about has an identifiable principal. State
  failures BEFORE we see the user happen pre-callback and are NOT
  logged here (no email known yet) — they surface in api-health.
* ``provider`` — ``google`` / ``kakao``. String over enum so adding
  a new provider doesn't require a migration.
* ``event_type`` — ``start`` / ``success`` / ``fail``. We log all
  three so the failure-rate is computable as
  ``fail / (fail + success)`` per email.
* ``fail_reason`` — short token ("state_mismatch", "provisioning_failed",
  "google_failed", "kakao_failed", "userinfo_missing"). Nullable —
  populated only on ``event_type='fail'``.
* ``created_at`` — server clock, naive UTC (mirrors ``users.created_at``).

Indexing
--------
The hot query is
    SELECT email, COUNT(*) FROM auth_events
    WHERE event_type='fail' AND created_at >= now() - INTERVAL '1 hour'
    GROUP BY email HAVING COUNT(*) >= 3;
A composite index on ``(email, event_type, created_at)`` makes the
predicate index-only. Individual ``created_at`` index supports a
window-only fast path for retention cleanup.

Retention
---------
The PIPA purge cron (Wave I C-2) treats ``auth_events`` as
PIPA-personal-data (the ``email`` column). On user hard-delete the
rows are SHA256-hashed in place (NOT deleted) so aggregate audit
remains while the principal is unidentifiable. See
``scripts/nightly/pipa_purge.py``.

Idempotency
-----------
Inspector-pattern — skips CREATE TABLE if the table already exists.
"""
from alembic import op
import sqlalchemy as sa


revision = "040_auth_events"
down_revision = "039_nps_feedback"
branch_labels = None
depends_on = None


_TABLE = "auth_events"


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        # ``email`` is store-key; we deliberately do NOT FK to users.id
        # because a fail can fire before the user row exists (or after
        # it is deleted). String(255) matches RFC 5321 max length.
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("fail_reason", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('start', 'success', 'fail')",
            name="ck_auth_events_event_type",
        ),
        sa.CheckConstraint(
            "provider IN ('google', 'kakao')",
            name="ck_auth_events_provider",
        ),
    )
    # Composite index — primary read path is per-email-per-window failure count.
    op.create_index(
        "ix_auth_events_email_event_created",
        _TABLE,
        ["email", "event_type", "created_at"],
    )
    # Secondary index — window-only retention sweeps + ops dashboards.
    op.create_index(
        "ix_auth_events_created_at",
        _TABLE,
        ["created_at"],
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        op.drop_index("ix_auth_events_email_event_created", table_name=_TABLE)
        op.drop_index("ix_auth_events_created_at", table_name=_TABLE)
        op.drop_table(_TABLE)
