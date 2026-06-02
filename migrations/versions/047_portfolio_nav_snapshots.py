"""Add portfolio_nav_snapshots (real daily NAV record for the equity curve).

Revision ID: 047_portfolio_nav_snapshots
Revises: 046_user_locale
Create Date: 2026-06-02

Why
===
The equity curve was reconstructed from CURRENT holdings × historical prices —
a counterfactual that drew months the user never actually held (CEO: fake data;
표시광고법 fabrication risk). This table stores the only honest source: NAV we
actually observed and recorded each day (positions × prices at the time). The
curve reads from here. No backfill — it grows truthfully from first record.

Idempotency
-----------
- Table existence check via SQLAlchemy Inspector (mirrors 046_user_locale).
- app.py ``_do_migrations`` self-heal guard covers alembic-less prod boxes
  (Railway). Both paths are idempotent.

Compliance
----------
NAV snapshots are the user's own financial data (one user owns every row, FK
CASCADE on delete — purged on 회원탈퇴, PIPA §21). Never aggregated across users.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "047_portfolio_nav_snapshots"
down_revision = "046_user_locale"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    try:
        return insp.has_table(table)
    except Exception:
        return False


def upgrade():
    if _has_table("portfolio_nav_snapshots"):
        return
    op.create_table(
        "portfolio_nav_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("nav_total_usd", sa.Numeric(20, 2), nullable=False),
        sa.Column("nav_us_usd", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("nav_kr_krw", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("fx_rate", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "as_of_date", name="uq_nav_snapshot_user_day"),
    )
    op.create_index(
        "idx_nav_snapshot_user_day",
        "portfolio_nav_snapshots",
        ["user_id", "as_of_date"],
    )
    op.create_index(
        op.f("ix_portfolio_nav_snapshots_user_id"),
        "portfolio_nav_snapshots",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_portfolio_nav_snapshots_as_of_date"),
        "portfolio_nav_snapshots",
        ["as_of_date"],
    )


def downgrade():
    if not _has_table("portfolio_nav_snapshots"):
        return
    op.drop_index("ix_portfolio_nav_snapshots_as_of_date", table_name="portfolio_nav_snapshots")
    op.drop_index("ix_portfolio_nav_snapshots_user_id", table_name="portfolio_nav_snapshots")
    op.drop_index("idx_nav_snapshot_user_day", table_name="portfolio_nav_snapshots")
    op.drop_table("portfolio_nav_snapshots")
