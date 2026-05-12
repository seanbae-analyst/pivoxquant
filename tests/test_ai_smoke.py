"""Smoke tests for routes/ai.py — Claude-backed AI analysis surface.

Legal boundary: every payload passes through legal_filter.scrub_response.
We mock services.container.ai (Anthropic) so no real API calls fire.

Auth chain examples:
    /api/ai/status             — @api_auth (any tier)
    /api/ai/swot               — @api_auth + @require_tier("pro")
    /api/ai/chat               — @api_auth (any tier)
"""
from __future__ import annotations

from unittest.mock import patch


class TestAiStatusSmoke:
    def test_unauthenticated_status_returns_401(self, client):
        r = client.get("/api/ai/status")
        assert r.status_code == 401

    def test_status_authenticated(self, client, auth_user):
        # ai.available is a property derived from ANTHROPIC_API_KEY presence;
        # conftest scrubs that env var so it should be False, but assert shape.
        r = client.get("/api/ai/status")
        assert r.status_code == 200
        d = r.get_json()
        assert "available" in d
        assert isinstance(d["available"], bool)


class TestAiSwotSmoke:
    def test_unauthenticated_swot_returns_401(self, client):
        r = client.post("/api/ai/swot", json={"ticker": "AAPL"})
        assert r.status_code == 401

    def test_free_tier_blocked_by_require_tier(self, client, auth_user):
        # Free-tier default → 403 UPGRADE_REQUIRED before any AI call.
        r = client.post("/api/ai/swot", json={"ticker": "AAPL"})
        assert r.status_code == 403
        assert r.get_json().get("code") == "UPGRADE_REQUIRED"

    def test_swot_503_when_ai_unavailable(self, client, make_user):
        # Pro-tier user but ai.available is False (no API key in tests).
        u = make_user(email="pro@test.com", tier="pro")
        client.post("/api/auth/login",
                    json={"email": u["email"], "password": u["password"]})
        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = False
            r = client.post("/api/ai/swot", json={"ticker": "AAPL"})
        assert r.status_code == 503

    def test_swot_500_surfaces_last_error_detail(self, app, client, make_user):
        """Bug #14: a transient Anthropic failure caused an opaque 500.
        Route must now include ``detail`` (from ``ai.last_error``) so the
        operator sees the failing op + exception type without guessing.
        """
        u = make_user(email="pro2@test.com", tier="pro")
        # Allowlist AAPL so access_guard doesn't 403 us before generate_swot.
        from models import Watchlist
        from extensions import db
        with app.app_context():
            db.session.add(Watchlist(user_id=u["id"], ticker="AAPL"))
            db.session.commit()
        client.post("/api/auth/login",
                    json={"email": u["email"], "password": u["password"]})
        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_swot.return_value = None
            mock_ai.last_error = "swot: APIStatusError: rate limited"
            r = client.post("/api/ai/swot", json={"ticker": "AAPL"})
        # PR #229 (2026-05-10, B-08 graceful): transient AI failure returns
        # 503 with retry_after instead of 500.
        assert r.status_code == 503
        body = r.get_json()
        assert body.get("error") == "Failed to generate SWOT"
        assert body.get("detail") == "swot: APIStatusError: rate limited"
        assert body.get("retry_after") == 60

    def test_swot_500_no_detail_when_last_error_unset(self, app, client, make_user):
        """Backwards-compat: if `last_error` isn't set, the route must NOT
        include `detail` (avoid leaking ``None`` into the JSON body)."""
        u = make_user(email="pro3@test.com", tier="pro")
        from models import Watchlist
        from extensions import db
        with app.app_context():
            db.session.add(Watchlist(user_id=u["id"], ticker="AAPL"))
            db.session.commit()
        client.post("/api/auth/login",
                    json={"email": u["email"], "password": u["password"]})
        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_swot.return_value = None
            mock_ai.last_error = None
            r = client.post("/api/ai/swot", json={"ticker": "AAPL"})
        # PR #229 (2026-05-10, B-08 graceful): transient AI failure returns 503.
        assert r.status_code == 503
        body = r.get_json()
        assert body.get("error") == "Failed to generate SWOT"
        assert "detail" not in body
        assert body.get("retry_after") == 60


class TestAiChatSmoke:
    def test_unauthenticated_chat_returns_401(self, client):
        r = client.post("/api/ai/chat", json={"message": "hi"})
        assert r.status_code == 401
