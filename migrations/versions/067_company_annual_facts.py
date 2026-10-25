"""company_annual_facts — 회사 연간 숫자 (내가 고른 회사들 카드).

Revision ID: 067_company_annual_facts
Revises: 066_company_filing_title
Create Date: 2026-10-25

Why
===
/mirror 「내가 고른 회사들」: 유저가 최근 1년에 산 회사가 산 날 직전에 공시된
연간 보고에서 순손실이었나 · 매출이 줄었나 · 부채가 자본보다 많았나를 개수로
센다 (services/pick_facts). 공시 원천(SEC companyfacts · OpenDART 주요계정)에서
연간 값만 골라 회계연도별로 둔다. ``filed_on`` 은 그 숫자가 처음 공시된 날.

Legal / privacy posture
-----------------------
공개된 공시 숫자뿐이다. ``user_id`` 없음, 개인정보 없음, 시세 없음, 평가 없음.

Idempotency
-----------
``app.py`` 의 ``db.create_all()`` 이 먼저 만들었을 수 있으므로 Inspector 로
존재를 보고 없을 때만 만든다 (064 · 065 와 같은 관례).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "067_company_annual_facts"
down_revision = "066_company_filing_title"
branch_labels = None
depends_on = None

_TABLE = "company_annual_facts"
_INDEX = "idx_company_annual_facts_ticker"


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes() -> set[str]:
    return {i["name"] for i in inspect(op.get_bind()).get_indexes(_TABLE)}


def upgrade():
    if _TABLE not in _tables():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source", sa.String(length=8), nullable=False),
            sa.Column("ticker", sa.String(length=20), nullable=False),
            sa.Column("fiscal_end", sa.Date(), nullable=False),
            sa.Column("filed_on", sa.Date(), nullable=False),
            sa.Column("revenue", sa.Float(), nullable=True),
            sa.Column("net_income", sa.Float(), nullable=True),
            sa.Column("liabilities", sa.Float(), nullable=True),
            sa.Column("equity", sa.Float(), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("source", "ticker", "fiscal_end", name="uq_company_annual_facts_source_ticker_end"),
        )
    if _TABLE in _tables() and _INDEX not in _indexes():
        op.create_index(_INDEX, _TABLE, ["ticker"])


def downgrade():
    if _TABLE not in _tables():
        return
    if _INDEX in _indexes():
        op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
