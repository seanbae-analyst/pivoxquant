"""Real-time price streaming routes."""
import json
import logging
import time
import threading
from collections import defaultdict
from flask import Blueprint, jsonify, Response
from flask_login import current_user

from models import Position
from services.container import realtime
from services.market_status import get_market_status
from .decorators import api_auth

logger = logging.getLogger(__name__)

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

    # ── SSE connection limit check (atomic check + increment) ──
    with _sse_lock:
        if _sse_connections[user_id] >= _MAX_SSE_PER_USER:
            return jsonify({
                "error": "Too many concurrent SSE connections.",
                "error_kr": "동시 SSE 연결 수가 초과되었습니다.",
                "code": "SSE_LIMIT_EXCEEDED",
            }), 429
        _sse_connections[user_id] += 1

    try:
        positions = Position.query.filter_by(user_id=user_id).all()
        tickers = [p.ticker for p in positions]
        if not tickers:
            with _sse_lock:
                _sse_connections[user_id] = max(0, _sse_connections[user_id] - 1)
            return jsonify({"error": "No positions"}), 400
    except Exception:
        with _sse_lock:
            _sse_connections[user_id] = max(0, _sse_connections[user_id] - 1)
        raise

    # SSE-1 fix (2026-05-09): refresh ticker list every 60s so newly-added
    # positions stream prices without manual reconnect.
    _TICKER_REFRESH_EVERY = 60

    def generate():
        local_tickers = list(tickers)
        last_refresh = time.monotonic()
        try:
            while True:
                try:
                    if time.monotonic() - last_refresh >= _TICKER_REFRESH_EVERY:
                        try:
                            fresh = Position.query.filter_by(user_id=user_id).all()
                            new_tickers = [p.ticker for p in fresh]
                            if new_tickers != local_tickers:
                                logger.info(
                                    "SSE price stream ticker delta user=%s old=%d new=%d",
                                    user_id, len(local_tickers), len(new_tickers),
                                )
                                local_tickers = new_tickers
                        except Exception:
                            logger.exception("SSE ticker refresh failed user=%s", user_id)
                        last_refresh = time.monotonic()

                    prices = realtime.get_prices_batch(local_tickers) if local_tickers else {}
                    yield f"data: {json.dumps(prices, ensure_ascii=False)}\n\n"
                except Exception:
                    logger.exception("SSE price stream error user=%s", user_id)
                    yield f"data: {json.dumps({'error': 'Price update failed'})}\n\n"
                # Heartbeat to detect dead connections
                yield ": heartbeat\n\n"
                time.sleep(_stream_interval())
        except GeneratorExit:
            # Client closed the connection — expected, not an error.
            logger.debug("SSE price stream closed user=%s", user_id)
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

    # ── SSE connection limit check (atomic check + increment) ──
    with _sse_lock:
        if _sse_connections[user_id] >= _MAX_SSE_PER_USER:
            return jsonify({
                "error": "Too many concurrent SSE connections.",
                "error_kr": "동시 SSE 연결 수가 초과되었습니다.",
                "code": "SSE_LIMIT_EXCEEDED",
            }), 429
        _sse_connections[user_id] += 1

    try:
        positions = Position.query.filter_by(user_id=user_id).all()
        tickers = [p.ticker for p in positions]
        if not tickers:
            with _sse_lock:
                _sse_connections[user_id] = max(0, _sse_connections[user_id] - 1)
            return jsonify({"error": "No positions"}), 400
    except Exception:
        with _sse_lock:
            _sse_connections[user_id] = max(0, _sse_connections[user_id] - 1)
        raise

    # SSE-1: same as /stream above.
    _TICKER_REFRESH_EVERY_PORTFOLIO = 60

    def generate():
        local_tickers = list(tickers)
        last_refresh = time.monotonic()
        try:
            while True:
                try:
                    if time.monotonic() - last_refresh >= _TICKER_REFRESH_EVERY_PORTFOLIO:
                        try:
                            fresh = Position.query.filter_by(user_id=user_id).all()
                            new_tickers = [p.ticker for p in fresh]
                            if new_tickers != local_tickers:
                                logger.info(
                                    "SSE portfolio stream ticker delta user=%s old=%d new=%d",
                                    user_id, len(local_tickers), len(new_tickers),
                                )
                                local_tickers = new_tickers
                        except Exception:
                            logger.exception("SSE portfolio ticker refresh failed user=%s", user_id)
                        last_refresh = time.monotonic()

                    batch = realtime.get_prices_batch(local_tickers) if local_tickers else {}
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
                except Exception:
                    logger.exception("SSE portfolio stream error user=%s", user_id)
                    yield f"data: {json.dumps({'error': 'Portfolio update failed'})}\n\n"
                yield ": heartbeat\n\n"
                time.sleep(_stream_interval())
        except GeneratorExit:
            # Client closed the connection — expected, not an error.
            logger.debug("SSE portfolio stream closed user=%s", user_id)
        finally:
            with _sse_lock:
                _sse_connections[user_id] = max(0, _sse_connections[user_id] - 1)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@realtime_bp.route("/price/<ticker>")
@api_auth
def single(ticker):
    """Single-ticker realtime price.

    Response shape:
      - 200 + quote dict (may include ``"stale": true`` + ``"stale_at"``
        when FMP budget/cooldown forced a stale-cache fallback).
      - 503 + ``{"error": "data_provider_throttled"}`` when FMP is
        budget-exhausted or every primary provider is unavailable AND
        no stale cache exists. Signals the client to retry later
        rather than treating the ticker as permanently missing.
      - 404 + ``{"error": "ticker_not_found", ...}`` when providers
        responded but have no data for this symbol.
    """
    t = ticker.upper()
    p = realtime.get_price(t)
    if p:
        return jsonify(p)
    # Distinguish "provider throttled / budget exhausted" from
    # "ticker genuinely has no data". Previously both were 404 which
    # masked the FMP-budget outage behind "No price for <TICKER>".
    try:
        throttled = realtime.fmp_is_throttled()
    except Exception:
        throttled = False
    if throttled:
        return jsonify({
            "error": "data_provider_throttled",
            "message": f"Price providers unavailable for {t}; try again shortly.",
            "ticker": t,
        }), 503
    return jsonify({
        "error": "ticker_not_found",
        "message": f"No price for {t}",
        "ticker": t,
    }), 404


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
