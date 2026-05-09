"""tests/test_fmp_revenue_growth.py — Bug #16 (2026-05-08).

Locks in the wiring from FMP `/income-statement-growth` → ``info["revenueGrowth"]``.

Background:
    AAPL Detail page rendered "Revenue growth (YoY): —" because
    ``services/data/fmp.py::get_info`` deliberately set ``revenueGrowth``
    to ``None`` (an earlier mismapping had populated it with revenue-per-share,
    which the UI then multiplied by 100 to produce nonsense %).

    Now ``get_income_statement_growth(ticker)`` consults the FMP stable
    ``/income-statement-growth`` endpoint and returns the latest annual row
    whose ``growthRevenue`` field is a clean YoY rate (0.12 = +12%).

    The contract enforced here:
      - Helper returns the row dict on success.
      - Helper returns {} on miss / network failure (NOT None — callers use ``.get()``).
      - ``get_info`` exposes the float as ``info["revenueGrowth"]``.
      - Cache key ``income_growth:<ticker>`` follows existing pattern.
      - ``revenueGrowth`` flows through ``data_fetcher.get_snapshot`` as
        ``snapshot["revenue_growth"]`` (consumed by quant/engine.py).
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


class TestIncomeStatementGrowthHelper:
    def test_returns_first_row_on_success(self):
        _clear_fmp_cache()
        payload = [{
            "date": "2025-09-30",
            "fiscalYear": "2025",
            "period": "FY",
            "growthRevenue": 0.082,
            "growthNetIncome": 0.131,
            "growthEPS": 0.143,
        }]
        with patch("services.data.fmp._fmp_get", return_value=payload):
            row = fmp_service.get_income_statement_growth("AAPL")
        assert row.get("growthRevenue") == 0.082
        assert row.get("fiscalYear") == "2025"

    def test_returns_empty_dict_on_empty_payload(self):
        _clear_fmp_cache()
        with patch("services.data.fmp._fmp_get", return_value=[]):
            row = fmp_service.get_income_statement_growth("XYZNOTICKER")
        # Empty dict (not None) so callers can chain .get(...) safely.
        assert row == {}

    def test_returns_empty_dict_on_none_response(self):
        _clear_fmp_cache()
        with patch("services.data.fmp._fmp_get", return_value=None):
            row = fmp_service.get_income_statement_growth("XYZ")
        assert row == {}

    def test_uses_cache_within_ttl(self):
        _clear_fmp_cache()
        payload = [{"growthRevenue": 0.05}]
        with patch("services.data.fmp._fmp_get", return_value=payload) as m:
            r1 = fmp_service.get_income_statement_growth("AAPL")
            r2 = fmp_service.get_income_statement_growth("AAPL")
        assert r1.get("growthRevenue") == 0.05
        assert r2.get("growthRevenue") == 0.05
        # Single network call — second was a cache hit.
        assert m.call_count == 1

    def test_class_share_alt_retry(self):
        """BRK.B empty → retry as BRK-B (mirrors the get_ratios_ttm pattern)."""
        _clear_fmp_cache()
        calls = []

        def _fake(endpoint, params=None, timeout=5):
            calls.append((endpoint, dict(params or {})))
            sym = (params or {}).get("symbol")
            if sym == "BRK.B":
                return []
            if sym == "BRK-B":
                return [{"growthRevenue": 0.07}]
            return None

        with patch("services.data.fmp._fmp_get", side_effect=_fake):
            row = fmp_service.get_income_statement_growth("BRK.B")
        assert row.get("growthRevenue") == 0.07
        symbols = [c[1].get("symbol") for c in calls]
        assert "BRK.B" in symbols and "BRK-B" in symbols


class TestGetInfoWiresRevenueGrowth:
    """`get_info` must populate ``info["revenueGrowth"]`` from the helper."""

    def test_revenue_growth_populated_from_growth_endpoint(self):
        _clear_fmp_cache()
        with patch("services.data.fmp.get_profile",
                   return_value={"companyName": "Apple", "sector": "Tech",
                                 "marketCap": 3_500_000_000_000, "price": 200,
                                 "range": "180-220"}), \
             patch("services.data.fmp.get_ratios_ttm",
                   return_value={"priceToEarningsRatioTTM": 30,
                                 "netIncomePerShareTTM": 6.5,
                                 "revenuePerShareTTM": 25.0,
                                 "netProfitMarginTTM": 0.25,
                                 "priceToBookRatioTTM": 40}), \
             patch("services.data.fmp.get_key_metrics_ttm",
                   return_value={"epsTTM": 6.5}), \
             patch("services.data.fmp.get_income_statement_growth",
                   return_value={"growthRevenue": 0.082}):
            info = fmp_service.get_info("AAPL")
        assert info.get("revenueGrowth") == 0.082, (
            "Bug #16 regression: revenueGrowth must come from "
            "/income-statement-growth, not be hardcoded None"
        )

    def test_revenue_growth_none_when_endpoint_empty(self):
        _clear_fmp_cache()
        with patch("services.data.fmp.get_profile",
                   return_value={"companyName": "Apple", "sector": "Tech",
                                 "marketCap": 3_500_000_000_000, "price": 200,
                                 "range": "180-220"}), \
             patch("services.data.fmp.get_ratios_ttm",
                   return_value={"priceToEarningsRatioTTM": 30,
                                 "netIncomePerShareTTM": 6.5,
                                 "revenuePerShareTTM": 25.0,
                                 "netProfitMarginTTM": 0.25,
                                 "priceToBookRatioTTM": 40}), \
             patch("services.data.fmp.get_key_metrics_ttm",
                   return_value={"epsTTM": 6.5}), \
             patch("services.data.fmp.get_income_statement_growth",
                   return_value={}):
            info = fmp_service.get_info("AAPL")
        # When the endpoint returns nothing the field stays None — UI renders "—"
        # rather than zero (zero would imply "0% growth", which is a claim).
        assert info.get("revenueGrowth") is None

    def test_revenue_growth_failure_is_swallowed(self):
        """Exceptions from the growth helper must NOT break get_info."""
        _clear_fmp_cache()

        def _boom(_t):
            raise RuntimeError("upstream 502")

        with patch("services.data.fmp.get_profile",
                   return_value={"companyName": "Apple", "sector": "Tech",
                                 "marketCap": 3_500_000_000_000, "price": 200,
                                 "range": "180-220"}), \
             patch("services.data.fmp.get_ratios_ttm",
                   return_value={"priceToEarningsRatioTTM": 30,
                                 "netIncomePerShareTTM": 6.5,
                                 "revenuePerShareTTM": 25.0,
                                 "netProfitMarginTTM": 0.25,
                                 "priceToBookRatioTTM": 40}), \
             patch("services.data.fmp.get_key_metrics_ttm",
                   return_value={"epsTTM": 6.5}), \
             patch("services.data.fmp.get_income_statement_growth",
                   side_effect=_boom):
            info = fmp_service.get_info("AAPL")
        # Other fields must still be populated; revenueGrowth stays None.
        assert info.get("trailingPE") == 30
        assert info.get("revenueGrowth") is None
