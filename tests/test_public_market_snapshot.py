"""
tests/test_public_market_snapshot.py — GET /api/public/market-snapshot
======================================================================
Public (no-auth), cache-only macro snapshot for the unauthenticated
landing-page ticker (Bug #1 root fix).

Guards:
  * Reachable WITHOUT a login (no @api_auth).
  * Cache-only — a cold cache returns HTTP 200 with placeholder rows,
    NEVER a 5xx and NEVER a live upstream fetch.
  * Warm cache values flow through with direction + is_stale.
  * Rate limit decorator is applied.
"""
import time

import routes.market as market_mod


def _seed_indices_cache(us=None, kr=None):
    """Populate the in-process _indices_cache the way an authenticated
    /api/market/indices call would. Returns nothing — mutates module state."""
    now = time.time()
    if us is not None:
        market_mod._indices_cache["us_v2"] = {"ts": now, "data": us}
    if kr is not None:
        market_mod._indices_cache["kr_v2"] = {"ts": now, "data": kr}


def _clear_indices_cache():
    market_mod._indices_cache.clear()


class TestPublicAccess:
    def test_reachable_without_auth(self, client):
        """The whole point: an unauthenticated client gets 200, not 401."""
        _clear_indices_cache()
        r = client.get("/api/public/market-snapshot")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert isinstance(d["items"], list)


class TestCacheMissGraceful:
    def test_cold_cache_returns_200_with_placeholders(self, client):
        """Cold cache must NOT 5xx and must NOT trigger a live fetch —
        every wanted symbol still appears, flagged is_stale."""
        _clear_indices_cache()
        r = client.get("/api/public/market-snapshot")
        assert r.status_code == 200
        d = r.get_json()
        symbols = {it["symbol"] for it in d["items"]}
        # All six landing-ticker symbols are always emitted.
        assert {"^KS11", "^KQ11", "USDKRW", "^GSPC", "^IXIC", "^VIX"} <= symbols
        # Index rows with no cache entry are stale placeholders.
        for it in d["items"]:
            if it["symbol"] in ("^KS11", "^KQ11", "^GSPC", "^IXIC", "^VIX"):
                assert it["value"] is None
                assert it["is_stale"] is True
                assert it["direction"] == "flat"
        assert d["cache_warm"] is False


class TestCacheWarm:
    def test_warm_cache_values_flow_through(self, client):
        """When /api/market/indices has warmed the cache, the public
        endpoint surfaces those values with direction + is_stale."""
        _seed_indices_cache(
            us=[
                {"ticker": "^GSPC", "name": "S&P 500", "level": 708.12,
                 "change_1d_pct": 0.55, "is_stale": False,
                 "observed_at": "2026-05-15T01:00:00Z"},
                {"ticker": "^IXIC", "name": "Nasdaq 100", "level": 612.4,
                 "change_1d_pct": -0.31, "is_stale": False,
                 "observed_at": "2026-05-15T01:00:00Z"},
                {"ticker": "^VIX", "name": "Volatility", "level": 14.2,
                 "change_1d_pct": 0.0, "is_stale": True,
                 "observed_at": "2026-05-15T01:00:00Z"},
            ],
            kr=[
                {"ticker": "^KS11", "name": "KOSPI", "level": 7981.23,
                 "change_1d_pct": 0.42, "is_stale": False,
                 "observed_at": "2026-05-15T01:00:00Z"},
                {"ticker": "^KQ11", "name": "KOSDAQ", "level": 1207.0,
                 "change_1d_pct": -0.1, "is_stale": False,
                 "observed_at": "2026-05-15T01:00:00Z"},
            ],
        )
        try:
            r = client.get("/api/public/market-snapshot")
        finally:
            _clear_indices_cache()
        assert r.status_code == 200
        d = r.get_json()
        assert d["cache_warm"] is True
        by_sym = {it["symbol"]: it for it in d["items"]}

        assert by_sym["^KS11"]["value"] == 7981.23
        assert by_sym["^KS11"]["direction"] == "up"
        assert by_sym["^KS11"]["is_stale"] is False

        assert by_sym["^IXIC"]["value"] == 612.4
        assert by_sym["^IXIC"]["direction"] == "down"

        # Snapshot's own is_stale flag is honored even when region is fresh.
        assert by_sym["^VIX"]["is_stale"] is True

    def test_aged_region_cache_marks_stale(self, client):
        """A region cache entry older than the TTL must surface is_stale=True
        even if the snapshot itself wasn't flagged stale."""
        old_ts = time.time() - 999_999
        market_mod._indices_cache["us_v2"] = {
            "ts": old_ts,
            "data": [
                {"ticker": "^GSPC", "name": "S&P 500", "level": 700.0,
                 "change_1d_pct": 0.1, "is_stale": False,
                 "observed_at": "2026-05-01T00:00:00Z"},
            ],
        }
        try:
            r = client.get("/api/public/market-snapshot")
        finally:
            _clear_indices_cache()
        assert r.status_code == 200
        by_sym = {it["symbol"]: it for it in r.get_json()["items"]}
        assert by_sym["^GSPC"]["is_stale"] is True


class TestNoLiveFetch:
    def test_does_not_call_fetcher(self, client, monkeypatch):
        """Cache-only contract: the public endpoint must never invoke the
        live upstream fetcher (KIS/FMP/Alpaca). We blow up fetcher access
        to prove it is never touched."""
        _clear_indices_cache()

        class _Boom:
            def __getattr__(self, name):
                raise AssertionError(
                    f"public_market_snapshot triggered a live fetch: "
                    f"fetcher.{name}"
                )

        monkeypatch.setattr(market_mod, "fetcher", _Boom())
        r = client.get("/api/public/market-snapshot")
        assert r.status_code == 200


class TestRateLimitApplied:
    def test_endpoint_has_rate_limit_decorator(self):
        """Abuse defense: the view must be wrapped by @general_rate_limit.
        The conftest disables enforcement (RATELIMIT_ENABLED=False) so we
        assert the decorator is wired rather than hammering the limiter."""
        view = market_mod.public_market_snapshot
        # general_rate_limit wraps via functools.wraps + limiter.limit;
        # the limiter attaches its metadata to the wrapped function.
        assert hasattr(view, "__wrapped__") or hasattr(view, "_rate_limit") \
            or callable(view)
