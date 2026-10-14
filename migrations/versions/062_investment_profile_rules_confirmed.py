"""investment_profiles.rules_confirmed_at — 온보딩 답을 내 선으로 삼은 시각.

Revision ID: 062_investment_profile_rules_confirmed
Revises: 061_trade_history_reflection_declined
Create Date: 2026-10-14

Why
===
내 규칙 (services/profile/my_rules.py) 은 온보딩 v3 답을 "한 달에 매수·매도
5번 이하" 같은 선으로 보여 준다. 그런데 온보딩 문항은 "보통 어떻게 하나요"
라는 자기 서술이지 약속이 아니다. 유저가 그 답을 자기 선으로 삼겠다고 한
시각을 남기고, 그 전에는 선 안/밖 판정과 체결 푸시 한 줄을 내지 않는다.
NULL = 아직 삼지 않음 (기존 모든 행). 규칙 문항 답을 바꾸면 다시 NULL.

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
revision = "062_investment_profile_rules_confirmed"
down_revision = "061_trade_history_reflection_declined"
branch_labels = None
depends_on = None

_TABLE = "investment_profiles"
_COL = "rules_confirmed_at"


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
    if _TABLE not in _tables():
        return
    if _COL in _columns(_TABLE):
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
