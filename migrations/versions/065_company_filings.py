"""company_filings — 미국 회사 공시 목록 (SEC EDGAR), 종목 기록 타임라인용.

Revision ID: 065_company_filings
Revises: 064_doorway_checks
Create Date: 2026-10-25

Why
===
종목별 내 기록(/journal/stock/<ticker>)에 그 종목의 공시(연간·분기·수시
보고, 실적 발표)를 유저 기록 사이에 끼운다. SEC ``data.sec.gov/submissions``
목록에서 보여 줄 양식만 골라 행으로 둔다 — 종목당 하루 한 번만 SEC 에 묻고
나머지는 여기서 읽는다 (services/filing_timeline).

Legal / privacy posture
-----------------------
공개된 사실(양식 · 공식 공시일 · 원문 주소)뿐이다. ``user_id`` 가 없고 개인
정보가 없다 — 탈퇴 삭제 경로에 넣을 것이 없다. 제목·요약·평가 컬럼이 없다.
시세 컬럼 없음.

Idempotency
-----------
``app.py`` 의 ``db.create_all()`` 이 먼저 만들었을 수 있으므로 Inspector 로
존재를 보고 없을 때만 만든다 (054 · 063 · 064 와 같은 관례).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "065_company_filings"
down_revision = "064_doorway_checks"
branch_labels = None
depends_on = None

_TABLE = "company_filings"
_UNIQUE = "uq_company_filings_source_ticker_accession"
_INDEXES = {
    "idx_company_filings_ticker_filed": ["ticker", "filed_on"],
}


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in _inspector().get_indexes(table)}


def upgrade():
    if _TABLE not in _tables():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source", sa.String(length=8), nullable=False),
            sa.Column("ticker", sa.String(length=20), nullable=False),
            sa.Column("cik", sa.String(length=10), nullable=True),
            sa.Column("accession", sa.String(length=25), nullable=False),
            sa.Column("form", sa.String(length=16), nullable=False),
            sa.Column("items", sa.String(length=64), nullable=True),
            sa.Column("filed_on", sa.Date(), nullable=False),
            sa.Column("url", sa.String(length=300), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("source", "ticker", "accession", name=_UNIQUE),
        )
    if _TABLE in _tables():
        existing = _indexes(_TABLE)
        for name, cols in _INDEXES.items():
            if name not in existing:
                op.create_index(name, _TABLE, cols)


def downgrade():
    if _TABLE not in _tables():
        return
    existing = _indexes(_TABLE)
    for name in _INDEXES:
        if name in existing:
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
