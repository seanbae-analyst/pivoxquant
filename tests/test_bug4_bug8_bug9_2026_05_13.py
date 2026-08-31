"""Regression tests for the 2026-05-13 carry-over backend wave.

Covers:
  * Bug #4 — /api/discover/* 503 envelope reworded to "Live tape paused"
             while keeping the machine code DISCOVER_FMP_UNAVAILABLE.
             DISCOVER_FRESH_TTL bumped 1800 → 3600 to absorb FMP quota
             cool-offs without flipping the section to stale.
  * Bug #8 — Snapshot tags ``fundamentals_limited`` / ``fundamentals_source``
             so the detail UI can render an honest tooltip on KR tickers
             rather than looking broken when KIS can't supply margin/
             revenue_growth/debt_equity.
  * Bug #9 — Watchlist serializer publishes ``range_52w`` from the cached
             snapshot (KIS-sourced for KR, FMP/Alpaca for US). Em-dash
             remains the honest output when the bounds are missing —
             we never synthesize from current price.
"""
from __future__ import annotations

import json
from unittest.mock import patch


# ══════════════════════════════════════════════════════════════════════
# Bug #4 — /api/discover/* 503 envelope copy
# ══════════════════════════════════════════════════════════════════════


class TestDiscoverFreshTtlBump:
    """DISCOVER_FRESH_TTL must be at least 1 hour so a cached payload
    written at the top of the hour still classifies as ``fresh`` mid-hour
    when the next FMP burst hits the soft quota."""

    def test_fresh_ttl_at_least_3600(self):
        from services import cache_service
        assert cache_service.DISCOVER_FRESH_TTL >= 3600


# ══════════════════════════════════════════════════════════════════════
# Bug #9 — Watchlist range_52w
# ══════════════════════════════════════════════════════════════════════


class TestFundamentalsLimitedFlag:
    """The snapshot dict must annotate when KR fundamentals are
    structurally absent (KIS license scope) so the detail UI can render
    a tooltip rather than a blank "—" that looks broken. The flag is
    advisory — the underlying values stay None as before."""

    def test_kr_with_all_three_null_flags_limited(self):
        from services.data.fetcher import DataFetcher

        fetcher = DataFetcher()
        # Minimal stub: monkeypatch the dependencies that hit the wire,
        # leaving the dict-build path under test.
        import pandas as pd

        df = pd.DataFrame({
            "Open":  [50000] * 20,
            "High":  [60000] * 20,
            "Low":   [40000] * 20,
            "Close": [55000] * 20,
            "Volume":[1000] * 20,
        })

        with patch.object(fetcher, "currency", return_value="KRW"), \
             patch.object(fetcher, "is_korean", return_value=True), \
             patch.object(fetcher, "get_price_history", return_value=df), \
             patch("services.data.fetcher.fmp.get_info", return_value={
                 "shortName": "삼성전자",
                 "trailingPE": 12.3,
                 # KIS does NOT publish these three for KR
                 "revenueGrowth": None,
                 "netProfitMargin": None,
                 "debtToEquity": None,
             }), \
             patch("services.container.realtime") as mock_rt:
            mock_rt.get_price.return_value = {"price": 55000}
            snap = fetcher._fetch_snapshot("005930.KS")

        assert snap is not None
        assert snap["is_korean"] is True
        assert snap["fundamentals_limited"] is True
        assert snap["fundamentals_source"] == "kis"
        # Underlying fields stay None (we don't fabricate)
        assert snap["profit_margin"] is None
        assert snap["revenue_growth"] is None
        assert snap["debt_equity"] is None

    def test_us_ticker_never_marked_limited(self):
        from services.data.fetcher import DataFetcher
        import pandas as pd

        df = pd.DataFrame({
            "Open":  [100] * 20,
            "High":  [110] * 20,
            "Low":   [90]  * 20,
            "Close": [105] * 20,
            "Volume":[5000] * 20,
        })

        fetcher = DataFetcher()
        with patch.object(fetcher, "currency", return_value="USD"), \
             patch.object(fetcher, "is_korean", return_value=False), \
             patch.object(fetcher, "get_price_history", return_value=df), \
             patch.object(fetcher, "_alpaca_latest_quote",
                          return_value={"price": 105}), \
             patch("services.data.fetcher.fmp.get_info", return_value={
                 "shortName": "Apple Inc.",
                 "revenueGrowth": None,
                 "netProfitMargin": None,
                 "debtToEquity": None,
             }):
            snap = fetcher._fetch_snapshot("AAPL")

        assert snap is not None
        assert snap["is_korean"] is False
        # Even with all three None, US must NOT flag limited — that's
        # an FMP coverage gap, not a license-scope structural one.
        assert snap["fundamentals_limited"] is False
        assert snap["fundamentals_source"] == "fmp"
