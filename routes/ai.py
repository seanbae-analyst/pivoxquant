"""AI analysis routes: SWOT, competitor, sector trend, chat, coaching, earnings tone, sector regime.

Legal boundary
--------------
Every AI response MUST pass through ``legal_filter.scrub_response`` before
``jsonify`` — this is the last runtime defense against 자본시장법 §6 (미등록
투자자문업) and §101 (불공정 영업행위) violations. Use ``_scrub_and_jsonify``
helper instead of calling ``jsonify`` directly.
"""
import json
import logging
import os
from flask import Blueprint, request, jsonify, Response
from flask_login import current_user

from models import Position, SignalCache

# 2026-05-17 wave 13 P0 — detail-leak gate. routes/ai.py wraps the
# Anthropic SDK; `ai.last_error` strings frequently embed sensitive
# upstream context: "Your credit balance is too low", request-id,
# model name, organization hint, and (in some SDK versions) the
# leading prefix of the API key. The pre-fix code forwarded that
# string as `body["detail"]` on every 503 response, unconditionally.
# That surfaced provider identity + credit state to anyone hitting
# an authenticated endpoint. Production responses now scrub the
# detail; dev / test deployments keep it so operator debugging
# stays cheap.
_AI_DETAIL_IN_RESPONSE = (
    os.environ.get("FLASK_ENV", "development").lower() != "production"
)
from security import ai_rate_limit
from services.container import ai, fetcher
from services import cache_service, fx_service
from services.access_guard import is_user_allowed_ticker, access_denied_response
from services.error_responses import api_error
from services.legal_filter import scrub_response
from services.ai.models import EarningsCallToneAnalyzer, AISectorRotation, AIRiskSummary
from .decorators import api_auth, require_tier

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _scrub_and_jsonify(payload, status: int = 200):
    """Deep-scrub AI payload through legal_filter, then jsonify.

    This is the single exit point for every AI response in this module — do
    NOT call ``jsonify(ai_result)`` directly; it would bypass §6 / §101 the
    legal boundary. Non-AI errors (e.g. {"error": "AI not configured"}) also
    go through this path (idempotent on dicts with no risky text).
    """
    return jsonify(scrub_response(payload)), status


def _extract_ticker_from_payload(d: dict) -> str:
    """Pull ticker out of an AI request body, checking nested ``snapshot``
    too — engine.analyze() output is typically the analysis_data and stores
    the ticker at the top level. Empty string if missing.
    """
    if not isinstance(d, dict):
        return ""
    t = (d.get("ticker") or "").strip()
    if not t and isinstance(d.get("snapshot"), dict):
        t = (d["snapshot"].get("ticker") or "").strip()
    return t.upper()


@ai_bp.route("/status")
@api_auth
def status():
    return jsonify({"available": ai.available})


