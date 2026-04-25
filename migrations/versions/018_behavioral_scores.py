"""behavioral_scores — weekly observational behaviour score per user.

Revision ID: 018_behavioral_scores
Revises: 017_pre_trade_reflections
Create Date: 2026-04-25

Why
---
Backs Feature 7 (Weekly Behavioural Score). Each row is a single user's
own retrospective score for the week ending ``week_ending`` —
purely observational, computed Sunday 22:00 KST (before the
PersonaSnapshot 23:00 cron) by ``services.behavior.scorer.compute_weekly_score``.

Legal posture
-------------
Read-only retrospective. Sub-scores name what *was* done, never what
*should be* done. The ``notes`` field is filtered through the same
``services.legal.forbidden_terms`` blocklist that protects every other
artefact surface. Persona-average comparison uses the existing
``persona_group_stats`` ``MIN_GROUP_SIZE=20`` legal floor (PIPA
Art.26-2 / 신용정보법 Art.32).

Privacy posture
---------------
``user_id`` FK ``ON DELETE CASCADE`` removes every weekly row on
account deletion. Strictly per-user — never cross-aggregated. The
``persona_avg`` JSON references the *anonymised* PersonaGroupStats
window (n_users >= 20) so re-identification is bounded by the same
floor used elsewhere.

UNIQUE ``(user_id, week_ending)`` keeps the cron idempotent — a
manually-triggered re-compute on Monday noon overwrites the same
Sunday row instead of creating duplicates.

Chaining
--------
``down_revision="017_pre_trade_reflections"`` continues the strictly
linear Alembic history.
"""
from alembic import op
import sqlalchemy as sa


revision = "018_behavioral_scores"
down_revision = "017_pre_trade_reflections"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "behavioral_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_ending", sa.Date(), nullable=False),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False),
        # JSON payload — TEXT for SQLite/Postgres portability.
        sa.Column("sub_scores", sa.Text(), nullable=False),
        sa.Column("persona_avg", sa.Text(), nullable=True),
        # Observational note only — services.behavior.scorer enforces the
        # forbidden_terms blocklist before persisting. Free-text but
        # generated, never user-supplied.
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "week_ending",
            name="uq_behavioral_scores_user_week",
        ),
    )
    op.create_index(
        "idx_behavioral_scores_user_week",
        "behavioral_scores",
        ["user_id", "week_ending"],
    )


def downgrade():
    op.drop_index(
        "idx_behavioral_scores_user_week",
        table_name="behavioral_scores",
    )
    op.drop_table("behavioral_scores")
