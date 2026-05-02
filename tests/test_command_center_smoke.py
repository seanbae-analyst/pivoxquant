"""Smoke tests for routes/command_center.py — internal CEO ops console.

Blueprint is *opt-in*: routes/__init__.py only registers it when
ENABLE_COMMAND_CENTER=1. The route itself has no @api_auth (CEO local
tool), per the inline comment "프로덕션 배포 시 @api_auth 데코레이터 필수".

Since conftest.py builds the app without ENABLE_COMMAND_CENTER, every
endpoint 404s. We import-verify the module and walk a fresh app with
the blueprint registered to exercise the validation paths.
"""
from __future__ import annotations

import os
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

    def test_log_validates_payload_when_registered(self):
        """Walk the blueprint with a one-off Flask app to exercise validation
        without forcing every other test to set ENABLE_COMMAND_CENTER."""
        from flask import Flask
        from routes.command_center import command_center_bp

        app = Flask(__name__)
        app.register_blueprint(command_center_bp)
        with app.test_client() as c:
            r = c.post("/api/command-center/log", json=None)
            assert r.status_code == 400  # JSON body required

            r = c.post("/api/command-center/log",
                       json={"command": "x", "status": "completed"})
            assert r.status_code == 400  # source required

            r = c.post("/api/command-center/log",
                       json={"source": "agent", "status": "completed"})
            assert r.status_code == 400  # command required
