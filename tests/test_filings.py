"""보유 종목 공시 사실표 — services/filings (EDGAR · DART) + GET /positions/<id>/filings.

네트워크 없음: 계산은 고정 JSON 으로, 라우트는 filings.get_facts 를 patch 한다.
"""
import re
from datetime import date
from unittest.mock import patch

import pytest

from services import filings
from services.filings import common, dart_facts, edgar_facts


@pytest.fixture(autouse=True)
def _clear_cache():
    filings.clear_cache()
    yield
    filings.clear_cache()


# ── 공통 분기화 ──────────────────────────────────────────────────────────────

class TestQuarterly:
    def test_cumulative_spans_are_differenced(self):
        spans = {
            ("2025-01-01", "2025-03-31"): -10.0,
            ("2025-01-01", "2025-06-30"): -25.0,   # 6개월 누적
            ("2025-01-01", "2025-09-30"): -45.0,   # 9개월 누적
            ("2025-01-01", "2025-12-31"): -70.0,   # 연간
        }
        q = common.quarterly_from_spans(spans)
        assert q == {
            "2025-03-31": -10.0, "2025-06-30": -15.0,
            "2025-09-30": -20.0, "2025-12-31": -25.0,
        }

    def test_three_month_value_wins_over_difference(self):
        spans = {
            ("2025-04-01", "2025-06-30"): 7.0,
            ("2025-01-01", "2025-03-31"): 3.0,
            ("2025-01-01", "2025-06-30"): 99.0,
        }
        assert common.quarterly_from_spans(spans)["2025-06-30"] == 7.0

    def test_trailing_four_needs_contiguous_quarters(self):
        assert common.trailing_four({"2025-03-31": 1, "2025-06-30": 1, "2025-09-30": 1}) is None
        gap = {"2024-03-31": 1, "2025-06-30": 1, "2025-09-30": 1, "2025-12-31": 1}
        assert common.trailing_four(gap) is None
        ok = {"2025-03-31": 1, "2025-06-30": 2, "2025-09-30": 3, "2025-12-31": 4}
        assert common.trailing_four(ok) == 10


# ── EDGAR ────────────────────────────────────────────────────────────────────

def _e(start, end, val, form="10-Q"):
    row = {"end": end, "val": val, "form": form}
    if start:
        row["start"] = start
    return row


def _companyfacts():
    q = [("2025-04-01", "2025-06-30"), ("2025-07-01", "2025-09-30"),
         ("2026-01-01", "2026-03-31"), ("2026-04-01", "2026-06-30")]
    return {
        "entityName": "Example Corp",
        "facts": {"us-gaap": {
            # 옛 태그 — 더 이른 기간까지만 있다. 골라지면 안 된다.
            "SalesRevenueNet": {"units": {"USD": [_e("2019-01-01", "2019-03-31", 999)]}},
            "Revenues": {"units": {"USD": [
                _e(*q[0], 10), _e(*q[1], 20),
                _e("2025-01-01", "2025-09-30", 40),
                _e("2025-01-01", "2025-12-31", 70, "10-K"),   # → 4분기 30
                _e(*q[2], 40), _e(*q[3], 50),
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                _e(*q[0], -5), _e(*q[1], -6),
                _e("2025-01-01", "2025-09-30", -15),
                _e("2025-01-01", "2025-12-31", -22, "10-K"),  # → 4분기 -7
                _e(*q[2], -8), _e(*q[3], -9),
            ]}},
            "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
                _e("2025-01-01", "2025-06-30", -20),
                _e("2025-01-01", "2025-09-30", -30),
                _e("2025-01-01", "2025-12-31", -40, "10-K"),
                _e("2026-01-01", "2026-03-31", -10),
                _e("2026-01-01", "2026-06-30", -20),
            ]}},
            "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [
                _e(None, "2026-06-30", 100)]}},
            "ShortTermInvestments": {"units": {"USD": [_e(None, "2026-06-30", 200)]}},
            "Liabilities": {"units": {"USD": [_e(None, "2026-06-30", 50)]}},
            "StockholdersEquity": {"units": {"USD": [_e(None, "2026-06-30", 100)]}},
            "WeightedAverageNumberOfSharesOutstandingBasic": {"units": {"shares": [
                _e(*q[0], 100), _e(*q[3], 130),
            ]}},
        }},
    }


