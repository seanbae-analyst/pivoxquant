"""trade_history.reflection_id — 매수 기록과 그 앞의 멈춤(reflection)을 잇는 명시적 연결.

Revision ID: 060_trade_history_reflection_link
Revises: 059_alerts_push_only
Create Date: 2026-09-29

Why
===
``services/pre_trade/friction_outcome.py`` 는 멈춤과 매수를 **추정**으로만
이었다 — 같은 종목 · proceeded_at 뒤 7일 창. 같은 종목을 자주 사는 사용자는
오귀속되고, 취소한 멈춤이 "결국 샀다"로 잡히는 것도 시각 비교뿐이었다.
사용자가 매수를 기록하면서 "이 매수는 그 멈춤의 결과다"라고 직접 이으면
추정이 필요 없다. 이 컬럼이 그 연결이다. NULL = 연결 없음 (기존 모든 행) —
그때는 friction_outcome 이 예전처럼 시간 창으로 추정한다.

FK 는 ``pre_trade_reflections.id`` · ``ON DELETE SET NULL`` — 기록이 지워져도
매수 행은 남는다.

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
revision = "060_trade_history_reflection_link"
down_revision = "059_alerts_push_only"
branch_labels = None
depends_on = None

_TABLE = "trade_history"
_COL = "reflection_id"
_INDEX = "ix_trade_history_reflection_id"


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in _inspector().get_indexes(table)}


def upgrade():
    if _TABLE not in _tables():
        return
    if _COL not in _columns(_TABLE):
        # SQLite 는 ALTER 로 제약을 못 단다 (alembic NotImplementedError) —
        # 로컬 SQLite 에서는 컬럼만, PostgreSQL 에서는 FK 까지.
        fk = () if op.get_bind().dialect.name == "sqlite" else (
            sa.ForeignKey("pre_trade_reflections.id", ondelete="SET NULL"),
        )
        op.add_column(_TABLE, sa.Column(_COL, sa.Integer(), *fk, nullable=True))
    if _INDEX not in _indexes(_TABLE):
        op.create_index(_INDEX, _TABLE, [_COL])


def downgrade():
    if _TABLE not in _tables():
        return
    if _INDEX in _indexes(_TABLE):
        op.drop_index(_INDEX, table_name=_TABLE)
    if _COL in _columns(_TABLE):
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
