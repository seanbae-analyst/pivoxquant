"""Smoke tests for routes/command_center.py — internal CEO ops console.

Blueprint is *opt-in*: routes/__init__.py only registers it when
ENABLE_COMMAND_CENTER=1. After the 2026-05-02 security fix, every route
is gated by ``@api_auth`` plus an admin-email check (``ADMIN_EMAILS`` env
var, mirrors ``routes/admin_fmp.py``).

Coverage:
  - Default test app has ENABLE_COMMAND_CENTER unset → 404 everywhere.
  - With the blueprint registered, anonymous callers get 401 (api_auth
    short-circuit) — no validation reachable without a session.
  - With the blueprint registered + a logged-in non-admin user, every
    endpoint returns 403 (admin gate).
  - The module stays importable and exposes the expected blueprint.
"""
from __future__ import annotations

from unittest.mock import patch


class TestCommandCenterRouteUnregistered:
    """Default test app has ENABLE_COMMAND_CENTER unset → 404 everywhere."""

    def test_log_404_when_blueprint_unregistered(self, client):
        r = client.post("/api/command-center/log", json={})
        assert r.status_code == 404

    def test_stats_404_when_blueprint_unregistered(self, client):
        r = client.get("/api/command-center/stats")
        assert r.status_code == 404


class TestCommandCenterModuleImports:
    """Dead-code defense: blueprint must remain importable + well-formed."""

    def test_module_imports(self):
        from routes import command_center
        assert hasattr(command_center, "command_center_bp")

    def test_blueprint_registers_six_routes(self):
        # /command-center, /agents, /api/command-center/log, /stream,
        # /stats, /dispatch → six deferred routes.
        from routes.command_center import command_center_bp
        assert len(command_center_bp.deferred_functions) == 6


class TestCommandCenterAuth:
    """@api_auth + admin gate enforcement (added 2026-05-02 — B5 follow-up)."""

    def _build_app_with_bp(self):
        """Construct a minimal Flask app with the command-center blueprint
        wired up alongside Flask-Login + a user_loader so @api_auth /
        current_user resolve cleanly."""
        from flask import Flask
        from flask_login import LoginManager, UserMixin, login_user

        from routes.command_center import command_center_bp

        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test-cc-smoke"
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        login_manager = LoginManager()
        login_manager.init_app(app)

        class _U(UserMixin):
            def __init__(self, uid: int, email: str):
                self.id = uid
                self.email = email

        users: dict[int, _U] = {}

        @login_manager.user_loader
        def _load(uid):
            return users.get(int(uid))

        @app.route("/_test/login_as/<email>")
        def _login_as(email):
            uid = len(users) + 1
            u = _U(uid, email)
            users[uid] = u
            login_user(u)
            return "ok"

        app.register_blueprint(command_center_bp)
        return app

    def test_log_anonymous_returns_401(self):
        app = self._build_app_with_bp()
        with app.test_client() as c:
            r = c.post("/api/command-center/log", json={})
            assert r.status_code == 401

    def test_stream_anonymous_returns_401(self):
        app = self._build_app_with_bp()
        with app.test_client() as c:
            r = c.get("/api/command-center/stream")
            assert r.status_code == 401

    def test_stats_anonymous_returns_401(self):
        app = self._build_app_with_bp()
        with app.test_client() as c:
            r = c.get("/api/command-center/stats")
            assert r.status_code == 401

    def test_dispatch_anonymous_returns_401(self):
        app = self._build_app_with_bp()
        with app.test_client() as c:
            r = c.post("/api/command-center/dispatch", json={})
            assert r.status_code == 401

    def test_serve_command_center_anonymous_returns_401(self):
        app = self._build_app_with_bp()
        with app.test_client() as c:
            r = c.get("/command-center")
            assert r.status_code == 401

    def test_serve_agents_anonymous_returns_401(self):
        app = self._build_app_with_bp()
        with app.test_client() as c:
            r = c.get("/agents")
            assert r.status_code == 401

    def test_log_non_admin_returns_403(self):
        """Logged-in but non-admin → 403 (admin gate fails closed)."""
        app = self._build_app_with_bp()
        with patch.dict("os.environ", {"ADMIN_EMAILS": "ceo@pivoxquant.com"}):
            with app.test_client() as c:
                c.get("/_test/login_as/random@user.com")
                r = c.post("/api/command-center/log", json={})
                assert r.status_code == 403

    def test_log_admin_validates_payload(self):
        """Admin user reaches validation logic — same 400s as before."""
        app = self._build_app_with_bp()
        with patch.dict("os.environ", {"ADMIN_EMAILS": "ceo@pivoxquant.com"}):
            with app.test_client() as c:
                c.get("/_test/login_as/ceo@pivoxquant.com")

                r = c.post("/api/command-center/log", json=None)
                assert r.status_code == 400  # JSON body required

                r = c.post("/api/command-center/log",
                           json={"command": "x", "status": "completed"})
                assert r.status_code == 400  # source required

                r = c.post("/api/command-center/log",
                           json={"source": "agent", "status": "completed"})
                assert r.status_code == 400  # command required

    def test_log_admin_emails_unset_returns_403(self):
        """Fail-closed: ADMIN_EMAILS missing → 403 even for logged-in users."""
        app = self._build_app_with_bp()
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("ADMIN_EMAILS", None)
            with app.test_client() as c:
                c.get("/_test/login_as/ceo@pivoxquant.com")
                r = c.post("/api/command-center/log", json={})
                assert r.status_code == 403
