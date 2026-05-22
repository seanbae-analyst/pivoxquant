"""
tests/test_security.py — CSRF, Rate Limit, Auth, Injection guards
===================================================================
These are P0 tests. A single failure here = real user data at risk.
"""


# ── CSRF Protection (double-submit cookie) ──────────────────────────────────

class TestCSRFProtection:
    def test_authenticated_mutation_without_csrf_header_returns_403(
        self, raw_client, make_user,
    ):
        """After login, a state-changing request without X-CSRF-Token must 403."""
        u = make_user(email="csrf@test.com", password="mypass123")
        # Login — this also sets the session AND the csrf cookie.
        login = raw_client.post("/api/auth/login", json={
            "email": u["email"], "password": u["password"],
        })
        assert login.status_code == 200

        # PUT /api/portfolio/capital without any CSRF header — should 403.
        r = raw_client.put("/api/portfolio/capital", json={"capital_usd": 500})
        assert r.status_code == 403
        body = r.get_json()
        assert body.get("code") in ("CSRF_MISSING", "CSRF_MISMATCH")

    def test_csrf_header_without_cookie_returns_403(self, raw_client, make_user):
        """CSRF header alone (no matching cookie) must not bypass."""
        u = make_user(email="csrf2@test.com", password="goodpass")
        raw_client.post("/api/auth/login", json={
            "email": u["email"], "password": u["password"],
        })
        # Delete the csrf cookie, then send the header.
        raw_client.delete_cookie("csrf_token")
        r = raw_client.put(
            "/api/portfolio/capital",
            json={"capital_usd": 100},
            headers={"X-CSRF-Token": "some.fake.token"},
        )
        # Either CSRF_MISSING (no cookie) or CSRF_MISMATCH (injected ≠ new)
        assert r.status_code == 403

    def test_unauthenticated_write_bypasses_csrf(self, raw_client):
        """Unauthenticated requests skip CSRF (by design — no session to fix)."""
        # POST /api/auth/register is a legitimate unauth mutation. Birthdate
        # included so we exercise the success path (CSRF, not §22 ⑥).
        r = raw_client.post("/api/auth/register", json={
            "email": "bypass@test.com", "password": "pwpwpw",
            "birthdate": "1990-06-15",
        })
        # Should NOT be 403 CSRF — either 200 (new user) or 409 (existing).
        assert r.status_code not in (403,), (
            f"Unauthenticated register hit CSRF block: {r.data!r}"
        )


# ── Rate Limiting ───────────────────────────────────────────────────────────

class TestRateLimit:
    def test_auth_rate_limit_triggers_429(self, raw_client, enable_rate_limit):
        """auth_rate_limit = 5/min. 6th login attempt in a minute → 429."""
        # Intentionally wrong credentials to avoid successful login that
        # would rotate session/cookies mid-loop.
        for _ in range(5):
            raw_client.post("/api/auth/login", json={
                "email": "nobody@test.com", "password": "wrong",
            })
        r = raw_client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "wrong",
        })
        assert r.status_code == 429
        body = r.get_json()
        assert "retry" in body["error"].lower() or "too many" in body["error"].lower()


# ── Session / Auth ──────────────────────────────────────────────────────────

class TestSessionAuth:
    def test_accessing_protected_endpoint_without_login_returns_401(self, client):
        """/api/portfolio requires auth."""
        r = client.get("/api/portfolio")
        assert r.status_code == 401

    def test_session_fixation_defense_on_login(self, raw_client, make_user):
        """Session ID should rotate on login (session.clear())."""
        u = make_user(email="fix@test.com", password="goodpass")

        # Pre-login session (trigger creation).
        raw_client.get("/api/auth/me")
        pre_session = None
        for c in raw_client._cookies.values():
            if c.key == "session":
                pre_session = c.value
                break

        raw_client.post("/api/auth/login", json={
            "email": u["email"], "password": u["password"],
        })
        post_session = None
        for c in raw_client._cookies.values():
            if c.key == "session":
                post_session = c.value
                break

        # If both cookies exist, they MUST differ.
        if pre_session and post_session:
            assert pre_session != post_session, (
                "CRITICAL: Session ID unchanged across login (session fixation)."
            )


# ── Inactivity timeout cookie cleanup (Fix 2, 2026-05-22) ───────────────────

