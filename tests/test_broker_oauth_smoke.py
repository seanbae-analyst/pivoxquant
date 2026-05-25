"""Smoke tests for routes/broker_oauth.py — KIS + Alpaca connection mgmt.

External APIs (KIS token mint, Alpaca paper-account ping) are mocked.
No real broker network calls.
"""
from __future__ import annotations

from unittest.mock import patch


class TestKisStatusSmoke:
    def test_unauthenticated_status_returns_401(self, client):
        r = client.get("/api/broker/kis/status")
        assert r.status_code == 401

    def test_status_when_no_connection(self, client, auth_user):
        r = client.get("/api/broker/kis/status")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["connected"] is False


class TestKisConnectSmoke:
    def test_unauthenticated_connect_returns_401(self, client):
        r = client.post("/api/broker/kis/connect", json={})
        assert r.status_code == 401

    def test_connect_400_on_empty_payload(self, client, auth_user):
        r = client.post("/api/broker/kis/connect", json={})
        assert r.status_code == 400


class TestKisDisconnectSmoke:
    def test_unauthenticated_disconnect_returns_401(self, client):
        r = client.delete("/api/broker/kis/disconnect")
        assert r.status_code == 401

    def test_disconnect_when_no_connection_returns_404(self, client, auth_user):
        r = client.delete("/api/broker/kis/disconnect")
        assert r.status_code == 404


class TestKisSyncSmoke:
    def test_unauthenticated_sync_returns_401(self, client):
        r = client.post("/api/broker/kis/sync", json={})
        assert r.status_code == 401


class TestBrokerConnectionsSummarySmoke:
    def test_unauthenticated_connections_returns_401(self, client):
        r = client.get("/api/broker/connections")
        assert r.status_code == 401

    def test_connections_summary_default(self, client, auth_user):
        r = client.get("/api/broker/connections")
        assert r.status_code == 200
        d = r.get_json()
        # Stable schema — UI relies on keys being present even when nothing connected.
        assert "kis_connected" in d
        assert "alpaca_connected" in d


class TestAlpacaSurfaceSmoke:
    def test_unauthenticated_alpaca_status_returns_401(self, client):
        r = client.get("/api/broker/alpaca/status")
        assert r.status_code == 401

    def test_unauthenticated_alpaca_connect_returns_401(self, client):
        r = client.post("/api/broker/alpaca/connect", json={})
        assert r.status_code == 401

    def test_unauthenticated_alpaca_disconnect_returns_401(self, client):
        r = client.delete("/api/broker/alpaca/disconnect")
        assert r.status_code == 401


# ── Wave 10 (QA gap fill) — KIS account_no boundary rejection ──────────────
# 2026-05-17: PR #416 tightened the backend regex from \d{6,12} to \d{8} to
# match the frontend Wave 6 fix. Only the valid 8-digit happy path was
# tested; this parametric set pins the boundary so any future regex drift
# (e.g. reverting to \d{6,12}) breaks a test immediately.


import pytest as _pytest


@_pytest.mark.parametrize("bad_account_no", [
    "1234567",      # 7 digits — was valid under \d{6,12}, now invalid
    "123456789",    # 9 digits — was valid, now invalid
    "12345678901",  # 11 digits — was valid, now invalid
    "1234",         # 4 digits — always invalid
    "12345678a",    # non-numeric — always invalid
    "",             # empty — always invalid
    "  12345678",   # leading whitespace — always invalid
])
def test_connect_rejects_non_8_digit_account_no(client, auth_user, bad_account_no):
    """Regression guard for PR #416 — backend MUST mirror the frontend
    `/^\\d{8}$/` regex exactly. Anything else is a 400 before we touch KIS."""
    r = client.post(
        "/api/broker/kis/connect",
        json={
            "app_key": "k" * 16,
            "app_secret": "s" * 32,
            "account_no": bad_account_no,
            "account_prod": "01",
            "is_paper": False,
        },
    )
    assert r.status_code == 400, (
        f"account_no={bad_account_no!r} should be rejected; "
        f"got {r.status_code} body={r.get_data(as_text=True)}"
    )