@ai_bp.route("/swot", methods=["POST"])
@api_auth
@require_tier("pro")
@ai_rate_limit
def swot():
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    d = request.get_json() or {}
    # §101 회피 — SWOT 은 종목 단위 분석이므로 보유/관심 외 ticker 거부.
    ticker = _extract_ticker_from_payload(d)
    if not ticker:
        return api_error(
            en="ticker is required",
            kr="종목 코드가 필요합니다.",
            code="AI_TICKER_REQUIRED",
            status=400,
        )
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status
    result = ai.generate_swot(d)
    if result:
        return _scrub_and_jsonify(result)
    # Bug #14: was an opaque 500 ("Failed to generate SWOT"); the AAPL detail
    # page surfaced it as "Failed to generate SWOT" with no clue why. The
    # generator swallows the upstream Anthropic exception per its public
    # contract (returns None on transient errors — see test_ai_failure_paths)
    # but stashes the type+message in ``ai.last_error`` for diagnostics.
    detail = getattr(ai, "last_error", None)
    body = {
        "error": "Failed to generate SWOT",
        "error_kr": "SWOT 분석을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    }
    if detail and _AI_DETAIL_IN_RESPONSE:
        body["detail"] = detail
    body["retry_after"] = 60  # B-08 graceful
    return jsonify(body), 503


@ai_bp.route("/competitor", methods=["POST"])
@api_auth
@require_tier("pro")
@ai_rate_limit
def competitor():
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    d = request.get_json() or {}
    ticker = d.get("ticker", "")
    # §101 회피 — competitor 분석은 ticker 기준이므로 보유/관심 외 거부.
    ticker_check = _extract_ticker_from_payload(d)
    if not ticker_check:
        return api_error(
            en="ticker is required",
            kr="종목 코드가 필요합니다.",
            code="AI_TICKER_REQUIRED",
            status=400,
        )
    if not is_user_allowed_ticker(current_user.id, ticker_check):
        body, status = access_denied_response()
        return jsonify(body), status
    target_sector = d.get("sector", d.get("snapshot", {}).get("sector", ""))
    peers = []
    # Intentional global scan: peer discovery requires sampling every cached
    # ticker to find sector matches. Single query (not N+1). Sector column
    # would let this become an indexed filter; deferred until SignalCache
    # schema migration.
    for sc in SignalCache.query.all():
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == target_sector and sc.ticker != ticker:
                peers.append(sd)
        except Exception:
            logger.debug("silent-fallback: competitor", exc_info=True)
            pass
    result = ai.generate_competitor_analysis(d, peers[:8])
    if result:
        return _scrub_and_jsonify(result)
    detail = getattr(ai, "last_error", None)
    body = {
        "error": "Failed to generate competitor analysis",
        "error_kr": "경쟁사 분석을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    }
    if detail and _AI_DETAIL_IN_RESPONSE:
        body["detail"] = detail
    body["retry_after"] = 60  # B-08 graceful
    return jsonify(body), 503


@ai_bp.route("/sector-trend", methods=["POST"])
@api_auth
@require_tier("pro")
@ai_rate_limit
def sector_trend():
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    d = request.get_json() or {}
    # §101 회피 — sector-trend 가 ticker 와 함께 호출되는 경우 (예: Detail page
    # context) 에는 ticker 화이트리스트 검사를 우선 적용. ticker 없이 sector
    # 만으로 호출되는 경우 (Discover/Market 위젯) 는 통과 (sector 통계는 정보
    # 매체성 데이터).
    ticker_check = _extract_ticker_from_payload(d)
    if ticker_check and not is_user_allowed_ticker(current_user.id, ticker_check):
        body, status = access_denied_response()
        return jsonify(body), status
    sector = d.get("sector", "")
    stocks = []
    # Intentional global scan: sector-trend aggregates every cached ticker
    # in the sector. Single query (not N+1). See competitor() comment.
    for sc in SignalCache.query.all():
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == sector:
                stocks.append(sd)
        except Exception:
            logger.debug("silent-fallback: sector_trend", exc_info=True)
            pass
    result = ai.generate_sector_trend(sector, stocks[:10])
    if result:
        return _scrub_and_jsonify(result)
    detail = getattr(ai, "last_error", None)
    body = {
        "error": "Failed to generate sector trend",
        "error_kr": "섹터 트렌드 분석을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    }
    if detail and _AI_DETAIL_IN_RESPONSE:
        body["detail"] = detail
    body["retry_after"] = 60  # B-08 graceful
    return jsonify(body), 503


@ai_bp.route("/chat", methods=["POST"])
@api_auth
@require_tier("pro")
@ai_rate_limit
def chat():
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    d = request.get_json() or {}
    message = (d.get("message") or "").strip()
    # Bug #3 (Wave F-1) — incoming `history` is user-controlled but flows
    # straight into Anthropic `messages` API at services/ai/service.py:333.
    # Without role/content validation a caller can inject a fake `assistant`
    # turn carrying advisory language; Claude will trust it as prior context
    # and continue the pattern, defeating SYSTEM_PROMPT compliance. Cap the
    # window to last 10 turns and 1000 chars/content to bound prompt cost too.
    raw_history = d.get("history") or []
    history: list[dict] = []
    if isinstance(raw_history, list):
        for h in raw_history[-10:]:
            if not isinstance(h, dict):
                continue
            role = h.get("role")
            content = h.get("content")
            if role not in ("user", "assistant"):
                continue
            if not isinstance(content, str) or not content:
                continue
            history.append({"role": role, "content": content[:1000]})
    if not message:
        return api_error(
            en="Message required",
            kr="메시지가 필요합니다.",
            code="AI_MESSAGE_REQUIRED",
            status=400,
        )

    positions = Position.query.filter_by(user_id=current_user.id).all()
    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}
    sig_cache = {}
    for p in positions:
        c = cache_map.get(p.ticker)
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
@api_auth
@require_tier("pro")
@ai_rate_limit
def commentary():
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    d = request.get_json() or {}
    # §101 회피 — commentary 가 단일 ticker 분석과 함께 호출되는 경우만 가드.
    ticker_check = _extract_ticker_from_payload(d)
    if ticker_check and not is_user_allowed_ticker(current_user.id, ticker_check):
        body, status = access_denied_response()
        return jsonify(body), status
    result = ai.generate_commentary(d)
    if result:
        return _scrub_and_jsonify(result)
    detail = getattr(ai, "last_error", None)
    body = {
        "error": "Failed to generate commentary",
        "error_kr": "코멘터리를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    }
    if detail and _AI_DETAIL_IN_RESPONSE:
        body["detail"] = detail
    body["retry_after"] = 60  # B-08 graceful
    return jsonify(body), 503


@ai_bp.route("/morning-summary", methods=["POST"])
@api_auth
@require_tier("pro")
@ai_rate_limit
def morning_summary():
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    d = request.get_json() or {}
    result = ai.generate_morning_summary(d)
    if result:
        return _scrub_and_jsonify(result)
    detail = getattr(ai, "last_error", None)
    body = {
        "error": "Failed to generate summary",
        "error_kr": "요약을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    }
    if detail and _AI_DETAIL_IN_RESPONSE:
        body["detail"] = detail
    body["retry_after"] = 60  # B-08 graceful
    return jsonify(body), 503


@ai_bp.route("/coaching", methods=["POST"])
@api_auth
@require_tier("pro")
@ai_rate_limit
def coaching():
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"insight": "Add some positions first to use the AI Assistant!",
                        "insight_kr": "AI Assistant를 사용하려면 먼저 포지션을 추가하세요!"})
    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}
    sig_cache = {}
    for p in positions:
        c = cache_map.get(p.ticker)
        if c and c.data_json:
            sig_cache[p.ticker] = json.loads(c.data_json)
    context = ai.build_portfolio_context(current_user, positions, sig_cache)
    result = ai.generate_coaching(context)
    if result:
        return _scrub_and_jsonify(result)
    detail = getattr(ai, "last_error", None)
    body = {
        "error": "Failed to generate coaching",
        "error_kr": "코칭 메시지를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    }
    if detail and _AI_DETAIL_IN_RESPONSE:
        body["detail"] = detail
    body["retry_after"] = 60  # B-08 graceful
    return jsonify(body), 503


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
    # Include the Companion / owner tiers (premium_plus rank 3, founding_lifetime
    # rank 4 in routes/decorators._TIER_RANK) so top-tier accounts are never
    # blocked from a Pro+ feature. effective_tier returns founding_lifetime for
    # DEV_FOUNDING_EMAILS; subscription_tier may carry premium_plus directly.
    return tier in ("pro", "premium", "premium_plus", "founding_lifetime")


@ai_bp.route("/earnings-tone", methods=["POST"])
@api_auth
@ai_rate_limit
def earnings_tone():
    """Analyze earnings call transcript sentiment for a ticker (Pro/Premium).
    Body: {"ticker": "AAPL"} or {"ticker": "AAPL", "transcript": "..."}
    Returns cached result when available (90-day TTL).
    """
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503

    d = request.get_json() or {}
    ticker = (d.get("ticker") or "").strip()
    if not ticker:
        return api_error(
            en="ticker is required",
            kr="종목 코드가 필요합니다.",
            code="AI_TICKER_REQUIRED",
            status=400,
        )
    transcript = d.get("transcript")
    if transcript is not None and not isinstance(transcript, str):
        return api_error(
            en="transcript must be a string",
            kr="transcript 필드는 문자열이어야 합니다.",
            code="AI_TRANSCRIPT_INVALID",
            status=400,
        )

    ticker = ticker.upper()

    # §101 회피 — earnings tone 은 ticker 단위 분석이므로 화이트리스트 검사.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

    # 1) Cache hit — serve cached result regardless of tier (already paid for).
    #    But tier-gate: free users cannot retrieve results either.
    if not _earnings_tone_tier_ok(current_user):
        return jsonify({
            "error": "Earnings tone analysis is a Pro feature. Please upgrade.",
            "error_kr": "실적 톤 분석은 Pro 전용 기능입니다. 업그레이드해 주세요.",
            "upgrade_required": True,
        }), 403

    # P0-1 (Wave H-2): cross-user cache poisoning guard.
    # A Pro user can POST an arbitrary `transcript` (fabricated or from a
    # private earnings call). If we cached that result under the ticker key,
    # every other user's GET would receive the tampered analysis for 90 days.
    # Defence: transcript-supplied results are NEVER written to the shared
    # cache. Only the official path (no transcript) uses the shared cache.
    if transcript:
        # User-supplied transcript: bypass shared cache entirely (read + write).
        # Still gate the Claude budget so a malicious Pro user can't burn $$ at
        # no cost by flooding custom transcripts.
        if not cache_service.earnings_tone_budget_check_and_increment():
            return jsonify({
                "error": "Daily earnings-tone analysis limit reached. Please try again tomorrow.",
                "error_kr": "오늘의 실적 톤 분석 한도를 모두 사용했습니다. 내일 다시 시도해 주세요.",
                "budget_exceeded": True,
            }), 429
        result, status_code = EarningsCallToneAnalyzer.analyze(ticker, transcript_text=transcript)
        # NOTE: intentionally NOT calling earnings_tone_cache_set() here.
        return _scrub_and_jsonify(result, status_code)

    # Official path (no transcript): shared cache read is safe.
    cached = cache_service.earnings_tone_cache_get(ticker)
    if cached is not None:
        return _scrub_and_jsonify({**cached, "cached": True}, 200)

    # 2) Cache miss — enforce daily Claude budget before spending tokens.
    if not cache_service.earnings_tone_budget_check_and_increment():
        return jsonify({
            "error": "Daily earnings-tone analysis limit reached. Please try again tomorrow.",
            "error_kr": "오늘의 실적 톤 분석 한도를 모두 사용했습니다. 내일 다시 시도해 주세요.",
            "budget_exceeded": True,
        }), 429

    # 3) Run analyzer (also writes to ai_models internal 24h cache).
    result, status_code = EarningsCallToneAnalyzer.analyze(ticker, transcript_text=None)

    # 4) Persist to 90-day cache on success so engine.analyze() can surface it.
    if status_code == 200 and isinstance(result, dict) and "error" not in result:
        cache_service.earnings_tone_cache_set(ticker, result)

    return _scrub_and_jsonify(result, status_code)


@ai_bp.route("/earnings-tone/<ticker>", methods=["GET"])
@api_auth
@ai_rate_limit
def earnings_tone_get(ticker):
    """Lazy-load earnings tone for a single ticker (Pro/Premium).
    Cache-first: returns cached result when fresh (<=90d), otherwise triggers
    one Claude call subject to daily budget. Designed for the Detail page.
    """
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503

    if not ticker or not isinstance(ticker, str):
        return api_error(
            en="ticker is required",
            kr="종목 코드가 필요합니다.",
            code="AI_TICKER_REQUIRED",
            status=400,
        )

    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 20:
        return api_error(
            en="Invalid ticker",
            kr="유효하지 않은 종목 코드입니다.",
            code="AI_TICKER_INVALID",
            status=400,
        )

    # §101 회피 — earnings tone 은 ticker 단위 분석이므로 화이트리스트 검사.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

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
@api_auth
@require_tier("pro")
@ai_rate_limit
def sector_regime():
    """Classify current macro regime and return historical sector performance.
    No parameters needed — uses current macro data automatically.
    LEGAL: Informational only. Does not recommend buying or selling sectors.
    """
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503
    result, status_code = AISectorRotation.analyze()
    return _scrub_and_jsonify(result, status_code)


# ── AI Risk Summary (GREEN — pure analysis, no advisory) ──────────────────────

@ai_bp.route("/risk-summary", methods=["POST"])
@api_auth
@require_tier("pro")
@ai_rate_limit
def risk_summary():
    """Generate a plain-language risk summary for the user's portfolio.

    Body (optional): {"var_data": {...}, "stress_data": {...}}
    If omitted, only portfolio-level data is used.
    LEGAL: GREEN — analysis of user's own data, no advisory content.
    """
    if not ai.available:
        return jsonify({
            "error": "AI not configured",
            "error_kr": "AI 서비스가 일시적으로 사용 불가합니다. 잠시 후 다시 시도해 주세요.",
            "code": "AI_NOT_CONFIGURED",
        }), 503

    # Build portfolio_data from user's positions
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return api_error(
            en="No positions in portfolio",
            kr="포트폴리오에 보유 종목이 없습니다.",
            code="AI_NO_POSITIONS",
            status=400,
        )

    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    # FX normalization (Pattern 7 fix — mirrors portfolio.py:260-272).
    # KR tickers price in KRW, US tickers in USD. Naive `price * shares` sum
    # mixed both numeraires, inflating total_value ~700x for KRW positions
    # (e.g. ₩75,000 read as $75,000). The downstream Claude prompt uses
    # `${value}` so we converge to USD: KR positions divided by spot USD/KRW.
    fx_rate = fx_service.get_rate()  # USD/KRW spot; identical to portfolio.py
    total_value = 0.0
    max_position_value = 0.0
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        price = sd.get("price", p.avg_cost)
        is_kr = (
            p.ticker.upper().endswith(".KS")
            or p.ticker.upper().endswith(".KQ")
            or sd.get("is_korean", False)
        )
        mv_native = price * p.shares
        mv_usd = (mv_native / fx_rate) if (is_kr and fx_rate) else mv_native
        total_value += mv_usd
        if mv_usd > max_position_value:
            max_position_value = mv_usd

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

    # Pattern 10 (prompt injection defense) — request body is fully
    # user-controlled. AIRiskSummary embeds these fields into the Claude
    # prompt, so we whitelist the exact subset we render and coerce types
    # before pass-through. Any extra keys an attacker tacks on are dropped
    # on the floor. AIRiskSummary applies a second sanitization layer (cap
    # + type check) as defense in depth.
    raw_var = d.get("var_data") if isinstance(d.get("var_data"), dict) else None
    raw_stress = (
        d.get("stress_data") if isinstance(d.get("stress_data"), dict) else None
    )
    var_data = None
    if raw_var is not None:
        try:
            cvar_clean = float(raw_var.get("cvar_95_pct", 0) or 0)
        except (TypeError, ValueError):
            cvar_clean = 0.0
        var_data = {"cvar_95_pct": cvar_clean}
    stress_data = None
    if raw_stress is not None:
        worst_raw = raw_stress.get("most_vulnerable_scenario")
        worst_clean = worst_raw[:200] if isinstance(worst_raw, str) else None
        stress_data = {"most_vulnerable_scenario": worst_clean}

    # user_id is MANDATORY: AIRiskSummary caches by (user_id, value); omitting
    # it would let two Pro users with the same portfolio value share a cache
    # entry (cross-user PII leakage — Pattern 6, mirror of earnings_tone fix
    # in v44.9 PR #488 + v45.2 d1867a74).
    result, status_code = AIRiskSummary.generate(
        portfolio_data, var_data, stress_data, user_id=current_user.id,
    )
    return _scrub_and_jsonify(result, status_code)
