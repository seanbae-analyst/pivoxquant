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
import json
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import (
    ArtifactFeedback,
    InvestmentProfile,
    VALID_CADENCES,
    VOTE_CHOICES,
    WeeklyPulse,
)
from models.investment_profile import calculate_profile_type
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
from .decorators import api_auth
from security import general_rate_limit, limiter

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
        from questionnaire import QUESTIONNAIRE_V2
        return jsonify({"questions": QUESTIONNAIRE_V2})
    except ImportError:
        # Fallback to v1 if questionnaire.py not available
        return jsonify({"questions": QUESTIONNAIRE})


@profile_bp.route("/onboarding", methods=["POST"])
@api_auth
@general_rate_limit
def submit_onboarding():
    """Submit onboarding answers → calculate profile → save → return result."""
    data = request.get_json() or {}
    answers = data.get("answers", {})

    # Try v2 classification first (20-question), fall back to v1
    profile_v2_result = None
    try:
        from questionnaire import calculate_profile_v2
        profile_v2_result = calculate_profile_v2(answers)
        profile_type = profile_v2_result.get("investor_type", "risk_managed_growth")
    except (ImportError, Exception):
        profile_type = calculate_profile_type(answers)

    # Create or update investment profile
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = InvestmentProfile(user_id=current_user.id)
        db.session.add(profile)

    # Store answers
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

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.submit_onboarding commit failed (user_id=%s)", current_user.id)
        return jsonify({"error": "Failed to save onboarding answers. Please try again."}), 500

    return jsonify({
        "ok": True,
        "profile_type": profile_type,
        "profile": profile.to_dict(),
        "message": f"Profile set to {profile_type.title()}. Quant engine parameters updated.",
    })


@profile_bp.route("", methods=["GET"])
@api_auth
def get_profile():
    """Get current user's investment profile."""
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        return jsonify({"profile": None, "has_profile": False})

    return jsonify({
        "profile": profile.to_dict(),
        "has_profile": True,
        "changes_left": current_user.profile_changes_left,
        "subscription_tier": current_user.subscription_tier,
    })


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
        return jsonify({"error": str(err)}), 400

    if keep_usd and keep_krw:
        return jsonify({"error": "Provide at least one of available_capital_usd or available_capital_krw"}), 400

    if not keep_usd:
        current_user.available_capital = usd
    if not keep_krw:
        current_user.available_capital_krw = krw

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.update_capital commit failed (user_id=%s)", current_user.id)
        return jsonify({"error": "Failed to update capital. Please try again."}), 500

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
    if current_user.subscription_tier == "free" and current_user.profile_changes_left <= 0:
        return jsonify({"error": "Profile change limit reached. Upgrade to Pro for unlimited changes."}), 403

    data = request.get_json() or {}
    answers = data.get("answers", {})
    profile_type = calculate_profile_type(answers)

    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        return jsonify({"error": "No profile found. Complete onboarding first."}), 404

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
    if current_user.subscription_tier == "free":
        current_user.profile_changes_left -= 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("profile.update_profile commit failed (user_id=%s)", current_user.id)
        return jsonify({"error": "Failed to update profile. Please try again."}), 500

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
def get_persona_analysis():
    """Return declared + observed persona for Layer 2 hero card.

    Shape: see ``PersonaResponse`` in ``frontend/src/lib/cfo/hooks.ts``.
    """
    try:
        payload = compute_persona_response(current_user.id)
    except Exception:
        logger.exception("profile.get_persona_analysis failed (user_id=%s)", current_user.id)
        return jsonify({"error": "Failed to compute persona"}), 500
    return jsonify(payload)


@profile_bp.route("/persona-detail", methods=["GET"])
@api_auth
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
        return jsonify({"error": "Failed to compute persona detail"}), 500
    return jsonify(payload)


@profile_bp.route("/persona-explain", methods=["GET"])
@api_auth
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
        return jsonify({"error": "Failed to compute persona explanation"}), 500
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
        return jsonify({"error": "Failed to compute rolling window"}), 500
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
        return jsonify({"error": "artifact_id is required"}), 400
    if not section:
        return jsonify({"error": "section is required"}), 400
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
        return jsonify({"error": "Failed to save feedback"}), 500

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
        return jsonify({"error": "mood and confidence must be integers 1..5"}), 400
    if not (1 <= mood <= 5 and 1 <= confidence <= 5):
        return jsonify({"error": "mood and confidence must be integers 1..5"}), 400

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
        return jsonify({"error": "Failed to save pulse"}), 500

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
        return jsonify({"error": "window must be one of 30, 90, 365"}), 400

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

    return jsonify({
        "available": True,
        "persona": persona,
        "persona_label": PERSONA_LABELS.get(persona, persona),
        "window_days": window,
        "stats": stats,
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
        return jsonify({"error": "window must be one of 30, 90, 365"}), 400

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
            out[persona] = {
                "available": True,
                "label": label,
                "stats": stats,
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
        return jsonify({"error": "Failed to load persona history"}), 500

    return jsonify({
        "snapshots": snapshots,
        "n": len(snapshots),
        "days": days,
        "disclaimer": DRIFT_DISCLAIMER,
    })


@profile_bp.route("/persona-drift", methods=["GET"])
@api_auth
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
        return jsonify({"error": "Failed to compute persona drift"}), 500

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
        return jsonify({"error": "Failed to take persona snapshot"}), 500

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
        return jsonify({"error": str(err)}), 400

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
        return jsonify({"error": "Failed to update email preferences"}), 500

    return jsonify({
        "ok": True,
        "preferences": {
            "email_opt_out": bool(current_user.email_opt_out),
            "email_opt_out_earnings": bool(current_user.email_opt_out_earnings),
        },
    })
