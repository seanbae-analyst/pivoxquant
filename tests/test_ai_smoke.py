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


class TestAiChatSmoke:
    def test_unauthenticated_chat_returns_401(self, client):
        r = client.post("/api/ai/chat", json={"message": "hi"})
        assert r.status_code == 401
