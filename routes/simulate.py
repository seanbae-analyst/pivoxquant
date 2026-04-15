"""Portfolio simulation routes: HRP, Tail Risk Parity, Max Diversification.

READ-ONLY simulation endpoints. No apply/rebalance/trade functionality.
Every response includes a legal disclaimer.
"""
import json
import math
import time as _time

import numpy as np
from flask import Blueprint, jsonify, request
from flask_login import current_user

from .decorators import api_auth

simulate_bp = Blueprint("simulate", __name__, url_prefix="/api/portfolio/simulate")

# Per-user cache: {user_id: {"data": ..., "ts": ..., "key": ...}}
_hrp_cache: dict = {}
_trp_cache: dict = {}
_mdp_cache: dict = {}
_CACHE_TTL = 300  # 5 minutes

DISCLAIMER = (
    "Portfolio simulation for educational reference only. "
    "Does not constitute investment advice or portfolio allocation recommendation."
)


# ── Shared helpers ──────────────────────────────────────────────────────────

def _load_user_positions():
    """Load current user's positions with latest cached prices.

    Returns list of dicts [{ticker, shares, avg_cost, price, market_value}]
    and total portfolio value.
    """
    from models import Position, SignalCache

    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return [], 0.0

    items = []
    total = 0.0
    for p in positions:
        cached = SignalCache.query.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        price = sd.get("price", p.avg_cost)
        mv = price * p.shares
        items.append({
            "ticker": p.ticker,
            "shares": p.shares,
            "avg_cost": p.avg_cost,
            "price": price,
            "market_value": mv,
        })
        total += mv

    return items, total


def _build_returns_matrix(items, period="1y"):
    """Fetch historical returns for each position and build aligned matrix.

    Returns:
        returns_matrix: np.ndarray (n_dates, n_assets) of daily returns
        tickers: list of ticker strings (matching column order)
        dates: list of date strings
    """
    from services.container import fetcher

    if not items:
        return None, [], []

    # Fetch per-ticker returns keyed by date
    ticker_date_returns: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    for it in items:
        hist = fetcher.get_price_history(it["ticker"], period=period)
        if hist is None or hist.empty or len(hist) < 5:
            continue

        closes = hist["Close"]
        pct = closes.pct_change().dropna()
        dr = {}
        for dt, ret in pct.items():
            ds = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            if math.isfinite(ret):
                dr[ds] = float(ret)
                all_dates.add(ds)
        if dr:
            ticker_date_returns[it["ticker"]] = dr

    if not ticker_date_returns or not all_dates:
        return None, [], []

    tickers = list(ticker_date_returns.keys())
    sorted_dates = sorted(all_dates)

    # Build aligned matrix — only dates where ALL tickers have data
    rows = []
    valid_dates = []
    for ds in sorted_dates:
        row = []
        complete = True
        for t in tickers:
            if ds in ticker_date_returns[t]:
                row.append(ticker_date_returns[t][ds])
            else:
                complete = False
                break
        if complete:
            rows.append(row)
            valid_dates.append(ds)

    if len(rows) < 5:
        return None, tickers, valid_dates

    return np.array(rows, dtype=np.float64), tickers, valid_dates


def _cache_check(cache: dict, uid: int, key: str):
    """Check per-user cache. Returns cached data or None."""
    now = _time.time()
    entry = cache.get(uid)
    if entry and entry.get("key") == key and now - entry.get("ts", 0) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(cache: dict, uid: int, key: str, data: dict):
    cache[uid] = {"data": data, "ts": _time.time(), "key": key}


# ── HRP Endpoint ──────────────────────────────────────────────────────────

