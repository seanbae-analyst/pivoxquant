"""Risk analytics quant routes: VaR/CVaR, drawdown, stress-test, GKYZ
volatility, Component ES, defense-status, conditional drawdown, tail ratio,
sortino-by-position, Ledoit-Wolf shrinkage.

Split from routes/quant.py (Wave 11 SRP refactor).
All URL paths preserved exactly (`/api/risk/...`). No behaviour change.
"""

import json
import logging
import math
import time as _time

import numpy as np
from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.error_responses import api_error
from services.name_resolver import canonical_display_name, resolve_stock_name
from security import general_rate_limit
from .decorators import api_auth, legal_scrub_response
from .quant_helpers import (
    _bounded_set,
    _get_portfolio_returns,
    _identify_drawdown_periods,
    _load_positions_with_prices,
    _safe_kurtosis,
    _safe_skew,
    add_disclaimer,
)

logger = logging.getLogger(__name__)

risk_quant_bp = Blueprint("risk_quant", __name__, url_prefix="/api")

# ─────────────────────────────────────────────────────────────────────────────
# Caches
# ─────────────────────────────────────────────────────────────────────────────

_var_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_dd_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_VAR_CACHE_TTL = 300  # 5 minutes

_vol_cache: dict = {}  # {ticker: {"data": ..., "ts": ...}}
_VOL_CACHE_TTL = 300  # 5 minutes

_ces_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_CES_CACHE_TTL = 300  # 5 minutes

_defense_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_DEFENSE_CACHE_TTL = 60  # 1 minute

_cddar_cache: dict = {}
_tailratio_cache: dict = {}
_sortino_cache: dict = {}
_lws_cache: dict = {}
_RISK_X_CACHE_TTL = 300  # 5 minutes


# ─────────────────────────────────────────────────────────────────────────────
# Risk Analytics — VaR / CVaR
# ─────────────────────────────────────────────────────────────────────────────

@risk_quant_bp.route("/risk/var")
@api_auth
@legal_scrub_response
def portfolio_var():
    """Calculate VaR and CVaR for the user's portfolio.

    Supports both parametric (normal) and historical simulation.
    Query params:
        period: history lookback (default '1y')
        horizon: holding period in days (default 1)
    """
    # cache check (per-user)
    now = _time.time()
    uid = current_user.id
    user_cache = _var_cache.get(uid)
    if user_cache and now - user_cache.get("ts", 0) < _VAR_CACHE_TTL:
        return jsonify(user_cache["data"])

    period = request.args.get("period", "1y")
    try:
        horizon = max(1, min(int(request.args.get("horizon", "1")), 252))
    except (ValueError, TypeError):
        horizon = 1

    items, total_value = _load_positions_with_prices()
    if not items:
        return api_error(
            en="No positions in portfolio", kr="포트폴리오에 보유 종목이 없습니다.",
            code="RISK_NO_POSITIONS", status=400,
        )

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if len(daily_returns) < 20:
        return api_error(
            en="Insufficient history (need 20+ trading days)",
            kr="과거 데이터가 부족합니다 (최소 20거래일 필요).",
            code="RISK_INSUFFICIENT_HISTORY_20D", status=400,
        )

    ret_arr = np.array(daily_returns, dtype=np.float64)

    # ── Parametric VaR (assumes normal distribution) ──
    mu = float(np.mean(ret_arr))
    sigma = float(np.std(ret_arr, ddof=1))

    z_95 = 1.6449
    z_99 = 2.3263
    sqrt_h = math.sqrt(horizon)

    # VaR as positive loss amount
    var_95_param = total_value * (z_95 * sigma * sqrt_h - mu * horizon)
    var_99_param = total_value * (z_99 * sigma * sqrt_h - mu * horizon)

    # ── Historical VaR ──
    if horizon > 1:
        # rolling multi-day returns
        rolling = []
        for i in range(len(ret_arr) - horizon + 1):
            cum = float(np.prod(1 + ret_arr[i:i + horizon]) - 1)
            rolling.append(cum)
        hist_arr = np.array(rolling, dtype=np.float64)
    else:
        hist_arr = ret_arr

    var_95_hist = float(-np.percentile(hist_arr, 5)) * total_value
    var_99_hist = float(-np.percentile(hist_arr, 1)) * total_value

    # ── CVaR (Expected Shortfall) ──
    threshold_95 = np.percentile(hist_arr, 5)
    threshold_99 = np.percentile(hist_arr, 1)
    tail_95 = hist_arr[hist_arr <= threshold_95]
    tail_99 = hist_arr[hist_arr <= threshold_99]

    cvar_95 = float(-np.mean(tail_95)) * total_value if len(tail_95) > 0 else var_95_hist
    cvar_99 = float(-np.mean(tail_99)) * total_value if len(tail_99) > 0 else var_99_hist

    # ── Worst day ──
    worst_idx = int(np.argmin(ret_arr))
    worst_return = float(ret_arr[worst_idx])
    worst_date = dates[worst_idx] if worst_idx < len(dates) else "N/A"

    # ── Best day (for context) ──
    best_idx = int(np.argmax(ret_arr))
    best_return = float(ret_arr[best_idx])
    best_date = dates[best_idx] if best_idx < len(dates) else "N/A"

    # ── Distribution stats ──
    skewness = float(_safe_skew(ret_arr))
    kurt = float(_safe_kurtosis(ret_arr))

    annual_vol = sigma * math.sqrt(252)

    payload = {
        "portfolio_value": round(total_value, 2),
        "horizon_days": horizon,
        "observation_days": len(ret_arr),
        "parametric": {
            "var_95": round(max(var_95_param, 0), 2),
            "var_99": round(max(var_99_param, 0), 2),
            "var_95_pct": round(max(var_95_param, 0) / total_value * 100, 2) if total_value else 0,
            "var_99_pct": round(max(var_99_param, 0) / total_value * 100, 2) if total_value else 0,
        },
        "historical": {
            "var_95": round(max(var_95_hist, 0), 2),
            "var_99": round(max(var_99_hist, 0), 2),
            "var_95_pct": round(max(var_95_hist, 0) / total_value * 100, 2) if total_value else 0,
            "var_99_pct": round(max(var_99_hist, 0) / total_value * 100, 2) if total_value else 0,
        },
        "cvar_95": round(max(cvar_95, 0), 2),
        "cvar_99": round(max(cvar_99, 0), 2),
        "cvar_95_pct": round(max(cvar_95, 0) / total_value * 100, 2) if total_value else 0,
        "cvar_99_pct": round(max(cvar_99, 0) / total_value * 100, 2) if total_value else 0,
        "portfolio_daily_vol": round(sigma * 100, 4),
        "portfolio_annual_vol": round(annual_vol * 100, 2),
        "worst_day": {"date": worst_date, "return_pct": round(worst_return * 100, 2)},
        "best_day": {"date": best_date, "return_pct": round(best_return * 100, 2)},
        "distribution": {
            "mean_daily_return_pct": round(mu * 100, 4),
            "skewness": round(skewness, 4),
            "kurtosis": round(kurt, 4),
        },
        "methodology": "parametric (normal) + historical simulation",
    }

    add_disclaimer(payload, "analysis")
    _bounded_set(_var_cache, uid, {"data": payload, "ts": now})
    return jsonify(payload)


