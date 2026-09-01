"""Regression tests for the 2026-05-09 P1 backend bug-hunter batch.

Covers three production-surface bugs that were live on the CEO account:

1. ``serialize_user`` / ``/api/auth/me`` — a ``founding_lifetime`` user
   produced by ``DEV_FOUNDING_EMAILS`` was returned with
   ``subscription_status: "inactive"``, which the frontend tier-gate
   (ui/profile-dropdown.tsx) read as "downgrade to FREE". The serializer
   now coerces the status to "active" when the env override promotes the
   stored DB tier, and additionally exposes ``effective_tier`` and
   ``raw_subscription_status`` as additive aliases.

2. ``GET /api/portfolio/summary`` did not emit a ``cashPct`` field,
   leaving the PORTFOLIO header chip stuck on "Cash buffer at —".
   The endpoint now computes the idle-cash share of total equity
   (cash + holdings, USD-unified via the same FX path as totalNav).

3. ``services.alert_service.maybe_generate`` persisted alert messages
   that read "124500.KQ (124500.KQ) — Score …" for KR tickers because
   the upstream snapshot fell back to the ticker as the name. The
   service now re-resolves through ``services.name_resolver`` so the
   stored title carries the human-readable company name when available.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


# ── Bug #4: founding_lifetime user reports active status ──────────────────

class TestServeUserEffectiveTierStatus:
    def test_founding_lifetime_env_override_reports_active(
        self, app, make_user, monkeypatch,
    ):
        """DEV_FOUNDING_EMAILS-promoted user must return status=active."""
        from services.serializers import serialize_user
        from models import User

        email = "ceo-active@test.com"
        make_user(email=email, tier="free")
        monkeypatch.setenv("DEV_FOUNDING_EMAILS", email)

        with app.app_context():
            u = User.query.filter_by(email=email).first()
            payload = serialize_user(u)

        assert payload["subscription_tier"] == "founding_lifetime"
        assert payload["effective_tier"] == "founding_lifetime"
        assert payload["subscription_status"] == "active"
        # Raw column still surfaces for billing reconciliation.
        assert payload["raw_subscription_status"] == "inactive"

    def test_premium_env_override_reports_active(
        self, app, make_user, monkeypatch,
    ):
        from services.serializers import serialize_user
        from models import User

        email = "premium-env@test.com"
        make_user(email=email, tier="free")
        monkeypatch.setenv("DEV_PREMIUM_EMAILS", email)
        # Make sure DEV_FOUNDING_EMAILS doesn't accidentally win
        monkeypatch.delenv("DEV_FOUNDING_EMAILS", raising=False)

        with app.app_context():
            u = User.query.filter_by(email=email).first()
            payload = serialize_user(u)

        assert payload["subscription_tier"] == "premium"
        assert payload["effective_tier"] == "premium"
        assert payload["subscription_status"] == "active"
        assert payload["raw_subscription_status"] == "inactive"

    def test_unpromoted_free_user_keeps_raw_status(
        self, app, make_user, monkeypatch,
    ):
        """No env override → raw status flows through unchanged."""
        from services.serializers import serialize_user
        from models import User

        monkeypatch.delenv("DEV_FOUNDING_EMAILS", raising=False)
        monkeypatch.delenv("DEV_PREMIUM_EMAILS", raising=False)
        email = "regular@test.com"
        make_user(email=email, tier="free")

        with app.app_context():
            u = User.query.filter_by(email=email).first()
            payload = serialize_user(u)

        assert payload["subscription_tier"] == "free"
        assert payload["effective_tier"] == "free"
        # Default DB value remains "inactive" — not promoted.
        assert payload["subscription_status"] == "inactive"
        assert payload["raw_subscription_status"] == "inactive"

    def test_stripe_active_paid_user_unaffected(
        self, app, make_user, monkeypatch,
    ):
        """A genuine Stripe-active premium user keeps their raw status —
        no env-override promotion path runs."""
        from extensions import db
        from services.serializers import serialize_user
        from models import User

        monkeypatch.delenv("DEV_FOUNDING_EMAILS", raising=False)
        monkeypatch.delenv("DEV_PREMIUM_EMAILS", raising=False)
        email = "paid-premium@test.com"
        make_user(email=email, tier="premium")

        with app.app_context():
            u = User.query.filter_by(email=email).first()
            u.subscription_status = "active"
            db.session.commit()
            payload = serialize_user(u)

        assert payload["subscription_tier"] == "premium"
        assert payload["effective_tier"] == "premium"
        assert payload["subscription_status"] == "active"
        assert payload["raw_subscription_status"] == "active"


# ── Bug #5: /api/portfolio/summary cashPct ────────────────────────────────

class TestPortfolioSummaryCashPct:
    def test_summary_emits_cashpct_field(self, client, auth_user):
        """The endpoint must always emit a numeric ``cashPct``."""
        # auth_user fixture seeds default capital (10_000 USD + 1_000_000 KRW)
        # with no positions → cashPct should be 100.
        resp = client.get("/api/portfolio/summary")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "cashPct" in body, "cashPct field must be present"
        assert isinstance(body["cashPct"], (int, float))
        assert 0.0 <= body["cashPct"] <= 100.0

    def test_summary_cashpct_full_cash_no_positions(
        self, client, auth_user,
    ):
        """No positions → 100% cash buffer."""
        resp = client.get("/api/portfolio/summary")
        assert resp.status_code == 200
        body = resp.get_json()
        # All capital sits in cash, NAV is zero → 100.
        assert body["positionCount"] == 0
        assert body["cashPct"] == 100.0

    def test_summary_cashpct_never_negative(
        self, app, client, auth_user, add_position,
    ):
        """cashPct is clamped to [0, 100] regardless of mocked prices."""
        from extensions import db
        from models import User

        with app.app_context():
            u = User.query.filter_by(email=auth_user["email"]).first()
            # Zero out cash: with positions present, cashPct must be 0.
            u.available_capital = 0.0
            u.available_capital_krw = 0.0
            db.session.commit()

        add_position(auth_user["id"], ticker="AAPL", shares=5, avg_cost=100.0)

        resp = client.get("/api/portfolio/summary")
        assert resp.status_code == 200
        body = resp.get_json()
        assert 0.0 <= body["cashPct"] <= 100.0

    def test_summary_legacy_fields_preserved(self, client, auth_user):
        """The new field is additive — every prior field still ships."""
        resp = client.get("/api/portfolio/summary")
        assert resp.status_code == 200
        body = resp.get_json()
        for required in (
            "totalNav", "todayPnl", "todayPnlPct", "unrealized",
            "realizedYtd", "currency", "fxRate", "positionCount",
            "observed_at",
        ):
            assert required in body, f"missing legacy field: {required}"


# ── Bug #11: alert title uses resolved company name ───────────────────────
