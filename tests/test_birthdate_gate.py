"""tests/test_birthdate_gate.py — PIPA §22 ⑥ age-verification gate.

Regression coverage for the defense-in-depth birthdate gate
(`app.birthdate_gate_blocks` + `app._require_birthdate` before_request).

Threat closed: an OAuth signup is provisioned (login_user) BEFORE the
birthdate is captured, so the frontend can POST it to /api/auth/oauth-finalize.
Pre-fix, a direct API caller (curl) could skip the browser interstitial and
use every /api feature — and flip onboarding_completed=True — without ever
confirming they are 14+.

Two layers verified here:
1. The pure predicate `birthdate_gate_blocks` (whitelist + /api scoping).
2. The wired `before_request` gate (via the conftest test app, which mirrors
   create_app) — a NULL-birthdate authed user is 403'd on a feature endpoint
   but the whitelist (oauth-finalize / me / logout / callbacks / delete /
   health) stays reachable, and a normal birthdate user is untouched.
"""
from __future__ import annotations

import pytest

from app import birthdate_gate_blocks, BIRTHDATE_GATE_WHITELIST


# ── 1. Pure predicate ────────────────────────────────────────────────────────

def test_predicate_blocks_authed_null_birthdate_on_feature_api():
    assert birthdate_gate_blocks("/api/profile/onboarding", True, None) is True
    assert birthdate_gate_blocks("/api/signals", True, None) is True
    # trailing slash normalized
    assert birthdate_gate_blocks("/api/signals/", True, None) is True


def test_predicate_allows_authed_with_birthdate():
    from datetime import date
    assert birthdate_gate_blocks("/api/signals", True, date(1990, 1, 1)) is False


def test_predicate_allows_unauthenticated():
    # Unauthenticated callers are handled by api_auth / public routes.
    assert birthdate_gate_blocks("/api/signals", False, None) is False


def test_predicate_ignores_non_api_paths():
    assert birthdate_gate_blocks("/", True, None) is False
    assert birthdate_gate_blocks("/login", True, None) is False
    assert birthdate_gate_blocks("/signup/oauth-finalize", True, None) is False


@pytest.mark.parametrize("path", sorted(BIRTHDATE_GATE_WHITELIST))
def test_predicate_whitelist_always_allowed(path):
    # Even an authed NULL-birthdate user must reach every whitelisted route.
    assert birthdate_gate_blocks(path, True, None) is False
    # trailing-slash variants too
    assert birthdate_gate_blocks(path + "/", True, None) is False


def test_whitelist_contains_essential_escape_routes():
    # Guard against an accidental deletion that would lock fresh OAuth users
    # out entirely (no way to set birthdate / log out / be seen by frontend).
    for required in (
        "/api/auth/oauth-finalize",  # only route that writes birthdate
        "/api/auth/me",              # frontend reads birthdate_required
        "/api/auth/logout",
        "/api/logout",
        "/api/auth/google/callback",
        "/api/auth/kakao/callback",
    ):
        assert required in BIRTHDATE_GATE_WHITELIST, required


# ── 2. Wired gate (integration via conftest test app) ────────────────────────

def _login(client, user):
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_null_birthdate_user_blocked_on_feature_endpoint(client, make_user):
    """The core bypass: authed but birthdate NULL → 403 on any /api feature."""
    user = make_user(email="nullbd@test.com", birthdate=None)
    _login(client, user)

    # /api/auth/me is whitelisted → still works (frontend needs it).
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["birthdate_required"] is True

    # Any feature endpoint is blocked with BIRTHDATE_REQUIRED.
    r = client.get("/api/profile/persona")
    assert r.status_code == 403
    assert r.get_json()["code"] == "BIRTHDATE_REQUIRED"


def test_null_birthdate_user_cannot_complete_onboarding(client, make_user):
    """PIPA §22 ⑥ — direct-API onboarding bypass closed (global gate)."""
    user = make_user(email="nullbd2@test.com", birthdate=None)
    _login(client, user)

    r = client.post("/api/profile/onboarding", json={"answers": {}})
    assert r.status_code == 403
    assert r.get_json()["code"] == "BIRTHDATE_REQUIRED"


def test_oauth_finalize_reachable_for_null_birthdate_user(client, make_user):
    """The birthdate-writing route MUST stay open (whitelist) or no fresh
    OAuth user could ever escape the half-provisioned state."""
    from datetime import date
    user = make_user(email="finalize@test.com", birthdate=None)
    _login(client, user)

    adult = date(2000, 1, 1).isoformat()
    # 2026-09-17 P1 — 필수 동의 3종도 함께 보내야 통과한다
    # (게이트 자체의 회귀 테스트는 tests/test_oauth_finalize_consents.py).
    r = client.post("/api/auth/oauth-finalize", json={
        "birthdate": adult,
        "consents": {"terms": True, "non_advisory": True, "cross_border": True},
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["ok"] is True

    # After finalize, the previously-blocked feature endpoint works.
    r2 = client.get("/api/profile/persona")
    assert r2.status_code != 403


def test_logout_reachable_for_null_birthdate_user(client, make_user):
    user = make_user(email="logoutnull@test.com", birthdate=None)
    _login(client, user)
    r = client.post("/api/auth/logout")
    # Logout must not be gated (200 success or origin-guarded, never 403 gate).
    assert r.status_code != 403
    if r.status_code == 403:  # explicit: never the birthdate gate
        assert r.get_json().get("code") != "BIRTHDATE_REQUIRED"


def test_normal_user_unaffected(client, make_user):
    """Regression guard: a user WITH a birthdate sails through (no false block)."""
    user = make_user(email="normal@test.com")  # default adult birthdate
    _login(client, user)
    r = client.get("/api/profile/persona")
    assert r.status_code != 403