@simulate_bp.route("/hrp")
@api_auth
def simulate_hrp():
    """Run Hierarchical Risk Parity on user's portfolio positions.

    Query params:
        period: lookback (default '1y')
    """
    uid = current_user.id
    period = request.args.get("period", "1y")
    cache_key = f"hrp:{period}"

    cached = _cache_check(_hrp_cache, uid, cache_key)
    if cached:
        return jsonify(cached)

    items, total_value = _load_user_positions()
    if not items or len(items) < 2:
        return jsonify({
            "error": "Need at least 2 positions for portfolio simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    returns_matrix, tickers, dates = _build_returns_matrix(items, period=period)
    if returns_matrix is None or len(tickers) < 2:
        return jsonify({
            "error": "Insufficient price history for simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    from portfolio_models import HRP

    try:
        result = HRP.allocate(returns_matrix, tickers=tickers)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).error(f"HRP simulation failed: {e}")
        return jsonify({
            "error": "HRP simulation failed. Please try again.",
            "disclaimer": DISCLAIMER,
        }), 500

    # Add current vs suggested comparison
    current_weights = {}
    for it in items:
        if it["ticker"] in tickers:
            current_weights[it["ticker"]] = round(it["market_value"] / total_value, 6) if total_value > 0 else 0

    payload = {
        "simulation": result,
        "current_weights": current_weights,
        "portfolio_value": round(total_value, 2),
        "period": period,
        "observation_days": len(dates),
        "assets_analyzed": len(tickers),
        "disclaimer": DISCLAIMER,
    }

    _cache_set(_hrp_cache, uid, cache_key, payload)
    return jsonify(payload)


# ── TRP Endpoint ──────────────────────────────────────────────────────────

@simulate_bp.route("/trp")
@api_auth
def simulate_trp():
    """Run Tail Risk Parity on user's portfolio positions.

    Query params:
        period: lookback (default '1y')
        alpha: tail probability (default 0.05)
    """
    uid = current_user.id
    period = request.args.get("period", "1y")
    try:
        alpha = float(request.args.get("alpha", "0.05"))
        alpha = max(0.01, min(0.20, alpha))  # clamp
    except (ValueError, TypeError):
        alpha = 0.05

    cache_key = f"trp:{period}:{alpha}"

    cached = _cache_check(_trp_cache, uid, cache_key)
    if cached:
        return jsonify(cached)

    items, total_value = _load_user_positions()
    if not items or len(items) < 2:
        return jsonify({
            "error": "Need at least 2 positions for portfolio simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    returns_matrix, tickers, dates = _build_returns_matrix(items, period=period)
    if returns_matrix is None or len(tickers) < 2:
        return jsonify({
            "error": "Insufficient price history for simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    from portfolio_models import TailRiskParity

    try:
        result = TailRiskParity.allocate(returns_matrix, tickers=tickers, alpha=alpha)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).error(f"TRP simulation failed: {e}")
        return jsonify({
            "error": "TRP simulation failed. Please try again.",
            "disclaimer": DISCLAIMER,
        }), 500

    current_weights = {}
    for it in items:
        if it["ticker"] in tickers:
            current_weights[it["ticker"]] = round(it["market_value"] / total_value, 6) if total_value > 0 else 0

    payload = {
        "simulation": result,
        "current_weights": current_weights,
        "portfolio_value": round(total_value, 2),
        "period": period,
        "observation_days": len(dates),
        "assets_analyzed": len(tickers),
        "disclaimer": DISCLAIMER,
    }

    _cache_set(_trp_cache, uid, cache_key, payload)
    return jsonify(payload)


# ── MDP Endpoint ──────────────────────────────────────────────────────────

@simulate_bp.route("/mdp")
@api_auth
def simulate_mdp():
    """Run Maximum Diversification Portfolio on user's portfolio positions.

    Query params:
        period: lookback (default '1y')
    """
    uid = current_user.id
    period = request.args.get("period", "1y")
    cache_key = f"mdp:{period}"

    cached = _cache_check(_mdp_cache, uid, cache_key)
    if cached:
        return jsonify(cached)

    items, total_value = _load_user_positions()
    if not items or len(items) < 2:
        return jsonify({
            "error": "Need at least 2 positions for portfolio simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    returns_matrix, tickers, dates = _build_returns_matrix(items, period=period)
    if returns_matrix is None or len(tickers) < 2:
        return jsonify({
            "error": "Insufficient price history for simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    from portfolio_models import MaxDiversification

    try:
        result = MaxDiversification.allocate(returns_matrix, tickers=tickers)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).error(f"MDP simulation failed: {e}")
        return jsonify({
            "error": "MDP simulation failed. Please try again.",
            "disclaimer": DISCLAIMER,
        }), 500

    current_weights = {}
    for it in items:
        if it["ticker"] in tickers:
            current_weights[it["ticker"]] = round(it["market_value"] / total_value, 6) if total_value > 0 else 0

    payload = {
        "simulation": result,
        "current_weights": current_weights,
        "portfolio_value": round(total_value, 2),
        "period": period,
        "observation_days": len(dates),
        "assets_analyzed": len(tickers),
        "disclaimer": DISCLAIMER,
    }

    _cache_set(_mdp_cache, uid, cache_key, payload)
    return jsonify(payload)


# ── ERC Endpoint ─────────────────────────────────────────────────────────

_erc_cache: dict = {}


@simulate_bp.route("/erc")
@api_auth
def simulate_erc():
    """Run Equal Risk Contribution on user's portfolio positions.

    Query params:
        period: lookback (default '1y')
    """
    uid = current_user.id
    period = request.args.get("period", "1y")
    cache_key = f"erc:{period}"

    cached = _cache_check(_erc_cache, uid, cache_key)
    if cached:
        return jsonify(cached)

    items, total_value = _load_user_positions()
    if not items or len(items) < 2:
        return jsonify({
            "error": "Need at least 2 positions for portfolio simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    returns_matrix, tickers, dates = _build_returns_matrix(items, period=period)
    if returns_matrix is None or len(tickers) < 2:
        return jsonify({
            "error": "Insufficient price history for simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    from portfolio_models import EqualRiskContribution

    try:
        result = EqualRiskContribution.allocate(returns_matrix, tickers=tickers)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).error(f"ERC simulation failed: {e}")
        return jsonify({
            "error": "ERC simulation failed. Please try again.",
            "disclaimer": DISCLAIMER,
        }), 500

    current_weights = {}
    for it in items:
        if it["ticker"] in tickers:
            current_weights[it["ticker"]] = round(it["market_value"] / total_value, 6) if total_value > 0 else 0

    payload = {
        "simulation": result,
        "current_weights": current_weights,
        "portfolio_value": round(total_value, 2),
        "period": period,
        "observation_days": len(dates),
        "assets_analyzed": len(tickers),
        "disclaimer": DISCLAIMER,
    }

    _cache_set(_erc_cache, uid, cache_key, payload)
    return jsonify(payload)


# ── MinVariance Endpoint ─────────────────────────────────────────────────

_minvar_cache: dict = {}


@simulate_bp.route("/min-variance")
@api_auth
def simulate_min_variance():
    """Run Minimum Variance Portfolio on user's portfolio positions.

    Query params:
        period: lookback (default '1y')
    """
    uid = current_user.id
    period = request.args.get("period", "1y")
    cache_key = f"minvar:{period}"

    cached = _cache_check(_minvar_cache, uid, cache_key)
    if cached:
        return jsonify(cached)

    items, total_value = _load_user_positions()
    if not items or len(items) < 2:
        return jsonify({
            "error": "Need at least 2 positions for portfolio simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    returns_matrix, tickers, dates = _build_returns_matrix(items, period=period)
    if returns_matrix is None or len(tickers) < 2:
        return jsonify({
            "error": "Insufficient price history for simulation",
            "disclaimer": DISCLAIMER,
        }), 400

    from portfolio_models import MinVariance

    try:
        result = MinVariance.allocate(returns_matrix, tickers=tickers)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).error(f"MinVariance simulation failed: {e}")
        return jsonify({
            "error": "MinVariance simulation failed. Please try again.",
            "disclaimer": DISCLAIMER,
        }), 500

    current_weights = {}
    for it in items:
        if it["ticker"] in tickers:
            current_weights[it["ticker"]] = round(it["market_value"] / total_value, 6) if total_value > 0 else 0

    payload = {
        "simulation": result,
        "current_weights": current_weights,
        "portfolio_value": round(total_value, 2),
        "period": period,
        "observation_days": len(dates),
        "assets_analyzed": len(tickers),
        "disclaimer": DISCLAIMER,
    }

    _cache_set(_minvar_cache, uid, cache_key, payload)
    return jsonify(payload)