@risk_quant_bp.route("/risk/drawdown")
@api_auth
@legal_scrub_response
def portfolio_drawdown():
    """Advanced drawdown analytics: Calmar, Ulcer Index, drawdown periods.

    Query params:
        period: history lookback (default '1y')
    """
    now = _time.time()
    uid = current_user.id
    user_cache = _dd_cache.get(uid)
    if user_cache and now - user_cache.get("ts", 0) < _VAR_CACHE_TTL:
        return jsonify(user_cache["data"])

    period = request.args.get("period", "1y")

    items, total_value = _load_positions_with_prices()
    if not items:
        return api_error(
            en="No positions in portfolio", kr="포트폴리오에 보유 종목이 없습니다.",
            code="RISK_NO_POSITIONS", status=400,
        )

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if len(daily_returns) < 5:
        return api_error(
            en="Insufficient history (need 5+ trading days)",
            kr="과거 데이터가 부족합니다 (최소 5거래일 필요).",
            code="RISK_INSUFFICIENT_HISTORY_5D", status=400,
        )

    ret_arr = np.array(daily_returns, dtype=np.float64)

    # ── Build equity curve (start at total_value, walk forward) ──
    equity = [total_value]
    for r in ret_arr:
        equity.append(equity[-1] * (1 + r))
    equity_arr = np.array(equity, dtype=np.float64)
    # dates for equity: prepend a "start" date
    eq_dates = ["start"] + dates

    # ── Running max (peak) and drawdown series ──
    running_max = np.maximum.accumulate(equity_arr)
    drawdown_series = (equity_arr - running_max) / running_max  # negative values

    # ── Max Drawdown ──
    max_dd = float(np.min(drawdown_series))
    max_dd_idx = int(np.argmin(drawdown_series))

    # ── Underwater equity curve [{date, drawdown_pct}] ──
    underwater = []
    for i in range(1, len(drawdown_series)):
        underwater.append({
            "date": eq_dates[i],
            "drawdown_pct": round(float(drawdown_series[i]) * 100, 2),
        })

    # ── Identify drawdown periods ──
    dd_periods = _identify_drawdown_periods(drawdown_series, eq_dates)

    # top 5 by depth
    dd_periods_sorted = sorted(dd_periods, key=lambda x: x["depth_pct"])[:5]

    # ── Current drawdown ──
    current_dd = float(drawdown_series[-1])
    current_dd_start = None
    current_dd_days = 0
    if current_dd < -0.001:
        # walk back to find when this drawdown started
        for i in range(len(drawdown_series) - 1, -1, -1):
            if drawdown_series[i] >= -0.0001:
                current_dd_start = eq_dates[i] if i < len(eq_dates) else None
                current_dd_days = len(drawdown_series) - 1 - i
                break

    # ── CAGR ──
    n_days = len(ret_arr)
    total_return = equity_arr[-1] / equity_arr[0] - 1
    cagr = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0

    # ── Calmar Ratio = CAGR / |Max Drawdown| ──
    calmar = cagr / abs(max_dd) if abs(max_dd) > 0.0001 else 0

    # ── Ulcer Index = sqrt(mean(drawdown^2)) ──
    # Only use the underwater portion (negative drawdowns)
    dd_squared = drawdown_series ** 2
    ulcer_index = float(np.sqrt(np.mean(dd_squared)))

    # ── Ulcer Performance Index = (CAGR - risk_free) / Ulcer Index ──
    risk_free_annual = 0.045  # approximate current rate
    upi = (cagr - risk_free_annual) / ulcer_index if ulcer_index > 0.0001 else 0

    # ── Recovery analysis ──
    # longest recovery time across all drawdown periods
    longest_recovery = 0
    avg_recovery = 0
    recovered_periods = [p for p in dd_periods if p.get("recovery_days") is not None]
    if recovered_periods:
        longest_recovery = max(p["recovery_days"] for p in recovered_periods)
        avg_recovery = sum(p["recovery_days"] for p in recovered_periods) / len(recovered_periods)

    payload = {
        "portfolio_value": round(total_value, 2),
        "observation_days": n_days,
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "max_drawdown_date": eq_dates[max_dd_idx] if max_dd_idx < len(eq_dates) else None,
        "calmar_ratio": round(calmar, 3),
        "ulcer_index": round(ulcer_index * 100, 4),
        "ulcer_performance_index": round(upi, 3),
        "current_drawdown": {
            "pct": round(current_dd * 100, 2),
            "start_date": current_dd_start,
            "duration_days": current_dd_days,
            "is_in_drawdown": current_dd < -0.001,
        },
        "recovery": {
            "longest_days": longest_recovery,
            "average_days": round(avg_recovery, 1),
            "total_periods": len(dd_periods),
            "recovered_periods": len(recovered_periods),
        },
        "top_drawdowns": dd_periods_sorted,
        "underwater_curve": underwater,
        "methodology": "historical equity curve reconstruction",
    }

    add_disclaimer(payload, "analysis")
    _bounded_set(_dd_cache, uid, {"data": payload, "ts": now})
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Stress Test
# ─────────────────────────────────────────────────────────────────────────────

