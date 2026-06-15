"""tests/test_discover_cache_swr.py — Discover SWR cache (B-07).

Stale-while-revalidate behaviour for /api/discover/{market-overview,
movers, sectors}. The contract:

    upstream OK                 → 200 + stale=false (or list w/o flag) +
                                  fresh cache replaced
    upstream FAIL + fresh cache → 200 + stale=false (cache hit)
    upstream FAIL + stale cache → 200 + stale=true + last_updated +
                                  code=DISCOVER_STALE_DATA_ONLY
    upstream FAIL + no cache    → 503 + DISCOVER_FMP_UNAVAILABLE

Memory pattern [feedback_bug_fix_patterns] "stale fallback". Replaces the
all-or-nothing fail-fast that took down the entire Discover page on FMP
402 bursts. We never fabricate data — only re-emit what FMP previously
returned, with a "this may be up to 24h old" annotation.

Discover screeners stay 503-only (no live source wired); we don't test
SWR there because there's nothing real to cache.
"""
from __future__ import annotations

import time
from unittest.mock import patch


# ── helpers ──────────────────────────────────────────────────────────────────

OVERVIEW_OK = {
    "sp500":  {"price": 5800.0, "change_pct":  0.42},
    "nasdaq": {"price": 19000.0, "change_pct":  0.55},
    "dow":    {"price": 42000.0, "change_pct": -0.10},
    "kospi":  {"price": 2650.0, "change_pct":  0.30},
    "kosdaq": {"price":  870.0, "change_pct": -0.22},
}

SECTORS_OK = [
    {"sector": "Technology", "changesPercentage": "1.23%"},
    {"sector": "Health Care", "changesPercentage": "-0.45%"},
    {"sector": "Financials", "changesPercentage": "0.30%"},
    {"sector": "Energy", "changesPercentage": "-0.80%"},
    {"sector": "Consumer Discretionary", "changesPercentage": "0.55%"},
    {"sector": "Industrials", "changesPercentage": "0.10%"},
]


def _clear_section_cache():
    from services import cache_service
    cache_service.discover_section_cache_clear()


def _set_swr_ttls(fresh, max_age):
    from services import cache_service
    cache_service.discover_section_cache_set_ttls(fresh, max_age)


def _reset_swr_ttls():
    from services import cache_service
    cache_service.discover_section_cache_set_ttls(None, None)


# ── market-overview SWR (representative section) ────────────────────────────

class TestMarketOverviewSWR:
    def setup_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def teardown_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def test_upstream_ok_fresh_cache_200(self, client, auth_user):
        """FMP returns full payload → 200 + cache populated as fresh."""
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.return_value = OVERVIEW_OK
            r = client.get("/api/discover/market-overview")
        assert r.status_code == 200
        body = r.get_json()
        # market-overview historically returns a list — fresh path keeps that.
        assert isinstance(body, list)
        assert len(body) == 5

    def test_upstream_fail_fresh_cache_serves_cache(self, client, auth_user):
        """FMP fails BUT cache is fresh → 200 from cache."""
        # Prime the cache with a successful upstream call.
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.return_value = OVERVIEW_OK
            r = client.get("/api/discover/market-overview")
            assert r.status_code == 200

        # Now upstream fails — fresh cache (still <30min) must serve.
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.side_effect = RuntimeError("FMP 402")
            r = client.get("/api/discover/market-overview")
        assert r.status_code == 200
        # Fresh-path returns the original list shape (no stale flag).
        body = r.get_json()
        assert isinstance(body, list)
        assert len(body) == 5

    def test_upstream_fail_stale_cache_serves_stale_with_flag(self, client, auth_user):
        """FMP fails AND cache is stale (>30min, <24h) → 200 + stale=true."""
        # Prime cache.
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.return_value = OVERVIEW_OK
            r = client.get("/api/discover/market-overview")
            assert r.status_code == 200

        # Force the cache into "stale" classification: fresh threshold
        # tiny (1ms) so any age > 1ms is stale. Sleep > 1ms to age the
        # entry without waiting 30 minutes.
        _set_swr_ttls(0.001, 86400)
        time.sleep(0.01)

        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.side_effect = RuntimeError("FMP 402")
            r = client.get("/api/discover/market-overview")
        assert r.status_code == 200
        body = r.get_json()
        # Stale-path wraps the list in a dict with the staleness fields.
        assert isinstance(body, dict)
        assert body.get("stale") is True
        assert body.get("code") == "DISCOVER_STALE_DATA_ONLY"
        assert "last_updated" in body
        assert "indices" in body
        assert isinstance(body["indices"], list)
        assert len(body["indices"]) == 5

    def test_upstream_fail_no_cache_503(self, client, auth_user):
        """FMP fails with no cache at all → 503 + DISCOVER_FMP_UNAVAILABLE."""
        # No prior priming → cache is empty.
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.side_effect = RuntimeError("FMP 402")
            r = client.get("/api/discover/market-overview")
        assert r.status_code == 503
        body = r.get_json()
        assert body.get("code") == "DISCOVER_FMP_UNAVAILABLE"
        assert "retry_after" in body

    def test_cache_max_age_eviction_drops_to_503(self, client, auth_user):
        """Past 24h max-age, the entry is evicted → fall to 503."""
        # Prime cache.
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.return_value = OVERVIEW_OK
            r = client.get("/api/discover/market-overview")
            assert r.status_code == 200

        # Squash both TTLs to 1ms → next read past 1ms = miss (evicted).
        _set_swr_ttls(0.001, 0.001)
        time.sleep(0.01)

        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.side_effect = RuntimeError("FMP 402")
            r = client.get("/api/discover/market-overview")
        assert r.status_code == 503
        body = r.get_json()
        assert body.get("code") == "DISCOVER_FMP_UNAVAILABLE"