# ── 2026-05-25 Bug #3 — display_name length validation ─────────────────────
# BrokerConnection.display_name is db.String(100). A >100-char value reaches
# PostgreSQL and raises DataError → 500. Reject explicitly at the boundary.


class TestConnectDisplayNameLength:
    _VALID_BASE = {
        "app_key": "k" * 16,
        "app_secret": "s" * 32,
        "account_no": "12345678",
        "account_prod": "01",
    }

    def test_display_name_over_100_chars_rejected_400(self, client, auth_user):
        body = {**self._VALID_BASE, "display_name": "x" * 101}
        r = client.post("/api/broker/kis/connect", json=body)
        assert r.status_code == 400, r.get_data(as_text=True)
        assert r.get_json()["code"] == "INVALID_DISPLAY_NAME"

    def test_display_name_exactly_100_chars_passes_validation(self, client, auth_user):
        # Exactly 100 chars must NOT be rejected by the length guard. We stop
        # before the real KIS round-trip by mocking the service, so a non-400
        # status (here 200) proves validation accepted the value.
        body = {**self._VALID_BASE, "display_name": "x" * 100}
        with patch("routes.broker_oauth.upsert_kis_connection") as up, \
                patch("routes.broker_oauth.UserKISService") as svc:
            up.return_value = type("C", (), {"id": 1, "display_name": "x" * 100,
                                             "is_paper": False})()
            inst = svc.return_value
            inst.authenticate.return_value = {"ok": True}
            inst.sync_to_db.return_value = {"ok": True, "added": [], "updated": []}
            r = client.post("/api/broker/kis/connect", json=body)
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json().get("code") != "INVALID_DISPLAY_NAME"

    def test_display_name_none_passes_validation(self, client, auth_user):
        body = {**self._VALID_BASE}  # no display_name
        with patch("routes.broker_oauth.upsert_kis_connection") as up, \
                patch("routes.broker_oauth.UserKISService") as svc:
            up.return_value = type("C", (), {"id": 1, "display_name": None,
                                             "is_paper": False})()
            inst = svc.return_value
            inst.authenticate.return_value = {"ok": True}
            inst.sync_to_db.return_value = {"ok": True, "added": [], "updated": []}
            r = client.post("/api/broker/kis/connect", json=body)
        assert r.status_code == 200, r.get_data(as_text=True)


# ── 2026-05-25 Bug #1 — free-tier 3-position cap on KIS sync/connect ────────
# kis_connect (initial sync) and kis_sync were calling sync_to_db() with NO
# cap, letting a free user bypass the 3-position limit (revenue leak).
# reconcile (routes/portfolio.py) computes max_new_positions = cap - held.


