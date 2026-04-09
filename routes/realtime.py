"""Real-time price streaming routes."""
import json
import time
from flask import Blueprint, jsonify, Response
from flask_login import current_user

from models import Position
from services.container import realtime
from .decorators import api_auth

realtime_bp = Blueprint("realtime", __name__, url_prefix="/api/realtime")


@realtime_bp.route("/stream")
@api_auth
def stream():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"error": "No positions"}), 400

    def generate():
        try:
            while True:
                try:
                    prices = realtime.get_prices_batch(tickers)
                    yield f"data: {json.dumps(prices, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                # Heartbeat to detect dead connections
                yield ": heartbeat\n\n"
                time.sleep(5)
        except GeneratorExit:
            pass

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@realtime_bp.route("/portfolio-stream")
@api_auth
def portfolio_stream():
    """SSE endpoint: streams portfolio price updates every 30 seconds."""
    user_id = current_user.id
    positions = Position.query.filter_by(user_id=user_id).all()
    tickers = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"error": "No positions"}), 400

    def generate():
        try:
            while True:
                try:
                    batch = realtime.get_prices_batch(tickers)
                    prices = {}
                    full = {}
                    for t, info in batch.items():
                        prices[t] = info.get("price", 0)
                        full[t] = {
                            "price": info.get("price", 0),
                            "price_display": info.get("price_display", ""),
                            "change_pct": info.get("change_pct"),
                        }
                    payload = json.dumps({"prices": prices, "details": full}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield ": heartbeat\n\n"
                time.sleep(30)
        except GeneratorExit:
            pass

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@realtime_bp.route("/price/<ticker>")
@api_auth
def single(ticker):
    p = realtime.get_price(ticker.upper())
    if p:
        return jsonify(p)
    return jsonify({"error": f"No price for {ticker}"}), 404


@realtime_bp.route("/status")
@api_auth
def status():
    return jsonify({
        "alpaca": realtime.alpaca_available,
        "kis": realtime.kis_available,
        "sources": {
            "us": "alpaca" if realtime.alpaca_available else "yfinance",
            "kr": "kis" if realtime.kis_available else "yfinance",
        }
    })