# Sector classification for sensitivity multipliers
_TECH_TICKERS = frozenset({
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSM", "AVGO",
    "ASML", "AMD", "INTC", "CRM", "ADBE", "ORCL", "NOW", "SHOP", "SQ",
    "PLTR", "NET", "SNOW", "DDOG", "MDB", "CRWD", "ZS", "PANW", "UBER",
    "ABNB", "COIN", "MSTR", "TSLA", "NFLX",
})
_DEFENSIVE_TICKERS = frozenset({
    "JNJ", "PG", "KO", "PEP", "MRK", "ABT", "UNH", "LLY", "ABBV",
    "WMT", "COST", "CL", "GIS", "K", "MCD", "SO", "DUK", "NEE",
    "ED", "AEP", "XEL", "VZ", "T",
})
_GOLD_TICKERS = frozenset({"GLD", "IAU", "GDX", "GOLD", "NEM", "AEM"})
_BOND_TICKERS = frozenset({"TLT", "IEF", "BND", "AGG", "SHY", "LQD", "HYG"})
_OIL_TICKERS = frozenset({"XLE", "USO", "OXY", "CVX", "XOM", "COP", "SLB"})

STRESS_SCENARIOS = {
    "2008_gfc": {
        "name": "2008 Global Financial Crisis",
        "period": "Sep 2008 - Mar 2009",
        "spx_return": -0.569,
        "factors": {
            "equity": -0.57, "bonds": 0.05, "gold": 0.25,
            "oil": -0.70, "vix_spike": 3.5,
        },
    },
    "2020_covid": {
        "name": "2020 COVID Crash",
        "period": "Feb 2020 - Mar 2020",
        "spx_return": -0.339,
        "factors": {
            "equity": -0.34, "bonds": 0.08, "gold": -0.03,
            "oil": -0.65, "vix_spike": 4.0,
        },
    },
    "2022_rate_shock": {
        "name": "2022 Rate Hike Shock",
        "period": "Jan 2022 - Oct 2022",
        "spx_return": -0.252,
        "factors": {
            "equity": -0.25, "bonds": -0.18, "gold": -0.10,
            "oil": 0.15, "vix_spike": 1.5,
        },
    },
    "flash_crash": {
        "name": "Flash Crash Scenario",
        "period": "Hypothetical",
        "spx_return": -0.10,
        "factors": {
            "equity": -0.10, "bonds": 0.03, "gold": 0.05,
            "oil": -0.08, "vix_spike": 5.0,
        },
    },
    "custom_vix_50": {
        "name": "VIX Spike to 50",
        "period": "Hypothetical",
        "spx_return": -0.15,
        "factors": {
            "equity": -0.15, "bonds": 0.02, "gold": 0.10,
            "oil": -0.20, "vix_spike": 2.5,
        },
    },
}


def _classify_position(ticker: str):
    """Return (asset_class, sensitivity_multiplier) for a ticker.

    asset_class: 'equity_tech' | 'equity_defensive' | 'equity' | 'gold' | 'bond' | 'oil'
    multiplier: applied to the equity factor (>1 = more sensitive, <1 = less)
    """
    t = ticker.upper().replace(".KS", "").replace(".KQ", "")
    if t in _GOLD_TICKERS:
        return "gold", 0.0
    if t in _BOND_TICKERS:
        return "bond", 0.0
    if t in _OIL_TICKERS:
        return "oil", 1.0
    if t in _TECH_TICKERS:
        return "equity_tech", 1.2
    if t in _DEFENSIVE_TICKERS:
        return "equity_defensive", 0.8
    # Korean stocks: slightly higher beta assumption (emerging-market premium)
    if ticker.upper().endswith(".KS") or ticker.upper().endswith(".KQ"):
        return "equity", 1.1
    return "equity", 1.0


def _estimate_position_loss(position, scenario_factors):
    """Estimate loss for a single position under a stress scenario.

    Returns (estimated_return, estimated_loss_usd).
    Uses factor-based model:
      - Gold/Bond/Oil tickers use their dedicated factor directly
      - Equity tickers use: equity_factor * sensitivity_multiplier
    """
    ticker = position["ticker"]
    mv = position["market_value"]
    asset_class, multiplier = _classify_position(ticker)

    if asset_class == "gold":
        est_return = scenario_factors.get("gold", 0.0)
    elif asset_class == "bond":
        est_return = scenario_factors.get("bonds", 0.0)
    elif asset_class == "oil":
        est_return = scenario_factors.get("oil", 0.0)
    else:
        # equity (tech / defensive / generic)
        est_return = scenario_factors.get("equity", 0.0) * multiplier

    est_loss_usd = mv * est_return
    return est_return, est_loss_usd


