"""Tests for two pre-launch fixes:

FIX 1 (HIGH, §101) — canslim_screener (/api/screener/canslim/<ticker>) must
enforce the same owned|watched ticker isolation as swot/discover. An arbitrary
ticker outside the user's scope must 403 with the standard
``ticker_not_in_user_scope`` payload — analysing an arbitrary universe would
read as 미등록 투자자문업 (capital-markets-law grey zone).

FIX 2 (MEDIUM) — /api/search must not interpolate the raw user query into the
FMP URL (param-injection / oversize) and must cap query length.
"""
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------
# FIX 1 — CAN SLIM ticker isolation (§101)
# --------------------------------------------------------------------------
class TestCanslimIsolation:
    def test_canslim_denies_ticker_not_in_user_scope(self, client, auth_user):
        """A ticker the user neither owns nor watches → 403, no analysis run."""
        # Patch the price fetcher so that, *if* the guard failed to fire, the
        # endpoint would still return something analysable — proving the 403
        # comes from the guard, not from a data miss.
        with patch("services.data.fetcher.DataFetcher") as MockFetcher:
            inst = MockFetcher.return_value
            inst.get_price_history.return_value = MagicMock()
            r = client.get("/api/screener/canslim/TSLA")
        assert r.status_code == 403, r.data
        body = r.get_json()
        assert body["error"] == "ticker_not_in_user_scope"
        assert body["cta"] == "add_to_watchlist"
        # Guard must short-circuit BEFORE any upstream fetch.
        inst.get_price_history.assert_not_called()

    def test_canslim_allows_owned_ticker(self, client, auth_user, add_position):
        """A held ticker passes the guard and proceeds to scoring."""
        add_position(auth_user["id"], ticker="AAPL")
        # 404 "insufficient data" is fine — it proves we passed the guard and
        # reached the data-fetch stage. We assert it is NOT a 403 scope error.
        with patch("services.data.fetcher.DataFetcher") as MockFetcher:
            inst = MockFetcher.return_value
            inst.get_price_history.return_value = None  # → 404 insufficient
            r = client.get("/api/screener/canslim/AAPL")
        assert r.status_code != 403, r.data
        inst.get_price_history.assert_called()  # guard passed → fetch attempted

    def test_canslim_allows_watched_ticker(self, client, auth_user, app):
        """A watchlisted ticker passes the guard."""
        from extensions import db
        from models.watchlist import Watchlist
        with app.app_context():
            db.session.add(Watchlist(user_id=auth_user["id"], ticker="MSFT"))
            db.session.commit()
        with patch("services.data.fetcher.DataFetcher") as MockFetcher:
            inst = MockFetcher.return_value
            inst.get_price_history.return_value = None
            r = client.get("/api/screener/canslim/MSFT")
        assert r.status_code != 403, r.data
        inst.get_price_history.assert_called()

    def test_canslim_requires_auth(self, client):
        r = client.get("/api/screener/canslim/AAPL")
        assert r.status_code in (401, 403)


# --------------------------------------------------------------------------
# FIX 2 — /api/search URL encoding + length cap
# --------------------------------------------------------------------------
class TestSearchSafety:
    def _patch_fmp(self, captured):
        """Patch requests.get inside the search route, recording call kwargs."""
        def _fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = []
            return resp
        return _fake_get

    def test_search_uses_params_not_fstring(self, client, auth_user):
        """Query/key go through requests params= so they are URL-encoded."""
        captured = {}
        with patch.dict("os.environ", {"FMP_API_KEY": "testkey123"}), \
             patch("requests.get", side_effect=self._patch_fmp(captured)):
            r = client.get("/api/search?q=AAPL")
        assert r.status_code == 200
        # FMP must be called with params dict, not an interpolated URL.
        assert captured.get("params") == {
            "query": "AAPL", "limit": 10, "apikey": "testkey123"
        }
        # The raw URL must NOT carry the query/apikey inline.
        assert "?query=" not in (captured.get("url") or "")
        assert "apikey=" not in (captured.get("url") or "")

    def test_search_special_chars_not_injected(self, client, auth_user):
        """A query with & / = can't clobber FMP params (passed as a value)."""
        captured = {}
        with patch.dict("os.environ", {"FMP_API_KEY": "testkey123"}), \
             patch("requests.get", side_effect=self._patch_fmp(captured)):
            r = client.get("/api/search?q=x%26apikey%3Devil%26limit%3D9999")
        assert r.status_code == 200
        # The whole hostile string lands in the 'query' value verbatim — not
        # as separate apikey/limit params. apikey stays our real key.
        assert captured["params"]["apikey"] == "testkey123"
        assert captured["params"]["limit"] == 10
        assert "evil" not in str(captured["params"]["apikey"])
        # query holds the raw (decoded) string
        assert "apikey=evil" in captured["params"]["query"]

    def test_search_caps_query_length(self, client, auth_user):
        """Query > 50 chars is truncated before reaching FMP."""
        captured = {}
        long_q = "A" * 500
        with patch.dict("os.environ", {"FMP_API_KEY": "testkey123"}), \
             patch("requests.get", side_effect=self._patch_fmp(captured)):
            r = client.get(f"/api/search?q={long_q}")
        assert r.status_code == 200
        assert len(captured["params"]["query"]) == 50

    def test_search_empty_query_short_circuits(self, client, auth_user):
        r = client.get("/api/search?q=")
        assert r.status_code == 200
        assert r.get_json() == {"results": []}

    def test_search_requires_auth(self, client):
        r = client.get("/api/search?q=AAPL")
        assert r.status_code in (401, 403)
