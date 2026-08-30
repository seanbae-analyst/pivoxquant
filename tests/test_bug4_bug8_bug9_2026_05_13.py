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


class TestDiscoverUnavailableEnvelope:
    """The reworded envelope must keep ``code=DISCOVER_FMP_UNAVAILABLE``
    (frontend SWR + log alerts dispatch on the machine code) but ship a
    user-facing ``error`` that names the upstream cause without sounding
    catastrophic. ``error_kr`` is now part of the contract.
    """

    def test_movers_503_envelope_names_the_real_cause(self, client, auth_user):
        """An empty per-user cache is "nothing scanned", not a provider outage.

        Superseded 2026-08-30: this case used to assert the shared
        DISCOVER_FMP_UNAVAILABLE envelope. Movers has no provider call — it
        reads the per-user discover cache — so blaming FMP quota sent US users
        to wait out an outage that was not happening. The non-catastrophic-copy
        contract this class guards still holds, on the accurate code.
        """
        from services import cache_service
        cache_service.discover_section_cache_clear()
        # Empty user discover cache → no rows for movers + no section cache → 503.
        cache_service.discover_cache.pop(auth_user["id"], None)

        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 503
        body = r.get_json()
        assert body["code"] == "MOVERS_US_NO_DATA"
        assert body["error"] != "Data temporarily unavailable"
        assert "quota" not in body["error"].lower()
        assert "한도" not in body["error_kr"]
        assert body["retry_after"] == 60

    def test_data_unavailable_envelope_still_guards_real_provider_failures(
        self, client, auth_user
    ):
        """The reworded FMP envelope stays intact for endpoints that do call it."""
        from unittest.mock import patch
        from services import cache_service
        cache_service.discover_section_cache_clear()

        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.side_effect = RuntimeError("FMP 402")
            r = client.get("/api/discover/market-overview")
        assert r.status_code == 503
        body = r.get_json()
        assert body["code"] == "DISCOVER_FMP_UNAVAILABLE"
        assert "tape" in body["error"].lower()
        assert "라이브" in body["error_kr"]


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


class TestWatchlistRange52W:
    def _seed(self, app, user_id, ticker, signal_data):
        from extensions import db
        from models import Watchlist, SignalCache
        with app.app_context():
            db.session.add(Watchlist(user_id=user_id, ticker=ticker, note=""))
            db.session.add(SignalCache(
                ticker=ticker,
                data_json=json.dumps(signal_data),
            ))
            db.session.commit()

    def test_kr_ticker_range_52w_published(self, client, auth_user, app):
        """005930.KS — KIS history feeds snapshot.week52_high/low, which
        watchlist serializer now surfaces as range_52w: [lo, hi]."""
        self._seed(app, auth_user["id"], "005930.KS", {
            "name": "삼성전자",
            "currency": "KRW",
            "is_korean": True,
            "price_display": "₩53,700",
            "snapshot": {
                "week52_low": 53700,
                "week52_high": 291500,
                "currency": "KRW",
            },
        })
        with patch("routes.watchlist.overlay_prices", return_value={}):
            r = client.get("/api/watchlist")
        assert r.status_code == 200
        items = r.get_json()["watchlist"]
        assert len(items) == 1
        # KR = integer (dp=0)
        assert items[0]["range_52w"] == [53700, 291500]

    def test_us_ticker_range_52w_published(self, client, auth_user, app):
        self._seed(app, auth_user["id"], "AAPL", {
            "name": "Apple Inc.",
            "currency": "USD",
            "is_korean": False,
            "price_display": "$182.34",
            "snapshot": {
                "week52_low": 164.08,
                "week52_high": 237.49,
                "currency": "USD",
            },
        })
        with patch("routes.watchlist.overlay_prices", return_value={}):
            r = client.get("/api/watchlist")
        items = r.get_json()["watchlist"]
        assert len(items) == 1
        # USD = 2 dp
        assert items[0]["range_52w"] == [164.08, 237.49]

    def test_missing_bounds_returns_none(self, client, auth_user, app):
        """No week52 in snapshot → range_52w stays None (UI renders "—").
        Never fabricated from the current price."""
        self._seed(app, auth_user["id"], "TSLA", {
            "name": "Tesla, Inc.",
            "currency": "USD",
            "is_korean": False,
            "price_display": "$251.10",
            # snapshot absent entirely
        })
        with patch("routes.watchlist.overlay_prices", return_value={}):
            r = client.get("/api/watchlist")
        items = r.get_json()["watchlist"]
        assert len(items) == 1
        assert items[0]["range_52w"] is None

    def test_inverted_or_zero_bounds_rejected(self, client, auth_user, app):
        """Defensive: a snapshot with low > high or any 0 bound is
        rejected — we never publish a sentinel/garbage range as truth."""
        self._seed(app, auth_user["id"], "MSFT", {
            "name": "Microsoft Corporation",
            "currency": "USD",
            "is_korean": False,
            "snapshot": {"week52_low": 500, "week52_high": 100},
        })
        with patch("routes.watchlist.overlay_prices", return_value={}):
            r = client.get("/api/watchlist")
        items = r.get_json()["watchlist"]
        assert items[0]["range_52w"] is None


# ══════════════════════════════════════════════════════════════════════
# Bug #8 — Snapshot fundamentals data-source hint
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
