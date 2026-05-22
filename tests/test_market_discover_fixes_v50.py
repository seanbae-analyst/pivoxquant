"""tests/test_market_discover_fixes_v50.py — three lead-confirmed fixes.

Covers (autonomous v50 session):

  FIX 1 (discover sectors): d5/m1 are emitted as None (not fabricated from
         d1 × multiplier); d1 (the only real datum the fetcher provides) is
         preserved.
  FIX 2 (news route): /api/news/<ticker> is wrapped with @legal_scrub_response,
         so advisory language in mocked news titles is neutralized in the body.
  FIX 3 (per-ticker earnings): GET /api/earnings/<ticker> returns earnings for
         a ticker the user holds OR watches, and 403s for a ticker outside the
         user's §101 scope.

All upstream data layers (fetcher / FMP) are mocked.
"""
from __future__ import annotations

from unittest.mock import patch


# ---------------------------------------------------------------------------
# FIX 1 — discover sectors no longer fabricates 5D / 1M returns
# ---------------------------------------------------------------------------
class TestDiscoverSectorsNoFabrication:
    def test_d5_m1_null_d1_preserved(self, client, auth_user):
        """d1 is real (from fetcher 1-day perf); d5/m1 must be None, not a
        scaled multiple of d1 (no fake multi-period numbers)."""
        from services import cache_service
        cache_service.discover_section_cache_clear()

        live = [
            {"sector": "Technology", "changesPercentage": "1.50%"},
            {"sector": "Energy", "changesPercentage": "-0.80%"},
            {"sector": "Financials", "changesPercentage": "0.40%"},
            {"sector": "Healthcare", "changesPercentage": "0.90%"},
            {"sector": "Utilities", "changesPercentage": "0.20%"},
            {"sector": "Industrials", "changesPercentage": "0.60%"},
        ]
        with patch("routes.discover.fetcher") as mock_fetcher:
            mock_fetcher.get_sector_performance.return_value = live
            r = client.get("/api/discover/sectors")

        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        # Fresh envelope passes a list payload through unchanged; a stale
        # envelope would nest it under a list key ("sectors").
        if isinstance(body, list):
            rows = body
        else:
            rows = body.get("sectors") or body.get("data") or []
        assert isinstance(rows, list) and len(rows) >= 5

        tech = next(row for row in rows if row["sector"] == "Technology")
        # d1 = real, preserved exactly.
        assert tech["d1"] == 1.50
        # d5 / m1 = explicitly null (not 1.50*2.5 / 1.50*5.0).
        assert tech["d5"] is None
        assert tech["m1"] is None

        # No row may carry a fabricated d5/m1 anywhere.
        for row in rows:
            assert row["d5"] is None
            assert row["m1"] is None


# ---------------------------------------------------------------------------
# FIX 2 — /api/news/<ticker> is legal-scrubbed
# ---------------------------------------------------------------------------
class TestNewsRouteLegalScrub:
    def test_advisory_language_in_news_is_scrubbed(self, client, auth_user):
        """A mocked news title containing advisory language must come back
        neutralized (the @legal_scrub_response decorator deep-scrubs the body)."""
        fake_news = [
            {"title": "애널리스트 매수 추천", "summary": "BUY signal flagged by desk"},
            {"title": "We recommend buying soon", "summary": "neutral coverage"},
        ]
        with patch("routes.market.fetcher") as mock_fetcher:
            mock_fetcher.get_news.return_value = fake_news
            r = client.get("/api/news/AAPL")

        assert r.status_code == 200, r.get_json()
        items = r.get_json()["news"]
        blob = " ".join(
            f"{it.get('title','')} {it.get('summary','')}" for it in items
        )
        # Advisory tokens must be neutralized by safe_scrub.
        assert "추천" not in blob          # 매수 추천 → 정보 고지 …
        assert "매수" not in blob
        assert "BUY signal" not in blob    # BUY → POSITIVE
        assert "recommend" not in blob     # recommend → note
        # Confirm neutralized replacements are present (not just deleted).
        assert "POSITIVE" in blob


# ---------------------------------------------------------------------------
# FIX 3 — per-ticker earnings endpoint with §101 access gate
# ---------------------------------------------------------------------------
class TestEarningsPerTicker:
    def _mock_cal(self):
        return [{"date": "2026-07-30"}]

    def test_allowed_ticker_in_holdings_returns_data(self, client, auth_user,
                                                     add_position):
        """Ticker in the user's Position holdings → 200 with an item shaped
        like the /api/earnings list entries."""
        add_position(auth_user["id"], ticker="AAPL")
        with patch("services.data.fmp.get_earnings_calendar",
                   return_value=self._mock_cal()):
            r = client.get("/api/earnings/AAPL")

        assert r.status_code == 200, r.get_json()
        item = r.get_json()["earnings"]
        assert item is not None
        assert item["ticker"] == "AAPL"
        assert item["date"] == "2026-07-30"
        # Same shape as the list-endpoint items.
        for key in ("ticker", "name", "date", "signal", "score"):
            assert key in item

    def test_allowed_ticker_in_watchlist_returns_data(self, client, auth_user, app):
        """Ticker in the user's Watchlist (not held) → 200 (still in scope)."""
        from extensions import db
        from models import Watchlist
        with app.app_context():
            db.session.add(Watchlist(user_id=auth_user["id"], ticker="MSFT"))
            db.session.commit()

        with patch("services.data.fmp.get_earnings_calendar",
                   return_value=self._mock_cal()):
            r = client.get("/api/earnings/MSFT")

        assert r.status_code == 200, r.get_json()
        assert r.get_json()["earnings"]["ticker"] == "MSFT"

    def test_disallowed_ticker_403(self, client, auth_user):
        """Ticker the user neither holds nor watches → 403 (§101 isolation).
        FMP must NOT be consulted for an out-of-scope ticker."""
        with patch("services.data.fmp.get_earnings_calendar") as mock_cal:
            r = client.get("/api/earnings/NVDA")
            assert r.status_code == 403, r.get_json()
            mock_cal.assert_not_called()
        body = r.get_json()
        assert body["error"] == "ticker_not_in_user_scope"

    def test_per_ticker_unauthenticated_401(self, client):
        r = client.get("/api/earnings/AAPL")
        assert r.status_code == 401
