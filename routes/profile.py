"""Investment profile routes: onboarding, get/update profile, questionnaire.

Also hosts the **Living CFO Layer 2** endpoints consumed by
``frontend/src/lib/cfo/hooks.ts``:

    GET  /api/profile/persona
    GET  /api/profile/rolling-window
    POST /api/profile/feedback
    GET  /api/profile/pulse
    POST /api/profile/pulse

All Layer 2 endpoints return HTTP 200 with a degraded-but-valid payload
when the user has no trade history yet — the frontend SWR layer relies
on that contract for first-load UX.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, Response
from flask_login import current_user

from extensions import db
from models import (
    AITwinPortfolio,
    AITwinPosition,
    AITwinTrade,
    AITwinWeeklyReport,
    Alert,
    Artifact,
    ArtifactFeedback,
    AuthEvent,
    BehavioralScore,
    BrokerConnection,
    CheckoutExpiration,
    CompanionWaitlist,
    FunnelEvent,
    Inquiry,
    InvestmentProfile,
    NpsFeedback,
    PersonaSnapshot,
    PortfolioShare,
    Position,
    PositionDDCheck,
    PreTradeReflection,
    PushSubscription,
    ScheduledEmail,
    TradeHistory,
    UserReferral,
    VALID_CADENCES,
    VOTE_CHOICES,
    Watchlist,
    WeeklyPulse,
)
from models.investment_profile import calculate_profile_type
from services.error_responses import api_error
from services.profile import (
    compute_persona_response,
    compute_rolling_response,
    classify_persona_multi,
    explain_persona_classification,
    DRIFT_DISCLAIMER,
    take_snapshot,
    get_history,
    compute_drift,
    detect_significant_drift,
)
from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit, limiter
from services.legal.disclaimers import DISCLAIMER_MIRROR_RETROSPECTIVE_KR

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


# ── Questionnaire (질문 목록) ──────────────────────────────────────────────

QUESTIONNAIRE = [
    {
        "id": "experience_level",
        "question": "How much investment experience do you have?",
        "question_kr": "투자 경험은 어느 정도인가요?",
        "options": [
            {"value": "beginner", "label": "Beginner", "label_kr": "초보 (1년 미만)", "icon": "seedling"},
            {"value": "intermediate", "label": "1-3 years", "label_kr": "1~3년", "icon": "sprout"},
            {"value": "advanced", "label": "3-5 years", "label_kr": "3~5년", "icon": "tree"},
            {"value": "expert", "label": "5+ years", "label_kr": "5년 이상", "icon": "mountain"},
        ],
    },
    {
        "id": "investment_goal",
        "question": "What is your primary investment goal?",
        "question_kr": "주요 투자 목표는?",
        "options": [
            {"value": "preservation", "label": "Capital Preservation", "label_kr": "자산 보존", "icon": "shield"},
            {"value": "income", "label": "Stable Income", "label_kr": "안정적 수익", "icon": "wallet"},
            {"value": "growth", "label": "Growth", "label_kr": "성장", "icon": "trending-up"},
            {"value": "aggressive_growth", "label": "Aggressive Growth", "label_kr": "공격적 성장", "icon": "rocket"},
        ],
    },
    {
        "id": "risk_tolerance",
        "question": "If your portfolio dropped 20%, what would you do?",
        "question_kr": "포트폴리오가 -20% 하락하면?",
        "type": "slider",
        "options": [
            {"value": 2, "label": "Sell Everything", "label_kr": "전량 매도"},
            {"value": 4, "label": "Sell Some", "label_kr": "일부 매도"},
            {"value": 6, "label": "Hold", "label_kr": "유지"},
            {"value": 9, "label": "Buy More", "label_kr": "추가 매수"},
        ],
    },
    {
        "id": "time_horizon",
        "question": "What is your preferred investment horizon?",
        "question_kr": "선호하는 투자 기간은?",
        "options": [
            {"value": "short", "label": "Short-term (< 3 months)", "label_kr": "단기 (~3개월)", "icon": "zap"},
            {"value": "medium", "label": "Medium (3-12 months)", "label_kr": "중기 (3~12개월)", "icon": "clock"},
            {"value": "long", "label": "Long-term (1+ years)", "label_kr": "장기 (1년+)", "icon": "calendar"},
        ],
    },
    {
        "id": "preferred_markets",
        "question": "Which markets are you interested in?",
        "question_kr": "관심 있는 시장은?",
        "options": [
            {"value": "us", "label": "US Only", "label_kr": "미국만", "icon": "flag-us"},
            {"value": "kr", "label": "Korea Only", "label_kr": "한국만", "icon": "flag-kr"},
            {"value": "both", "label": "Both US & Korea", "label_kr": "둘 다", "icon": "globe"},
        ],
    },
    {
        "id": "preferred_sectors",
        "question": "Which sectors interest you? (Select multiple)",
        "question_kr": "관심 있는 섹터는? (복수 선택)",
        "type": "multi",
        "options": [
            {"value": "Technology", "label": "Tech", "label_kr": "기술"},
            {"value": "Healthcare", "label": "Healthcare", "label_kr": "헬스케어"},
            {"value": "Financial Services", "label": "Finance", "label_kr": "금융"},
            {"value": "Energy", "label": "Energy", "label_kr": "에너지"},
            {"value": "Consumer Cyclical", "label": "Consumer", "label_kr": "소비재"},
            {"value": "Industrials", "label": "Industrials", "label_kr": "산업재"},
        ],
    },
    {
        "id": "auto_trade_preference",
        "question": "How do you want to manage trades?",
        "question_kr": "자동 매매에 관심이 있나요?",
        "options": [
            {"value": "manual", "label": "Manual Only", "label_kr": "수동만", "icon": "hand"},
            {"value": "signals", "label": "Signal Alerts", "label_kr": "시그널 알림", "icon": "bell"},
            {"value": "semi_auto", "label": "Semi-Auto", "label_kr": "반자동", "icon": "settings"},
            {"value": "full_auto", "label": "Full Auto", "label_kr": "완전 자동", "icon": "bot"},
        ],
    },
    {
        "id": "daily_time",
        "question": "How much time can you spend on investing daily?",
        "question_kr": "하루에 투자에 쓸 수 있는 시간은?",
        "options": [
            {"value": "minimal", "label": "< 10 minutes", "label_kr": "10분 이하", "icon": "coffee"},
            {"value": "moderate", "label": "30 minutes", "label_kr": "30분", "icon": "clock"},
            {"value": "active", "label": "1+ hours", "label_kr": "1시간 이상", "icon": "monitor"},
        ],
    },
]


@profile_bp.route("/questionnaire")
def get_questionnaire():
    """Return the 20-question v2 questionnaire (falls back to v1 8-question)."""
    try:
        from services.profile.questionnaire import QUESTIONNAIRE_V2
        return jsonify({"questions": QUESTIONNAIRE_V2})
    except ImportError:
        # Fallback to v1 if questionnaire.py not available
        return jsonify({"questions": QUESTIONNAIRE})


# 2026-05-17 wave 12 UX P0 — onboarding partial-save / device handoff.
# Pre-fix the wizard stored progress in localStorage only; a user who
# answered 15 of 20 questions on mobile and then logged in on desktop
# saw an empty wizard. These two endpoints let the frontend round-trip
# the draft through the server every few questions so any signed-in
# device picks up where the last one left off.

_DRAFT_MAX_BYTES = 32 * 1024  # 32KB ceiling — well above the realistic
# answer payload, gives a hard upper bound against pathological clients.


@profile_bp.route("/onboarding/draft", methods=["GET"])
@api_auth
def get_onboarding_draft():
    """Read the current user's saved onboarding draft.

    Returns ``{"draft": null}`` when nothing is saved (brand-new user
    or one who already completed onboarding — the submit handler clears
    the draft on success).
    """
    raw = getattr(current_user, "onboarding_draft_json", None)
    if not raw:
        return jsonify({"draft": None})
    try:
        return jsonify({"draft": json.loads(raw)})
    except (TypeError, ValueError):
        # Corrupt blob (manual DB edit, partial write). Treat as no draft
        # so the wizard restarts cleanly rather than crashing on parse.
        logger.warning(
            "profile.get_onboarding_draft: corrupt JSON for user_id=%s",
            current_user.id,
        )
        return jsonify({"draft": None})


@profile_bp.route("/onboarding/draft", methods=["PUT"])
@api_auth
@general_rate_limit
def save_onboarding_draft():
    """Save / overwrite the current user's onboarding draft.

    Body: ``{"answers": {...}}`` — the wizard's full answer object.
    Empty object is allowed (treat as "reset").
    """
    data = request.get_json(silent=True) or {}
    answers = data.get("answers")
    if answers is None or not isinstance(answers, dict):
        return jsonify({
            "error": "Body must include 'answers' object.",
            "error_kr": "answers 객체가 필요합니다.",
        }), 400

    payload = json.dumps(answers, ensure_ascii=False)
    if len(payload.encode("utf-8")) > _DRAFT_MAX_BYTES:
        return jsonify({
            "error": "Draft payload exceeds 32KB.",
            "error_kr": "임시 저장 데이터가 너무 큽니다.",
        }), 413

    current_user.onboarding_draft_json = payload
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "profile.save_onboarding_draft commit failed user_id=%s",
            current_user.id,
        )
        return api_error(
            en="Failed to save draft. Please try again.",
            kr="임시 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            code="ONBOARDING_DRAFT_SAVE_FAILED", status=500,
        )

    return jsonify({"ok": True, "bytes": len(payload.encode("utf-8"))})


@profile_bp.route("/onboarding", methods=["POST"])
@api_auth
@general_rate_limit
def submit_onboarding():
    """Submit onboarding answers → calculate profile → save → return result."""
    # PIPA §22 ⑥ fail-fast ( double defense behind app._require_birthdate).
    # onboarding_completed must never flip to True for a session whose age
    # was never confirmed — a half-provisioned OAuth user (birthdate NULL)
    # calling this directly would otherwise mark themselves onboarded. The
    # global gate already 403s here, but this in-route guard keeps the
    # invariant local and survives any future whitelist edit.
    if getattr(current_user, "birthdate", None) is None:
        return api_error(
            en="Birthdate confirmation required before onboarding.",
            kr="온보딩 전에 생년월일 확인이 필요합니다.",
            code="BIRTHDATE_REQUIRED", status=403,
        )

    data = request.get_json() or {}
    answers = data.get("answers", {})
    if not isinstance(answers, dict):
        return api_error(
            en="'answers' must be an object.",
            kr="answers 객체가 필요합니다.",
            code="ONBOARDING_INVALID_PAYLOAD", status=400,
        )

    # 2026-05-17 wave D-1 — legal gate. The V2 questionnaire's last block
    # (``legal_confirmations`` multi_required) is the disclaimer wall: age 14+,
    # risk acknowledgment, "past performance ≠ future results", "AI-generated
    # analysis, not licensed financial advice". Pre-fix the route only computed
    # ``legal_confirmed`` and never enforced it, so a client that omitted the
    # block could complete onboarding without confirming the disclaimer — a
    # 자본시장법 §6 / 정통망법 §50 compliance hole. The frontend's "Skip" path
    # (page.tsx ~770) submits ``{}`` and is still allowed; we only reject
    # submissions that include partial answers but omit the legal block.
    # 2026-05-22 — server-side gate hardening (자본시장법 §6 bypass close).
    # Pre-fix, the legal gate only fired for V2-shaped submissions
    # (``is_v2_submission``). A direct API caller could POST v1-style keys
    # (e.g. {"answers": {"experience_level": "beginner",
    # "investment_goal": "growth"}}) → is_v2_submission=False → SKIP the
    # legal gate → onboarding_completed=True without confirming the
    # disclaimer wall. The frontend only ever sends either ``{}`` (skip,
    # page.tsx ~781) or a full V2 payload that ALWAYS carries
    # ``legal_confirmations`` (the wizard's legal step, page.tsx ~668), so
    # any NON-EMPTY submission that lacks ``legal_confirmations`` cannot be
    # a legitimate client request — it's a direct-API gate-bypass. Reject
    # it (400) rather than silently completing onboarding. The empty
    # ``{}`` skip path and proper V2 path are both untouched.
    legal_block = answers.get("legal_confirmations")
    has_legal_block = bool(legal_block) and (
        not isinstance(legal_block, (list, dict)) or len(legal_block) > 0
    )
    if bool(answers) and not has_legal_block:
        return api_error(
            en=(
                "Required legal confirmations missing: age 14+, risk acknowledgment, "
                "past performance disclaimer, and AI-analysis (not licensed advice) "
                "acknowledgment must all be checked to proceed. (Empty submission to "
                "skip onboarding is allowed; a non-empty submission must include the "
                "legal confirmations block.)"
            ),
            kr=(
                "법적 확인 항목이 누락되었습니다. 만 14세 이상, 투자 위험 인지, "
                "과거 수익률 면책, AI 분석(공인 투자자문 아님) 확인을 모두 체크해 "
                "주셔야 진행할 수 있습니다."
            ),
            code="ONBOARDING_LEGAL_REQUIRED", status=400,
        )

    from services.profile.questionnaire import calculate_profile_v2
    profile_v2_result = calculate_profile_v2(answers)
    is_v2_submission = bool(answers) and any(
        k in answers for k in (
            "experience_years", "portfolio_size", "scenario_portfolio_drop",
            "legal_confirmations",
        )
    )
    if is_v2_submission and not profile_v2_result.get("legal_confirmed", False):
        return api_error(
            en=(
                "Required legal confirmations missing: age 14+, risk acknowledgment, "
                "past performance disclaimer, and AI-analysis (not licensed advice) "
                "acknowledgment must all be checked to proceed."
            ),
            kr=(
                "법적 확인 항목이 누락되었습니다. 만 14세 이상, 투자 위험 인지, "
                "과거 수익률 면책, AI 분석(공인 투자자문 아님) 확인을 모두 체크해 "
                "주셔야 진행할 수 있습니다."
            ),
            code="ONBOARDING_LEGAL_REQUIRED", status=400,
        )

    if is_v2_submission:
        profile_type = profile_v2_result.get("investor_type", "risk_managed_growth")
    else:
        # Skip path (empty answers) or legacy v1 submission.
        profile_type = calculate_profile_type(answers)

    # Create or update investment profile
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = InvestmentProfile(user_id=current_user.id)
        db.session.add(profile)

    # 2026-05-17 wave D-1 — persist V2 answers under the V2 IDs the wizard
    # actually emits, not the V1 IDs (``experience_level`` / ``investment_goal``
    # etc.) which no longer appear in the payload. Pre-fix every V2 submission
    # caused the ``InvestmentProfile`` row to be filled with the ``.get(..., default)``
    # defaults ("beginner" / "growth" / 5 / "medium" / "both" / "manual" /
    # "moderate") regardless of what the user actually answered.
    if is_v2_submission:
        # Translate V2 IDs → existing ORM columns (kept stable so analytics
        # downstream code that filters on ``profile_type`` / ``experience_level``
        # keeps working). Use the V2-derived fields when available, fall back
        # to the raw answer for direct-mapped fields.
        profile.experience_level = profile_v2_result.get(
            "experience_level", profile.experience_level or "beginner"
        )
        profile.risk_tolerance = int(round(profile_v2_result.get("risk_score", 50) / 10))
        # holding_period is the V2 analogue of time_horizon
        hold_to_horizon = {
            "intraday": "short", "days": "short",
            "weeks": "short", "months": "medium", "years": "long",
        }
        profile.time_horizon = hold_to_horizon.get(
            answers.get("holding_period"), profile.time_horizon or "medium"
        )
        profile.preferred_markets = answers.get(
            "preferred_markets", profile.preferred_markets or "both"
        )
        profile.preferred_sectors = json.dumps(
            answers.get("preferred_sectors", [])
            if isinstance(answers.get("preferred_sectors"), list) else []
        )
        # rebalance_preference maps to auto_trade_preference (auto_daily ≈
        # full_auto; manual rebalance ≈ manual)
        rebal_to_auto = {
            "auto_daily": "full_auto", "weekly": "semi_auto",
            "biweekly": "semi_auto", "monthly": "signals",
            "quarterly": "manual",
        }
        profile.auto_trade_preference = rebal_to_auto.get(
            answers.get("rebalance_preference"),
            profile.auto_trade_preference or "manual",
        )
        # time_commitment from V2 maps to daily_time
        commit_to_daily = {
            "minimal": "minimal", "moderate": "moderate",
            "active": "active", "full_time": "active",
        }
        profile.daily_time = commit_to_daily.get(
            profile_v2_result.get("time_commitment"),
            profile.daily_time or "moderate",
        )
        # investment_goal: derive from return ambition + risk tolerance
        risk_score = profile_v2_result.get("risk_score", 50)
        if risk_score <= 25:
            profile.investment_goal = "preservation"
        elif risk_score <= 45:
            profile.investment_goal = "income"
        elif risk_score <= 70:
            profile.investment_goal = "growth"
        else:
            profile.investment_goal = "aggressive_growth"
    else:
        # Legacy v1 / skip-path: preserve existing behaviour exactly.
        profile.experience_level = answers.get("experience_level", "beginner")
        profile.investment_goal = answers.get("investment_goal", "growth")
        profile.risk_tolerance = answers.get("risk_tolerance", 5)
        profile.time_horizon = answers.get("time_horizon", "medium")
        profile.preferred_markets = answers.get("preferred_markets", "both")
        profile.preferred_sectors = json.dumps(answers.get("preferred_sectors", []))
        profile.auto_trade_preference = answers.get("auto_trade_preference", "manual")
        profile.daily_time = answers.get("daily_time", "moderate")

    # Set profile type and apply quant presets
    profile.profile_type = profile_type
    profile.apply_preset()

    # Update user
    current_user.risk_profile = profile_type
    current_user.onboarding_completed = True
    # 2026-05-17 wave 12 UX P0 — clear the partial-save draft on successful
    # completion so a future device session doesn't resurrect a stale
    # wizard for an already-onboarded user. ``onboarding_completed`` is
    # the authoritative flag; the draft becomes vestigial.
    current_user.onboarding_draft_json = None

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.submit_onboarding commit failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to save onboarding answers. Please try again.",
            kr="온보딩 응답 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            code="ONBOARDING_SAVE_FAILED", status=500,
        )

    return jsonify({
        "ok": True,
        "profile_type": profile_type,
        "profile": profile.to_dict(),
        "message": f"Profile set to {profile_type.title()}. Quant engine parameters updated.",
    })


@profile_bp.route("", methods=["GET"])
@api_auth
def get_profile():
    """Get current user's investment profile.

    2026-05-17: surface ``email_opt_out`` + ``email_opt_out_earnings`` at the
    top level so settings/_v2 page can hydrate the "email delivery enabled"
    toggle from server truth, not just localStorage. The fields live on the
    ``User`` row (see ``models/user.py:43,52``) not on ``InvestmentProfile``,
    which is why ``profile.to_dict()`` alone did not include them. Without
    this, a user who opted out on a different device would see the toggle
    re-flipped to "enabled" the next time they opened settings — a 정통망법
    §50 surface accuracy issue.
    """
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    email_opt_out = bool(getattr(current_user, "email_opt_out", False))
    email_opt_out_earnings = bool(
        getattr(current_user, "email_opt_out_earnings", False)
    )
    if not profile:
        return jsonify({
            "profile": None,
            "has_profile": False,
            "email_opt_out": email_opt_out,
            "email_opt_out_earnings": email_opt_out_earnings,
        })

    return jsonify({
        "profile": profile.to_dict(),
        "has_profile": True,
        "changes_left": current_user.profile_changes_left,
        "subscription_tier": current_user.subscription_tier,
        "email_opt_out": email_opt_out,
        "email_opt_out_earnings": email_opt_out_earnings,
        "locale": getattr(current_user, "locale", "ko") or "ko",
    })


# ── Locale (UI/PDF/email language preference) ─────────────────────────────
# Wave F (2026-05-28). Frontend ``sp_locale`` cookie sync target. Artifact
# services + EmailSender read ``user.locale`` to branch ko/en at render time.
SUPPORTED_LOCALES = frozenset({"ko", "en"})


@profile_bp.route("/locale", methods=["GET"])
@api_auth
def get_locale():
    """Return the user's stored locale preference (defaults to 'ko')."""
    return jsonify({
        "locale": getattr(current_user, "locale", "ko") or "ko",
        "supported": sorted(SUPPORTED_LOCALES),
    })


