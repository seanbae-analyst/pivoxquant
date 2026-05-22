"""tests/test_fmp_get_info_kr_guard.py — FIX 2 (2026-05-22).

``get_info(ticker)`` previously called get_profile + get_ratios_ttm +
get_key_metrics_ttm (+ get_income_statement_growth + a /quote fallback)
UNCONDITIONALLY before dispatching `.KS` / `.KQ` tickers to the KIS path.
FMP Starter has no KRX coverage, so for KR tickers every one of those FMP
calls returned {} yet still burned an FMP API call.

This locks in the early KR-dispatch guard at the top of get_info (mirrors
get_history's guard): KR tickers must NOT trigger the FMP fundamentals
calls, and must still resolve KR fundamentals via the licensed KIS path.
"""
from __future__ import annotations

import time
from unittest.mock import patch

from services.data import fmp as fmp_service


def _clear_fmp_cache():
    with fmp_service._cache_lock:
        fmp_service._cache.clear()
        fmp_service._endpoint_402_counts.clear()
        fmp_service._endpoint_402_cooldown.clear()
    fmp_service._daily_calls = 0
    fmp_service._daily_calls_reset = time.time()


class TestGetInfoKrGuard:
    def test_kr_ticker_skips_fmp_fundamentals_calls(self):
        _clear_fmp_cache()
        kr_payload = {
            "marketCap": 1.7071e15,
            "trailingPE": 12.3,
            "trailingEps": 5400,
            "priceToBook": 1.1,
        }
        with patch.object(fmp_service, "get_profile") as m_profile, \
                patch.object(fmp_service, "get_ratios_ttm") as m_ratios, \
                patch.object(fmp_service, "get_key_metrics_ttm") as m_metrics, \
                patch.object(fmp_service, "get_income_statement_growth") as m_growth, \
                patch.object(fmp_service, "_fmp_get") as m_fmp_get, \
                patch("services.data.kr_fundamentals.get_kr_fundamentals",
                      return_value=kr_payload):
            info = fmp_service.get_info("005930.KS")

        # FMP US-only fundamentals layer must NOT be touched for KR tickers.
        m_profile.assert_not_called()
        m_ratios.assert_not_called()
        m_metrics.assert_not_called()
        m_growth.assert_not_called()
        # The /quote fallback (raw _fmp_get) must also be skipped for KR.
        m_fmp_get.assert_not_called()

        # KR fundamentals still flow through via the KIS path.
        assert info["marketCap"] == 1.7071e15
        assert info["trailingPE"] == 12.3
        assert info["trailingEps"] == 5400

    def test_kosdaq_ticker_also_guarded(self):
        _clear_fmp_cache()
        with patch.object(fmp_service, "get_profile") as m_profile, \
                patch.object(fmp_service, "get_ratios_ttm") as m_ratios, \
                patch.object(fmp_service, "get_key_metrics_ttm") as m_metrics, \
                patch("services.data.kr_fundamentals.get_kr_fundamentals",
                      return_value={"marketCap": 1.0e12}):
            info = fmp_service.get_info("035720.KQ")
        m_profile.assert_not_called()
        m_ratios.assert_not_called()
        m_metrics.assert_not_called()
        assert info["marketCap"] == 1.0e12

    def test_us_ticker_still_calls_fmp_fundamentals(self):
        """Regression guard: US path must be unchanged (still calls FMP)."""
        _clear_fmp_cache()
        with patch.object(fmp_service, "get_profile",
                          return_value={"companyName": "Apple Inc.", "price": 100}) as m_profile, \
                patch.object(fmp_service, "get_ratios_ttm",
                             return_value={"priceToEarningsRatioTTM": 30}) as m_ratios, \
                patch.object(fmp_service, "get_key_metrics_ttm",
                             return_value={}) as m_metrics:
            info = fmp_service.get_info("AAPL")
        m_profile.assert_called_once()
        m_ratios.assert_called_once()
        m_metrics.assert_called_once()
        assert info["shortName"] == "Apple Inc."
        assert info["trailingPE"] == 30
