"""
PivoxQuant — SEC EDGAR alt-data service tests
=============================================
Covers ``services/data/sec_edgar_service.py`` + ``routes/alt_data.py`` US
endpoints. All HTTP egress to SEC is **mocked** — tests never touch the wire.

We verify:
  1. User-Agent header compliance (SEC fair-access rule)
  2. Rate-limit throttle actually sleeps when bursting
  3. 13F XML parser round-trips a realistic informationTable
  4. Form 4 XML parser extracts insider + transaction code + A/D flag
  5. Cluster-buy detector: <3 insiders => not triggered, ≥3 => triggered
  6. Error resilience: HTTP 5xx => [] (never raises)
  7. Flask route returns the documented envelope shape
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from services.data.sec_edgar_service import (
    SECEdgarService,
    SMART_MONEY_CIKS,
    _parse_13f_information_table,
    _parse_form4,
    _clear_cache_for_tests,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _clear_edgar_cache():
    """Every test starts with an empty SEC cache."""
    _clear_cache_for_tests()
    yield
    _clear_cache_for_tests()


SAMPLE_13F_XML = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip>
    <value>175000000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>915560382</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>DFND</investmentDiscretion>
    <votingAuthority>
      <Sole>915560382</Sole>
      <Shared>0</Shared>
      <None>0</None>
    </votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>BANK OF AMERICA</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>060505104</cusip>
    <value>30000000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>1032852006</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
  </infoTable>
</informationTable>
"""


