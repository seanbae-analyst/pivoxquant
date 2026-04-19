import os
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id               = db.Column(db.Integer,     primary_key=True)
    email            = db.Column(db.String(120),  unique=True, nullable=False)
    password_hash    = db.Column(db.String(200),  nullable=True)
    name             = db.Column(db.String(100),  default="")
    oauth_provider   = db.Column(db.String(20),   nullable=True)  # google, kakao, or NULL (email)
    google_id        = db.Column(db.String(100),  unique=True, nullable=True)
    kakao_id         = db.Column(db.String(100),  unique=True, nullable=True)
    avatar_url       = db.Column(db.String(500),  nullable=True)
    available_capital     = db.Column(db.Float, default=0.0)
    available_capital_krw = db.Column(db.Float, default=0.0)
    risk_profile          = db.Column(db.String(20), default="balanced")
    profile_changes_left  = db.Column(db.Integer, default=3)
    subscription_tier     = db.Column(db.String(10), default="free")
    stripe_customer_id    = db.Column(db.String(100), nullable=True)
    stripe_subscription_id = db.Column(db.String(100), nullable=True)
    subscription_status   = db.Column(db.String(20), default="inactive")
    onboarding_completed  = db.Column(db.Boolean, default=False)
    # Brag Card (MVP #2) — anonymous mode masks ticker names as "A 종목"
    # on shared cards. Default False so existing users keep identified
    # tickers unless they explicitly opt in via /api/artifacts/brag-card/privacy.
    privacy_mode          = db.Column(db.Boolean, default=False)
    # Per-user referral code (viral loop). Kept nullable so the column
    # can be added via idempotent ALTER TABLE without backfill — the
    # legacy UserReferral side-table remains the authoritative store
    # until every row is backfilled. `unique=True` is expressed via a
    # unique index in the migration (SQLite can't add UNIQUE inline).
    referral_code         = db.Column(db.String(16), nullable=True)
    # Earnings Pre-Brief (MVP #3) per-channel email opt-out. Distinct from
    # the global `email_opt_out` so users can mute time-sensitive earnings
    # alerts without silencing every artefact email. Default False so
    # existing users continue to receive Pre-Briefs until they explicitly
    # opt out. Managed via migration 009_earnings_prebrief.
    email_opt_out_earnings = db.Column(db.Boolean, default=False,
                                        nullable=False, server_default="0")
    created_at       = db.Column(db.DateTime,     default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    positions = db.relationship("Position", backref="user", lazy=True,
                                cascade="all, delete-orphan")
    alerts    = db.relationship("Alert",    backref="user", lazy=True,
                                cascade="all, delete-orphan")
    investment_profile = db.relationship("InvestmentProfile", backref="user",
                                         uselist=False, lazy=True)
    broker_connections = db.relationship("BrokerConnection", backref="user",
                                         lazy=True)

    def set_pw(self, pw):
        self.password_hash = generate_password_hash(
            pw, method="pbkdf2:sha256", salt_length=16
        )

    def chk_pw(self, pw):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, pw)

    @property
    def effective_tier(self) -> str:
        """Tier after applying dev overrides.

        Any email listed in `DEV_PREMIUM_EMAILS` (comma-separated env var) is
        treated as Premium regardless of their stored `subscription_tier`.
        This is a dev/admin backdoor for owner accounts and invited testers —
        it never downgrades, only upgrades. The stored column remains the
        source of truth for Stripe billing state.
        """
        raw = os.environ.get("DEV_PREMIUM_EMAILS", "") or ""
        if raw and self.email:
            allow = {e.strip().lower() for e in raw.split(",") if e.strip()}
            if self.email.lower() in allow:
                return "premium"
        return self.subscription_tier or "free"
