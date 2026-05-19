"""Quant tool routes: position-sizing calculator (Kelly Criterion),
extended indicators (10 technical + 8 fundamental), correlation matrix,
sector heatmap.

Split from routes/quant.py (Wave 11 SRP refactor).
All URL paths preserved exactly (`/api/tools/...`, `/api/indicators/...`).
No behaviour change.
"""

# legal-exempt: disclaimer language only — section101-check detector FP

import logging
import math
import time as _time

import numpy as np
from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.error_responses import api_error
from services.name_resolver import resolve_stock_name
from security import general_rate_limit
from .decorators import api_auth, legal_scrub_response
from .quant_helpers import (
    _load_positions_with_prices,
    add_disclaimer,
)

logger = logging.getLogger(__name__)

tools_quant_bp = Blueprint("tools_quant", __name__, url_prefix="/api")

# ─────────────────────────────────────────────────────────────────────────────
# Caches
# ─────────────────────────────────────────────────────────────────────────────

_indicators_cache: dict = {}  # {ticker: {"data": ..., "ts": ...}}
_INDICATORS_CACHE_TTL = 300   # 5 minutes

_corr_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_CORR_CACHE_TTL = 300  # 5 minutes

_sector_hm_cache: dict = {}  # global cache (not per-user)
_SECTOR_HM_TTL = 300  # 5 minutes

# GICS sector ETFs — standard proxies
_SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


# ─────────────────────────────────────────────────────────────────────────────
# Position Sizing Calculator (Kelly Criterion)
# ─────────────────────────────────────────────────────────────────────────────