@profile_bp.route("/locale", methods=["PUT"])
@api_auth
@general_rate_limit
def update_locale():
    """Persist a new locale preference.

    Body: {"locale": "ko" | "en"}

    The cookie ``sp_locale`` on the frontend stays the immediate-feedback
    source of truth for unauthenticated pages; once logged in this column
    becomes the authoritative value (cron jobs, scheduled emails, PDF
    generation all read from the row, not the cookie).
    """
    data = request.get_json(silent=True) or {}
    requested = (data.get("locale") or "").strip().lower()
    if requested not in SUPPORTED_LOCALES:
        return api_error(
            en="Unsupported locale. Allowed: ko, en.",
            kr="지원하지 않는 언어입니다. ko 또는 en 만 가능합니다.",
            code="LOCALE_INVALID", status=400,
        )
    try:
        current_user.locale = requested
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning("locale update failed user=%s: %s", current_user.id, exc)
        return api_error(
            en="Failed to update locale.",
            kr="언어 설정을 저장하지 못했습니다.",
            code="LOCALE_UPDATE_FAILED", status=500,
        )
    return jsonify({"locale": current_user.locale, "ok": True})


# ── Seed Capital (분석용 시드머니) ────────────────────────────────────────
# Upper bound: ₩1B / $1B (arbitrary sanity cap — prevents accidental overflow).
MAX_CAPITAL = 1_000_000_000.0


@profile_bp.route("/capital", methods=["POST"])
@api_auth
@general_rate_limit
def update_capital():
    """Update the user's seed capital used by signals/discover/portfolio analysis.

    Body: {"available_capital_usd"?: number, "available_capital_krw"?: number}
    Either field may be omitted; omitted fields are left unchanged.

    Values are validated as non-negative finite numbers within MAX_CAPITAL.
    Returns the committed values so the client can refresh its AuthContext.
    """
    data = request.get_json(silent=True) or {}

    def _coerce(value, field):
        """Coerce one optional numeric input; return (kept_existing, parsed)."""
        if value is None:
            return True, None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field} must be a number")
        if parsed != parsed or parsed in (float("inf"), float("-inf")):
            raise ValueError(f"{field} must be a finite number")
        if parsed < 0:
            raise ValueError(f"{field} must be ≥ 0")
        if parsed > MAX_CAPITAL:
            raise ValueError(f"{field} must be ≤ {int(MAX_CAPITAL):,}")
        return False, parsed

    try:
        keep_usd, usd = _coerce(data.get("available_capital_usd"), "available_capital_usd")
        keep_krw, krw = _coerce(data.get("available_capital_krw"), "available_capital_krw")
    except ValueError as err:
        return api_error(
            en=str(err), kr="시드머니 값이 유효하지 않습니다.",
            code="CAPITAL_INVALID_VALUE", status=400,
        )

    if keep_usd and keep_krw:
        return api_error(
            en="Provide at least one of available_capital_usd or available_capital_krw",
            kr="시드머니 (USD 또는 KRW) 중 최소 한 가지는 입력해 주세요.",
            code="CAPITAL_AT_LEAST_ONE_REQUIRED", status=400,
        )

    if not keep_usd:
        current_user.available_capital = usd
    if not keep_krw:
        current_user.available_capital_krw = krw

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.update_capital commit failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to update capital. Please try again.",
            kr="시드머니 업데이트에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            code="CAPITAL_UPDATE_FAILED", status=500,
        )

    return jsonify({
        "ok": True,
        "available_capital": current_user.available_capital,
        "available_capital_krw": current_user.available_capital_krw,
    })


@profile_bp.route("", methods=["PUT"])
@api_auth
@general_rate_limit
def update_profile():
    """Update profile (re-take questionnaire). Free users: 3 changes max."""
    # Use effective_tier so DEV_PREMIUM_EMAILS / founding accounts bypass the
    # free-plan change cap (mirror routes/portfolio.py:add_position).
    if getattr(current_user, "effective_tier", None) in (None, "free") and current_user.profile_changes_left <= 0:
        return api_error(
            en="Profile change limit reached. Upgrade to Pro for unlimited changes.",
            kr="투자 성향 변경 횟수 한도에 도달했습니다. Pro 로 업그레이드하면 무제한 변경할 수 있습니다.",
            code="PROFILE_CHANGE_LIMIT", status=403,
        )

    data = request.get_json() or {}
    answers = data.get("answers", {})
    if not isinstance(answers, dict):
        return api_error(
            en="'answers' must be an object.",
            kr="answers 객체가 필요합니다.",
            code="PROFILE_INVALID_PAYLOAD", status=400,
        )

    # 2026-05-22 — server-side gate hardening (자본시장법 §6 bypass close).
    # Mirror submit_onboarding: any NON-EMPTY ``answers`` that omits the
    # ``legal_confirmations`` block is a direct-API gate-bypass (the
    # frontend always sends either ``{}`` or a full V2 payload carrying the
    # legal block). Reject (400) rather than silently re-classifying.
    legal_block = answers.get("legal_confirmations")
    has_legal_block = bool(legal_block) and (
        not isinstance(legal_block, (list, dict)) or len(legal_block) > 0
    )
    if bool(answers) and not has_legal_block:
        return api_error(
            en=(
                "Required legal confirmations missing: age 14+, risk acknowledgment, "
                "past performance disclaimer, and AI-analysis (not licensed advice) "
                "acknowledgment must all be checked to proceed. (Empty submission is "
                "allowed; a non-empty submission must include the legal confirmations "
                "block.)"
            ),
            kr=(
                "법적 확인 항목이 누락되었습니다. 만 14세 이상, 투자 위험 인지, "
                "과거 수익률 면책, AI 분석(공인 투자자문 아님) 확인을 모두 체크해 "
                "주셔야 진행할 수 있습니다."
            ),
            code="PROFILE_LEGAL_REQUIRED", status=400,
        )

    # 2026-05-17 wave D-1 — mirror the V2 path from ``submit_onboarding`` so
    # re-taking the questionnaire actually re-classifies the user against
    # the 8-type V2 system. Pre-fix this PUT path called only
    # ``calculate_profile_type`` (V1 4-tier) — so a Pro user who re-took the
    # 20-question wizard silently collapsed back to one of the 4 legacy types
    # and lost any V2 preset (max_alloc_pct, leverage_allowed, preferred_models,
    # etc.) the original submit had derived.
    from services.profile.questionnaire import calculate_profile_v2
    profile_v2_result = calculate_profile_v2(answers)
    is_v2_submission = bool(answers) and any(
        k in answers for k in (
            "experience_years", "portfolio_size", "scenario_portfolio_drop",
            "legal_confirmations",
        )
    )
    if is_v2_submission and not profile_v2_result.get("legal_confirmed", False):
        return api_error(
            en=(
                "Required legal confirmations missing: age 14+, risk acknowledgment, "
                "past performance disclaimer, and AI-analysis (not licensed advice) "
                "acknowledgment must all be checked to proceed."
            ),
            kr=(
                "법적 확인 항목이 누락되었습니다. 만 14세 이상, 투자 위험 인지, "
                "과거 수익률 면책, AI 분석(공인 투자자문 아님) 확인을 모두 체크해 "
                "주셔야 진행할 수 있습니다."
            ),
            code="PROFILE_LEGAL_REQUIRED", status=400,
        )

    if is_v2_submission:
        profile_type = profile_v2_result.get("investor_type", "risk_managed_growth")
    else:
        profile_type = calculate_profile_type(answers)

    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        return api_error(
            en="No profile found. Complete onboarding first.",
            kr="프로필이 없습니다. 먼저 온보딩을 완료해 주세요.",
            code="PROFILE_NOT_FOUND", status=404,
        )

    if is_v2_submission:
        profile.experience_level = profile_v2_result.get(
            "experience_level", profile.experience_level
        )
        profile.risk_tolerance = int(round(profile_v2_result.get("risk_score", 50) / 10))
        hold_to_horizon = {
            "intraday": "short", "days": "short",
            "weeks": "short", "months": "medium", "years": "long",
        }
        profile.time_horizon = hold_to_horizon.get(
            answers.get("holding_period"), profile.time_horizon
        )
        profile.preferred_markets = answers.get(
            "preferred_markets", profile.preferred_markets
        )
        if isinstance(answers.get("preferred_sectors"), list):
            profile.preferred_sectors = json.dumps(answers.get("preferred_sectors", []))
        rebal_to_auto = {
            "auto_daily": "full_auto", "weekly": "semi_auto",
            "biweekly": "semi_auto", "monthly": "signals",
            "quarterly": "manual",
        }
        profile.auto_trade_preference = rebal_to_auto.get(
            answers.get("rebalance_preference"), profile.auto_trade_preference
        )
        commit_to_daily = {
            "minimal": "minimal", "moderate": "moderate",
            "active": "active", "full_time": "active",
        }
        profile.daily_time = commit_to_daily.get(
            profile_v2_result.get("time_commitment"), profile.daily_time
        )
        risk_score = profile_v2_result.get("risk_score", 50)
        if risk_score <= 25:
            profile.investment_goal = "preservation"
        elif risk_score <= 45:
            profile.investment_goal = "income"
        elif risk_score <= 70:
            profile.investment_goal = "growth"
        else:
            profile.investment_goal = "aggressive_growth"
    else:
        # Store answers
        profile.experience_level = answers.get("experience_level", profile.experience_level)
        profile.investment_goal = answers.get("investment_goal", profile.investment_goal)
        profile.risk_tolerance = answers.get("risk_tolerance", profile.risk_tolerance)
        profile.time_horizon = answers.get("time_horizon", profile.time_horizon)
        profile.preferred_markets = answers.get("preferred_markets", profile.preferred_markets)
        profile.preferred_sectors = json.dumps(answers.get("preferred_sectors", []))
        profile.auto_trade_preference = answers.get("auto_trade_preference", profile.auto_trade_preference)
        profile.daily_time = answers.get("daily_time", profile.daily_time)

    profile.profile_type = profile_type
    profile.apply_preset()

    current_user.risk_profile = profile_type
    if getattr(current_user, "effective_tier", None) in (None, "free"):
        current_user.profile_changes_left -= 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.update_profile commit failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to update profile. Please try again.",
            kr="프로필 업데이트에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            code="PROFILE_UPDATE_FAILED", status=500,
        )

    return jsonify({
        "ok": True,
        "profile_type": profile_type,
        "profile": profile.to_dict(),
        "changes_left": current_user.profile_changes_left,
    })


