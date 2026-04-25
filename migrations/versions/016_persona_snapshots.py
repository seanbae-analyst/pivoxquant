"""persona_snapshots — historical PersonaSnapshot rows for Evolution Timeline.

Revision ID: 016_persona_snapshots
Revises: 015_quant_composer
Create Date: 2026-04-25

Why
---
Backs Feature 3+4 (PersonaSnapshot persistence + Evolution Timeline).
Each row is a frozen point-in-time output of
:func:`services.profile.persona_classifier_v2.classify_persona_multi`,
written either by the weekly cron (`persona_snapshot_weekly`) or by the
``POST /api/profile/persona-snapshot`` endpoint.

Goal: let the UI render a timeline of how a user's behavioural persona
drifts over weeks/months — purely *observational* (no recommendation
language anywhere on the read or write path).

Privacy posture
---------------
Every row is FK-bound to a single ``users.id`` and is dropped on
account deletion (``ON DELETE CASCADE``). The historical series is the
**user's own** behaviour over time — never aggregated across users
(that's PersonaGroupStats, migration 013). UNIQUE (user_id, computed_at)
prevents accidental double-writes when the cron coalesces or when a
manual trigger fires inside the same second as the weekly job.

Chaining
--------
``down_revision="015_quant_composer"`` continues the strictly linear
Alembic history. If the parallel agent's 015 ships under a different
slug, update this string before merging — the head MUST stay singular.
"""
from alembic import op
import sqlalchemy as sa


revision = "016_persona_snapshots"
down_revision = "015_quant_composer"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "persona_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("persona", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        # JSON payloads — stored as TEXT so SQLite + Postgres stay portable.
        sa.Column("features", sa.Text(), nullable=False),
        sa.Column("present_mask", sa.Text(), nullable=False),
        sa.Column("ranking", sa.Text(), nullable=False),
        sa.Column("breakdown", sa.Text(), nullable=True),
        sa.Column("declared_persona", sa.String(length=20), nullable=True),
        sa.Column(
            "trade_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "window_days",
            sa.Integer(),
            nullable=False,
            server_default="90",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Confidence is a 0..100 integer — enforce at the DB layer too so
        # a bad service-layer regression can't poison historical data.
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_persona_snapshots_confidence_range",
        ),
        sa.UniqueConstraint(
            "user_id", "computed_at",
            name="uq_persona_snapshots_user_time",
        ),
    )
    # Hot read path: "most-recent-first per user" timeline.
    op.create_index(
        "idx_persona_snapshots_user_time",
        "persona_snapshots",
        ["user_id", sa.text("computed_at DESC")],
    )


def downgrade():
    op.drop_index(
        "idx_persona_snapshots_user_time",
        table_name="persona_snapshots",
    )
    op.drop_table("persona_snapshots")
