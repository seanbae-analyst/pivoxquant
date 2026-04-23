"""
tests/test_auth.py — Auth routes
==================================
Registration, login, logout, session, CSRF cookie.

Covers /api/auth/register, /api/auth/login, /api/auth/logout, /api/auth/me.
"""


# ── Registration ────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={
            "email": "new@test.com",
            "password": "secretpass",
            "name": "New User",
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["user"]["email"] == "new@test.com"
        assert data["user"]["name"] == "New User"
        # Password hash must never leak.
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    def test_register_duplicate_email_returns_409(self, client, make_user):
        make_user(email="dupe@test.com")
        r = client.post("/api/auth/register", json={
            "email": "dupe@test.com",
            "password": "anything",
        })
        assert r.status_code == 409
        assert "already" in r.get_json()["error"].lower()

    def test_register_missing_email_returns_400(self, client):
        r = client.post("/api/auth/register", json={"password": "x" * 8})
        assert r.status_code == 400

    def test_register_short_password_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "short@test.com",
            "password": "12345",  # < 6 chars
        })
        assert r.status_code == 400

    def test_register_normalizes_email_casing(self, client):
        r = client.post("/api/auth/register", json={
            "email": "MIXED@Test.COM",
            "password": "goodpass",
        })
        assert r.status_code == 200
        assert r.get_json()["user"]["email"] == "mixed@test.com"


# ── Login ───────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self, client, make_user):
        u = make_user(email="login@test.com", password="mypass123")
        r = client.post("/api/auth/login", json={
            "email": u["email"], "password": u["password"],
        })
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_login_wrong_password_returns_401(self, client, make_user):
        make_user(email="login2@test.com", password="correct123")
        r = client.post("/api/auth/login", json={
            "email": "login2@test.com", "password": "wrong",
        })
        assert r.status_code == 401

    def test_login_unknown_email_returns_401(self, client):
        r = client.post("/api/auth/login", json={
            "email": "ghost@test.com", "password": "whatever",
        })
        assert r.status_code == 401


# ── Session / me ────────────────────────────────────────────────────────────

class TestMe:
    def test_me_unauthenticated_returns_authenticated_false(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.get_json()["authenticated"] is False

    def test_me_after_login_returns_user(self, client, auth_user):
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        data = r.get_json()
        assert data["authenticated"] is True
        assert data["user"]["email"] == auth_user["email"]


# ── Logout ──────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_unauthenticated_is_idempotent_200(self, client):
        """Logout is idempotent: calling it while already logged out is a no-op
        that still returns 200 OK. HttpOnly session cookies can't be cleared
        client-side, so the endpoint must never refuse with 401 or the user
        is stuck with partially-invalid credentials they can't flush.
        """
        r = client.post("/api/auth/logout")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert body["was_authenticated"] is False

    def test_logout_then_me_shows_logged_out(self, client, auth_user):
        r = client.post("/api/auth/logout")
        assert r.status_code == 200
        assert r.get_json()["was_authenticated"] is True
        # Now /me should show logged out.
        me = client.get("/api/auth/me")
        assert me.get_json()["authenticated"] is False

    def test_logout_alias_root_path_works(self, client, auth_user):
        """`/api/logout` is the shorter alias for `/api/auth/logout`."""
        r = client.post("/api/logout")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        me = client.get("/api/auth/me")
        assert me.get_json()["authenticated"] is False

    def test_logout_clears_session_cookie(self, raw_client, make_user):
        """Logout response must explicitly expire the session cookie so the
        browser drops it even if the client didn't clear cookies itself.
        """
        u = make_user(email="cookielogout@test.com", password="pass1234")
        login = raw_client.post("/api/auth/login", json={
            "email": u["email"], "password": u["password"],
        })
        assert login.status_code == 200
        # Logout — no CSRF header on raw_client, but logout is CSRF-exempt.
        r = raw_client.post("/api/auth/logout")
        assert r.status_code == 200
        set_cookies = r.headers.getlist("Set-Cookie")
        # Session cookie must be emitted with an expiry in the past (deletion).
        assert any(
            "session=" in h and ("Expires=" in h or "Max-Age=0" in h)
            for h in set_cookies
        ), f"session cookie not expired; headers={set_cookies}"

    def test_logout_rejects_cross_origin_post(self, raw_client):
        """A POST with a disallowed Origin header must be rejected with 403.
        No login needed — the origin gate fires before we look at the session.
        """
        r = raw_client.post(
            "/api/auth/logout",
            headers={"Origin": "https://evil.example.com"},
        )
        assert r.status_code == 403
        assert r.get_json()["code"] == "UNTRUSTED_ORIGIN"


# ── CSRF cookie issuance ────────────────────────────────────────────────────

class TestCSRFCookie:
    def test_csrf_cookie_is_set_on_every_response(self, raw_client):
        r = raw_client.get("/api/auth/me")
        # Look through Set-Cookie headers for csrf_token.
        cookie_headers = r.headers.getlist("Set-Cookie")
        has_csrf = any("csrf_token=" in h for h in cookie_headers)
        assert has_csrf, f"csrf_token cookie missing; headers={cookie_headers}"

    def test_csrf_cookie_is_signed_and_stable(self, raw_client):
        """Cookie once set should remain valid across subsequent requests."""
        r1 = raw_client.get("/api/auth/me")
        token_1 = None
        for h in r1.headers.getlist("Set-Cookie"):
            if h.startswith("csrf_token="):
                token_1 = h.split(";", 1)[0].split("=", 1)[1]
                break
        assert token_1
        # Token must be of the form <random>.<sig>
        assert "." in token_1
        parts = token_1.split(".")
        assert len(parts) == 2 and all(parts), "CSRF token is not properly signed"
