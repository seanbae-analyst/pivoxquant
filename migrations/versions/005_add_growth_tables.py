"""Add Growth OS tables — daily logs, reflections, scores, weekly reports.

Revision ID: 005_growth_tables
Revises: 004_agent_tables
Create Date: 2026-04-17

Solo Founder Growth OS v1:
- growth_daily_logs: morning briefing + system-collected activity data
- growth_reflections: AI-generated questions + user answers
- growth_scores: daily composite score (activity + reflection + streak)
- growth_weekly_reports: AI-generated weekly summaries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005_growth_tables"
down_revision = "004_agent_tables"
branch_labels = None
depends_on = None


def upgrade():
    # ── growth_daily_logs ────────────────────────────────────────────────
    op.create_table(
        "growth_daily_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column(
            "type",
            sa.String(length=20),
            nullable=False,
            comment="briefing | system | manual",
        ),
        sa.Column(
            "priorities",
            postgresql.JSONB(),
            nullable=True,
            comment="Top 3 priorities for the day",
        ),
        sa.Column(
            "motivation",
            sa.Text(),
            nullable=True,
            comment="One-liner motivational message",
        ),
        sa.Column(
            "actual_done",
            postgresql.JSONB(),
            nullable=True,
            comment="Items actually completed (updated in the evening)",
        ),
        sa.Column(
            "raw_response",
            sa.Text(),
            nullable=True,
            comment="Full Claude API response for audit",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── growth_reflections ───────────────────────────────────────────────
    op.create_table(
        "growth_reflections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "questions",
            postgresql.JSONB(),
            nullable=False,
            comment="AI-generated reflection questions (list of 3)",
        ),
        sa.Column(
            "answers",
            postgresql.JSONB(),
            nullable=True,
            comment="User answers (null until submitted)",
        ),
        sa.Column(
            "mood",
            sa.Integer(),
            nullable=True,
            comment="User mood 1-5 (null until submitted)",
        ),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column(
            "raw_response",
            sa.Text(),
            nullable=True,
            comment="Full Claude API response for audit",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "mood IS NULL OR mood BETWEEN 1 AND 5",
            name="ck_growth_reflections_mood_range",
        ),
    )
    op.create_index(
        "idx_growth_reflections_date",
        "growth_reflections",
        ["date"],
    )

    # ── growth_scores ────────────────────────────────────────────────────
    # NOTE: PostgreSQL GENERATED ALWAYS AS ... STORED requires the expression
    # to use only immutable functions. LEAST is immutable but the mixed
    # integer/float arithmetic is fine. We cast to INTEGER for clean output.
    op.create_table(
        "growth_scores",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column(
            "activity_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="0-100: activity level (commits, tasks done)",
        ),
        sa.Column(
            "reflection_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="0-100: reflection depth (answer length, insight)",
        ),
        sa.Column(
            "streak_days",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Consecutive usage days",
        ),
        sa.Column(
            "total_score",
            sa.Integer(),
            sa.Computed(
                "CAST("
                "activity_score * 0.4 "
                "+ reflection_score * 0.4 "
                "+ LEAST(streak_days, 30) * 0.67 "
                "AS INTEGER)",
                persisted=True,
            ),
            comment="Composite score (auto-computed)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_growth_scores_range",
        "growth_scores",
        ["date"],
    )

    # ── growth_weekly_reports ────────────────────────────────────────────
    op.create_table(
        "growth_weekly_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "week_start",
            sa.Date(),
            nullable=False,
            unique=True,
            comment="Monday of the report week",
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "patterns",
            postgresql.JSONB(),
            nullable=True,
            comment="Discovered patterns",
        ),
        sa.Column(
            "growth_areas",
            postgresql.JSONB(),
            nullable=True,
            comment="Growth highlights with evidence",
        ),
        sa.Column(
            "next_week_suggestions",
            postgresql.JSONB(),
            nullable=True,
            comment="Actionable items for next week",
        ),
        sa.Column(
            "week_score",
            sa.Integer(),
            nullable=True,
            comment="Aggregate score for the week",
        ),
        sa.Column(
            "raw_response",
            sa.Text(),
            nullable=True,
            comment="Full Claude API response for audit",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("growth_weekly_reports")
    op.drop_index("idx_growth_scores_range", table_name="growth_scores")
    op.drop_table("growth_scores")
    op.drop_index("idx_growth_reflections_date", table_name="growth_reflections")
    op.drop_table("growth_reflections")
    op.drop_table("growth_daily_logs")
