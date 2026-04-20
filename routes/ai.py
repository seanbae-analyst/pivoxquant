"""AI analysis routes: SWOT, competitor, sector trend, chat, coaching, earnings tone, sector regime.

Legal boundary
--------------
Every AI response MUST pass through ``legal_filter.scrub_response`` before
``jsonify`` — this is the last runtime defense against 자본시장법 §6 (미등록
투자자문업) and §101 (불공정 영업행위) violations. Use ``_scrub_and_jsonify``
helper instead of calling ``jsonify`` directly.
"""
import json
from flask import Blueprint, request, jsonify, Response
from flask_login import current_user

from extensions import db
from models import Position, SignalCache
from security import ai_rate_limit
from services.container import ai, fetcher
from services import cache_service
from services.legal_filter import scrub_response
from ai_models import EarningsCallToneAnalyzer, AISectorRotation, AIRiskSummary
from .decorators import api_auth, require_tier

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _scrub_and_jsonify(payload, status: int = 200):
    """Deep-scrub AI payload through legal_filter, then jsonify.

    This is the single exit point for every AI response in this module — do
    NOT call ``jsonify(ai_result)`` directly; it would bypass §6 / §101 the
    legal boundary. Non-AI errors (e.g. {"error": "AI not configured"}) also
    go through this path (idempotent on dicts with no risky text).
    """
    return jsonify(scrub_response(payload)), status


@ai_bp.route("/status")
@api_auth
def status():
    return jsonify({"available": ai.available})


