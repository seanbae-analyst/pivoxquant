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
    """resolve_stock_name + _kis_name use a positive-only result cache;
    clear it between tests so transient-failure scenarios are isolated."""
    name_resolver.clear_name_cache()
    yield
    name_resolver.clear_name_cache()


class TestPureResolver:
    def test_curated_kr_hit(self):
        # 005930.KS Samsung is in the curated registry
        assert name_resolver.resolve_stock_name("005930.KS") == "삼성전자"

    def test_bare_kr_code_normalizes_and_resolves(self):
        # Bare 6-digit KRX codes (no .KS/.KQ suffix) must normalize and resolve
        # to the hangul name. Before the fix these fell through _is_korean() as
        # if they were US tickers and resolved to None, so every PDF/email
        # artifact rendered the naked number as the hero. Regression gate for
        # [[티커번호 대신 종목이름 표시]] (CEO "티커번호말고 종목이름").
        assert name_resolver.resolve_stock_name("005930") == "삼성전자"   # KOSPI
        assert name_resolver.resolve_stock_name("035760") == "CJ ENM"     # KOSDAQ
        assert name_resolver.resolve_stock_name("000660") == "SK하이닉스"

    def test_bare_kr_code_matches_suffixed_form(self):
        # Bare and .KS/.KQ-suffixed forms must resolve identically.
        assert (name_resolver.resolve_stock_name("373220")
                == name_resolver.resolve_stock_name("373220.KS") == "LG에너지솔루션")

    def test_us_symbol_not_treated_as_bare_kr_code(self):
        # US symbols are never all-digit, so the bare-code normalization path
        # must not fire on them.
        out = name_resolver.resolve_stock_name("AAPL")
        assert out and "Apple" in out

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


class TestPositiveOnlyCache:
    """FIX 1 (2026-05-22): a transient None resolution must NOT be cached.

    The old ``functools.lru_cache`` memoised None, so a brief KIS outage on
    the FIRST lookup of a ticker pinned the raw ticker for the whole process
    life. Only resolved (truthy) names should be cached.
    """

    def test_transient_none_is_not_cached_then_succeeds(self):
        # 999777.KS is unmapped in the curated registry → falls to KIS rung.
        with patch("services.data.kis_market_adapter.get_name") as kis_m:
            # First call: KIS transiently down → None (must NOT be cached).
            kis_m.return_value = None
            first = name_resolver.resolve_stock_name("999777.KS")
            assert first is None

            # Second call: KIS recovered → name resolves (proves no None cache
            # short-circuited the retry).
            kis_m.return_value = "삼성전자"
            second = name_resolver.resolve_stock_name("999777.KS")
            assert second == "삼성전자"
            # KIS was hit on BOTH calls (None wasn't cached).
            assert kis_m.call_count == 2

    def test_good_result_is_cached(self):
        with patch("services.data.kis_market_adapter.get_name") as kis_m:
            kis_m.return_value = "삼성전자"
            assert name_resolver.resolve_stock_name("999666.KS") == "삼성전자"
            assert name_resolver.resolve_stock_name("999666.KS") == "삼성전자"
            # Resolved name cached → KIS called only once.
            assert kis_m.call_count == 1

    def test_kis_name_positive_only_cache(self):
        """_kis_name itself must not cache None."""
        with patch("services.data.kis_market_adapter.get_name") as kis_m:
            kis_m.return_value = None
            assert name_resolver._kis_name("123123.KS") is None
            kis_m.return_value = "롯데렌탈"
            assert name_resolver._kis_name("123123.KS") == "롯데렌탈"
            assert kis_m.call_count == 2
            # Now the good result IS cached.
            assert name_resolver._kis_name("123123.KS") == "롯데렌탈"
            assert kis_m.call_count == 2


class TestNameOrTicker:
    def test_falls_back_to_ticker(self):
        with patch.object(name_resolver, "resolve_stock_name", return_value=None):
            assert name_resolver.name_or_ticker("XYZ") == "XYZ"

    def test_returns_resolved_name(self):
        with patch.object(name_resolver, "resolve_stock_name",
                          return_value="Apple Inc."):
            assert name_resolver.name_or_ticker("AAPL") == "Apple Inc."


class TestKrSuffixToggleFallback:
    """Regression for Bug B-02 (2026-05-10).

    KIS API has been observed returning some KOSDAQ tickers with the .KS
    suffix (and vice-versa). The curated + full registries store every
    KRX listing under exactly one suffix, so a suffix-toggle fallback is
    safe and unambiguous: there is no 6-digit code that exists on both
    KOSPI and KOSDAQ at once.
    """

    def test_kq_only_ticker_resolves_when_called_with_ks_suffix(self):
        """``124500.KQ`` (아이티센글로벌) is in the JSON master only as .KQ.
        KIS sometimes hands us ``124500.KS`` — that *must* still resolve
        to the same Korean name, otherwise alerts render the bare ticker.
        """
        from services import kr_stock_registry as r
        assert r.get_name("124500.KS") == "아이티센글로벌"
        assert r.get_name("124500.KQ") == "아이티센글로벌"

    def test_curated_kospi_ticker_unchanged(self):
        """Suffix toggle must never override an existing primary hit."""
        from services import kr_stock_registry as r
        assert r.get_name("005930.KS") == "삼성전자"

    def test_curated_kosdaq_ticker_unchanged(self):
        from services import kr_stock_registry as r
        assert r.get_name("247540.KQ") == "에코프로비엠"

    def test_us_ticker_not_affected(self):
        """The toggle path is gated on the ``XXXXXX.K[SQ]`` shape, so US
        tickers and free-form symbols pass through unchanged (None)."""
        from services import kr_stock_registry as r
        assert r.get_name("AAPL") is None
        assert r.get_name("BRK.B") is None
        assert r.get_name("") is None

    def test_unknown_six_digit_returns_none(self):
        """Both suffix variants miss → fall back to None (caller uses
        the ticker itself)."""
        from services import kr_stock_registry as r
        assert r.get_name("999999.KS") is None
        assert r.get_name("999999.KQ") is None

    def test_resolve_via_name_resolver_picks_up_toggle(self):
        """End-to-end: the alert pipeline calls
        ``resolve_stock_name_with_db('124500.KS')`` and must now return
        the human name, not None."""
        # Pure resolver — no DB rung.
        name_resolver.clear_name_cache()
        assert name_resolver.resolve_stock_name("124500.KS") == "아이티센글로벌"
