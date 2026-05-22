"""Regression tests for tier-judgement consistency (FIX 1/2/3).

Background
----------
`models.User.effective_tier` and `routes.decorators._TIER_RANK` recognise the
Companion / owner tiers `premium_plus` (rank 3) and `founding_lifetime`
(rank 4), both of which outrank `premium` (rank 2). Three code paths used to
test membership against narrower literals and silently excluded those top
tiers:

  FIX 1  artifact cron fan-out  — every `_PAID_TIERS` literal omitted
         premium_plus / founding_lifetime, so the highest-paying / owner
         accounts received *no* scheduled artifacts.
  FIX 2  routes/profile.update_profile compared `subscription_tier == "free"`
         directly, ignoring DEV_*_EMAILS env overrides.
  FIX 3  routes/ai._earnings_tone_tier_ok returned `tier in ("pro","premium")`,
         blocking founding_lifetime / premium_plus.

These tests pin the fixed behaviour.
"""
from __future__ import annotations

import importlib

import pytest


# All 15 artifact services that gate cron recipients on _PAID_TIERS.
_ARTIFACT_SERVICE_MODULES = [
    "weekly_memo",
    "earnings_prebrief",
    "credit_rating",
    "burn_rate",
    "dd_checklist",
    "kpi_dashboard",
    "self_audit",
    "risk_board",
    "year_end_letter",
    "capital_allocation",
    "insider_mirror",
    "quarterly_self_report",
    "monthly_finance",
    "portfolio_segment",
    "dividend_income",
]


# ── FIX 1: artifact cron fan-out includes top tiers ────────────────────────

@pytest.mark.parametrize("mod_name", _ARTIFACT_SERVICE_MODULES)
def test_artifact_paid_tiers_include_top_tiers(mod_name):
    """Every artifact service's _PAID_TIERS must cover founding_lifetime &
    premium_plus, otherwise those users miss all scheduled artifacts."""
    mod = importlib.import_module(f"services.artifacts.{mod_name}_service")
    paid = getattr(mod, "_PAID_TIERS")
    assert "founding_lifetime" in paid, f"{mod_name}: founding_lifetime dropped"
    assert "premium_plus" in paid, f"{mod_name}: premium_plus dropped"
    # premium must always remain (no accidental downgrade of base coverage).
    assert "premium" in paid, f"{mod_name}: premium dropped"


def test_shared_tier_sets():
    """The two canonical shared sets behave as documented."""
    from services.artifacts._tiers import (
        PAID_TIERS_PREMIUM_AND_UP,
        PAID_TIERS_PRO_AND_UP,
    )
    for s in (PAID_TIERS_PRO_AND_UP, PAID_TIERS_PREMIUM_AND_UP):
        assert {"premium", "premium_plus", "founding_lifetime"} <= s
    # pro is included only in the PRO_AND_UP set.
    assert "pro" in PAID_TIERS_PRO_AND_UP
    assert "pro" not in PAID_TIERS_PREMIUM_AND_UP


def test_founding_user_included_in_artifact_query(app, make_user):
    """A founding_lifetime user is selected by the weekly-memo recipient
    filter, where previously they were excluded."""
    from extensions import db
    from models import User
    from services.artifacts.weekly_memo_service import _PAID_TIERS

    make_user(email="founder@test.com", tier="founding_lifetime")
    make_user(email="freebie@test.com", tier="free")

    with app.app_context():
        rows = (
            db.session.query(User)
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )
        emails = {u.email for u in rows}
        assert "founder@test.com" in emails
        assert "freebie@test.com" not in emails


# ── FIX 2: update_profile honours effective_tier, not raw column ───────────

def test_update_profile_unlimited_for_founding_via_env(app, client, make_user, monkeypatch):
    """A user whose stored tier is 'free' but who is in DEV_FOUNDING_EMAILS
    gets unlimited profile changes (env override respected)."""
    monkeypatch.setenv("DEV_FOUNDING_EMAILS", "envfound@test.com")

    from extensions import db
    from models import User

    user = make_user(email="envfound@test.com", tier="free")
    # Exhaust the free-tier change budget so the gate would normally trip.
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.profile_changes_left = 0
        db.session.commit()
        assert u.effective_tier == "founding_lifetime"

    login = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert login.status_code == 200

    resp = client.put("/api/profile", json={
        "answers": {"risk_tolerance": 8},
        "profile_type": "growth",
    })
    # The PROFILE_CHANGE_LIMIT 403 must NOT fire for the override account.
    # (No InvestmentProfile exists, so the request proceeds past the gate and
    # returns 404 PROFILE_NOT_FOUND — which proves the gate was bypassed.)
    assert b"PROFILE_CHANGE_LIMIT" not in resp.data, resp.data
    assert resp.status_code != 403, resp.data


def test_update_profile_still_limits_free_user(app, client, make_user):
    """A genuine free user with no env override is still capped (no regression
    that accidentally opens the gate for everyone)."""
    from extensions import db
    from models import User

    user = make_user(email="reallyfree@test.com", tier="free")
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.profile_changes_left = 0
        db.session.commit()

    login = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert login.status_code == 200

    resp = client.put("/api/profile", json={
        "answers": {"risk_tolerance": 8},
        "profile_type": "growth",
    })
    assert resp.status_code == 403
    assert b"PROFILE_CHANGE_LIMIT" in resp.data


# ── FIX 3: earnings-tone gate allows top tiers ─────────────────────────────

@pytest.mark.parametrize("tier", ["pro", "premium", "premium_plus", "founding_lifetime"])
def test_earnings_tone_tier_ok_allows_paid(app, make_user, tier):
    from routes.ai import _earnings_tone_tier_ok
    from extensions import db
    from models import User

    user = make_user(email=f"{tier}@test.com", tier=tier)
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert _earnings_tone_tier_ok(u) is True


def test_earnings_tone_tier_ok_blocks_free(app, make_user):
    from routes.ai import _earnings_tone_tier_ok
    from extensions import db
    from models import User

    user = make_user(email="freetone@test.com", tier="free")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert _earnings_tone_tier_ok(u) is False


def test_earnings_tone_tier_ok_founding_via_env(app, make_user, monkeypatch):
    """founding_lifetime granted purely through DEV_FOUNDING_EMAILS passes."""
    monkeypatch.setenv("DEV_FOUNDING_EMAILS", "tonefound@test.com")
    from routes.ai import _earnings_tone_tier_ok
    from extensions import db
    from models import User

    user = make_user(email="tonefound@test.com", tier="free")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.effective_tier == "founding_lifetime"
        assert _earnings_tone_tier_ok(u) is True
