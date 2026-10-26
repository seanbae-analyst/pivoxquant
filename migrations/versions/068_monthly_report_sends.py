"""monthly_report_sends — 월간 거울 리포트를 그 달 몫으로 보낸 기록.

Revision ID: 068_monthly_report_sends
Revises: 067_company_annual_facts
Create Date: 2026-10-25

Why
===
Render Free 는 무트래픽 15분이면 잠들고, 인프로세스 APScheduler 는 잠든 동안의
발화를 복구하지 않는다(MemoryJobStore). 1일 08:30 KST 월간 리포트가 그 시각에
서버가 자고 있으면 그 달 몫이 통째로 사라졌다. 이제 1일 08:30–23:30 매시 다시
시도하고, 이 표로 같은 달을 두 번 보내지 않는다 (services/reports_delivery.py).

Legal / privacy posture
-----------------------
발송 사실(유저 · 달 · 시각)뿐 — 리포트 내용 없음. ``user_id`` FK ON DELETE
CASCADE + services/account_erasure 명시 삭제.

Idempotency
-----------
``app.py`` 의 ``db.create_all()`` 이 먼저 만들었을 수 있으므로 Inspector 로
존재를 보고 없을 때만 만든다.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "068_monthly_report_sends"
down_revision = "067_company_annual_facts"
branch_labels = None
depends_on = None

_TABLE = "monthly_report_sends"
_INDEX = "ix_monthly_report_sends_user_id"


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes() -> set[str]:
    return {i["name"] for i in inspect(op.get_bind()).get_indexes(_TABLE)}


def upgrade():
    if _TABLE not in _tables():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "period", name="uq_monthly_report_sends_user_period"),
        )
    if _TABLE in _tables() and _INDEX not in _indexes():
        op.create_index(_INDEX, _TABLE, ["user_id"])


def downgrade():
    if _TABLE not in _tables():
        return
    if _INDEX in _indexes():
        op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