# ── Living CFO Layer 2 (frontend/src/lib/cfo/hooks.ts) ───────────────────
# All endpoints below power the Layer 2 dashboard ("2 years in, knows
# you better than you know yourself"). They must always return HTTP 200
# on authenticated requests — brand-new users with no trade history
# receive a *valid empty* payload so the frontend can degrade gracefully
# (see hooks.ts:cfoFetch which falls back to mocks on non-200 only).


@profile_bp.route("/persona", methods=["GET"])
@api_auth
@legal_scrub_response
def get_persona_analysis():
    """Return declared + observed persona for Layer 2 hero card.

    Shape: see ``PersonaResponse`` in ``frontend/src/lib/cfo/hooks.ts``.
    """
    try:
        payload = compute_persona_response(current_user.id)
    except Exception:
        logger.exception("profile.get_persona_analysis failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to compute persona",
            kr="페르소나 분석에 실패했습니다.",
            code="PERSONA_COMPUTE_FAILED", status=500,
        )
    return jsonify(payload)


@profile_bp.route("/persona-detail", methods=["GET"])
@api_auth
@legal_scrub_response
def get_persona_detail():
    """Return the multi-dimensional persona classification (v2).

    Powered by :func:`services.profile.classify_persona_multi`. Fuses
    trade mechanics, intra-trade patterns, declared preferences,
    self-report (WeeklyPulse) and engagement (ArtifactFeedback) into a
    9-D behavioural vector and compares to 8 persona centroids.

    Query params
    ------------
    window_days : int (default 90, bounded to [30, 365])
        Lookback window for the trade-history features.

    Response shape
    --------------
    See :func:`services.profile.persona_classifier_v2.classify_persona_multi`
    — adds ``persona``, ``confidence``, ``data_sparse``, ``features``,
    ``present``, ``ranking``, ``breakdown``.

    The simpler :func:`get_persona_analysis` (``GET /api/profile/persona``)
    remains the canonical endpoint for the hero card; this one is the
    detail view the tooltip / debug panel reads.
    """
    raw = request.args.get("window_days", "90")
    try:
        window_days = int(raw)
    except (TypeError, ValueError):
        window_days = 90
    # Bound — absurd windows would blow up query latency for no signal.
    window_days = max(30, min(365, window_days))

    try:
        payload = classify_persona_multi(current_user.id, window_days=window_days)
    except Exception:
        logger.exception(
            "profile.get_persona_detail failed (user_id=%s, window=%s)",
            current_user.id, window_days,
        )
        return api_error(
            en="Failed to compute persona detail",
            kr="페르소나 상세 분석에 실패했습니다.",
            code="PERSONA_DETAIL_FAILED", status=500,
        )
    return jsonify(payload)


@profile_bp.route("/persona-explain", methods=["GET"])
@api_auth
@legal_scrub_response
def get_persona_explain():
    """Lightweight explainability payload — tooltip-sized.

    Returns only ``persona``, ``label``, ``confidence``, ``breakdown``
    and ``features``. Suitable for the frontend info popover that
    answers "why was I classified as ___?".
    """
    try:
        payload = explain_persona_classification(current_user.id)
    except Exception:
        logger.exception(
            "profile.get_persona_explain failed (user_id=%s)",
            current_user.id,
        )
        return api_error(
            en="Failed to compute persona explanation",
            kr="페르소나 설명 생성에 실패했습니다.",
            code="PERSONA_EXPLAIN_FAILED", status=500,
        )
    return jsonify(payload)


@profile_bp.route("/rolling-window", methods=["GET"])
@api_auth
def get_rolling_window():
    """Return 30/60/90-day rolling behavioural metrics for Layer 2.

    Shape: see ``RollingWindowResponse`` in
    ``frontend/src/lib/cfo/hooks.ts``.
    """
    try:
        payload = compute_rolling_response(current_user.id)
    except Exception:
        logger.exception("profile.get_rolling_window failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to compute rolling window",
            kr="롤링 윈도우 분석에 실패했습니다.",
            code="ROLLING_WINDOW_FAILED", status=500,
        )
    return jsonify(payload)


# ── Feedback ──────────────────────────────────────────────────────────────

# Per-section free-text length cap. Keep short — this is a vote, not an
# essay. Longer text is truncated silently.
_SECTION_MAX_LEN = 80
_ARTIFACT_ID_MAX_LEN = 64


@profile_bp.route("/feedback", methods=["POST"])
@api_auth
@general_rate_limit
def submit_feedback():
    """Record a section-level vote on a rendered artifact.

    Body (JSON):
        artifact_id: string (required, <= 64 chars)
        section:     string (required, <= 80 chars)
        vote:        "useful" | "meh" | "skip"

    Returns: ``{"ok": true}`` on success, ``{"error": "..."}`` + 400 on
    bad input. Duplicate ``(user, artifact, section)`` rows are allowed
    — the analytics layer takes the latest ``created_at`` as canonical.
    """
    data = request.get_json(silent=True) or {}
    artifact_id = (data.get("artifact_id") or "").strip()
    section = (data.get("section") or "").strip()
    vote = (data.get("vote") or "").strip().lower()

    if not artifact_id:
        return api_error(
            en="artifact_id is required",
            kr="artifact_id 가 필요합니다.",
            code="FEEDBACK_ARTIFACT_ID_REQUIRED", status=400,
        )
    if not section:
        return api_error(
            en="section is required",
            kr="section 필드가 필요합니다.",
            code="FEEDBACK_SECTION_REQUIRED", status=400,
        )
    if vote not in VOTE_CHOICES:
        return jsonify({
            "error": f"vote must be one of: {', '.join(VOTE_CHOICES)}",
        }), 400

    # Truncate rather than reject — the frontend may legitimately send
    # long section headings, but we don't want runaway strings in the DB.
    if len(artifact_id) > _ARTIFACT_ID_MAX_LEN:
        artifact_id = artifact_id[:_ARTIFACT_ID_MAX_LEN]
    if len(section) > _SECTION_MAX_LEN:
        section = section[:_SECTION_MAX_LEN]

    row = ArtifactFeedback(
        user_id=current_user.id,
        artifact_id=artifact_id,
        section=section,
        vote=vote,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.submit_feedback commit failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to save feedback",
            kr="피드백 저장에 실패했습니다.",
            code="FEEDBACK_SAVE_FAILED", status=500,
        )

    return jsonify({"ok": True})


# ── Weekly pulse (mood / confidence / worry / topics / learn) ────────────

_CADENCE_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30}
_PULSE_HISTORY_LIMIT = 52  # ~1 year weekly
_PULSE_TEXT_MAX_LEN = 500
_PULSE_TOPIC_MAX = 10
_PULSE_TOPIC_LEN = 40


def _next_due_at(last_submitted: datetime | None, cadence: str) -> str | None:
    days = _CADENCE_DAYS.get(cadence, 7)
    base = last_submitted or datetime.now(timezone.utc).replace(tzinfo=None)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return (base + timedelta(days=days)).astimezone(timezone.utc).isoformat()


@profile_bp.route("/pulse", methods=["GET"])
@api_auth
def get_pulse():
    """Return the user's weekly pulse history + next-due timestamp.

    Shape: see ``PulseResponse`` in ``frontend/src/lib/cfo/hooks.ts``.
    """
    rows = (
        WeeklyPulse.query
        .filter_by(user_id=current_user.id)
        .order_by(WeeklyPulse.submitted_at.desc())
        .limit(_PULSE_HISTORY_LIMIT)
        .all()
    )
    # Most recent cadence wins; default weekly.
    latest = rows[0] if rows else None
    cadence = (latest.cadence if latest else "weekly") or "weekly"
    if cadence not in VALID_CADENCES:
        cadence = "weekly"

    history = [r.to_dict() for r in reversed(rows)]  # oldest → newest
    next_due = _next_due_at(latest.submitted_at if latest else None, cadence)

    return jsonify({
        "history": history,
        "next_due_at": next_due,
        "cadence": cadence,
    })


