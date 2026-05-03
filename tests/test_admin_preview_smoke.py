"""Smoke tests for routes/admin_preview.py — artifact preview console.

Spec: '일반 유저는 404'. Non-admins get **404**, not 403, so the route
appears nonexistent. Unauthenticated callers hit @login_required → 401.
"""
from __future__ import annotations

import os
from unittest.mock import patch


class TestAdminPreviewListSmoke:
    def test_unauthenticated_list_returns_401(self, client):
        r = client.get("/api/admin/artifacts/list")
        assert r.status_code == 401

    def test_non_admin_list_returns_404(self, client, auth_user):
        # ADMIN_EMAILS unset → fails closed → 404 (silent).
        os.environ.pop("ADMIN_EMAILS", None)
        r = client.get("/api/admin/artifacts/list")
        assert r.status_code == 404

    def test_admin_list_returns_catalog(self, client, make_user):
        admin = make_user(email="admin@pivoxquant.com")
        client.post("/api/auth/login",
                    json={"email": admin["email"], "password": admin["password"]})
        with patch.dict(os.environ, {"ADMIN_EMAILS": "admin@pivoxquant.com"}):
            r = client.get("/api/admin/artifacts/list")
        assert r.status_code == 200
        d = r.get_json()
        assert "artifacts" in d and "count" in d
        assert d["count"] == len(d["artifacts"])


class TestAdminPreviewArtifactSmoke:
    def test_unauthenticated_preview_returns_401(self, client):
        r = client.get("/api/admin/artifacts/preview/weekly_memo")
        assert r.status_code == 401

    def test_non_admin_preview_returns_404(self, client, auth_user):
        os.environ.pop("ADMIN_EMAILS", None)
        r = client.get("/api/admin/artifacts/preview/weekly_memo")
        assert r.status_code == 404

    def test_admin_unknown_artifact_type_returns_404(self, client, make_user):
        admin = make_user(email="admin@pivoxquant.com")
        client.post("/api/auth/login",
                    json={"email": admin["email"], "password": admin["password"]})
        with patch.dict(os.environ, {"ADMIN_EMAILS": "admin@pivoxquant.com"}):
            r = client.get("/api/admin/artifacts/preview/__nope__")
        assert r.status_code == 404

    def test_admin_invalid_format_returns_400(self, client, make_user):
        admin = make_user(email="admin@pivoxquant.com")
        client.post("/api/auth/login",
                    json={"email": admin["email"], "password": admin["password"]})
        with patch.dict(os.environ, {"ADMIN_EMAILS": "admin@pivoxquant.com"}):
            r = client.get("/api/admin/artifacts/preview/weekly_memo?format=xml")
        assert r.status_code == 400