@ai_bp.route("/swot", methods=["POST"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def swot():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_swot(d)
    if result:
        return _scrub_and_jsonify(result)
    return jsonify({"error": "Failed to generate SWOT"}), 500


@ai_bp.route("/competitor", methods=["POST"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def competitor():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    ticker = d.get("ticker", "")
    target_sector = d.get("sector", d.get("snapshot", {}).get("sector", ""))
    peers = []
    for sc in SignalCache.query.all():
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == target_sector and sc.ticker != ticker:
                peers.append(sd)
        except Exception:
            pass
    result = ai.generate_competitor_analysis(d, peers[:8])
    if result:
        return _scrub_and_jsonify(result)
    return jsonify({"error": "Failed to generate competitor analysis"}), 500


@ai_bp.route("/sector-trend", methods=["POST"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def sector_trend():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    sector = d.get("sector", "")
    stocks = []
    for sc in SignalCache.query.all():
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == sector:
                stocks.append(sd)
        except Exception:
            pass
    result = ai.generate_sector_trend(sector, stocks[:10])
    if result:
        return _scrub_and_jsonify(result)
    return jsonify({"error": "Failed to generate sector trend"}), 500


@ai_bp.route("/chat", methods=["POST"])
@ai_rate_limit
@api_auth
def chat():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    message = (d.get("message") or "").strip()
    history = d.get("history") or []
    if not message:
        return jsonify({"error": "Message required"}), 400

    positions = Position.query.filter_by(user_id=current_user.id).all()
    sig_cache = {}
    for p in positions:
        c = db.session.get(SignalCache, p.ticker)
        if c and c.data_json:
            sig_cache[p.ticker] = json.loads(c.data_json)

    try:
        macro = fetcher.get_macro_data()
    except Exception:
        macro = {}

    context = ai.build_portfolio_context(current_user, positions, sig_cache, macro)

    def generate():
        try:
            from services.legal_filter import safe_scrub
            for chunk in ai.chat_stream(message, history, context):
                # SSE 스트림 경계에서도 §6 / §101 방어선 유지.
                safe_chunk = safe_scrub(chunk, context="ai.chat.stream") or ""
                yield f"data: {json.dumps({'text': safe_chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).error(f"AI chat stream error: {e}")
            yield f"data: {json.dumps({'error': 'An error occurred during AI processing.'})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@ai_bp.route("/commentary", methods=["POST"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def commentary():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_commentary(d)
    if result:
        return _scrub_and_jsonify(result)
    return jsonify({"error": "Failed to generate commentary"}), 500


@ai_bp.route("/morning-summary", methods=["POST"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def morning_summary():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_morning_summary(d)
    if result:
        return _scrub_and_jsonify(result)
    return jsonify({"error": "Failed to generate summary"}), 500


@ai_bp.route("/coaching", methods=["POST"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def coaching():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"insight": "Add some positions first to get AI coaching!",
                        "insight_kr": "AI 코칭을 받으려면 먼저 포지션을 추가하세요!"})
    sig_cache = {}
    for p in positions:
        c = db.session.get(SignalCache, p.ticker)
        if c and c.data_json:
            sig_cache[p.ticker] = json.loads(c.data_json)
    context = ai.build_portfolio_context(current_user, positions, sig_cache)
    result = ai.generate_coaching(context)
    if result:
        return _scrub_and_jsonify(result)
    return jsonify({"error": "Failed to generate coaching"}), 500


# ── Earnings Call Tone Analyzer (GREEN) ──────────────────────────────────────
# Cost control strategy:
#   1. Lazy-load: never called from engine.analyze() (the hot path).
#   2. Tier-gated: Pro / Premium only. Free users receive 403.
#   3. Cache: 90-day in-memory cache (earnings cycle is quarterly).
#   4. Daily budget: hard cap of 50 fresh Claude calls per UTC day across
#      the whole app to bound worst-case Anthropic spend.
#   5. Flask-Limiter: 10 req/min/user on top.

def _earnings_tone_tier_ok(user) -> bool:
    tier = (
        getattr(user, "effective_tier", None)
        or getattr(user, "subscription_tier", "free")
        or "free"
    ).lower()
    return tier in ("pro", "premium")


@ai_bp.route("/earnings-tone", methods=["POST"])
@ai_rate_limit
@api_auth
def earnings_tone():
    """Analyze earnings call transcript sentiment for a ticker (Pro/Premium).
    Body: {"ticker": "AAPL"} or {"ticker": "AAPL", "transcript": "..."}
    Returns cached result when available (90-day TTL).
    """
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503

    d = request.get_json() or {}
    ticker = (d.get("ticker") or "").strip()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    transcript = d.get("transcript")
    if transcript is not None and not isinstance(transcript, str):
        return jsonify({"error": "transcript must be a string"}), 400

    ticker = ticker.upper()

    # 1) Cache hit — serve cached result regardless of tier (already paid for).
    #    But tier-gate: free users cannot retrieve results either.
    if not _earnings_tone_tier_ok(current_user):
        return jsonify({
            "error": "Earnings tone analysis is a Pro feature. Please upgrade.",
            "error_kr": "실적 톤 분석은 Pro 전용 기능입니다. 업그레이드해 주세요.",
            "upgrade_required": True,
        }), 403

    cached = cache_service.earnings_tone_cache_get(ticker)
    if cached is not None and transcript is None:
        return _scrub_and_jsonify({**cached, "cached": True}, 200)

    # 2) Cache miss — enforce daily Claude budget before spending tokens.
    if not cache_service.earnings_tone_budget_check_and_increment():
        return jsonify({
            "error": "Daily earnings-tone analysis limit reached. Please try again tomorrow.",
            "error_kr": "오늘의 실적 톤 분석 한도를 모두 사용했습니다. 내일 다시 시도해 주세요.",
            "budget_exceeded": True,
        }), 429

    # 3) Run analyzer (also writes to ai_models internal 24h cache).
    result, status_code = EarningsCallToneAnalyzer.analyze(ticker, transcript)

    # 4) Persist to 90-day cache on success so engine.analyze() can surface it.
    if status_code == 200 and isinstance(result, dict) and "error" not in result:
        cache_service.earnings_tone_cache_set(ticker, result)

    return _scrub_and_jsonify(result, status_code)


@ai_bp.route("/earnings-tone/<ticker>", methods=["GET"])
@ai_rate_limit
@api_auth
def earnings_tone_get(ticker):
    """Lazy-load earnings tone for a single ticker (Pro/Premium).
    Cache-first: returns cached result when fresh (<=90d), otherwise triggers
    one Claude call subject to daily budget. Designed for the Detail page.
    """
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503

    if not ticker or not isinstance(ticker, str):
        return jsonify({"error": "ticker is required"}), 400

    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 20:
        return jsonify({"error": "Invalid ticker"}), 400

    if not _earnings_tone_tier_ok(current_user):
        return jsonify({
            "error": "Earnings tone analysis is a Pro feature. Please upgrade.",
            "error_kr": "실적 톤 분석은 Pro 전용 기능입니다. 업그레이드해 주세요.",
            "upgrade_required": True,
        }), 403

    cached = cache_service.earnings_tone_cache_get(ticker)
    if cached is not None:
        return _scrub_and_jsonify({**cached, "cached": True}, 200)

    if not cache_service.earnings_tone_budget_check_and_increment():
        return jsonify({
            "error": "Daily earnings-tone analysis limit reached. Please try again tomorrow.",
            "error_kr": "오늘의 실적 톤 분석 한도를 모두 사용했습니다. 내일 다시 시도해 주세요.",
            "budget_exceeded": True,
        }), 429

    result, status_code = EarningsCallToneAnalyzer.analyze(ticker)
    if status_code == 200 and isinstance(result, dict) and "error" not in result:
        cache_service.earnings_tone_cache_set(ticker, result)

    return _scrub_and_jsonify(result, status_code)


# ── AI Sector Regime Classification (YELLOW — informational only) ────────────

@ai_bp.route("/sector-regime", methods=["GET"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def sector_regime():
    """Classify current macro regime and return historical sector performance.
    No parameters needed — uses current macro data automatically.
    LEGAL: Informational only. Does not recommend buying or selling sectors.
    """
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    result, status_code = AISectorRotation.analyze()
    return _scrub_and_jsonify(result, status_code)


# ── AI Risk Summary (GREEN — pure analysis, no advisory) ──────────────────────

@ai_bp.route("/risk-summary", methods=["POST"])
@ai_rate_limit
@api_auth
@require_tier("pro")
def risk_summary():
    """Generate a plain-language risk summary for the user's portfolio.

    Body (optional): {"var_data": {...}, "stress_data": {...}}
    If omitted, only portfolio-level data is used.
    LEGAL: GREEN — analysis of user's own data, no advisory content.
    """
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503

    # Build portfolio_data from user's positions
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"error": "No positions in portfolio"}), 400

    total_value = 0.0
    max_position_value = 0.0
    for p in positions:
        cached = SignalCache.query.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        price = sd.get("price", p.avg_cost)
        mv = price * p.shares
        total_value += mv
        if mv > max_position_value:
            max_position_value = mv

    top_pct = (max_position_value / total_value * 100) if total_value > 0 else 0

    d = request.get_json() or {}

    portfolio_data = {
        "value": total_value,
        "annual_vol": d.get("annual_vol", 0),
        "var_95": d.get("var_95", 0),
        "max_dd": d.get("max_dd", 0),
        "sharpe": d.get("sharpe", 0),
        "top_pct": top_pct,
    }

    var_data = d.get("var_data")
    stress_data = d.get("stress_data")

    result, status_code = AIRiskSummary.generate(portfolio_data, var_data, stress_data)
    return _scrub_and_jsonify(result, status_code)
