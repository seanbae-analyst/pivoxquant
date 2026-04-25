# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""tests/test_agent_route.py — /api/agent/{query,status}

Covers the Closed-Beta auth / entitlement / feature-flag ladder without
hitting the real Anthropic API (the JournalCompanion's ``_invoke_llm``
is patched to a stub so tests stay offline and fast).

Guarantees exercised:
  - Feature flag OFF     → 503 regardless of auth
  - Not authenticated    → 401
  - Not entitled (free)  → 403
  - Premium + flag ON    → 200
  - Per-user rate limit  → 429 on the second request inside the window
  - Empty / oversized message input handling
  - /status is unauth-safe
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def _mock_companion_query():
    """Patch JournalCompanion.query to return a canned success response.

    Skips the Anthropic HTTP call + legal gate; the T5/gate behavior is
    already covered by test_journal_companion_gate.py.
    """
    from datetime import datetime, timezone

    from services.agents.journal_companion import AgentResponse

    fake = AgentResponse(
        text="(mocked companion response)",
        gate_verdict="pass",
        gate_reason="",
        model="mock-haiku",
        request_id="mock12345678",
        generated_at=datetime.now(timezone.utc),
    )

    with patch(
        "services.agents.journal_companion.JournalCompanion.query",
        return_value=fake,
    ) as m:
        yield m


@pytest.fixture
def _flag_on(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "1")
    yield


@pytest.fixture
def _flag_off(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "0")
    yield


@pytest.fixture
def _reset_agent_rate_limit():
    """Clear the in-memory rate-limit map between tests."""
    from routes import agent as agent_route

    agent_route._last_request.clear()
    yield
    agent_route._last_request.clear()


@pytest.fixture
def _kill_switch_off():
    """Force the agent kill switch to report OFF for the test duration.

    Uses the cache entry directly — the route reads through the
    ``is_agent_killed`` helper, and patching its cache is cheaper than
    mocking the DB round-trip.
    """
    from routes import agent_admin

    # Prime cache: killed=False, expires far in the future.
    agent_admin._KILL_CACHE["killed"] = False
    agent_admin._KILL_CACHE["expires_at"] = 1e18
    yield
    agent_admin._invalidate_kill_cache()


def _make_premium_user(make_user, tier: str = "premium_plus"):
    """Fixture helper — make_user only sets ``subscription_tier``."""
    return make_user(
        email=f"premium+{tier}@test.com",
        password="secretpass",
        tier=tier,
    )


def _login(client, email: str, password: str):
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.data
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# /api/agent/status — public
# ─────────────────────────────────────────────────────────────────────────────


class TestStatus:
    def test_status_unauthenticated_returns_200(self, client, _flag_off):
        r = client.get("/api/agent/status")
        assert r.status_code == 200
        data = r.get_json()
        assert data["enabled"] is False
        assert data["phase"] == "off"
        assert "entitlement_plans" in data

    def test_status_reflects_flag_on(self, client, _flag_on):
        r = client.get("/api/agent/status")
        assert r.status_code == 200
        data = r.get_json()
        assert data["enabled"] is True
        assert data["phase"] == "closed-beta"


# ─────────────────────────────────────────────────────────────────────────────
# /api/agent/query — feature flag + auth + entitlement ladder
# ─────────────────────────────────────────────────────────────────────────────


class TestQueryGate:
    def test_unauthenticated_when_flag_on_returns_401(
        self, client, _flag_on, _kill_switch_off
    ):
        r = client.post("/api/agent/query", json={"message": "hi"})
        assert r.status_code == 401

    def test_free_tier_user_returns_403(
        self,
        client,
        make_user,
        _flag_on,
        _kill_switch_off,
        _reset_agent_rate_limit,
    ):
        u = make_user(email="free@test.com", password="xxxxxxxx", tier="free")
        _login(client, u["email"], u["password"])
        r = client.post("/api/agent/query", json={"message": "hi"})
        assert r.status_code == 403
        assert r.get_json()["error"] == "not-entitled"

    def test_premium_plus_with_flag_off_returns_503(
        self, client, make_user, _flag_off, _kill_switch_off
    ):
        u = _make_premium_user(make_user)
        _login(client, u["email"], u["password"])
        r = client.post("/api/agent/query", json={"message": "hi"})
        assert r.status_code == 503
        assert r.get_json()["error"] == "agent-disabled"

    def test_premium_plus_with_flag_on_returns_200(
        self,
        client,
        make_user,
        _flag_on,
        _kill_switch_off,
        _mock_companion_query,
        _reset_agent_rate_limit,
    ):
        u = _make_premium_user(make_user)
        _login(client, u["email"], u["password"])
        r = client.post(
            "/api/agent/query",
            json={"message": "오늘 매매 기록 어떻게 되어 있었지?"},
        )
        assert r.status_code == 200, r.data
        data = r.get_json()
        assert data["text"] == "(mocked companion response)"
        assert data["gate_verdict"] == "pass"
        # Disclaimer mandatory on every response.
        assert "자본시장법" in data.get("disclaimer", "")


# ─────────────────────────────────────────────────────────────────────────────
# Input validation
# ─────────────────────────────────────────────────────────────────────────────


class TestQueryInput:
    def test_missing_message_returns_400(
        self,
        client,
        make_user,
        _flag_on,
        _kill_switch_off,
        _reset_agent_rate_limit,
    ):
        u = _make_premium_user(make_user, tier="founding_lifetime")
        _login(client, u["email"], u["password"])
        r = client.post("/api/agent/query", json={})
        assert r.status_code == 400

    def test_empty_message_returns_400(
        self,
        client,
        make_user,
        _flag_on,
        _kill_switch_off,
        _reset_agent_rate_limit,
    ):
        u = _make_premium_user(make_user)
        _login(client, u["email"], u["password"])
        r = client.post("/api/agent/query", json={"message": "   "})
        assert r.status_code == 400

    def test_oversized_message_passes_to_companion(
        self,
        client,
        make_user,
        _flag_on,
        _kill_switch_off,
        _mock_companion_query,
        _reset_agent_rate_limit,
    ):
        """Route itself does not cap length — the companion's T5 handler
        refuses messages > 2000 chars. Either a 200 (mocked pass-through)
        or a 400 is acceptable; we just verify we don't 500."""
        u = _make_premium_user(make_user)
        _login(client, u["email"], u["password"])
        r = client.post(
            "/api/agent/query", json={"message": "x" * 5000}
        )
        assert r.status_code in (200, 400)


# ─────────────────────────────────────────────────────────────────────────────
# Rate limit
# ─────────────────────────────────────────────────────────────────────────────


class TestQueryRateLimit:
    def test_second_request_within_window_returns_429(
        self,
        client,
        make_user,
        _flag_on,
        _kill_switch_off,
        _mock_companion_query,
        _reset_agent_rate_limit,
    ):
        u = _make_premium_user(make_user)
        _login(client, u["email"], u["password"])
        r1 = client.post("/api/agent/query", json={"message": "first"})
        assert r1.status_code == 200
        r2 = client.post("/api/agent/query", json={"message": "second"})
        assert r2.status_code == 429
        body = r2.get_json()
        assert body["error"] == "rate-limited"
        assert body["retry_after_sec"] > 0
