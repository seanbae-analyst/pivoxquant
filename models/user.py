import os
from datetime import datetime, timezone
import sqlalchemy as sa
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


# ── Notification preference matrix (settings v2) ─────────────────────────────
# Frontend SoT: ``frontend/src/components/settings/v2/notifications-matrix.tsx``
# (the ``EVENTS`` array). These three constants MUST stay byte-for-byte aligned
# with the frontend EVENTS ids + per-channel defaults — the GET/PUT
# ``/api/notifications/preferences`` contract merges stored values over these
# defaults and always returns all seven events.
NOTIFICATION_CHANNELS: tuple[str, ...] = ("email", "push", "inapp")

# 2026-09-01: was seven ids — weekly_memo, earnings_pre_brief, signal_state,
# risk_breach, pulse_prompt, brag_card, broker_sync_error. Six of them had no
# producer left after the prune, and the seventh (signal_state) died with the
# quant engine, so Settings offered toggles for notifications that could never
# arrive. Meanwhile the two alerts that DO fire — the 52-week range sweep and
# the sector-concentration sweep, both scheduled in app.py — mapped to no event
# id at all, so their toggles did nothing.
#
# These two are the notifications this product actually sends. Stale keys left
# in a user's stored ``notification_prefs`` JSON are simply ignored by
# ``notification_channel_enabled`` below, so no migration is required.
# 2026-09-17: ``monthly_mirror`` joined the two alert sweeps. It is added
# together with its producer — the monthly APScheduler job
# ``ops_monthly_mirror_report`` (services/scheduler/cron_jobs.py) which calls
# ``services.reports_delivery.main`` on the 1st of each month. The "되살리려면
# 발신자부터" rule is satisfied: the sender ships in the same change.
NOTIFICATION_EVENT_IDS: tuple[str, ...] = (
    "price_52w",
    "concentration",
    "monthly_mirror",
)

#: Events whose producer needs a vendor market quote. While
#: ``MARKET_DATA_DISPLAY_ENABLED`` is off, ``app.py::_scheduled_price_alerts``
#: skips their sweep, so nothing can ever send them.
_MARKET_PRICED_EVENT_IDS: frozenset[str] = frozenset({"price_52w"})


def visible_notification_event_ids() -> tuple[str, ...]:
    """The event ids the Settings matrix may SHOW right now.

    Same SoT rule as the 2026-09-01 prune — "실제로 발신되는 것만 노출".
    ``price_52w`` has exactly one producer (``check_52w_highs_lows`` via the
    ``price_alerts_daily`` cron) and that producer is skipped while
    ``MARKET_DATA_DISPLAY_ENABLED`` is off, so leaving its row on screen would
    re-create precisely the dead toggle that prune removed.

    This filters DISPLAY only. ``NOTIFICATION_EVENT_IDS`` stays the full tuple
    and remains the validation vocabulary: a stored ``price_52w`` preference
    is still accepted and persisted, so a user's setting survives the gate
    being flipped back on.
    """
    # Imported lazily — models must not import services at module scope.
    from services.market_display import market_data_display_enabled

    if market_data_display_enabled():
        return NOTIFICATION_EVENT_IDS
    return tuple(
        e for e in NOTIFICATION_EVENT_IDS if e not in _MARKET_PRICED_EVENT_IDS
    )

