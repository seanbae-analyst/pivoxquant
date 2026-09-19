"""PIPA §22 ⑥ — users.age_confirmed_at (만 14세 이상 자가선언 시각).

Revision ID: 053_age_self_declaration
Revises: 052_import_tokens
Create Date: 2026-09-19

Why
===
2026-09-19 the product stopped collecting a date of birth. The under-14
gate (PIPA §22 ⑥ — no guardian-consent flow exists, so under-14 signups
are refused) is now evidenced by the "만 14세 이상입니다" self-declaration
checkbox in the signup consent stack; the server stamps the submission
time into ``users.age_confirmed_at`` (naive UTC, same convention as the
other consent timestamps on ``users``). Whether a self-declaration is
sufficient is still an open lawyer question — Q9 in
docs/legal/legal-audit-2026-06-05.md.

``users.birthdate`` (031) is **kept**, column and data. Legacy users who
already supplied one keep passing the gate without any re-prompt
(``User.age_confirmed`` = ``age_confirmed_at IS NOT NULL OR birthdate IS
NOT NULL``). No new code writes ``birthdate``.

Idempotency
-----------
The column is added only if absent (Inspector check) so re-running — or
running after the app.py ``db.create_all()`` + ``_add_column_if_missing``
boot path already did the work — is safe. Plain nullable DATETIME:
identical DDL on SQLite (dev/test) and PostgreSQL (prod). Downgrade
drops it via ``batch_alter_table`` so SQLite can cope.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "053_age_self_declaration"
down_revision = "052_import_tokens"
branch_labels = None
depends_on = None

_TABLE = "users"
_COL = "age_confirmed_at"


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def upgrade():
    if _TABLE not in _tables():
        return
    if _COL not in _columns(_TABLE):
        op.add_column(_TABLE, sa.Column(_COL, sa.DateTime(), nullable=True))


def downgrade():
    if _TABLE in _tables() and _COL in _columns(_TABLE):
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
