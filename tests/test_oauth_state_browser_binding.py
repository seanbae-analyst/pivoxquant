"""tests/test_oauth_state_browser_binding.py — OAuth login-CSRF defence.

2026-10-09: the HMAC-signed OAuth ``state`` proved that *we* minted it, not
that *this browser* started the flow, and its ``k`` nonce was never checked.
An attacker could start a login on their own account, stop before the
callback, and send a victim to ``/api/auth/<p>/callback?code=…&state=…`` —
logging the victim into the attacker's account (login CSRF).

Now the login-start route sets a one-time, HttpOnly, SameSite=Lax cookie
holding ``payload["k"]`` and the callback requires it (hmac.compare_digest)
before it touches the token exchange, then expires it.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from routes import auth as auth_mod

ORIGIN = "http://localhost:3000"


# ── helpers ──────────────────────────────────────────────────────────────────

def _start(raw_client, provider):
    """Hit the real login-start route; return (response, state handed to the IdP)."""
    fake_provider = MagicMock()
    fake_provider.authorize_redirect.return_value = ("", 302)
    env = {"KAKAO_CLIENT_ID": "test-kakao"} if provider == "kakao" else {}
    with patch.object(auth_mod, "oauth", SimpleNamespace(**{provider: fake_provider})), \
            patch.dict("os.environ", env):
        resp = raw_client.get(f"/api/auth/{provider}", headers={"Referer": f"{ORIGIN}/login"})
    state = fake_provider.authorize_redirect.call_args.kwargs["state"]
    return resp, state


def _k(app, state):
    with app.test_request_context("/"):
        return auth_mod._state_serializer().loads(state)["k"]


def _cookie_name(app, provider):
    with app.test_request_context("/"):
        return auth_mod._oauth_bind_cookie_name(provider)


def _bind_set_cookie(resp, name):
    headers = [h for h in resp.headers.getlist("Set-Cookie") if h.startswith(f"{name}=")]
    assert len(headers) == 1, resp.headers.getlist("Set-Cookie")
    return headers[0]


def _callback(raw_client, provider, state):
    """Drive the real callback with only the IdP token exchange faked.

    Returns (response, fake_provider) so a test can tell whether the state
    check let the request reach ``authorize_access_token``.
    """
    fake = MagicMock()
    if provider == "google":
        fake.authorize_access_token.return_value = {
            "userinfo": {"sub": "g-bind-1", "email": "bind@example.com",
                         "email_verified": True, "name": "B"},
        }
    else:
        fake.authorize_access_token.return_value = {"access_token": "t"}
        me = MagicMock()
        me.raise_for_status.return_value = None
        me.json.return_value = {
            "id": 770001,
            "kakao_account": {"email": "bind-k@example.com", "is_email_verified": True,
                              "profile": {"nickname": "닉"}},
        }
        fake.get.return_value = me
    with patch.object(auth_mod, "oauth", SimpleNamespace(**{provider: fake})):
        resp = raw_client.get(
            f"/api/auth/{provider}/callback?state={state}",
            headers={"Referer": f"{ORIGIN}/login"},
        )
    return resp, fake


def _is_state_mismatch(resp):
    loc = urlparse(resp.headers.get("Location", ""))
    return resp.status_code == 302 and loc.path == "/login" and \
        parse_qs(loc.query).get("error") == ["state_mismatch"]


# ── login start sets the binding cookie ──────────────────────────────────────

@pytest.mark.parametrize("provider", ["google", "kakao"])
def test_start_sets_httponly_lax_binding_cookie(app, raw_client, provider):
    resp, state = _start(raw_client, provider)
    name = _cookie_name(app, provider)
    header = _bind_set_cookie(resp, name)
    attrs = [a.strip().lower() for a in header.split(";")]
    assert header.split(";")[0] == f"{name}={_k(app, state)}"
    assert "httponly" in attrs
    assert "samesite=lax" in attrs
    assert "path=/" in attrs
    assert f"max-age={auth_mod._OAUTH_STATE_MAX_AGE}" in attrs
    # CLAUDE.md trap 15 — never a Domain attribute (host-only cookie).
    assert not any(a.startswith("domain=") for a in attrs)


def test_secure_mode_uses_host_prefix_and_secure_flag(app, raw_client, monkeypatch):
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", True)
    resp, _state = _start(raw_client, "google")
    header = _bind_set_cookie(resp, "__Host-pq_oauth_bind_google")
    attrs = [a.strip().lower() for a in header.split(";")]
    assert "secure" in attrs and "path=/" in attrs
    assert not any(a.startswith("domain=") for a in attrs)


# ── callback rejects a state this browser did not start ──────────────────────

@pytest.mark.parametrize("provider", ["google", "kakao"])
def test_valid_state_without_cookie_is_rejected(app, raw_client, provider):
    """The attack: a valid, unexpired state minted for someone else's browser."""
    _resp, state = _start(raw_client, provider)
    raw_client.delete_cookie(_cookie_name(app, provider))
    resp, fake = _callback(raw_client, provider, state)
    assert _is_state_mismatch(resp)
    fake.authorize_access_token.assert_not_called()


