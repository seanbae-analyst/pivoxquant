"""Widen String(500) free-text columns to TEXT for at-rest encryption.

Revision ID: 048_widen_encrypted_text_columns
Revises: 047_portfolio_nav_snapshots
Create Date: 2026-06-02

Why
===
``positions.thesis`` / ``positions.thesis_reason`` / ``watchlist.note`` /
``position_dd_checks.note`` / ``weekly_pulse.worry`` / ``weekly_pulse.learn``
became ``EncryptedText`` columns (AES-256-GCM at rest — see
``services.crypto_service.EncryptedText``). The stored form is
``pqenc:{v}:base64(nonce||ciphertext)``; for multi-byte Korean free-text this
easily exceeds the old ``VARCHAR(500)`` cap and would overflow on PostgreSQL
(``value too long for type character varying(500)``). Widen each to TEXT.

SQLite has no VARCHAR length enforcement, so this is a metadata no-op there
(skipped). The app.py ``_do_migrations`` self-heal twin performs the same
widening on alembic-less prod boxes (Railway) — both are idempotent.

Idempotency
-----------
Only a column that is still VARCHAR is altered (already-TEXT columns are
skipped via Inspector), so re-running — or running after the self-heal already
widened — is safe.

Compliance
----------
These are the user's own free-text (매수 이유 / 메모 / mood self-report). The
widening is a prerequisite for encrypting them at rest, which is the data-trust
storage guarantee (PIPA §29 안전성 확보조치 — 암호화 저장).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "048_widen_encrypted_text_columns"
down_revision = "047_portfolio_nav_snapshots"
branch_labels = None
depends_on = None


# (table, column) pairs that move String(500) -> Text.
_COLUMNS = [
    ("positions", "thesis"),
    ("positions", "thesis_reason"),
    ("watchlist", "note"),
    ("position_dd_checks", "note"),
    ("weekly_pulse", "worry"),
    ("weekly_pulse", "learn"),
]


def _column_type(insp, table, column):
    """Return the upper-cased column type string, or None if absent."""
    try:
        for col in insp.get_columns(table):
            if col["name"] == column:
                return str(col["type"]).upper()
    except Exception:
        return None
    return None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite ignores VARCHAR length; the column already behaves as TEXT.
        return
    insp = inspect(bind)
    for table, column in _COLUMNS:
        coltype = _column_type(insp, table, column)
        if coltype is None or "TEXT" in coltype:
            continue  # absent (fresh box creates as TEXT) or already wide
        op.alter_column(
            table,
            column,
            existing_type=sa.String(length=500),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade():
    # Reverse the widening. UNSAFE if any ciphertext longer than 500 chars
    # already lives in the column (PostgreSQL raises on truncation) — only run
    # before any encrypted write. Provided for alembic linearity / completeness.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    insp = inspect(bind)
    for table, column in _COLUMNS:
        coltype = _column_type(insp, table, column)
        if coltype is None or "TEXT" not in coltype:
            continue  # absent or already VARCHAR
        op.alter_column(
            table,
            column,
            existing_type=sa.Text(),
            type_=sa.String(length=500),
            existing_nullable=True,
        )