@risk_quant_bp.route("/risk/stress-test")
@api_auth
@legal_scrub_response
def portfolio_stress_test():
    """Run portfolio through historical crisis scenarios.

    Returns estimated impact for each scenario including per-position breakdown,
    survivors, worst-hit ticker, and hedge considerations.
    """
    items, total_value = _load_positions_with_prices()
    if not items:
        return api_error(
            en="No positions in portfolio", kr="포트폴리오에 보유 종목이 없습니다.",
            code="RISK_NO_POSITIONS", status=400,
        )

    scenarios_out = []
    worst_scenario_id = None
    worst_scenario_loss = 0.0

    for sid, scenario in STRESS_SCENARIOS.items():
        factors = scenario["factors"]
        positions_out = []
        portfolio_loss_usd = 0.0
        survivors = []
        worst_hit_ticker = None
        worst_hit_pct = 0.0

        for pos in items:
            est_return, est_loss_usd = _estimate_position_loss(pos, factors)
            portfolio_loss_usd += est_loss_usd

            pct = round(est_return * 100, 2)
            loss_usd = round(est_loss_usd, 2)

            positions_out.append({
                "ticker": pos["ticker"],
                "name": pos.get("name") or pos["ticker"],
                "current_value": round(pos["market_value"], 2),
                "estimated_loss_pct": pct,
                # Currency-neutral key: value is KRW-normalized (market_value
                # from _load_positions_with_prices is KRW for ALL positions),
                # so the old `_usd` suffix lied to KR users.
                "estimated_loss": loss_usd,
            })

            if est_return >= 0:
                survivors.append(pos["ticker"])
            if est_return < worst_hit_pct:
                worst_hit_pct = est_return
                worst_hit_ticker = pos["ticker"]

        portfolio_impact_pct = (portfolio_loss_usd / total_value * 100) if total_value else 0.0

        # track worst scenario across all
        if portfolio_loss_usd < worst_scenario_loss:
            worst_scenario_loss = portfolio_loss_usd
            worst_scenario_id = sid

        scenarios_out.append({
            "id": sid,
            "name": scenario["name"],
            "period": scenario["period"],
            "spx_return_pct": round(scenario["spx_return"] * 100, 1),
            "portfolio_impact_pct": round(portfolio_impact_pct, 2),
            # Currency-neutral: value is KRW-normalized (see note above).
            "portfolio_impact": round(portfolio_loss_usd, 2),
            "positions": positions_out,
            "survivors": survivors,
            "worst_hit": worst_hit_ticker,
        })

    # ── Hedge considerations based on portfolio composition ──
    hedges = []
    has_gold = any(_classify_position(p["ticker"])[0] == "gold" for p in items)
    has_bonds = any(_classify_position(p["ticker"])[0] == "bond" for p in items)
    tech_weight = sum(
        p["market_value"] for p in items
        if _classify_position(p["ticker"])[0] == "equity_tech"
    ) / total_value if total_value else 0

    if not has_gold:
        hedges.append("Consider adding gold (GLD) for crisis protection")
    if not has_bonds:
        hedges.append("Consider adding bonds (TLT/IEF) for rate-shock hedging")
    if tech_weight > 0.5:
        hedges.append(
            f"Tech concentration is {round(tech_weight * 100, 1)}% — "
            "consider diversifying into defensive sectors (XLU, XLP)"
        )
    if not hedges:
        hedges.append("Portfolio has reasonable diversification across asset classes")

    payload = {
        "scenarios": scenarios_out,
        "portfolio_value": round(total_value, 2),
        "most_vulnerable_scenario": worst_scenario_id,
        "hedge_considerations": hedges,
    }
    add_disclaimer(payload, "simulation")
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# GKYZ Volatility
# ─────────────────────────────────────────────────────────────────────────────

@risk_quant_bp.route("/risk/volatility/<ticker>")
@api_auth
@legal_scrub_response
def risk_volatility(ticker):
    """GKYZ volatility estimate for a single ticker.

    Uses Garman-Klass-Yang-Zhang estimator on OHLC data for 7-8x efficiency
    over standard close-to-close volatility.

    Query params:
        window: lookback window in trading days (default 20, max 120)
    """
    import re

    ticker = ticker.upper().strip()
    if not re.match(r"^[A-Z0-9]{1,10}(\.[A-Z]{1,2})?$", ticker):
        return api_error(
            en="Invalid ticker format", kr="유효하지 않은 종목 형식입니다.",
            code="RISK_INVALID_TICKER", status=400,
        )

    try:
        window = max(5, min(int(request.args.get("window", "20")), 120))
    except (ValueError, TypeError):
        window = 20

    now = _time.time()
    cache_key = f"{ticker}:{window}"
    cached = _vol_cache.get(cache_key)
    if cached and now - cached["ts"] < _VOL_CACHE_TTL:
        return jsonify(cached["data"])

    from services.container import fetcher

    hist = fetcher.get_price_history(ticker, period="6mo")
    if hist is None or hist.empty or len(hist) < window + 1:
        return api_error(
            en=f"Insufficient OHLC data for {ticker} (need {window + 1}+ bars)",
            kr=f"{ticker} OHLC 데이터가 부족합니다 (최소 {window + 1}개 봉 필요).",
            code="RISK_INSUFFICIENT_OHLC", status=400,
        )

    from services.quant.risk_metrics import GKYZVolatility

    opens = hist["Open"].tolist()
    highs = hist["High"].tolist()
    lows = hist["Low"].tolist()
    closes = hist["Close"].tolist()

    result = GKYZVolatility.estimate(opens, highs, lows, closes, window=window)

    if result["vol_gkyz"] is None:
        return api_error(
            en="Could not compute volatility", kr="변동성 계산에 실패했습니다.",
            code="RISK_VOLATILITY_COMPUTATION_FAILED", status=500,
        )

    payload = {"ticker": ticker, "name": resolve_stock_name(ticker) or ticker, **result}
    add_disclaimer(payload, "indicator")
    _vol_cache[cache_key] = {"data": payload, "ts": now}
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Component Expected Shortfall
# ─────────────────────────────────────────────────────────────────────────────

