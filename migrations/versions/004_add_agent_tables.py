"""Create agent worker tables — tasks, decisions, and daily budget.

Revision ID: 004_agent_tables
Revises: 003_morning_briefs
Create Date: 2026-04-16

Backing store for the autonomous agent worker (see agent_worker/).
- agent_tasks: task queue with status, risk, escalation, retries, chain depth.
- agent_decisions: immutable audit trail of every Claude call + token cost.
- agent_budget: per-day hard cap; set halted=TRUE to stop all agent spend.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "004_agent_tables"
down_revision = "003_morning_briefs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("assigned_to", sa.String(length=50), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "parent_task_id",
            sa.Integer(),
            sa.ForeignKey("agent_tasks.id"),
            nullable=True,
        ),
        sa.Column(
            "chain_depth", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "risk_score", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "retry_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "max_retries", sa.Integer(), nullable=False, server_default="3"
        ),
        sa.CheckConstraint(
            "risk_score BETWEEN 0 AND 100", name="ck_agent_tasks_risk_range"
        ),
    )
    op.create_index(
        "idx_agent_tasks_pending",
        "agent_tasks",
        ["status", "assigned_to"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "idx_agent_tasks_chain", "agent_tasks", ["parent_task_id"]
    )

    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("agent", sa.String(length=50), nullable=False),
        sa.Column("decision_type", sa.String(length=50), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("prompt_snapshot", sa.Text(), nullable=True),
        sa.Column("response_snapshot", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 100",
            name="ck_agent_decisions_confidence_range",
        ),
    )
    op.create_index(
        "idx_agent_decisions_task", "agent_decisions", ["task_id"]
    )

    op.create_table(
        "agent_budget",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column(
            "tokens_used", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "daily_cap_usd",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="5.00",
        ),
        sa.Column(
            "halted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade():
    op.drop_table("agent_budget")
    op.drop_index("idx_agent_decisions_task", table_name="agent_decisions")
    op.drop_table("agent_decisions")
    op.drop_index("idx_agent_tasks_chain", table_name="agent_tasks")
    op.drop_index("idx_agent_tasks_pending", table_name="agent_tasks")
    op.drop_table("agent_tasks")
