"""CompanyAnnualFact — 회사 한 곳의 연간 숫자 한 해치 (내가 고른 회사들 카드용).

docs: services/pick_facts/__init__.py. 유저가 산 회사가 "산 날 직전에 공시된
연간 보고"에서 어떤 숫자였는지(순이익·매출·부채·자본)를 세려고, 공시 원천에서
연간 값만 골라 둔다.

- ``source="sec"``  미국 — SEC ``companyfacts`` (XBRL). 같은 회계연도 값이 여러
  보고서에 다시 실리므로 **가장 먼저 공시된 값**만 둔다.
- ``source="dart"`` 한국 — OpenDART 단일회사 주요계정(사업보고서). 연결 우선.

무엇이 아닌가
-------------
- 유저 데이터가 아니다 — ``user_id`` 없음, 모든 유저가 같은 행을 읽는다.
- 시세가 아니다. 주가·시가총액·PER 이 없다.
- 평가가 아니다. 점수·등급·"좋은 회사" 판정이 없다 — 공시된 숫자뿐이다.
- ``filed_on`` 이 핵심이다: 그날 이전에 산 유저에게는 이 숫자를 대지 않는다
  (산 뒤에 나온 숫자로 과거 결정을 비추지 않는다).

스키마는 ``migrations/versions/067_company_annual_facts.py`` 와 1:1.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompanyAnnualFact(db.Model):
    __tablename__ = "company_annual_facts"
    __table_args__ = (
        db.UniqueConstraint("source", "ticker", "fiscal_end", name="uq_company_annual_facts_source_ticker_end"),
        db.Index("idx_company_annual_facts_ticker", "ticker"),
    )

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(8), nullable=False)
    # friction_outcome.ticker_key 값 (대문자, 거래소 접미사 없음).
    ticker = db.Column(db.String(20), nullable=False)
    fiscal_end = db.Column(db.Date, nullable=False)
    # 이 숫자가 처음 공시된 날 — 이 날짜 이후에 산 결정에만 댄다.
    filed_on = db.Column(db.Date, nullable=False)
    revenue = db.Column(db.Float, nullable=True)
    net_income = db.Column(db.Float, nullable=True)
    liabilities = db.Column(db.Float, nullable=True)
    equity = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(8), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return f"<CompanyAnnualFact {self.ticker} {self.fiscal_end} filed {self.filed_on}>"