@risk_quant_bp.route("/risk/component-es")
@api_auth
@legal_scrub_response
def risk_component_es():
    """Decompose portfolio tail risk into per-position contributions.

    Uses Component Expected Shortfall (Euler principle) on historical returns.

    Query params:
        period: lookback period (default '1y')
        alpha: tail probability (default 0.05 = 95% ES)
    """
    now = _time.time()
    uid = current_user.id
    user_cache = _ces_cache.get(uid)
    if user_cache and now - user_cache.get("ts", 0) < _CES_CACHE_TTL:
        return jsonify(user_cache["data"])

    period = request.args.get("period", "1y")
    try:
        alpha = max(0.01, min(float(request.args.get("alpha", "0.05")), 0.20))
    except (ValueError, TypeError):
        alpha = 0.05

    items, total_value = _load_positions_with_prices()
    if not items or len(items) < 2:
        return api_error(
            en="Need at least 2 positions for ES decomposition",
            kr="ES 분해를 위해 최소 2개 포지션이 필요합니다.",
            code="RISK_ES_NEED_TWO_POSITIONS", status=400,
        )

    # Fetch per-asset daily returns aligned by date
    from services.container import fetcher

    ticker_returns: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    # Wave H-4 P0 (2026-05-18): parallel fetch (same fix as quant_helpers)
    import concurrent.futures as _cf
    _tks = [it["ticker"] for it in items]
    def _f(t):
        try: return t, fetcher.get_price_history(t, period=period)
        except Exception: return t, None
    with _cf.ThreadPoolExecutor(max_workers=min(8, max(1, len(_tks)))) as _ex:
        for t, hist in _ex.map(_f, _tks):
            if hist is None or hist.empty or len(hist) < 2:
                continue
            pct = hist["Close"].pct_change().dropna()
            date_ret = {}
            for dt, ret in pct.items():
                ds = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
                if math.isfinite(ret):
                    date_ret[ds] = float(ret)
                    all_dates.add(ds)
            ticker_returns[t] = date_ret

    if len(ticker_returns) < 2:
        return api_error(
            en="Insufficient history for ES decomposition",
            kr="ES 분해를 위한 과거 데이터가 부족합니다.",
            code="RISK_ES_INSUFFICIENT_HISTORY", status=400,
        )

    # Align: only dates present for ALL tickers with data
    common_dates = sorted(
        set.intersection(*(set(dr.keys()) for dr in ticker_returns.values()))
    )

    if len(common_dates) < 30:
        return api_error(
            en="Insufficient overlapping trading days (need 30+)",
            kr="공통 거래일이 부족합니다 (최소 30일 필요).",
            code="RISK_ES_INSUFFICIENT_OVERLAP_30D", status=400,
        )

    # Build returns matrix (n_dates x n_assets) and weights vector
    tickers_used = [it["ticker"] for it in items if it["ticker"] in ticker_returns]
    n_assets = len(tickers_used)
    n_obs = len(common_dates)

    returns_matrix = np.zeros((n_obs, n_assets), dtype=np.float64)
    for j, ticker_sym in enumerate(tickers_used):
        for i, d in enumerate(common_dates):
            returns_matrix[i, j] = ticker_returns[ticker_sym].get(d, 0.0)

    # Weights from current market value
    used_items = [it for it in items if it["ticker"] in ticker_returns]
    total_used_value = sum(it["market_value"] for it in used_items)
    weights = np.array(
        [it["market_value"] / total_used_value for it in used_items],
        dtype=np.float64,
    )

    from services.quant.risk_metrics import ComponentES

    result = ComponentES.decompose(returns_matrix, weights, alpha=alpha)

    if result["portfolio_es"] is None:
        return api_error(
            en="Could not compute Expected Shortfall",
            kr="Expected Shortfall 계산에 실패했습니다.",
            code="RISK_ES_COMPUTATION_FAILED", status=500,
        )

    # Enrich with ticker labels + resolved company name (name primary in UI)
    positions_out = []
    for j, ticker_sym in enumerate(tickers_used):
        positions_out.append({
            "ticker": ticker_sym,
            "name": resolve_stock_name(ticker_sym) or ticker_sym,
            "weight_pct": round(float(weights[j]) * 100, 2),
            "component_es_pct": result["component_es"][j],
            "risk_contribution_pct": result["pct_contribution"][j],
        })

    # Sort by risk contribution descending
    positions_out.sort(key=lambda x: abs(x["risk_contribution_pct"]), reverse=True)

    payload = {
        "portfolio_value": round(total_value, 2),
        "portfolio_es_pct": result["portfolio_es"],
        "portfolio_var_pct": result["portfolio_var"],
        "alpha": alpha,
        "confidence_level_pct": round((1 - alpha) * 100, 1),
        "observation_days": n_obs,
        "n_tail_scenarios": result["n_tail_scenarios"],
        "positions": positions_out,
        "tickers_used": tickers_used,
        "methodology": "Historical Component ES (Euler decomposition)",
    }

    add_disclaimer(payload, "analysis")
    _bounded_set(_ces_cache, uid, {"data": payload, "ts": now})
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Risk Defense Status (7-layer)
# ─────────────────────────────────────────────────────────────────────────────

