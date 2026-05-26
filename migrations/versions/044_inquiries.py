"""inquiries table — customer support tickets.

Revision ID: 044_inquiries
Revises: 043_notification_prefs
Create Date: 2026-05-26

Customer support center backend
===============================
``inquiries`` backs the contact form (``POST /api/support/inquiries``)
and the support chatbot's human-escalation path (``POST /api/support/chat``).
One row per ticket; lifecycle ``open`` → ``answered`` → ``closed``.

Idempotency
-----------
Inspector-pattern create (mirrors 045_funnel_events / position_dd_checks
self-heal). Table-exists check → skip. Re-runnable no-op. Stays in sync
with app.py ``_do_migrations`` boot-time guard (both멱등).

Chain
-----
This wedges between 043_notification_prefs and 045_funnel_events:
``043 → 044 → 045``. 045's ``down_revision`` was repointed from
``043_notification_prefs`` to ``044_inquiries`` in the same change so the
alembic head stays single + linear.
"""
from alembic import op
import sqlalchemy as sa


revision = "044_inquiries"
down_revision = "043_notification_prefs"
branch_labels = None
depends_on = None


_TABLE = "inquiries"


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _TABLE not in inspector.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("category", sa.String(32), nullable=False,
                      server_default="other"),
            sa.Column("subject", sa.String(200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False,
                      server_default="open"),
            sa.Column("admin_reply", sa.Text(), nullable=True),
            sa.Column("email_snapshot", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("answered_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_inquiries_user_id", _TABLE, ["user_id"])
        op.create_index("ix_inquiries_status", _TABLE, ["status"])


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
