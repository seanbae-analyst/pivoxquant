"""Inquiry CRUD / validation / rate-limit / IDOR / admin reply.

Uses the real SQLite test DB (conftest ``db.create_all()`` builds the
``inquiries`` table from the model). Email side effects are best-effort
and swallowed, so no transport mocking is required for these paths.
"""
from datetime import timedelta

import pytest

from extensions import db
from models.inquiry import Inquiry


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@pivoxquant.com")
    yield


# ── create / validation ───────────────────────────────────────────────────────
def test_create_inquiry_success(client, auth_user):
    resp = client.post("/api/support/inquiries", json={
        "category": "billing",
        "subject": "결제 영수증 문의",
        "body": "지난 달 영수증을 받지 못했습니다.",
    })
    assert resp.status_code == 201, resp.data
    data = resp.get_json()
    assert data["status"] == "open"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_inquiry_bad_category(client, auth_user):
    resp = client.post("/api/support/inquiries", json={
        "category": "investment", "subject": "x", "body": "y",
    })
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_CATEGORY"


def test_create_inquiry_empty_subject(client, auth_user):
    resp = client.post("/api/support/inquiries", json={
        "category": "other", "subject": "   ", "body": "y",
    })
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_SUBJECT"


def test_create_inquiry_oversize_body(client, auth_user):
    resp = client.post("/api/support/inquiries", json={
        "category": "other", "subject": "ok", "body": "x" * 5001,
    })
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_BODY"


def test_create_inquiry_requires_auth(client):
    resp = client.post("/api/support/inquiries", json={
        "category": "other", "subject": "a", "body": "b",
    })
    assert resp.status_code == 401


# ── rate limit ─────────────────────────────────────────────────────────────────
def test_create_inquiry_cooldown(client, auth_user):
    r1 = client.post("/api/support/inquiries", json={
        "category": "other", "subject": "first", "body": "body",
    })
    assert r1.status_code == 201
    r2 = client.post("/api/support/inquiries", json={
        "category": "other", "subject": "second", "body": "body",
    })
    assert r2.status_code == 429
    assert r2.get_json()["code"] == "RATE_LIMITED"


def test_create_inquiry_open_cap(client, auth_user, app):
    # Seed 10 open inquiries directly (bypass cooldown), all backdated.
    with app.app_context():
        from datetime import datetime, timezone
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        for i in range(10):
            db.session.add(Inquiry(
                user_id=auth_user["id"], category="other",
                subject=f"s{i}", body="b", status="open",
                email_snapshot=auth_user["email"], created_at=old,
            ))
        db.session.commit()
    resp = client.post("/api/support/inquiries", json={
        "category": "other", "subject": "overflow", "body": "body",
    })
    assert resp.status_code == 429
    assert resp.get_json()["code"] == "RATE_LIMITED"


# ── list / detail / IDOR ───────────────────────────────────────────────────────
def test_list_inquiries_only_mine(client, auth_user, app, make_user):
    with app.app_context():
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        other = make_user(email="other@test.com")
        db.session.add(Inquiry(
            user_id=auth_user["id"], category="other", subject="mine",
            body="b", status="open", email_snapshot=auth_user["email"],
            created_at=now,
        ))
        db.session.add(Inquiry(
            user_id=other["id"], category="other", subject="theirs",
            body="b", status="open", email_snapshot=other["email"],
            created_at=now,
        ))
        db.session.commit()
    resp = client.get("/api/support/inquiries")
    assert resp.status_code == 200
    rows = resp.get_json()["inquiries"]
    assert len(rows) == 1
    assert rows[0]["subject"] == "mine"
    assert "body" not in rows[0]  # summary only


def test_get_inquiry_detail(client, auth_user, app):
    with app.app_context():
        from datetime import datetime, timezone
        inq = Inquiry(
            user_id=auth_user["id"], category="account", subject="detail",
            body="the body", status="open", email_snapshot=auth_user["email"],
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(inq)
        db.session.commit()
        iid = inq.id
    resp = client.get(f"/api/support/inquiries/{iid}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["body"] == "the body"
    assert data["has_reply"] is False


def test_get_inquiry_idor_returns_404(client, auth_user, app, make_user):
    with app.app_context():
        from datetime import datetime, timezone
        other = make_user(email="victim@test.com")
        inq = Inquiry(
            user_id=other["id"], category="other", subject="secret",
            body="private", status="open", email_snapshot=other["email"],
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(inq)
        db.session.commit()
        iid = inq.id
    resp = client.get(f"/api/support/inquiries/{iid}")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "INQUIRY_NOT_FOUND"


# ── admin ──────────────────────────────────────────────────────────────────────
def test_admin_list_blocked_for_non_admin(client, auth_user, admin_env):
    # auth_user is user@test.com, not admin → 404 (route appears absent).
    resp = client.get("/api/support/admin/inquiries")
    assert resp.status_code == 404


def test_admin_reply_flow(client, app, make_user, admin_env):
    # Login as admin user.
    admin = make_user(email="admin@pivoxquant.com")
    login = client.post("/api/auth/login", json={
        "email": admin["email"], "password": admin["password"],
    })
    assert login.status_code == 200
    with app.app_context():
        from datetime import datetime, timezone
        inq = Inquiry(
            user_id=admin["id"], category="technical", subject="bug",
            body="broke", status="open", email_snapshot=admin["email"],
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(inq)
        db.session.commit()
        iid = inq.id

    # Admin sees it in the list with user_id + email_snapshot.
    lst = client.get("/api/support/admin/inquiries")
    assert lst.status_code == 200
    assert any(r["id"] == iid for r in lst.get_json()["inquiries"])
    assert all("email_snapshot" in r for r in lst.get_json()["inquiries"])

    # Reply.
    rep = client.post(f"/api/support/admin/inquiries/{iid}/reply", json={
        "reply": "수정했습니다. 확인 부탁드립니다.",
    })
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["status"] == "answered"
    assert data["has_reply"] is True
    assert data["answered_at"] is not None

    with app.app_context():
        refreshed = db.session.get(Inquiry, iid)
        assert refreshed.status == "answered"
        assert refreshed.admin_reply == "수정했습니다. 확인 부탁드립니다."


def test_admin_reply_validation(client, app, make_user, admin_env):
    admin = make_user(email="admin@pivoxquant.com")
    client.post("/api/auth/login", json={
        "email": admin["email"], "password": admin["password"],
    })
    with app.app_context():
        from datetime import datetime, timezone
        inq = Inquiry(
            user_id=admin["id"], category="other", subject="s",
            body="b", status="open", email_snapshot=admin["email"],
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(inq)
        db.session.commit()
        iid = inq.id
    resp = client.post(f"/api/support/admin/inquiries/{iid}/reply", json={
        "reply": "  ",
    })
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_REPLY"
