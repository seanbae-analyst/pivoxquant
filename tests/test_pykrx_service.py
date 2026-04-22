"""
PivoxQuant — pyKRX service tests (DEPRECATED)
=============================================
The original pyKRX scraper was removed on 2026-04-19 for legal compliance.
The module is now a thin deprecation shim that returns empty data so
``/api/alt-data/kr/*`` routes still respond 200.

These tests verify the shim's public contract:
  1. Ticker normalisation (unchanged — the helper is still used by routes)
  2. Every public method returns an empty container
  3. The cache primitives still work (tests construct PyKRXService directly)

When a licensed replacement lands, these tests will be rewritten against
the new internals; until then they guard the "no crashes, empty payload"
contract that keeps the frontend from 500-ing.
"""
from __future__ import annotations


from services.data.pykrx_service import PyKRXService, _normalize_ticker


# ── 1. Ticker normalisation (unchanged contract) ─────────────────────────────

class TestNormalizeTicker:
    def test_bare_6_digit(self):
        assert _normalize_ticker("005930") == "005930"

    def test_with_ks_suffix(self):
        assert _normalize_ticker("005930.KS") == "005930"

    def test_with_kq_suffix_lowercase(self):
        assert _normalize_ticker("035720.kq") == "035720"

    def test_with_krx_suffix(self):
        assert _normalize_ticker("000660.KRX") == "000660"

    def test_invalid_too_short(self):
        assert _normalize_ticker("12345") is None

    def test_invalid_alpha(self):
        assert _normalize_ticker("AAPL") is None

    def test_invalid_empty(self):
        assert _normalize_ticker("") is None

    def test_invalid_none(self):
        assert _normalize_ticker(None) is None  # type: ignore[arg-type]


# ── 2. Deprecation contract — all methods return empty data ─────────────────

class TestDeprecatedEmptyResults:
    def test_get_foreign_flow_empty(self):
        svc = PyKRXService(rate_limit_sleep=0)
        assert svc.get_foreign_flow("005930", days=30) == []

    def test_get_foreign_flow_invalid_ticker(self):
        svc = PyKRXService(rate_limit_sleep=0)
        # Invalid ticker must not raise; returns [] and logs a warning.
        assert svc.get_foreign_flow("AAPL", days=30) == []

    def test_get_institutional_flow_empty(self):
        svc = PyKRXService(rate_limit_sleep=0)
        assert svc.get_institutional_flow("005930", days=30) == []

    def test_get_short_interest_empty(self):
        svc = PyKRXService(rate_limit_sleep=0)
        assert svc.get_short_interest("005930") == []

    def test_get_short_balance_ratio_empty(self):
        svc = PyKRXService(rate_limit_sleep=0)
        assert svc.get_short_balance_ratio("005930") == {}

    def test_get_market_flow_summary_empty(self):
        svc = PyKRXService(rate_limit_sleep=0)
        assert svc.get_market_flow_summary("KOSPI") == {}

    def test_get_market_flow_summary_invalid_market(self):
        svc = PyKRXService(rate_limit_sleep=0)
        assert svc.get_market_flow_summary("NASDAQ") == {}

    def test_cached_at_none(self):
        svc = PyKRXService()
        assert svc.cached_at("005930", "foreign_flow") is None


# ── 3. Cache primitives still work ──────────────────────────────────────────

class TestCachePrimitives:
    def test_cache_set_and_get(self):
        svc = PyKRXService(cache_ttl=60, rate_limit_sleep=0)
        svc._cache_set("k", [{"hello": "world"}])
        assert svc._cache_get("k") == [{"hello": "world"}]

    def test_clear_cache(self):
        svc = PyKRXService(cache_ttl=60, rate_limit_sleep=0)
        svc._cache_set("k", [1])
        svc.clear_cache()
        assert svc._cache_get("k") is None
