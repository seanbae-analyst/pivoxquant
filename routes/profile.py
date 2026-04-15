"""Investment profile routes: onboarding, get/update profile, questionnaire."""
import json
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import InvestmentProfile
from models.investment_profile import calculate_profile_type, PROFILE_PRESETS
from .decorators import api_auth

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

    db.session.commit()

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


@profile_bp.route("", methods=["PUT"])
@api_auth
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

    db.session.commit()

    return jsonify({
        "ok": True,
        "profile_type": profile_type,
        "profile": profile.to_dict(),
        "changes_left": current_user.profile_changes_left,
    })