@risk_quant_bp.route("/risk/defense-status")
@api_auth
@legal_scrub_response
def risk_defense_status():
    """Run the 7-layer Risk Defense System on the user's current portfolio.

    Returns defense_score, status (GREEN/YELLOW/RED), triggered layers,
    warnings, and risk exposure data.
    """
    from models import Position, SignalCache
    from services.quant.risk_defense import RiskDefenseSystem
    from services.data.fetcher import DataFetcher

    uid = current_user.id
    now = _time.time()

    # Cache check
    user_cache = _defense_cache.get(uid)
    if user_cache and user_cache.get("data") and now - user_cache.get("ts", 0) < _DEFENSE_CACHE_TTL:
        return jsonify(user_cache["data"])

    positions = Position.query.filter_by(user_id=uid).all()
    if not positions:
        return api_error(
            en="No positions in portfolio", kr="포트폴리오에 보유 종목이 없습니다.",
            code="RISK_NO_POSITIONS", status=400,
        )

    fetcher = DataFetcher()

    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    # Build position list with weights, values, sectors
    # Currency normalization (CRITICAL): KR positions (.KS/.KQ) are already in
    # KRW; US positions are in USD and must be FX-converted before aggregation,
    # otherwise mixed US+KR portfolios get wrong defense-layer weights.
    from services import fx_service
    fx_rate = fx_service.get_rate()  # USD → KRW, computed once
    pos_list = []
    total_value = 0
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        price = sd.get("price", p.avg_cost)
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        mv_native = price * p.shares
        mv = mv_native if is_kr else mv_native * fx_rate
        sector = sd.get("sector", "Unknown")
        total_value += mv
        pos_list.append({
            "ticker": p.ticker,
            "name": canonical_display_name(sd.get("name"), p.ticker),
            "value": mv,
            "sector": sector,
            "weight": 0,  # filled below
        })

    if total_value <= 0:
        return api_error(
            en="Portfolio value is zero", kr="포트폴리오 평가액이 0입니다.",
            code="RISK_PORTFOLIO_VALUE_ZERO", status=400,
        )

    # Assign weights
    for pos in pos_list:
        pos["weight"] = pos["value"] / total_value

    # Build returns matrix from price history (20-day lookback)
    # Wave H-4 P0 (2026-05-18): parallel fetch
    returns_cols = []
    valid_tickers = []
    import concurrent.futures as _cf
    _tks2 = [pos["ticker"] for pos in pos_list]
    def _f2(t):
        try: return t, fetcher.get_price_history(t, period="3mo")
        except Exception:
            logger.debug("silent-fallback: risk_defense_status", exc_info=True)
            return t, None
    with _cf.ThreadPoolExecutor(max_workers=min(8, max(1, len(_tks2)))) as _ex:
        for t, hist in _ex.map(_f2, _tks2):
            if hist is not None and not hist.empty and len(hist) >= 21:
                closes = hist["Close"].values[-21:]
                daily_rets = np.diff(closes) / closes[:-1]
                returns_cols.append(daily_rets)
                valid_tickers.append(t)

    returns_matrix = None
    if len(returns_cols) >= 2:
        min_len = min(len(c) for c in returns_cols)
        returns_matrix = np.column_stack([c[-min_len:] for c in returns_cols])

    # Estimate daily return from portfolio-level last 2 days
    daily_return = 0.0
    if returns_matrix is not None and returns_matrix.shape[0] >= 1:
        weights = np.array([pos["weight"] for pos in pos_list
                            if pos["ticker"] in valid_tickers])
        if len(weights) == returns_matrix.shape[1]:
            daily_return = float(returns_matrix[-1] @ weights) * 100

    # Get VIX if available
    # NOTE: VIXStrategy.analyze() returns the level under the "vix" key
    # (services/quant/models.py), NOT "current_vix". Using the wrong key
    # left vix=None permanently, so Layer 3 (VIX) never fired.
    vix = None
    try:
        from services.quant.models import VIXStrategy
        vix_data = VIXStrategy.analyze()
        if vix_data and "vix" in vix_data:
            vix = vix_data["vix"]
    except Exception:
        logger.debug("silent-fallback: risk_defense_status", exc_info=True)
        pass

    # Get current market regime.
    # NOTE: there is no VolatilityRegime.detect() — only
    # RegimeSwitching.analyze(closes) / VolatilityRegime.analyze(closes).
    # The old code called a non-existent .detect(), so every call raised
    # AttributeError and regime stayed pinned to "TRANSITION".
    # We derive the bull/bear regime from a representative market index
    # (KOSPI for KR-weighted portfolios, S&P 500 ETF otherwise) so Layer 7
    # cash management receives a real regime. On any data failure we keep
    # the graceful "TRANSITION" fallback.
    regime = "TRANSITION"
    try:
        from services.quant.models import RegimeSwitching
        # Choose index by where the portfolio is concentrated.
        kr_weight = sum(
            pos["weight"] for pos in pos_list
            if pos["ticker"].upper().endswith((".KS", ".KQ"))
        )
        index_ticker = "069500.KS" if kr_weight >= 0.5 else "SPY"
        idx_hist = fetcher.get_price_history(index_ticker, period="6mo")
        if idx_hist is not None and not idx_hist.empty and len(idx_hist) >= 80:
            idx_closes = idx_hist["Close"].values
            regime_data = RegimeSwitching.analyze(idx_closes)
            if regime_data and regime_data.get("regime"):
                regime = regime_data["regime"]
    except Exception:
        logger.debug("silent-fallback: risk_defense_status", exc_info=True)
        pass

    # Run defense system
    rds = RiskDefenseSystem()
    result = rds.check_all({
        "positions": pos_list,
        "portfolio_value": total_value,
        "daily_return": daily_return,
        "vix": vix,
        "regime": regime,
        "returns_matrix": returns_matrix,
    })

    payload = {
        "ok": True,
        "defense_score": result["defense_score"],
        "status": result.get("status", "GREEN"),
        "layers_triggered": result["layers_triggered"],
        "warnings": result["warnings"],
        "risk_exposure": [
            {
                "ticker": t,
                "name": resolve_stock_name(t) or t,
                "risk_contribution_pct": r,
                "reason": reason,
            }
            for t, r, reason in result["risk_exposure"]
        ],
        "regime_risk_level": result["regime_risk_level"],
        "halt_trading": result["halt_trading"],
        "portfolio_value": round(total_value, 2),
        "position_count": len(pos_list),
        "vix": vix,
        "regime": regime,
    }
    add_disclaimer(payload, "analysis")

    _defense_cache[uid] = {"data": payload, "ts": now}
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Additional Risk Analytics — CDDaR / TailRatio / SortinoByPosition / LedoitWolf
# ─────────────────────────────────────────────────────────────────────────────

