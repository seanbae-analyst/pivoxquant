"""
tests/test_autotrade_csrf.py — CSRF & ownership guards for AutoTrader routes
=============================================================================

H6 (2026-04-24): verify that every state-changing /api/autotrade/* endpoint
is protected by the double-submit-cookie CSRF middleware. A missing or
mismatched X-CSRF-Token header must yield 403 — NOT a 200 that actually
mutates the global `trader` singleton.

C1 (2026-04-24): additionally verify ownership guards — once User A has
claimed the trader via /start, concurrent calls from User B must be
rejected (403/409), not silently attributed to A's DB rows.

Conventions
-----------
- `raw_client` — plain Flask test client without the CSRF helper wrapper.
- `client`     — CSRF-aware wrapper (normal request path).

Both fixtures come from tests/conftest.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────

def _login(raw_client, email: str, password: str) -> None:
    resp = raw_client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"login failed: {resp.data!r}"


@pytest.fixture(autouse=True)
def _init_trader(app):
    """Ensure the global AutoTrader singleton is initialised + reset between tests.

    The test app factory (tests/conftest.py) does NOT call
    `services.container.init_trader()` by default, but the /api/autotrade
    routes depend on `services.container.trader` being non-None. We
    initialise it once (idempotent) and roll back its mutable state
    between tests.
    """
    from services import container
    from extensions import db
    from models import Position, TradeHistory

    if container.trader is None:
        with app.app_context():
            container.init_trader(db, Position, TradeHistory, app)

    _t = container.trader
    prev_user = getattr(_t, "_user_id", None)
    prev_running = getattr(_t, "running", False)
    prev_available = getattr(_t, "available", False)
    _t._user_id = None
    _t.running = False
    yield
    _t._user_id = prev_user
    _t.running = prev_running
    _t.available = prev_available


# ═══════════════════════════════════════════════════════════════════════════
# H6 — CSRF enforcement on every mutating autotrade endpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestAutotradeCSRF:
    """Each POST on /api/autotrade/* must be CSRF-protected."""

    def test_start_without_csrf_returns_403(self, raw_client, make_user):
        u = make_user(email="at1@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.post("/api/autotrade/start")
        assert r.status_code == 403, f"CSRF must block /start: {r.data!r}"
        body = r.get_json() or {}
        assert body.get("code") in ("CSRF_MISSING", "CSRF_MISMATCH")

    def test_stop_without_csrf_returns_403(self, raw_client, make_user):
        u = make_user(email="at2@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.post("/api/autotrade/stop")
        assert r.status_code == 403
        assert r.get_json().get("code") in ("CSRF_MISSING", "CSRF_MISMATCH")

    def test_sell_all_without_csrf_returns_403(self, raw_client, make_user):
        u = make_user(email="at3@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.post("/api/autotrade/sell-all")
        assert r.status_code == 403

    def test_emergency_halt_without_csrf_returns_403(self, raw_client, make_user):
        u = make_user(email="at4@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.post("/api/autotrade/emergency-halt")
        assert r.status_code == 403

    def test_approve_without_csrf_returns_403(self, raw_client, make_user):
        u = make_user(email="at5@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.post("/api/autotrade/approve/some_id")
        assert r.status_code == 403

    def test_reject_without_csrf_returns_403(self, raw_client, make_user):
        u = make_user(email="at6@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.post("/api/autotrade/reject/some_id")
        assert r.status_code == 403

    def test_csrf_token_mismatch_returns_403(self, raw_client, make_user):
        """Sending a header token that doesn't match the cookie must 403."""
        u = make_user(email="at7@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        # Inject a forged header that doesn't match the cookie.
        r = raw_client.post(
            "/api/autotrade/start",
            headers={"X-CSRF-Token": "not.the.real.token"},
        )
        assert r.status_code == 403
        assert r.get_json().get("code") in ("CSRF_MISSING", "CSRF_MISMATCH", "CSRF_INVALID")

    def test_status_bypasses_csrf_read_only(self, raw_client, make_user):
        """GET /status is read-only and must NOT require a CSRF token."""
        u = make_user(email="at8@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.get("/api/autotrade/status")
        # Either 200 (normal) or 503 (trader not initialised in test mode) —
        # must never be 403.
        assert r.status_code != 403

    def test_pending_bypasses_csrf_read_only(self, raw_client, make_user):
        """GET /pending is read-only."""
        u = make_user(email="at9@test.com", password="goodpass")
        _login(raw_client, u["email"], u["password"])
        r = raw_client.get("/api/autotrade/pending")
        assert r.status_code != 403


# ═══════════════════════════════════════════════════════════════════════════
# C1 — Cross-user ownership enforcement
# ═══════════════════════════════════════════════════════════════════════════

class TestAutotradeOwnership:
    """Once user A claims the trader, user B must not manipulate it."""

    def test_claim_then_other_user_cannot_stop(self, client, make_user):
        """User A /start → User B /stop must be rejected."""
        # Build user A with CSRF-aware client.
        ua = make_user(email="owner_a@test.com", password="goodpass")
        # Log in A and try to claim.
        client.post("/api/auth/login", json={
            "email": ua["email"], "password": ua["password"],
        })

        # Force the trader's _user_id as if A had successfully claimed it
        # and the trader is running. We bypass AutoTrader.start() because
        # in the test env the real broker is unavailable.
        from services.container import trader
        # Save + install fake state.
        trader._user_id = ua["id"]
        trader.running = True
        trader.available = True
        # Stub methods to avoid hitting real broker.
        trader.stop = MagicMock(return_value={"ok": True, "status": "stopped"})
        trader.force_sell_all = MagicMock(return_value={"results": []})
        trader.force_sell_all_kr = MagicMock(return_value=[])
        trader.emergency_halt = MagicMock(
            return_value={"ok": True, "halted_until": "2099-01-01T00:00:00", "positions_closed": 0, "results": []}
        )
        trader.approve_trade = MagicMock(return_value={"ok": True})
        trader.reject_trade = MagicMock(return_value={"ok": True})

        # Log out A, log in B.
        client.post("/api/auth/logout")
        ub = make_user(email="intruder_b@test.com", password="goodpass")
        client.post("/api/auth/login", json={
            "email": ub["email"], "password": ub["password"],
        })

        # Each of these must return 409 TRADER_BUSY, not silently run.
        for path in (
            "/api/autotrade/stop",
            "/api/autotrade/sell-all",
            "/api/autotrade/emergency-halt",
            "/api/autotrade/approve/fake_id",
            "/api/autotrade/reject/fake_id",
        ):
            r = client.post(path)
            assert r.status_code == 409, (
                f"{path} should reject foreign user: got {r.status_code} {r.data!r}"
            )
            body = r.get_json() or {}
            assert body.get("code") == "TRADER_BUSY"

        # And B must NOT have caused any of the stubbed methods to run.
        trader.stop.assert_not_called()
        trader.force_sell_all.assert_not_called()
        trader.force_sell_all_kr.assert_not_called()
        trader.emergency_halt.assert_not_called()
        trader.approve_trade.assert_not_called()
        trader.reject_trade.assert_not_called()

    def test_start_does_not_leak_user_id_when_busy(self, client, make_user):
        """If A owns a running trader, B's /start must not overwrite _user_id.

        Pre-fix behaviour: `trader._user_id = current_user.id` happened BEFORE
        the "already running" check, so B's id would leak onto A's running
        session. Post-fix: the claim is atomic and rejects foreign users.
        """
        ua = make_user(email="owner2@test.com", password="goodpass")
        ub = make_user(email="intruder2@test.com", password="goodpass")

        from services.container import trader
        trader._user_id = ua["id"]
        trader.running = True
        trader.available = True

        # Log in as B and try to start.
        client.post("/api/auth/login", json={
            "email": ub["email"], "password": ub["password"],
        })
        r = client.post("/api/autotrade/start")
        # The request is rejected with 409, and most importantly the user_id
        # on the singleton must still be A (never B).
        assert r.status_code == 409
        assert trader._user_id == ua["id"], (
            f"CRITICAL: trader._user_id leaked — expected {ua['id']}, "
            f"got {trader._user_id}. This is the C1 regression."
        )

    def test_pending_returns_empty_for_foreign_user(self, client, make_user):
        """B must not see A's pending trades."""
        ua = make_user(email="owner3@test.com", password="goodpass")
        ub = make_user(email="intruder3@test.com", password="goodpass")

        from services.container import trader
        trader._user_id = ua["id"]
        trader.running = True
        trader.available = True
        trader.get_pending_trades = MagicMock(return_value=[
            {"id": "secret_1", "ticker": "AAPL", "action": "BUY",
             "shares": 10, "price": 100.0, "score": 80, "signal": "POSITIVE",
             "reason": "test", "proposed_at": 0, "status": "PENDING",
             "expires_at": 9e12},
        ])

        client.post("/api/auth/login", json={
            "email": ub["email"], "password": ub["password"],
        })
        r = client.get("/api/autotrade/pending")
        assert r.status_code == 200
        body = r.get_json() or {}
        assert body.get("pending") == [], (
            f"User B must not see User A's pending trades: {body!r}"
        )
