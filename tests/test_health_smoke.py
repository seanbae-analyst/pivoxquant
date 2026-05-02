"""Smoke tests for routes/health.py — public probe, no auth.

Locked response contract (Railway probes depend on it):
    200  {"status": "ok",       "version": "...", "timestamp": "...", "db": "ok"}
    503  {"status": "degraded", ...}
"""
from __future__ import annotations


class TestHealthSmoke:
    def test_health_no_auth_required(self, client):
        r = client.get("/api/health")
        # Either healthy (200) or DB-degraded (503), but never 401.
        assert r.status_code in (200, 503)

    def test_health_returns_contract_fields(self, client):
        r = client.get("/api/health")
        d = r.get_json()
        assert "status" in d
        assert "version" in d
        assert "timestamp" in d
        assert "db" in d

    def test_health_status_ok_when_sqlite_works(self, client):
        # Test SQLite is in-memory & always responsive — should be ok.
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"
