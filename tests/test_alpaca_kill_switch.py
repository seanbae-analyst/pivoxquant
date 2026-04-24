"""PivoxQuant — Alpaca kill-switch route tests.

Guards the 2026-04-24 legal-risk mitigation: Alpaca broker endpoints MUST
return 503 when ``ALPACA_ENABLED`` is off (the default). Legacy users who
previously connected an Alpaca account are preserved in the DB but cannot
call any Alpaca-gated endpoint until the kill switch is flipped.

These tests assert the following contract:

  1. With ``ALPACA_ENABLED=0`` (default), authenticated requests to every
     Alpaca endpoint return HTTP 503 with code="ALPACA_DISABLED".
  2. Unauthenticated requests still 401 (decorator order — auth first).
  3. ``GET /api/broker/connections`` returns ``alpaca_disabled=True`` and
     ``alpaca_connected=False`` even when a legacy DB row exists.
  4. With ``ALPACA_ENABLED=1``, the kill-switch short-circuit is bypassed
     (endpoints still require auth + valid credentials but no longer 503
     from the switch itself).

Network is not touched: we stop at the kill-switch return path. Tests that
need a valid Alpaca SDK call are covered separately in
``test_alpaca_market_adapter.py``.
"""
from __future__ import annotations

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────────────

ALPACA_ENDPOINTS = [
    ("POST",   "/api/broker/alpaca/connect",    {}),
    ("POST",   "/api/broker/alpaca/sync",       None),
    ("DELETE", "/api/broker/alpaca/disconnect", None),
    ("GET",    "/api/broker/alpaca/status",     None),
]


def _call(client, method: str, url: str, body):
    if method == "GET":
        return client.get(url)
    if method == "POST":
        return client.post(url, json=(body or {}))
    if method == "DELETE":
        return client.delete(url)
    raise AssertionError(f"unsupported method: {method}")


# ─── 1. Kill switch ON (default) — every Alpaca endpoint returns 503 ─────────

class TestKillSwitchDefault:
    """ALPACA_ENABLED defaults to 0 → every endpoint must 503."""

    @pytest.mark.parametrize("method,url,body", ALPACA_ENDPOINTS)
    def test_endpoint_returns_503(self, app, client, auth_user, method, url, body):
        # Safety: explicitly assert the default is disabled in the Flask config
        # we built for tests (config.py reads os.environ at import time).
        assert app.config.get("ALPACA_ENABLED") is False, (
            "Test app loaded with ALPACA_ENABLED=True — the default must be "
            "False. Check config.py or conftest.py env setup."
        )

        resp = _call(client, method, url, body)
        assert resp.status_code == 503, (
            f"{method} {url} expected 503, got {resp.status_code}: {resp.data!r}"
        )
        payload = resp.get_json() or {}
        assert payload.get("error") == "alpaca-disabled"
        assert payload.get("code") == "ALPACA_DISABLED"
        # User-facing message must name KIS as the supported broker.
        assert "KIS" in (payload.get("message") or "")


# ─── 2. Unauthenticated → 401, NOT 503 ───────────────────────────────────────

class TestUnauthenticatedStillAuthGated:
    """The @api_auth decorator runs before the kill-switch check, so a
    probe from an unauthenticated client must still get 401 (never 503).
    """

    @pytest.mark.parametrize("method,url,body", ALPACA_ENDPOINTS)
    def test_unauth_401(self, client, method, url, body):
        resp = _call(client, method, url, body)
        assert resp.status_code == 401, (
            f"{method} {url} unauth expected 401, got {resp.status_code}"
        )


# ─── 3. /api/broker/connections surface ──────────────────────────────────────

class TestConnectionsSummary:
    """The connections summary endpoint is NOT gated (it has to load for
    every dashboard visit), but it must reflect the kill switch by
    reporting alpaca_connected=False + alpaca_disabled=True.
    """

    def test_alpaca_disabled_flag_exposed(self, client, auth_user):
        resp = client.get("/api/broker/connections")
        assert resp.status_code == 200, resp.data
        payload = resp.get_json() or {}
        # Schema contract: keys always present, boolean types.
        for key in (
            "kis_connected",
            "alpaca_connected",
            "alpaca_last_sync",
            "alpaca_mode",
            "alpaca_disabled",
        ):
            assert key in payload, f"missing key {key}: {payload}"
        # With kill switch default ON, Alpaca is never surfaced as connected.
        assert payload["alpaca_connected"] is False
        assert payload["alpaca_disabled"] is True
        assert payload["alpaca_mode"] == "paper"

    def test_legacy_alpaca_row_is_not_surfaced(
        self, app, client, auth_user
    ):
        """Even if a legacy `broker='alpaca'` row exists in the DB, the
        kill switch must force alpaca_connected=False so the UI hides it.
        """
        from models.broker_connection import BrokerConnection
        from extensions import db

        # Manual push/pop avoids the "popped wrong app context" assertion
        # that surfaces when `db_session` fixture's `with` context collides
        # with the test_client request context stack during teardown.
        ctx = app.app_context()
        ctx.push()
        try:
            legacy = BrokerConnection(
                user_id=auth_user["id"],
                broker="alpaca",
                is_active=True,
                is_paper=True,
                encrypted_app_key="FAKE_ENCRYPTED_KEY",
                encrypted_app_secret="FAKE_ENCRYPTED_SECRET",
            )
            db.session.add(legacy)
            db.session.commit()
            db.session.close()
        finally:
            ctx.pop()

        resp = client.get("/api/broker/connections")
        assert resp.status_code == 200
        payload = resp.get_json() or {}
        assert payload["alpaca_connected"] is False
        assert payload["alpaca_disabled"] is True


# ─── 4. Kill switch OFF (opt-in) — endpoints no longer 503 from switch ───────

class TestKillSwitchOptIn:
    """With ALPACA_ENABLED=True, the kill switch is bypassed. Endpoints
    still enforce auth, body validation, and real credential verification —
    but they must NOT short-circuit with 503/ALPACA_DISABLED.
    """

    @pytest.fixture
    def alpaca_enabled(self, app):
        """Flip the Flask app config to simulate ALPACA_ENABLED=1."""
        prev = app.config.get("ALPACA_ENABLED")
        app.config["ALPACA_ENABLED"] = True
        yield
        app.config["ALPACA_ENABLED"] = prev

    def test_connect_no_longer_503(self, client, auth_user, alpaca_enabled):
        # Empty body → the validator rejects with 400 (INVALID_*) instead
        # of the kill-switch 503. That's the key contract: 503 is gone.
        resp = client.post("/api/broker/alpaca/connect", json={})
        assert resp.status_code != 503, (
            f"Kill switch still active with ALPACA_ENABLED=True: {resp.data!r}"
        )
        # Expected: validation 400 because body lacks key_id/secret_key.
        assert resp.status_code in (400, 401)

    def test_status_no_longer_503(self, client, auth_user, alpaca_enabled):
        resp = client.get("/api/broker/alpaca/status")
        assert resp.status_code != 503
        # No legacy row → "connected": False with 200.
        assert resp.status_code == 200
        payload = resp.get_json() or {}
        assert payload.get("connected") is False

    def test_connections_summary_alpaca_disabled_flag_is_false(
        self, client, auth_user, alpaca_enabled
    ):
        resp = client.get("/api/broker/connections")
        assert resp.status_code == 200
        payload = resp.get_json() or {}
        # Now that the switch is on, the flag flips.
        assert payload["alpaca_disabled"] is False
