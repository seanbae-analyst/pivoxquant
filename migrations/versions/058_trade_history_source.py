"""trade_history.source — 보유 등록 시드 매수 행 표시.

Revision ID: 058_trade_history_source
Revises: 057_pending_currency_stated
Create Date: 2026-09-29

Why
===
보유 등록 경로(POST /api/portfolio/positions · /position · 보유 캡처
가져오기)가 ``positions`` 만 쓰고 ``trade_history`` 는 쓰지 않았다. 거울들
(보유기간·회전·물타기·손익처분·멈춤 귀결·관찰 페르소나)은 FIFO 로트를
``trade_history`` 에서만 다시 세우므로, 등록한 종목을 팔면 빈 큐에 부딪혀
그 매도가 버려지고, 추가매수는 새 진입으로 읽혔다. 전량 매도는 Position 행을
지우므로 Position 에서 거꾸로 세울 수도 없다.

그래서 등록이 주식을 더할 때 ``source='holding_seed'`` 인 매수 행을 하나 쓴다.
이 컬럼이 그 표시다. NULL = 기존의 모든 체결 행.

Idempotency
-----------
컬럼이 없을 때만 더한다 (Inspector). app.py 의 ``db.create_all()`` +
``_add_column_if_missing`` 부팅 경로가 먼저 했어도 안전하다. nullable
VARCHAR(20) — SQLite·PostgreSQL 같은 DDL. Downgrade 는 ``batch_alter_table``.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "058_trade_history_source"
# 057_pending_currency_stated (pending_trades.currency_stated) lands on the
# branch just before this one — linear history.
down_revision = "057_pending_currency_stated"
branch_labels = None
depends_on = None

_TABLE = "trade_history"
_COL = "source"


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
        op.add_column(_TABLE, sa.Column(_COL, sa.String(length=20), nullable=True))


def downgrade():
    if _TABLE in _tables() and _COL in _columns(_TABLE):
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
