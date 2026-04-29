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
    # NOTE 2026-04-29: Morning Brief 기능 제거(commit a7a09ef). 그러나 production
    # DB에는 이미 morning_briefs 테이블이 존재 → 매 deploy마다 alembic이 이
    # migration을 시도하면서 DuplicateTable 에러로 fail (chain 멈춤).
    # idempotent 처리: 테이블이 이미 있으면 skip.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("morning_briefs"):
        return  # already exists — skip
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("morning_briefs"):
        return
    op.drop_index("ix_morning_briefs_brief_date", table_name="morning_briefs")
    op.drop_index("ix_morning_briefs_user_id", table_name="morning_briefs")
    op.drop_table("morning_briefs")
