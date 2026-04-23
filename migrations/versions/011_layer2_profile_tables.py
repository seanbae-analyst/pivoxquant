"""Layer 2 CFO dashboard tables — artifact_feedback + weekly_pulse.

Revision ID: 011_layer2_profile_tables
Revises: 010_user_agent_audit
Create Date: 2026-04-23

Why
---
Adds two new persistence surfaces for Living CFO Layer 2 (Wave 3):

- ``artifact_feedback`` : per-section votes (useful/meh/skip) on rendered
  CFO artifacts. Read by the future persona-refinement cron; write path
  is ``POST /api/profile/feedback``.
- ``weekly_pulse`` : self-reported mood / confidence / worry / topics /
  learn entries submitted on a weekly/biweekly/monthly cadence. Read by
  ``GET /api/profile/pulse``; write path is ``POST /api/profile/pulse``.

Both tables carry a user_id FK with ``ON DELETE CASCADE`` so the GDPR /
PIPA account-deletion path stays O(n) without manual cleanup.

Chaining
--------
``down_revision="010_user_agent_audit"`` keeps Alembic history strictly
linear (no branch / merge). Next migration should set
``down_revision="011_layer2_profile_tables"``.
"""
from alembic import op
import sqlalchemy as sa


revision = "011_layer2_profile_tables"
down_revision = "010_user_agent_audit"
branch_labels = None
depends_on = None


def upgrade():
    # ── artifact_feedback ──────────────────────────────────────────
    op.create_table(
        "artifact_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("section", sa.String(length=80), nullable=False),
        sa.Column("vote", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_artifact_feedback_user_id",
        "artifact_feedback",
        ["user_id"],
    )
    op.create_index(
        "ix_artifact_feedback_artifact_id",
        "artifact_feedback",
        ["artifact_id"],
    )
    op.create_index(
        "ix_artifact_feedback_created_at",
        "artifact_feedback",
        ["created_at"],
    )
    op.create_index(
        "idx_artifact_feedback_user_artifact_section",
        "artifact_feedback",
        ["user_id", "artifact_id", "section"],
    )

    # ── weekly_pulse ────────────────────────────────────────────────
    op.create_table(
        "weekly_pulse",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mood", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("worry", sa.String(length=500), server_default=""),
        sa.Column("topics", sa.Text(), server_default="[]"),
        sa.Column("learn", sa.String(length=500), server_default=""),
        sa.Column(
            "cadence",
            sa.String(length=16),
            nullable=False,
            server_default="weekly",
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_weekly_pulse_user_id",
        "weekly_pulse",
        ["user_id"],
    )
    op.create_index(
        "ix_weekly_pulse_submitted_at",
        "weekly_pulse",
        ["submitted_at"],
    )
    op.create_index(
        "idx_weekly_pulse_user_submitted",
        "weekly_pulse",
        ["user_id", "submitted_at"],
    )


def downgrade():
    op.drop_index("idx_weekly_pulse_user_submitted", table_name="weekly_pulse")
    op.drop_index("ix_weekly_pulse_submitted_at", table_name="weekly_pulse")
    op.drop_index("ix_weekly_pulse_user_id", table_name="weekly_pulse")
    op.drop_table("weekly_pulse")

    op.drop_index(
        "idx_artifact_feedback_user_artifact_section",
        table_name="artifact_feedback",
    )
    op.drop_index(
        "ix_artifact_feedback_created_at",
        table_name="artifact_feedback",
    )
    op.drop_index(
        "ix_artifact_feedback_artifact_id",
        table_name="artifact_feedback",
    )
    op.drop_index(
        "ix_artifact_feedback_user_id",
        table_name="artifact_feedback",
    )
    op.drop_table("artifact_feedback")
