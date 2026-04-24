"""Tests for /api/notifications — alias over /api/alerts.

Ensures the new notifications_bp mirrors the four bell-dropdown endpoints
from routes/alerts.py at the /api/notifications prefix, preserves auth,
and returns identical shapes to /api/alerts.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from extensions import db
from models import Alert


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _seed_alert(app, user_id: int, *, is_read: bool = False, title: str = "Observation",
                body: str = "Ready.", kind: str = "price_52w_high") -> int:
    with app.app_context():
        a = Alert(
            user_id=user_id,
            ticker="AAPL",
            kind=kind,
            title=title,
            body=body,
            link="/reports",
            message=body,
            signal="POSITIVE",
            score=0,
            is_read=is_read,
            read_at=datetime.now(timezone.utc).replace(tzinfo=None) if is_read else None,
        )
        db.session.add(a)
        db.session.commit()
        return a.id


# ═════════════════════════════════════════════════════════════════════════════
# Auth gates
# ═════════════════════════════════════════════════════════════════════════════

def test_list_unauth_returns_401(client):
    resp = client.get("/api/notifications")
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "Login required"}


def test_unread_count_unauth_returns_401(client):
    resp = client.get("/api/notifications/unread-count")
    assert resp.status_code == 401


def test_read_all_unauth_returns_401(client):
    resp = client.post("/api/notifications/read-all")
    assert resp.status_code == 401


def test_mark_one_read_unauth_returns_401(client):
    resp = client.post("/api/notifications/1/read")
    assert resp.status_code == 401


def test_delete_one_unauth_returns_401(client):
    resp = client.delete("/api/notifications/1")
    assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# Authed happy paths
# ═════════════════════════════════════════════════════════════════════════════

def test_list_empty_authed(client, auth_user):
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"alerts": [], "unread": 0}


def test_list_returns_seeded_alert(app, client, auth_user):
    _seed_alert(app, auth_user["id"], is_read=False, title="Ready")
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["alerts"]) == 1
    assert data["unread"] == 1
    # Contract fields the frontend consumes
    row = data["alerts"][0]
    for key in ("id", "kind", "title", "body", "link", "created_at", "is_read"):
        assert key in row, f"missing field: {key}"
    assert row["is_read"] is False


def test_list_respects_limit_param(app, client, auth_user):
    for i in range(5):
        _seed_alert(app, auth_user["id"], title=f"A{i}")
    resp = client.get("/api/notifications?limit=3")
    assert resp.status_code == 200
    assert len(resp.get_json()["alerts"]) == 3


def test_unread_count_authed(app, client, auth_user):
    _seed_alert(app, auth_user["id"], is_read=False)
    _seed_alert(app, auth_user["id"], is_read=False)
    _seed_alert(app, auth_user["id"], is_read=True)
    resp = client.get("/api/notifications/unread-count")
    assert resp.status_code == 200
    assert resp.get_json() == {"count": 2}


def test_read_all_marks_every_unread(app, client, auth_user):
    _seed_alert(app, auth_user["id"], is_read=False)
    _seed_alert(app, auth_user["id"], is_read=False)

    resp = client.post("/api/notifications/read-all")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}

    # All should now be read.
    count = client.get("/api/notifications/unread-count").get_json()["count"]
    assert count == 0


def test_mark_one_read(app, client, auth_user):
    aid = _seed_alert(app, auth_user["id"], is_read=False)

    resp = client.post(f"/api/notifications/{aid}/read")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}

    with app.app_context():
        a = db.session.get(Alert, aid)
        assert a.is_read is True
        assert a.read_at is not None


def test_mark_one_read_404_if_missing(client, auth_user):
    resp = client.post("/api/notifications/99999/read")
    assert resp.status_code == 404


def test_delete_one(app, client, auth_user):
    aid = _seed_alert(app, auth_user["id"])

    resp = client.delete(f"/api/notifications/{aid}")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}

    with app.app_context():
        assert db.session.get(Alert, aid) is None


def test_delete_one_404_if_missing(client, auth_user):
    resp = client.delete("/api/notifications/99999")
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Cross-user isolation — a user must never see another user's alerts
# ═════════════════════════════════════════════════════════════════════════════

def test_cannot_read_other_users_alert(app, client, auth_user, make_user):
    other = make_user(email="other@test.com")
    other_alert = _seed_alert(app, other["id"], is_read=False)

    # The currently logged-in user should NOT see it in list
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    assert resp.get_json()["alerts"] == []

    # And cannot mark it read
    resp = client.post(f"/api/notifications/{other_alert}/read")
    assert resp.status_code == 404

    # Nor delete it
    resp = client.delete(f"/api/notifications/{other_alert}")
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Alias parity — /api/notifications must mirror /api/alerts shape exactly
# ═════════════════════════════════════════════════════════════════════════════

def test_alias_parity_list(app, client, auth_user):
    _seed_alert(app, auth_user["id"], title="Parity")
    a1 = client.get("/api/alerts").get_json()
    a2 = client.get("/api/notifications").get_json()
    assert a1.keys() == a2.keys()
    assert a1["unread"] == a2["unread"]
    assert len(a1["alerts"]) == len(a2["alerts"])


def test_alias_parity_unread_count(app, client, auth_user):
    _seed_alert(app, auth_user["id"], is_read=False)
    c1 = client.get("/api/alerts/unread-count").get_json()
    c2 = client.get("/api/notifications/unread-count").get_json()
    assert c1 == c2
