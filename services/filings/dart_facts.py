"""DART 전체 재무제표 → 보유 종목 공시 사실표 (한국 상장사).

시세를 쓰지 않는다. 금융감독원 OpenDART ``fnlttSinglAcntAll.json`` (전체
재무제표)만 읽는다. 키는 ``DART_API_KEY`` — 없으면 None 을 돌려준다.

이용 근거 (2026-10-06 공식 원문 확인): OpenDART FAQ "공시정보를 상업적으로
사용해도 되나요?" — 공공데이터법상 공공데이터라 "데이터의 공개 및 활용은 제한되지
않습니다", 단 "재배포 및 재가공과 관련한 모든 책임은 이용자 부담". 한도는 키당
일 20,000건 · 분당 1,000회 미만.

금액 규약 (개발가이드 fnlttSinglAcntAll):

* 손익계산서(IS/CIS) ``thstrm_amount`` = 그 분기 3개월, ``thstrm_add_amount`` =
  당기 누적. 사업보고서(11011)의 ``thstrm_amount`` 는 연간.
* 현금흐름표(CF) ``thstrm_amount`` 는 누적이다 → 공통 분기화(차분)로 넘긴다.
* 재무상태표(BS) ``thstrm_amount`` 는 분기말 잔액.

12월 결산을 가정한다 (보고서 코드 → 기간 매핑). 비12월 결산 회사는 분기 날짜가
어긋날 수 있다.
"""
from __future__ import annotations

import io
import logging
import os
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

from services.filings.common import build_facts, quarterly_from_spans, trailing_four

logger = logging.getLogger(__name__)

BASE = "https://opendart.fss.or.kr/api"
TIMEOUT = 15

# reprt_code → (분기 시작 MM-DD, 분기 끝 MM-DD)
REPORTS = (
    ("11013", "01-01", "03-31"),
    ("11012", "04-01", "06-30"),
    ("11014", "07-01", "09-30"),
    ("11011", "10-01", "12-31"),
)

REVENUE = ("ifrs-full_Revenue", "ifrs_Revenue")
REVENUE_NAMES = ("매출액", "수익(매출액)", "영업수익", "매출")
NET_INCOME = ("ifrs-full_ProfitLoss", "ifrs_ProfitLoss")
EPS = ("ifrs-full_BasicEarningsLossPerShare", "ifrs_BasicEarningsLossPerShare")
OPERATING_CF = (
    "ifrs-full_CashFlowsFromUsedInOperatingActivities",
    "ifrs_CashFlowsFromUsedInOperatingActivities",
)
CASH = ("ifrs-full_CashAndCashEquivalents", "ifrs_CashAndCashEquivalents")
SHORT_TERM_INV = (
    "dart_ShortTermDepositsNotClassifiedAsCashEquivalents",
    "ifrs-full_ShortTermInvestments",
)
LIABILITIES = ("ifrs-full_Liabilities", "ifrs_Liabilities")
EQUITY = ("ifrs-full_Equity", "ifrs_Equity")

CORP_CODE_TTL = 7 * 86400
_corp_codes: dict[str, tuple[str, str]] = {}  # stock_code → (corp_code, corp_name)
_corp_codes_at = 0.0
_corp_lock = threading.Lock()


def api_key() -> str:
    return os.environ.get("DART_API_KEY", "").strip()


