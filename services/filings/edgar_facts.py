"""SEC EDGAR companyfacts → 보유 종목 공시 사실표 (미국 상장사).

시세를 쓰지 않는다. 입력은 SEC XBRL companyfacts JSON 하나뿐이고, 출력은
:mod:`services.filings` 의 공통 사실표 dict 다. 순수 함수라 고정 JSON 으로
결정론적으로 테스트된다 (네트워크는 :func:`fetch_companyfacts` 만).

XBRL 을 그대로 읽으면 틀리기 쉬운 곳 (2026-10-06 실데이터로 확인):

* **회사가 태그를 바꾼다.** 같은 계정에 후보 태그가 여럿이면 *가장 최근 기간까지*
  공시된 태그를 고른다. 첫 번째로 존재하는 태그를 고르면 합병 전 옛 숫자를 집는다
  (ABTC: 적자인데 양의 EPS 가 나왔다).
* **10-Q 현금흐름표는 누적(YTD)이다.** 3개월 값이 없으면 같은 시작일의 누적값
  차분으로 분기값을 만든다. 4분기는 연간 − 9개월 누적.
* **현금만 보면 안 된다.** 단기투자자산을 같은 날짜로 더한다 (JOBY: 현금 $630M,
  단기투자 $1.63B).
* **표지 주식 수(dei)는 합병·다중 클래스에서 끊긴다.** 분기 가중평균 주식 수를 쓴다.
"""
from __future__ import annotations

from datetime import date

from services.filings.common import build_facts, quarterly_from_spans

_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}

REVENUE = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)
NET_INCOME = ("NetIncomeLoss", "ProfitLoss")
OPERATING_CF = (
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
)
CASH = (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
)
SHORT_TERM_INV = (
    "ShortTermInvestments",
    "MarketableSecuritiesCurrent",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
)
LIABILITIES = ("Liabilities",)
EQUITY = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
SHARES = (
    "WeightedAverageNumberOfSharesOutstandingBasic",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
)


def _rows(facts: dict, concepts: tuple[str, ...], unit: str) -> list[dict]:
    """후보 태그 중 가장 최근 기간까지 공시된 태그의 10-K/10-Q 행."""
    best: list[dict] = []
    best_end = ""
    gaap = facts.get("us-gaap", {})
    for concept in concepts:
        node = gaap.get(concept)
        if not node:
            continue
        rows = [e for e in node.get("units", {}).get(unit, []) if e.get("form") in _FORMS]
        if not rows:
            continue
        end = max(e["end"] for e in rows)
        if end > best_end:
            best, best_end = rows, end
    return best


def _spans(rows: list[dict]) -> dict[tuple[str, str], float]:
    # 같은 기간이 여러 공시에 나오면 나중 공시(정정 포함)가 이긴다.
    return {(e["start"], e["end"]): e["val"] for e in rows if "start" in e}


def _instants(rows: list[dict]) -> dict[str, float]:
    return {e["end"]: e["val"] for e in rows if "start" not in e}


def compute(companyfacts: dict) -> dict | None:
    """companyfacts JSON → 공통 사실표. 손익 데이터가 없으면 None."""
    facts = companyfacts.get("facts") or {}
    revenue = quarterly_from_spans(_spans(_rows(facts, REVENUE, "USD")))
    net_income = quarterly_from_spans(_spans(_rows(facts, NET_INCOME, "USD")))
    if not revenue and not net_income:
        return None
    operating_cf = quarterly_from_spans(_spans(_rows(facts, OPERATING_CF, "USD")))

    cash = _instants(_rows(facts, CASH, "USD"))
    short_term = _instants(_rows(facts, SHORT_TERM_INV, "USD"))
    cash_end = max(cash) if cash else None
    cash_total = None
    if cash_end:
        cash_total = cash[cash_end] + short_term.get(cash_end, 0)

    shares = {
        end: v
        for (start, end), v in _spans(_rows(facts, SHARES, "shares")).items()
        if 80 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 100
    }

    return build_facts(
        source="SEC EDGAR",
        entity_name=companyfacts.get("entityName") or "",
        currency="USD",
        revenue=revenue,
        net_income=net_income,
        operating_cf=operating_cf,
        cash=(cash_end, cash_total) if cash_end else None,
        cash_includes_short_term=bool(cash_end and cash_end in short_term),
        liabilities=_latest(_instants(_rows(facts, LIABILITIES, "USD"))),
        equity=_latest(_instants(_rows(facts, EQUITY, "USD"))),
        shares=dict(sorted(shares.items())),
    )


def _latest(series: dict[str, float]) -> tuple[str, float] | None:
    if not series:
        return None
    end = max(series)
    return end, series[end]


def fetch_companyfacts(ticker: str) -> dict | None:
    """티커 → companyfacts JSON (수 MB — 캐시하지 않는다, 계산 결과를 캐시한다).

    SEC 호출·스로틀·CIK 맵은 EdgarService 를 재사용한다.
    """
    from services.data.edgar import EdgarService

    cik = EdgarService.get_cik(ticker)
    if not cik:
        return None
    return EdgarService._get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
