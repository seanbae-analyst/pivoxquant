"""company_filings.title — 한국 공시(OpenDART)의 공식 보고서명.

Revision ID: 066_company_filing_title
Revises: 065_company_filings
Create Date: 2026-10-25

Why
===
종목 기록에 한국 종목 공시를 끼운다 (services/filing_timeline/dart.py). DART
공시는 양식 코드가 아니라 공식 보고서명(``report_nm`` — "분기보고서 (2026.06)",
"연결재무제표기준영업(잠정)실적(공정공시)" …)으로 구분되므로 그 이름을 그대로
둘 칸이 필요하다. SEC 행은 비워 둔다.

Legal / privacy posture
-----------------------
공개된 공시 제목뿐이다. 개인정보 없음. 요약·평가가 아니라 금융감독원이 붙인
공식 이름이다.

Idempotency
-----------
app.py ``_do_migrations`` 가 같은 컬럼을 런타임에 더할 수 있으므로 Inspector 로
보고 없을 때만 더한다.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "066_company_filing_title"
down_revision = "065_company_filings"
branch_labels = None
depends_on = None

_TABLE = "company_filings"
_COLUMN = "title"


def _columns() -> set[str]:
    insp = inspect(op.get_bind())
    if _TABLE not in set(insp.get_table_names()):
        return set()
    return {c["name"] for c in insp.get_columns(_TABLE)}


def upgrade():
    cols = _columns()
    if cols and _COLUMN not in cols:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=200), nullable=True))


def downgrade():
    if _COLUMN in _columns():
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COLUMN)
