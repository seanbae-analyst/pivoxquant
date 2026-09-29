"""trade_history.reflection_declined — 보여진 멈춤 후보를 끄고 기록한 매수 (명시 거절).

Revision ID: 061_trade_history_reflection_declined
Revises: 060_trade_history_reflection_link
Create Date: 2026-09-29

Why
===
060 이 매수 ↔ 멈춤 명시 연결(``reflection_id``)을 더했다. 그런데 사용자가
후보를 보고 체크를 **끈** 매수는 연결이 없는 옛 행과 구분되지 않아,
``services/pre_trade/friction_outcome.py`` 의 7일 창 추정이 그 매수를 다시
멈춤에 귀속시켰다. 이 컬럼이 그 거절을 남긴다. True = 명시 거절 (추정하지
않는다), NULL = 거절 기록 없음 (기존 모든 행 · 후보가 없었음).

Idempotency
-----------
컬럼이 없을 때만 더한다 (Inspector). app.py 의 ``db.create_all()`` +
``_add_column_if_missing`` 부팅 경로가 먼저 했어도 안전하다.
Downgrade 는 ``batch_alter_table`` (SQLite 호환).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "061_trade_history_reflection_declined"
down_revision = "060_trade_history_reflection_link"
branch_labels = None
depends_on = None

_TABLE = "trade_history"
_COL = "reflection_declined"


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
        op.add_column(_TABLE, sa.Column(_COL, sa.Boolean(), nullable=True))


def downgrade():
    if _TABLE not in _tables():
        return
    if _COL in _columns(_TABLE):
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
