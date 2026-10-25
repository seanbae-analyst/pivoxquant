"""CompanyFiling — 미국 회사가 SEC 에 낸 공시 한 건 (종목 기록 타임라인용).

docs: services/filing_timeline/__init__.py. 종목별 내 기록(/journal/stock/<ticker>)
에 "그 종목에 무슨 공시가 났나"를 유저 기록 사이에 끼우려고, SEC EDGAR 공시
목록(``data.sec.gov/submissions``)에서 보여 줄 양식만 골라 저장한다.

무엇이 아닌가
-------------
- 유저 데이터가 아니다. 공개된 사실(양식 · 공식 공시일 · 원문 주소)이라
  ``user_id`` 가 없고 모든 유저가 같은 행을 읽는다. 탈퇴 삭제 대상도 아니다.
- 해석이 아니다. 제목·요약·평가를 저장하지 않는다 — 화면 이름표("분기보고서",
  "실적 발표")는 읽을 때 ``form`` · ``items`` 에서 고정 목록으로 붙인다.
- 시각이 아니다. SEC 목록의 ``acceptanceDateTime`` 은 회사·날짜마다 몇 시간씩
  어긋난다는 보고가 있어(2026-10) 쓰지 않고, 공식 공시일(미 동부 날짜)만 둔다.

스키마는 ``migrations/versions/065_company_filings.py`` 와 1:1.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db

SOURCE_SEC = "sec"

TICKER_MAX_LEN = 20       # pre_trade_reflections / research_notes 와 동일
ACCESSION_MAX_LEN = 25    # "0000320193-26-000020" = 20자
FORM_MAX_LEN = 16         # "10-K/A", "SCHEDULE 13G/A" …
ITEMS_MAX_LEN = 64        # 8-K 항목 "2.02,9.01"
URL_MAX_LEN = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompanyFiling(db.Model):
    __tablename__ = "company_filings"
    __table_args__ = (
        # 같은 공시가 두 표기의 종목(GOOG · GOOGL)에 각각 들어갈 수 있어 종목까지 묶는다.
        db.UniqueConstraint("source", "ticker", "accession", name="uq_company_filings_source_ticker_accession"),
        db.Index("idx_company_filings_ticker_filed", "ticker", "filed_on"),
    )

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(8), nullable=False, default=SOURCE_SEC)
    # friction_outcome.ticker_key 값 (대문자, 거래소 접미사 없음).
    ticker = db.Column(db.String(TICKER_MAX_LEN), nullable=False)
    cik = db.Column(db.String(10), nullable=True)
    accession = db.Column(db.String(ACCESSION_MAX_LEN), nullable=False)
    form = db.Column(db.String(FORM_MAX_LEN), nullable=False)
    items = db.Column(db.String(ITEMS_MAX_LEN), nullable=True)
    # SEC 공식 공시일 (미 동부 날짜). 17:30 ET 뒤 접수분은 다음 영업일이 된다.
    filed_on = db.Column(db.Date, nullable=False)
    url = db.Column(db.String(URL_MAX_LEN), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return f"<CompanyFiling {self.ticker} {self.form} {self.filed_on}>"