class TestInactivityCookieCleanup:
    """Fix 2: inactivity logout on a NON-/api/ path must clear auth cookies.

    Previously the remember_token cookie was only cleared inside the
    ``if request.path.startswith('/api/')`` branch, so for a rendered HTML
    path the server-side session was cleared but the browser kept the
    remember_token — and the next /api/ request silently re-authenticated,
    defeating the inactivity timeout. We now clear cookies for BOTH path
    classes.
    """

    @staticmethod
    def _remember_token_cleared(response) -> bool:
        """True iff the response carries a Set-Cookie expiring remember_token."""
        for header, value in response.headers:
            if header.lower() != "set-cookie":
                continue
            if value.startswith("remember_token=") and (
                "Max-Age=0" in value
                or "max-age=0" in value
                or "Expires=Thu, 01 Jan 1970" in value
                or "01-Jan-1970" in value
            ):
                return True
        return False

    def _login_then_expire(self, raw_client, make_user):
        u = make_user(email="inactive@test.com", password="goodpass1")
        login = raw_client.post("/api/auth/login", json={
            "email": u["email"], "password": u["password"],
        })
        assert login.status_code == 200, login.data
        # Force the session's last-active timestamp far enough into the past
        # to exceed _INACTIVITY_TIMEOUT (2h) on the next request.
        from datetime import datetime, timezone, timedelta
        with raw_client.session_transaction() as sess:
            sess["_last_active"] = (
                datetime.now(timezone.utc) - timedelta(hours=5)
            ).isoformat()
        return u

    def test_non_api_path_inactivity_clears_remember_cookie(
        self, raw_client, make_user
    ):
        """A non-/api/ GET after the inactivity window must clear the cookie
        AND redirect (rendered-page flow continues client-side)."""
        self._login_then_expire(raw_client, make_user)
        # follow_redirects=False so we inspect the redirect + Set-Cookie itself.
        r = raw_client.get("/some-html-page", follow_redirects=False)
        assert r.status_code in (301, 302), (
            f"expected redirect on inactivity logout, got {r.status_code}"
        )
        assert "session_expired" in r.headers.get("Location", "")
        assert self._remember_token_cleared(r), (
            "remember_token cookie was NOT cleared on non-API inactivity logout "
            "(Fix 2 regression — cookie would re-authenticate next /api/ call)"
        )

    def test_api_path_inactivity_still_returns_401_json(
        self, raw_client, make_user
    ):
        """The /api/ branch must keep its JSON-401 behaviour (unchanged)."""
        self._login_then_expire(raw_client, make_user)
        r = raw_client.get("/api/portfolio", follow_redirects=False)
        assert r.status_code == 401
        assert r.get_json().get("code") == "SESSION_EXPIRED"
        assert self._remember_token_cleared(r)


# ── Injection / Input validation ────────────────────────────────────────────

class TestInjectionGuards:
    def test_sql_injection_in_email_is_safely_handled(self, client):
        """SQLAlchemy parameterization should neutralize raw SQL payloads."""
        payload = "admin'--@test.com"
        r = client.post("/api/auth/login", json={
            "email": payload, "password": "x' OR '1'='1",
        })
        # Must be a clean 401, not a 500 or an unexpected 200.
        assert r.status_code == 401, (
            f"SQL injection attempt produced unexpected {r.status_code}: {r.data!r}"
        )

    def test_xss_payload_in_name_is_stored_as_literal(self, client):
        """XSS payloads must round-trip as literal text (never executed)."""
        payload = "<script>alert('xss')</script>"
        r = client.post("/api/auth/register", json={
            "email": "xss@test.com",
            "password": "goodpass",
            "name": payload,
            "birthdate": "1990-06-15",
        })
        assert r.status_code == 200
        data = r.get_json()
        # Value should be stored verbatim (not HTML-stripped),
        # and of course not executed. Flask's jsonify escapes it for JSON.
        assert data["user"]["name"] == payload


# ── Security response headers ───────────────────────────────────────────────

class TestSecurityHeaders:
    def test_permissions_policy_header_blocks_sensors_and_payment_self(self, client):
        """Permissions-Policy must lock down camera/mic/geo/usb/sensors;
        payment is allowed only for self (Stripe checkout 향후 호환).
        interest-cohort=() opts out of FLoC.
        Frontend (next.config.ts) 헤더와 정합."""
        r = client.get("/api/health")
        assert r.status_code == 200
        pp = r.headers.get("Permissions-Policy", "")
        for directive in (
            "camera=()",
            "microphone=()",
            "geolocation=()",
            "payment=(self)",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()",
            "interest-cohort=()",
        ):
            assert directive in pp, (
                f"Permissions-Policy missing {directive!r}; got: {pp!r}"
            )

    def test_baseline_security_headers_present(self, client):
        """Defense in depth — 기존 보안 헤더 회귀 방지."""
        r = client.get("/api/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in r.headers.get("Content-Security-Policy", "")

    def test_csp_script_src_is_none(self, client):
        """2026-05-10 (H1): backend CSP must lock script-src to 'none'.
        Backend serves only JSON + fully static HTML (artifacts share /
        admin preview / email preferences). Any future template change
        that introduces inline scripts would silently break in browsers
        — caught here so the regression is loud, not silent."""
        r = client.get("/api/health")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "script-src 'none'" in csp, (
            f"CSP must declare script-src 'none' (no 'unsafe-inline', "
            f"no CDN allow-list); got: {csp!r}"
        )
        # Defense-in-depth: the legacy CDN allow-list and 'unsafe-inline'
        # MUST NOT come back through a copy-paste merge.
        assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0], (
            f"script-src must not contain 'unsafe-inline'; got: {csp!r}"
        )
        assert "cdn.tailwindcss.com" not in csp, (
            f"script-src must not whitelist cdn.tailwindcss.com; got: {csp!r}"
        )
