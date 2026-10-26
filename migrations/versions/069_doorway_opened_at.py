"""doorway_checks.opened_at — 증권 앱이 열렸다는 신호가 온 시각.

Revision ID: 069_doorway_opened_at
Revises: 068_monthly_report_sends
Create Date: 2026-10-26

Why
===
문 앞의 한 줄은 지금까지 "질문에 답한" 열림만 남겼다. 아이폰 단축어 메뉴를
닫거나 안드로이드 웹 문에서 뒤로 가면 아무것도 저장되지 않아, 거울의 "증권 앱을
N번 열었어요" 는 실제로 연 횟수보다 적게 셌다. 이제 자동화가 질문을 띄우기 전에
'열림 신호'를 먼저 보낼 수 있고(services/doorway/service.py), 그 신호로 시작한
행은 이 칸에 시각을 남긴다. 답이 오면 같은 행이 답으로 바뀐다. NULL = 신호 없이
답만 온 행 (기존 모든 행).

Legal / privacy posture
-----------------------
새 수집 항목이 아니다 — 가져오기 토큰 동의 문구와 처리방침 §1.2 가 이미 "증권 앱을
연 시각"을 문 앞 기록의 수집 항목으로 적는다. 서술 없음, 시세 없음.

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
revision = "069_doorway_opened_at"
down_revision = "068_monthly_report_sends"
branch_labels = None
depends_on = None

_TABLE = "doorway_checks"
_COL = "opened_at"


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
