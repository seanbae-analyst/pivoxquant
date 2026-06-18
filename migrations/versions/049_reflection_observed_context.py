"""Observed-context snapshot column on pre_trade_reflections.

Revision ID: 049_reflection_observed_context
Revises: 048_widen_encrypted_text_columns
Create Date: 2026-06-10

Why
===
record-as-spine Phase 2 (docs/strategy/record-as-spine_2026-06-09.md §5):
the journal answers "왜 들어갔나" (rationale) but not "그때 무엇을 보고
있었나". This column stores a small JSON snapshot of the observation
surfaces at the moment the user opened their reflection — the ticker's
own POSITIVE/NEGATIVE/NEUTRAL signal label + score from SignalCache, the
VIX level, and the last-hour move. Collected best-effort in
``services.pre_trade.friction._collect_observed_context`` (a collection
failure never blocks the reflection write).

Compliance (§17)
----------------
The snapshot is a FACTUAL record of what the product was already showing
the user — observation labels only (POSITIVE/NEGATIVE/NEUTRAL, the legal
surface), never rec_* / target / stop fields, never a directive.

Idempotency
-----------
Column added only if absent (Inspector check), so re-running — or running
after the app.py self-heal twin already added it — is safe. Plain nullable
TEXT: identical DDL on SQLite (dev/test) and PostgreSQL (prod).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "049_reflection_observed_context"
down_revision = "048_widen_encrypted_text_columns"
branch_labels = None
depends_on = None

_TABLE = "pre_trade_reflections"
_COLUMN = "observed_context_json"


def _has_column() -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    if _TABLE not in insp.get_table_names():
        return True  # table missing entirely — nothing to do either way
    return any(c["name"] == _COLUMN for c in insp.get_columns(_TABLE))


def upgrade():
    if _has_column():
        return
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.Text(), nullable=True))


def downgrade():
    if not _has_column():
        return
    op.drop_column(_TABLE, _COLUMN)
