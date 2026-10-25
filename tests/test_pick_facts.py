"""tests/test_pick_facts.py — 내가 고른 회사들 (services/pick_facts).

Pins: annual values only (FY, ~1-year spans), the first-filed value of a year
wins over later comparatives, total liabilities filled from L+E − equity, the
IFRS path for foreign issuers, DART consolidated-first with this year and last;
a number filed on or after the buy day is never used (no look-ahead); counts
of net loss · revenue down · liabilities over equity over the year's first
buys only; at most SYNC_BUDGET source calls per request; flag off or no
source → nothing called; the route is auth-gated and carries no score words.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from extensions import db
from models import TradeHistory
from services.pick_facts import SYNC_BUDGET, as_of, pick_facts
from services.pick_facts import store
from services.pick_facts.annual import (
    AnnualRow, annual_rows_from_companyfacts, annual_rows_from_dart, earliest_per_year,
)

NOW = datetime(2026, 10, 20, 3, 0, 0)


def _fact(val, end, filed, start=None, form="10-K", fp="FY"):
    f = {"val": val, "end": end, "filed": filed, "form": form, "fp": fp}
    if start:
        f["start"] = start
    return f


def _companyfacts(rev, ni, liab, eq, unit="USD", taxonomy="us-gaap"):
    names = {
        "us-gaap": ("RevenueFromContractWithCustomerExcludingAssessedTax", "NetIncomeLoss", "Liabilities", "StockholdersEquity"),
        "ifrs-full": ("Revenue", "ProfitLoss", "Liabilities", "Equity"),
    }[taxonomy]
    return {"facts": {taxonomy: {
        names[0]: {"units": {unit: rev}}, names[1]: {"units": {unit: ni}},
        names[2]: {"units": {unit: liab}}, names[3]: {"units": {unit: eq}},
    }}}


# ── annual.py ───────────────────────────────────────────────────────────────


def test_annual_rows_first_filed_wins_and_quarters_are_ignored():
    payload = _companyfacts(
        rev=[
            _fact(100, "2024-12-31", "2025-02-10", start="2024-01-01"),
            _fact(999, "2024-12-31", "2026-02-10", start="2024-01-01"),        # comparative, later
            _fact(30, "2024-12-31", "2025-02-10", start="2024-10-01"),         # a quarter inside a 10-K
            _fact(120, "2025-12-31", "2026-02-10", start="2025-01-01"),
            _fact(50, "2025-06-30", "2025-08-01", start="2025-01-01", form="10-Q", fp="Q2"),
        ],
        ni=[_fact(-5, "2024-12-31", "2025-02-10", start="2024-01-01"),
            _fact(7, "2025-12-31", "2026-02-10", start="2025-01-01")],
        liab=[_fact(300, "2025-12-31", "2026-02-10")],
        eq=[_fact(100, "2025-12-31", "2026-02-10")],
    )
    rows = annual_rows_from_companyfacts(payload)
    assert [(r.fiscal_end, r.revenue, r.net_income) for r in rows] == [
        (date(2024, 12, 31), 100.0, -5.0), (date(2025, 12, 31), 120.0, 7.0),
    ]
    assert rows[0].filed_on == date(2025, 2, 10) and rows[1].liabilities == 300.0 and rows[1].currency == "USD"


def test_liabilities_from_total_and_ifrs_path():
    payload = _companyfacts(
        rev=[_fact(10, "2025-12-31", "2026-03-01", start="2025-01-01")],
        ni=[_fact(1, "2025-12-31", "2026-03-01", start="2025-01-01")],
        liab=[], eq=[_fact(40, "2025-12-31", "2026-03-01")],
    )
    payload["facts"]["us-gaap"]["LiabilitiesAndStockholdersEquity"] = {"units": {"USD": [_fact(100, "2025-12-31", "2026-03-01")]}}
    assert annual_rows_from_companyfacts(payload)[0].liabilities == 60.0
    ifrs = _companyfacts(
        rev=[_fact(5, "2025-12-31", "2026-04-15", start="2025-01-01", form="20-F")],
        ni=[_fact(2, "2025-12-31", "2026-04-15", start="2025-01-01", form="20-F")],
        liab=[_fact(3, "2025-12-31", "2026-04-15", form="20-F")],
        eq=[_fact(4, "2025-12-31", "2026-04-15", form="20-F")],
        unit="TWD", taxonomy="ifrs-full",
    )
    r = annual_rows_from_companyfacts(ifrs)[0]
    assert (r.revenue, r.net_income, r.liabilities, r.equity, r.currency) == (5.0, 2.0, 3.0, 4.0, "TWD")


def test_dart_annual_rows_consolidated_first():
    rows = [
        {"rcept_no": "20260310000123", "fs_div": "OFS", "account_nm": "매출액", "thstrm_amount": "1", "frmtrm_amount": "1", "currency": "KRW"},
        {"rcept_no": "20260310000123", "fs_div": "CFS", "account_nm": "매출액", "thstrm_amount": "3,000", "frmtrm_amount": "3,500", "currency": "KRW"},
        {"rcept_no": "20260310000123", "fs_div": "CFS", "account_nm": "당기순이익(손실)", "thstrm_amount": "-120", "frmtrm_amount": "80", "currency": "KRW"},
        {"rcept_no": "20260310000123", "fs_div": "CFS", "account_nm": "부채총계", "thstrm_amount": "900", "frmtrm_amount": "800", "currency": "KRW"},
        {"rcept_no": "20260310000123", "fs_div": "CFS", "account_nm": "자본총계", "thstrm_amount": "600", "frmtrm_amount": "700", "currency": "KRW"},
    ]
    out = annual_rows_from_dart(rows, 2025)
    assert [(r.fiscal_end, r.revenue, r.net_income, r.filed_on) for r in out] == [
        (date(2025, 12, 31), 3000.0, -120.0, date(2026, 3, 10)),
        (date(2024, 12, 31), 3500.0, 80.0, date(2026, 3, 10)),
    ]
    # The year's own report (filed earlier) beats the comparative in the next one.
    older = AnnualRow(fiscal_end=date(2024, 12, 31), filed_on=date(2025, 3, 11), revenue=3400.0)
    assert earliest_per_year(out + [older])[0].revenue == 3400.0


def test_as_of_never_uses_a_number_filed_after_the_buy():
    rows = [
        AnnualRow(date(2024, 12, 31), date(2025, 2, 10), revenue=100, net_income=5),
        AnnualRow(date(2025, 12, 31), date(2026, 2, 10), revenue=90, net_income=-1),
    ]
    latest, prev = as_of(rows, date(2026, 1, 15))
    assert latest.fiscal_end == date(2024, 12, 31) and prev is None
    latest, prev = as_of(rows, date(2026, 2, 11))
    assert latest.fiscal_end == date(2025, 12, 31) and prev.fiscal_end == date(2024, 12, 31)
    assert as_of(rows, date(2025, 2, 10)) is None   # the filing day itself is not "before"


# ── pick_facts (integration) ────────────────────────────────────────────────


def _buy(uid, ticker, at, name=""):
    db.session.add(TradeHistory(
        user_id=uid, ticker=ticker, name=name, action="BUY", shares=1.0, price_per_share=10.0,
        total_value=10.0, currency="USD", traded_at=at,
    ))
    db.session.commit()


FACTS = {
    # net loss
    "LOSS": _companyfacts(
        rev=[_fact(10, "2025-12-31", "2026-02-01", start="2025-01-01")],
        ni=[_fact(-3, "2025-12-31", "2026-02-01", start="2025-01-01")],
        liab=[_fact(5, "2025-12-31", "2026-02-01")], eq=[_fact(10, "2025-12-31", "2026-02-01")]),
    # revenue down vs the year before
    "DOWN": _companyfacts(
        rev=[_fact(100, "2024-12-31", "2025-02-01", start="2024-01-01"),
             _fact(80, "2025-12-31", "2026-02-01", start="2025-01-01")],
        ni=[_fact(4, "2025-12-31", "2026-02-01", start="2025-01-01")],
        liab=[_fact(5, "2025-12-31", "2026-02-01")], eq=[_fact(10, "2025-12-31", "2026-02-01")]),
    # liabilities over equity
    "LEV": _companyfacts(
        rev=[_fact(10, "2025-12-31", "2026-02-01", start="2025-01-01")],
        ni=[_fact(1, "2025-12-31", "2026-02-01", start="2025-01-01")],
        liab=[_fact(50, "2025-12-31", "2026-02-01")], eq=[_fact(10, "2025-12-31", "2026-02-01")]),
    # only filed after the buy → no number at the decision
    "LATE": _companyfacts(
        rev=[_fact(10, "2026-06-30", "2026-08-01", start="2025-07-01")],
        ni=[_fact(1, "2026-06-30", "2026-08-01", start="2025-07-01")],
        liab=[], eq=[]),
}


@pytest.fixture
def sec_facts(monkeypatch):
    from services.data.edgar import EdgarService

    calls = []

    def fake(cls, ticker, **_kw):
        calls.append(ticker)
        return "0000000001", FACTS.get(ticker)

    monkeypatch.setattr(EdgarService, "get_companyfacts", classmethod(fake))
    store.reset_sync_state()
    yield calls
    store.reset_sync_state()


def test_counts_over_first_buys_with_numbers_known_at_the_time(app, make_user, sec_facts, monkeypatch):
    monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
    monkeypatch.setattr("services.pick_facts.SYNC_BUDGET", 10)
    me = make_user(email="pf-me@test.com")["id"]
    with app.app_context():
        for t in ("LOSS", "DOWN", "LEV"):
            _buy(me, t, datetime(2026, 5, 1, 14, 0), name=t.title())
        _buy(me, "LOSS", datetime(2026, 6, 1, 14, 0))          # second buy — the first one counts
        _buy(me, "LATE", datetime(2026, 7, 1, 14, 0))
        _buy(me, "005930.KS", datetime(2026, 7, 2, 0, 0))     # KR, no DART key → no source
        out = pick_facts(me, now=NOW)
    assert (out["picked"], out["with_facts"], out["pending"], out["no_facts"]) == (5, 3, 0, 2)
    assert out["counts"] == {"net_loss": 1, "revenue_down": 1, "liabilities_over_equity": 1}
    assert out["sources"] == ["SEC EDGAR"]
    by = {p["ticker"]: p for p in out["picks"]}
    assert by["LOSS"]["net_loss"] and by["DOWN"]["revenue_down"] and by["LEV"]["liabilities_over_equity"]
    assert by["LOSS"]["bought_on"] == "2026-05-01" and by["LOSS"]["fiscal_end"] == "2025-12-31"


def test_sync_budget_and_flag_off(app, make_user, sec_facts, monkeypatch):
    me = make_user(email="pf-budget@test.com")["id"]
    with app.app_context():
        for i, t in enumerate(("LOSS", "DOWN", "LEV", "LATE")):
            _buy(me, t, datetime(2026, 5, 1 + i, 14, 0))
        out = pick_facts(me, now=NOW)                          # flag off in tests
        assert sec_facts == [] and out["with_facts"] == 0 and out["no_facts"] == 4
        monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
        out = pick_facts(me, now=NOW)
    assert len(sec_facts) == SYNC_BUDGET
    assert out["pending"] == 4 - SYNC_BUDGET


def test_route_is_auth_gated_and_has_no_score_words(client, auth_user, app, sec_facts, monkeypatch):
    monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
    with app.app_context():
        _buy(auth_user["id"], "LOSS", datetime(2026, 5, 1, 14, 0))
    resp = client.get("/api/pick-facts")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True and body["disclaimer"] and body["window_days"] == 365
    blob = json.dumps({k: v for k, v in body.items() if k != "disclaimer"}, ensure_ascii=False)
    for word in ("score", "grade", "점수", "등급", "rating"):
        assert word not in blob


def test_route_requires_login(raw_client):
    assert raw_client.get("/api/pick-facts").status_code in (401, 302)