# ``monthly_mirror`` channel defaults, and why they differ from the two
# sweeps above:
#   * email = False — this one is an explicit opt-in. It attaches a PDF built
#     from the user's own record and arrives unprompted once a month; nobody
#     gets it because we decided they would like it.
#   * push / inapp = False — the two sweeps default those channels on because
#     they HAVE push/in-app producers (services/alert.py maps their alert
#     kinds onto these event ids). The monthly report has exactly one
#     producer, the email cron. Defaulting a channel on with nothing behind it
#     re-creates the dead toggles that the 2026-09-01 prune removed. Flip
#     either to True in the same change that ships its sender, not before.
NOTIFICATION_PREF_DEFAULTS: dict[str, dict[str, bool]] = {
    "price_52w":      {"email": False, "push": True,  "inapp": True},
    "concentration":  {"email": True,  "push": True,  "inapp": True},
    "monthly_mirror": {"email": False, "push": False, "inapp": False},
}


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
    subscription_tier     = db.Column(db.String(32), default="free")  # fits 'founding_lifetime' (17)
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
    # Viral loop — attribution. The referral code of the inviter, captured
    # once at signup from the ``?ref=`` query param (carried through OAuth
    # via the signed state token). Stores the *code string* only — never a
    # raw integer user id (PIPA §29 enumeration guard). Nullable + immutable
    # after first set (attribution must not be rewritable). Managed via
    # migration 045_funnel_events.
    referred_by           = db.Column(db.String(16), nullable=True, index=True)
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
    # 정통망법 §50 ① 정보성 vs 광고성 분리 동의 (Wave D Sub-wave 1, C-S1).
    # ``marketing_consent_at`` (위) 는 통합 1차 게이트로 유지하되, §50 시행령 및
    # KISA 가이드라인이 권고하는 카테고리 분리 동의를 위해 컬럼 4개를 추가한다.
    # application layer 의 ``PIVOX_CS1_CONSENT_ENABLED`` 환경 변수 (default
    # false) 에 게이트되어 변호사 Q-S1 답변 전까지는 dormant. flag=true 로
    # 전환되면 ``services.email.sender.EmailCategory.INFORMATION`` 발송은
    # ``marketing_consent_information_at`` 을 검사하고, MARKETING 발송은
    # ``marketing_consent_marketing_at`` 을 검사한다. TRANSACTIONAL 은 동의
    # 무관 (계정 알림 / 보안 / 결제 영수증). Managed via migration
    # 037_marketing_consent_split.
    marketing_consent_information_at         = db.Column(db.DateTime, nullable=True)
    marketing_consent_information_revoked_at = db.Column(db.DateTime, nullable=True)
    marketing_consent_marketing_at           = db.Column(db.DateTime, nullable=True)
    marketing_consent_marketing_revoked_at   = db.Column(db.DateTime, nullable=True)
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
    # PIPA §22 ⑥ — 만 14세 미만 아동은 법정대리인 동의가 필요하다.
    # PivoxQuant 에는 법정대리인 동의 절차가 없으므로 만 14세 미만 가입을
    # fail-fast 한다.
    #
    # 2026-09-19 — 생년월일 수집을 **중단**했다. 이제 증거는 가입 동의
    # 스택의 "만 14세 이상입니다" 자가선언 체크박스이고, 그 제출 시각을
    # ``age_confirmed_at`` (naive UTC, 다른 동의 타임스탬프와 같은 컨벤션)
    # 에 남긴다. 자가선언의 충분성은 변호사 질문 Q9
    # (docs/legal/legal-audit-2026-06-05.md) 로 아직 열려 있다.
    #
    # ``birthdate`` 컬럼과 그 데이터는 **유지**한다 (삭제 금지 — CLAUDE.md
    # 구조 규칙). 생년월일 시대(2026-05 ~ 2026-09-19)에 가입한 사용자는
    # 이 값이 있으면 재확인 없이 계속 통과한다 (``age_confirmed`` 참조).
    # 새 코드는 이 컬럼에 쓰지 않는다. Managed via migration 031_user_birthdate.
    birthdate = db.Column(db.Date, nullable=True)
    # 만 14세 이상 자가선언 제출 시각. NULL 이면 (그리고 ``birthdate`` 도
    # NULL 이면) 아직 확인 전 — half-provisioned OAuth 계정 또는 레거시.
    # Managed via migration 053_age_self_declaration; 부팅 시
    # ``app._do_migrations`` 의 ``_add_column_if_missing`` 이 prod 안전망.
    age_confirmed_at = db.Column(db.DateTime, nullable=True)
    # Continuous User Simulation (CAUS) Phase 1 격리 플래그.
    # ``docs/specs/continuous-user-sim-spec.md`` Q3 — 시뮬 user 와 실 user
    # 를 단일 BOOLEAN 으로 격리한다. TRUE 인 row 는:
    #   * EmailSender 가 발송 스킵 (정통망법 §50 안전판, 후속 PR)
    #   * Analytics / KPI 쿼리에서 ``WHERE is_simulated = FALSE`` 필터로 제외
    #   * Sentry tag ``user_type=sim`` 분리
    #   * 일요일 04:30 KST cron 이 7일 이상 묵은 로그/artifact truncate
    # 일반 user response 에는 노출하지 않는다 (admin 전용). Managed via
    # migration 032_users_is_simulated.
    is_simulated = db.Column(db.Boolean, nullable=False, default=False,
                              server_default=sa.false())
    # 2026-05-17 wave 12 UX P0 — onboarding partial-save draft slot. Holds an
    # opaque JSON string of whatever the wizard's answer dict shape currently
    # is. Cleared by routes/profile.py:submit_onboarding on completion.
    # NULL means "no draft" (brand-new user or already completed). Managed
    # via migration 035_user_onboarding_draft.
    onboarding_draft_json = db.Column(db.Text, nullable=True)
    # Wave G C-S2 (2026-05-19) — 24h inactive nudge idempotency timestamp.
    # NULL = never nudged. Set by ``scripts/nightly/inactive_nudge_dispatcher``
    # on a successful INFORMATION-class onboarding nudge so subsequent
    # hourly cron runs (and any cron overlap) skip the user. Column is
    # populated only when BOTH ``PIVOX_INACTIVE_NUDGE_ENABLED`` and
    # ``PIVOX_CS1_CONSENT_ENABLED`` are true — until the lawyer's Q-S1
    # answer arrives the column stays NULL for every row. Managed via
    # migration 038_inactive_nudge_sent_at.
    inactive_nudge_sent_at = db.Column(db.DateTime, nullable=True)
    # Wave I C-2 (2026-05-19) — PIPA §21 30-day soft-delete grace period.
    # ``deletion_requested_at`` 이 NOT NULL = "soft delete" 상태:
    #   * 모든 로그인 거부 (auth_bp.login 401)
    #   * 데이터 read API 401 (decorators.api_auth 일치)
    #   * 30일 grace 동안 사용자가 ``POST /api/auth/delete-cancel`` 로 철회 가능
    # ``deleted_at`` 은 ``pipa_purge`` cron 이 hard delete 직전 stamp + commit
    # 하여 "30일 만에 실제 삭제" 증거를 audit log 와 함께 남긴다.
    # Managed via migration 041_user_deletion_request.
    deletion_requested_at = db.Column(db.DateTime, nullable=True)
    deleted_at            = db.Column(db.DateTime, nullable=True)
    # Settings v2 per-event × per-channel notification preferences. NULL means
    # "never customised" → fall back to ``NOTIFICATION_PREF_DEFAULTS``. Stored
    # as a partial dict ({event_id: {channel: bool}}); the GET/PUT
    # ``/api/notifications/preferences`` route merges it over the defaults so
    # the client always sees all seven events. Managed via Alembic migration
    # 043_notification_prefs (+ app.py ``_do_migrations`` self-heal guard).
    notification_prefs    = db.Column(db.JSON, nullable=True)
    # Wave F (2026-05-28) — UI/PDF/email locale preference. "ko" (default) | "en".
    # Server-side source of truth for artifact rendering + scheduled email
    # subject/body language. Frontend cookie ``sp_locale`` syncs into this
    # column via ``PUT /api/profile/locale`` (lib/locale.tsx ↔ routes/profile.py).
    # Managed via migration 046_user_locale + ``_do_migrations`` self-heal.
    locale           = db.Column(db.String(2), nullable=False, server_default="ko", default="ko")
    created_at       = db.Column(db.DateTime,     default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    positions = db.relationship("Position", backref="user", lazy=True,
                                cascade="all, delete-orphan")
    alerts    = db.relationship("Alert",    backref="user", lazy=True,
                                cascade="all, delete-orphan")
    investment_profile = db.relationship("InvestmentProfile", backref="user",
                                         uselist=False, lazy=True)
    broker_connections = db.relationship("BrokerConnection", backref="user",
                                         lazy=True)
    # Support tickets (고객문의센터). delete-orphan so a HARD account delete
    # (PIPA §21 after the 30-day grace) removes the tickets too; soft-delete
    # (deletion_requested_at set, row retained) leaves them intact.
    inquiries = db.relationship("Inquiry", backref="user", lazy=True,
                                cascade="all, delete-orphan")

    def set_pw(self, pw):
        self.password_hash = generate_password_hash(
            pw, method="pbkdf2:sha256", salt_length=16
        )

    def chk_pw(self, pw):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, pw)

    def notification_channel_enabled(self, event_id: str, channel: str) -> bool:
        """Whether *channel* is enabled for *event_id* for this user.

        Resolution order:
          1. Stored ``notification_prefs[event_id][channel]`` if present
             (and a real bool).
          2. ``NOTIFICATION_PREF_DEFAULTS[event_id][channel]`` otherwise.
          3. For an **unknown** ``event_id`` (not in the canonical seven) we
             return ``True`` — fail-open. The enforcement gate must never
             silently swallow a notification just because the caller passed a
             label we don't recognise; that would be a worse failure mode than
             an over-send. Unknown *channel* on a known event likewise → True.
        """
        defaults = NOTIFICATION_PREF_DEFAULTS.get(event_id)
        if defaults is None:
            # Unknown event id — fail-open (never silently mute).
            return True

        stored = self.notification_prefs or {}
        event_stored = stored.get(event_id) if isinstance(stored, dict) else None
        if isinstance(event_stored, dict) and channel in event_stored:
            val = event_stored[channel]
            if isinstance(val, bool):
                return val

        # Fall back to the per-event default; unknown channel → fail-open.
        return defaults.get(channel, True)

    @property
    def age_confirmed(self) -> bool:
        """True iff this user has cleared the PIPA §22 ⑥ (만 14세) gate.

        Two kinds of evidence count, either one is enough:
          * ``age_confirmed_at`` — self-declaration checkbox timestamp
            (the only thing new code writes, since 2026-09-19);
          * ``birthdate`` — legacy value from the birthdate era. Users who
            already supplied one are never re-prompted.
        The API gate (``app.age_gate_blocks``), the serializer
        (``age_confirmation_required``) and the OAuth callbacks all read
        this property so the two columns never drift apart.
        """
        return self.age_confirmed_at is not None or self.birthdate is not None

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

        ── Free-launch flag (LAUNCH_FREE_ALL_TIERS) ─────────────────────────
        2026-05-30: DECISIONS.md ✅ confirms the launch is FREE (Stage 0); the
        3-tier monthly subscription model is ⬛superseded. Per CEO ("PDF
        기능들 싹다 오픈"), every paid Artifact (18 types) + one-way AI is opened
        to all authenticated users by returning "premium" here. Because every
        backend gate (`@require_tier` in routes/decorators.py, the unified
        artifact generate gate in routes/artifacts.py, and serialize_user in
        services/serializers.py → frontend TierGate) reads THIS single
        property, flipping it here opens both backend and frontend in one move.

        Intentional carve-out — Companion stays CLOSED. The Companion gate
        (routes/agent.py `_ENTITLED_PLANS = {premium_plus, founding_lifetime}`)
        requires a strictly-higher tier than "premium" (ranks 3/4 > 2), so
        returning "premium" does NOT unlock the two-way AI chat (§101③ 양방향
        AI 격리). ai-chat is separately isolated behind its own AI_CHAT_ENABLED
        flag and is likewise unaffected.

        Flag is ON by default for the free launch. When Stage 1 paywall lands,
        set LAUNCH_FREE_ALL_TIERS=0 (or "false") to restore the prior logic
        (env override + subscription_tier column) with no code change — the
        original code path below is preserved verbatim.
        """
        # Unset OR empty → default ON. Only an explicit falsy string turns the
        # free launch OFF (Stage 1 paywall). Empty string is treated as unset.
        free_all_raw = os.environ.get("LAUNCH_FREE_ALL_TIERS", "1").strip().lower()
        if free_all_raw == "":
            free_all_raw = "1"
        if free_all_raw not in ("0", "false", "no", "off"):
            return "premium"

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
