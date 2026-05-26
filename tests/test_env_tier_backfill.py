"""Regression: _do_migrations backfills DB subscription_tier for env-override
accounts (DEV_FOUNDING_EMAILS / DEV_PREMIUM_EMAILS).

Cron artifact fan-out filters on the DB ``subscription_tier`` column; the
runtime ``effective_tier`` property is never written there, so owner/tester
override accounts were excluded from scheduled artifacts. The boot-time
backfill upgrades matching emails in the DB (upgrade-only, never downgrades a
real Stripe tier).
"""

import app as app_module
from extensions import db
from models import User


def _mk(app, email, tier="free"):
    with app.app_context():
        u = User(email=email, subscription_tier=tier, oauth_provider="google")
        db.session.add(u)
        db.session.commit()
        return u.id


def test_backfill_upgrades_founding_and_premium(app, monkeypatch):
    fid = _mk(app, "owner@pivoxquant.com", "free")
    pid = _mk(app, "tester@pivoxquant.com", "free")
    nid = _mk(app, "normal@pivoxquant.com", "free")
    monkeypatch.setenv("DEV_FOUNDING_EMAILS", "owner@pivoxquant.com")
    monkeypatch.setenv("DEV_PREMIUM_EMAILS", "tester@pivoxquant.com")
    with app.app_context():
        app_module._do_migrations()
        assert db.session.get(User, fid).subscription_tier == "founding_lifetime"
        assert db.session.get(User, pid).subscription_tier == "premium"
        # untouched account stays free
        assert db.session.get(User, nid).subscription_tier == "free"


def test_backfill_never_downgrades_real_paid_tier(app, monkeypatch):
    # A real Stripe premium user who is ALSO in DEV_PREMIUM_EMAILS keeps premium
    # (same rank — no change); but if in DEV_FOUNDING it upgrades to founding.
    keep_id = _mk(app, "paid@pivoxquant.com", "premium")
    up_id = _mk(app, "paid2@pivoxquant.com", "premium")
    monkeypatch.setenv("DEV_PREMIUM_EMAILS", "paid@pivoxquant.com")
    monkeypatch.setenv("DEV_FOUNDING_EMAILS", "paid2@pivoxquant.com")
    with app.app_context():
        app_module._do_migrations()
        assert db.session.get(User, keep_id).subscription_tier == "premium"      # unchanged
        assert db.session.get(User, up_id).subscription_tier == "founding_lifetime"  # upgraded


def test_backfill_noop_when_env_unset(app, monkeypatch):
    uid = _mk(app, "plain@pivoxquant.com", "free")
    monkeypatch.delenv("DEV_FOUNDING_EMAILS", raising=False)
    monkeypatch.delenv("DEV_PREMIUM_EMAILS", raising=False)
    with app.app_context():
        app_module._do_migrations()
        assert db.session.get(User, uid).subscription_tier == "free"
