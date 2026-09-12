"""PIPA §21 self-service deletion-cancel route (POST /api/auth/delete-cancel).

The 30-day soft-delete (/delete-request) logs the user out and login is refused
while ``deletion_requested_at`` is set, so the cancel path CANNOT use a session.
It authenticates with the HMAC token emailed at request time (same trust model
as a password-reset link). These tests lock that contract:

  * a valid token clears deletion_requested_at + deleted_at (restore)
  * idempotent when the account is not pending (already_active)
  * forged / missing / expired tokens are rejected (no restore)
  * a token whose user row is already purged → gone
  * the emailed cancel URL round-trips back to the user id
"""
from __future__ import annotations

import datetime as _dt

import pytest

from extensions import db
from models import User


def _token_for(app, uid):
    from routes.auth import _make_delete_cancel_token
    with app.app_context():
        return _make_delete_cancel_token(uid)


def _set_pending(app, uid, when=None):
    with app.app_context():
        u = db.session.get(User, uid)
        u.deletion_requested_at = when or _dt.datetime.utcnow()
        db.session.commit()


# ── Happy path ───────────────────────────────────────────────────────────────

def test_valid_token_restores_pending_account(app, raw_client, make_user):
    u = make_user(email="restore@test.com")
    _set_pending(app, u["id"])
    token = _token_for(app, u["id"])

    resp = raw_client.post("/api/auth/delete-cancel", json={"token": token})
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True and body.get("restored") is True

    with app.app_context():
        refreshed = db.session.get(User, u["id"])
        assert refreshed.deletion_requested_at is None
        assert refreshed.deleted_at is None


def test_idempotent_when_not_pending(app, raw_client, make_user):
    u = make_user(email="notpending@test.com")  # deletion_requested_at stays NULL
    token = _token_for(app, u["id"])

    resp = raw_client.post("/api/auth/delete-cancel", json={"token": token})
    assert resp.status_code == 200, resp.data
    assert resp.get_json().get("already_active") is True


# ── Rejection paths ──────────────────────────────────────────────────────────

def test_missing_token_rejected(raw_client):
    resp = raw_client.post("/api/auth/delete-cancel", json={})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "AUTH_DELETE_CANCEL_NO_TOKEN"


def test_forged_token_rejected(app, raw_client, make_user):
    u = make_user(email="forged@test.com")
    _set_pending(app, u["id"])

    resp = raw_client.post("/api/auth/delete-cancel", json={"token": "not.a.real-token"})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "AUTH_DELETE_CANCEL_INVALID"

    # The account must remain pending — a bad token never restores.
    with app.app_context():
        assert db.session.get(User, u["id"]).deletion_requested_at is not None


def test_expired_token_rejected(app, raw_client, make_user, monkeypatch):
    u = make_user(email="expired@test.com")
    _set_pending(app, u["id"])
    token = _token_for(app, u["id"])

    # Force any token to read as expired (age > max_age).
    monkeypatch.setattr("routes.auth._DELETE_CANCEL_MAX_AGE", -1)
    resp = raw_client.post("/api/auth/delete-cancel", json={"token": token})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "AUTH_DELETE_CANCEL_EXPIRED"

    with app.app_context():
        assert db.session.get(User, u["id"]).deletion_requested_at is not None


def test_token_for_purged_user_is_gone(app, raw_client):
    # Sign a token for a uid that does not exist (row already hard-deleted).
    token = _token_for(app, 9_999_999)
    resp = raw_client.post("/api/auth/delete-cancel", json={"token": token})
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "AUTH_DELETE_CANCEL_GONE"


# ── Cross-account safety + email link ────────────────────────────────────────

def test_token_only_restores_its_own_user(app, raw_client, make_user):
    victim = make_user(email="victim@test.com")
    attacker = make_user(email="attacker@test.com")
    _set_pending(app, victim["id"])
    _set_pending(app, attacker["id"])

    # A token minted for the attacker must NOT restore the victim.
    token = _token_for(app, attacker["id"])
    resp = raw_client.post("/api/auth/delete-cancel", json={"token": token})
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(User, attacker["id"]).deletion_requested_at is None
        assert db.session.get(User, victim["id"]).deletion_requested_at is not None


def test_cancel_url_round_trips_to_uid(app):
    from routes.auth import _delete_cancel_url, _delete_cancel_serializer

    # test_request_context so _resolve_frontend_url (reads request headers) works.
    with app.test_request_context():
        url = _delete_cancel_url(4242)
        assert "/delete-cancel?token=" in url
        token = url.split("token=", 1)[1]
        payload = _delete_cancel_serializer().loads(token)
        assert payload == {"uid": 4242}


def test_cancel_url_honors_forwarded_host_in_prod(app):
    """The emailed cancel link must point at the real prod domain (resolved
    from X-Forwarded-Host, whitelisted), NOT localhost — independent of whether
    FRONTEND_URL env is set on the box."""
    from routes.auth import _delete_cancel_url

    with app.test_request_context(
        headers={"X-Forwarded-Host": "www.pivoxquant.com", "X-Forwarded-Proto": "https"}
    ):
        url = _delete_cancel_url(7)
        assert url.startswith("https://www.pivoxquant.com/delete-cancel?token=")


def test_delete_request_email_embeds_self_service_cancel_link(
    client, auth_user, monkeypatch
):
    """End-to-end: POST /delete-request emails a self-service cancel link
    (replacing the old 'contact support to cancel' line)."""
    captured = {}

    def _fake_send(self, user, **kwargs):
        captured["html"] = kwargs.get("html_body", "")
        return True

    # Patch the class method (same object via either import path).
    monkeypatch.setattr(
        "services.email.sender.EmailSender.send", _fake_send, raising=True
    )

    resp = client.post("/api/auth/delete-request")
    assert resp.status_code == 200, resp.data

    html = captured.get("html", "")
    assert "/delete-cancel?token=" in html, "cancel link missing from email"
    assert "탈퇴 철회하기" in html
    # The old support-email cancel instruction must be gone.
    assert "고객센터(support@pivoxquant.com)로 연락" not in html



def test_token_from_an_earlier_request_cannot_cancel_a_later_one(app, raw_client, make_user):
    """2026-09-10: request → cancel → request again. The first email's link
    must not undo the second request."""
    from datetime import datetime, timedelta
    from extensions import db
    from models import User
    from routes.auth import _make_delete_cancel_token

    u = make_user(email="stale-cancel@test.com")
    first = datetime(2026, 9, 1, 3, 0, 0)
    second = first + timedelta(days=2)
    with app.app_context():
        row = db.session.get(User, u["id"])
        row.deletion_requested_at = second
        db.session.commit()
        old_token = _make_delete_cancel_token(u["id"], first)
        new_token = _make_delete_cancel_token(u["id"], second)

    resp = raw_client.post("/api/auth/delete-cancel", json={"token": old_token})
    assert resp.status_code == 400
    body = resp.get_json()
    assert "AUTH_DELETE_CANCEL_STALE" in (body.get("code"), body.get("error_code"), body.get("error"))
    with app.app_context():
        assert db.session.get(User, u["id"]).deletion_requested_at is not None

    resp = raw_client.post("/api/auth/delete-cancel", json={"token": new_token})
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(User, u["id"]).deletion_requested_at is None
