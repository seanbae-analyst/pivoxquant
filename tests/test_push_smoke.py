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

    def test_subscribe_rejects_a_non_push_endpoint(self, client, auth_user):
        """2026-10-13: any URL was stored and later POSTed to by the server."""
        for bad in ("http://fcm.googleapis.com/fcm/send/x", "https://169.254.169.254/latest",
                    "https://evil.example/fcm.googleapis.com", "https://fcm.googleapis.com.evil.example/x",
                    "file:///etc/passwd", 123):
            r = client.post("/api/push/subscribe", json={"subscription": {"endpoint": bad, "keys": {}}})
            assert r.status_code == 400, bad
        # Edge (WNS) and Safari (Apple) endpoints are accepted.
        for good in ("https://wns2-pn1p.notify.windows.com/w/?token=abc", "https://web.push.apple.com/QGx"):
            r = client.post("/api/push/subscribe", json={"subscription": {"endpoint": good, "keys": {}}})
            assert r.status_code == 200, good

    def test_subscribe_non_dict_subscription_is_400(self, client, auth_user):
        r = client.post("/api/push/subscribe", json={"subscription": "x"})
        assert r.status_code == 400

    def test_subscribe_happy_path(self, client, auth_user):
        r = client.post("/api/push/subscribe", json={
            "subscription": {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
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
                "endpoint": "https://updates.push.services.mozilla.com/wpush/v2/e1",
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
