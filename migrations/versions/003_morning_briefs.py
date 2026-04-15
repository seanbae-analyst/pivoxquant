"""Create morning_briefs table.

Revision ID: 003_morning_briefs
Revises: 002_password_nullable
Create Date: 2026-04-14

Persists the daily personalized morning briefing that the 06:00 KST
scheduler job generates per user. Unique on (user_id, brief_date) so
the scheduler is idempotent and safe to retry.
"""
from alembic import op
import sqlalchemy as sa


revision = "003_morning_briefs"
down_revision = "002_password_nullable"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "morning_briefs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("brief_date", sa.Date(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "brief_date",
                            name="uq_morning_brief_user_date"),
    )
    op.create_index("ix_morning_briefs_user_id", "morning_briefs", ["user_id"])
    op.create_index("ix_morning_briefs_brief_date", "morning_briefs", ["brief_date"])


def downgrade():
    op.drop_index("ix_morning_briefs_brief_date", table_name="morning_briefs")
    op.drop_index("ix_morning_briefs_user_id", table_name="morning_briefs")
    op.drop_table("morning_briefs")
