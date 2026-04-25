"""ai_twin — paper-only AI Trader Twin tables (Feature 5).

Revision ID: 019_ai_twin
Revises: 018_behavioral_scores
Create Date: 2026-04-25

Why
---
Backs Feature 5 (LAUNCH_BUNDLE_SPEC.md) — a fully simulated paper-money
"twin" that acts on the user's currently-classified persona, runs a
daily decision pass, and exposes only AFTER-the-fact comparison data
to the user.

Legal posture (자본시장법 회피 핵심)
------------------------------------
- ZERO real-money fields. ``ai_twin_trades.is_paper`` is ``BOOLEAN NOT
  NULL DEFAULT TRUE`` and the service layer never inserts FALSE — the
  column exists purely as an auditable on-disk witness that this whole
  table is simulated.
- No FK or column references the production ``broker_connections``
  table — Twin is wholly isolated from any KIS/Alpaca credential row.
- ``side`` is a paper trade record only ('BUY'/'SELL'); the API layer
  in ``routes/twin.py`` rewrites it as a paper-portfolio event and
  attaches a fixed disclaimer to every response.
- Read-side endpoints only surface trades that have already executed
  (``executed_at <= now``) — ``last_decision_at`` on the portfolio is
  the public clock; nothing prospective is ever exposed.

Chaining
--------
``down_revision="018_behavioral_scores"`` continues the strictly
linear Alembic history. The 017/018 migrations are owned by parallel
agents in this Wave; this file MUST be re-pointed if either of those
slugs is renamed before merge.
"""
from alembic import op
import sqlalchemy as sa


revision = "019_ai_twin"
down_revision = "018_behavioral_scores"
branch_labels = None
depends_on = None


def upgrade():
    # ── ai_twin_portfolios ─────────────────────────────────────────
    op.create_table(
        "ai_twin_portfolios",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,  # one twin per user (1-init constraint)
        ),
        sa.Column("initialized_at", sa.DateTime(), nullable=False),
        sa.Column(
            "starting_cash",
            sa.Numeric(20, 4),
            nullable=False,
            server_default="10000.00",
        ),
        sa.Column("current_cash", sa.Numeric(20, 4), nullable=False),
        # Persona snapshot at initialization — used as a falsifiability
        # anchor in weekly reports (did the user's *declared* persona
        # match what the Twin was instructed to imitate?).
        sa.Column("persona_at_init", sa.String(length=20), nullable=False),
        sa.Column("last_decision_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── ai_twin_positions ──────────────────────────────────────────
    op.create_table(
        "ai_twin_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id",
            sa.BigInteger(),
            sa.ForeignKey("ai_twin_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("shares", sa.Numeric(20, 4), nullable=False),
        sa.Column("avg_cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "twin_id", "ticker",
            name="uq_ai_twin_positions_twin_ticker",
        ),
    )

    # ── ai_twin_trades ─────────────────────────────────────────────
    op.create_table(
        "ai_twin_trades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "twin_id",
            sa.BigInteger(),
            sa.ForeignKey("ai_twin_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        # 'BUY' or 'SELL' — paper label only. NEVER a directive.
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("shares", sa.Numeric(20, 4), nullable=False),
        sa.Column("price", sa.Numeric(20, 4), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("composite_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("pnl_at_close", sa.Numeric(20, 4), nullable=True),
        # ON-DISK WITNESS that this row is paper. Service layer never
        # writes FALSE; a CI check (test_no_real_money_field_anywhere)
        # asserts that no other code path can flip this column.
        sa.Column(
            "is_paper",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.CheckConstraint(
            "side IN ('BUY','SELL')",
            name="ck_ai_twin_trades_side",
        ),
    )
    op.create_index(
        "idx_twin_trades_executed",
        "ai_twin_trades",
        ["twin_id", sa.text("executed_at DESC")],
    )

    # ── ai_twin_weekly_reports ─────────────────────────────────────
    op.create_table(
        "ai_twin_weekly_reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_ending", sa.Date(), nullable=False),
        sa.Column("user_return_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("twin_return_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("diff_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("user_trades_count", sa.Integer(), nullable=True),
        sa.Column("twin_trades_count", sa.Integer(), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "week_ending",
            name="uq_ai_twin_weekly_reports_user_week",
        ),
    )
    op.create_index(
        "idx_twin_reports_user_week",
        "ai_twin_weekly_reports",
        ["user_id", sa.text("week_ending DESC")],
    )


def downgrade():
    op.drop_index(
        "idx_twin_reports_user_week",
        table_name="ai_twin_weekly_reports",
    )
    op.drop_table("ai_twin_weekly_reports")

    op.drop_index(
        "idx_twin_trades_executed",
        table_name="ai_twin_trades",
    )
    op.drop_table("ai_twin_trades")

    op.drop_table("ai_twin_positions")
    op.drop_table("ai_twin_portfolios")