@profile_bp.route("/pulse", methods=["POST"])
@api_auth
@general_rate_limit
def submit_pulse():
    """Record a weekly pulse submission.

    Body (JSON):
        mood:         int 1..5  (required)
        confidence:   int 1..5  (required)
        worry:        str       (optional, max 500)
        topics:       list[str] (optional, max 10 items, each <= 40 chars)
        learn:        str       (optional, max 500)
        submitted_at: ISO8601   (optional, server will override to now if
                                 missing / unparseable / in the future)
        cadence:      "weekly"|"biweekly"|"monthly" (optional, default
                                 keeps the last-used cadence)

    Returns: ``{"ok": true}`` on success, ``{"error": ...}`` + 400 on
    validation failure.
    """
    data = request.get_json(silent=True) or {}

    # mood / confidence — required ints 1..5
    try:
        mood = int(data.get("mood"))
        confidence = int(data.get("confidence"))
    except (TypeError, ValueError):
        return api_error(
            en="mood and confidence must be integers 1..5",
            kr="기분(mood)과 확신(confidence)은 1~5 정수여야 합니다.",
            code="PULSE_INVALID_RANGE", status=400,
        )
    if not (1 <= mood <= 5 and 1 <= confidence <= 5):
        return api_error(
            en="mood and confidence must be integers 1..5",
            kr="기분(mood)과 확신(confidence)은 1~5 정수여야 합니다.",
            code="PULSE_INVALID_RANGE", status=400,
        )

    # Free-text fields — truncate silently.
    worry = (data.get("worry") or "")
    if not isinstance(worry, str):
        worry = str(worry)
    worry = worry[:_PULSE_TEXT_MAX_LEN]

    learn = (data.get("learn") or "")
    if not isinstance(learn, str):
        learn = str(learn)
    learn = learn[:_PULSE_TEXT_MAX_LEN]

    # Topics — list of short strings, capped.
    topics_raw = data.get("topics") or []
    if not isinstance(topics_raw, list):
        topics_raw = []
    topics: list[str] = []
    for t in topics_raw[:_PULSE_TOPIC_MAX]:
        if t is None:
            continue
        t_str = str(t).strip()[:_PULSE_TOPIC_LEN]
        if t_str:
            topics.append(t_str)

    # Cadence — keep user's previous setting if unspecified.
    cadence = (data.get("cadence") or "").strip().lower()
    if cadence not in VALID_CADENCES:
        latest = (
            WeeklyPulse.query
            .filter_by(user_id=current_user.id)
            .order_by(WeeklyPulse.submitted_at.desc())
            .first()
        )
        cadence = latest.cadence if latest and latest.cadence in VALID_CADENCES else "weekly"

    # submitted_at — best-effort parse; fall back to now on failure or
    # when the client clock is ahead (no future-dated pulses).
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    submitted_at = now
    raw_sa = data.get("submitted_at")
    if isinstance(raw_sa, str) and raw_sa:
        try:
            parsed = datetime.fromisoformat(raw_sa.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            if parsed <= now + timedelta(minutes=5):  # tolerate small skew
                submitted_at = parsed
        except ValueError:
            submitted_at = now

    row = WeeklyPulse(
        user_id=current_user.id,
        mood=mood,
        confidence=confidence,
        worry=worry,
        topics=json.dumps(topics, ensure_ascii=False),
        learn=learn,
        cadence=cadence,
        submitted_at=submitted_at,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.submit_pulse commit failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to save pulse",
            kr="펄스 저장에 실패했습니다.",
            code="PULSE_SAVE_FAILED", status=500,
        )

    return jsonify({"ok": True})


# ── Group Benchmark (anonymized peer stats) ──────────────────────────────
# See reports/product/GROUP_BENCHMARK_SPEC_2026-04-24.md.
# Exposes two read-only endpoints:
#   GET /api/profile/persona-benchmark?window=90
#       → own-persona group stats (200 w/ available=false when suppressed)
#   GET /api/profile/persona-benchmark-all?window=90
#       → all 8 personas, each entry null if suppressed / not computed
#
# Writes happen out-of-band via scripts/compute_group_stats.py (APScheduler
# cron — weekly). These endpoints NEVER trigger a computation, so the
# legal gate (n_users >= 20) is enforced at the service layer and these
# routes cannot accidentally leak under-threshold stats.
_DEFAULT_WINDOW = 90


def _parse_window(raw: str | None) -> int | None:
    """Validate the ``window`` query param. Returns None on invalid input."""
    from models import VALID_WINDOWS  # local to avoid top-import churn
    try:
        val = int(raw) if raw is not None else _DEFAULT_WINDOW
    except (TypeError, ValueError):
        logger.debug("silent-fallback: _parse_window", exc_info=True)
        return None
    return val if val in VALID_WINDOWS else None


def _public_benchmark_metrics(metrics: dict | None) -> dict:
    """Strip the 5 behavioural sub-score (0-100) keys before peer-benchmark
    metrics leave the API.

    legal-kr-fintech (2026-06, 현행법): an anonymised cohort MEDIAN is not
    individual profiling (PIPA §37조의2 / 한국 AI기본법 = LOW), but surfacing a
    0-100 score-shaped number still (a) risks 표시광고법 §3 우열 오인, (b)
    contradicts the "AI 점수화 폐기" decision (DECISIONS.md), and (c) escalates
    to 자본시장법 §101 MED-HIGH on a paid tier. The medians stay COMPUTED in the
    stored PersonaGroupStats.metrics for the internal
    ``scorer._persona_avg_with_floor`` consumer — only this API surface is
    stripped. Legitimate peer stats (CAGR / Sharpe / holding / win-rate /
    drawdown / sectors / comparison_to_all) are kept.
    """
    from models import SUB_SCORE_KEYS
    return {k: v for k, v in (metrics or {}).items() if k not in SUB_SCORE_KEYS}


@profile_bp.route("/persona-benchmark", methods=["GET"])
@api_auth
def get_persona_benchmark():
    """Return the authenticated user's peer-group stats.

    Query params:
        window: 30 | 90 | 365  (default 90)

    Response shape (always HTTP 200 when the gate passes):
        {"available": true, "persona": "...", "window_days": 90, "stats": {...}}

    If the latest snapshot is suppressed (``n_users < 20``) OR hasn't been
    computed yet, returns HTTP 200 with:
        {"available": false, "reason": "insufficient_group_size" | "not_computed",
         "persona": "...", "window_days": 90}

    Individual user records are NEVER exposed — only sector-level
    aggregates and behavioural mistake labels.
    """
    from services.profile import get_persona_stats
    from services.profile.persona_analytics import (
        DECLARED_TO_PERSONA,
        PERSONA_LABELS,
    )

    window = _parse_window(request.args.get("window"))
    if window is None:
        return api_error(
            en="window must be one of 30, 90, 365",
            kr="window 는 30, 90, 365 중 하나여야 합니다.",
            code="WINDOW_INVALID", status=400,
        )

    # Resolve the calling user's declared persona.
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    profile_type = (profile.profile_type or "").lower() if profile else ""
    persona = DECLARED_TO_PERSONA.get(profile_type, "balanced")

    stats = get_persona_stats(persona, window)
    if stats is None:
        # Distinguish "no row at all" vs "suppressed" for the UI.
        from models import PersonaGroupStats
        latest = (
            PersonaGroupStats.query
            .filter_by(persona=persona, window_days=window)
            .order_by(PersonaGroupStats.computed_at.desc())
            .first()
        )
        reason = "not_computed" if latest is None else "insufficient_group_size"
        return jsonify({
            "available": False,
            "reason": reason,
            "persona": persona,
            "persona_label": PERSONA_LABELS.get(persona, persona),
            "window_days": window,
        })

    # ``get_persona_stats`` returns the nested model shape
    # (``{persona, window_days, n_users, suppressed, metrics:{...}}``).
    # The frontend ``BenchmarkStats`` contract (and both consumers:
    # page-v2 ``peerMetrics`` + ``peer-benchmark-block``) expect the
    # metric fields at the TOP level of ``stats``. The ``metrics`` dict
    # already carries ``persona`` + ``window_days``, so exposing it
    # directly matches the contract 1:1. We flatten at the route layer
    # only — ``to_dict()`` keeps its nested shape for internal consumers
    # (e.g. ``services.behavior.scorer._persona_avg_with_floor``).
    flat_stats = _public_benchmark_metrics(stats.get("metrics"))
    return jsonify({
        "available": True,
        "persona": persona,
        "persona_label": PERSONA_LABELS.get(persona, persona),
        "window_days": window,
        "stats": flat_stats,
    })


@profile_bp.route("/persona-benchmark-all", methods=["GET"])
@api_auth
def get_persona_benchmark_all():
    """Return benchmark stats for every persona — for cross-group comparison.

    Query params:
        window: 30 | 90 | 365  (default 90)

    Response shape:
        {
          "window_days": 90,
          "personas": {
            "growth":    {"available": true, "stats": {...}, "label": "Growth CFO"},
            "value":     {"available": false, "reason": "insufficient_group_size", ...},
            ...
          }
        }

    Suppressed personas return ``available=false`` — never numeric values.
    """
    from services.profile import get_all_persona_stats
    from services.profile.persona_analytics import (
        PERSONA_CODES,
        PERSONA_LABELS,
    )
    from models import PersonaGroupStats

    window = _parse_window(request.args.get("window"))
    if window is None:
        return api_error(
            en="window must be one of 30, 90, 365",
            kr="window 는 30, 90, 365 중 하나여야 합니다.",
            code="WINDOW_INVALID", status=400,
        )

    published = get_all_persona_stats(window)

    # Single round-trip for "is there ANY snapshot per persona?" — used
    # only when ``stats is None`` to distinguish "not computed yet" vs
    # "computed but suppressed". Replaces the previous N+1 (8 queries
    # per request).
    presence_rows = (
        db.session.query(PersonaGroupStats.persona)
        .filter(
            PersonaGroupStats.persona.in_(list(PERSONA_CODES)),
            PersonaGroupStats.window_days == window,
        )
        .distinct()
        .all()
    )
    has_any_snapshot: set[str] = {row[0] for row in presence_rows}

    out: dict[str, dict] = {}
    for persona in PERSONA_CODES:
        stats = published.get(persona)
        label = PERSONA_LABELS.get(persona, persona)
        if stats is not None:
            # Flatten to the frontend ``BenchmarkStats`` contract — see
            # ``get_persona_benchmark`` above. Metric fields live at the
            # top level of ``stats``; the nested model shape stays
            # internal-only via ``to_dict()``.
            out[persona] = {
                "available": True,
                "label": label,
                "stats": _public_benchmark_metrics(stats.get("metrics")),
            }
            continue
        reason = (
            "insufficient_group_size"
            if persona in has_any_snapshot
            else "not_computed"
        )
        out[persona] = {
            "available": False,
            "label": label,
            "reason": reason,
        }

    return jsonify({
        "window_days": window,
        "personas": out,
    })


# ── PersonaSnapshot history + Evolution Timeline (Feature 3+4) ────────────
# All read endpoints scope strictly to ``current_user.id`` — never another
# user's data. Write endpoint is self-only too: there is no admin override
# that lets one user trigger another user's snapshot. The
# ``/api/profile/persona-snapshot`` POST is rate-limited at the security
# layer and exists primarily as a test/debug surface for the frontend
# Evolution Timeline component while the weekly cron is the production
# write path. Every response carries ``DRIFT_DISCLAIMER`` so the
# observational framing the legal filter expects is always present.


# Bound the timeline lookback. ``days_back`` matches the service-layer
# clamp (1..365) but we keep a separate constant for clarity at the
# route boundary.
_HISTORY_MIN_DAYS = 1
_HISTORY_MAX_DAYS = 365
_HISTORY_DEFAULT_DAYS = 180


@profile_bp.route("/persona-history", methods=["GET"])
@api_auth
@legal_scrub_response
def get_persona_history():
    """Return the authenticated user's PersonaSnapshot timeline.

    Query params:
        days: int (default 180, bounded to [1, 365])

    Response shape:
        {
            "snapshots": [...],   # oldest → newest
            "n":         int,
            "days":      int,
            "disclaimer": "...",
        }

    Empty list when no snapshots exist — the API always returns HTTP
    200 so SWR doesn't fall back to mocks for fresh users.
    """
    raw = request.args.get("days", str(_HISTORY_DEFAULT_DAYS))
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = _HISTORY_DEFAULT_DAYS
    days = max(_HISTORY_MIN_DAYS, min(_HISTORY_MAX_DAYS, days))

    try:
        snapshots = get_history(current_user.id, days_back=days)
    except Exception:
        logger.exception(
            "profile.get_persona_history failed (user_id=%s, days=%s)",
            current_user.id, days,
        )
        return api_error(
            en="Failed to load persona history",
            kr="페르소나 이력을 불러오지 못했습니다.",
            code="PERSONA_HISTORY_FAILED", status=500,
        )

    return jsonify({
        "snapshots": snapshots,
        "n": len(snapshots),
        "days": days,
        "disclaimer": DRIFT_DISCLAIMER,
    })


@profile_bp.route("/persona-drift", methods=["GET"])
@api_auth
@legal_scrub_response
def get_persona_drift():
    """Return a recent-drift summary for the authenticated user.

    Combines a 180-day full-history drift summary with a 4-week
    significance check. Always returns HTTP 200; the ``available``
    flag inside ``drift`` indicates whether enough data exists. The
    ``significant`` block is ``None`` when the recent change is below
    the threshold (steady state) — the UI hides the banner in that
    case.

    Every textual field is observational. ``disclaimer`` is the same
    constant the timeline endpoint emits.
    """
    try:
        snapshots = get_history(current_user.id, days_back=_HISTORY_DEFAULT_DAYS)
        drift = compute_drift(snapshots)
        significant = detect_significant_drift(current_user.id)
    except Exception:
        logger.exception(
            "profile.get_persona_drift failed (user_id=%s)",
            current_user.id,
        )
        return api_error(
            en="Failed to compute persona drift",
            kr="페르소나 변화 분석에 실패했습니다.",
            code="PERSONA_DRIFT_FAILED", status=500,
        )

    return jsonify({
        "drift": drift,
        "significant": significant,
        "disclaimer": DRIFT_DISCLAIMER,
    })


@profile_bp.route("/persona-snapshot", methods=["POST"])
@api_auth
@general_rate_limit
def post_persona_snapshot():
    """Take an immediate PersonaSnapshot for the authenticated user.

    Self-only — there is no admin override that lets one user trigger
    another user's snapshot. The weekly cron remains the production
    write path; this endpoint is the test / debug surface so the
    frontend Evolution Timeline can be exercised before the first
    Sunday cron fires for a new account.

    Returns ``{"ok": true, "snapshot": {...}}`` on success or
    ``{"ok": true, "snapshot": null, "reason": "duplicate"}`` when a
    snapshot at the same instant already exists (UNIQUE collision).
    """
    body = request.get_json(silent=True) or {}
    raw_window = body.get("window_days", 90)
    try:
        window_days = int(raw_window)
    except (TypeError, ValueError):
        window_days = 90
    window_days = max(30, min(365, window_days))

    try:
        row = take_snapshot(current_user.id, window_days=window_days)
    except Exception:
        logger.exception(
            "profile.post_persona_snapshot failed (user_id=%s)",
            current_user.id,
        )
        return api_error(
            en="Failed to take persona snapshot",
            kr="페르소나 스냅샷 생성에 실패했습니다.",
            code="PERSONA_SNAPSHOT_FAILED", status=500,
        )

    if row is None:
        return jsonify({
            "ok": True,
            "snapshot": None,
            "reason": "duplicate",
            "disclaimer": DRIFT_DISCLAIMER,
        })

    return jsonify({
        "ok": True,
        "snapshot": row.to_dict(),
        "disclaimer": DRIFT_DISCLAIMER,
    })


# ── Email preferences (정통망법 §50 compliance) ───────────────────────────
# Honoured by every artefact email service in services/artifacts/*. Two
# independent dials:
#   - email_opt_out         : global kill switch (every email)
#   - email_opt_out_earnings: per-channel kill switch for earnings pre-briefs
#
# Sent over CSRF-protected, cookie-authenticated PATCH so the toggles in
# the Settings UI can update either or both flags atomically. Unauthenticated
# callers receive a 401 from `@api_auth` before the handler runs. The
# token-based public unsubscribe link (GET /api/email/unsubscribe) lives
# in routes/email_preferences.py and bypasses CSRF on purpose — see that
# module for the rationale.

@profile_bp.route("/email-preferences", methods=["PATCH"])
@api_auth
@limiter.limit("30 per minute")
def patch_email_preferences():
    """Update one or both email opt-out flags.

    Body (JSON, all keys optional):
        email_opt_out:          bool
        email_opt_out_earnings: bool

    Omitted keys are left unchanged. Non-bool values for a present key
    are rejected with HTTP 400. Returns the *committed* values so the
    client can refresh its local state without an extra GET.

    Response shape::

        {
            "ok": true,
            "preferences": {
                "email_opt_out": false,
                "email_opt_out_earnings": false,
            }
        }
    """
    data = request.get_json(silent=True) or {}

    def _coerce(value, field):
        """Reject non-bool inputs explicitly — JSON ``null`` means "leave
        as is" but an integer/string is a client bug we should surface."""
        if value is None:
            return None
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be a boolean")
        return value

    try:
        new_global = _coerce(data.get("email_opt_out"), "email_opt_out")
        new_earnings = _coerce(
            data.get("email_opt_out_earnings"),
            "email_opt_out_earnings",
        )
    except ValueError as err:
        return api_error(
            en=str(err),
            kr="이메일 환경설정 값이 유효하지 않습니다 (boolean 필요).",
            code="EMAIL_PREFS_INVALID", status=400,
        )

    if new_global is None and new_earnings is None:
        return jsonify({
            "error": (
                "Provide at least one of email_opt_out or email_opt_out_earnings"
            ),
        }), 400

    if new_global is not None:
        current_user.email_opt_out = new_global
    if new_earnings is not None:
        current_user.email_opt_out_earnings = new_earnings

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "profile.patch_email_preferences commit failed (user_id=%s)",
            current_user.id,
        )
        return api_error(
            en="Failed to update email preferences",
            kr="이메일 환경설정 업데이트에 실패했습니다.",
            code="EMAIL_PREFS_UPDATE_FAILED", status=500,
        )

    return jsonify({
        "ok": True,
        "preferences": {
            "email_opt_out": bool(current_user.email_opt_out),
            "email_opt_out_earnings": bool(current_user.email_opt_out_earnings),
        },
    })


