"""tests/test_age_gate.py — PIPA §22 ⑥ age-confirmation gate.

Regression coverage for the defense-in-depth age gate
(`app.age_gate_blocks` + `app._require_age_confirmation` before_request).

Threat closed: an OAuth signup is provisioned (login_user) BEFORE the user
confirms they are 14+, so the frontend can POST the consent stack to
/api/auth/oauth-finalize. Without the gate a direct API caller (curl) could
skip the browser interstitial and use every /api feature — and flip
onboarding_completed=True — without ever confirming their age.

2026-09-19: the evidence switched from a date of birth to the "만 14세 이상"
self-declaration stamp (``users.age_confirmed_at``). ``users.birthdate`` is
kept as legacy evidence — a birthdate-era user passes without re-prompt.

Two layers verified here:
1. The pure predicate `age_gate_blocks` (whitelist + /api scoping).
2. The wired `before_request` gate (via the conftest test app, which mirrors
   create_app) — an unconfirmed authed user is 403'd on a feature endpoint
   but the whitelist (oauth-finalize / me / logout / callbacks / delete /
   health) stays reachable, and a confirmed or legacy user is untouched.
"""
from __future__ import annotations

from datetime import date

import pytest

from app import age_gate_blocks, AGE_GATE_WHITELIST


# ── 1. Pure predicate ────────────────────────────────────────────────────────

def test_predicate_blocks_authed_unconfirmed_on_feature_api():
    assert age_gate_blocks("/api/profile/onboarding", True, False) is True
    assert age_gate_blocks("/api/signals", True, False) is True
    # trailing slash normalized
    assert age_gate_blocks("/api/signals/", True, False) is True


def test_predicate_allows_authed_confirmed():
    assert age_gate_blocks("/api/signals", True, True) is False


def test_predicate_allows_unauthenticated():
    # Unauthenticated callers are handled by api_auth / public routes.
    assert age_gate_blocks("/api/signals", False, False) is False


def test_predicate_ignores_non_api_paths():
    assert age_gate_blocks("/", True, False) is False
    assert age_gate_blocks("/login", True, False) is False
    assert age_gate_blocks("/signup/oauth-finalize", True, False) is False


@pytest.mark.parametrize("path", sorted(AGE_GATE_WHITELIST))
def test_predicate_whitelist_always_allowed(path):
    # Even an authed unconfirmed user must reach every whitelisted route.
    assert age_gate_blocks(path, True, False) is False
    # trailing-slash variants too
    assert age_gate_blocks(path + "/", True, False) is False


def test_whitelist_contains_essential_escape_routes():
    # Guard against an accidental deletion that would lock fresh OAuth users
    # out entirely (no way to confirm age / log out / be seen by frontend).
    for required in (
        "/api/auth/oauth-finalize",  # only OAuth route that writes age_confirmed_at
        "/api/auth/me",              # frontend reads age_confirmation_required
        "/api/auth/logout",
        "/api/logout",
        "/api/auth/google/callback",
        "/api/auth/kakao/callback",
    ):
        assert required in AGE_GATE_WHITELIST, required


# ── 2. User.age_confirmed — the value the gate consumes ─────────────────────

def test_user_age_confirmed_property(app):
    from datetime import datetime
    from models import User
    with app.app_context():
        assert User(email="a@t.com", name="a").age_confirmed is False
        assert User(email="b@t.com", name="b",
                    age_confirmed_at=datetime(2026, 9, 19)).age_confirmed is True
        # Legacy birthdate-era evidence counts on its own.
        assert User(email="c@t.com", name="c",
                    birthdate=date(1990, 1, 1)).age_confirmed is True


# ── 3. Wired gate (integration via conftest test app) ────────────────────────

