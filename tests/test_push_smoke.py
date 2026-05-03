"""Smoke tests for routes/push.py — Web Push subscriptions."""
from __future__ import annotations


class TestPushSubscribeSmoke:
    def test_unauthenticated_subscribe_returns_401(self, client):
        r = client.post("/api/push/subscribe", json={})
        assert r.status_code == 401

    def test_subscribe_400_when_subscription_missing(self, client, auth_user):
        r = client.post("/api/push/subscribe", json={})
        assert r.status_code == 400

    def test_subscribe_400_when_endpoint_missing(self, client, auth_user):
        r = client.post("/api/push/subscribe",
                        json={"subscription": {"keys": {}}})
        assert r.status_code == 400

    def test_subscribe_happy_path(self, client, auth_user):
        r = client.post("/api/push/subscribe", json={
            "subscription": {
                "endpoint": "https://example.test/endpoint/abc",
                "keys": {"p256dh": "p256_x", "auth": "auth_y"},
            }
        })
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


class TestPushUnsubscribeSmoke:
    def test_unauthenticated_unsubscribe_returns_401(self, client):
        r = client.post("/api/push/unsubscribe", json={})
        assert r.status_code == 401

    def test_unsubscribe_no_endpoint_clears_all(self, client, auth_user):
        # Subscribe first.
        client.post("/api/push/subscribe", json={
            "subscription": {
                "endpoint": "https://example.test/e1",
                "keys": {"p256dh": "x", "auth": "y"},
            }
        })
        r = client.post("/api/push/unsubscribe", json={})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


class TestPushStatusSmoke:
    def test_unauthenticated_status_returns_401(self, client):
        r = client.get("/api/push/status")
        assert r.status_code == 401

    def test_status_no_subscriptions(self, client, auth_user):
        r = client.get("/api/push/status")
        assert r.status_code == 200
        d = r.get_json()
        assert d["subscribed"] is False
        assert d["count"] == 0
