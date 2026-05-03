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
