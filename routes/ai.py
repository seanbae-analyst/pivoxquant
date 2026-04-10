"""AI analysis routes: SWOT, competitor, sector trend, chat, coaching."""
import json
from flask import Blueprint, request, jsonify, Response
from flask_login import current_user

from extensions import db
from models import Position, SignalCache
from security import ai_rate_limit
from services.container import ai, fetcher
from .decorators import api_auth

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@ai_bp.route("/status")
@api_auth
def status():
    return jsonify({"available": ai.available})


@ai_bp.route("/swot", methods=["POST"])
@ai_rate_limit
@api_auth
def swot():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_swot(d)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate SWOT"}), 500


@ai_bp.route("/competitor", methods=["POST"])
@ai_rate_limit
@api_auth
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
        return jsonify(result)
    return jsonify({"error": "Failed to generate competitor analysis"}), 500


@ai_bp.route("/sector-trend", methods=["POST"])
@ai_rate_limit
@api_auth
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
        return jsonify(result)
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
            for chunk in ai.chat_stream(message, history, context):
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@ai_bp.route("/commentary", methods=["POST"])
@ai_rate_limit
@api_auth
def commentary():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_commentary(d)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate commentary"}), 500


@ai_bp.route("/morning-summary", methods=["POST"])
@ai_rate_limit
@api_auth
def morning_summary():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_morning_summary(d)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate summary"}), 500


@ai_bp.route("/coaching", methods=["POST"])
@ai_rate_limit
@api_auth
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
        return jsonify(result)
    return jsonify({"error": "Failed to generate coaching"}), 500
