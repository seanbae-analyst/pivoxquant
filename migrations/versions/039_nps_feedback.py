"""NPS 1-click feedback table — Wave G C-AC2.

Revision ID: 039_nps_feedback
Revises: 038_checkout_expirations, 038_inactive_nudge_sent_at, 038_scheduled_emails
Create Date: 2026-05-19

Wave G C-AC2 — NPS 1-click widget (transactional)
=================================================

Captures a single NPS-style score (1-10) per user, optionally tied to
the Weekly Memo artifact that triggered the prompt. Classified as
*transactional* under 정통망법 §50 (서비스 개선) — no marketing
content, no consent required. Stored server-side so we can correlate
detractors / promoters with cohort and artifact version without
relying on volatile client storage.

Why a dedicated table instead of reusing ``artifact_feedback``?
---------------------------------------------------------------
``artifact_feedback`` records a section-level qualitative vote
(useful / meh / skip) tied to a specific artifact section. NPS is a
quantitative whole-product score with a distinct write path (one-click
email link or post-receipt prompt) and aggregation pattern (per-month
NPS rollups). Conflating the two would force every reader of either
signal to know which is which.

Multi-head merge
----------------
Three sibling revisions ship as 038_* (checkout_expirations,
inactive_nudge_sent_at, scheduled_emails). This revision merges all
three into a single head so subsequent migrations have one parent.

Idempotency
-----------
Inspector-pattern (mirrors 023 / 037 / 038_*) — skips CREATE TABLE if
the table already exists. Re-running this migration is a safe no-op.
"""
from alembic import op
import sqlalchemy as sa


revision = "039_nps_feedback"
# Merge the three 038 heads so subsequent migrations have a single parent.
down_revision = (
    "038_checkout_expirations",
    "038_inactive_nudge_sent_at",
    "038_scheduled_emails",
)
branch_labels = None
depends_on = None


_TABLE = "nps_feedback"


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        # weekly_memo_id is an opaque artifact identifier — strings on the
        # frontend (UUID / hash). Deliberately NOT FK'd to artifacts.id so
        # NPS history survives artifact deletion.
        sa.Column("weekly_memo_id", sa.String(64), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("score >= 1 AND score <= 10", name="ck_nps_score_range"),
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
