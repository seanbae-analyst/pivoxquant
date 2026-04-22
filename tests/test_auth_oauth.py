"""
tests/test_auth_oauth.py — OAuth redirect_uri resolution
========================================================
Verifies `_resolve_frontend_url()` picks the correct origin based on
Referer / Origin / X-Forwarded-Host headers with a strict whitelist so
multi-domain deployments (vercel.app / pivoxquant.com / www.pivoxquant.com)
route OAuth callbacks back to the user's actual frontend.

Background: previously redirect_uri was hard-coded to FRONTEND_URL, so a
user on pivoxquant.vercel.app would have their Kakao/Google callback sent
to pivoxquant.com — and if that domain's DNS was broken, the login 500'd.
"""


from routes.auth import _resolve_frontend_url


class TestResolveFrontendUrl:
    """Exercise origin resolution under realistic header permutations."""

    def test_whitelisted_referrer_wins(self, app):
        """Referer from an allowed origin is returned verbatim."""
        with app.test_request_context(
            "/api/auth/kakao",
            headers={"Referer": "https://pivoxquant.vercel.app/login"},
        ):
            assert _resolve_frontend_url() == "https://pivoxquant.vercel.app"

    def test_whitelisted_referrer_apex(self, app):
        with app.test_request_context(
            "/api/auth/kakao",
            headers={"Referer": "https://pivoxquant.com/login?foo=bar"},
        ):
            assert _resolve_frontend_url() == "https://pivoxquant.com"

    def test_whitelisted_referrer_www(self, app):
        with app.test_request_context(
            "/api/auth/kakao",
            headers={"Referer": "https://www.pivoxquant.com/"},
        ):
            assert _resolve_frontend_url() == "https://www.pivoxquant.com"

    def test_origin_header_used_when_no_referrer(self, app):
        """Without Referer, Origin header drives the decision."""
        with app.test_request_context(
            "/api/auth/kakao",
            headers={"Origin": "https://pivoxquant.vercel.app"},
        ):
            assert _resolve_frontend_url() == "https://pivoxquant.vercel.app"

    def test_x_forwarded_host_used_last(self, app):
        """X-Forwarded-Host + X-Forwarded-Proto produce a full origin."""
        with app.test_request_context(
            "/api/auth/kakao",
            headers={
                "X-Forwarded-Host": "pivoxquant.vercel.app",
                "X-Forwarded-Proto": "https",
            },
        ):
            assert _resolve_frontend_url() == "https://pivoxquant.vercel.app"

    def test_x_forwarded_host_takes_first_in_chain(self, app):
        """XFH can be a comma-separated list — first entry wins."""
        with app.test_request_context(
            "/api/auth/kakao",
            headers={
                "X-Forwarded-Host": "pivoxquant.vercel.app, internal-proxy",
                "X-Forwarded-Proto": "https",
            },
        ):
            assert _resolve_frontend_url() == "https://pivoxquant.vercel.app"

    def test_non_whitelisted_origin_falls_back_to_env(self, app, monkeypatch):
        """Unknown/attacker origin is rejected; FRONTEND_URL used."""
        monkeypatch.setenv("FRONTEND_URL", "https://fallback.example.com")
        with app.test_request_context(
            "/api/auth/kakao",
            headers={"Referer": "https://evil.attacker.com/phish"},
        ):
            assert _resolve_frontend_url() == "https://fallback.example.com"

    def test_no_headers_uses_env_fallback(self, app, monkeypatch):
        """Direct server-side call with no headers: env var wins."""
        monkeypatch.setenv("FRONTEND_URL", "https://fallback.example.com")
        with app.test_request_context("/api/auth/kakao"):
            assert _resolve_frontend_url() == "https://fallback.example.com"

    def test_env_fallback_strips_trailing_slash(self, app, monkeypatch):
        monkeypatch.setenv("FRONTEND_URL", "https://fallback.example.com/")
        with app.test_request_context("/api/auth/kakao"):
            assert _resolve_frontend_url() == "https://fallback.example.com"

    def test_localhost_referrer_allowed_for_dev(self, app):
        with app.test_request_context(
            "/api/auth/kakao",
            headers={"Referer": "http://localhost:3000/login"},
        ):
            assert _resolve_frontend_url() == "http://localhost:3000"

    def test_referrer_beats_non_whitelisted_xfh(self, app):
        """Whitelisted Referer wins even if XFH points at a junk host."""
        with app.test_request_context(
            "/api/auth/kakao",
            headers={
                "Referer": "https://pivoxquant.com/login",
                "X-Forwarded-Host": "evil.attacker.com",
                "X-Forwarded-Proto": "https",
            },
        ):
            assert _resolve_frontend_url() == "https://pivoxquant.com"


class TestKakaoRedirectUriIntegration:
    """End-to-end: /api/auth/kakao's 302 uses the caller's origin."""

    def test_kakao_login_without_client_id_redirects_to_caller_origin(
        self, client, monkeypatch
    ):
        """With no KAKAO_CLIENT_ID the route redirects to /login?error=...
        on the caller's origin — easy integration check without live OAuth."""
        monkeypatch.delenv("KAKAO_CLIENT_ID", raising=False)
        r = client.get(
            "/api/auth/kakao",
            headers={"Referer": "https://pivoxquant.vercel.app/login"},
        )
        # 302 to caller origin, not the configured FRONTEND_URL.
        assert r.status_code in (301, 302)
        assert r.headers["Location"].startswith("https://pivoxquant.vercel.app")