class TestFreeTierPositionCap:
    _VALID_BASE = {
        "app_key": "k" * 16,
        "app_secret": "s" * 32,
        "account_no": "12345678",
        "account_prod": "01",
    }

    def _login(self, client, user):
        resp = client.post("/api/auth/login",
                           json={"email": user["email"], "password": user["password"]})
        assert resp.status_code == 200, resp.data

    def test_sync_passes_cap_for_free_user_with_no_positions(
        self, client, make_user
    ):
        """Free user, 0 held → budget should be 3."""
        user = make_user(email="free0@test.com", tier="free")
        self._login(client, user)
        with patch("routes.broker_oauth.UserKISService") as svc:
            inst = svc.return_value
            inst.sync_to_db.return_value = {
                "ok": True, "added": [], "updated": [], "synced": 0,
                "available_cash": 0, "total_value": 0,
            }
            r = client.post("/api/broker/kis/sync", json={})
        assert r.status_code == 200, r.get_data(as_text=True)
        inst.sync_to_db.assert_called_once_with(max_new_positions=3)

    def test_sync_passes_remaining_budget_for_free_user_with_two_positions(
        self, client, make_user, add_position
    ):
        """Free user already holding 2 → budget should be 3-2 = 1."""
        user = make_user(email="free2@test.com", tier="free")
        add_position(user["id"], ticker="AAPL", shares=5)
        add_position(user["id"], ticker="MSFT", shares=5)
        self._login(client, user)
        with patch("routes.broker_oauth.UserKISService") as svc:
            inst = svc.return_value
            inst.sync_to_db.return_value = {
                "ok": True, "added": [], "updated": [], "synced": 0,
                "available_cash": 0, "total_value": 0,
            }
            r = client.post("/api/broker/kis/sync", json={})
        assert r.status_code == 200, r.get_data(as_text=True)
        inst.sync_to_db.assert_called_once_with(max_new_positions=1)

    def test_sync_budget_clamped_to_zero_when_at_or_over_cap(
        self, client, make_user, add_position
    ):
        """Free user already holding 3 → budget clamps to 0 (never negative)."""
        user = make_user(email="free3@test.com", tier="free")
        for t in ("AAPL", "MSFT", "GOOG"):
            add_position(user["id"], ticker=t, shares=5)
        self._login(client, user)
        with patch("routes.broker_oauth.UserKISService") as svc:
            inst = svc.return_value
            inst.sync_to_db.return_value = {
                "ok": True, "added": [], "updated": [], "synced": 0,
                "available_cash": 0, "total_value": 0,
            }
            r = client.post("/api/broker/kis/sync", json={})
        assert r.status_code == 200, r.get_data(as_text=True)
        inst.sync_to_db.assert_called_once_with(max_new_positions=0)

    def test_sync_unlimited_for_paid_user(self, client, make_user, add_position):
        """Paid (premium) user → max_new_positions=None (unlimited)."""
        user = make_user(email="paid@test.com", tier="premium")
        add_position(user["id"], ticker="AAPL", shares=5)
        self._login(client, user)
        with patch("routes.broker_oauth.UserKISService") as svc:
            inst = svc.return_value
            inst.sync_to_db.return_value = {
                "ok": True, "added": [], "updated": [], "synced": 0,
                "available_cash": 0, "total_value": 0,
            }
            r = client.post("/api/broker/kis/sync", json={})
        assert r.status_code == 200, r.get_data(as_text=True)
        inst.sync_to_db.assert_called_once_with(max_new_positions=None)

    def test_connect_initial_sync_passes_cap_for_free_user(
        self, client, make_user, add_position
    ):
        """connect's initial sync must apply the same cap. Free user holding 1
        → budget 3-1 = 2."""
        user = make_user(email="freeconn@test.com", tier="free")
        add_position(user["id"], ticker="AAPL", shares=5)
        self._login(client, user)
        with patch("routes.broker_oauth.upsert_kis_connection") as up, \
                patch("routes.broker_oauth.UserKISService") as svc:
            up.return_value = type("C", (), {"id": 1, "display_name": None,
                                             "is_paper": False})()
            inst = svc.return_value
            inst.authenticate.return_value = {"ok": True}
            inst.sync_to_db.return_value = {"ok": True, "added": [], "updated": []}
            r = client.post("/api/broker/kis/connect", json={**self._VALID_BASE})
        assert r.status_code == 200, r.get_data(as_text=True)
        inst.sync_to_db.assert_called_once_with(max_new_positions=2)

    def test_connect_initial_sync_unlimited_for_paid_user(self, client, make_user):
        """connect's initial sync is unlimited for paid tiers."""
        user = make_user(email="paidconn@test.com", tier="pro")
        self._login(client, user)
        with patch("routes.broker_oauth.upsert_kis_connection") as up, \
                patch("routes.broker_oauth.UserKISService") as svc:
            up.return_value = type("C", (), {"id": 1, "display_name": None,
                                             "is_paper": False})()
            inst = svc.return_value
            inst.authenticate.return_value = {"ok": True}
            inst.sync_to_db.return_value = {"ok": True, "added": [], "updated": []}
            r = client.post("/api/broker/kis/connect", json={**self._VALID_BASE})
        assert r.status_code == 200, r.get_data(as_text=True)
        inst.sync_to_db.assert_called_once_with(max_new_positions=None)
