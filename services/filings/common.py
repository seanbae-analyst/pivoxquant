"""공시 사실표 공통 계산 — EDGAR·DART 가 같은 모양을 내보낸다.

여기 있는 건 산수뿐이다: 분기화 · 최근 4분기 합 · 연속 흑자/적자 분기 수 ·
현금 ÷ 영업현금 유출 · 부채/자본 · 주식 수 1년 변화. 점수·등급·판정 어휘는 없다
(DECISIONS.md — 점수화 폐기). 숫자를 합쳐 하나의 지표로 만들지 않는다.
"""
from __future__ import annotations

from datetime import date

QUARTER_DAYS = (80, 100)
RECENT_QUARTERS = 5


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def quarterly_from_spans(spans: dict[tuple[str, str], float]) -> dict[str, float]:
    """기간값 {(start, end): val} → 분기값 {end: val}, end 오름차순.

    3개월 값이 있으면 그대로 쓰고, 없으면 같은 시작일의 누적값끼리 차분한다
    (6개월 − 3개월, 9개월 − 6개월, 연간 − 9개월).
    """
    q: dict[str, float] = {}
    for (start, end), v in spans.items():
        if QUARTER_DAYS[0] <= _days(start, end) <= QUARTER_DAYS[1]:
            q[end] = v
    for (start, end), v in spans.items():
        if end in q or _days(start, end) < 150:
            continue
        for (s2, e2), v2 in spans.items():
            if s2 == start and QUARTER_DAYS[0] <= _days(e2, end) <= QUARTER_DAYS[1]:
                q[end] = v - v2
                break
    return dict(sorted(q.items()))


def trailing_four(q: dict[str, float]) -> float | None:
    """최근 4분기 합. 4개가 안 되거나 사이에 빈 분기가 있으면 None."""
    ends = list(q)[-4:]
    if len(ends) < 4 or _days(ends[0], ends[-1]) > 300:
        return None
    return sum(q[e] for e in ends)


def _streak(values: list[float]) -> dict | None:
    if not values:
        return None
    profit = values[-1] >= 0
    n = 0
    for v in reversed(values):
        if (v >= 0) != profit:
            break
        n += 1
    return {"kind": "profit" if profit else "loss", "quarters": n}


def _shares_change(shares: dict[str, float]) -> dict | None:
    if len(shares) < 2:
        return None
    end, now = list(shares.items())[-1]
    for e0, then in reversed(list(shares.items())[:-1]):
        if 330 <= _days(e0, end) <= 400 and then:
            return {"from": e0, "to": end, "pct": (now - then) / then}
    return None


def build_facts(
    *,
    source: str,
    entity_name: str,
    currency: str,
    revenue: dict[str, float],
    net_income: dict[str, float],
    operating_cf: dict[str, float],
    cash: tuple[str, float] | None,
    cash_includes_short_term: bool,
    liabilities: tuple[str, float] | None,
    equity: tuple[str, float] | None,
    shares: dict[str, float],
) -> dict:
    ends = sorted(set(revenue) | set(net_income))[-RECENT_QUARTERS:]
    ni_ttm = trailing_four(net_income)
    ocf_ttm = trailing_four(operating_cf)

    runway = None
    if cash and ocf_ttm is not None and ocf_ttm < 0 and cash[1] is not None:
        runway = cash[1] / -ocf_ttm * 12

    per_share = None
    if ni_ttm is not None and shares:
        latest_shares = list(shares.values())[-1]
        if latest_shares:
            per_share = ni_ttm / latest_shares

    debt_ratio = None
    if liabilities and equity and equity[1] and equity[1] > 0:
        debt_ratio = {"as_of": liabilities[0], "value": liabilities[1] / equity[1]}

    return {
        "source": source,
        "entity_name": entity_name,
        "currency": currency,
        "as_of": ends[-1] if ends else None,
        "quarters": [
            {"end": e, "revenue": revenue.get(e), "net_income": net_income.get(e)}
            for e in ends
        ],
        "revenue_ttm": trailing_four(revenue),
        "net_income_ttm": ni_ttm,
        "net_income_streak": _streak(list(net_income.values())),
        "net_income_per_share_ttm": per_share,
        "cash": (
            {"as_of": cash[0], "value": cash[1], "includes_short_term": cash_includes_short_term}
            if cash else None
        ),
        "operating_cf_ttm": ocf_ttm,
        "cash_months_at_ttm_burn": runway,
        "liabilities_to_equity": debt_ratio,
        "shares_change_1y": _shares_change(shares),
    }
