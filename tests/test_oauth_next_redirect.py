"""tests/test_oauth_next_redirect.py — 로그인 후 딥링크(``?next=``) 보존.

2026-09-29: 콜백은 ``request.args.get("next")`` 를 읽었지만, 그 요청은 Google /
Kakao 가 보내는 리다이렉트라 ``next`` 가 실릴 수 없다 — 딥링크는 항상 사라지고
/mirror 로 떨어졌다. 이제 로그인 시작 라우트가 받은 ``next`` 를 서명된 state
(``ref`` 가 이미 타는 그 payload) 에 실어 보내고, 콜백이 거기서 꺼낸다.
open redirect 방어는 ``_safe_next`` 가 시작·콜백 양쪽에서 한다.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from routes import auth as auth_mod

ORIGIN = "http://localhost:3000"


def _state_from_login(raw_client, provider, query):
    """시작 라우트를 돌리고, 공급자에게 넘긴 state 를 가로채 돌려준다."""
    fake_provider = MagicMock()
    fake_provider.authorize_redirect.return_value = ("", 302)
    fake_oauth = SimpleNamespace(**{provider: fake_provider})
    env = {"KAKAO_CLIENT_ID": "test-kakao"} if provider == "kakao" else {}
    with patch.object(auth_mod, "oauth", fake_oauth), \
            patch.dict("os.environ", env):
        raw_client.get(f"/api/auth/{provider}{query}")
    assert fake_provider.authorize_redirect.called
    return fake_provider.authorize_redirect.call_args.kwargs["state"]


def _payload(app, state):
    with app.test_request_context("/"):
        return auth_mod._state_serializer().loads(state)


def _drive_google(raw_client, state, *, sub, email):
    fake_google = MagicMock()
    fake_google.authorize_access_token.return_value = {
        "userinfo": {"sub": sub, "email": email, "email_verified": True,
                     "name": "N"},
    }
    with patch.object(auth_mod, "oauth", SimpleNamespace(google=fake_google)):
        return raw_client.get(f"/api/auth/google/callback?state={state}")


def _drive_kakao(raw_client, state, *, kid, email):
    fake_kakao = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {
        "id": kid,
        "kakao_account": {"email": email, "is_email_verified": True,
                          "profile": {"nickname": "닉"}},
    }
    fake_kakao.get.return_value = resp
    with patch.object(auth_mod, "oauth", SimpleNamespace(kakao=fake_kakao)):
        return raw_client.get(f"/api/auth/kakao/callback?state={state}")


def _confirmed_user(app, **kw):
    from extensions import db
    from models import User
    with app.app_context():
        u = User(name="N", age_confirmed_at=datetime(2026, 9, 19), **kw)
        db.session.add(u)
        db.session.commit()


class TestStateCarriesNext:
    def test_google_login_puts_safe_next_in_state(self, app, raw_client):
        state = _state_from_login(raw_client, "google", "?next=/journal?tab=2")
        assert _payload(app, state).get("nx") == "/journal?tab=2"

    def test_open_redirect_next_is_not_carried(self, app, raw_client):
        for bad in ("//evil.example", "https://evil.example/x", "evil"):
            state = _state_from_login(raw_client, "google", f"?next={bad}")
            nx = _payload(app, state).get("nx")
            assert nx in (None, "/mirror"), (bad, nx)

    def test_kakao_login_puts_next_in_state(self, app, raw_client):
        state = _state_from_login(raw_client, "kakao", "?next=/pre-trade")
        assert _payload(app, state).get("nx") == "/pre-trade"


class TestCallbackHonoursNext:
    def test_google_returning_user_lands_on_next(self, app, raw_client):
        _confirmed_user(app, email="nx-g@example.com", google_id="g-nx-1",
                        oauth_provider="google")
        state = _state_from_login(raw_client, "google", "?next=/journal")
        r = _drive_google(raw_client, state, sub="g-nx-1", email="nx-g@example.com")
        assert r.status_code in (301, 302)
        assert r.headers["Location"] == f"{ORIGIN}/journal"

    def test_google_new_user_finalize_keeps_next(self, app, raw_client):
        state = _state_from_login(raw_client, "google", "?next=/portfolio")
        r = _drive_google(raw_client, state, sub="g-nx-new", email="nx-new@example.com")
        loc = urlparse(r.headers["Location"])
        assert loc.path == "/signup/oauth-finalize"
        assert parse_qs(loc.query).get("next") == ["/portfolio"]

    def test_kakao_returning_user_lands_on_next(self, app, raw_client):
        _confirmed_user(app, email="nx-k@example.com", kakao_id="880001",
                        oauth_provider="kakao")
        state = _state_from_login(raw_client, "kakao", "?next=/pre-trade")
        r = _drive_kakao(raw_client, state, kid=880001, email="nx-k@example.com")
        assert r.headers["Location"] == f"{ORIGIN}/pre-trade"

    def test_callback_query_next_is_ignored(self, app, raw_client):
        """콜백 쿼리의 next 는 공급자 밖에서 붙일 수 있는 값이다 — 믿지 않는다."""
        _confirmed_user(app, email="nx-q@example.com", google_id="g-nx-q",
                        oauth_provider="google")
        state = _state_from_login(raw_client, "google", "")
        fake_google = MagicMock()
        fake_google.authorize_access_token.return_value = {
            "userinfo": {"sub": "g-nx-q", "email": "nx-q@example.com",
                         "email_verified": True},
        }
        with patch.object(auth_mod, "oauth", SimpleNamespace(google=fake_google)):
            r = raw_client.get(
                f"/api/auth/google/callback?state={state}&next=/settings")
        assert r.headers["Location"] == f"{ORIGIN}/mirror"
