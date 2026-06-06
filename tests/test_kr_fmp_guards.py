"""tests/test_kr_fmp_guards.py — KR-ticker FMP guard sweep (2026-05-26).

FMP Starter has no KRX coverage, so .KS / .KQ tickers always return empty
payloads from FMP fundamental/profile/dividend/earnings/transcript endpoints
yet each call still burns an FMP API request (budget waste + empty/wrong data).

These tests lock in early KR guards added at the call sites so KR tickers:
  - never reach the FMP endpoint (assert_not_called on the FMP layer), and
  - return the appropriate empty / DATA_UNAVAILABLE shape,
while US tickers keep their existing FMP-backed behavior unchanged.

Covers:
  D#1  services/quant/indicators.py  current_ratio / interest_coverage
  D#3  routes/market.py              /api/dividend/<ticker>
  D#4  routes/market.py              _earnings_item_for_ticker
  D#7  services/data/fmp.py          get_info KR currency default
  +    services/ai/models.py         EarningsCallToneAnalyzer._fetch_transcript
"""
from __future__ import annotations

import time
from unittest.mock import patch

from services.quant.indicators import AdditionalFundamentals


# ── D#1: indicators current_ratio / interest_coverage ──────────────────────

class TestIndicatorsKrGuard:
    def test_current_ratio_kr_skips_balance_sheet(self):
        with patch("services.data.fmp.get_balance_sheet") as m_bs:
            out = AdditionalFundamentals.current_ratio("005930.KS")
        m_bs.assert_not_called()
        assert out["value"] is None
        assert out["status"] == "DATA_UNAVAILABLE"

    def test_current_ratio_kosdaq_skips_balance_sheet(self):
        with patch("services.data.fmp.get_balance_sheet") as m_bs:
            out = AdditionalFundamentals.current_ratio("035720.KQ")
        m_bs.assert_not_called()
        assert out["status"] == "DATA_UNAVAILABLE"

    def test_interest_coverage_kr_skips_income_statement(self):
        with patch("services.data.fmp.get_income_statement") as m_is:
            out = AdditionalFundamentals.interest_coverage("005930.KS")
        m_is.assert_not_called()
        assert out["value"] is None
        assert out["status"] == "DATA_UNAVAILABLE"

    def test_current_ratio_us_still_calls_fmp(self):
        """Regression: US path unchanged — still hits get_balance_sheet."""
        with patch("services.data.fmp.get_balance_sheet",
                   return_value=[{"totalCurrentAssets": 200,
                                  "totalCurrentLiabilities": 100,
                                  "date": "2025-12-31"}]) as m_bs:
            out = AdditionalFundamentals.current_ratio("AAPL")
        m_bs.assert_called_once()
        assert out["status"] == "OK"
        assert out["value"] == 2.0

    def test_interest_coverage_us_still_calls_fmp(self):
        with patch("services.data.fmp.get_income_statement",
                   return_value=[{"operatingIncome": 1000,
                                  "interestExpense": 100,
                                  "date": "2025-12-31"}]) as m_is:
            out = AdditionalFundamentals.interest_coverage("AAPL")
        m_is.assert_called_once()
        assert out["status"] == "OK"
        assert out["value"] == 10.0


# ── D#4: market _earnings_item_for_ticker ──────────────────────────────────

class TestEarningsItemKrGuard:
    def test_kr_ticker_returns_none_without_fmp(self):
        from routes import market
        with patch("services.data.fmp.get_earnings_calendar") as m_cal:
            out = market._earnings_item_for_ticker("005930.KS")
        m_cal.assert_not_called()
        assert out is None

    def test_kosdaq_ticker_returns_none_without_fmp(self):
        from routes import market
        with patch("services.data.fmp.get_earnings_calendar") as m_cal:
            out = market._earnings_item_for_ticker("035720.KQ")
        m_cal.assert_not_called()
        assert out is None

    def test_us_ticker_still_calls_earnings_calendar(self):
        """Regression: US ticker still queries FMP earnings calendar."""
        from routes import market
        with patch("services.data.fmp.get_earnings_calendar",
                   return_value=[]) as m_cal:
            out = market._earnings_item_for_ticker("AAPL")
        m_cal.assert_called_once()
        # empty calendar -> None, but FMP WAS consulted (US path preserved).
        assert out is None


# ── D#3: /api/dividend/<ticker> ─────────────────────────────────────────────