# ── sectors SWR ──────────────────────────────────────────────────────────────

class TestSectorsSWR:
    def setup_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def teardown_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def test_sectors_fresh_path(self, client, auth_user):
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_sector_performance.return_value = SECTORS_OK
            r = client.get("/api/discover/sectors")
        assert r.status_code == 200
        body = r.get_json()
        assert isinstance(body, list)
        assert len(body) == len(SECTORS_OK)

    def test_sectors_stale_served_when_upstream_fails(self, client, auth_user):
        # Prime
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_sector_performance.return_value = SECTORS_OK
            r = client.get("/api/discover/sectors")
            assert r.status_code == 200

        # Age the entry → stale
        _set_swr_ttls(0.001, 86400)
        time.sleep(0.01)

        # Upstream now returns nothing (the typical FMP 402 case where
        # fetcher swallows the error and returns []).
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_sector_performance.return_value = []
            r = client.get("/api/discover/sectors")
        assert r.status_code == 200
        body = r.get_json()
        assert isinstance(body, dict)
        assert body.get("stale") is True
        assert body.get("code") == "DISCOVER_STALE_DATA_ONLY"
        assert "last_updated" in body
        assert "sectors" in body
        assert len(body["sectors"]) == len(SECTORS_OK)

    def test_sectors_no_cache_503(self, client, auth_user):
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_sector_performance.return_value = []
            r = client.get("/api/discover/sectors")
        assert r.status_code == 503
        body = r.get_json()
        assert body.get("code") == "DISCOVER_FMP_UNAVAILABLE"


# ── movers SWR ───────────────────────────────────────────────────────────────

class TestMoversSWR:
    """Movers is sourced from the per-user discover_cache, not a direct FMP
    call. We simulate by populating that cache directly."""

    def setup_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def teardown_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def _seed_user_discover(self, uid):
        """Plant analyzed rows into discover_cache so movers can derive.

        change_pct spans BOTH signs (P1-A fix, 2026-06-15): losers are now
        strictly negative, so an all-positive seed would yield zero losers.
        ``(5 - i) * 0.9`` → 5 gainers (>0), 1 flat (=0), 4 losers (<0).
        """
        from services import cache_service
        rows = [
            {"ticker": f"T{i}", "name": f"Stock {i}", "is_korean": False,
             "price": 100.0 + i, "change_pct": (5 - i) * 0.9}
            for i in range(10)
        ]
        cache_service.discover_cache[uid] = {"data": rows, "ts": time.time()}

    def test_movers_fresh_path(self, client, auth_user):
        self._seed_user_discover(auth_user["id"])
        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("region") == "us"
        assert len(body.get("gainers", [])) >= 3
        assert len(body.get("losers", [])) >= 3
        assert body.get("stale") is False

    def test_movers_stale_when_universe_empty(self, client, auth_user):
        # Prime cache with full data.
        self._seed_user_discover(auth_user["id"])
        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 200

        # Now the universe rows are gone (e.g. user logs out, cache evicted)
        # — section cache should still serve stale.
        from services import cache_service
        cache_service.discover_cache.pop(auth_user["id"], None)
        _set_swr_ttls(0.001, 86400)
        time.sleep(0.01)

        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("stale") is True
        assert body.get("code") == "DISCOVER_STALE_DATA_ONLY"
        assert "last_updated" in body

    def test_movers_503_when_no_cache_and_no_data(self, client, auth_user):
        # No priming, no rows.
        from services import cache_service
        cache_service.discover_cache.pop(auth_user["id"], None)
        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 503
        body = r.get_json()
        assert body.get("code") == "DISCOVER_FMP_UNAVAILABLE"