# ── PIPA §35 정보주체 열람권 (Right to Access self-service) ─────────────
# 개인정보보호법 §35 ① 정보주체는 본인의 개인정보 열람을 요구할 수 있다.
# §35 ④ 개인정보처리자는 10일 이내에 열람할 수 있도록 해야 한다.
#
# privacy-ko.md 의 "[설정 > 개인정보 관리] 페이지에서 직접 처리" 약속에
# 대응하는 self-service endpoint. 사용자가 본인 데이터를 즉시 다운로드.
#
# 보안:
#   - login_required (api_auth) → 본인 데이터만 반환
#   - 민감 시크릿 제외: stripe_customer_id, password_hash, oauth_id,
#     refresh_token 등 → 응답에 포함 금지 (PII 최소 노출)
#   - JSON download (Content-Disposition: attachment)
#
# 회귀 방지: query 는 모두 `user_id == current_user.id` 로 스코핑.
# 다른 사용자 데이터는 어떤 경로로도 노출되지 않아야 한다 (테스트로 검증).

# Caps to keep export size sane while still being PIPA-compliant
# (사용자가 본인 정보를 "전부" 받을 수 있도록 충분히 크게).
_EXPORT_TRADE_LIMIT = 5000   # >5000 trades 면 파일 분할이 필요한 사용자
_EXPORT_ALERT_LIMIT = 1000   # 1년치 알림 충분
# Behavioural/pulse PII sections (PIPA §35) — weekly cadence so even
# multi-year accounts stay well under these caps; bounded for safety.
_EXPORT_BEHAVIORAL_LIMIT = 520   # ~10 years of weekly scores
_EXPORT_PULSE_LIMIT = 520        # ~10 years of weekly pulses
_EXPORT_PERSONA_LIMIT = 520      # ~10 years of weekly persona snapshots
_EXPORT_NPS_LIMIT = 1000         # 1-click NPS submissions
# PIPA §35 — pre-trade reflections hold user free-text (rationale) and the
# devil's-advocate-seen flag, both purged on account deletion
# (routes/auth.py:delete_account → PreTradeReflection.delete), which confirms
# they are personal data and must therefore be reachable via the §35 열람권
# export. Cap bounds a pathological journaller; well above realistic usage.
_EXPORT_REFLECTION_LIMIT = 5000  # pre-trade reflection journal entries
# PIPA §35 §2 (2026-05-30) — remaining user-owned sections added to close
# the §35 열람권 coverage gap (was 11/26 tables; see export_profile docstring
# for the full registry). All are the user's *own* personal data, all purged
# on account deletion (routes/auth.py:delete_account +
# scripts/nightly/pipa_purge.py), confirming they are personal data and must
# be reachable here. Caps bound pathological accounts; well above realistic use.
_EXPORT_ARTIFACT_LIMIT = 2000          # generated CFO artefacts (memo/brag/brief)
_EXPORT_ARTIFACT_FEEDBACK_LIMIT = 2000  # 👍/👎 on artefacts
_EXPORT_REFERRAL_LIMIT = 50            # one row per user normally (UNIQUE user_id)
_EXPORT_DD_CHECK_LIMIT = 5000          # one per position
_EXPORT_INQUIRY_LIMIT = 1000           # support inquiries (subject/body free-text)
_EXPORT_TWIN_REPORT_LIMIT = 520        # ~10y weekly paper-twin reports
_EXPORT_TWIN_POSITION_LIMIT = 5000     # paper twin open positions
_EXPORT_TWIN_TRADE_LIMIT = 5000        # paper twin trade ledger
_EXPORT_WAITLIST_LIMIT = 50            # companion waitlist enrolments
_EXPORT_PORTFOLIO_SHARE_LIMIT = 1000   # share links the user created
_EXPORT_PUSH_SUB_LIMIT = 100           # browser push registrations
_EXPORT_SCHEDULED_EMAIL_LIMIT = 1000   # onboarding email queue rows
_EXPORT_CHECKOUT_EXPIRATION_LIMIT = 1000  # abandoned-checkout follow-up queue
# P1 sections — login/funnel history (the user's own activity records).
_EXPORT_AUTH_EVENT_LIMIT = 2000        # OAuth start/success/fail log (keyed by email)
_EXPORT_FUNNEL_EVENT_LIMIT = 5000      # acquisition/activation funnel events


def _iso_or_none(value):
    """Safe ISO-8601 conversion. Returns None for None / non-datetime input."""
    if value is None:
        return None
    try:
        return value.isoformat()
    except (AttributeError, TypeError):
        return None


def _serialize_user(user) -> dict:
    """Serialize User row, excluding sensitive secrets per PIPA minimization.

    Excluded on purpose:
        - password_hash      : credential hash (never expose)
        - stripe_customer_id : payment processor identifier
        - oauth_id           : OAuth provider's internal user ID
        - refresh_token      : broker connection tokens (handled separately
                                in BrokerConnection if at all)

    Included: identity (email, name), profile metadata, capital, tier,
    consent flags.
    """
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": getattr(user, "avatar_url", None),
        "oauth_provider": getattr(user, "oauth_provider", None),
        "created_at": _iso_or_none(getattr(user, "created_at", None)),
        "available_capital_usd": getattr(user, "available_capital", None),
        "available_capital_krw": getattr(user, "available_capital_krw", None),
        "risk_profile": getattr(user, "risk_profile", None),
        "subscription_tier": getattr(user, "subscription_tier", None),
        "onboarding_completed": bool(getattr(user, "onboarding_completed", False)),
        "profile_changes_left": getattr(user, "profile_changes_left", None),
        "email_opt_out": bool(getattr(user, "email_opt_out", False)),
        "email_opt_out_earnings": bool(
            getattr(user, "email_opt_out_earnings", False)
        ),
    }


def _serialize_position(p) -> dict:
    return {
        "id": p.id,
        "ticker": p.ticker,
        "shares": p.shares,
        "avg_cost": p.avg_cost,
        "buy_fx_rate": getattr(p, "buy_fx_rate", None),
        "added_at": _iso_or_none(getattr(p, "added_at", None)),
        "thesis": getattr(p, "thesis", None),
        "thesis_status": getattr(p, "thesis_status", None),
    }


def _serialize_watchlist(w) -> dict:
    return {
        "id": w.id,
        "ticker": w.ticker,
        "note": getattr(w, "note", None),
        "added_at": _iso_or_none(getattr(w, "added_at", None)),
    }


def _serialize_trade(t) -> dict:
    return {
        "id": t.id,
        "ticker": t.ticker,
        "name": getattr(t, "name", None),
        "action": t.action,
        "shares": t.shares,
        "price_per_share": t.price_per_share,
        "total_value": t.total_value,
        "pnl": getattr(t, "pnl", None),
        "pnl_pct": getattr(t, "pnl_pct", None),
        "currency": getattr(t, "currency", None),
        "traded_at": _iso_or_none(getattr(t, "traded_at", None)),
    }


def _serialize_alert(a) -> dict:
    return {
        "id": a.id,
        "ticker": getattr(a, "ticker", None),
        "kind": getattr(a, "kind", None),
        "title": getattr(a, "title", None),
        "body": getattr(a, "body", None),
        "message": getattr(a, "message", None),
        "signal": getattr(a, "signal", None),
        "score": getattr(a, "score", None),
        "is_read": bool(getattr(a, "is_read", False)),
        "created_at": _iso_or_none(getattr(a, "created_at", None)),
        "read_at": _iso_or_none(getattr(a, "read_at", None)),
    }


# ── Serializers for models without a built-in to_dict (PIPA §35 §2) ──────────
# Each one deliberately omits credential / endpoint-key material. The four
# tables below have no model-level ``to_dict`` (push/scheduled/checkout/share
# are queue/secret-bearing rows), so the exclusion lives here at the boundary.

def _serialize_portfolio_share(s) -> dict:
    """Share-link metadata. ``token`` is the unguessable secret that grants
    read access to the shared portfolio — exclude it (a leaked export must
    not hand out a live share URL). Expose only existence + lifecycle."""
    return {
        "id": s.id,
        "created_at": _iso_or_none(getattr(s, "created_at", None)),
        "expires_at": _iso_or_none(getattr(s, "expires_at", None)),
        "has_token": bool(getattr(s, "token", None)),
    }


def _serialize_push_subscription(p) -> dict:
    """Web-Push registration. ``endpoint`` / ``p256dh`` / ``auth`` are the
    push *secret* keys (anyone with them can push to the device) — exclude
    all three. Expose only existence + when it was registered."""
    return {
        "id": p.id,
        "created_at": _iso_or_none(getattr(p, "created_at", None)),
        "has_endpoint": bool(getattr(p, "endpoint", None)),
    }


def _serialize_scheduled_email(e) -> dict:
    return {
        "id": e.id,
        "email_type": getattr(e, "email_type", None),
        "email_category": getattr(e, "email_category", None),
        "scheduled_send_at": _iso_or_none(getattr(e, "scheduled_send_at", None)),
        "sent_at": _iso_or_none(getattr(e, "sent_at", None)),
        "skipped_reason": getattr(e, "skipped_reason", None),
        "created_at": _iso_or_none(getattr(e, "created_at", None)),
    }


def _serialize_checkout_expiration(c) -> dict:
    """Abandoned-checkout follow-up queue row. ``session_id`` is a Stripe
    checkout-session identifier — a payment-processor token, excluded under
    the same minimization rule as ``stripe_customer_id`` in _serialize_user."""
    return {
        "id": c.id,
        "expired_at": _iso_or_none(getattr(c, "expired_at", None)),
        "scheduled_send_at": _iso_or_none(getattr(c, "scheduled_send_at", None)),
        "sent_at": _iso_or_none(getattr(c, "sent_at", None)),
        "skipped_reason": getattr(c, "skipped_reason", None),
        "created_at": _iso_or_none(getattr(c, "created_at", None)),
    }


def _serialize_companion_waitlist(w) -> dict:
    """Journal Companion waitlist enrolment (CompanionWaitlist has no
    to_dict). ``email_hash`` is a SHA256 of the email — not reversible, but
    omitted as it carries no value to the data subject; ``email_plaintext``
    IS the user's own email so it is included (it's their data)."""
    return {
        "id": w.id,
        "email_plaintext": getattr(w, "email_plaintext", None),
        "email_consent_at": _iso_or_none(getattr(w, "email_consent_at", None)),
        "source": getattr(w, "source", None),
        "persona_interest": getattr(w, "persona_interest", None),
        "invited_at": _iso_or_none(getattr(w, "invited_at", None)),
        "activated_at": _iso_or_none(getattr(w, "activated_at", None)),
        "created_at": _iso_or_none(getattr(w, "created_at", None)),
    }


# ── CSV export (tabular raw-fact download) ───────────────────────────────────
# A focused, spreadsheet-friendly slice of the §35 JSON export. Strictly raw
# stored fields — NO live price, NO computed metric, NO FX conversion, NO
# advice/recommendation. Deterministic: the same DB row always yields the same
# CSV cell. This keeps the surface legally inert (it is "your own data", not a
# performance brag) and free of brittle live-data coupling.
#
# Datasets are restricted to the three the user most often wants in a sheet:
#   trades     — TradeHistory ledger (what you did, when, at what stored price)
#   positions  — current Position rows (ticker / shares / avg cost)
#   watchlist  — Watchlist rows (ticker / note / when added)
#
# Name resolution: per feedback_ticker_display the numeric KR code is replaced
# by the company name. ``resolve_stock_name_with_db`` is a name LOOKUP only
# (curated registry + SignalCache rung) — it performs no live price fetch and
# no calculation, so it stays within the raw-fact boundary. We always emit BOTH
# ``name`` and ``ticker`` columns so the raw identifier is never lost.

_CSV_DATASETS = (
    "trades", "positions", "watchlist",
    # Capital-gains (해외주식 양도소득세) — computed from the user's own trades
    # via FIFO matching + trade-date FX. capital_gains = per-lot detail,
    # capital_gains_summary = per-year 손익통산/공제/예상세액. NOT raw stored
    # fields (they involve a deterministic calc), so they are built specially
    # in _csv_export_response rather than mapped from a single ORM row.
    "capital_gains", "capital_gains_summary",
    # Self-record journals — the user's own PreTradeReflection / WeeklyPulse
    # free-text. Raw stored fields, mapped row-by-row like trades/positions.
    "journal", "pulse",
)


