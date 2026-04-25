"""pre_trade_reflections — 거래 의도에 대한 self-imposed reflection cooldown.

Revision ID: 017_pre_trade_reflections
Revises: 016_persona_snapshots
Create Date: 2026-04-25

Why
---
Backs Feature 6 (Pre-Trade Friction). Each row is the user's own opt-in
"give me 2 minutes + a written rationale before I trade" record. The
broker (Alpaca paper / KIS read-only) is unaffected — this is a UX
layer the user adds in front of *their* decision, not a recommendation
from us.

Legal posture
-------------
Strictly observational / behavioural. We never block the trade — when
the cooldown ends, the user clicks **Proceed** and the existing
broker route runs unchanged. The rationale is the user's own free-text
input. ``intended_side`` is a label for the user's record only; we do
not derive any directive from it (자본시장법 §49 분리). The
``auto_extended_reason`` enum is purely an informational flag —
"market is volatile, here's a longer reflection window if you want it"
— never a "do not trade" signal.

Privacy posture
---------------
``user_id`` FK ``ON DELETE CASCADE`` so account deletion removes every
reflection row (PIPA Art.36 right-to-erasure). No third-party
identifiers, no PII beyond the user's own rationale text. Rationale is
rendered only back to the originating user (route-level ownership
check); never aggregated, never shipped to peer benchmarks.

Chaining
--------
``down_revision="016_persona_snapshots"`` continues the strictly linear
Alembic history.
"""
from alembic import op
import sqlalchemy as sa


revision = "017_pre_trade_reflections"
down_revision = "016_persona_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pre_trade_reflections",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("intended_ticker", sa.String(length=20), nullable=False),
        # 'BUY' / 'SELL' — purely a user-supplied label for their own
        # reflection record. NOT a directive emitted by us.
        sa.Column("intended_side", sa.String(length=4), nullable=True),
        sa.Column("intended_shares", sa.Numeric(20, 4), nullable=True),
        # Free-text rationale (>=50 chars enforced at service layer).
        sa.Column("rationale", sa.Text(), nullable=False),
        # Optional: snapshot of the AI Devil's-Advocate counterpoints
        # the user saw when starting this reflection (Feature R hook).
        sa.Column("devil_advocate_seen", sa.Text(), nullable=True),
        # Market context at the time of /start — VIX or KRX vol. Plain
        # numeric so we can later analyse whether high-vol windows
        # correlate with longer cooldowns.
        sa.Column("market_volatility_at_request", sa.Numeric(8, 4), nullable=True),
        sa.Column("cooldown_started_at", sa.DateTime(), nullable=False),
        sa.Column("cooldown_ends_at", sa.DateTime(), nullable=False),
        sa.Column("proceeded_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        # Why we auto-extended (FOMC / VIX / big move). Null if default 2 min.
        sa.Column("auto_extended_reason", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Active reflections for a user: the read path filters
    # `proceeded_at IS NULL AND cancelled_at IS NULL`. Postgres supports
    # partial indexes; SQLite parses but ignores the predicate. We render
    # the same DDL on both for portability and let the engines decide.
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE INDEX idx_pre_trade_user_active "
            "ON pre_trade_reflections(user_id, cooldown_ends_at) "
            "WHERE proceeded_at IS NULL AND cancelled_at IS NULL"
        )
    else:
        # SQLite — no partial index; plain composite is enough at the
        # row volumes we expect (one user has dozens, not millions).
        op.create_index(
            "idx_pre_trade_user_active",
            "pre_trade_reflections",
            ["user_id", "cooldown_ends_at"],
        )


def downgrade():
    try:
        op.drop_index("idx_pre_trade_user_active", table_name="pre_trade_reflections")
    except Exception:
        # Partial index name may not be tracked by Alembic on PG. Best-effort.
        pass
    op.drop_table("pre_trade_reflections")
