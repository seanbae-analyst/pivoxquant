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