def _csv_num(value, ndigits=2):
    """Round a numeric CSV cell to ``ndigits``; blank for None.

    Keeps KRW/USD amounts readable in a sheet without fabricating precision.
    A genuinely-missing value (FX unavailable) stays an empty cell — never 0.
    """
    if value is None:
        return ""
    try:
        rounded = round(float(value), ndigits)
    except (TypeError, ValueError):
        return ""
    # ndigits=0 → emit a clean integer cell (KRW amounts have no fractional
    # won), not a trailing ".0" that clutters the sheet.
    if ndigits == 0:
        return int(rounded)
    return rounded


def _csv_resolve_name(ticker):
    """Best-effort display name for a ticker, falling back to the ticker.

    Pure LOCAL lookup (curated registry + SignalCache DB rung) — ``allow_live
    =False`` deliberately skips the KIS live rung so a bulk export never fans
    out one network call per row (a 200-row KRX export would otherwise fire
    200 KIS requests) and stays deterministic. No price fetch, no computation.
    Never raises; a miss returns the ticker unchanged so the column is never
    blank.
    """
    if not ticker:
        return ""
    try:
        from services.name_resolver import resolve_stock_name_with_db
        return resolve_stock_name_with_db(ticker, allow_live=False) or ticker
    except Exception:
        # Name resolution is a convenience, never a hard dependency: a miss
        # must not break the user's own-data download.
        logger.debug("csv name resolve miss: ticker=%s", ticker, exc_info=True)
        return ticker


def _csv_currency_for(ticker):
    """Stored-fact currency inference from the ticker suffix only.

    KR-listed tickers (``.KS`` / ``.KQ``) settle in KRW; everything else in
    USD. This is a deterministic property of the symbol itself, not a live
    FX rate or a computed value — it stays inside the raw-fact boundary.
    """
    if ticker and str(ticker).upper().endswith((".KS", ".KQ")):
        return "KRW"
    return "USD"


# Column order is fixed and documented so the CSV is stable across releases.
# Each tuple is (header, row->value). Only RAW stored fields are read.
_CSV_SPECS = {
    "trades": (
        ["traded_at", "ticker", "name", "action", "shares",
         "price_per_share", "total_value", "currency", "pnl"],
        lambda t: [
            _iso_or_none(getattr(t, "traded_at", None)) or "",
            t.ticker or "",
            # TradeHistory stores its own ``name`` at trade time; prefer that
            # stored fact, fall back to the registry lookup only if absent.
            getattr(t, "name", None) or _csv_resolve_name(t.ticker),
            getattr(t, "action", None) or "",
            t.shares if t.shares is not None else "",
            t.price_per_share if t.price_per_share is not None else "",
            t.total_value if t.total_value is not None else "",
            getattr(t, "currency", None) or _csv_currency_for(t.ticker),
            getattr(t, "pnl", None) if getattr(t, "pnl", None) is not None else "",
        ],
    ),
    "positions": (
        ["ticker", "name", "shares", "avg_cost", "currency", "added_at"],
        lambda p: [
            p.ticker or "",
            _csv_resolve_name(p.ticker),
            p.shares if p.shares is not None else "",
            p.avg_cost if p.avg_cost is not None else "",
            _csv_currency_for(p.ticker),
            _iso_or_none(getattr(p, "added_at", None)) or "",
        ],
    ),
    "watchlist": (
        ["ticker", "name", "note", "added_at"],
        lambda w: [
            w.ticker or "",
            _csv_resolve_name(w.ticker),
            getattr(w, "note", None) or "",
            _iso_or_none(getattr(w, "added_at", None)) or "",
        ],
    ),
    # ── Capital-gains lot detail (해외주식 양도소득세, lot별 상세) ──────────
    # Rows are CapitalGainLot NamedTuples from services.tax.capital_gains.
    # KRW columns are blank (never 0) when FX is unavailable; the note column
    # carries the reason (KR 비과세 / 환율 확인 불가).
    "capital_gains": (
        ["귀속연도", "종목코드", "종목명", "수량", "취득일", "양도일",
         "취득가USD", "양도가USD", "취득일환율", "양도일환율",
         "취득가KRW", "양도가KRW", "실현손익KRW", "과세대상", "note"],
        lambda lot: [
            lot.attribution_year or "",
            lot.ticker or "",
            lot.name or "",
            _csv_num(lot.quantity, 6),
            lot.buy_date or "",
            lot.sell_date or "",
            _csv_num(lot.buy_price_usd, 4),
            _csv_num(lot.sell_price_usd, 4),
            _csv_num(lot.buy_fx, 2),
            _csv_num(lot.sell_fx, 2),
            _csv_num(lot.buy_cost_krw, 0),
            _csv_num(lot.sell_proceeds_krw, 0),
            _csv_num(lot.realized_pnl_krw, 0),
            "과세" if lot.taxable else "비과세",
            lot.note or "",
        ],
    ),
    # ── Capital-gains yearly summary (연간 요약: 손익통산/공제/예상세액) ────
    # Rows are CapitalGainYear NamedTuples.
    "capital_gains_summary": (
        ["귀속연도", "거래수", "환율결손제외수", "취득가결손제외수",
         "합산실현손익KRW", "기본공제KRW", "과세표준KRW", "예상세액KRW(22%)"],
        lambda y: [
            y.attribution_year or "",
            y.trade_count,
            y.fx_missing_count,
            y.price_missing_count,
            _csv_num(y.total_realized_pnl_krw, 0),
            _csv_num(y.basic_deduction_krw, 0),
            _csv_num(y.taxable_base_krw, 0),
            _csv_num(y.estimated_tax_krw, 0),
        ],
    ),
    # ── Investment journal (PreTradeReflection — 본인 기록) ────────────────
    # intended_side is the user's OWN record of intent (a fact they entered),
    # not a signal/recommendation — mirrors how the trades CSV surfaces the
    # raw ``action``. Free-text rationale / devil-advocate pass through the
    # injection guard in _build_csv.
    "journal": (
        ["작성일", "종목코드", "종목명", "의도", "수량", "rationale",
         "devil_advocate_seen", "상태"],
        lambda r: [
            _iso_or_none(getattr(r, "created_at", None)) or "",
            getattr(r, "intended_ticker", None) or "",
            _csv_resolve_name(getattr(r, "intended_ticker", None)),
            getattr(r, "intended_side", None) or "",
            r.intended_shares if getattr(r, "intended_shares", None) is not None else "",
            getattr(r, "rationale", None) or "",
            getattr(r, "devil_advocate_seen", None) or "",
            r.status_label() if hasattr(r, "status_label") else "",
        ],
    ),
    # ── Weekly pulse (WeeklyPulse — 본인 기록) ─────────────────────────────
    "pulse": (
        ["제출일", "mood", "confidence", "worry", "learn", "topics"],
        lambda p: [
            _iso_or_none(getattr(p, "submitted_at", None)) or "",
            p.mood if getattr(p, "mood", None) is not None else "",
            p.confidence if getattr(p, "confidence", None) is not None else "",
            getattr(p, "worry", None) or "",
            getattr(p, "learn", None) or "",
            ", ".join(p.topics_list()) if hasattr(p, "topics_list") else "",
        ],
    ),
}


# CSV/formula-injection guard (CWE-1236): a cell that *starts* with one of
# these breaks out into a spreadsheet formula when the file is opened in
# Excel / Google Sheets / LibreOffice. Free-text fields (Watchlist.note, a
# resolved company name) are user-influenced, so we neutralise them by
# prefixing a single quote. Applied to STRING cells only — numeric cells
# (shares / price / pnl, incl. legitimately negative pnl like ``-5.0``) are
# never strings here, so a negative number is preserved verbatim.
_CSV_INJECT_LEADERS = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value):
    """Neutralise spreadsheet formula injection on a single CSV cell.

    Only string values that lead with a dangerous character are quoted;
    everything else (numbers, blanks) passes through unchanged.
    """
    if isinstance(value, str) and value and value[0] in _CSV_INJECT_LEADERS:
        return "'" + value
    return value


def _build_csv(dataset, rows, disclaimer=None):
    """Render ``rows`` of ``dataset`` to a UTF-8 (BOM-prefixed) CSV string.

    The UTF-8 BOM (``\\ufeff``) makes Excel on Windows/macOS auto-detect UTF-8
    so Hangul company names (삼성전자) render instead of mojibake. ``csv`` is
    the Python standard library — no new dependency.

    Every data cell passes through :func:`_safe_cell` so a user-supplied note
    or name can never smuggle a spreadsheet formula into the download.

    An empty dataset still emits the header row (honest: an empty CSV with
    columns, never fabricated data).

    ``disclaimer`` (optional): when set, a leading single-column comment row
    "# <text>" is written above the header — used by the capital-gains
    datasets to make the 참고용 추정 framing impossible to miss in a sheet.
    The text is run through :func:`_safe_cell` so it can never become a
    formula either.
    """
    header, row_fn = _CSV_SPECS[dataset]
    buf = io.StringIO()
    writer = csv.writer(buf)
    if disclaimer:
        writer.writerow([_safe_cell("# " + disclaimer)])
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe_cell(c) for c in row_fn(row)])
    return "﻿" + buf.getvalue()


def _capital_gain_rows(user_id):
    """Build (lots, summary) for the user's own overseas-equity capital gains.

    Pulls the user's TradeHistory (self-only), FIFO-matches via the shared
    :func:`fifo_match_closed_trades`, then computes lots + per-year summary
    with the STRICT FX resolver (``get_rate_at_strict``) so a missing
    historical rate yields a blank KRW cell + note, never a fabricated rate.
    """
    from services.profile.fifo_util import fifo_match_closed_trades
    from services.tax.capital_gains import (
        compute_capital_gain_lots,
        summarize_by_year,
    )
    from services.fx_service import get_rate_at_strict

    trades = (
        TradeHistory.query
        .filter_by(user_id=user_id)
        .order_by(TradeHistory.traded_at.asc())
        .limit(_EXPORT_TRADE_LIMIT)
        .all()
    )
    pairs = fifo_match_closed_trades(trades)
    lots = compute_capital_gain_lots(
        pairs,
        fx_resolver=get_rate_at_strict,
        name_resolver=lambda tk: _csv_resolve_name(tk),
    )
    summary = summarize_by_year(lots)
    return lots, summary


def _query_dataset_rows(user_id, dataset):
    """Query the user's own rows for one export dataset → ``(rows, disclaimer)``.

    Self-only scope (``user_id == current_user.id``). Shared by the CSV and the
    XLSX export paths so both stay in lock-step on what each dataset contains.
    """
    disclaimer = None
    if dataset == "trades":
        rows = (
            TradeHistory.query
            .filter_by(user_id=user_id)
            .order_by(TradeHistory.traded_at.desc())
            .limit(_EXPORT_TRADE_LIMIT)
            .all()
        )
    elif dataset == "positions":
        rows = (
            Position.query
            .filter_by(user_id=user_id)
            .order_by(Position.added_at.desc())
            .all()
        )
    elif dataset == "watchlist":
        rows = (
            Watchlist.query
            .filter_by(user_id=user_id)
            .order_by(Watchlist.added_at.desc())
            .all()
        )
    elif dataset in ("capital_gains", "capital_gains_summary"):
        # Both views derive from one FIFO+tax pass over the user's trades.
        from services.tax.capital_gains import DISCLAIMER_KR
        lots, summary = _capital_gain_rows(user_id)
        rows = lots if dataset == "capital_gains" else summary
        disclaimer = DISCLAIMER_KR
    elif dataset == "journal":
        rows = (
            PreTradeReflection.query
            .filter_by(user_id=user_id)
            .order_by(PreTradeReflection.created_at.desc())
            .limit(_EXPORT_REFLECTION_LIMIT)
            .all()
        )
    else:  # pulse (validated by caller against _CSV_DATASETS)
        rows = (
            WeeklyPulse.query
            .filter_by(user_id=user_id)
            .order_by(WeeklyPulse.submitted_at.desc())
            .limit(_EXPORT_PULSE_LIMIT)
            .all()
        )
    return rows, disclaimer


# Friendly per-sheet titles for the multi-sheet .xlsx workbook. Excel caps a
# sheet title at 31 chars and forbids []:*?/\ — all of these are safe.
_XLSX_SHEET_TITLES = {
    "trades": "거래내역",
    "positions": "보유종목",
    "watchlist": "관심종목",
    "capital_gains": "양도손익(상세)",
    "capital_gains_summary": "양도손익(연간)",
    "journal": "매매일지",
    "pulse": "주간펄스",
}

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# openpyxl raises IllegalCharacterError on XML-illegal control chars
# (\x00-\x08, \x0B, \x0C, \x0E-\x1F — tab/newline/CR are fine). Pasted user
# free-text (note / worry / rationale) can carry these; CSV tolerates them but
# an .xlsx cannot, so one stray control char would 500 the WHOLE workbook.
# Strip them. 32767 is Excel's hard per-cell character cap.
_XLSX_ILLEGAL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_XLSX_CELL_MAXLEN = 32767


def _xlsx_cell(value):
    """formula-injection guard + Decimal→float + non-finite guard + strip
    openpyxl-illegal chars + cap length, so no single user/computed cell can
    crash workbook generation or produce an Excel-invalid number."""
    import math
    from decimal import Decimal

    v = _safe_cell(value)
    if isinstance(v, Decimal):
        # Decimal('Infinity')/('NaN') are valid Decimals but become non-finite
        # floats; fall through to the isfinite guard below.
        try:
            v = float(v)
        except (ValueError, OverflowError):
            return None
    if isinstance(v, float) and not math.isfinite(v):
        # NaN / ±Inf are not valid spreadsheet numbers (well-formed XML but
        # Excel rejects them). Blank the cell rather than emit a bad workbook.
        return None
    if isinstance(v, str):
        v = _XLSX_ILLEGAL_RE.sub("", v)
        if len(v) > _XLSX_CELL_MAXLEN:
            v = v[:_XLSX_CELL_MAXLEN]
    return v


