# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""user_agent_audit — Journal Companion 2-year regulatory retention table.

Revision ID: 010_user_agent_audit
Revises: 009_earnings_prebrief
Create Date: 2026-04-23

Why
---
Every call to :class:`services.agents.journal_companion.JournalCompanion`
writes one row here (Wave B — the logger is a no-op until the table
exists and counsel has signed off). See ``models/user_agent_audit.py``
for field rationale.

Retention
---------
``purge_after`` is populated at insert time. A nightly cron
(:func:`services.agents.audit_logger.purge_expired`) deletes rows older
than 2 years. Index ``idx_user_agent_audit_purge`` keeps that delete
query O(log n).

Chaining
--------
``down_revision="009_earnings_prebrief"`` keeps Alembic history strictly
linear through the MVP #1–#3 migrations. No branch — avoids a merge
step before the next Wave B migration.
"""
from alembic import op
import sqlalchemy as sa


revision = "010_user_agent_audit"
down_revision = "009_earnings_prebrief"
branch_labels = None
depends_on = None


def upgrade():
    # ── Kill switch (singleton row, id=1) ──────────────────────────────
    # Distributed-safe replacement for an in-memory flag: every dyno reads
    # the same row. Route layer caches for 5s (see routes.agent_admin).
    op.create_table(
        "agent_kill_switch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "killed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("killed_at", sa.DateTime(), nullable=True),
        sa.Column("killed_by", sa.String(length=120), nullable=True),
        sa.Column("killed_reason", sa.String(length=500), nullable=True),
        sa.Column("revived_at", sa.DateTime(), nullable=True),
        sa.Column("revived_by", sa.String(length=120), nullable=True),
        sa.Column("revived_note", sa.String(length=500), nullable=True),
    )

    op.create_table(
        "user_agent_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=12), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("persona_code", sa.String(length=8), nullable=False),
        sa.Column("user_message_hash", sa.String(length=80), nullable=False),
        sa.Column("user_message_len", sa.Integer(), nullable=False),
        sa.Column(
            "raw_output_len",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("gate_verdict", sa.String(length=32), nullable=False),
        sa.Column(
            "gate_reason",
            sa.String(length=120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "model",
            sa.String(length=60),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("purge_after", sa.DateTime(), nullable=False),
    )

    # Single-column indexes (queried frequently on their own)
    op.create_index(
        "idx_user_agent_audit_request_id",
        "user_agent_audit",
        ["request_id"],
    )
    op.create_index(
        "idx_user_agent_audit_user_id",
        "user_agent_audit",
        ["user_id"],
    )
    op.create_index(
        "idx_user_agent_audit_generated_at",
        "user_agent_audit",
        ["generated_at"],
    )

    # Composite indexes (admin dashboards: user timeline / verdict timeline)
    op.create_index(
        "idx_user_agent_audit_user_time",
        "user_agent_audit",
        ["user_id", "generated_at"],
    )
    op.create_index(
        "idx_user_agent_audit_verdict_time",
        "user_agent_audit",
        ["gate_verdict", "generated_at"],
    )

    # Purge horizon — nightly cron scans WHERE purge_after < NOW().
    op.create_index(
        "idx_user_agent_audit_purge",
        "user_agent_audit",
        ["purge_after"],
    )


def downgrade():
    op.drop_index(
        "idx_user_agent_audit_purge", table_name="user_agent_audit"
    )
    op.drop_index(
        "idx_user_agent_audit_verdict_time", table_name="user_agent_audit"
    )
    op.drop_index(
        "idx_user_agent_audit_user_time", table_name="user_agent_audit"
    )
    op.drop_index(
        "idx_user_agent_audit_generated_at", table_name="user_agent_audit"
    )
    op.drop_index(
        "idx_user_agent_audit_user_id", table_name="user_agent_audit"
    )
    op.drop_index(
        "idx_user_agent_audit_request_id", table_name="user_agent_audit"
    )
    op.drop_table("user_agent_audit")
    op.drop_table("agent_kill_switch")