def _login(client, user):
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_unconfirmed_user_blocked_on_feature_endpoint(client, make_user):
    """The core bypass: authed but unconfirmed → 403 on any /api feature."""
    user = make_user(email="unconfirmed@test.com", age_confirmed=False)
    _login(client, user)

    # /api/auth/me is whitelisted → still works (frontend needs it).
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    payload = me.get_json()["user"]
    assert payload["age_confirmation_required"] is True
    assert payload["birthdate_required"] is True  # deprecated alias, same value

    # Any feature endpoint is blocked with AGE_CONFIRMATION_REQUIRED.
    r = client.get("/api/profile/persona")
    assert r.status_code == 403
    body = r.get_json()
    assert body["code"] == "AGE_CONFIRMATION_REQUIRED"
    assert body["error"] == "Age confirmation required."
    assert body["error_kr"] == "만 14세 이상 확인이 필요합니다."


def test_unconfirmed_user_cannot_complete_onboarding(client, make_user):
    """PIPA §22 ⑥ — direct-API onboarding bypass closed (global gate)."""
    user = make_user(email="unconfirmed2@test.com", age_confirmed=False)
    _login(client, user)

    r = client.post("/api/profile/onboarding", json={"answers": {}})
    assert r.status_code == 403
    assert r.get_json()["code"] == "AGE_CONFIRMATION_REQUIRED"


def test_in_route_onboarding_guard_matches_gate_code(app, client, make_user, monkeypatch):
    """routes/profile.py keeps its own fail-fast behind the global gate.
    Unhook the global before_request gate for this test so the 403 can only
    come from the in-route guard — and prove it uses the same code."""
    user = make_user(email="unconfirmed3@test.com", age_confirmed=False)
    _login(client, user)
    hooks = app.before_request_funcs.get(None, [])
    kept = [f for f in hooks if f.__name__ != "_require_age_confirmation_test"]
    assert len(kept) == len(hooks) - 1, "conftest gate hook not found by name"
    monkeypatch.setitem(app.before_request_funcs, None, kept)

    r = client.post("/api/profile/onboarding", json={"answers": {}})
    assert r.status_code == 403
    body = r.get_json()
    assert body["code"] == "AGE_CONFIRMATION_REQUIRED"
    assert body["error_kr"] == "온보딩 전에 만 14세 이상 확인이 필요합니다."


def test_oauth_finalize_reachable_for_unconfirmed_user(client, make_user):
    """The age-writing route MUST stay open (whitelist) or no fresh OAuth
    user could ever escape the half-provisioned state."""
    user = make_user(email="finalize@test.com", age_confirmed=False)
    _login(client, user)

    # 2026-09-19 — 필수 동의 4종 (age 포함) 을 보내야 통과한다
    # (게이트 자체의 회귀 테스트는 tests/test_oauth_finalize_consents.py).
    r = client.post("/api/auth/oauth-finalize", json={
        "consents": {"terms": True, "non_advisory": True,
                     "cross_border": True, "age": True},
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["ok"] is True
    assert r.get_json()["user"]["age_confirmation_required"] is False

    # After finalize, the previously-blocked feature endpoint works.
    r2 = client.get("/api/profile/persona")
    assert r2.status_code != 403


def test_logout_reachable_for_unconfirmed_user(client, make_user):
    user = make_user(email="logoutnull@test.com", age_confirmed=False)
    _login(client, user)
    r = client.post("/api/auth/logout")
    # Logout must not be gated (200 success or origin-guarded, never 403 gate).
    if r.status_code == 403:  # explicit: never the age gate
        assert r.get_json().get("code") != "AGE_CONFIRMATION_REQUIRED"


def test_normal_user_unaffected(client, make_user):
    """Regression guard: a confirmed user sails through (no false block)."""
    user = make_user(email="normal@test.com")  # default: age_confirmed_at set
    _login(client, user)
    r = client.get("/api/profile/persona")
    assert r.status_code != 403


def test_legacy_birthdate_user_passes_without_reprompt(client, make_user):
    """Birthdate-era user: ``birthdate`` set, ``age_confirmed_at`` NULL. The
    2026-09-19 switch must not lock them out or send them back through the
    interstitial."""
    user = make_user(email="legacy@test.com", age_confirmed=False,
                     birthdate=date(1990, 1, 1))
    _login(client, user)

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    payload = me.get_json()["user"]
    assert payload["age_confirmation_required"] is False
    assert payload["birthdate_required"] is False
    assert "birthdate" not in payload  # raw value never leaves the server

    r = client.get("/api/profile/persona")
    assert r.status_code != 403