# Byte-identical to routes.behavior._TURNOVER_MIRROR_DISCLAIMER so every
# behaviour mirror reads with one legal voice (자본시장법 §49 — 사실 관찰, not
# advice). test_export_xlsx asserts the two never drift.
_ACTIVITY_MIRROR_DISCLAIMER = DISCLAIMER_MIRROR_RETROSPECTIVE_KR


def _activity_gross(mirror, code):
    """Pull one currency's gross traded value out of a turnover-mirror dict."""
    for row in (mirror.get("by_currency") or []):
        if (row.get("currency") or "").upper() == code:
            return row.get("gross_value")
    return None


def _build_activity_summary_sheet(wb, user_id):
    """Prepend an observational 'Activity' summary sheet built from the SAME
    vetted computation the in-app turnover mirror uses
    (services.behavior.turnover_mirror, surfaced at routes/behavior.py).

    Facts ONLY — BUY/SELL fill counts + per-currency gross traded value +
    hold-day median/mean, for all-history vs the last 30 days. There is
    deliberately NO turnover ratio, NO score/grade/label, and NO efficacy
    statistic (Barber&Odean / KCMI 회전율) — that juxtaposition would be an
    implicit "과잉거래" verdict (자본시장법 §49 advice + 표시광고법 efficacy
    risk), which the product intentionally avoids (DECISIONS.md AI 점수화 폐기;
    v55 research: non-judgmental beats judgmental). Best-effort: any failure
    leaves the workbook's data sheets untouched.
    """
    try:
        from models import TradeHistory
        from services.behavior.turnover_mirror import compute_turnover_mirror

        trades = TradeHistory.query.filter_by(user_id=user_id).all()
        m_all = compute_turnover_mirror(trades, period_days=None)
        m_30 = compute_turnover_mirror(trades, period_days=30)

        ws = wb.create_sheet(title="활동 요약", index=0)

        def _v(mirror, key):
            """Numeric fact, or '—' when the window lacks enough fills."""
            if not mirror.get("sufficient_data"):
                return "—"
            val = mirror.get(key)
            return val if val is not None else "—"

        ws.append([_xlsx_cell("활동 요약 · Activity Mirror")])
        ws.append([_xlsx_cell(_ACTIVITY_MIRROR_DISCLAIMER)])
        ws.append([])
        ws.append([_xlsx_cell(x) for x in ("구분", "전체 기록", "최근 30일")])
        rows = [
            ("매수 체결 (건)", "buy_count"),
            ("매도 체결 (건)", "sell_count"),
            ("총 체결 (건)", "trade_count"),
        ]
        for label, key in rows:
            ws.append([_xlsx_cell(label), _xlsx_cell(_v(m_all, key)), _xlsx_cell(_v(m_30, key))])
        # Per-currency gross traded value (KRW / USD reported separately —
        # never FX-merged, matching the mirror module).
        for label, code in (("거래대금 합계 (KRW)", "KRW"), ("거래대금 합계 (USD)", "USD")):
            a = _activity_gross(m_all, code) if m_all.get("sufficient_data") else None
            b = _activity_gross(m_30, code) if m_30.get("sufficient_data") else None
            ws.append([
                _xlsx_cell(label),
                _xlsx_cell(a if a is not None else "—"),
                _xlsx_cell(b if b is not None else "—"),
            ])
        for label, key in (("보유기간 중앙값 (일)", "median_hold_days"),
                           ("보유기간 평균 (일)", "mean_hold_days")):
            ws.append([_xlsx_cell(label), _xlsx_cell(_v(m_all, key)), _xlsx_cell(_v(m_30, key))])

        if not m_all.get("sufficient_data"):
            ws.append([])
            ws.append([_xlsx_cell("거래가 더 쌓이면 숫자가 표시됩니다.")])

        # Light formatting: bold title + the 구분 header row + label column.
        try:
            from openpyxl.styles import Font
            bold = Font(bold=True)
            ws.cell(1, 1).font = Font(bold=True, size=13)
            for c in range(1, 4):
                ws.cell(4, c).font = bold
            for r in range(5, ws.max_row + 1):
                ws.cell(r, 1).font = bold
            ws.column_dimensions["A"].width = 22
            ws.column_dimensions["B"].width = 16
            ws.column_dimensions["C"].width = 16
            for r in range(5, ws.max_row + 1):
                for c in (2, 3):
                    cell = ws.cell(r, c)
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = "#,##0.##"
        except Exception:
            logger.exception("activity summary styling failed (non-fatal)")
    except Exception:
        logger.exception("activity summary sheet failed (non-fatal) user_id=%s", user_id)


def _style_xlsx_sheet(ws, dataset, header, header_row):
    """Visual polish on a finished sheet: bold header, thousands-separator
    number format on numeric cells, estimated column widths, a frozen header,
    and an Excel Table (banded rows + auto-filter). Best-effort — any styling
    failure is swallowed so it can never break the export itself. The cell
    VALUES are never changed (only presentation), so the raw-fact guarantee and
    every value-level test still hold."""
    try:
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.table import Table, TableStyleInfo

        ncols = len(header)
        last_row = ws.max_row
        n_data = last_row - header_row

        bold = Font(bold=True)
        for c in range(1, ncols + 1):
            ws.cell(header_row, c).font = bold
            longest = 0
            for r in range(header_row, last_row + 1):
                cell = ws.cell(r, c)
                if r > header_row and isinstance(cell.value, (int, float)):
                    cell.number_format = "#,##0.####"
                if cell.value is not None:
                    longest = max(longest, len(str(cell.value)))
            ws.column_dimensions[get_column_letter(c)].width = max(10, min(48, longest + 2))

        # Freeze the header row so it stays visible while scrolling.
        ws.freeze_panes = ws.cell(header_row + 1, 1).coordinate

        # Convert the range into a real Excel Table (banded rows + auto-filter).
        # Excel requires ≥1 data row AND unique header names.
        if n_data >= 1 and len(set(header)) == ncols:
            ref = f"A{header_row}:{get_column_letter(ncols)}{last_row}"
            name = "tbl_" + re.sub(r"[^A-Za-z0-9_]", "_", str(dataset))
            tbl = Table(displayName=name, ref=ref)
            tbl.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2", showRowStripes=True,
                showColumnStripes=False, showFirstColumn=False,
                showLastColumn=False,
            )
            ws.add_table(tbl)
    except Exception:
        logger.exception("xlsx styling failed for %s (non-fatal)", dataset)


def _build_xlsx(user_id, datasets, include_summary=False):
    """Build a multi-sheet ``.xlsx`` workbook (one sheet per dataset) of the
    user's own data. Returns raw bytes. ``include_summary`` prepends the
    observational activity-mirror summary sheet (used for the full export only).

    Reuses the exact CSV column specs (``_CSV_SPECS``) + the same
    formula-injection guard (``_safe_cell``) so the Excel file carries the same
    raw-fact columns as the CSV — no live price, no computed metric, no advice.
    openpyxl is imported lazily (already a dependency for broker-statement
    import) so a non-xlsx request never pays for it. An empty dataset still
    emits its header row (honest empty sheet, never fabricated rows).
    """
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)  # drop the default empty sheet
    for dataset in datasets:
        header, row_fn = _CSV_SPECS[dataset]
        ws = wb.create_sheet(title=_XLSX_SHEET_TITLES.get(dataset, dataset)[:31])
        # Per-dataset isolation: one dataset that throws (e.g. a capital-gains
        # FIFO/FX edge case, or a single malformed row) must NOT kill the whole
        # workbook — the user still gets every other sheet. The failed sheet
        # carries its header + an honest note instead of fabricated data.
        try:
            rows, disclaimer = _query_dataset_rows(user_id, dataset)
            header_row = 1
            if disclaimer:
                ws.append([_xlsx_cell("# " + disclaimer)])
                header_row = 2
            ws.append([_xlsx_cell(h) for h in header])
            for r in rows:
                ws.append([_xlsx_cell(c) for c in row_fn(r)])
            _style_xlsx_sheet(ws, dataset, header, header_row)
        except Exception:
            logger.exception(
                "xlsx export: dataset %s failed — emitting header-only sheet",
                dataset,
            )
            # A freshly-created openpyxl sheet reports max_row == 1, so <= 1
            # means "nothing written yet" — add the header before the note.
            if ws.max_row <= 1:
                ws.append([_xlsx_cell(h) for h in header])
            ws.append(
                [_xlsx_cell("# 이 표는 일시적으로 생성하지 못했습니다 — 다시 시도해 주세요.")]
            )
    if include_summary:
        _build_activity_summary_sheet(wb, user_id)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _xlsx_export_response(user_id, datasets, now, include_summary=False):
    """Build the multi-sheet workbook and return it as an .xlsx download.

    Same self-only scope + no-store cache headers as the CSV path.
    """
    body = _build_xlsx(user_id, datasets, include_summary=include_summary)
    filename = f"pivoxquant-export-{now.strftime('%Y%m%d')}.xlsx"
    response = Response(body, mimetype=_XLSX_MIME)
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    # Personal data — never let an intermediate cache retain it.
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, private"
    )
    response.headers["Pragma"] = "no-cache"
    return response


def _csv_export_response(user_id, dataset, now):
    """Query the user's own ``dataset`` rows and return a CSV download Response.

    Scope is STRICTLY ``user_id == current_user.id`` — identical isolation
    rule to the JSON export. No user-id parameter is ever accepted.
    """
    rows, disclaimer = _query_dataset_rows(user_id, dataset)
    body = _build_csv(dataset, rows, disclaimer=disclaimer)
    filename = f"pivoxquant-{dataset}-{now.strftime('%Y%m%d')}.csv"
    response = Response(body, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    # Personal data — never let an intermediate cache retain it.
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, private"
    )
    response.headers["Pragma"] = "no-cache"
    return response


