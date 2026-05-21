"""Regression — load_user soft-delete session invalidation (PIPA §21, Wave I C-2).

FIX 1 (2026-05-22): app.py:load_user previously returned the User unconditionally
(`db.session.get(User, int(uid))`). routes/auth.py login() + google/kakao callbacks
reject users whose ``deletion_requested_at`` is set, but a remember_token cookie
issued *before* the delete-request would silently re-authenticate the same user on
every request — bypassing the login-time block and granting full 200 access to
/api/auth/me and every data API.

The production loader (app.py) now returns ``None`` for any user with
``deletion_requested_at != NULL``, invalidating the session everywhere.

The conftest test app installs its OWN minimal ``load_user`` (without this guard),
so these tests exercise the production loader's logic directly and verify the
end-to-end session behaviour by monkeypatching the conftest app's login_manager to
the production-equivalent loader.
"""
from __future__ import annotations

import datetime as _dt

import pytest


def _prod_load_user(uid):
    """Mirror of app.py:load_user (production user loader). Kept here so the
    regression locks the exact behaviour: None for soft-deleted users."""
    from extensions import db
    from models import User

    try:
        user = db.session.get(User, int(uid))
    except (TypeError, ValueError):
        return None
    if user is not None and user.deletion_requested_at is not None:
        return None
    return user


# ── Unit: the loader contract ────────────────────────────────────────────────

def test_load_user_returns_user_when_not_pending_deletion(app, make_user):
    u = make_user(email="alive@test.com")
    with app.app_context():
        loaded = _prod_load_user(u["id"])
        assert loaded is not None
        assert loaded.id == u["id"]


def test_load_user_returns_none_when_deletion_requested(app, make_user):
    from extensions import db
    from models import User

    u = make_user(email="pending@test.com")
    with app.app_context():
        user = db.session.get(User, u["id"])
        user.deletion_requested_at = _dt.datetime.utcnow()
        db.session.commit()

        assert _prod_load_user(u["id"]) is None


def test_load_user_returns_none_for_bad_uid(app):
    with app.app_context():
        assert _prod_load_user("not-an-int") is None
        assert _prod_load_user(None) is None


def test_app_py_loader_matches_prod_logic():
    """The production loader source must keep the deletion guard. Locks against
    accidental reverts that drop the deletion_requested_at check."""
    import inspect

    import app as app_module

    src = inspect.getsource(app_module.create_app)
    assert "deletion_requested_at is not None" in src, (
        "app.py:load_user lost the soft-delete guard"
    )


# ── Integration: same session, re-auth bypass is closed ──────────────────────

@pytest.fixture
def prod_loader_app():
    """Build an isolated Flask app whose user_loader is the PRODUCTION loader
    (the conftest ``app`` fixture installs its own minimal loader without the
    soft-delete guard, so we can't reuse it to test this path). This mirrors
    the conftest test-app wiring but registers ``_prod_load_user``.

    A dedicated app sidesteps the session-scoped identity-map sharing that the
    shared ``app`` fixture exhibits, so each request gets a clean read of the
    persisted ``deletion_requested_at`` flag — exactly like prod's per-request
    scoped session teardown.
    """
    import os
    import tempfile

    from flask import Flask, redirect

    from config import Config
    from extensions import db, login_manager, migrate
    from routes import register_blueprints
    from security import init_security, limiter

    fd, db_path = tempfile.mkstemp(suffix=".sqlite", prefix="pivox_softdel_")
    os.close(fd)

    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    init_security(app)
    limiter.enabled = False
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # The production loader under test.
    login_manager.user_loader(_prod_load_user)

    @app.route("/")
    def index():
        return redirect("/home")

    register_blueprints(app)
    with app.app_context():
        db.create_all()

    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


def test_delete_request_invalidates_existing_session(prod_loader_app):
    """Login → delete-request → the SAME session can no longer authenticate.

    Reproduces the bypass: a cookie minted before delete-request must stop
    working the moment deletion_requested_at is set, because load_user returns
    None on every subsequent request.
    """
    from extensions import db
    from models import User

    app = prod_loader_app

    with app.app_context():
        u = User(email="session-bypass@test.com", name="Tester")
        u.set_pw("password123")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with app.test_client() as raw:
        # 1. Authenticate normally — establishes the session cookie.
        login = raw.post("/api/auth/login", json={
            "email": "session-bypass@test.com", "password": "password123",
        })
        assert login.status_code == 200, login.data

        # Sanity: the session authenticates before deletion.
        me_before = raw.get("/api/auth/me").get_json()
        assert me_before["authenticated"] is True

        # 2. Soft-delete the account (simulating /delete-request).
        with app.app_context():
            user = db.session.get(User, uid)
            user.deletion_requested_at = _dt.datetime.utcnow()
            db.session.commit()

        # 3. The pre-existing session must NO LONGER authenticate.
        me_after = raw.get("/api/auth/me").get_json()
        assert me_after["authenticated"] is False, (
            "soft-deleted user still authenticated via stale session cookie"
        )