class TestEdgarFacts:
    def test_facts(self):
        f = edgar_facts.compute(_companyfacts())
        assert f["source"] == "SEC EDGAR"
        assert f["entity_name"] == "Example Corp"
        assert f["as_of"] == "2026-06-30"
        assert [x["revenue"] for x in f["quarters"]] == [10, 20, 30, 40, 50]
        assert f["revenue_ttm"] == 20 + 30 + 40 + 50
        assert f["net_income_ttm"] == -6 - 7 - 8 - 9
        assert f["net_income_streak"] == {"kind": "loss", "quarters": 5}
        assert f["net_income_per_share_ttm"] == pytest.approx(-30 / 130)
        # 현금 100 + 단기투자 200
        assert f["cash"] == {"as_of": "2026-06-30", "value": 300, "includes_short_term": True}
        # 영업현금흐름 분기: 25Q3 -10, 25Q4 -10, 26Q1 -10, 26Q2 -10 → 300 / 40 * 12
        assert f["operating_cf_ttm"] == -40
        assert f["cash_months_at_ttm_burn"] == pytest.approx(90)
        assert f["liabilities_to_equity"]["value"] == pytest.approx(0.5)
        assert f["shares_change_1y"]["pct"] == pytest.approx(0.3)

    def test_no_income_data_is_none(self):
        assert edgar_facts.compute({"facts": {"us-gaap": {}}}) is None

    def test_no_vocabulary_of_judgement(self):
        words = set(re.findall(r"[a-z]+", repr(edgar_facts.compute(_companyfacts())).lower()))
        assert not words & {"score", "grade", "rating", "buy", "sell", "recommend", "signal"}


# ── DART ─────────────────────────────────────────────────────────────────────

def _row(sj, account_id, this, cum=None, name=""):
    return {"sj_div": sj, "account_id": account_id, "account_nm": name,
            "thstrm_amount": this, "thstrm_add_amount": cum}


def _report(rev, rev_cum, ni, ni_cum, eps, eps_cum, ocf_cum, cash=None):
    rows = [
        _row("IS", "ifrs-full_Revenue", rev, rev_cum),
        _row("IS", "ifrs-full_ProfitLoss", ni, ni_cum),
        _row("IS", "ifrs-full_BasicEarningsLossPerShare", eps, eps_cum),
        _row("CF", "ifrs-full_CashFlowsFromUsedInOperatingActivities", ocf_cum),
    ]
    if cash is not None:
        rows += [
            _row("BS", "ifrs-full_CashAndCashEquivalents", cash),
            _row("BS", "dart_ShortTermDepositsNotClassifiedAsCashEquivalents", "1,000"),
            _row("BS", "ifrs-full_Liabilities", "3,000"),
            _row("BS", "ifrs-full_Equity", "6,000"),
        ]
    return rows


class TestDartFacts:
    def _reports(self):
        return {
            (2025, "11013"): _report("100", "100", "10", "10", "50", "50", "20"),
            (2025, "11012"): _report("110", "210", "11", "21", "55", "105", "45"),
            (2025, "11014"): _report("120", "330", "12", "33", "60", "165", "70"),
            # 사업보고서: thstrm = 연간, 누적 칸 없음
            (2025, "11011"): _report("460", None, "46", None, "230", None, "100"),
            (2026, "11013"): _report("140", "140", "14", "14", "70", "70", "30"),
            (2026, "11012"): _report("1,500", "290", "15", "29", "75", "145", "60",
                                     cash="2,000"),
        }

    def test_facts(self):
        f = dart_facts.compute(self._reports(), "예시전자")
        assert f["source"] == "DART"
        assert f["currency"] == "KRW"
        assert f["entity_name"] == "예시전자"
        # 4분기 = 연간 460 − 9개월 누적 330
        assert [x["revenue"] for x in f["quarters"]] == [110, 120, 130, 140, 1500]
        assert f["net_income_ttm"] == 12 + 13 + 14 + 15
        assert f["net_income_streak"] == {"kind": "profit", "quarters": 6}
        # 주당순이익 = 분기 EPS 4개 합 (60 + 65 + 70 + 75)
        assert f["net_income_per_share_ttm"] == 270
        assert f["cash"] == {"as_of": "2026-06-30", "value": 3000, "includes_short_term": True}
        assert f["operating_cf_ttm"] == 25 + 30 + 30 + 30
        assert f["cash_months_at_ttm_burn"] is None  # 영업현금 유입 — 소진 계산 없음
        assert f["liabilities_to_equity"]["value"] == pytest.approx(0.5)
        assert f["shares_change_1y"] is None

    def test_amount_parsing(self):
        assert dart_facts._amount("-1,234") == -1234
        assert dart_facts._amount("") is None
        assert dart_facts._amount("-") is None
        assert dart_facts._amount(None) is None

    def test_no_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("DART_API_KEY", raising=False)
        assert dart_facts.facts_for("005930.KS") is None

    def test_unfinished_quarters_are_not_requested(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "k")
        calls = []
        monkeypatch.setattr(dart_facts, "corp_code_for", lambda s: ("00126380", "예시"))
        monkeypatch.setattr(dart_facts, "fetch_report",
                            lambda c, y, r: calls.append((y, r)) or None)
        dart_facts.facts_for("005930.KS", today=date(2026, 10, 6))
        assert (2026, "11014") in calls          # 9/30 끝난 분기
        assert (2026, "11011") not in calls      # 12/31 아직
        assert len(calls) == 4 + 4 + 3