@risk_quant_bp.route("/risk/conditional-drawdown", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def risk_conditional_drawdown():
    """Conditional Drawdown at Risk (CDDaR) for the user's portfolio.

    Body (JSON, optional):
        period: lookback (default '1y')
        alpha:  tail probability (default 0.05)
    """
    now = _time.time()
    uid = current_user.id

    body = request.get_json(silent=True) or {}
    period = body.get("period") or request.args.get("period", "1y")
    try:
        alpha = max(0.01, min(float(body.get("alpha", request.args.get("alpha", 0.05))), 0.20))
    except (ValueError, TypeError):
        alpha = 0.05

    cache_key = f"{period}:{alpha}"
    user_cache = _cddar_cache.get(uid)
    if (user_cache and user_cache.get("key") == cache_key
            and now - user_cache.get("ts", 0) < _RISK_X_CACHE_TTL):
        return jsonify(user_cache["data"])

    items, total_value = _load_positions_with_prices()
    if not items:
        return api_error(
            en="No positions to analyze", kr="분석할 보유 종목이 없습니다.",
            code="RISK_NO_POSITIONS", status=400,
        )

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if not daily_returns or len(daily_returns) < 20:
        return api_error(
            en="Insufficient history (need 20+ trading days)",
            kr="과거 데이터가 부족합니다 (최소 20거래일 필요).",
            code="RISK_INSUFFICIENT_HISTORY_20D", status=400,
        )

    # Reconstruct portfolio equity curve from daily returns
    pv = [1.0]
    for r in daily_returns:
        pv.append(pv[-1] * (1.0 + r))

    from services.quant.risk_metrics import ConditionalDrawdown
    result = ConditionalDrawdown.calculate(pv, alpha=alpha)

    if result.get("cddar") is None:
        return api_error(
            en="Could not compute CDDaR", kr="조건부 손실폭(CDDaR) 계산에 실패했습니다.",
            code="RISK_CDDAR_COMPUTATION_FAILED", status=500,
        )

    payload = {
        "cddar_pct": result["cddar"],
        "max_dd_pct": result["max_dd"],
        "alpha": result["alpha"],
        "confidence_level_pct": round((1 - result["alpha"]) * 100, 1),
        "observation_days": len(daily_returns),
        "portfolio_value": round(total_value, 2),
        "period": period,
        "methodology": "Conditional Drawdown at Risk (historical)",
    }
    add_disclaimer(payload, "analysis")
    _cddar_cache[uid] = {"data": payload, "ts": now, "key": cache_key}
    return jsonify(payload)


@risk_quant_bp.route("/risk/tail-ratio", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def risk_tail_ratio():
    """Tail Ratio — |95th pct| / |5th pct| of portfolio daily returns.

    Body (JSON, optional):
        period: lookback (default '1y')
    """
    now = _time.time()
    uid = current_user.id

    body = request.get_json(silent=True) or {}
    period = body.get("period") or request.args.get("period", "1y")

    cache_key = f"{period}"
    user_cache = _tailratio_cache.get(uid)
    if (user_cache and user_cache.get("key") == cache_key
            and now - user_cache.get("ts", 0) < _RISK_X_CACHE_TTL):
        return jsonify(user_cache["data"])

    items, total_value = _load_positions_with_prices()
    if not items:
        return api_error(
            en="No positions to analyze", kr="분석할 보유 종목이 없습니다.",
            code="RISK_NO_POSITIONS", status=400,
        )

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if not daily_returns or len(daily_returns) < 20:
        return api_error(
            en="Insufficient history (need 20+ trading days)",
            kr="과거 데이터가 부족합니다 (최소 20거래일 필요).",
            code="RISK_INSUFFICIENT_HISTORY_20D", status=400,
        )

    from services.quant.risk_metrics import TailRatio
    result = TailRatio.calculate(daily_returns)

    if result.get("tail_ratio") is None:
        return api_error(
            en="Could not compute Tail Ratio", kr="Tail Ratio 계산에 실패했습니다.",
            code="RISK_TAIL_RATIO_COMPUTATION_FAILED", status=500,
        )

    payload = {
        "tail_ratio": result["tail_ratio"],
        "p95_pct": result["p95"],
        "p5_pct": result["p5"],
        "interpretation": result["interpretation"],
        "observation_days": len(daily_returns),
        "portfolio_value": round(total_value, 2),
        "period": period,
        "methodology": "|95th| / |5th| percentile ratio",
    }
    add_disclaimer(payload, "analysis")
    _tailratio_cache[uid] = {"data": payload, "ts": now, "key": cache_key}
    return jsonify(payload)


@risk_quant_bp.route("/risk/sortino-by-position", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def risk_sortino_by_position():
    """Per-position Sortino ratio (downside-only risk-adjusted return).

    Body (JSON, optional):
        period: lookback (default '1y')
        risk_free: annual risk-free rate (default 0.045)
    """
    now = _time.time()
    uid = current_user.id

    body = request.get_json(silent=True) or {}
    period = body.get("period") or request.args.get("period", "1y")
    try:
        rf = float(body.get("risk_free", request.args.get("risk_free", 0.045)))
        rf = max(0.0, min(rf, 0.20))
    except (ValueError, TypeError):
        rf = 0.045

    cache_key = f"{period}:{rf}"
    user_cache = _sortino_cache.get(uid)
    if (user_cache and user_cache.get("key") == cache_key
            and now - user_cache.get("ts", 0) < _RISK_X_CACHE_TTL):
        return jsonify(user_cache["data"])

    items, total_value = _load_positions_with_prices()
    if not items:
        return api_error(
            en="No positions to analyze", kr="분석할 보유 종목이 없습니다.",
            code="RISK_NO_POSITIONS", status=400,
        )

    from services.container import fetcher
    from services.quant.risk_metrics import SortinoByPosition

    # Parallel price-history fetch (mirrors Wave H-4 pattern at risk_component_es
    # / defense_status). Eliminates N+1 serial latency (~8s) for the per-position
    # processing below, which still runs serially over the prefetched map.
    import concurrent.futures as _cf
    _tks = [it["ticker"] for it in items]
    def _fetch_hist(t):
        try:
            return t, fetcher.get_price_history(t, period=period)
        except Exception:
            logger.debug("silent-fallback: sortino_by_position", exc_info=True)
            return t, None
    _hist_map = {}
    with _cf.ThreadPoolExecutor(max_workers=min(8, max(1, len(_tks)))) as _ex:
        for t, hist in _ex.map(_fetch_hist, _tks):
            _hist_map[t] = hist

    positions_out = []
    for it in items:
        hist = _hist_map.get(it["ticker"])
        if hist is None or hist.empty or len(hist) < 21:
            positions_out.append({
                "ticker": it["ticker"],
                "name": it.get("name") or it["ticker"],
                "sortino": None,
                "error": "insufficient history",
            })
            continue
        # Drop non-finite returns (Inf/NaN). 0-filled prices from missing FMP
        # columns (services/data/fmp.py) produce Inf via pct_change against a
        # zero base; an Inf in this raw list propagates through np.mean() into
        # SortinoByPosition's `annualized_return`, yielding `Infinity` in the
        # JSON body — invalid JSON that crashes the browser's JSON.parse and
        # blanks the Risk Sortino tab. The dict-building risk paths (663/1178)
        # and LedoitWolf/ComponentES already filter; this raw .tolist() path
        # was the lone gap. 2026-05-20 bug-hunter (P1).
        rets = [
            r for r in hist["Close"].astype(float).pct_change().dropna().tolist()
            if math.isfinite(r)
        ]
        if len(rets) < 20:
            positions_out.append({
                "ticker": it["ticker"],
                "name": it.get("name") or it["ticker"],
                "sortino": None,
                "error": "insufficient history",
            })
            continue
        result = SortinoByPosition.calculate(rets, risk_free_annual=rf)
        positions_out.append({
            "ticker": it["ticker"],
            "name": it.get("name") or it["ticker"],
            "sortino": result.get("sortino"),
            "downside_dev_pct": result.get("downside_dev"),
            "annualized_return_pct": result.get("annualized_return"),
            "weight_pct": round(it["market_value"] / total_value * 100, 2) if total_value > 0 else 0,
        })

    # Sort by sortino desc (None last)
    positions_out.sort(
        key=lambda x: (x.get("sortino") is None, -(x.get("sortino") or 0)),
    )

    payload = {
        "positions": positions_out,
        "position_count": len(positions_out),
        "risk_free_rate": rf,
        "portfolio_value": round(total_value, 2),
        "period": period,
        "methodology": "Sortino ratio — downside deviation only (MAR = risk-free)",
    }
    add_disclaimer(payload, "analysis")
    _sortino_cache[uid] = {"data": payload, "ts": now, "key": cache_key}
    return jsonify(payload)


@risk_quant_bp.route("/risk/ledoit-wolf-shrinkage", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def risk_ledoit_wolf_shrinkage():
    """Ledoit-Wolf shrinkage covariance estimator for the user's portfolio.

    Produces a well-conditioned covariance matrix with analytically optimal
    shrinkage intensity. Useful diagnostic before running portfolio
    simulations (HRP/MDP/MinVar).

    Body (JSON, optional):
        period: lookback (default '1y')
    """
    now = _time.time()
    uid = current_user.id

    body = request.get_json(silent=True) or {}
    period = body.get("period") or request.args.get("period", "1y")

    cache_key = f"{period}"
    user_cache = _lws_cache.get(uid)
    if (user_cache and user_cache.get("key") == cache_key
            and now - user_cache.get("ts", 0) < _RISK_X_CACHE_TTL):
        return jsonify(user_cache["data"])

    items, total_value = _load_positions_with_prices()
    if not items or len(items) < 2:
        return api_error(
            en="Need at least 2 positions for covariance",
            kr="공분산 추정을 위해 최소 2개 포지션이 필요합니다.",
            code="RISK_COV_NEED_TWO_POSITIONS", status=400,
        )

    # Build aligned returns matrix (only dates where ALL tickers have data)
    from services.container import fetcher

    # Parallel price-history fetch (mirrors Wave H-4 pattern). Per-item finite
    # filtering and insufficient-history handling below are preserved.
    import concurrent.futures as _cf
    _tks = [it["ticker"] for it in items]
    def _fetch_hist(t):
        try:
            return t, fetcher.get_price_history(t, period=period)
        except Exception:
            logger.debug("silent-fallback: ledoit_wolf_shrinkage", exc_info=True)
            return t, None
    _hist_map = {}
    with _cf.ThreadPoolExecutor(max_workers=min(8, max(1, len(_tks)))) as _ex:
        for t, hist in _ex.map(_fetch_hist, _tks):
            _hist_map[t] = hist

    ticker_returns: dict[str, dict[str, float]] = {}
    for it in items:
        hist = _hist_map.get(it["ticker"])
        if hist is None or hist.empty or len(hist) < 2:
            continue
        pct = hist["Close"].astype(float).pct_change().dropna()
        dr = {}
        for dt, ret in pct.items():
            ds = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            if math.isfinite(ret):
                dr[ds] = float(ret)
        if dr:
            ticker_returns[it["ticker"]] = dr

    if len(ticker_returns) < 2:
        return api_error(
            en="Insufficient history for covariance",
            kr="공분산 추정을 위한 과거 데이터가 부족합니다.",
            code="RISK_COV_INSUFFICIENT_HISTORY", status=400,
        )

    common_dates = sorted(
        set.intersection(*(set(dr.keys()) for dr in ticker_returns.values()))
    )
    if len(common_dates) < 20:
        return api_error(
            en="Insufficient overlapping trading days (need 20+)",
            kr="공통 거래일이 부족합니다 (최소 20일 필요).",
            code="RISK_COV_INSUFFICIENT_OVERLAP_20D", status=400,
        )

    tickers_used = list(ticker_returns.keys())
    n_obs = len(common_dates)
    n_assets = len(tickers_used)

    returns_matrix = np.zeros((n_obs, n_assets), dtype=np.float64)
    for j, tk in enumerate(tickers_used):
        for i, d in enumerate(common_dates):
            returns_matrix[i, j] = ticker_returns[tk].get(d, 0.0)

    from services.quant.risk_metrics import LedoitWolfShrinkage

    result = LedoitWolfShrinkage.estimate(returns_matrix)
    if result.get("shrunk_cov") is None:
        return api_error(
            en="Could not estimate shrinkage covariance",
            kr="축소(shrinkage) 공분산 추정에 실패했습니다.",
            code="RISK_LEDOIT_WOLF_COMPUTATION_FAILED", status=500,
        )

    # Convert matrices to serialisable lists (annualised for readability)
    shrunk = (np.asarray(result["shrunk_cov"]) * 252).round(6).tolist()
    sample = (np.asarray(result["sample_cov"]) * 252).round(6).tolist()

    payload = {
        "tickers": tickers_used,
        "shrinkage_intensity": result["shrinkage_intensity"],
        "target_variance_annualized": round(result["target_variance"] * 252, 6),
        "shrunk_covariance_annualized": shrunk,
        "sample_covariance_annualized": sample,
        "n_observations": result["n_observations"],
        "n_assets": result["n_assets"],
        "portfolio_value": round(total_value, 2),
        "period": period,
        "methodology": "Ledoit-Wolf (2004) shrinkage toward scaled identity",
    }
    add_disclaimer(payload, "analysis")
    _lws_cache[uid] = {"data": payload, "ts": now, "key": cache_key}
    return jsonify(payload)
