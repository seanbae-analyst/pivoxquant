"""tests/test_canslim_l_sector_relative.py

Unit tests for the L factor sector-relative-strength implementation
(Wave C-4 P1-02, 2026-05-18).

Covers:
  - _benchmark_ticker: US sector mapping, KR index routing, SPY fallback
  - _check_leader: SECTOR_RELATIVE pass/fail, ABSOLUTE_FALLBACK, NO_DATA
  - CANSLIMScreener.score: L factor wired correctly via sector kwarg
  - score: sector=None still works (SPY fallback path)

All benchmark price fetches are mocked — no live network traffic.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from services.quant.canslim import (
    _US_SECTOR_ETF,
    _benchmark_ticker,
    _check_leader,
    CANSLIMScreener,
)


# ── _benchmark_ticker ────────────────────────────────────────────────────────

class TestBenchmarkTicker:
    def test_kr_ks_returns_ks11(self):
        assert _benchmark_ticker("005930.KS", "Technology") == "^KS11"

    def test_kr_kq_returns_kq11(self):
        assert _benchmark_ticker("247540.KQ", None) == "^KQ11"

    def test_us_technology_maps_xlk(self):
        assert _benchmark_ticker("AAPL", "Technology") == "XLK"

    def test_us_healthcare_maps_xlv(self):
        assert _benchmark_ticker("JNJ", "Healthcare") == "XLV"

    def test_us_financial_services_maps_xlf(self):
        assert _benchmark_ticker("JPM", "Financial Services") == "XLF"

    def test_us_consumer_cyclical_maps_xly(self):
        assert _benchmark_ticker("AMZN", "Consumer Cyclical") == "XLY"

    def test_us_consumer_defensive_maps_xlp(self):
        assert _benchmark_ticker("WMT", "Consumer Defensive") == "XLP"

    def test_us_industrials_maps_xli(self):
        assert _benchmark_ticker("GE", "Industrials") == "XLI"

    def test_us_energy_maps_xle(self):
        assert _benchmark_ticker("XOM", "Energy") == "XLE"

    def test_us_real_estate_maps_xlre(self):
        assert _benchmark_ticker("AMT", "Real Estate") == "XLRE"

    def test_us_utilities_maps_xlu(self):
        assert _benchmark_ticker("NEE", "Utilities") == "XLU"

    def test_us_communication_services_maps_xlc(self):
        assert _benchmark_ticker("META", "Communication Services") == "XLC"

    def test_us_basic_materials_maps_xlb(self):
        assert _benchmark_ticker("NEM", "Basic Materials") == "XLB"

    def test_unknown_sector_falls_back_to_spy(self):
        assert _benchmark_ticker("AAPL", "Conglomerate") == "SPY"

    def test_none_sector_falls_back_to_spy(self):
        assert _benchmark_ticker("AAPL", None) == "SPY"

    def test_empty_sector_falls_back_to_spy(self):
        assert _benchmark_ticker("AAPL", "") == "SPY"

    def test_all_11_sectors_covered(self):
        """All 11 GICS SPDR sectors must map to a non-SPY ETF."""
        for sector, etf in _US_SECTOR_ETF.items():
            assert _benchmark_ticker("X", sector) == etf
            assert etf != "SPY"


# ── _check_leader ────────────────────────────────────────────────────────────

def _prices(start: float, end: float, n: int = 21) -> list[float]:
    """Build a synthetic price list from start to end in n steps."""
    step = (end - start) / (n - 1)
    return [start + i * step for i in range(n)]


class TestCheckLeader:

    @patch("services.quant.canslim._fetch_prices_1m")
    def test_sector_relative_pass_when_stock_beats_sector(self, mock_fetch):
        """Stock +5% vs sector +2% → rel=+3% → pass=True."""
        mock_fetch.return_value = _prices(100.0, 102.0)  # bench +2%
        stock_prices = _prices(100.0, 105.0)  # stock +5%
        result = _check_leader("AAPL", stock_prices, sector="Technology")
        assert result["method"] == "SECTOR_RELATIVE"
        assert result["pass"] is True
        assert result["benchmark"] == "XLK"
        assert result["stock_ret_1m"] == pytest.approx(5.0, abs=0.1)
        assert result["bench_ret_1m"] == pytest.approx(2.0, abs=0.1)
        assert result["value"] == pytest.approx(3.0, abs=0.1)

    @patch("services.quant.canslim._fetch_prices_1m")
    def test_sector_relative_fail_when_stock_lags_sector(self, mock_fetch):
        """Stock +1% vs sector +4% → rel=-3% → pass=False."""
        mock_fetch.return_value = _prices(100.0, 104.0)  # bench +4%
        stock_prices = _prices(100.0, 101.0)  # stock +1%
        result = _check_leader("AAPL", stock_prices, sector="Technology")
        assert result["method"] == "SECTOR_RELATIVE"
        assert result["pass"] is False
        assert result["value"] < 0

    @patch("services.quant.canslim._fetch_prices_1m")
    def test_kr_ticker_uses_ks11_benchmark(self, mock_fetch):
        """005930.KS → ^KS11 benchmark regardless of sector arg."""
        mock_fetch.return_value = _prices(2700.0, 2750.0)  # KS11 +1.8%
        stock_prices = _prices(70000.0, 72000.0)  # stock +2.9%
        result = _check_leader("005930.KS", stock_prices, sector=None)
        assert result["benchmark"] == "^KS11"
        assert result["method"] == "SECTOR_RELATIVE"
        assert result["pass"] is True

    @patch("services.quant.canslim._fetch_prices_1m")
    def test_benchmark_fetch_failure_uses_absolute_fallback(self, mock_fetch):
        """When benchmark fetch returns None, fall back to absolute return."""
        mock_fetch.return_value = None
        stock_prices = _prices(100.0, 103.0)  # +3%
        result = _check_leader("AAPL", stock_prices, sector="Technology")
        assert result["method"] == "ABSOLUTE_FALLBACK"
        assert result["pass"] is True
        assert result["benchmark"] == "XLK"
        assert result["stock_ret_1m"] == pytest.approx(3.0, abs=0.1)
        # bench_ret_1m must NOT appear (not computed)
        assert "bench_ret_1m" not in result

    @patch("services.quant.canslim._fetch_prices_1m")
    def test_absolute_fallback_fail_when_stock_negative(self, mock_fetch):
        """Fallback path: stock -2% → pass=False."""
        mock_fetch.return_value = None
        stock_prices = _prices(100.0, 98.0)  # -2%
        result = _check_leader("AAPL", stock_prices, sector="Technology")
        assert result["method"] == "ABSOLUTE_FALLBACK"
        assert result["pass"] is False

    def test_no_data_returns_pass_false(self):
        """Empty prices → method=NO_DATA, pass=False."""
        result = _check_leader("AAPL", [], sector="Technology")
        assert result["pass"] is False
        assert result["method"] == "NO_DATA"

    def test_single_price_returns_pass_false(self):
        """Single price → need >=2 for a return calculation."""
        result = _check_leader("AAPL", [100.0], sector="Technology")
        assert result["pass"] is False
        assert result["method"] == "NO_DATA"

    @patch("services.quant.canslim._fetch_prices_1m")
    def test_result_keys_present_on_sector_relative(self, mock_fetch):
        """SECTOR_RELATIVE result must include all documented payload keys."""
        mock_fetch.return_value = _prices(100.0, 101.0)
        result = _check_leader("AAPL", _prices(100.0, 105.0), sector="Technology")
        for key in ("value", "pass", "reason", "method", "benchmark",
                    "stock_ret_1m", "bench_ret_1m"):
            assert key in result, f"missing key: {key}"

    @patch("services.quant.canslim._fetch_prices_1m")
    def test_result_keys_present_on_absolute_fallback(self, mock_fetch):
        """ABSOLUTE_FALLBACK result must include documented payload keys."""
        mock_fetch.return_value = None
        result = _check_leader("AAPL", _prices(100.0, 105.0), sector="Technology")
        for key in ("value", "pass", "reason", "method", "benchmark", "stock_ret_1m"):
            assert key in result, f"missing key: {key}"


# ── CANSLIMScreener.score — L wiring ─────────────────────────────────────────

def _make_closes(n: int = 252, start: float = 100.0, end: float = 120.0):
    return np.linspace(start, end, n)


def _make_volumes(n: int = 252, base: float = 1_000_000.0):
    return np.full(n, base)


class TestScoreLFactorWiring:
    """Integration: CANSLIMScreener.score passes sector to _check_leader."""

    @patch("services.quant.canslim._fetch_prices_1m")
    @patch("services.quant.canslim._check_current_eps")
    @patch("services.quant.canslim._check_annual_eps")
    @patch("services.quant.canslim._check_institutional")
    def test_score_passes_sector_to_l_factor(
        self, mock_inst, mock_annual, mock_current, mock_fetch
    ):
        """sector kwarg must reach _fetch_prices_1m (via _check_leader → _benchmark_ticker)."""
        mock_current.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_annual.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_inst.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        # Benchmark outperforms → L should fail (stock at +3%, bench at +5%)
        mock_fetch.return_value = _prices(100.0, 105.0, 21)  # bench +5%

        closes = _make_closes(252, 100.0, 103.0)  # last 21 bars ≈ +3%
        volumes = _make_volumes(252)

        result = CANSLIMScreener.score(
            "AAPL", closes, volumes, regime="BULL", sector="Technology"
        )

        l = result["criteria"]["L"]
        assert l["method"] == "SECTOR_RELATIVE", f"expected SECTOR_RELATIVE, got {l}"
        assert l["benchmark"] == "XLK"
        assert l["pass"] is False  # stock lagged sector

        # Confirm _fetch_prices_1m was called with XLK
        call_args = [call.args[0] for call in mock_fetch.call_args_list]
        assert "XLK" in call_args, f"XLK not fetched; calls: {call_args}"

    @patch("services.quant.canslim._fetch_prices_1m")
    @patch("services.quant.canslim._check_current_eps")
    @patch("services.quant.canslim._check_annual_eps")
    @patch("services.quant.canslim._check_institutional")
    def test_score_with_sector_none_uses_spy(
        self, mock_inst, mock_annual, mock_current, mock_fetch
    ):
        """sector=None → SPY benchmark (broad-market fallback)."""
        mock_current.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_annual.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_inst.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_fetch.return_value = _prices(100.0, 102.0, 21)  # SPY +2%

        closes = _make_closes(252, 100.0, 105.0)  # stock outperforms
        volumes = _make_volumes(252)

        result = CANSLIMScreener.score(
            "AAPL", closes, volumes, regime="BULL", sector=None
        )
        l = result["criteria"]["L"]
        assert l["benchmark"] == "SPY"

    @patch("services.quant.canslim._fetch_prices_1m")
    @patch("services.quant.canslim._check_current_eps")
    @patch("services.quant.canslim._check_annual_eps")
    @patch("services.quant.canslim._check_institutional")
    def test_score_l_name_updated(
        self, mock_inst, mock_annual, mock_current, mock_fetch
    ):
        """L factor name field must reflect the new implementation."""
        mock_current.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_annual.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_inst.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_fetch.return_value = _prices(100.0, 101.0, 21)

        closes = _make_closes(252)
        result = CANSLIMScreener.score("AAPL", closes, _make_volumes(252), sector="Technology")
        assert result["criteria"]["L"]["name"] == "Leader (Sector Relative Strength)"

    @patch("services.quant.canslim._fetch_prices_1m")
    @patch("services.quant.canslim._check_current_eps")
    @patch("services.quant.canslim._check_annual_eps")
    @patch("services.quant.canslim._check_institutional")
    def test_score_backwards_compat_no_sector_kwarg(
        self, mock_inst, mock_annual, mock_current, mock_fetch
    ):
        """Calling score() without sector kwarg must not raise (backwards compat)."""
        mock_current.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_annual.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_inst.return_value = {"value": None, "pass": None, "method": "UNAVAILABLE", "reason": ""}
        mock_fetch.return_value = None  # bench unavailable → absolute fallback

        closes = _make_closes(252)
        # Must not raise
        result = CANSLIMScreener.score("AAPL", closes, _make_volumes(252))
        assert "L" in result["criteria"]
        assert result["criteria"]["L"]["method"] == "ABSOLUTE_FALLBACK"
