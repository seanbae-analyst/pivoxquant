"""alerts.push_only — in-app 꺼짐·푸시 켜짐 알림의 숨김 행.

Revision ID: 059_alerts_push_only
Revises: 058_trade_history_source
Create Date: 2026-09-29

Why
===
in-app 을 끈 유저에게도 푸시가 가도록 create_alert 가 벨 행을 건너뛰게 했더니,
dedup 창(dedup_window_hours)이 조회할 행이 사라져 조건이 유지되는 동안 매
스윕마다 같은 푸시가 다시 나갔다. 그래서 행은 쓰되 ``push_only=True``(읽음)
로 표시하고 벨 목록(routes/alerts.py)에서 거른다. NULL/False = 기존 벨 행.

Idempotency
-----------
컬럼이 없을 때만 더한다 (Inspector). app.py 의 ``_add_column_if_missing``
부팅 경로가 먼저 했어도 안전하다.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "059_alerts_push_only"
down_revision = "058_trade_history_source"
branch_labels = None
depends_on = None

_TABLE = "alerts"
_COL = "push_only"


def _inspector():
    return inspect(op.get_bind())


def upgrade():
    insp = _inspector()
    if _TABLE not in set(insp.get_table_names()):
        return
    if _COL not in {c["name"] for c in insp.get_columns(_TABLE)}:
        op.add_column(_TABLE, sa.Column(_COL, sa.Boolean(), nullable=True,
                                        server_default=sa.false()))


def downgrade():
    insp = _inspector()
    if _TABLE in set(insp.get_table_names()) and \
            _COL in {c["name"] for c in insp.get_columns(_TABLE)}:
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
