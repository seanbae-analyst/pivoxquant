"""SEC 공시 목록 → 보여 줄 공시 행 (순수 함수 — 네트워크·DB 없음).

``data.sec.gov/submissions/CIK##########.json`` 의 ``filings.recent`` 는 열
이름별 평행 배열이다 (``form[i]`` · ``filingDate[i]`` · ``items[i]`` …). 여기서
회사가 스스로 낸 정기·수시 보고만 골라 행으로 바꾼다.

고르는 양식
-----------
* 연간보고서 10-K · 20-F · 40-F(해외 기업) / 분기보고서 10-Q
* 수시보고 8-K · 6-K(해외 기업). 8-K 중 항목 2.02(Results of Operations and
  Financial Condition)는 "실적 발표"
* 위 양식의 정정(/A)
* 빼는 것: Form 4 등 내부자 거래 보고(종목에 따라 연 수백 건이고 '따라 사기'
  신호로 읽힌다), 13G 등 남이 낸 대량보유 보고, 424B·FWP 등 증권 발행 서류

시각을 쓰지 않는다
------------------
``acceptanceDateTime`` 은 "Z" 를 달고 있지만 회사·날짜마다 미 동부 시각이
섞여 몇 시간씩 어긋난다는 보고가 있다 (2026-10, edgartools #1501 등). 그래서
SEC 가 매긴 공식 공시일 ``filingDate`` (미 동부 날짜)만 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

EARNINGS_ITEM = "2.02"

# 이름표는 사실의 이름이다 — 무엇이 났는지만 말하고 좋다/나쁘다를 말하지 않는다.
_PERIODIC = {
    "10-K": "연간보고서",
    "20-F": "연간보고서",
    "40-F": "연간보고서",
    "10-Q": "분기보고서",
}
_CURRENT = {
    "8-K": "수시보고",
    "6-K": "수시보고",
}
SHOWN_FORMS = frozenset(_PERIODIC) | frozenset(_CURRENT)

_ARCHIVE = "https://www.sec.gov/Archives/edgar/data"


@dataclass(frozen=True)
class ParsedFiling:
    accession: str
    form: str
    items: str
    filed_on: date
    url: str
    title: str | None = None  # DART 공식 보고서명 (SEC 는 None)


def _base_form(form: str) -> tuple[str, bool]:
    f = (form or "").strip().upper()
    if f.endswith("/A"):
        return f[:-2], True
    return f, False


def _items(raw: str | None) -> set[str]:
    return {p.strip() for p in (raw or "").split(",") if p.strip()}


def is_shown(form: str) -> bool:
    return _base_form(form)[0] in SHOWN_FORMS


def is_earnings(form: str, items: str | None) -> bool:
    """8-K 항목 2.02 원본 한 건. 정정(8-K/A)은 같은 발표를 두 번 세지 않게 뺀다."""
    base, amended = _base_form(form)
    return base == "8-K" and not amended and EARNINGS_ITEM in _items(items)


def label_for(form: str, items: str | None) -> str | None:
    """화면 이름표. 보여 주지 않는 양식이면 None."""
    base, amended = _base_form(form)
    if base in _PERIODIC:
        label = _PERIODIC[base]
    elif base == "8-K" and EARNINGS_ITEM in _items(items):
        label = "실적 발표"
    elif base in _CURRENT:
        label = _CURRENT[base]
    else:
        return None
    return f"{label} 정정" if amended else label


def filing_url(cik: str | int | None, accession: str, primary_document: str | None) -> str:
    """원문 주소. 본문 파일 이름이 없으면 공시 색인 페이지."""
    try:
        cik_int = int(str(cik or "").strip())
    except ValueError:
        cik_int = 0
    folder = f"{_ARCHIVE}/{cik_int}/{accession.replace('-', '')}"
    doc = (primary_document or "").strip()
    return f"{folder}/{doc}" if doc else f"{folder}/{accession}-index.htm"


def _parse_day(raw: str | None) -> date | None:
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except ValueError:
        return None


def parse_recent(payload: dict | None, cik: str | int | None) -> list[ParsedFiling]:
    """``filings.recent`` → 보여 줄 공시만, SEC 순서(최신 먼저) 그대로.

    배열 길이가 어긋나거나 날짜·접수번호가 비면 그 행만 건너뛴다.
    """
    recent = ((payload or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    days = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    items = recent.get("items") or []
    docs = recent.get("primaryDocument") or []

    out: list[ParsedFiling] = []
    for i, form in enumerate(forms):
        if not is_shown(form):
            continue
        accession = str(accessions[i]).strip() if i < len(accessions) else ""
        filed_on = _parse_day(days[i]) if i < len(days) else None
        if not accession or filed_on is None:
            continue
        item = str(items[i] or "").strip() if i < len(items) else ""
        doc = docs[i] if i < len(docs) else None
        out.append(ParsedFiling(
            accession=accession,
            form=str(form).strip().upper(),
            items=item,
            filed_on=filed_on,
            url=filing_url(cik, accession, doc),
        ))
    return out
