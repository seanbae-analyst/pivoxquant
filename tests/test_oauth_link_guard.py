"""tests/test_oauth_link_guard.py — Fix 1: OAuth email-collision link guard.

Background (2026-05-22, Fix 1, decision (a))
--------------------------------------------
When an OAuth provider returns an email that matches an EXISTING account but
a NEW provider id (e.g. a Google login whose email equals a Kakao-created
account's email), the old code silently set ``google_id`` / ``kakao_id`` and
logged in — an account-takeover vector if the provider asserts an email it did
not verify.

Both providers reliably expose a verified flag (Google OIDC ``email_verified``,
Kakao ``is_email_verified``), so we implement decision (a): refuse to link when
the incoming email is NOT provider-verified, AND refuse to link onto a
credentialed (password_hash) account. A successful link fires a security email.

These tests prove BOTH:
  1. NORMAL login is untouched — brand-new Google user creates+logs in, and a
     returning user whose google_id already matches logs in. (LOGIN-CRITICAL.)
  2. The guard fires only on the email-collision-new-provider-id branch.

The full-callback tests drive the real ``google_callback`` route end-to-end:
build a valid signed state, patch ``oauth.google.authorize_access_token`` to
return a userinfo dict, and assert the resulting User / redirect.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from routes import auth as auth_mod
from routes.auth import (
    OAuthLinkRefused,
    _email_is_provider_verified,
    _guard_oauth_email_link,
)


# ── Unit: verified-flag parsing ──────────────────────────────────────────────

class TestEmailIsProviderVerified:
    def test_google_explicit_true(self):
        assert _email_is_provider_verified("google", {"email_verified": True}) is True

    def test_google_explicit_false_blocks(self):
        assert _email_is_provider_verified("google", {"email_verified": False}) is False

    def test_google_legacy_verified_email_key(self):
        assert _email_is_provider_verified("google", {"verified_email": False}) is False
        assert _email_is_provider_verified("google", {"verified_email": True}) is True

    def test_google_missing_key_defaults_verified(self):
        # Conservative non-breaking default: only an EXPLICIT False blocks.
        assert _email_is_provider_verified("google", {}) is True

    def test_kakao_explicit_false_blocks(self):
        assert _email_is_provider_verified("kakao", {"is_email_verified": False}) is False

    def test_kakao_explicit_true(self):
        assert _email_is_provider_verified("kakao", {"is_email_verified": True}) is True

    def test_string_false_blocks(self):
        assert _email_is_provider_verified("google", {"email_verified": "false"}) is False


# ── Unit: link guard decision ────────────────────────────────────────────────

class _FakeUser:
    def __init__(self, password_hash=None):
        self.password_hash = password_hash


class TestGuardOauthEmailLink:
    def test_verified_no_password_allows(self):
        # Returns None (no raise) → caller proceeds to link.
        assert _guard_oauth_email_link("google", _FakeUser(), True) is None

    def test_unverified_email_refused(self):
        with pytest.raises(OAuthLinkRefused) as ei:
            _guard_oauth_email_link("google", _FakeUser(), False)
        assert ei.value.reason == "email_unverified"

    def test_password_account_refused_even_if_verified(self):
        with pytest.raises(OAuthLinkRefused) as ei:
            _guard_oauth_email_link("kakao", _FakeUser(password_hash="x"), True)
        assert ei.value.reason == "password_account"


# ── Integration: real google_callback end-to-end ─────────────────────────────

def _signed_state(app, origin="http://localhost:3000"):
    """Build a valid signed state token inside an app context."""
    with app.test_request_context("/"):
        return auth_mod._build_signed_state(
            "google", origin, f"{origin}/api/auth/google/callback"
        )


def _fake_token(*, sub, email, email_verified=True, name="Test User"):
    return {
        "userinfo": {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "name": name,
        }
    }


def _drive_google_callback(app, raw_client, token_dict, *, origin="http://localhost:3000"):
    """Run google_callback with a patched token exchange. Returns the response.

    The test app does not register the live authlib Google client (no
    GOOGLE_CLIENT_ID), so we swap ``auth_mod.oauth`` for a stand-in whose
    ``.google.authorize_access_token()`` returns our fake token dict. Only the
    token-exchange surface the route touches is faked; the rest of the callback
    (state verify, provisioning, guard, login) runs the real code.
    """
    state = _signed_state(app, origin)
    fake_google = MagicMock()
    fake_google.authorize_access_token.return_value = token_dict
    fake_oauth = SimpleNamespace(google=fake_google)
    with patch.object(auth_mod, "oauth", fake_oauth):
        return raw_client.get(
            f"/api/auth/google/callback?state={state}",
            headers={"Referer": f"{origin}/login"},
        )


class TestNormalLoginUntouched:
    """LOGIN-CRITICAL: these MUST pass — they prove login still works."""

    def test_brand_new_google_user_creates_and_logs_in(self, app, raw_client):
        from models import User
        r = _drive_google_callback(
            app, raw_client,
            _fake_token(sub="g-new-1", email="brandnew@example.com"),
        )
        # New user has no age confirmation → redirected to the finalize interstitial,
        # NOT to a login error. The user row must now exist with google_id set.
        assert r.status_code in (301, 302)
        assert "/login?error=" not in r.headers["Location"]
        assert "oauth-finalize" in r.headers["Location"]
        with app.app_context():
            u = User.query.filter_by(email="brandnew@example.com").first()
            assert u is not None
            assert u.google_id == "g-new-1"
            assert u.oauth_provider == "google"

    def test_returning_user_matching_google_id_logs_in(self, app, raw_client):
        from extensions import db
        from models import User
        from datetime import datetime
        # Pre-create a user already linked to this google_id, with the 만 14세
        # self-declaration stamped so the callback redirects to home (full
        # login), not the interstitial.
        with app.app_context():
            u = User(email="returning@example.com", name="Ret",
                     google_id="g-ret-1", oauth_provider="google",
                     age_confirmed_at=datetime(2026, 9, 19, 0, 0, 0))
            db.session.add(u)
            db.session.commit()

        r = _drive_google_callback(
            app, raw_client,
            _fake_token(sub="g-ret-1", email="returning@example.com"),
        )
        assert r.status_code in (301, 302)
        loc = r.headers["Location"]
        assert "/login?error=" not in loc
        assert "oauth-finalize" not in loc  # age confirmed → straight to app

    def test_returning_legacy_birthdate_user_is_not_reprompted(self, app, raw_client):
        """Birthdate-era user (``birthdate`` set, ``age_confirmed_at`` NULL)
        must go straight to the app — the 2026-09-19 switch to
        self-declaration never re-prompts anyone who already supplied a
        date of birth."""
        from extensions import db
        from models import User
        from datetime import date
        with app.app_context():
            u = User(email="legacy-bd@example.com", name="Legacy",
                     google_id="g-legacy-1", oauth_provider="google",
                     birthdate=date(1990, 1, 1))
            db.session.add(u)
            db.session.commit()

        r = _drive_google_callback(
            app, raw_client,
            _fake_token(sub="g-legacy-1", email="legacy-bd@example.com"),
        )
        assert r.status_code in (301, 302)
        loc = r.headers["Location"]
        assert "/login?error=" not in loc
        assert "oauth-finalize" not in loc


class TestEmailCollisionGuard:
    """Fix 1: email matches an existing account but the provider id is new."""

    def test_unverified_email_collision_refused(self, app, raw_client):
        """Existing Kakao account; a Google login asserts the SAME email but
        UNVERIFIED → must refuse to link/login (no takeover)."""
        from extensions import db
        from models import User
        with app.app_context():
            u = User(email="victim@example.com", name="Victim",
                     kakao_id="k-victim-1", oauth_provider="kakao")
            db.session.add(u)
            db.session.commit()
            victim_id = u.id

        r = _drive_google_callback(
            app, raw_client,
            _fake_token(sub="g-attacker-1", email="victim@example.com",
                        email_verified=False),
        )
        assert r.status_code in (301, 302)
        assert "error=oauth_link_refused" in r.headers["Location"]
        # The existing account must be UNCHANGED — google_id NOT set.
        with app.app_context():
            u = User.query.get(victim_id)
            assert u.google_id is None
            assert u.kakao_id == "k-victim-1"

    def test_verified_email_collision_links_and_alerts(self, app, raw_client):
        """Existing account, SAME email, but the incoming Google email IS
        verified → link is allowed AND a security-alert email fires."""
        from extensions import db
        from models import User
        from datetime import datetime
        with app.app_context():
            u = User(email="linkme@example.com", name="Link",
                     kakao_id="k-link-1", oauth_provider="kakao",
                     age_confirmed_at=datetime(2026, 9, 19, 0, 0, 0))
            db.session.add(u)
            db.session.commit()
            uid = u.id

        with patch.object(auth_mod, "_send_oauth_link_alert", return_value=True) as alert:
            r = _drive_google_callback(
                app, raw_client,
                _fake_token(sub="g-link-1", email="linkme@example.com",
                            email_verified=True),
            )
        assert r.status_code in (301, 302)
        assert "/login?error=" not in r.headers["Location"]
        alert.assert_called_once()
        with app.app_context():
            u = User.query.get(uid)
            assert u.google_id == "g-link-1"  # link succeeded

    def test_password_account_collision_refused(self, app, raw_client):
        """Defense-in-depth: never merge a social id onto a password account
        even when the email is verified."""
        from extensions import db
        from models import User
        with app.app_context():
            u = User(email="pwuser@example.com", name="PW")
            u.set_pw("password123")  # non-null password_hash
            db.session.add(u)
            db.session.commit()
            uid = u.id

        r = _drive_google_callback(
            app, raw_client,
            _fake_token(sub="g-pw-1", email="pwuser@example.com",
                        email_verified=True),
        )
        assert r.status_code in (301, 302)
        assert "error=oauth_link_refused" in r.headers["Location"]
        with app.app_context():
            assert User.query.get(uid).google_id is None
