"""Import Inbox — import_batches + pending_trades.

Revision ID: 051_import_inbox
Revises: 050_onboarding_v3_declared
Create Date: 2026-09-13

Why
===
docs/product/IMPORT_INBOX_DESIGN.md — the user uploads a broker CSV/XLSX
or pastes a fill notification; every parsed fill waits in
``pending_trades`` until the user attaches their own thesis and approves
it, at which point ``services/imports/ledger.py`` writes ``trade_history``
/ ``positions``. ``import_batches`` keeps one row per upload: counts, the
consent timestamp and a broker guess — never the file or the full text.

Compliance
----------
``raw_snippet`` is capped at 300 chars with account-number patterns
masked before storage. ``approved_thesis`` is the user's own free text and
is encrypted at rest (services.crypto_service.EncryptedText → TEXT
column). ``action`` holds the TradeHistory data value (BUY / SELL); no  # // legal-ok — trade action data value, not user copy
column here stores a score, grade or directive.

Idempotency
-----------
Each table is created only if absent (Inspector check) so re-running
after the app.py ``db.create_all()`` boot path already created it is
safe. Plain INTEGER/VARCHAR/FLOAT/TEXT/DATETIME/BOOLEAN: identical DDL on
SQLite (dev/test) and PostgreSQL (prod).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "051_import_inbox"
down_revision = "050_onboarding_v3_declared"
branch_labels = None
depends_on = None

_BATCHES = "import_batches"
_PENDING = "pending_trades"


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade():
    have = _tables()
    if _BATCHES not in have:
        op.create_table(
            _BATCHES,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("broker_guess", sa.String(40), nullable=False, server_default="unknown"),
            sa.Column("filename", sa.String(255), nullable=True),
            sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("parsed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unresolved_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consent_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_import_batches_user_id", _BATCHES, ["user_id"])

    if _PENDING not in have:
        op.create_table(
            _PENDING,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("batch_id", sa.Integer(),
                      sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("ticker", sa.String(20), nullable=True),
            sa.Column("name", sa.String(100), nullable=False, server_default=""),
            sa.Column("action", sa.String(4), nullable=False),
            sa.Column("shares", sa.Float(), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(5), nullable=False, server_default="KRW"),
            sa.Column("traded_at", sa.DateTime(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
            sa.Column("dedupe_key", sa.String(64), nullable=False),
            sa.Column("needs_ticker", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("raw_snippet", sa.String(300), nullable=True),
            sa.Column("pre_trade_reflection_id", sa.Integer(),
                      sa.ForeignKey("pre_trade_reflections.id", ondelete="SET NULL"),
                      nullable=True),
            sa.Column("approved_thesis", sa.Text(), nullable=True),
            sa.Column("approved_trade_id", sa.Integer(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_pending_trades_batch_id", _PENDING, ["batch_id"])
        op.create_index("ix_pending_trades_user_id", _PENDING, ["user_id"])
        op.create_index("ix_pending_trades_status", _PENDING, ["status"])
        op.create_index("ix_pending_trades_dedupe_key", _PENDING, ["dedupe_key"])


def downgrade():
    have = _tables()
    if _PENDING in have:
        op.drop_table(_PENDING)
    if _BATCHES in have:
        op.drop_table(_BATCHES)
