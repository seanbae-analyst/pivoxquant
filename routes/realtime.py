"""Real-time price streaming routes."""
import json
import time
import threading
from collections import defaultdict
from flask import Blueprint, jsonify, Response
from flask_login import current_user

from models import Position
from services.container import realtime
from services.market_status import get_market_status
from .decorators import api_auth

realtime_bp = Blueprint("realtime", __name__, url_prefix="/api/realtime")

# ── SSE Connection Limiter ──────────────────────────────────────────────────
# Prevents DoS via unlimited SSE connections per user.
_MAX_SSE_PER_USER = 3
_sse_connections = defaultdict(int)   # user_id -> active count
_sse_lock = threading.Lock()

# ── SSE cadence (seconds) ───────────────────────────────────────────────────
# Tiered by market open status: ultra-tight cadence intraday so prices
# in /portfolio and /watchlist feel genuinely live; relaxed off-hours
# so we don't spin the event loop or upstream APIs for no benefit.
INTERVAL_OPEN = 5
INTERVAL_CLOSED = 30


def _stream_interval() -> int:
    """Pick push cadence based on live market status.

    Returns INTERVAL_OPEN when either US or KR market is tradable
    (regular / pre / after), else INTERVAL_CLOSED. Failures fall back
    to the safer long interval so we never hammer a broken status path.
    """
    try:
        st = get_market_status() or {}
        us = (st.get("us") or {}).get("tradable", False)
        kr = (st.get("kr") or {}).get("tradable", False)
        return INTERVAL_OPEN if (us or kr) else INTERVAL_CLOSED
    except Exception:
        return INTERVAL_CLOSED


@realtime_bp.route("/stream")
@api_auth
def stream():
    user_id = current_user.id

    # ── SSE connection limit check ──
    with _sse_lock:
        if _sse_connections[user_id] >= _MAX_SSE_PER_USER:
            return jsonify({
                "error": "Too many concurrent SSE connections.",
                "error_kr": "동시 SSE 연결 수가 초과되었습니다.",
                "code": "SSE_LIMIT_EXCEEDED",
            }), 429

    positions = Position.query.filter_by(user_id=user_id).all()
    tickers = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"error": "No positions"}), 400

    def generate():
        with _sse_lock:
            _sse_connections[user_id] += 1
        try:
            while True:
                try:
                    prices = realtime.get_prices_batch(tickers)
                    yield f"data: {json.dumps(prices, ensure_ascii=False)}\n\n"
                except Exception as e:
                    import logging as _logging
                    _logging.getLogger(__name__).error(f"SSE price stream error: {e}")
                    yield f"data: {json.dumps({'error': 'Price update failed'})}\n\n"
                # Heartbeat to detect dead connections
                yield ": heartbeat\n\n"
                time.sleep(_stream_interval())
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                _sse_connections[user_id] = max(0, _sse_connections[user_id] - 1)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@realtime_bp.route("/portfolio-stream")
@api_auth
def portfolio_stream():
    """SSE endpoint: streams portfolio price updates every 30 seconds."""
    user_id = current_user.id

    # ── SSE connection limit check ──
    with _sse_lock:
        if _sse_connections[user_id] >= _MAX_SSE_PER_USER:
            return jsonify({
                "error": "Too many concurrent SSE connections.",
                "error_kr": "동시 SSE 연결 수가 초과되었습니다.",
                "code": "SSE_LIMIT_EXCEEDED",
            }), 429

    positions = Position.query.filter_by(user_id=user_id).all()
    tickers = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"error": "No positions"}), 400

    def generate():
        with _sse_lock:
            _sse_connections[user_id] += 1
        try:
            while True:
                try:
                    batch = realtime.get_prices_batch(tickers)
                    prices = {}
                    full = {}
                    positions_arr = []
                    for t, info in batch.items():
                        px = info.get("price", 0)
                        obs = info.get("timestamp")
                        prices[t] = px
                        full[t] = {
                            "price": px,
                            "price_display": info.get("price_display", ""),
                            "change_pct": info.get("change_pct"),
                            "observed_at": obs,
                        }
                        # Alias shape so the frontend /positions consumer can
                        # mutate its SWR cache directly off this event.
                        positions_arr.append({
                            "ticker": t,
                            "symbol": t,
                            "price": px,
                            "current_price": px,
                            "change_pct": info.get("change_pct"),
                            "timestamp": obs,
                            "observed_at": obs,
                        })
                    payload = json.dumps({
                        "prices": prices,
                        "details": full,
                        "positions": positions_arr,
                    }, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                except Exception as e:
                    import logging as _logging
                    _logging.getLogger(__name__).error(f"SSE portfolio stream error: {e}")
                    yield f"data: {json.dumps({'error': 'Portfolio update failed'})}\n\n"
                yield ": heartbeat\n\n"
                time.sleep(_stream_interval())
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                _sse_connections[user_id] = max(0, _sse_connections[user_id] - 1)

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
            "us": "alpaca" if realtime.alpaca_available else "fmp",
            "kr": "kis" if realtime.kis_available else "fmp",
        }
    })