class TestDividendRouteKrGuard:
    def test_kr_dividend_skips_fmp(self, client, auth_user):
        with patch("services.data.fmp.get_info") as m_info, \
                patch("services.data.fmp.get_dividends") as m_div:
            r = client.get("/api/dividend/005930.KS")
        assert r.status_code == 200
        body = r.get_json()
        assert body["has_dividend"] is False
        assert body["ticker"] == "005930.KS"
        assert "note" in body
        m_info.assert_not_called()
        m_div.assert_not_called()

    def test_us_dividend_still_calls_fmp(self, client, auth_user):
        """Regression: US ticker still queries FMP for dividend data."""
        with patch("services.data.fmp.get_info",
                   return_value={"dividendYield": 0.005}) as m_info, \
                patch("services.data.fmp.get_dividends",
                      return_value=[{"dividend": 0.25, "date": "2025-11-01"}]) as m_div:
            r = client.get("/api/dividend/AAPL")
        assert r.status_code == 200
        body = r.get_json()
        assert body["has_dividend"] is True
        m_info.assert_called_once()
        m_div.assert_called_once()


# ── D#7: get_info KR currency default ───────────────────────────────────────

class TestGetInfoKrCurrency:
    def _clear_cache(self):
        from services.data import fmp as fmp_service
        with fmp_service._cache_lock:
            fmp_service._cache.clear()
            fmp_service._endpoint_402_counts.clear()
            fmp_service._endpoint_402_cooldown.clear()
        fmp_service._daily_calls = 0
        fmp_service._daily_calls_reset = time.time()

    def test_kr_info_has_krw_currency(self):
        from services.data import fmp as fmp_service
        self._clear_cache()
        with patch.object(fmp_service, "get_profile") as m_profile, \
                patch.object(fmp_service, "get_ratios_ttm"), \
                patch.object(fmp_service, "get_key_metrics_ttm"), \
                patch("services.data.kr_fundamentals.get_kr_fundamentals",
                      return_value={"marketCap": 1.0e12}):
            info = fmp_service.get_info("005930.KS")
        m_profile.assert_not_called()
        assert info.get("currency") == "KRW"

    def test_kr_fundamentals_currency_not_overwritten(self):
        """If KIS fundamentals already provide currency, keep it (fill-only)."""
        from services.data import fmp as fmp_service
        self._clear_cache()
        with patch.object(fmp_service, "get_profile"), \
                patch.object(fmp_service, "get_ratios_ttm"), \
                patch.object(fmp_service, "get_key_metrics_ttm"), \
                patch("services.data.kr_fundamentals.get_kr_fundamentals",
                      return_value={"marketCap": 1.0e12, "currency": "KRW"}):
            info = fmp_service.get_info("035720.KQ")
        assert info.get("currency") == "KRW"

    def test_us_info_currency_unchanged(self):
        """Regression: US info still derives currency from FMP profile."""
        from services.data import fmp as fmp_service
        self._clear_cache()
        with patch.object(fmp_service, "get_profile",
                          return_value={"companyName": "Apple Inc.",
                                        "price": 100, "currency": "USD"}), \
                patch.object(fmp_service, "get_ratios_ttm", return_value={}), \
                patch.object(fmp_service, "get_key_metrics_ttm", return_value={}):
            info = fmp_service.get_info("AAPL")
        assert info.get("currency") == "USD"


# ── EarningsCallToneAnalyzer._fetch_transcript KR guard ─────────────────────

class TestEarningsTranscriptKrGuard:
    def test_kr_transcript_skips_fmp(self):
        from services.ai.models import EarningsCallToneAnalyzer
        with patch("services.data.fmp._fmp_get") as m_get:
            out = EarningsCallToneAnalyzer._fetch_transcript("005930.KS")
        m_get.assert_not_called()
        assert out is None

    def test_us_transcript_calls_fmp_when_plan_enabled(self):
        # When the FMP plan includes earning-call-transcript (gate flipped on),
        # US tickers pass the KR guard and reach the FMP layer.
        from services.ai.models import EarningsCallToneAnalyzer
        with patch("services.ai.models._FMP_TRANSCRIPT_AVAILABLE", True):
            with patch("services.data.fmp._fmp_get",
                       return_value=[{"content": "x" * 200}]) as m_get:
                out = EarningsCallToneAnalyzer._fetch_transcript("AAPL")
        m_get.assert_called_once()
        assert out is not None

    def test_us_transcript_skipped_when_plan_gated(self):
        # Default state: earning-call-transcript is 402-gated on the Starter plan,
        # so _FMP_TRANSCRIPT_AVAILABLE is False and even US tickers skip FMP
        # (no wasted call / 402 log). Users supply transcript_text instead.
        from services.ai.models import EarningsCallToneAnalyzer, _FMP_TRANSCRIPT_AVAILABLE
        assert _FMP_TRANSCRIPT_AVAILABLE is False
        with patch("services.data.fmp._fmp_get") as m_get:
            out = EarningsCallToneAnalyzer._fetch_transcript("AAPL")
        m_get.assert_not_called()
        assert out is None
