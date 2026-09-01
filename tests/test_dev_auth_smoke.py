"""Smoke tests for routes/dev_auth.py — DEV_LOGIN_SECRET-gated test bypass.

Production must NOT set DEV_LOGIN_SECRET. The blueprint itself is
*conditionally registered* in routes/__init__.py — when DEV_LOGIN_SECRET
is unset at app-boot, the routes don't exist (Flask 404).

The test app fixture in conftest.py is built without DEV_LOGIN_SECRET
(prod-like), so we verify the route is dead in that mode. We also
import-verify the module + assert its endpoints' code paths are coherent
without standing up a separate app.
"""
from __future__ import annotations

import pytest


class TestDevAuthRouteNotRegistered:
    """When DEV_LOGIN_SECRET is unset (prod default), the routes 404."""

    def test_dev_login_404_when_blueprint_unregistered(self, client):
        r = client.post("/api/auth/dev-login", json={"secret": "anything"})
        assert r.status_code == 404

    def test_dev_upgrade_404_when_blueprint_unregistered(self, client):
        r = client.post("/api/auth/dev-upgrade", json={"secret": "anything"})
        assert r.status_code == 404


class TestDevAuthModuleImports:
    """Smoke-check the module can be imported and exposes the expected
    handlers (dead-code defense — routes/__init__.py imports it under a
    conditional, so a syntax error there would never be caught at boot)."""

    def test_module_imports_cleanly(self):
        from routes import dev_auth
        assert hasattr(dev_auth, "dev_auth_bp")
        assert hasattr(dev_auth, "dev_login")
        assert hasattr(dev_auth, "dev_upgrade")

    def test_blueprint_has_two_routes(self):
        from routes.dev_auth import dev_auth_bp
        # Each @route decorator adds a deferred function to deferred_functions.
        assert len(dev_auth_bp.deferred_functions) == 2


class TestPlatformMarkerRefusal:
    """The DEV_LOGIN_SECRET guard must refuse on ANY hosting platform, not
    just Railway.

    2026-09-01: the marker list was Railway-only. Moving the backend to Render
    would have silently dropped the second layer of the W2-P3 belt-and-
    suspenders check, leaving FLASK_ENV as the sole barrier — which is the
    single-check state W2-P3 was written to fix. These cases lock each marker
    in by presence (Render sets RENDER=true / RENDER_SERVICE_ID; Fly sets
    FLY_APP_NAME), with FLASK_ENV explicitly NOT production so that only the
    marker can be doing the work.
    """

    @pytest.mark.parametrize(
        "marker",
        [
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_PUBLIC_DOMAIN",
            "RENDER",
            "RENDER_SERVICE_ID",
            "FLY_APP_NAME",
        ],
    )
    def test_marker_alone_refuses_to_mount(self, monkeypatch, marker):
        from flask import Flask

        from routes import register_blueprints

        monkeypatch.setenv("DEV_LOGIN_SECRET", "anything")
        monkeypatch.setenv("FLASK_ENV", "development")
        for m in (
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_PUBLIC_DOMAIN",
            "RENDER",
            "RENDER_SERVICE_ID",
            "FLY_APP_NAME",
        ):
            monkeypatch.delenv(m, raising=False)
        monkeypatch.setenv(marker, "1")

        with pytest.raises(RuntimeError, match="DEV_LOGIN_SECRET"):
            register_blueprints(Flask(__name__))

    def test_no_marker_and_not_production_still_mounts(self, monkeypatch):
        """The guard must not become a blanket refusal — local dev with
        DEV_LOGIN_SECRET set is the supported E2E workflow."""
        from flask import Flask

        from routes import register_blueprints

        monkeypatch.setenv("DEV_LOGIN_SECRET", "anything")
        monkeypatch.setenv("FLASK_ENV", "development")
        for m in (
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_PUBLIC_DOMAIN",
            "RENDER",
            "RENDER_SERVICE_ID",
            "FLY_APP_NAME",
        ):
            monkeypatch.delenv(m, raising=False)

        app = Flask(__name__)
        register_blueprints(app)
        assert "dev_auth" in app.blueprints
