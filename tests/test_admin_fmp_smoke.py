"""Smoke tests for routes/admin_fmp.py — admin-gated FMP usage probe.

Auth chain:
    @login_required → unauthenticated callers get 401 (Flask-Login default,
                       no login_view set in test app).
    _deny_non_admin() → authenticated non-admins get 403.
    Authenticated admin → 200 + fmp_service.get_api_usage() payload.
"""
from __future__ import annotations

import os
from unittest.mock import patch


class TestAdminFmpSmoke:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/admin/fmp-usage")
        assert r.status_code == 401

    def test_authenticated_non_admin_returns_403(self, client, auth_user):
        # auth_user has email user@test.com, not in ADMIN_EMAILS.
        with patch.dict(os.environ, {"ADMIN_EMAILS": "ceo@pivoxquant.com"}):
            r = client.get("/api/admin/fmp-usage")
        assert r.status_code == 403

    def test_no_admin_emails_env_fails_closed(self, client, auth_user):
        # If ADMIN_EMAILS is unset, every authenticated user is denied.
        os.environ.pop("ADMIN_EMAILS", None)
        r = client.get("/api/admin/fmp-usage")
        assert r.status_code == 403

    def test_admin_user_gets_usage_payload(self, client, make_user):
        admin = make_user(email="admin@pivoxquant.com")
        client.post("/api/auth/login",
                    json={"email": admin["email"], "password": admin["password"]})
        with patch.dict(os.environ, {"ADMIN_EMAILS": "admin@pivoxquant.com"}), \
             patch("fmp_service.get_api_usage", return_value={"daily_calls": 1}):
            r = client.get("/api/admin/fmp-usage")
        assert r.status_code == 200
        assert r.get_json() == {"daily_calls": 1}