def _form4_xml(insider: str, code: str, ad: str, shares: int, price: float) -> str:
    """Build a minimal Form 4 ownershipDocument XML with one non-derivative txn."""
    return f"""<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001234567</rptOwnerCik>
      <rptOwnerName>{insider}</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>1</isOfficer>
      <officerTitle>CEO</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-04-10</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>{code}</transactionCode>
        <equitySwapInvolved>0</equitySwapInvolved>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>{ad}</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests — parsers + throttle + error handling
# ══════════════════════════════════════════════════════════════════════════════
class TestParsers:
    def test_13f_parser_extracts_holdings(self):
        rows = _parse_13f_information_table(SAMPLE_13F_XML)
        assert len(rows) == 2
        aapl = rows[0]
        assert aapl["company"] == "APPLE INC"
        assert aapl["cusip"] == "037833100"
        assert aapl["shares"] == 915_560_382
        assert aapl["value_usd"] == 175_000_000_000
        # second row
        assert rows[1]["company"] == "BANK OF AMERICA"
        assert rows[1]["shares"] == 1_032_852_006

    def test_13f_parser_returns_empty_on_bad_xml(self):
        assert _parse_13f_information_table("not-xml<<<>>>") == []
        assert _parse_13f_information_table("") == []

    def test_form4_parser_extracts_insider_and_code(self):
        xml = _form4_xml("Tim Cook", "P", "A", 1000, 150.50)
        rows = _parse_form4(xml)
        assert len(rows) == 1
        r = rows[0]
        assert r["insider"] == "Tim Cook"
        assert r["transaction_code"] == "P"
        assert r["acquired"] is True
        assert r["shares"] == 1000
        assert r["price"] == 150.50
        assert r["value_usd"] == 150_500.0
        # Relationship should include CEO title + Director/Officer
        assert "CEO" in r["relationship"]

    def test_form4_parser_sale_flags_acquired_false(self):
        xml = _form4_xml("Jane Doe", "S", "D", 500, 200.0)
        rows = _parse_form4(xml)
        assert rows[0]["acquired"] is False
        assert rows[0]["transaction_code"] == "S"


class TestRateLimit:
    def test_throttle_sleeps_on_burst(self):
        """Back-to-back calls must respect _MIN_REQUEST_INTERVAL (~0.11s)."""
        # Reset the global last-request timestamp by calling once first.
        SECEdgarService._throttle()
        t0 = time.perf_counter()
        for _ in range(3):
            SECEdgarService._throttle()
        elapsed = time.perf_counter() - t0
        # 3 throttled calls => ≥ 2 * 0.11s = 0.22s (first is already "recent")
        assert elapsed >= 0.20, f"throttle too fast: {elapsed:.3f}s"


class TestHTTPErrorResilience:
    def test_non_200_returns_empty(self):
        """HTTP 5xx / 404 must yield [] and never raise."""
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch(
            "services.data.sec_edgar_service._requests.get",
            return_value=mock_resp,
        ):
            out = SECEdgarService.get_13f_holdings("0001067983")
        assert out == []

    def test_user_agent_is_sec_compliant(self):
        """User-Agent must include 'PivoxQuant' + an email (@)."""
        captured = {}

        def fake_get(url, headers=None, timeout=None):  # noqa: ARG001
            captured["headers"] = headers
            m = MagicMock()
            m.status_code = 404
            return m

        with patch(
            "services.data.sec_edgar_service._requests.get",
            side_effect=fake_get,
        ):
            SECEdgarService._http_get("https://data.sec.gov/whatever")

        ua = captured["headers"]["User-Agent"]
        assert "PivoxQuant" in ua
        assert "@" in ua, f"User-Agent missing contact email: {ua!r}"

    def test_network_exception_returns_none(self):
        with patch(
            "services.data.sec_edgar_service._requests.get",
            side_effect=Exception("connection refused"),
        ):
            assert SECEdgarService._http_get("https://data.sec.gov/x") is None


# ══════════════════════════════════════════════════════════════════════════════
# Cluster-buy logic
# ══════════════════════════════════════════════════════════════════════════════
class TestClusterBuy:
    def test_fewer_than_threshold_not_triggered(self):
        trades = [
            {"insider": "Alice", "transaction_code": "P", "acquired": True},
            {"insider": "Bob",   "transaction_code": "P", "acquired": True},
        ]
        with patch.object(
            SECEdgarService, "get_form4_insider_trades", return_value=trades
        ):
            out = SECEdgarService.detect_cluster_buys("AAPL", days=30, min_insiders=3)
        assert out["triggered"] is False
        assert out["insider_count"] == 2

    def test_threshold_met_triggered(self):
        trades = [
            {"insider": "Alice",   "transaction_code": "P", "acquired": True},
            {"insider": "Bob",     "transaction_code": "P", "acquired": True},
            {"insider": "Charlie", "transaction_code": "P", "acquired": True},
            # Award (A code) must be ignored even if acquired=True.
            {"insider": "Dan",     "transaction_code": "A", "acquired": True},
            # Sale must be ignored.
            {"insider": "Eve",     "transaction_code": "S", "acquired": False},
        ]
        with patch.object(
            SECEdgarService, "get_form4_insider_trades", return_value=trades
        ):
            out = SECEdgarService.detect_cluster_buys("AAPL", days=30, min_insiders=3)
        assert out["triggered"] is True
        assert out["insider_count"] == 3
        assert set(out["unique_insiders"]) == {"Alice", "Bob", "Charlie"}

    def test_duplicate_insiders_counted_once(self):
        trades = [
            {"insider": "Alice", "transaction_code": "P", "acquired": True},
            {"insider": "Alice", "transaction_code": "P", "acquired": True},
            {"insider": "Alice", "transaction_code": "P", "acquired": True},
        ]
        with patch.object(
            SECEdgarService, "get_form4_insider_trades", return_value=trades
        ):
            out = SECEdgarService.detect_cluster_buys("AAPL", days=30, min_insiders=3)
        assert out["triggered"] is False
        assert out["insider_count"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# Registry integrity
# ══════════════════════════════════════════════════════════════════════════════
class TestSmartMoneyRegistry:
    def test_all_ciks_are_10_digits(self):
        for name, cik in SMART_MONEY_CIKS.items():
            assert len(cik) == 10, f"{name} CIK not zero-padded: {cik}"
            assert cik.isdigit(), f"{name} CIK non-numeric: {cik}"

    def test_expected_funds_present(self):
        for key in ("berkshire", "renaissance", "citadel", "bridgewater", "ark"):
            assert key in SMART_MONEY_CIKS


# ══════════════════════════════════════════════════════════════════════════════
# Flask route integration
# ══════════════════════════════════════════════════════════════════════════════
class TestRoutes:
    def test_cluster_buys_endpoint_requires_auth(self, client):
        resp = client.get("/api/alt-data/us/cluster-buys/AAPL")
        assert resp.status_code == 401

    def test_cluster_buys_endpoint_envelope(self, client, auth_user):
        """Envelope: {ticker, data, cached_at, source: 'SEC EDGAR'}."""
        with patch.object(
            SECEdgarService,
            "detect_cluster_buys",
            return_value={
                "ticker": "AAPL", "triggered": False,
                "insider_count": 1, "unique_insiders": ["Alice"],
                "trades": [], "window_days": 30, "threshold": 3,
            },
        ):
            resp = client.get("/api/alt-data/us/cluster-buys/AAPL?days=30&min_insiders=3")
        assert resp.status_code == 200, resp.data
        body = resp.get_json()
        assert body["ticker"] == "AAPL"
        assert body["source"] == "SEC EDGAR"
        assert "cached_at" in body
        assert body["data"]["triggered"] is False

    def test_13f_endpoint_resolves_smart_money_key(self, client, auth_user):
        """`/us/13f/berkshire` should resolve via SMART_MONEY_CIKS."""
        with patch.object(
            SECEdgarService, "get_13f_holdings", return_value=[]
        ) as mock_13f:
            resp = client.get("/api/alt-data/us/13f/berkshire")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["cik"] == SMART_MONEY_CIKS["berkshire"]
        mock_13f.assert_called_once_with(SMART_MONEY_CIKS["berkshire"])

    def test_insider_trades_rejects_bad_days(self, client, auth_user):
        resp = client.get("/api/alt-data/us/insider-trades/AAPL?days=9999")
        assert resp.status_code == 400

    def test_smart_money_endpoint(self, client, auth_user):
        fake = [
            {"filer": "berkshire", "cik": "0001067983", "shares": 915_560_382,
             "value_usd": 175_000_000_000, "filing_date": "2026-02-14",
             "period": "2025-12-31"},
        ]
        with patch.object(
            SECEdgarService,
            "get_institutional_filers_by_ticker",
            return_value=fake,
        ):
            resp = client.get("/api/alt-data/us/smart-money/AAPL?limit=10")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ticker"] == "AAPL"
        assert body["data"] == fake
        assert body["source"] == "SEC EDGAR"