@tools_quant_bp.route("/tools/position-sizing", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def position_sizing_calculator():
    """Kelly Criterion-based position sizing calculator.

    Legal: YELLOW -- labeled as 'calculator', not 'advisor' or 'coach'.

    Takes JSON body:
        ticker: str           -- ticker symbol
        win_probability: float -- historical win probability (0-1)
        avg_win: float        -- average win return (decimal, e.g. 0.08 = 8%)
        avg_loss: float       -- average loss return (decimal, e.g. 0.04 = 4%)
    """
    data = request.get_json(silent=True)
    if not data:
        return api_error(
            en="Request body required (JSON)",
            kr="요청 본문(JSON)이 필요합니다.",
            code="TOOL_QUANT_INVALID_PARAMS",
            status=400,
        )

    ticker = (data.get("ticker") or "").upper().strip()
    if not ticker or len(ticker) > 20:
        return api_error(
            en="Invalid or missing ticker",
            kr="유효하지 않거나 누락된 종목 코드입니다.",
            code="TOOL_QUANT_INVALID_PARAMS",
            status=400,
        )

    # ── Input validation ──
    try:
        win_prob = float(data.get("win_probability", 0))
        avg_win = float(data.get("avg_win", 0))
        avg_loss = float(data.get("avg_loss", 0))
    except (TypeError, ValueError):
        return api_error(
            en="win_probability, avg_win, avg_loss must be numbers",
            kr="win_probability, avg_win, avg_loss 값은 숫자여야 합니다.",
            code="TOOL_QUANT_INVALID_PARAMS",
            status=400,
        )

    if not (0 < win_prob < 1):
        return api_error(
            en="win_probability must be between 0 and 1 (exclusive)",
            kr="win_probability 값은 0과 1 사이여야 합니다 (양 끝값 제외).",
            code="TOOL_QUANT_INVALID_PARAMS",
            status=400,
        )
    if avg_win <= 0:
        return api_error(
            en="avg_win must be positive",
            kr="avg_win 값은 양수여야 합니다.",
            code="TOOL_QUANT_INVALID_PARAMS",
            status=400,
        )
    if avg_loss <= 0:
        return api_error(
            en="avg_loss must be positive",
            kr="avg_loss 값은 양수여야 합니다.",
            code="TOOL_QUANT_INVALID_PARAMS",
            status=400,
        )

    # ── Kelly Criterion ──
    # Full Kelly: f* = (p * b - q) / b
    # where p = win probability, q = 1 - p, b = avg_win / avg_loss (odds ratio)
    q = 1 - win_prob
    b = avg_win / avg_loss  # win/loss ratio (odds)

    kelly_full = (win_prob * b - q) / b
    kelly_full = max(kelly_full, 0.0)  # never negative (means don't bet)

    # Half-Kelly (commonly used for safety margin)
    kelly_half = kelly_full / 2.0

    # Quarter-Kelly (conservative)
    kelly_quarter = kelly_full / 4.0

    # ── Compare to current allocation (if user holds this ticker) ──
    current_allocation_pct = None
    try:
        items, total_value = _load_positions_with_prices()
        if items and total_value > 0:
            for pos in items:
                if pos["ticker"].upper() == ticker:
                    current_allocation_pct = round(
                        pos["market_value"] / total_value * 100, 2
                    )
                    break
    except Exception:
        pass  # non-critical -- skip if portfolio unavailable

    # ── Build sizing tiers ──
    sizing_tiers = {
        "full_kelly": round(kelly_full * 100, 2),
        "half_kelly": round(kelly_half * 100, 2),
        "quarter_kelly": round(kelly_quarter * 100, 2),
    }

    # ── Expected value per trade (for context) ──
    ev_per_trade = win_prob * avg_win - q * avg_loss

    # ── Risk of ruin estimate (simplified geometric) ──
    if kelly_full > 0 and b > 0:
        risk_of_ruin = min(
            round((q / win_prob) ** 20, 6), 1.0
        ) if win_prob > q else 0.0
    else:
        risk_of_ruin = 1.0

    payload = {
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "inputs": {
            "win_probability": win_prob,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": round(b, 3),
        },
        "kelly_criterion": sizing_tiers,
        "expected_value_per_trade_pct": round(ev_per_trade * 100, 2),
        "risk_of_ruin_approx": risk_of_ruin,
        "current_allocation_pct": current_allocation_pct,
        "methodology": "Kelly Criterion with half/quarter variants",
    }
    add_disclaimer(payload, "simulation")
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Extended Indicators (10 technical + 8 fundamental)
# ─────────────────────────────────────────────────────────────────────────────

@tools_quant_bp.route("/indicators/<ticker>")
@api_auth
@legal_scrub_response
def extended_indicators(ticker):
    """Return all 10 additional technical indicators + 8 fundamental factors.

    Pure mathematical calculations; no investment advice.
    Query params:
        period: lookback for technical indicators (default '6mo')
    """
    from services.data.fetcher import DataFetcher
    from services.quant.indicators import AdditionalIndicators, AdditionalFundamentals
    from services.data import fmp as fmp_svc

    ticker = ticker.strip().upper()
    period = request.args.get("period", "6mo")

    # Cache check (per-ticker, not per-user -- data is the same for everyone)
    now = _time.time()
    cache_key = f"{ticker}:{period}"
    cached = _indicators_cache.get(cache_key)
    if cached and now - cached.get("ts", 0) < _INDICATORS_CACHE_TTL:
        return jsonify(cached["data"])

    fetcher = DataFetcher()
    hist = fetcher.get_price_history(ticker, period=period)
    if hist is None or hist.empty or len(hist) < 20:
        return api_error(
            en="Insufficient price data for indicators",
            kr="지표 계산에 필요한 가격 데이터가 부족합니다.",
            code="TOOL_QUANT_COMPUTATION_FAILED",
            status=400,
        )

    opens = hist["Open"].values.astype(float).tolist()
    highs = hist["High"].values.astype(float).tolist()
    lows = hist["Low"].values.astype(float).tolist()
    closes = hist["Close"].values.astype(float).tolist()
    volumes = hist["Volume"].values.astype(float).tolist()

    current_price = closes[-1] if closes else None

    # ── 10 Technical indicators ──────────────────────────────────────────────

    ind = AdditionalIndicators
    technical = {
        "donchian": ind.donchian_channel(highs, lows, closes),
        "supertrend": ind.supertrend(highs, lows, closes),
        "parabolic_sar": ind.parabolic_sar(highs, lows, closes),
        "cmf": ind.cmf(highs, lows, closes, volumes),
        "adl": ind.adl(highs, lows, closes, volumes),
        "pivot_points": ind.pivot_points(highs[-1], lows[-1], closes[-1]),
        "atr_bands": ind.atr_bands(closes, highs, lows),
        "vwap": ind.vwap_daily(highs, lows, closes, volumes),
        "heikin_ashi": ind.heikin_ashi(opens, highs, lows, closes),
        "keltner_width": ind.keltner_width(highs, lows, closes),
    }

    # ── 8 Fundamental factors ────────────────────────────────────────────────

    fundamental = AdditionalFundamentals.calculate_all(ticker, current_price)

    # ── Float shares from FMP profile ────────────────────────────────────────
    float_shares = None
    try:
        profile = fmp_svc.get_profile(ticker)
        if profile:
            float_shares = profile.get("floatShares") or profile.get("sharesFloat")
    except Exception:
        logger.debug("silent-fallback: extended_indicators", exc_info=True)
        pass

    payload = {
        "ok": True,
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "period": period,
        "data_points": len(closes),
        "current_price": round(current_price, 2) if current_price else None,
        "technical": technical,
        "fundamental": fundamental,
        "float_shares": int(float_shares) if float_shares else None,
    }
    add_disclaimer(payload, "indicator")

    _indicators_cache[cache_key] = {"data": payload, "ts": now}
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Correlation Matrix
# ─────────────────────────────────────────────────────────────────────────────

@tools_quant_bp.route("/tools/correlation-matrix")
@api_auth
@legal_scrub_response
def correlation_matrix():
    """Correlation matrix for user's portfolio positions.

    Returns pairwise Pearson correlations as a matrix + heatmap-ready data.
    Uses 6-month daily returns. Requires at least 2 positions.
    """
    now = _time.time()
    uid = current_user.id
    user_cache = _corr_cache.get(uid)
    if user_cache and now - user_cache.get("ts", 0) < _CORR_CACHE_TTL:
        return jsonify(user_cache["data"])

    from services.container import fetcher

    items, total_value = _load_positions_with_prices()
    if not items or len(items) < 2:
        return api_error(
            en="Need at least 2 positions for correlation matrix",
            kr="상관관계 행렬 계산에는 최소 2개의 보유 종목이 필요합니다.",
            code="TOOL_QUANT_INVALID_PARAMS",
            status=400,
        )

    tickers = [it["ticker"] for it in items]

    # Fetch 6-month daily returns for each ticker
    ticker_returns: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    for ticker in tickers:
        try:
            hist = fetcher.get_price_history(ticker, period="6mo")
            if hist is None or hist.empty or len(hist) < 30:
                continue
            closes = hist["Close"]
            pct = closes.pct_change().dropna()
            date_ret = {}
            for dt, ret in pct.items():
                ds = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
                if math.isfinite(ret):
                    date_ret[ds] = float(ret)
                    all_dates.add(ds)
            ticker_returns[ticker] = date_ret
        except Exception:
            logger.debug("silent-fallback: correlation_matrix", exc_info=True)
            continue

    included = [t for t in tickers if t in ticker_returns]
    if len(included) < 2:
        return api_error(
            en="Insufficient data for correlation (need 2+ tickers with history)",
            kr="상관관계 계산에 필요한 데이터가 부족합니다 (과거 데이터가 있는 2개 이상 종목 필요).",
            code="TOOL_QUANT_COMPUTATION_FAILED",
            status=400,
        )

    # Align on common dates
    common_dates = sorted(all_dates)
    # Only keep dates where all tickers have data
    for t in included:
        common_dates = [d for d in common_dates if d in ticker_returns[t]]

    if len(common_dates) < 20:
        return api_error(
            en="Insufficient overlapping trading days (need 20+)",
            kr="공통 거래일 수가 부족합니다 (20일 이상 필요).",
            code="TOOL_QUANT_COMPUTATION_FAILED",
            status=400,
        )

    # Build returns matrix
    returns_matrix = np.array([
        [ticker_returns[t][d] for d in common_dates]
        for t in included
    ], dtype=np.float64)

    # Compute correlation matrix
    corr = np.corrcoef(returns_matrix)

    # Build heatmap-ready list of dicts
    heatmap = []
    for i, t1 in enumerate(included):
        for j, t2 in enumerate(included):
            heatmap.append({
                "x": t1,
                "y": t2,
                "value": round(float(corr[i, j]), 3),
            })

    # Correlation matrix as dict-of-dicts
    matrix = {}
    for i, t1 in enumerate(included):
        matrix[t1] = {}
        for j, t2 in enumerate(included):
            matrix[t1][t2] = round(float(corr[i, j]), 3)

    # Average correlation (off-diagonal)
    n = len(included)
    off_diag = []
    for i in range(n):
        for j in range(i + 1, n):
            off_diag.append(float(corr[i, j]))
    avg_corr = float(np.mean(off_diag)) if off_diag else 0

    payload = {
        "tickers": included,
        "matrix": matrix,
        "heatmap": heatmap,
        "avg_correlation": round(avg_corr, 3),
        "observation_days": len(common_dates),
        "diversification_note": (
            "High average correlation (>0.7) indicates low diversification benefit."
            if avg_corr > 0.7 else
            "Moderate correlation levels — portfolio has some diversification benefit."
            if avg_corr > 0.4 else
            "Low average correlation — good diversification across positions."
        ),
    }

    add_disclaimer(payload, "analysis")
    _corr_cache[uid] = {"data": payload, "ts": now}
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Sector Heatmap
# ─────────────────────────────────────────────────────────────────────────────

@tools_quant_bp.route("/tools/sector-heatmap")
@api_auth
@legal_scrub_response
def sector_heatmap():
    """Sector performance heatmap — current day, week, and month returns.

    Uses GICS sector ETFs (XLK, XLV, XLF, etc.) as sector proxies.
    Returns performance data formatted for heatmap visualisation.
    """
    now = _time.time()
    cached = _sector_hm_cache.get("data")
    if cached and now - _sector_hm_cache.get("ts", 0) < _SECTOR_HM_TTL:
        return jsonify(cached)

    from services.container import fetcher

    sectors = []

    for sector_name, etf in _SECTOR_ETFS.items():
        try:
            hist = fetcher.get_price_history(etf, period="3mo")
            if hist is None or hist.empty or len(hist) < 5:
                continue

            closes = hist["Close"].values.astype(float)
            current = float(closes[-1])

            # Day return
            day_ret = ((closes[-1] / closes[-2]) - 1) * 100 if len(closes) >= 2 else 0

            # Week return (5 trading days)
            week_ret = ((closes[-1] / closes[-5]) - 1) * 100 if len(closes) >= 5 else 0

            # Month return (21 trading days)
            month_ret = ((closes[-1] / closes[-21]) - 1) * 100 if len(closes) >= 21 else 0

            sectors.append({
                "sector": sector_name,
                "etf": etf,
                "price": round(current, 2),
                "day_return": round(float(day_ret), 2),
                "week_return": round(float(week_ret), 2),
                "month_return": round(float(month_ret), 2),
            })
        except Exception:
            logger.debug("silent-fallback: sector_heatmap", exc_info=True)
            continue

    if not sectors:
        return api_error(
            en="Sector data unavailable",
            kr="섹터 데이터를 가져올 수 없습니다.",
            code="TOOL_QUANT_COMPUTATION_FAILED",
            status=500,
        )

    # Sort by day return (strongest first)
    sectors.sort(key=lambda x: x["day_return"], reverse=True)

    # Market breadth: % of sectors positive today
    positive_count = sum(1 for s in sectors if s["day_return"] > 0)
    breadth = round(positive_count / len(sectors) * 100, 0) if sectors else 0

    payload = {
        "sectors": sectors,
        "count": len(sectors),
        "market_breadth_pct": breadth,
        "strongest_today": sectors[0]["sector"] if sectors else None,
        "weakest_today": sectors[-1]["sector"] if sectors else None,
    }

    add_disclaimer(payload, "indicator")
    _sector_hm_cache["data"] = payload
    _sector_hm_cache["ts"] = now
    return jsonify(payload)
