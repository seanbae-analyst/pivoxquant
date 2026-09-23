"""broker_connections — 평문 access_token / refresh_token 컬럼 제거.

Revision ID: 055_drop_broker_plaintext_tokens
Revises: 054_observation_notes
Create Date: 2026-09-23

Why
===
2026-09-23 DB 보안 감사. 두 컬럼은 Alpaca 연동 시절의 평문 토큰 자리였다.
Alpaca 코드는 사라졌고 KIS 흐름은 ``encrypted_access_token`` 만 쓴다 —
코드에서 두 컬럼에 쓰는 곳이 0곳이다(grep ``.access_token`` 실측). 남아 있으면
언젠가 누군가 평문 토큰을 다시 넣을 자리가 된다.

prod 실측(2026-09-23, Supabase ``yjiztgummaxecriiuumt``):
``broker_connections`` 0행 — 잃는 데이터가 없다.

Idempotency
-----------
``app.py`` 의 런타임 DDL 에서도 두 컬럼을 더하던 줄을 함께 지웠다(CLAUDE.md
함정 13). Inspector 로 존재 여부를 먼저 보고 있을 때만 지운다. SQLite 는
``batch_alter_table`` 로 테이블 재작성.

Downgrade 는 빈 TEXT 컬럼만 되살린다 — 값은 되돌리지 않는다(애초에 0행).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "055_drop_broker_plaintext_tokens"
down_revision = "054_observation_notes"
branch_labels = None
depends_on = None

_TABLE = "broker_connections"
_COLUMNS = ("access_token", "refresh_token")


def _columns() -> set[str]:
    insp = inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(_TABLE)}


def upgrade():
    present = [c for c in _COLUMNS if c in _columns()]
    if not present:
        return
    with op.batch_alter_table(_TABLE) as batch:
        for name in present:
            batch.drop_column(name)


def downgrade():
    existing = _columns()
    if not existing:
        return
    missing = [c for c in _COLUMNS if c not in existing]
    if not missing:
        return
    with op.batch_alter_table(_TABLE) as batch:
        for name in missing:
            batch.add_column(sa.Column(name, sa.Text(), nullable=True))
