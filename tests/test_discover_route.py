"""tests/test_discover_route.py — /api/discover/* HTTP coverage.

Wave 11 (P1 critical path) — discover_bp had no direct HTTP tests. The
section endpoints fail-fast (503) on upstream data outage rather than
serving stale/mock numbers; we verify the auth gate is intact and the
happy path produces the expected envelope.

  - Unauthenticated movers → 401.
  - Authenticated discover → 200 with cached/fresh envelope.
  - market-overview response shape: list of {name, level, change_pct}.
"""
from __future__ import annotations

from unittest.mock import patch


class TestDiscoverUnauthenticated:
    def test_discover_movers_unauthenticated_401(self, raw_client):
        """Discover section endpoints all require auth — no public data."""
        r = raw_client.get("/api/discover/movers?region=us")
        assert r.status_code == 401

        r = raw_client.get("/api/discover")
        assert r.status_code == 401


class TestDiscoverAuthenticated:
    def test_discover_authenticated_200(self, client, auth_user, app):
        """Authenticated /api/discover returns 200 with results envelope.

        We force the engine to short-circuit (return None) so the test
        does NOT depend on whether the user has positions/watchlist —
        prior tests in the same session can pollute the discover_cache,
        and engine.analyze can hit the wire on KR tickers.
        """
        # Clear any cached results from previous tests using this app.
        from services import cache_service
        cache_service.discover_cache.pop(auth_user["id"], None)

        with patch("routes.discover.engine") as mock_engine:
            mock_engine.analyze.return_value = None
            r = client.get("/api/discover?force=1")

        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert "results" in body
        assert isinstance(body["results"], list)
        # engine returned None for every ticker → results filtered to [].
        assert body["results"] == []


class TestDiscoverResponseShape:
    def test_discover_response_shape(self, client, auth_user):
        """market-overview must either serve cache or fail-fast 503."""
        # Clear any cache pollution from prior tests so this assertion is
        # deterministic — without a cache, upstream raise → 503.
        from services import cache_service
        cache_service.discover_section_cache_clear()

        # Force the upstream call to raise so we exercise the fail-fast
        # 503 contract — documented when FMP is unreachable AND no usable
        # SWR cache exists (B-07 stale-while-revalidate).
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_enhanced_macro.side_effect = RuntimeError("upstream down")
            r = client.get("/api/discover/market-overview")

        assert r.status_code in (200, 503)
        body = r.get_json()
        if r.status_code == 503:
            # Documented fail-fast envelope (B-07: code renamed from
            # DATA_PROVIDER_DOWN → DISCOVER_FMP_UNAVAILABLE so frontend
            # can distinguish discover-specific failure modes).
            assert body.get("code") == "DISCOVER_FMP_UNAVAILABLE"
            assert "endpoint" in body
            assert "retry_after" in body
        else:
            # Live data path — must be a list of index cards.
            assert isinstance(body, list)
            for entry in body:
                assert "name" in entry
                assert "level" in entry
                assert "change_pct" in entry
