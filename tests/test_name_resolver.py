"""Tests for ``services.name_resolver``.

Verifies the layered fallback chain:
  static registry -> SignalCache (DB) -> KIS API (live KRX)
plus the DEBUG-log breadcrumbs that surface unmapped tickers (B8/B10).
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from services import name_resolver


@pytest.fixture(autouse=True)
def _clear_lru():
    """resolve_stock_name + _kis_name are LRU-cached; clear between tests."""
    name_resolver.resolve_stock_name.cache_clear()
    name_resolver._kis_name.cache_clear()
    yield
    name_resolver.resolve_stock_name.cache_clear()
    name_resolver._kis_name.cache_clear()


class TestPureResolver:
    def test_curated_kr_hit(self):
        # 005930.KS Samsung is in the curated registry
        assert name_resolver.resolve_stock_name("005930.KS") == "삼성전자"

    def test_us_registry_hit(self):
        # AAPL must exist in the Alpaca asset master
        out = name_resolver.resolve_stock_name("AAPL")
        assert out and "Apple" in out

    def test_empty_input_returns_none(self):
        assert name_resolver.resolve_stock_name("") is None
        assert name_resolver.resolve_stock_name(None) is None
        assert name_resolver.resolve_stock_name("   ") is None

    def test_kr_unknown_falls_through_to_kis(self):
        # An unmapped KOSDAQ ETF — registries miss, KIS rung hit
        with patch("services.data.kis_market_adapter.get_name",
                   return_value="KODEX 200"):
            out = name_resolver.resolve_stock_name("999999.KS")
        assert out == "KODEX 200"

    def test_kr_total_miss_logs_debug(self, caplog):
        with patch("services.data.kis_market_adapter.get_name",
                   return_value=None), \
                caplog.at_level(logging.DEBUG, logger="services.name_resolver"):
            out = name_resolver.resolve_stock_name("999998.KS")
        assert out is None
        assert any("name_resolver miss (KR" in r.message for r in caplog.records)

    def test_us_total_miss_logs_debug(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="services.name_resolver"):
            out = name_resolver.resolve_stock_name("ZZZZZZZ_NOT_A_TICKER")
        assert out is None
        assert any("name_resolver miss (US" in r.message for r in caplog.records)

    def test_pure_resolver_does_not_touch_db(self):
        """resolve_stock_name must NOT consult SignalCache (no app context)."""
        with patch.object(name_resolver, "lookup_name_from_signal_cache") as m:
            name_resolver.resolve_stock_name("AAPL")
        m.assert_not_called()


class TestDbResolverFallbackChain:
    def test_kr_signal_cache_rung_hit(self, caplog):
        """When registries miss, SignalCache name wins before KIS API."""
        # Unknown KR ticker; registry returns None, signal cache returns name
        with patch("services.kr_stock_registry.get_name", return_value=None), \
                patch.object(name_resolver, "lookup_name_from_signal_cache",
                             return_value="TIGER 미국S&P500"), \
                patch("services.data.kis_market_adapter.get_name") as kis_m, \
                caplog.at_level(logging.DEBUG, logger="services.name_resolver"):
            out = name_resolver.resolve_stock_name_with_db("360750.KS")
        assert out == "TIGER 미국S&P500"
        # KIS not called — SignalCache short-circuits
        kis_m.assert_not_called()
        assert any("SignalCache" in r.message for r in caplog.records)

    def test_kr_signal_cache_miss_falls_through_to_kis(self):
        with patch("services.kr_stock_registry.get_name", return_value=None), \
                patch.object(name_resolver, "lookup_name_from_signal_cache",
                             return_value=None), \
                patch("services.data.kis_market_adapter.get_name",
                      return_value="롯데렌탈"):
            out = name_resolver.resolve_stock_name_with_db("089860.KS")
        assert out == "롯데렌탈"

    def test_us_signal_cache_rung_hit(self, caplog):
        with patch("services.us_stock_registry.get_name", return_value=None), \
                patch.object(name_resolver, "lookup_name_from_signal_cache",
                             return_value="Some Recent IPO Inc."), \
                caplog.at_level(logging.DEBUG, logger="services.name_resolver"):
            out = name_resolver.resolve_stock_name_with_db("NEWIPO")
        assert out == "Some Recent IPO Inc."

    def test_us_total_miss_with_db_logs(self, caplog):
        with patch("services.us_stock_registry.get_name", return_value=None), \
                patch.object(name_resolver, "lookup_name_from_signal_cache",
                             return_value=None), \
                caplog.at_level(logging.DEBUG, logger="services.name_resolver"):
            out = name_resolver.resolve_stock_name_with_db("UNKNOWN")
        assert out is None
        assert any(
            "name_resolver miss (US, all rungs)" in r.message
            for r in caplog.records
        )

    def test_db_resolver_never_raises(self):
        """Exception from any rung must be swallowed."""
        with patch("services.kr_stock_registry.get_name",
                   side_effect=RuntimeError("boom")):
            assert name_resolver.resolve_stock_name_with_db("005930.KS") is None


class TestNameOrTicker:
    def test_falls_back_to_ticker(self):
        with patch.object(name_resolver, "resolve_stock_name", return_value=None):
            assert name_resolver.name_or_ticker("XYZ") == "XYZ"

    def test_returns_resolved_name(self):
        with patch.object(name_resolver, "resolve_stock_name",
                          return_value="Apple Inc."):
            assert name_resolver.name_or_ticker("AAPL") == "Apple Inc."
