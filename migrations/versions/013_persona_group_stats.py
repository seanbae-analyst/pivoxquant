"""persona_group_stats — anonymized group-benchmark aggregates.

Revision ID: 013_persona_group_stats
Revises: 012_companion_waitlist
Create Date: 2026-04-24

Why
---
Backs the Group Benchmark feature — same-persona peer comparison
("Value CFO peer group: avg CAGR 6.2%, median holding 42 days, …").
See reports/product/GROUP_BENCHMARK_SPEC_2026-04-24.md.

Privacy posture
---------------
Rows are strictly aggregate. No user_id FK, no ticker, no individual
identifier. ``suppressed=TRUE`` when ``n_users < 20`` so the API layer
can distinguish "not yet computed" from "legally withheld for
re-identification safety" (개인정보보호법 Art.26-2 / 신용정보법 Art.32).

Chaining
--------
``down_revision="012_companion_waitlist"`` continues the strictly
linear Alembic history.
"""
from alembic import op
import sqlalchemy as sa


revision = "013_persona_group_stats"
down_revision = "012_companion_waitlist"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "persona_group_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("persona", sa.String(length=20), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("n_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "suppressed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # JSON payload — stored as TEXT so SQLite + Postgres stay portable.
        sa.Column("metrics", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_persona_group_stats_persona",
        "persona_group_stats",
        ["persona"],
    )
    op.create_index(
        "ix_persona_group_stats_window_days",
        "persona_group_stats",
        ["window_days"],
    )
    op.create_index(
        "ix_persona_group_stats_computed_at",
        "persona_group_stats",
        ["computed_at"],
    )
    op.create_index(
        "idx_persona_group_stats_persona_window_computed",
        "persona_group_stats",
        ["persona", "window_days", "computed_at"],
    )


def downgrade():
    op.drop_index(
        "idx_persona_group_stats_persona_window_computed",
        table_name="persona_group_stats",
    )
    op.drop_index(
        "ix_persona_group_stats_computed_at",
        table_name="persona_group_stats",
    )
    op.drop_index(
        "ix_persona_group_stats_window_days",
        table_name="persona_group_stats",
    )
    op.drop_index(
        "ix_persona_group_stats_persona",
        table_name="persona_group_stats",
    )
    op.drop_table("persona_group_stats")
