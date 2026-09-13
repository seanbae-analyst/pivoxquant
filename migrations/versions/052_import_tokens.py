"""Import Inbox Phase 2 — import_tokens + import_batches.token_id.

Revision ID: 052_import_tokens
Revises: 051_import_inbox
Create Date: 2026-09-13

Why
===
docs/product/IMPORT_INBOX_DESIGN.md §Phase 2 v3-A — the user issues a
personal access token from /settings and points their own automation
(MacroDroid, a mail filter, cron) at ``POST /api/portfolio/imports/webhook``
with ``Authorization: Bearer pvx_…``. Every fill that arrives this way
still lands in ``pending_trades`` and waits for the user's thesis; the
token only replaces the session for the intake step.

Compliance
----------
``token_hash`` is sha256(raw); the raw token is never stored. ``prefix``
keeps 12 display characters. ``consent_at`` is the upload consent given at
issuance and is inherited by every webhook batch (``import_batches.token_id``
links them). No column stores a score, grade or directive.

Idempotency
-----------
Table / column / index are created only if absent (Inspector check) so
re-running — or running after the app.py ``db.create_all()`` +
``_add_column_if_missing`` boot path already did part of the work — is
safe. Plain INTEGER/VARCHAR/DATETIME: identical DDL on SQLite (dev/test)
and PostgreSQL (prod). The ``token_id`` FK constraint is emitted on
PostgreSQL only; SQLite cannot add a constraint via ALTER and the app-side
self-heal adds a plain INTEGER there anyway.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "052_import_tokens"
down_revision = "051_import_inbox"
branch_labels = None
depends_on = None

_TOKENS = "import_tokens"
_BATCHES = "import_batches"
_TOKEN_COL = "token_id"
_TOKEN_IDX = "ix_import_batches_token_id"


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in _inspector().get_indexes(table)}


def upgrade():
    have = _tables()
    is_pg = op.get_bind().dialect.name == "postgresql"

    if _TOKENS not in have:
        op.create_table(
            _TOKENS,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(60), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("prefix", sa.String(16), nullable=False),
            sa.Column("consent_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_import_tokens_user_id", _TOKENS, ["user_id"])
        op.create_index("ix_import_tokens_token_hash", _TOKENS, ["token_hash"], unique=True)

    if _BATCHES in have:
        if _TOKEN_COL not in _columns(_BATCHES):
            if is_pg:
                col = sa.Column(
                    _TOKEN_COL, sa.Integer(),
                    sa.ForeignKey("import_tokens.id", ondelete="SET NULL"),
                    nullable=True,
                )
            else:
                col = sa.Column(_TOKEN_COL, sa.Integer(), nullable=True)
            op.add_column(_BATCHES, col)
        if _TOKEN_IDX not in _indexes(_BATCHES):
            op.create_index(_TOKEN_IDX, _BATCHES, [_TOKEN_COL])


def downgrade():
    have = _tables()
    if _BATCHES in have and _TOKEN_COL in _columns(_BATCHES):
        if _TOKEN_IDX in _indexes(_BATCHES):
            op.drop_index(_TOKEN_IDX, table_name=_BATCHES)
        with op.batch_alter_table(_BATCHES) as batch:
            batch.drop_column(_TOKEN_COL)
    if _TOKENS in have:
        op.drop_table(_TOKENS)
