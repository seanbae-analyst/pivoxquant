"""Tests for services.access_guard — §101 회피 화이트리스트 가드.

Verifies that:
1. Position-only tickers pass.
2. Watchlist-only tickers pass.
3. Tickers with neither return False (and the routes return 403).
4. Case-insensitive ticker matching.
5. Empty/invalid inputs fail closed.
6. /api/signals/<ticker> and /api/scan return 403 on out-of-scope tickers.
"""
from __future__ import annotations

import pytest

from services.access_guard import is_user_allowed_ticker, access_denied_response


# ── Unit tests for is_user_allowed_ticker ────────────────────────────────────

class TestIsUserAllowedTicker:
    def test_position_match(self, app, make_user, add_position):
        user = make_user()
        add_position(user["id"], ticker="AAPL", shares=10, avg_cost=150)
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "AAPL") is True

    def test_position_match_case_insensitive(self, app, make_user, add_position):
        user = make_user()
        add_position(user["id"], ticker="AAPL")
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "aapl") is True
            assert is_user_allowed_ticker(user["id"], "AaPl") is True

    def test_watchlist_match(self, app, make_user):
        from extensions import db
        from models import Watchlist
        user = make_user()
        with app.app_context():
            w = Watchlist(user_id=user["id"], ticker="MSFT")
            db.session.add(w)
            db.session.commit()
            assert is_user_allowed_ticker(user["id"], "MSFT") is True

    def test_neither_returns_false(self, app, make_user):
        user = make_user()
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "TSLA") is False

    def test_other_user_position_does_not_grant_access(self, app, make_user, add_position):
        owner = make_user(email="owner@test.com")
        intruder = make_user(email="intruder@test.com")
        add_position(owner["id"], ticker="NVDA")
        with app.app_context():
            assert is_user_allowed_ticker(owner["id"], "NVDA") is True
            assert is_user_allowed_ticker(intruder["id"], "NVDA") is False

    def test_empty_ticker_returns_false(self, app, make_user):
        user = make_user()
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "") is False
            assert is_user_allowed_ticker(user["id"], "   ") is False

    def test_none_ticker_returns_false(self, app, make_user):
        user = make_user()
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], None) is False

    def test_zero_user_id_returns_false(self, app):
        with app.app_context():
            assert is_user_allowed_ticker(0, "AAPL") is False
            assert is_user_allowed_ticker(None, "AAPL") is False


class TestAccessDeniedResponse:
    def test_returns_403_payload(self):
        body, status = access_denied_response()
        assert status == 403
        assert body["error"] == "ticker_not_in_user_scope"
        assert body["cta"] == "add_to_watchlist"
        assert "보유" in body["message"]


# ── Integration tests for guarded routes ─────────────────────────────────────

class TestSignalsRouteGuard:
    def test_signal_detail_403_for_out_of_scope(self, client, auth_user):
        # User has no positions / watchlist for TSLA.
        resp = client.get("/api/signals/TSLA")
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "ticker_not_in_user_scope"

    def test_signal_detail_passes_guard_with_position(
        self, client, auth_user, add_position, monkeypatch,
    ):
        add_position(auth_user["id"], ticker="AAPL")
        # engine.analyze can be slow / external — short-circuit it.
        from routes import signals as signals_route
        monkeypatch.setattr(
            signals_route.engine, "analyze",
            lambda *a, **kw: {"ticker": "AAPL", "signal": "NEUTRAL", "name": "Apple"},
        )
        resp = client.get("/api/signals/AAPL")
        # Past the guard — depending on engine may be 200 / 404 / etc.
        assert resp.status_code != 403

    def test_scan_403_for_out_of_scope(self, client, auth_user):
        resp = client.post("/api/scan", json={"ticker": "TSLA"})
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "ticker_not_in_user_scope"

    def test_scan_passes_guard_with_watchlist(
        self, app, client, auth_user, monkeypatch,
    ):
        from extensions import db
        from models import Watchlist
        with app.app_context():
            db.session.add(Watchlist(user_id=auth_user["id"], ticker="MSFT"))
            db.session.commit()

        from routes import signals as signals_route
        monkeypatch.setattr(
            signals_route.engine, "analyze",
            lambda *a, **kw: {"ticker": "MSFT", "signal": "NEUTRAL", "name": "Microsoft"},
        )
        resp = client.post("/api/scan", json={"ticker": "MSFT"})
        assert resp.status_code != 403


class TestDiscoverRouteFilter:
    def test_discover_filters_to_owned_and_watched_only(
        self, app, client, auth_user, add_position, monkeypatch,
    ):
        from extensions import db
        from models import Watchlist
        add_position(auth_user["id"], ticker="AAPL")
        with app.app_context():
            db.session.add(Watchlist(user_id=auth_user["id"], ticker="MSFT"))
            db.session.commit()

        # Stub engine to return a result for every ticker passed in.
        from routes import discover as discover_route
        monkeypatch.setattr(
            discover_route.engine, "DISCOVER_POOL",
            ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL"],
        )
        monkeypatch.setattr(
            discover_route.engine, "analyze",
            lambda t, *a, **kw: {"ticker": t, "signal": "NEUTRAL", "priority": 1, "name": t},
        )
        # Bust user-level discover cache so this test sees fresh results.
        from services import cache_service
        cache_service.discover_cache.pop(auth_user["id"], None)

        resp = client.get("/api/discover?force=1")
        assert resp.status_code == 200
        tickers = {r["ticker"] for r in resp.get_json()["results"]}
        assert tickers == {"AAPL", "MSFT"}
        # Tickers outside user scope must be filtered out.
        assert "TSLA" not in tickers
        assert "NVDA" not in tickers
        assert "GOOGL" not in tickers

    def test_discover_includes_owned_tickers_not_in_curated_pool(
        self, app, client, auth_user, add_position, monkeypatch,
    ):
        """Regression for HANDOVER v19 P1 #7 — KR mid-caps that the user
        actually owns (e.g. 010170.KQ Taihan, 124500.KQ IT Sengle) were
        filtered out by the previous DISCOVER_POOL ∩ allowed intersection.
        After 2026-05-02 the pool is keyed off user demand directly, so
        any owned/watched ticker is analysed regardless of whether it's
        in engine.DISCOVER_POOL."""
        from extensions import db
        from models import Watchlist
        add_position(auth_user["id"], ticker="010170.KQ")
        with app.app_context():
            db.session.add(Watchlist(user_id=auth_user["id"], ticker="124500.KQ"))
            db.session.commit()

        from routes import discover as discover_route
        # DISCOVER_POOL deliberately does NOT contain either KR ticker.
        monkeypatch.setattr(
            discover_route.engine, "DISCOVER_POOL",
            ["AAPL", "MSFT", "NVDA"],
        )
        monkeypatch.setattr(
            discover_route.engine, "analyze",
            lambda t, *a, **kw: {"ticker": t, "signal": "NEUTRAL", "priority": 1, "name": t},
        )
        from services import cache_service
        cache_service.discover_cache.pop(auth_user["id"], None)

        resp = client.get("/api/discover?force=1")
        assert resp.status_code == 200
        tickers = {r["ticker"] for r in resp.get_json()["results"]}
        # Both owned + watched return analysis even though neither is in
        # DISCOVER_POOL — the §101 boundary moved from "curated pool" to
        # "user-demand pool".
        assert "010170.KQ" in tickers
        assert "124500.KQ" in tickers
