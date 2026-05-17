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
