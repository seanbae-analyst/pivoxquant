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
    # Global marketing/transactional email opt-out (정통망법 §50 compliance).
    # Honoured by every artefact email service in services/artifacts/* —
    # when True the _send_email path returns early before contacting the
    # provider. Distinct from `email_opt_out_earnings` (per-channel) so
    # users can mute *all* email or just the time-sensitive earnings
    # channel. Default False keeps existing users on the current
    # behaviour. Managed via migration 021_email_opt_out.
    email_opt_out          = db.Column(db.Boolean, default=False,
                                        nullable=False, server_default="0")
    # 정통망법 §50 ① marketing-consent proof of opt-in.
    # ``email_opt_out`` (above) is a boolean kill-switch honoured by every
    # email sender; the columns below capture the *evidentiary record* of
    # the user's consent decision, which is what the act actually requires
    # the sender to retain. Storing both timestamps separately (rather than
    # a single boolean) preserves history when a user opts in, opts out,
    # then opts in again — every state transition is recoverable.
    #
    #   marketing_consent_at         : timestamp when the user explicitly
    #                                  opted in (NULL = never consented).
    #   marketing_consent_revoked_at : timestamp of the most recent
    #                                  revocation (NULL = never revoked,
    #                                  or revoked then re-consented).
    #
    # Effective consent state == (marketing_consent_at is not None) AND
    # (marketing_consent_revoked_at is None OR
    #  marketing_consent_revoked_at < marketing_consent_at).
    #
    # Managed via migration 023_marketing_consent.
    marketing_consent_at         = db.Column(db.DateTime, nullable=True)
    marketing_consent_revoked_at = db.Column(db.DateTime, nullable=True)
    # PIPA §28-8 (개인정보보호법, 2024-09 시행) — 국외이전 별도 동의 타임스탬프.
    # Anthropic PBC (미국, Claude API), Stripe Inc. (미국), Vercel/Railway (미국)
    # 으로의 개인정보 국외이전에 대한 *명시적 별도* 동의가 §28-8 의무이며,
    # privacy-ko.md L189 의 "가입 시 간주 동의" 문구만으로는 요건을 충족하지 못한다.
    # `cross_border_consent_at` 이 NULL 이면 동의 미수령(국외이전 차단 신호),
    # 값이 채워지면 그 시점에 별도 체크박스 제출이 있었음을 입증한다.
    # 철회 시 `cross_border_consent_revoked_at` 에 시각을 기록하고 신규 추론은
    # 차단한다. Managed via migration 024_cross_border_consent.
    cross_border_consent_at = db.Column(db.DateTime, nullable=True)
    cross_border_consent_revoked_at = db.Column(db.DateTime, nullable=True)
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

        Two comma-separated env vars override the stored `subscription_tier`,
        in priority order (highest tier wins, never downgrades):

          DEV_FOUNDING_EMAILS  → "founding_lifetime"  (full access incl. Companion)
          DEV_PREMIUM_EMAILS   → "premium"            (legacy, pre-Companion)

        This is a dev/admin backdoor for owner accounts and invited testers.
        Stripe billing state remains the source of truth — these only flip
        runtime entitlement, not the stored column.
        """
        email = (self.email or "").lower()
        if email:
            founding_raw = os.environ.get("DEV_FOUNDING_EMAILS", "") or ""
            if founding_raw:
                founding = {e.strip().lower() for e in founding_raw.split(",") if e.strip()}
                if email in founding:
                    return "founding_lifetime"
            premium_raw = os.environ.get("DEV_PREMIUM_EMAILS", "") or ""
            if premium_raw:
                premium = {e.strip().lower() for e in premium_raw.split(",") if e.strip()}
                if email in premium:
                    return "premium"
        return self.subscription_tier or "free"
