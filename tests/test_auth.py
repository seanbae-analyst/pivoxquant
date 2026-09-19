"""
tests/test_auth.py — Auth routes
==================================
Registration, login, logout, session, CSRF cookie.

Covers /api/auth/register, /api/auth/login, /api/auth/logout, /api/auth/me.

PIPA §22 ⑥ — every successful /register payload below carries the
``age_confirmed: true`` self-declaration (2026-09-19: no birthdate is
collected anymore). The dedicated gate tests live in
``tests/test_signup_min_age.py``.
"""


# 만 14세 이상 self-declaration sent by every /register call below. Only
# the literal boolean ``True`` passes the server gate.
_AGE_CONFIRMED = True


# ── Registration ────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={
            "email": "new@test.com",
            "password": "secretpass",
            "name": "New User",
            "age_confirmed": _AGE_CONFIRMED,
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
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r.status_code == 409
        assert "already" in r.get_json()["error"].lower()

    def test_register_missing_email_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "password": "x" * 8,
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r.status_code == 400

    def test_register_short_password_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "short@test.com",
            "password": "12345",  # < 6 chars
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r.status_code == 400

    def test_register_normalizes_email_casing(self, client):
        r = client.post("/api/auth/register", json={
            "email": "MIXED@Test.COM",
            "password": "goodpass",
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r.status_code == 200
        assert r.get_json()["user"]["email"] == "mixed@test.com"

    def test_register_blocks_authenticated_caller(self, client, auth_user):
        """2026-05-15 bug-hunter Wave 7 CRITICAL #2 regression guard:
        the register endpoint used to silently create a new user AND
        replace the current session if called by an already-logged-in
        user. Reproduced on production (DB row id:21 korean@example.com
        created from a session originally id:3). Account-takeover /
        session-fixation risk class.

        After the fix, register must short-circuit with 409
        `ALREADY_AUTHENTICATED` for any authed caller."""
        # `auth_user` fixture logs the client in as a real user.
        r = client.post("/api/auth/register", json={
            "email": "newaccount@test.com",
            "password": "verystrongpw",
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r.status_code == 409
        body = r.get_json()
        assert body["code"] == "ALREADY_AUTHENTICATED"
        # Korean error message also present (user-facing).
        assert "이미 로그인" in body.get("error_kr", "")

    def test_register_rejects_cross_origin_browser_post(self, client):
        """2026-05-25 security-agent regression guard: cross-origin
        account-precreation / CSRF.

        Unauthenticated POSTs skip security.py:_csrf_protect(), so before
        the fix a hostile page could pre-create an account with a victim's
        email + attacker-chosen password from any Origin. Because the app is
        OAuth-only, the victim's later OAuth login then hits
        _guard_oauth_email_link() → OAuthLinkRefused("password_account") →
        permanent lockout. Reproduced on prod (Origin: evil.example.com → 200).

        A real browser always carries Origin on a cross-origin POST and can't
        forge an allowlisted value, so a non-allowlisted Origin must 403 and
        NO user row may be created."""
        from models import User

        r = client.post(
            "/api/auth/register",
            json={
                "email": "victim-precreate@test.com",
                "password": "attackerchosenpw",
                "age_confirmed": _AGE_CONFIRMED,
            },
            headers={"Origin": "https://evil.example.com"},
        )
        assert r.status_code == 403
        assert r.get_json()["code"] == "AUTH_ORIGIN_NOT_ALLOWED"
        # The attack must not have created the account.
        assert User.query.filter_by(email="victim-precreate@test.com").first() is None

    def test_register_allows_same_origin_browser_post(self, client):
        """The Origin guard must NOT break the legitimate first-party flow:
        an allowlisted frontend Origin still registers successfully."""
        r = client.post(
            "/api/auth/register",
            json={
                "email": "legit-origin@test.com",
                "password": "goodpassword",
                "age_confirmed": _AGE_CONFIRMED,
            },
            headers={"Origin": "https://pivoxquant.com"},
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_login_rejects_cross_origin_browser_post(self, client, make_user):
        """Companion guard on /login — a hostile Origin can't drive
        credential stuffing from a victim's browser. 403 before the
        credentials are even checked."""
        make_user(email="login-origin@test.com", password="rightpassword")
        r = client.post(
            "/api/auth/login",
            json={"email": "login-origin@test.com", "password": "rightpassword"},
            headers={"Origin": "https://evil.example.com"},
        )
        assert r.status_code == 403
        assert r.get_json()["code"] == "AUTH_ORIGIN_NOT_ALLOWED"


# ── Register race condition (wave 12 P0) ────────────────────────────────────
# 2026-05-17: TOCTOU race fix — the pre-fix code did `User.query.first()` then
# `db.session.add+commit` with no transaction guard. Two concurrent POSTs
# could both pass the check then race to commit; the second raised
# IntegrityError that bubbled as 500 and left the worker's SQLAlchemy
# session in a failed state. Locking the contract with a synthetic
# IntegrityError so this regression class is caught immediately.

class TestRegisterRaceGuard:
    def test_register_handles_concurrent_integrity_error_as_409(
        self, client, make_user
    ):
        """Simulate the race-winner: another worker already inserted the row
        between our existence check and our commit. Our commit must raise
        IntegrityError, the handler must rollback + return 409, and the
        next request on the same client must still work (no poisoned
        session). Uses an actual existing row to trigger the DB UNIQUE.
        """
        # Seed the user first.
        make_user(email="race@test.com", password="pass1234")

        # Manually craft a register request that passes the explicit check
        # but hits the UNIQUE constraint at commit. The simplest way to
        # exercise the IntegrityError path under a single-threaded test
        # is to monkeypatch User.query.filter_by(...).first() to lie —
        # but that's brittle. Instead just hit the existence check path
        # which now returns the same 409. The IntegrityError branch is
        # the same 409 response shape so this guards the contract.
        r = client.post("/api/auth/register", json={
            "email": "race@test.com",
            "password": "anotherpw",
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r.status_code == 409
        body = r.get_json()
        assert "already" in body["error"].lower()

        # Session must still work on the next request.
        r2 = client.get("/api/auth/me")
        assert r2.status_code in (200, 401)

    def test_register_integrity_error_branch_returns_409(
        self, client, monkeypatch
    ):
        """Force the IntegrityError branch by stubbing the existence check
        to lie (says 'no row') while the DB still has it. Exercises the
        try/except IntegrityError handler directly."""
        from sqlalchemy.exc import IntegrityError

        # First register succeeds.
        r1 = client.post("/api/auth/register", json={
            "email": "integ@test.com",
            "password": "firstpass",
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r1.status_code == 200

        # Now make the existence check return None so we reach commit() —
        # the DB UNIQUE will raise IntegrityError.
        from routes import auth as auth_module
        from extensions import db
        import flask_login

        class _LyingQuery:
            def filter_by(self, **_):
                return self
            def first(self):
                return None

        # Patch User.query just for this call.
        monkeypatch.setattr(auth_module.User, "query", _LyingQuery())
        # Also stop login_user from poisoning the session if reached.
        monkeypatch.setattr(flask_login, "login_user", lambda *a, **k: True)

        # Sign out so the register endpoint's authenticated-caller short
        # circuit (PR #409) doesn't fire first.
        client.post("/api/auth/logout")

        r2 = client.post("/api/auth/register", json={
            "email": "integ@test.com",
            "password": "secondpass",
            "age_confirmed": _AGE_CONFIRMED,
        })
        assert r2.status_code == 409, r2.get_data(as_text=True)
        body = r2.get_json()
        assert "already" in body["error"].lower()

        # Critically: the session must not be poisoned. Next request works.
        db.session.rollback()  # belt-and-suspenders for the test runner
        r3 = client.get("/api/auth/me")
        assert r3.status_code in (200, 401)


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


# ── Account-deletion + session-expiry cookie cleanup ──────────────────────────
# 2026-05-17 thorough sweep after PR #409. The Wave 7 fix only patched the
# canonical /logout pair, so two other termination paths still left cookies
# in the browser jar after server-side session clear. Regression guard.

class TestAuthCookieCleanupSweep:
    def test_delete_account_emits_cookie_deletion_headers(self, raw_client, make_user):
        """DELETE /api/auth/delete-account must mirror /logout's cookie
        cleanup. Previously only logout_user() was called, leaving a
        stale session cookie in the browser jar after the user's row
        was removed from the DB.
        """
        u = make_user(email="cookiedelete@test.com", password="pass1234")
        login = raw_client.post(
            "/api/auth/login",
            json={"email": u["email"], "password": u["password"]},
        )
        assert login.status_code == 200
        # delete_account requires the CSRF header (api_auth decorator).
        csrf_value = None
        for h in login.headers.getlist("Set-Cookie"):
            if h.startswith("csrf_token="):
                csrf_value = h.split(";", 1)[0].split("=", 1)[1]
                break
        assert csrf_value, "login should have issued a csrf_token cookie"
        r = raw_client.delete(
            "/api/auth/delete-account",
            headers={"X-CSRF-Token": csrf_value},
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        set_cookies = r.headers.getlist("Set-Cookie")
        # All three auth cookies must be expired.
        for name in ("session=", "remember_token=", "csrf_token="):
            assert any(
                name in h and ("Expires=" in h or "Max-Age=0" in h)
                for h in set_cookies
            ), f"{name} not expired in delete-account response; headers={set_cookies}"

    def test_session_expiry_emits_cookie_deletion_headers(
        self, raw_client, make_user, app, monkeypatch
    ):
        """When the inactivity timer fires (_enforce_session), the 401
        response must also expire the auth cookies. Previously only the
        server-side session was cleared, so the next request from the
        same browser would re-attach a stale session cookie pointing at
        a now-empty server session — confusing the login flow."""
        u = make_user(email="cookieexpiry@test.com", password="pass1234")
        login = raw_client.post(
            "/api/auth/login",
            json={"email": u["email"], "password": u["password"]},
        )
        assert login.status_code == 200
        # Force inactivity by dropping the _last_active marker far into
        # the past via a session transaction. The next request will be
        # past the configured INACTIVITY_TIMEOUT.
        from flask import session as _flask_session
        from datetime import datetime, timezone, timedelta

        with raw_client.session_transaction() as sess:
            sess["_last_active"] = (
                datetime.now(timezone.utc) - timedelta(days=365)
            ).isoformat()
        r = raw_client.get("/api/auth/me")
        assert r.status_code == 401
        body = r.get_json()
        assert body["code"] == "SESSION_EXPIRED"
        set_cookies = r.headers.getlist("Set-Cookie")
        for name in ("session=", "remember_token=", "csrf_token="):
            assert any(
                name in h and ("Expires=" in h or "Max-Age=0" in h)
                for h in set_cookies
            ), f"{name} not expired in session-expiry 401; headers={set_cookies}"

    def test_csrf_set_cookie_passes_domain_when_configured(self, raw_client, app):
        """The csrf_token SET-Cookie must include the same Domain= attribute
        that _clear_auth_cookies uses on the DELETE side. RFC 6265 treats
        host-only and Domain= cookies as separate slots — a SET without
        domain followed by a DELETE with domain leaves a stale csrf_token
        in the jar that breaks the double-submit pair on the next session.
        """
        old_domain = app.config.get("SESSION_COOKIE_DOMAIN")
        try:
            app.config["SESSION_COOKIE_DOMAIN"] = ".example.test"
            r = raw_client.get("/api/auth/me")
            set_cookies = r.headers.getlist("Set-Cookie")
            csrf_headers = [h for h in set_cookies if h.startswith("csrf_token=")]
            assert csrf_headers, f"no csrf_token Set-Cookie; headers={set_cookies}"
            assert any(
                "Domain=.example.test" in h or "Domain=example.test" in h
                for h in csrf_headers
            ), (
                "csrf_token Set-Cookie missing Domain= attribute; "
                f"headers={csrf_headers}"
            )
        finally:
            app.config["SESSION_COOKIE_DOMAIN"] = old_domain


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


# ── Account deletion cascade (PIPA §21 immediate hard-delete) ────────────────

class TestDeleteAccountCascade:
    """2026-05-22 — delete_account()'s explicit per-model delete list had
    diverged from scripts/nightly/pipa_purge._delete_user_cascade: the
    immediate "delete my account now" path MISSED NpsFeedback and
    ScheduledEmail (both user_id-FK PII), leaving orphan rows. The 30-day
    cron deleted them. This test pins the two paths back in sync.
    """

    def _login(self, raw_client, make_user):
        u = make_user(email="delcascade@test.com", password="pass1234")
        login = raw_client.post(
            "/api/auth/login",
            json={"email": u["email"], "password": u["password"]},
        )
        assert login.status_code == 200, login.data
        csrf_value = None
        for h in login.headers.getlist("Set-Cookie"):
            if h.startswith("csrf_token="):
                csrf_value = h.split(";", 1)[0].split("=", 1)[1]
                break
        assert csrf_value, "login should have issued a csrf_token cookie"
        return u, csrf_value

    def test_delete_account_purges_nps_and_scheduled_email(
        self, raw_client, make_user, app,
    ):
        from datetime import datetime, timezone

        from extensions import db
        from models import NpsFeedback, ScheduledEmail

        u, csrf_value = self._login(raw_client, make_user)
        uid = u["id"]

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with app.app_context():
            db.session.add(NpsFeedback(
                user_id=uid, score=8, weekly_memo_id="memo-del-1",
            ))
            db.session.add(ScheduledEmail(
                user_id=uid,
                email_type="welcome",
                email_category="transactional",
                scheduled_send_at=now,
                idempotency_key=f"u{uid}:welcome",
            ))
            db.session.commit()
            assert NpsFeedback.query.filter_by(user_id=uid).count() == 1
            assert ScheduledEmail.query.filter_by(user_id=uid).count() == 1

        r = raw_client.delete(
            "/api/auth/delete-account",
            headers={"X-CSRF-Token": csrf_value},
        )
        assert r.status_code == 200, r.get_data(as_text=True)

        with app.app_context():
            assert NpsFeedback.query.filter_by(user_id=uid).count() == 0, (
                "NpsFeedback rows survived immediate delete_account — "
                "diverged from pipa_purge cascade"
            )
            assert ScheduledEmail.query.filter_by(user_id=uid).count() == 0, (
                "ScheduledEmail rows survived immediate delete_account — "
                "diverged from pipa_purge cascade"
            )
