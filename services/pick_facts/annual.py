"""공시 원천 → 회계연도별 연간 숫자 (순수 함수 — 네트워크·DB 없음).

미국 (SEC ``companyfacts``)
--------------------------
XBRL 사실마다 ``end`` · ``val`` · ``fp`` · ``form`` · ``filed`` (+ 기간값은
``start``)가 붙는다. 연간 보고(10-K · 20-F · 40-F 와 정정)의 ``fp == "FY"`` 만
쓰고, 기간값(매출·순이익)은 330~400일짜리만 연간으로 본다. 같은 회계연도 값은
다음 해 보고서에 비교값으로 다시 실리므로 **가장 먼저 공시된 값**을 둔다.
한 해의 ``filed_on`` 은 그 해 숫자들 중 가장 늦게 공시된 날 — 모두 알려진 날이다.

개념 이름은 회사마다 다르다: 매출은 ``RevenueFromContractWithCustomer…`` /
``Revenues`` …, 해외 기업은 ``ifrs-full`` 의 ``Revenue`` · ``ProfitLoss`` ….
총부채가 없으면 ``LiabilitiesAndStockholdersEquity − 자본`` 으로 메운다.

한국 (OpenDART 단일회사 주요계정, 사업보고서 ``11011``)
--------------------------------------------------------
``account_nm`` 매출액·당기순이익·부채총계·자본총계, 연결(CFS) 우선. 당기
(``thstrm``)는 그 사업연도, 전기(``frmtrm``)는 한 해 전 값이다. 공시일은 접수번호
앞 8자리. 12월 결산을 가정한다 — 다른 결산월 회사는 회계연도 끝이 어긋날 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})

_US_REVENUE = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)
_US_NET_INCOME = ("NetIncomeLoss", "ProfitLoss")
_US_LIABILITIES = ("Liabilities",)
_US_EQUITY = ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")
_US_LIAB_AND_EQUITY = ("LiabilitiesAndStockholdersEquity",)

_IFRS_REVENUE = ("Revenue", "RevenueFromContractsWithCustomers")
_IFRS_NET_INCOME = ("ProfitLoss",)
_IFRS_LIABILITIES = ("Liabilities",)
_IFRS_EQUITY = ("Equity",)


@dataclass(frozen=True)
class AnnualRow:
    fiscal_end: date
    filed_on: date
    revenue: float | None = None
    net_income: float | None = None
    liabilities: float | None = None
    equity: float | None = None
    currency: str | None = None


def _day(raw) -> date | None:
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except ValueError:
        return None


def _series(group: dict, concepts: tuple[str, ...], *, flow: bool) -> tuple[dict[date, tuple[float, date]], str | None]:
    """개념 우선순위대로 {회계연도 끝: (값, 처음 공시일)} — 먼저 나온 개념이 그 해를 채운다."""
    out: dict[date, tuple[float, date]] = {}
    unit_used = None
    for concept in concepts:
        units = ((group.get(concept) or {}).get("units") or {})
        for unit, facts in units.items():
            if "/" in unit:  # USD/shares 따위
                continue
            for f in facts or []:
                if f.get("fp") != "FY" or f.get("form") not in ANNUAL_FORMS:
                    continue
                end, filed = _day(f.get("end")), _day(f.get("filed"))
                if end is None or filed is None or f.get("val") is None:
                    continue
                if flow:
                    start = _day(f.get("start"))
                    if start is None or not 330 <= (end - start).days <= 400:
                        continue
                prev = out.get(end)
                if prev is None or filed < prev[1]:
                    out[end] = (float(f["val"]), filed)
                    unit_used = unit_used or unit
    return out, unit_used


def annual_rows_from_companyfacts(payload: dict | None) -> list[AnnualRow]:
    facts = (payload or {}).get("facts") or {}
    gaap, ifrs = facts.get("us-gaap") or {}, facts.get("ifrs-full") or {}
    group, names = (gaap, (_US_REVENUE, _US_NET_INCOME, _US_LIABILITIES, _US_EQUITY)) if gaap else (
        ifrs, (_IFRS_REVENUE, _IFRS_NET_INCOME, _IFRS_LIABILITIES, _IFRS_EQUITY))
    revenue, cur = _series(group, names[0], flow=True)
    net_income, cur2 = _series(group, names[1], flow=True)
    liabilities, _ = _series(group, names[2], flow=False)
    equity, _ = _series(group, names[3], flow=False)
    if gaap:
        total, _ = _series(group, _US_LIAB_AND_EQUITY, flow=False)
        for end, (val, filed) in total.items():
            if end not in liabilities and end in equity:
                liabilities[end] = (val - equity[end][0], max(filed, equity[end][1]))
    rows = []
    for end in sorted(set(revenue) | set(net_income)):
        parts = [s[end] for s in (revenue, net_income, liabilities, equity) if end in s]
        rows.append(AnnualRow(
            fiscal_end=end,
            filed_on=max(p[1] for p in parts),
            revenue=revenue.get(end, (None,))[0],
            net_income=net_income.get(end, (None,))[0],
            liabilities=liabilities.get(end, (None,))[0],
            equity=equity.get(end, (None,))[0],
            currency=cur or cur2,
        ))
    return rows


_KR_REVENUE = ("매출액", "수익(매출액)", "영업수익", "매출")
_KR_NET_INCOME = ("당기순이익", "당기순이익(손실)", "당기순손익")
_KR_LIABILITIES = ("부채총계",)
_KR_EQUITY = ("자본총계",)


def _amount(raw) -> float | None:
    s = str(raw if raw is not None else "").replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def annual_rows_from_dart(rows: list[dict] | None, bsns_year: int) -> list[AnnualRow]:
    """사업보고서 주요계정 → [그 해, 한 해 전] (연결 우선, 없으면 별도)."""
    rows = rows or []
    picked = [r for r in rows if r.get("fs_div") == "CFS"] or [r for r in rows if r.get("fs_div") == "OFS"]
    if not picked:
        return []
    rcept = str(picked[0].get("rcept_no") or "")
    filed = _day(f"{rcept[:4]}-{rcept[4:6]}-{rcept[6:8]}") if len(rcept) >= 8 else None
    if filed is None:
        return []

    def find(names: tuple[str, ...], key: str) -> float | None:
        for name in names:
            for r in picked:
                if (r.get("account_nm") or "").strip() == name:
                    v = _amount(r.get(key))
                    if v is not None:
                        return v
        return None

    currency = (picked[0].get("currency") or "KRW").strip() or "KRW"
    out = []
    for key, year in (("thstrm_amount", bsns_year), ("frmtrm_amount", bsns_year - 1)):
        row = AnnualRow(
            fiscal_end=date(year, 12, 31), filed_on=filed,
            revenue=find(_KR_REVENUE, key), net_income=find(_KR_NET_INCOME, key),
            liabilities=find(_KR_LIABILITIES, key), equity=find(_KR_EQUITY, key), currency=currency,
        )
        if row.revenue is not None or row.net_income is not None:
            out.append(row)
    return out


def earliest_per_year(rows: list[AnnualRow]) -> list[AnnualRow]:
    """같은 회계연도가 여러 번 오면 가장 먼저 공시된 것만 (비교값으로 다시 실린 것 제외)."""
    best: dict[date, AnnualRow] = {}
    for r in rows:
        cur = best.get(r.fiscal_end)
        if cur is None or r.filed_on < cur.filed_on:
            best[r.fiscal_end] = r
        elif r.filed_on == cur.filed_on:
            best[r.fiscal_end] = replace(cur, **{k: getattr(r, k) for k in ("revenue", "net_income", "liabilities", "equity")
                                                 if getattr(cur, k) is None and getattr(r, k) is not None})
    return [best[k] for k in sorted(best)]


__all__ = ["AnnualRow", "annual_rows_from_companyfacts", "annual_rows_from_dart", "earliest_per_year"]