@pytest.mark.parametrize("provider", ["google", "kakao"])
def test_valid_state_with_mismatched_cookie_is_rejected(app, raw_client, provider):
    _resp, state = _start(raw_client, provider)
    # The victim's own (unrelated) login-start cookie — different k.
    raw_client.set_cookie(_cookie_name(app, provider), "not-the-k-of-this-state")
    resp, fake = _callback(raw_client, provider, state)
    assert _is_state_mismatch(resp)
    fake.authorize_access_token.assert_not_called()


def test_other_providers_cookie_does_not_bind(app, raw_client):
    """A Kakao binding cookie must not vouch for a Google state with the same k."""
    _resp, state = _start(raw_client, "google")
    k = _k(app, state)
    raw_client.delete_cookie(_cookie_name(app, "google"))
    raw_client.set_cookie(_cookie_name(app, "kakao"), k)
    resp, fake = _callback(raw_client, "google", state)
    assert _is_state_mismatch(resp)
    fake.authorize_access_token.assert_not_called()


# ── matching cookie passes, and is single-use ────────────────────────────────

@pytest.mark.parametrize("provider", ["google", "kakao"])
def test_matching_cookie_passes_state_check(app, raw_client, provider):
    _resp, state = _start(raw_client, provider)
    resp, fake = _callback(raw_client, provider, state)
    assert not _is_state_mismatch(resp)
    fake.authorize_access_token.assert_called_once()


@pytest.mark.parametrize("provider", ["google", "kakao"])
def test_callback_expires_cookie_so_state_is_single_use(app, raw_client, provider):
    _resp, state = _start(raw_client, provider)
    name = _cookie_name(app, provider)
    resp, _fake = _callback(raw_client, provider, state)
    header = _bind_set_cookie(resp, name)
    attrs = [a.strip().lower() for a in header.split(";")]
    assert header.split(";")[0] == f"{name}="
    assert "max-age=0" in attrs
    assert not any(a.startswith("domain=") for a in attrs)
    assert raw_client.get_cookie(name) is None
    # Replaying the same (still unexpired, still validly signed) state fails.
    replay, fake2 = _callback(raw_client, provider, state)
    assert _is_state_mismatch(replay)
    fake2.authorize_access_token.assert_not_called()


def test_failed_callback_also_expires_cookie(app, raw_client):
    """Even a rejected (tampered) state consumes the browser's binding cookie."""
    _resp, state = _start(raw_client, "google")
    name = _cookie_name(app, "google")
    resp, _fake = _callback(raw_client, "google", state + "x")
    assert _is_state_mismatch(resp)
    assert "max-age=0" in _bind_set_cookie(resp, name).lower()
