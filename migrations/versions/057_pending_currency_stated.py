"""pending_trades.currency_stated — did the input state the currency?

Revision ID: 057_pending_currency_stated
Revises: 056_enable_rls_public_tables
Create Date: 2026-09-29

Why
===
A resolved ticker used to overwrite the currency the input stated for every
source but ``screenshot_image``: ``TSLA 10주 매수 체결 350,000원`` became a
$350,000 fill, and PATCHing ``NVDA`` onto an unresolved ``… 175,000원`` row
re-labelled it $175,000. Ingest now skips a stated-currency mismatch; the
PATCH refusal needs to know, per row, whether ``currency`` came from the
input (원/₩/$, a 통화 column, a webhook field) or was a guess a picked
ticker may still correct. That is this column.

Nullable BOOLEAN, no backfill: NULL rows predate it and are treated as
stated by ``routes/imports.py::patch_pending`` (conservative — a refused
PATCH costs a re-import; a wrong one rescales a price).

Idempotency
-----------
Added only if absent (Inspector check); ``app.py::_do_migrations`` self-heals
the same column on boot.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "057_pending_currency_stated"
down_revision = "056_enable_rls_public_tables"
branch_labels = None
depends_on = None

_TABLE = "pending_trades"
_COL = "currency_stated"


def _columns() -> set[str]:
    insp = inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(_TABLE)}


def upgrade():
    cols = _columns()
    if cols and _COL not in cols:
        op.add_column(_TABLE, sa.Column(_COL, sa.Boolean(), nullable=True))


def downgrade():
    if _COL in _columns():
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