def _amount(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _get(path: str, **params):
    import requests

    params["crtfc_key"] = api_key()
    resp = requests.get(f"{BASE}/{path}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def corp_code_for(stock_code: str) -> tuple[str, str] | None:
    """6자리 종목코드 → (8자리 DART 고유번호, 회사명). corpCode.xml ZIP, 7일 캐시."""
    global _corp_codes_at
    with _corp_lock:
        if not _corp_codes or time.time() - _corp_codes_at > CORP_CODE_TTL:
            resp = _get("corpCode.xml")
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                xml = zf.read(zf.namelist()[0])
            mapping = {}
            for item in ET.fromstring(xml).iter("list"):
                stock = (item.findtext("stock_code") or "").strip()
                if stock:
                    mapping[stock] = (
                        item.findtext("corp_code").strip(),
                        (item.findtext("corp_name") or "").strip(),
                    )
            if mapping:
                _corp_codes.clear()
                _corp_codes.update(mapping)
                _corp_codes_at = time.time()
        return _corp_codes.get(stock_code)


def fetch_report(corp_code: str, year: int, reprt_code: str) -> list[dict] | None:
    """한 보고서의 전체 재무제표 행. 연결(CFS) 우선, 없으면 개별(OFS)."""
    for fs_div in ("CFS", "OFS"):
        body = _get(
            "fnlttSinglAcntAll.json",
            corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code, fs_div=fs_div,
        ).json()
        if body.get("status") == "000" and body.get("list"):
            return body["list"]
        if body.get("status") not in ("013", None):  # 013 = 데이터 없음
            logger.warning("DART %s %s %s %s: %s", corp_code, year, reprt_code, fs_div, body.get("message"))
            if body.get("status") == "020":  # 한도 초과 — 더 부르지 않는다
                return None
    return None


def _pick(rows: list[dict], sj: tuple[str, ...], ids: tuple[str, ...], names: tuple[str, ...] = ()) -> dict | None:
    cands = [r for r in rows if r.get("sj_div") in sj]
    for account_id in ids:
        for r in cands:
            if r.get("account_id") == account_id:
                return r
    for name in names:
        for r in cands:
            if (r.get("account_nm") or "").replace(" ", "") == name:
                return r
    return None


def compute(reports: dict[tuple[int, str], list[dict]], entity_name: str = "") -> dict | None:
    """{(연도, reprt_code): 행 목록} → 공통 사실표. 손익이 하나도 없으면 None."""
    spans: dict[str, dict[tuple[str, str], float]] = {
        "revenue": {}, "net_income": {}, "eps": {}, "operating_cf": {},
    }
    instants: dict[str, dict[str, float]] = {
        "cash": {}, "short_term": {}, "liabilities": {}, "equity": {},
    }
    by_code = {code: (qs, qe) for code, qs, qe in REPORTS}

    for (year, code), rows in reports.items():
        q_start, q_end = (f"{year}-{d}" for d in by_code[code])
        fy_start = f"{year}-01-01"
        annual = code == "11011"
        for key, ids, names in (
            ("revenue", REVENUE, REVENUE_NAMES),
            ("net_income", NET_INCOME, ()),
            ("eps", EPS, ()),
        ):
            r = _pick(rows, ("IS", "CIS"), ids, names)
            if not r:
                continue
            this = _amount(r.get("thstrm_amount"))
            if annual:
                if this is not None:
                    spans[key][(fy_start, q_end)] = this
                continue
            if this is not None:
                spans[key][(q_start, q_end)] = this
            cum = _amount(r.get("thstrm_add_amount"))
            if cum is not None and q_start != fy_start:
                spans[key][(fy_start, q_end)] = cum
        r = _pick(rows, ("CF",), OPERATING_CF)
        if r and _amount(r.get("thstrm_amount")) is not None:
            spans["operating_cf"][(fy_start, q_end)] = _amount(r["thstrm_amount"])
        for key, ids in (
            ("cash", CASH), ("short_term", SHORT_TERM_INV),
            ("liabilities", LIABILITIES), ("equity", EQUITY),
        ):
            r = _pick(rows, ("BS",), ids)
            if r and _amount(r.get("thstrm_amount")) is not None:
                instants[key][q_end] = _amount(r["thstrm_amount"])

    revenue = quarterly_from_spans(spans["revenue"])
    net_income = quarterly_from_spans(spans["net_income"])
    if not revenue and not net_income:
        return None

    cash = instants["cash"]
    cash_end = max(cash) if cash else None
    cash_total = None
    if cash_end:
        cash_total = cash[cash_end] + instants["short_term"].get(cash_end, 0)

    def latest(series):
        return (max(series), series[max(series)]) if series else None

    facts = build_facts(
        source="DART",
        entity_name=entity_name,
        currency="KRW",
        revenue=revenue,
        net_income=net_income,
        operating_cf=quarterly_from_spans(spans["operating_cf"]),
        cash=(cash_end, cash_total) if cash_end else None,
        cash_includes_short_term=bool(cash_end and cash_end in instants["short_term"]),
        liabilities=latest(instants["liabilities"]),
        equity=latest(instants["equity"]),
        shares={},
    )
    # 재무제표에 주식 수가 없다 → 분기 기본주당순이익 4개 합으로 대신한다.
    facts["net_income_per_share_ttm"] = trailing_four(quarterly_from_spans(spans["eps"]))
    return facts


def facts_for(ticker: str, today: date | None = None) -> dict | None:
    if not api_key():
        logger.warning("DART_API_KEY unset — KR filing facts unavailable")
        return None
    stock_code = ticker.upper().split(".")[0]
    found = corp_code_for(stock_code)
    if not found:
        return None
    corp_code, entity_name = found
    today = today or date.today()
    reports: dict[tuple[int, str], list[dict]] = {}
    for y in (today.year - 2, today.year - 1, today.year):
        for code, _, q_end in REPORTS:
            if date.fromisoformat(f"{y}-{q_end}") >= today:
                continue  # 아직 끝나지 않은 분기 — 공시가 있을 수 없다
            rows = fetch_report(corp_code, y, code)
            if rows:
                reports[(y, code)] = rows
    return compute(reports, entity_name)