# ── 시장 판별 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ticker,market", [
    ("AAPL", "US"), ("005930.KS", "KR"), ("010170.KQ", "KR"), ("7203.T", None), ("", None),
])
def test_market_of(ticker, market):
    assert filings.market_of(ticker) == market


# ── 라우트 ───────────────────────────────────────────────────────────────────

_FACTS = {
    "source": "SEC EDGAR", "entity_name": "Example", "currency": "USD",
    "as_of": "2026-06-30", "quarters": [], "revenue_ttm": 1.0,
    "net_income_ttm": 4.0, "net_income_streak": {"kind": "profit", "quarters": 4},
    "net_income_per_share_ttm": 2.0, "cash": None, "operating_cf_ttm": None,
    "cash_months_at_ttm_burn": None, "liabilities_to_equity": None,
    "shares_change_1y": None,
}


class TestRoute:
    def test_unauthenticated(self, client):
        assert client.get("/api/portfolio/positions/1/filings").status_code == 401

    def test_other_users_position_is_404(self, client, auth_user, make_user, add_position):
        other = make_user(email="other@example.com")
        pid = add_position(other["id"], ticker="AAPL")
        assert client.get(f"/api/portfolio/positions/{pid}/filings").status_code == 404

    def test_pe_at_my_cost(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], ticker="AAPL", avg_cost=50.0)
        with patch.object(filings, "get_facts", return_value=dict(_FACTS)) as gf:
            d = client.get(f"/api/portfolio/positions/{pid}/filings").get_json()
        gf.assert_called_once_with("AAPL")
        assert d["available"] is True
        assert d["avg_cost"] == 50.0
        assert d["pe_at_cost"] == pytest.approx(25.0)
        assert d["facts"]["source"] == "SEC EDGAR"

    def test_loss_has_no_pe(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], ticker="AAPL", avg_cost=50.0)
        facts = dict(_FACTS, net_income_per_share_ttm=-1.0)
        with patch.object(filings, "get_facts", return_value=facts):
            d = client.get(f"/api/portfolio/positions/{pid}/filings").get_json()
        assert d["pe_at_cost"] is None

    def test_unsupported_market(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], ticker="7203.T")
        d = client.get(f"/api/portfolio/positions/{pid}/filings").get_json()
        assert d == {"ticker": "7203.T", "available": False, "reason": "unsupported_market"}

    def test_kr_without_key(self, client, auth_user, add_position, monkeypatch):
        monkeypatch.delenv("DART_API_KEY", raising=False)
        pid = add_position(auth_user["id"], ticker="005930.KS", avg_cost=70000)
        d = client.get(f"/api/portfolio/positions/{pid}/filings").get_json()
        assert d["reason"] == "source_unconfigured"

    def test_no_filings(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], ticker="ZZZZ")
        with patch.object(filings, "get_facts", return_value=None):
            d = client.get(f"/api/portfolio/positions/{pid}/filings").get_json()
        assert d["reason"] == "no_filings"

    def test_open_while_market_display_off(self, client, auth_user, add_position, monkeypatch):
        """공시 원천이라 벤더 시세 플래그와 무관하다 (기본 OFF 에서도 열린다)."""
        monkeypatch.setenv("MARKET_DATA_DISPLAY_ENABLED", "0")
        pid = add_position(auth_user["id"], ticker="AAPL", avg_cost=50.0)
        with patch.object(filings, "get_facts", return_value=dict(_FACTS)):
            d = client.get(f"/api/portfolio/positions/{pid}/filings").get_json()
        assert d["available"] is True
