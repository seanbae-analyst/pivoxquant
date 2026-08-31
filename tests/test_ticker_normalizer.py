"""Tests for services.ticker_normalizer.

Verifies the single-source normalization rule: bare 6-digit codes route
to .KS or .KQ based on registry membership. Already-suffixed inputs
canonicalise. US tickers pass through.
"""
from __future__ import annotations

from unittest.mock import patch

from services.ticker_normalizer import (
    is_korean_ticker,
    normalize_ticker,
    strip_kr_suffix,
)


class TestNormalizeTicker:
    def test_empty_input(self):
        assert normalize_ticker("") == ""
        assert normalize_ticker("   ") == ""

    def test_non_string_input(self):
        # mypy-incorrect input shouldn't blow up
        assert normalize_ticker(None) == ""  # type: ignore[arg-type]
        assert normalize_ticker(12345) == ""  # type: ignore[arg-type]

    def test_us_passthrough_uppercase(self):
        assert normalize_ticker("aapl") == "AAPL"
        assert normalize_ticker("TSLA") == "TSLA"
        assert normalize_ticker("BRK-B") == "BRK-B"

    def test_already_suffixed_kospi(self):
        assert normalize_ticker("005930.KS") == "005930.KS"
        assert normalize_ticker("005930.ks") == "005930.KS"

    def test_already_suffixed_kosdaq(self):
        assert normalize_ticker("293490.KQ") == "293490.KQ"
        assert normalize_ticker("293490.kq") == "293490.KQ"

    def test_krx_alias_collapses_to_ks(self):
        # Legacy alias: ``.KRX`` is rewritten so downstream uses one form.
        assert normalize_ticker("005930.KRX") == "005930.KS"

    def test_bare_six_digit_known_kospi(self):
        # 005930 Samsung — curated registry .KS hit
        assert normalize_ticker("005930") == "005930.KS"

    def test_bare_six_digit_known_kosdaq(self):
        # Stub the full master so we don't depend on the live JSON
        with patch("services.kr_stock_registry.KR_STOCKS", {}), \
                patch("services.kr_stock_registry.KR_STOCKS_FULL",
                      {"293490.KQ": {"name": "카카오게임즈", "market": "KOSDAQ"}}):
            assert normalize_ticker("293490") == "293490.KQ"

    def test_bare_six_digit_unknown_defaults_to_ks(self):
        with patch("services.kr_stock_registry.KR_STOCKS", {}), \
                patch("services.kr_stock_registry.KR_STOCKS_FULL", {}):
            # Unknown 6-digit code — falls back to .KS legacy default
            assert normalize_ticker("999999") == "999999.KS"

    def test_curated_kospi_wins_over_full_master_on_kosdaq(self):
        # If a 6-digit code somehow appears in BOTH (curated KS, full KQ),
        # the curated registry wins because we probe it first. This
        # codifies current behaviour — change with care.
        with patch("services.kr_stock_registry.KR_STOCKS",
                   {"005930.KS": ("Samsung Electronics", "삼성전자")}), \
                patch("services.kr_stock_registry.KR_STOCKS_FULL",
                      {"005930.KQ": {"name": "fake", "market": "KOSDAQ"}}):
            assert normalize_ticker("005930") == "005930.KS"

    def test_suffix_with_non_six_digit_base(self):
        # Garbage in → garbage upper-cased out (caller decides whether
        # to reject — this function never raises).
        assert normalize_ticker("AAPL.KS") == "AAPL.KS"

    def test_strips_whitespace(self):
        assert normalize_ticker("  AAPL  ") == "AAPL"
        assert normalize_ticker("  005930.KS  ") == "005930.KS"


class TestIsKoreanTicker:
    def test_kospi(self):
        assert is_korean_ticker("005930.KS") is True

    def test_kosdaq(self):
        assert is_korean_ticker("293490.KQ") is True

    def test_us(self):
        assert is_korean_ticker("AAPL") is False

    def test_empty(self):
        assert is_korean_ticker("") is False
        assert is_korean_ticker(None) is False  # type: ignore[arg-type]

    def test_lowercase_suffix(self):
        assert is_korean_ticker("005930.ks") is True


class TestStripKrSuffix:
    def test_strips_ks(self):
        assert strip_kr_suffix("005930.KS") == "005930"

    def test_strips_kq(self):
        assert strip_kr_suffix("293490.KQ") == "293490"

    def test_strips_krx(self):
        assert strip_kr_suffix("005930.KRX") == "005930"

    def test_already_bare(self):
        assert strip_kr_suffix("005930") == "005930"

    def test_us_returns_none(self):
        assert strip_kr_suffix("AAPL") is None

    def test_invalid_input(self):
        assert strip_kr_suffix("") is None
        assert strip_kr_suffix(None) is None  # type: ignore[arg-type]
        assert strip_kr_suffix("12345") is None  # 5 digits, not 6


class TestRouteIntegration:
    """Spot-check that updated route handlers use the helper end-to-end."""

    def test_market_imports_normalize_ticker(self):
        from routes import market
        assert market.normalize_ticker is normalize_ticker