@profile_bp.route("/export", methods=["GET"])
@api_auth
@general_rate_limit
def export_profile():
    """PIPA §35 — Self-service personal data export.

    Returns the authenticated user's complete personal data record as a
    downloadable JSON file. This satisfies 개인정보보호법 §35 ① (정보주체
    열람권) and §35 ④ (10일 이내 열람) by making the data available
    instantly rather than requiring an email request workflow.

    Scope: STRICTLY ``user_id == current_user.id``. Every query is
    filtered by the current user's id. The endpoint never accepts a
    user-id parameter — there is no admin-impersonation path.

    Coverage (PIPA §35 §2, 2026-05-30): every user-owned table is reachable
    here. Scope is the user's own rows only — tables reached via a parent FK
    (ai_twin_positions / ai_twin_trades → ai_twin_portfolios.id) resolve the
    user's parent ids first, then filter. Global / non-user tables
    (signal_cache, persona_group_stats, processed_stripe_events,
    agent_kill_switch) are out of scope. Keep in sync with the two deletion
    paths (auth.py:delete_account + pipa_purge.py:_delete_user_cascade).

    Excluded (PII minimization — the user may not self-exfiltrate secrets):
        - password_hash
        - stripe_customer_id / checkout session_id
        - oauth_id / oauth refresh_token
        - broker credentials + tokens (encrypted_* / access_token /
          refresh_token) — see _serialize via BrokerConnection.to_dict
        - push subscription endpoint + p256dh + auth keys
        - portfolio_share token
        - other users' rows (never queried)

    Response headers:
        Content-Type: application/json
        Content-Disposition: attachment; filename="pivoxquant_export_<id>_<date>.json"

    Frontend hook: settings page "내 데이터 다운로드" button (TBD, separate PR).

    Optional CSV mode (spreadsheet-friendly raw-fact slice):
        ?format=csv&dataset=trades|positions|watchlist
    returns a single tabular dataset as ``text/csv`` instead of the full JSON
    record. CSV columns are RAW stored fields only — no live price, no computed
    metric, no FX conversion, no advice. Same self-only scope, same auth gate.
    The default (no ``format``) remains the complete §35 JSON export, unchanged.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # ── CSV branch — focused tabular download ────────────────────────────
    # Handled before the heavy JSON compilation so a CSV request never pays
    # for the 26-table JSON gather. Still self-only scoped.
    export_format = (request.args.get("format") or "").strip().lower()
    if export_format == "csv":
        dataset = (request.args.get("dataset") or "").strip().lower()
        if dataset not in _CSV_DATASETS:
            return api_error(
                en=(
                    "Invalid CSV dataset. Use one of: "
                    + ", ".join(_CSV_DATASETS)
                ),
                kr=(
                    "잘못된 CSV 데이터셋입니다. "
                    + " / ".join(_CSV_DATASETS)
                    + " 중 하나를 선택하세요."
                ),
                code="PROFILE_EXPORT_BAD_DATASET", status=400,
            )
        try:
            return _csv_export_response(current_user.id, dataset, now)
        except Exception:
            logger.exception(
                "profile.export_profile CSV failed (user_id=%s dataset=%s)",
                current_user.id, dataset,
            )
            return api_error(
                en="Failed to compile CSV export. Please try again.",
                kr="CSV 내보내기 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
                code="PROFILE_EXPORT_FAILED", status=500,
            )

    # ── XLSX branch — multi-sheet Excel workbook of the raw-fact datasets ──
    # No ``dataset`` param → every dataset becomes its own sheet in one .xlsx.
    # An optional ``?dataset=`` narrows to a single sheet. Same self-only scope
    # + same raw-fact columns as CSV (no live price / metric / advice).
    if export_format in ("xlsx", "excel"):
        ds_param = (request.args.get("dataset") or "").strip().lower()
        if ds_param and ds_param not in _CSV_DATASETS:
            return api_error(
                en="Invalid Excel dataset. Use one of: " + ", ".join(_CSV_DATASETS),
                kr=(
                    "잘못된 엑셀 데이터셋입니다. "
                    + " / ".join(_CSV_DATASETS)
                    + " 중 하나를 선택하세요."
                ),
                code="PROFILE_EXPORT_BAD_DATASET", status=400,
            )
        datasets = [ds_param] if ds_param else list(_CSV_DATASETS)
        try:
            # Full export (no single dataset requested) leads with the
            # observational activity-mirror summary sheet.
            return _xlsx_export_response(
                current_user.id, datasets, now, include_summary=not ds_param,
            )
        except Exception:
            logger.exception(
                "profile.export_profile XLSX failed (user_id=%s)", current_user.id,
            )
            return api_error(
                en="Failed to compile Excel export. Please try again.",
                kr="엑셀 내보내기 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
                code="PROFILE_EXPORT_FAILED", status=500,
            )

    # PIPA §35 ④ requires the export to reflect the *live* consent state,
    # not whatever Flask-Login cached for this request. Marketing opt-out
    # state can change via the one-click unsubscribe email link mid-session
    # (`routes/email_preferences.py`), and `current_user` is a LocalProxy
    # backed by SQLAlchemy's identity map which keeps a snapshot from the
    # session-load. Force a fresh column read so the export never lies
    # about a consent that was just flipped.
    user_id = current_user.id
    try:
        db.session.refresh(current_user._get_current_object())
    except Exception:
        # If refresh fails (detached / deleted between hops), fall back to
        # an explicit fresh fetch — same effect, slightly slower path.
        db.session.expire(current_user._get_current_object())
    user = current_user

    try:
        positions = Position.query.filter_by(user_id=user_id).all()
        watchlist = Watchlist.query.filter_by(user_id=user_id).all()
        trades = (
            TradeHistory.query
            .filter_by(user_id=user_id)
            .order_by(TradeHistory.traded_at.desc())
            .limit(_EXPORT_TRADE_LIMIT)
            .all()
        )
        alerts = (
            Alert.query
            .filter_by(user_id=user_id)
            .order_by(Alert.created_at.desc())
            .limit(_EXPORT_ALERT_LIMIT)
            .all()
        )
        investment_profile = (
            InvestmentProfile.query.filter_by(user_id=user_id).first()
        )
        # PIPA §35 — behavioural / pulse / persona / NPS rows are the
        # user's own personal data (all purged on deletion, confirming
        # they're personal data; WeeklyPulse holds free-text worry/learn).
        behavioral_scores = (
            BehavioralScore.query
            .filter_by(user_id=user_id)
            .order_by(BehavioralScore.week_ending.desc())
            .limit(_EXPORT_BEHAVIORAL_LIMIT)
            .all()
        )
        weekly_pulse = (
            WeeklyPulse.query
            .filter_by(user_id=user_id)
            .order_by(WeeklyPulse.submitted_at.desc())
            .limit(_EXPORT_PULSE_LIMIT)
            .all()
        )
        persona_snapshots = (
            PersonaSnapshot.query
            .filter_by(user_id=user_id)
            .order_by(PersonaSnapshot.computed_at.desc())
            .limit(_EXPORT_PERSONA_LIMIT)
            .all()
        )
        nps_feedback = (
            NpsFeedback.query
            .filter_by(user_id=user_id)
            .order_by(NpsFeedback.created_at.desc())
            .limit(_EXPORT_NPS_LIMIT)
            .all()
        )
        # PIPA §35 — pre-trade reflections carry user free-text rationale +
        # devil's-advocate-seen flag (PII; purged on deletion). Scoped to the
        # current user only, exactly like every other section above.
        pre_trade_reflections = (
            PreTradeReflection.query
            .filter_by(user_id=user_id)
            .order_by(PreTradeReflection.id.desc())
            .limit(_EXPORT_REFLECTION_LIMIT)
            .all()
        )

        # ── PIPA §35 §2 — remaining user-owned sections ──────────────────
        # All scoped to user_id (or, where the table is reached via a parent
        # FK, to the user's own parent rows). Credential / token / endpoint
        # secrets are excluded by the dedicated serializers above.
        artifacts = (
            Artifact.query
            .filter_by(user_id=user_id)
            .order_by(Artifact.created_at.desc())
            .limit(_EXPORT_ARTIFACT_LIMIT)
            .all()
        )
        artifact_feedback = (
            ArtifactFeedback.query
            .filter_by(user_id=user_id)
            .order_by(ArtifactFeedback.id.desc())
            .limit(_EXPORT_ARTIFACT_FEEDBACK_LIMIT)
            .all()
        )
        # broker_connections.to_dict() already omits every encrypted_*
        # column + access/refresh tokens (see models/broker_connection.py);
        # it exposes only broker, status and a has_credentials boolean.
        broker_connections = (
            BrokerConnection.query
            .filter_by(user_id=user_id)
            .order_by(BrokerConnection.id.asc())
            .all()
        )
        user_referrals = (
            UserReferral.query
            .filter_by(user_id=user_id)
            .order_by(UserReferral.id.asc())
            .limit(_EXPORT_REFERRAL_LIMIT)
            .all()
        )
        position_dd_checks = (
            PositionDDCheck.query
            .filter_by(user_id=user_id)
            .order_by(PositionDDCheck.id.desc())
            .limit(_EXPORT_DD_CHECK_LIMIT)
            .all()
        )
        inquiries = (
            Inquiry.query
            .filter_by(user_id=user_id)
            .order_by(Inquiry.created_at.desc())
            .limit(_EXPORT_INQUIRY_LIMIT)
            .all()
        )
        companion_waitlist = (
            CompanionWaitlist.query
            .filter_by(user_id=user_id)
            .order_by(CompanionWaitlist.id.desc())
            .limit(_EXPORT_WAITLIST_LIMIT)
            .all()
        )
        portfolio_shares = (
            PortfolioShare.query
            .filter_by(user_id=user_id)
            .order_by(PortfolioShare.id.desc())
            .limit(_EXPORT_PORTFOLIO_SHARE_LIMIT)
            .all()
        )
        push_subscriptions = (
            PushSubscription.query
            .filter_by(user_id=user_id)
            .order_by(PushSubscription.id.desc())
            .limit(_EXPORT_PUSH_SUB_LIMIT)
            .all()
        )
        scheduled_emails = (
            ScheduledEmail.query
            .filter_by(user_id=user_id)
            .order_by(ScheduledEmail.scheduled_send_at.desc())
            .limit(_EXPORT_SCHEDULED_EMAIL_LIMIT)
            .all()
        )
        checkout_expirations = (
            CheckoutExpiration.query
            .filter_by(user_id=user_id)
            .order_by(CheckoutExpiration.created_at.desc())
            .limit(_EXPORT_CHECKOUT_EXPIRATION_LIMIT)
            .all()
        )

        # AI Twin (paper-only) — portfolio is keyed by user_id; its positions
        # and trades are keyed by twin_id (the portfolio's PK), so resolve the
        # user's twin ids first, then ``.in_()`` filter. No cross-user leak:
        # the id set is derived solely from this user's portfolios.
        ai_twin_portfolios = (
            AITwinPortfolio.query
            .filter_by(user_id=user_id)
            .order_by(AITwinPortfolio.id.asc())
            .all()
        )
        twin_ids = [p.id for p in ai_twin_portfolios]
        if twin_ids:
            ai_twin_positions = (
                AITwinPosition.query
                .filter(AITwinPosition.twin_id.in_(twin_ids))
                .order_by(AITwinPosition.id.desc())
                .limit(_EXPORT_TWIN_POSITION_LIMIT)
                .all()
            )
            ai_twin_trades = (
                AITwinTrade.query
                .filter(AITwinTrade.twin_id.in_(twin_ids))
                .order_by(AITwinTrade.executed_at.desc())
                .limit(_EXPORT_TWIN_TRADE_LIMIT)
                .all()
            )
        else:
            ai_twin_positions = []
            ai_twin_trades = []
        ai_twin_weekly_reports = (
            AITwinWeeklyReport.query
            .filter_by(user_id=user_id)
            .order_by(AITwinWeeklyReport.week_ending.desc())
            .limit(_EXPORT_TWIN_REPORT_LIMIT)
            .all()
        )

        # ── P1 — login / funnel activity history ─────────────────────────
        # auth_events is keyed by email (not user_id) because a fail can
        # fire before the user row exists; filter by the current user's
        # live email. funnel_events is keyed by a user_id integer snapshot
        # (no FK) — the user's own acquisition/activation event trail.
        auth_events = (
            AuthEvent.query
            .filter(AuthEvent.email == user.email)
            .order_by(AuthEvent.created_at.desc())
            .limit(_EXPORT_AUTH_EVENT_LIMIT)
            .all()
        )
        funnel_events = (
            FunnelEvent.query
            .filter_by(user_id=user_id)
            .order_by(FunnelEvent.created_at.desc())
            .limit(_EXPORT_FUNNEL_EVENT_LIMIT)
            .all()
        )
    except Exception:
        logger.exception(
            "profile.export_profile query failed (user_id=%s)", user_id,
        )
        return api_error(
            en="Failed to compile export. Please try again.",
            kr="데이터 내보내기 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            code="PROFILE_EXPORT_FAILED", status=500,
        )

    payload = {
        "format_version": "1.0",
        "exported_at": now.isoformat() + "Z",
        "legal_basis": "개인정보보호법 §35 (정보주체 열람권)",
        "scope": "self_only",
        "user": _serialize_user(user),
        "positions": [_serialize_position(p) for p in positions],
        "watchlist": [_serialize_watchlist(w) for w in watchlist],
        "trade_history": [_serialize_trade(t) for t in trades],
        "alerts": [_serialize_alert(a) for a in alerts],
        "investment_profile": (
            investment_profile.to_dict() if investment_profile else None
        ),
        "behavioral_scores": [b.to_dict() for b in behavioral_scores],
        "weekly_pulse": [p.to_dict() for p in weekly_pulse],
        "persona_snapshots": [s.to_dict() for s in persona_snapshots],
        "nps_feedback": [n.to_dict() for n in nps_feedback],
        "pre_trade_reflections": [r.to_dict() for r in pre_trade_reflections],
        "artifacts": [a.to_dict() for a in artifacts],
        "artifact_feedback": [f.to_dict() for f in artifact_feedback],
        "broker_connections": [b.to_dict() for b in broker_connections],
        "user_referrals": [r.to_dict() for r in user_referrals],
        "position_dd_checks": [d.to_dict() for d in position_dd_checks],
        # Inquiry.to_dict(detail=True) — include the user's own subject/body
        # and any admin reply; this is their personal data under §35.
        "inquiries": [i.to_dict(detail=True) for i in inquiries],
        "companion_waitlist": [
            _serialize_companion_waitlist(w) for w in companion_waitlist
        ],
        "portfolio_shares": [
            _serialize_portfolio_share(s) for s in portfolio_shares
        ],
        "push_subscriptions": [
            _serialize_push_subscription(p) for p in push_subscriptions
        ],
        "scheduled_emails": [
            _serialize_scheduled_email(e) for e in scheduled_emails
        ],
        "checkout_expirations": [
            _serialize_checkout_expiration(c) for c in checkout_expirations
        ],
        "ai_twin_portfolios": [p.to_dict() for p in ai_twin_portfolios],
        "ai_twin_positions": [p.to_dict() for p in ai_twin_positions],
        "ai_twin_trades": [t.to_dict() for t in ai_twin_trades],
        "ai_twin_weekly_reports": [r.to_dict() for r in ai_twin_weekly_reports],
        "auth_events": [e.to_dict() for e in auth_events],
        "funnel_events": [e.to_dict() for e in funnel_events],
        "counts": {
            "positions": len(positions),
            "watchlist": len(watchlist),
            "trade_history": len(trades),
            "alerts": len(alerts),
            "behavioral_scores": len(behavioral_scores),
            "weekly_pulse": len(weekly_pulse),
            "persona_snapshots": len(persona_snapshots),
            "nps_feedback": len(nps_feedback),
            "pre_trade_reflections": len(pre_trade_reflections),
            "artifacts": len(artifacts),
            "artifact_feedback": len(artifact_feedback),
            "broker_connections": len(broker_connections),
            "user_referrals": len(user_referrals),
            "position_dd_checks": len(position_dd_checks),
            "inquiries": len(inquiries),
            "companion_waitlist": len(companion_waitlist),
            "portfolio_shares": len(portfolio_shares),
            "push_subscriptions": len(push_subscriptions),
            "scheduled_emails": len(scheduled_emails),
            "checkout_expirations": len(checkout_expirations),
            "ai_twin_portfolios": len(ai_twin_portfolios),
            "ai_twin_positions": len(ai_twin_positions),
            "ai_twin_trades": len(ai_twin_trades),
            "ai_twin_weekly_reports": len(ai_twin_weekly_reports),
            "auth_events": len(auth_events),
            "funnel_events": len(funnel_events),
        },
        "notes": {
            "excluded_fields": [
                "password_hash",
                "stripe_customer_id",
                "oauth_id",
                "oauth_refresh_token",
                # PIPA §35 §2 — own-secret material withheld from the export:
                # the user cannot self-exfiltrate their own credentials/keys.
                "broker_connection.encrypted_app_key",
                "broker_connection.encrypted_app_secret",
                "broker_connection.encrypted_account_no",
                "broker_connection.encrypted_access_token",
                "broker_connection.access_token",
                "broker_connection.refresh_token",
                "push_subscription.endpoint",
                "push_subscription.p256dh",
                "push_subscription.auth",
                "portfolio_share.token",
                "checkout_expiration.session_id",
                "companion_waitlist.email_hash",
            ],
            "trade_limit": _EXPORT_TRADE_LIMIT,
            "alert_limit": _EXPORT_ALERT_LIMIT,
            # Synchronization note (feedback_thorough_fixes): the set of
            # user-owned tables enumerated here MUST stay in sync with the two
            # deletion paths — routes/auth.py:delete_account and
            # scripts/nightly/pipa_purge.py:_delete_user_cascade. Adding a new
            # user-owned model requires updating all THREE locations.
            "contact": (
                "If you need older records or additional data not included "
                "here, contact privacy@pivoxquant.com per PIPA §35."
            ),
        },
    }

    response = jsonify(payload)
    filename = f"pivoxquant_export_{user_id}_{now.strftime('%Y%m%d')}.json"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    # Prevent any intermediate caches from storing personal data.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    return response
