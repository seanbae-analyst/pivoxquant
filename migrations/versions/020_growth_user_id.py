"""Growth OS — add user_id to growth_reflections + growth_scores (SEC-005 IDOR fix).

Revision ID: 020_growth_user_id
Revises: 019_ai_twin
Create Date: 2026-05-02

Why
---
Issue SEC-005 (HIGH): The original schema for ``growth_reflections`` and
``growth_scores`` (migration ``005_add_growth_tables.py``) does not include
a ``user_id`` column. Both tables key off ``date`` only, which means:

1. Any authenticated user can read/update another user's reflection by
   guessing ``reflection_id`` (Insecure Direct Object Reference / IDOR).
2. ``growth_scores`` is keyed solely on ``date`` — every user shares the
   same daily score row, which is a correctness bug as soon as a second
   user signs up.

Fix
---
- Add nullable ``user_id`` column.
- Backfill existing rows with ``user_id = 0`` (orphan / founder bucket).
  Operators clean up orphans manually after deploy if needed.
- Make ``user_id`` NOT NULL.
- Add an index on ``user_id`` for query performance.
- For ``growth_scores``, add a composite UNIQUE constraint on
  ``(user_id, date)`` so each user gets their own daily score row.

Compatibility
-------------
``op.batch_alter_table`` is used for SQLite compatibility in tests; on
PostgreSQL alembic skips the table-rebuild path and emits in-place
``ALTER TABLE`` statements.
"""
from alembic import op
import sqlalchemy as sa


revision = "020_growth_user_id"
down_revision = "019_ai_twin"
branch_labels = None
depends_on = None


def upgrade():
    # ── growth_reflections: add user_id ──────────────────────────────────
    with op.batch_alter_table("growth_reflections") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    # Backfill orphans to user_id=0 so we can enforce NOT NULL
    op.execute("UPDATE growth_reflections SET user_id = 0 WHERE user_id IS NULL")

    with op.batch_alter_table("growth_reflections") as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.create_index(
            "ix_growth_reflections_user_id",
            ["user_id"],
        )

    # ── growth_scores: add user_id + composite uniqueness ─────────────────
    # NOTE: ``date`` is the existing primary key. We keep it (DB-level
    # backwards-compatibility for any external readers) and layer a
    # composite UNIQUE on (user_id, date) so ON CONFLICT (user_id, date)
    # upserts work in the application layer.
    with op.batch_alter_table("growth_scores") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    op.execute("UPDATE growth_scores SET user_id = 0 WHERE user_id IS NULL")

    with op.batch_alter_table("growth_scores") as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.create_index(
            "ix_growth_scores_user_id",
            ["user_id"],
        )
        batch.create_unique_constraint(
            "uq_growth_scores_user_date",
            ["user_id", "date"],
        )


def downgrade():
    with op.batch_alter_table("growth_scores") as batch:
        batch.drop_constraint("uq_growth_scores_user_date", type_="unique")
        batch.drop_index("ix_growth_scores_user_id")
        batch.drop_column("user_id")

    with op.batch_alter_table("growth_reflections") as batch:
        batch.drop_index("ix_growth_reflections_user_id")
        batch.drop_column("user_id")
