"""Quant strategy routes: VIX strategy, cross-asset momentum, stat-arb, risk analytics."""
import json
import logging
import math
import time as _time

import numpy as np
from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.name_resolver import resolve_stock_name, canonical_display_name
from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit

logger = logging.getLogger(__name__)

quant_bp = Blueprint("quant", __name__, url_prefix="/api")

# ── Legal Disclaimers (YELLOW endpoints) ─────────────────────────────────────

DISCLAIMERS = {
    "simulation": (
        "Portfolio simulation for educational reference only. "
        "Does not constitute investment advice or portfolio allocation guidance."
    ),
    "indicator": (
        "Market analysis indicator for informational purposes only. "
        "Does not suggest any specific trading action."
    ),
    "analysis": (
        "Analysis based on historical data and mathematical models. "
        "Past performance does not guarantee future results."
    ),
    "tax": (
        "Tax information is estimated and for reference only. "
        "Consult a licensed tax professional for actual tax advice."
    ),
    "regime": (
        "Macro regime classification and historical sector performance data "
        "for informational purposes. Does not suggest specific sectors."
    ),
}


def add_disclaimer(response_dict, disclaimer_type="analysis"):
    """Inject a legal disclaimer into the response payload."""
    response_dict["disclaimer"] = DISCLAIMERS.get(disclaimer_type, DISCLAIMERS["analysis"])
    return response_dict

# MEM-001: bounded cache helper. Pre-fix the largest user-keyed caches were
# unbounded — they could grow without limit on a single long-running worker.
# 1000-entry cap with oldest-eviction is enough for our user count and keeps
# memory steady. TODO: convert remaining unbounded caches in this file.
def _bounded_set(cache: dict, key, value, max_size: int = 1000):
    if len(cache) >= max_size and key not in cache:
        try:
            oldest = min(cache, key=lambda k: cache[k].get("ts", 0))
            cache.pop(oldest, None)
        except Exception:
            # If eviction fails for any reason, fall through and just set —
            # better a slightly oversized cache than a broken response.
            pass
    cache[key] = value


_ca_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_sa_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}


@quant_bp.route("/vix-strategy")
@api_auth
@legal_scrub_response
def vix_strategy():
    from services.quant.models import VIXStrategy
    result = VIXStrategy.analyze()
    if result:
        return jsonify(result)
    return jsonify({"error": "VIX data unavailable"}), 500


@quant_bp.route("/cross-asset")
@api_auth
@legal_scrub_response
def cross_asset():
    now = _time.time()
    uid = current_user.id
    user_cache = _ca_cache.get(uid)
    if user_cache and user_cache.get("data") and now - user_cache.get("ts", 0) < 300:
        return jsonify(user_cache["data"])
    from services.quant.models import CrossAssetMomentum
    result = CrossAssetMomentum.analyze()
    if result:
        _bounded_set(_ca_cache, uid, {"data": result, "ts": now})
        return jsonify(result)
    return jsonify({"error": "Insufficient data"}), 500


@quant_bp.route("/stat-arb")
@api_auth
@legal_scrub_response
def stat_arb_analysis():
    """Run StatArb pair analysis on all default pairs."""
    now = _time.time()
    uid = current_user.id
    user_cache = _sa_cache.get(uid)
    if user_cache and user_cache.get("data") and now - user_cache.get("ts", 0) < 300:
        return jsonify(user_cache["data"])

    from services.quant.models import StatArb
    from services.data.fetcher import DataFetcher

    fetcher = DataFetcher()
    results = []

    for ticker_a, ticker_b in StatArb.PAIRS:
        try:
            hist_a = fetcher.get_price_history(ticker_a, period="6mo")
            hist_b = fetcher.get_price_history(ticker_b, period="6mo")

            if hist_a is None or hist_b is None or hist_a.empty or hist_b.empty:
                continue

            closes_a = hist_a["Close"].tolist()
            closes_b = hist_b["Close"].tolist()

            analysis = StatArb.analyze_pair(closes_a, closes_b, name_a=ticker_a, name_b=ticker_b)
            if analysis:
                results.append(analysis)
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).error(f"StatArb analysis failed for {ticker_a}/{ticker_b}: {e}")
            results.append({"pair": f"{ticker_a}/{ticker_b}", "error": "Analysis failed"})

    payload = {"pairs": results, "count": len(results)}
    add_disclaimer(payload, "simulation")
    _bounded_set(_sa_cache, uid, {"data": payload, "ts": now})
    return jsonify(payload)


# ── Regime-Conditional Performance Report ──────────────────────────────────────

_regime_cache: dict = {}  # {user_id: {"data": ..., "ts": ..., "key": ...}}
_REGIME_CACHE_TTL = 300  # 5 minutes


@quant_bp.route("/analytics/regime-report")
@api_auth
@legal_scrub_response
def regime_report():
    """Break down backtest performance by market regime.

    Query params:
        ticker: optional single stock (if omitted, runs on user's top 5 holdings)
        period: lookback period (default '1y')
    """
    from services.quant.backtester import Backtester
    from models import Position, SignalCache

    ticker = request.args.get("ticker")
    period = request.args.get("period", "1y")
    uid = current_user.id

    # Cache check (per-user, per-query)
    now = _time.time()
    cache_key = f"{ticker or 'portfolio'}:{period}"
    user_cache = _regime_cache.get(uid)
    if (user_cache and user_cache.get("key") == cache_key
            and now - user_cache.get("ts", 0) < _REGIME_CACHE_TTL):
        return jsonify(user_cache["data"])

    # Determine which tickers to test
    if ticker:
        tickers_to_test = [ticker.strip().upper()]
    else:
        # Get user's top 5 positions by market value
        positions = Position.query.filter_by(user_id=uid).all()
        if not positions:
            return jsonify({"error": "No positions in portfolio"}), 400

        # Batch-load SignalCache for all user positions in a single query (avoid N+1).
        pos_tickers = [p.ticker for p in positions]
        cache_map = {
            c.ticker: c
            for c in SignalCache.query.filter(SignalCache.ticker.in_(pos_tickers)).all()
        } if pos_tickers else {}

        pos_with_value = []
        for p in positions:
            cached = cache_map.get(p.ticker)
            sd = json.loads(cached.data_json) if cached and cached.data_json else {}
            price = sd.get("price", p.avg_cost)
            mv = price * p.shares
            pos_with_value.append({
                "ticker": p.ticker,
                "name": canonical_display_name(sd.get("name"), p.ticker),
                "market_value": mv,
            })

        pos_with_value.sort(key=lambda x: x["market_value"], reverse=True)
        tickers_to_test = [p["ticker"] for p in pos_with_value[:5]]

    if not tickers_to_test:
        return jsonify({"error": "No tickers to test"}), 400

    # Run backtests and aggregate regime stats
    per_ticker = {}
    # Aggregate: {regime: {wins, losses, pnl_values[]}}
    agg_regimes: dict = {}
    # Collect per-trade returns grouped by regime for Sharpe calculation
    regime_trade_returns: dict = {}

    for t in tickers_to_test:
        result = Backtester.run(t, period=period, initial_capital=10000)
        if result is None:
            per_ticker[t] = {"error": "Backtest failed or insufficient data"}
            continue

        # Per-ticker summary
        per_ticker[t] = {
            "total_return_net": result.get("total_return", 0),
            "alpha": result.get("alpha", 0),
            "trades": result.get("total_trades", 0),
            "current_regime": result.get("current_regime", {}).get("profile", "unknown"),
            "regime_stats": result.get("regime_stats", {}),
        }

        # Aggregate regime stats across tickers
        for regime_name, rstats in result.get("regime_stats", {}).items():
            if regime_name not in agg_regimes:
                agg_regimes[regime_name] = {
                    "trades": 0, "wins": 0, "losses": 0,
                    "total_pnl": 0.0,
                }
            agg_regimes[regime_name]["trades"] += rstats.get("trades", 0)
            agg_regimes[regime_name]["wins"] += rstats.get("wins", 0)
            agg_regimes[regime_name]["losses"] += rstats.get("losses", 0)
            agg_regimes[regime_name]["total_pnl"] += (
                rstats.get("avg_pnl", 0) * rstats.get("trades", 0)
            )

        # Extract per-trade pnl_pct grouped by regime from trade history
        for trade in result.get("trades", []):
            if trade.get("action") != "SELL":
                continue
            prof = trade.get("profile", "unknown")
            pnl_pct = trade.get("pnl_pct", 0)
            if prof not in regime_trade_returns:
                regime_trade_returns[prof] = []
            regime_trade_returns[prof].append(pnl_pct)

    # Build regime_performance with Sharpe and max drawdown proxy
    regime_performance = {}
    for regime_name, agg in agg_regimes.items():
        total = agg["trades"]
        win_rate = round(agg["wins"] / total * 100, 1) if total > 0 else 0.0
        avg_pnl = round(agg["total_pnl"] / total, 1) if total > 0 else 0.0

        # Trade-level Sharpe (not annualized — trade frequency varies by regime)
        returns = regime_trade_returns.get(regime_name, [])
        if len(returns) >= 2:
            ret_arr = np.array(returns, dtype=np.float64) / 100.0  # convert pct to decimal
            if np.std(ret_arr, ddof=1) > 0:
                sharpe = round(float(np.mean(ret_arr) / np.std(ret_arr, ddof=1)), 3)
            else:
                sharpe = 0.0
            max_dd = float(np.min(ret_arr) * 100)  # worst single trade as drawdown proxy
        elif len(returns) == 1:
            sharpe = 0.0
            max_dd = float(returns[0])
        else:
            sharpe = 0.0
            max_dd = 0.0

        regime_performance[regime_name] = {
            "trades": total,
            "wins": agg["wins"],
            "losses": agg["losses"],
            "win_rate": win_rate,
            "avg_pnl_pct": avg_pnl,
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(max_dd, 1),
        }

    # Determine best/worst regime by Sharpe (need at least 1 trade)
    scored_regimes = [
        (name, data) for name, data in regime_performance.items()
        if data["trades"] > 0
    ]
    if scored_regimes:
        best = max(scored_regimes, key=lambda x: x[1]["sharpe"])
        worst = min(scored_regimes, key=lambda x: x[1]["sharpe"])
        best_regime = best[0]
        worst_regime = worst[0]
        regime_summary = (
            f"Strategy performs best in {best[0].replace('_', ' ')} markets "
            f"(Sharpe {best[1]['sharpe']}) and struggles in "
            f"{worst[0].replace('_', ' ')} conditions "
            f"(Sharpe {worst[1]['sharpe']})."
        )
    else:
        best_regime = None
        worst_regime = None
        regime_summary = "Insufficient trade data to determine regime performance."

    # Chart data
    chart_regime_sharpe = [
        {"regime": name.replace("_", " ").title(), "sharpe": data["sharpe"]}
        for name, data in regime_performance.items()
    ]
    chart_regime_win_rate = [
        {"regime": name.replace("_", " ").title(), "win_rate": data["win_rate"]}
        for name, data in regime_performance.items()
    ]

    payload = {
        "tickers_tested": tickers_to_test,
        "period": period,
        "regime_performance": regime_performance,
        "best_regime": best_regime,
        "worst_regime": worst_regime,
        "regime_summary": regime_summary,
        "per_ticker": per_ticker,
        "chart_data": {
            "regime_sharpe": chart_regime_sharpe,
            "regime_win_rate": chart_regime_win_rate,
        },
    }

    add_disclaimer(payload, "analysis")
    _bounded_set(_regime_cache, uid, {"data": payload, "ts": now, "key": cache_key})
    return jsonify(payload)


# ── Risk Analytics ──────────────────────────────────────────────────────────────

_var_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_dd_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}

_VAR_CACHE_TTL = 300  # 5 minutes


def _load_positions_with_prices():
    """Load current user positions with latest prices.

    Returns list of dicts: [{ticker, shares, avg_cost, price, market_value, market_value_krw, is_kr, fx_rate}]
    and total portfolio value (KRW-normalized).

    Currency normalization (CRITICAL for cross-market risk analytics):
      - Korean tickers (.KS/.KQ): price is in KRW → market_value_krw = price * shares
      - US tickers: price is in USD → market_value_krw = price * shares * USD/KRW
      - All weight/contribution calculations downstream use market_value (KRW),
        ensuring US positions are not under-weighted vs KRW-denominated positions.
    """
    from models import Position, SignalCache
    from services import fx_service

    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return [], 0.0

    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    fx_rate = fx_service.get_rate()  # USD → KRW
    items = []
    total_value = 0.0
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        price = sd.get("price", p.avg_cost)
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        # Native-currency market value (KRW for KR, USD for US)
        mv_native = price * p.shares
        # Normalize to KRW for cross-market aggregation
        mv_krw = mv_native if is_kr else mv_native * fx_rate
        items.append({
            "ticker": p.ticker,
            "name": canonical_display_name(sd.get("name"), p.ticker),
            "shares": p.shares,
            "avg_cost": p.avg_cost,
            "price": price,
            "market_value": mv_krw,        # KRW-normalized (used for weights/risk)
            "market_value_native": mv_native,  # original currency (display only)
            "is_kr": is_kr,
            "fx_rate": fx_rate if not is_kr else 1.0,
        })
        total_value += mv_krw

    return items, total_value


def _get_portfolio_returns(items, total_value, period="1y"):
    """Fetch historical prices and compute portfolio-level daily returns.

    Returns:
        daily_returns: list of floats (decimal, e.g. -0.02 = -2%)
        dates: list of date strings
    """
    from services.container import fetcher

    if not items or total_value <= 0:
        return [], []

    # weights by current market value
    weights = {it["ticker"]: it["market_value"] / total_value for it in items}

    # fetch history for each ticker
    ticker_returns: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    for it in items:
        hist = fetcher.get_price_history(it["ticker"], period=period)
        if hist is None or hist.empty or len(hist) < 2:
            continue

        closes = hist["Close"]
        pct = closes.pct_change().dropna()
        date_ret = {}
        for dt, ret in pct.items():
            ds = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            if math.isfinite(ret):
                date_ret[ds] = float(ret)
                all_dates.add(ds)
        ticker_returns[it["ticker"]] = date_ret

    if not all_dates:
        return [], []

    sorted_dates = sorted(all_dates)

    # compute weighted portfolio return for each date
    daily_returns = []
    valid_dates = []
    for ds in sorted_dates:
        port_ret = 0.0
        coverage = 0.0
        for ticker, w in weights.items():
            if ticker in ticker_returns and ds in ticker_returns[ticker]:
                port_ret += w * ticker_returns[ticker][ds]
                coverage += w
        # only include dates where we have data for at least 50% of portfolio weight
        if coverage >= 0.5:
            # scale up to full portfolio
            port_ret = port_ret / coverage if coverage < 1.0 else port_ret
            daily_returns.append(port_ret)
            valid_dates.append(ds)

    return daily_returns, valid_dates


@quant_bp.route("/risk/var")
@api_auth
@legal_scrub_response
def portfolio_var():
    """Calculate VaR and CVaR for the user's portfolio.

    Supports both parametric (normal) and historical simulation.
    Query params:
        period: history lookback (default '1y')
        horizon: holding period in days (default 1)
    """
    import numpy as np

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
        return jsonify({"error": "No positions in portfolio"}), 400

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if len(daily_returns) < 20:
        return jsonify({"error": "Insufficient history (need 20+ trading days)"}), 400

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


@quant_bp.route("/risk/drawdown")
@api_auth
@legal_scrub_response
def portfolio_drawdown():
    """Advanced drawdown analytics: Calmar, Ulcer Index, drawdown periods.

    Query params:
        period: history lookback (default '1y')
    """
    import numpy as np

    now = _time.time()
    uid = current_user.id
    user_cache = _dd_cache.get(uid)
    if user_cache and now - user_cache.get("ts", 0) < _VAR_CACHE_TTL:
        return jsonify(user_cache["data"])

    period = request.args.get("period", "1y")

    items, total_value = _load_positions_with_prices()
    if not items:
        return jsonify({"error": "No positions in portfolio"}), 400

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if len(daily_returns) < 5:
        return jsonify({"error": "Insufficient history (need 5+ trading days)"}), 400

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


# ── Helper functions for risk analytics ─────────────────────────────────────────

def _safe_skew(arr):
    """Compute skewness without scipy dependency."""
    import numpy as np
    n = len(arr)
    if n < 3:
        return 0.0
    mu = np.mean(arr)
    sigma = np.std(arr, ddof=1)
    if sigma < 1e-12:
        return 0.0
    return float(n / ((n - 1) * (n - 2)) * np.sum(((arr - mu) / sigma) ** 3))


def _safe_kurtosis(arr):
    """Compute excess kurtosis without scipy dependency."""
    import numpy as np
    n = len(arr)
    if n < 4:
        return 0.0
    mu = np.mean(arr)
    sigma = np.std(arr, ddof=1)
    if sigma < 1e-12:
        return 0.0
    m4 = float(np.mean(((arr - mu) / sigma) ** 4))
    # excess kurtosis (Fisher's definition)
    return m4 - 3.0


def _identify_drawdown_periods(dd_series, dates):
    """Walk through drawdown series and identify distinct drawdown periods.

    Returns list of dicts:
        {start, trough, trough_date, end, depth_pct, duration_days, recovery_days}
    """
    periods = []
    i = 0
    n = len(dd_series)

    while i < n:
        # find start of drawdown
        if dd_series[i] < -0.001:
            start_idx = i - 1 if i > 0 else 0
            trough_idx = i
            trough_val = dd_series[i]

            # walk forward to find trough
            j = i + 1
            while j < n and dd_series[j] < -0.0001:
                if dd_series[j] < trough_val:
                    trough_val = dd_series[j]
                    trough_idx = j
                j += 1

            # end of drawdown (recovery to 0 or end of series)
            end_idx = j if j < n else None

            duration = trough_idx - start_idx
            recovery_days = (end_idx - trough_idx) if end_idx is not None else None

            start_date = dates[start_idx] if start_idx < len(dates) else None
            trough_date = dates[trough_idx] if trough_idx < len(dates) else None
            end_date = dates[end_idx] if end_idx is not None and end_idx < len(dates) else None

            periods.append({
                "start": start_date,
                "trough": trough_date,
                "end": end_date,
                "depth_pct": round(float(trough_val) * 100, 2),
                "duration_days": duration,
                "recovery_days": recovery_days,
            })

            i = j
        else:
            i += 1

    return periods


# ── Benchmark-Relative Analytics ───────────────────────────────────────────────

_bench_cache: dict = {}  # {user_id: {"data": ..., "ts": ..., "key": ...}}
_BENCH_CACHE_TTL = 300  # 5 minutes

_VALID_PERIODS = {"3mo", "6mo", "1y", "2y"}
_RISK_FREE = 0.045  # annualized risk-free rate


@quant_bp.route("/analytics/benchmark")
@api_auth
@legal_scrub_response
def benchmark_analytics():
    """Compare user portfolio performance against a benchmark index.

    Query params:
        period: lookback period (default '1y'; options: 3mo, 6mo, 1y, 2y)
        benchmark: benchmark ticker (default 'SPY')
    """
    from services.container import fetcher

    period = request.args.get("period", "1y")
    benchmark_ticker = request.args.get("benchmark", "SPY")

    # ── Input validation ──
    if period not in _VALID_PERIODS:
        return jsonify({
            "error": f"Invalid period. Must be one of: {', '.join(sorted(_VALID_PERIODS))}",
        }), 400

    if not benchmark_ticker or len(benchmark_ticker) > 20:
        return jsonify({"error": "Invalid benchmark ticker"}), 400

    benchmark_ticker = benchmark_ticker.upper().strip()

    # ── Cache check (per-user, keyed by period+benchmark) ──
    now = _time.time()
    uid = current_user.id
    cache_key = f"{period}:{benchmark_ticker}"
    user_cache = _bench_cache.get(uid)
    if (user_cache and user_cache.get("key") == cache_key
            and now - user_cache.get("ts", 0) < _BENCH_CACHE_TTL):
        return jsonify(user_cache["data"])

    # ── Load portfolio positions and compute daily returns ──
    items, total_value = _load_positions_with_prices()
    if not items:
        return jsonify({"error": "No positions in portfolio"}), 400

    port_daily, port_dates = _get_portfolio_returns(items, total_value, period=period)
    if len(port_daily) < 20:
        return jsonify({"error": "Insufficient portfolio history (need 20+ trading days)"}), 400

    # ── Fetch benchmark returns ──
    bench_hist = fetcher.get_price_history(benchmark_ticker, period=period)
    if bench_hist is None or bench_hist.empty or len(bench_hist) < 20:
        return jsonify({"error": f"Insufficient benchmark data for {benchmark_ticker}"}), 400

    bench_closes = bench_hist["Close"]
    bench_pct = bench_closes.pct_change().dropna()

    # Build date-aligned benchmark returns dict
    bench_date_ret: dict[str, float] = {}
    for dt, ret in bench_pct.items():
        ds = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
        if math.isfinite(ret):
            bench_date_ret[ds] = float(ret)

    # ── Align dates: only keep dates present in both series ──
    port_date_ret = dict(zip(port_dates, port_daily))
    common_dates = sorted(set(port_date_ret.keys()) & set(bench_date_ret.keys()))

    if len(common_dates) < 20:
        return jsonify({
            "error": "Insufficient overlapping trading days between portfolio and benchmark",
        }), 400

    p_ret = np.array([port_date_ret[d] for d in common_dates], dtype=np.float64)
    b_ret = np.array([bench_date_ret[d] for d in common_dates], dtype=np.float64)
    n_days = len(common_dates)
    years = n_days / 252.0

    # ── Portfolio stats ──
    port_total = float(np.prod(1 + p_ret) - 1)
    port_ann = (1 + port_total) ** (1 / years) - 1 if years > 0 else 0.0
    port_vol = float(np.std(p_ret, ddof=1)) * math.sqrt(252)
    port_sharpe = (port_ann - _RISK_FREE) / port_vol if port_vol > 1e-9 else 0.0

    # Portfolio max drawdown
    port_equity = np.cumprod(1 + p_ret)
    port_peak = np.maximum.accumulate(port_equity)
    port_dd_series = (port_equity - port_peak) / port_peak
    port_max_dd = float(np.min(port_dd_series))

    port_calmar = port_ann / abs(port_max_dd) if abs(port_max_dd) > 1e-9 else 0.0

    # ── Benchmark stats ──
    bench_total = float(np.prod(1 + b_ret) - 1)
    bench_ann = (1 + bench_total) ** (1 / years) - 1 if years > 0 else 0.0
    bench_vol = float(np.std(b_ret, ddof=1)) * math.sqrt(252)
    bench_sharpe = (bench_ann - _RISK_FREE) / bench_vol if bench_vol > 1e-9 else 0.0

    bench_equity = np.cumprod(1 + b_ret)
    bench_peak = np.maximum.accumulate(bench_equity)
    bench_dd_series = (bench_equity - bench_peak) / bench_peak
    bench_max_dd = float(np.min(bench_dd_series))

    # ── Relative metrics ──
    active_returns = p_ret - b_ret
    active_return_ann = port_ann - bench_ann
    tracking_error = float(np.std(active_returns, ddof=1)) * math.sqrt(252)
    info_ratio = active_return_ann / tracking_error if tracking_error > 1e-9 else 0.0

    # Beta = cov(port, bench) / var(bench)
    cov_matrix = np.cov(p_ret, b_ret, ddof=1)
    beta = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix[1, 1] > 1e-12 else 1.0

    # Jensen's alpha = portfolio_ann - (risk_free + beta * (benchmark_ann - risk_free))
    alpha = port_ann - (_RISK_FREE + beta * (bench_ann - _RISK_FREE))

    # Up/Down capture ratios
    up_mask = b_ret > 0
    down_mask = b_ret < 0

    if np.sum(up_mask) > 0:
        up_capture = (float(np.mean(p_ret[up_mask])) / float(np.mean(b_ret[up_mask]))) * 100
    else:
        up_capture = 100.0

    if np.sum(down_mask) > 0:
        down_capture = (float(np.mean(p_ret[down_mask])) / float(np.mean(b_ret[down_mask]))) * 100
    else:
        down_capture = 100.0

    # Active share: approximate from return correlation (no benchmark constituents)
    correlation = float(np.corrcoef(p_ret, b_ret)[0, 1]) if n_days > 1 else 1.0
    active_share_est = round((1 - abs(correlation)) * 100, 1)

    # ── Rolling alpha (monthly windows) ──
    rolling_alpha = []
    window = 21  # ~1 month of trading days
    if n_days >= window:
        for i in range(window, n_days + 1, window):
            chunk_p = p_ret[i - window:i]
            chunk_b = b_ret[i - window:i]
            chunk_p_ann = float(np.mean(chunk_p)) * 252
            chunk_b_ann = float(np.mean(chunk_b)) * 252

            if len(chunk_b) > 1:
                chunk_cov = np.cov(chunk_p, chunk_b, ddof=1)
                chunk_beta = (
                    float(chunk_cov[0, 1] / chunk_cov[1, 1])
                    if chunk_cov[1, 1] > 1e-12 else 1.0
                )
            else:
                chunk_beta = 1.0

            chunk_alpha = chunk_p_ann - (_RISK_FREE + chunk_beta * (chunk_b_ann - _RISK_FREE))
            end_date = common_dates[i - 1]
            rolling_alpha.append({
                "date": end_date[:7],  # YYYY-MM
                "alpha": round(chunk_alpha * 100, 2),
            })

    # ── Cumulative comparison (equity curves starting at 100) ──
    port_cum = np.cumprod(1 + p_ret) * 100
    bench_cum = np.cumprod(1 + b_ret) * 100

    # Sample to max ~250 data points to keep payload manageable
    step = max(1, n_days // 250)
    cumulative_comparison = [{
        "date": common_dates[0],
        "portfolio": 100.0,
        "benchmark": 100.0,
    }]
    for idx in range(step, n_days, step):
        cumulative_comparison.append({
            "date": common_dates[idx],
            "portfolio": round(float(port_cum[idx]), 2),
            "benchmark": round(float(bench_cum[idx]), 2),
        })
    # Always include the final data point
    if cumulative_comparison[-1]["date"] != common_dates[-1]:
        cumulative_comparison.append({
            "date": common_dates[-1],
            "portfolio": round(float(port_cum[-1]), 2),
            "benchmark": round(float(bench_cum[-1]), 2),
        })

    payload = {
        "period": period,
        "benchmark": benchmark_ticker,
        "observation_days": n_days,
        "portfolio": {
            "total_return": round(port_total * 100, 2),
            "annualized_return": round(port_ann * 100, 2),
            "volatility": round(port_vol * 100, 2),
            "sharpe": round(port_sharpe, 3),
            "max_drawdown": round(port_max_dd * 100, 2),
            "calmar": round(port_calmar, 3),
        },
        "benchmark_stats": {
            "total_return": round(bench_total * 100, 2),
            "annualized_return": round(bench_ann * 100, 2),
            "volatility": round(bench_vol * 100, 2),
            "sharpe": round(bench_sharpe, 3),
            "max_drawdown": round(bench_max_dd * 100, 2),
        },
        "relative": {
            "active_return": round(active_return_ann * 100, 2),
            "tracking_error": round(tracking_error * 100, 2),
            "information_ratio": round(info_ratio, 3),
            "active_share": active_share_est,
            "beta": round(beta, 3),
            "alpha": round(alpha * 100, 2),
            "up_capture": round(up_capture, 1),
            "down_capture": round(down_capture, 1),
        },
        "rolling_alpha": rolling_alpha,
        "cumulative_comparison": cumulative_comparison,
    }

    add_disclaimer(payload, "analysis")
    _bounded_set(_bench_cache, uid, {"data": payload, "ts": now, "key": cache_key})
    return jsonify(payload)


# ── Stress Test ────────────────────────────────────────────────────────────────

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


@quant_bp.route("/risk/stress-test")
@api_auth
@legal_scrub_response
def portfolio_stress_test():
    """Run portfolio through historical crisis scenarios.

    Returns estimated impact for each scenario including per-position breakdown,
    survivors, worst-hit ticker, and hedge considerations.
    """
    items, total_value = _load_positions_with_prices()
    if not items:
        return jsonify({"error": "No positions in portfolio"}), 400

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
                "estimated_loss_usd": loss_usd,
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
            "portfolio_impact_usd": round(portfolio_loss_usd, 2),
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


# ── Short Interest Signal ─────────────────────────────────────────────────────

_si_cache: dict = {}
_SI_CACHE_TTL = 24 * 3600  # 24 hours — short interest updates bi-monthly


def _compute_short_signal(records, quote):
    """Compute short interest signal, pressure conditions, and history from raw data.

    Args:
        records: list of FMP short interest records (newest first).
        quote: FMP quote dict for the ticker (price, volume, avgVolume, sharesOutstanding).

    Returns:
        dict with current, history, signal, and pressure_conditions.
    """
    if not records:
        return None

    # FMP short interest fields vary; normalise what we need.
    # Expected fields per record: date, shortInterest (or sharesShort),
    # shortInterestRatio (days to cover), floatShort (% as decimal or pct).
    latest = records[0]

    (quote or {}).get("sharesOutstanding", 0) or 0
    avg_volume = (quote or {}).get("avgVolume", 0) or 0
    price = (quote or {}).get("price", 0) or 0
    volume = (quote or {}).get("volume", 0) or 0
    prev_close = (quote or {}).get("previousClose", price)

    # -- current short interest --
    short_interest = (
        latest.get("shortInterest")
        or latest.get("sharesShort")
        or 0
    )

    # short_float_pct: FMP may supply as decimal (0.028) or percentage (2.8).
    raw_float_short = latest.get("floatShort", 0) or 0
    if 0 < raw_float_short < 1:
        short_float_pct = round(raw_float_short * 100, 2)
    else:
        short_float_pct = round(raw_float_short, 2)

    # days_to_cover: from API or calculate
    days_to_cover = latest.get("shortInterestRatio") or latest.get("daysToCover") or 0
    if not days_to_cover and avg_volume > 0 and short_interest > 0:
        days_to_cover = round(short_interest / avg_volume, 2)
    days_to_cover = round(float(days_to_cover), 2)

    # -- 30-day change in short % --
    short_ratio_change_30d = 0.0
    if len(records) >= 2:
        older = None
        for rec in records[1:]:
            older = rec
            break
        if older:
            older_float = older.get("floatShort", 0) or 0
            if 0 < older_float < 1:
                older_pct = older_float * 100
            else:
                older_pct = older_float
            short_ratio_change_30d = round(short_float_pct - older_pct, 2)

    # -- history for charting (cap at 24 records) --
    history = []
    for rec in records[:24]:
        rec_si = rec.get("shortInterest") or rec.get("sharesShort") or 0
        rec_fs = rec.get("floatShort", 0) or 0
        if 0 < rec_fs < 1:
            rec_fs = round(rec_fs * 100, 2)
        else:
            rec_fs = round(rec_fs, 2)
        history.append({
            "date": rec.get("date", ""),
            "short_interest": rec_si,
            "short_float_pct": rec_fs,
        })
    # chronological order for charts
    history.reverse()

    # -- short pressure conditions --
    high_short_float = short_float_pct > 20.0
    low_days_to_cover = days_to_cover < 3.0 if days_to_cover > 0 else False

    # NOTE: Uses 1-day price change (current vs previous close) as short-term trend proxy
    price_change_recent = 0.0
    if price and prev_close:
        price_change_recent = (price - prev_close) / prev_close
    rising_price = price_change_recent > 0

    # volume > 2x average
    high_volume = (volume > 2 * avg_volume) if avg_volume > 0 else False

    conditions_met = sum([high_short_float, low_days_to_cover, rising_price, high_volume])
    conditions_total = 4

    # short_pressure_score: simple scoring 0-100 based on conditions met
    short_pressure_score = round(conditions_met / conditions_total * 100, 1)

    # -- signal direction & strength --
    direction = "NEUTRAL"
    strength = 50

    if high_short_float and low_days_to_cover and rising_price:
        direction = "HIGH_SHORT_PRESSURE"
        strength = min(90, 60 + conditions_met * 10)
    elif short_ratio_change_30d < -0.3:
        direction = "BULLISH"
        strength = min(80, 50 + int(abs(short_ratio_change_30d) * 20))
    elif short_ratio_change_30d > 0.3:
        direction = "BEARISH"
        strength = min(80, 50 + int(abs(short_ratio_change_30d) * 20))
    else:
        direction = "NEUTRAL"
        strength = 45

    strength = max(0, min(100, strength))

    # -- explanation --
    explanations = {
        "HIGH_SHORT_PRESSURE": (
            f"High short float ({short_float_pct:.1f}%) with low days to cover "
            f"({days_to_cover:.1f}) and rising price. Short pressure risk is elevated."
        ),
        "BULLISH": (
            f"Short interest is declining (30d change: {short_ratio_change_30d:+.1f}%). "
            "Bears are covering positions, reducing downside pressure."
        ),
        "BEARISH": (
            f"Short interest is rising (30d change: {short_ratio_change_30d:+.1f}%). "
            "Bears are adding positions, increasing downside pressure."
        ),
        "NEUTRAL": (
            "Short interest is low and stable. No significant short-side pressure."
        ),
    }

    return {
        "current": {
            "short_interest": short_interest,
            "short_float_pct": short_float_pct,
            "days_to_cover": days_to_cover,
            "short_ratio_change_30d": short_ratio_change_30d,
        },
        "history": history,
        "signal": {
            "direction": direction,
            "strength": strength,
            "short_pressure_score": short_pressure_score,
            "explanation": explanations[direction],
        },
        "pressure_conditions": {
            "high_short_float": high_short_float,
            "low_days_to_cover": low_days_to_cover,
            "rising_price": rising_price,
            "high_volume": high_volume,
            "conditions_met": conditions_met,
            "conditions_total": conditions_total,
        },
    }


@quant_bp.route("/signals/short-interest/<ticker>")
@api_auth
@legal_scrub_response
def short_interest_signal(ticker):
    """Short interest signal for a single ticker.

    Returns current short data, historical chart data, directional signal,
    and short pressure condition analysis.
    """
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 10:
        return jsonify({"error": "Invalid ticker"}), 400

    # per-ticker cache
    now = _time.time()
    cache_entry = _si_cache.get(ticker)
    if cache_entry and now - cache_entry["ts"] < _SI_CACHE_TTL:
        return jsonify(cache_entry["data"])

    from services.data import fmp as fmp

    records = fmp.get_short_interest(ticker)
    if not records:
        return jsonify({"error": f"No short interest data for {ticker}"}), 404

    quote = fmp.get_quote(ticker)

    result = _compute_short_signal(records, quote)
    if not result:
        return jsonify({"error": "Could not compute short interest signal"}), 500

    payload = {"ticker": ticker, "name": resolve_stock_name(ticker) or ticker, **result}
    add_disclaimer(payload, "indicator")

    _bounded_set(_si_cache, ticker, {"data": payload, "ts": now})
    return jsonify(payload)


# ── Turnover Report ────────────────────────────────────────────────────────────

_HOLDING_BUCKETS = [
    ("< 1 day", 0, 1),
    ("1-3 days", 1, 3),
    ("3-7 days", 3, 7),
    ("1-4 weeks", 7, 28),
    ("1-3 months", 28, 90),
    ("> 3 months", 90, float("inf")),
]

# Korean securities transaction tax rate (approximate)
_KR_TAX_RATE = 0.0023  # 0.23%
# Estimated slippage per trade (half-spread assumption)
_SLIPPAGE_BPS = 0.0010  # 10 bps
# Estimated commission per trade (discount broker average)
_COMMISSION_BPS = 0.0005  # 5 bps


def _match_buy_sell_pairs(trades):
    """Match BUY->SELL pairs per ticker using FIFO to compute holding periods.

    Returns list of dicts: {ticker, buy_date, sell_date, holding_days, sell_value}
    """
    from collections import defaultdict

    # Group by ticker, sort by date
    by_ticker = defaultdict(list)
    for t in trades:
        by_ticker[t.ticker].append(t)

    pairs = []
    for ticker, ticker_trades in by_ticker.items():
        ticker_trades.sort(key=lambda x: x.traded_at)
        buy_queue = []  # [{date, remaining, price}]

        for trade in ticker_trades:
            if trade.action == "BUY":
                buy_queue.append({
                    "date": trade.traded_at,
                    "remaining": trade.shares,
                    "price": trade.price_per_share,
                })
            elif trade.action == "SELL" and buy_queue:
                sell_remaining = trade.shares
                sell_date = trade.traded_at
                sell_price = trade.price_per_share

                while sell_remaining > 0 and buy_queue:
                    buy = buy_queue[0]
                    matched = min(sell_remaining, buy["remaining"])
                    holding_days = (sell_date - buy["date"]).days
                    pairs.append({
                        "ticker": ticker,
                        "buy_date": buy["date"],
                        "sell_date": sell_date,
                        "holding_days": max(holding_days, 0),
                        "sell_value": matched * sell_price,
                        "is_kr": ticker.upper().endswith(".KS") or ticker.upper().endswith(".KQ"),
                    })
                    buy["remaining"] -= matched
                    sell_remaining -= matched
                    if buy["remaining"] <= 0:
                        buy_queue.pop(0)

    return pairs


def _bucket_holding_periods(pairs):
    """Distribute matched pairs into holding-period histogram buckets."""
    counts = {label: 0 for label, _, _ in _HOLDING_BUCKETS}
    for p in pairs:
        days = p["holding_days"]
        for label, lo, hi in _HOLDING_BUCKETS:
            if lo <= days < hi:
                counts[label] += 1
                break
    return [{"bucket": label, "count": counts[label]} for label, _, _ in _HOLDING_BUCKETS]


@quant_bp.route("/analytics/turnover")
@api_auth
@legal_scrub_response
def turnover_report():
    """Analyze user's trading activity for cost efficiency.

    Query params:
        period: '3m', '6m', '1y', '2y', 'all' (default '1y')
    """
    from datetime import datetime, timedelta, timezone
    from models.trade_history import TradeHistory

    period = request.args.get("period", "1y")
    period_map = {"3m": 90, "6m": 180, "1y": 365, "2y": 730}
    days = period_map.get(period, None)

    uid = current_user.id
    query = TradeHistory.query.filter_by(user_id=uid)
    if days is not None:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        query = query.filter(TradeHistory.traded_at >= cutoff)
    query = query.order_by(TradeHistory.traded_at.asc())
    trades = query.all()

    if not trades:
        return jsonify({"error": "No trade history found for the selected period"}), 404

    total_trades = len(trades)
    buys = [t for t in trades if t.action == "BUY"]
    sells = [t for t in trades if t.action == "SELL"]

    # Match BUY->SELL pairs to compute holding periods
    pairs = _match_buy_sell_pairs(trades)

    # Holding period stats
    if pairs:
        holding_days_list = [p["holding_days"] for p in pairs]
        holding_days_list.sort()
        avg_holding = sum(holding_days_list) / len(holding_days_list)
        n = len(holding_days_list)
        median_holding = (
            holding_days_list[n // 2]
            if n % 2 == 1
            else (holding_days_list[n // 2 - 1] + holding_days_list[n // 2]) / 2
        )
    else:
        avg_holding = 0.0
        median_holding = 0

    # Distribution histogram
    distribution = _bucket_holding_periods(pairs)

    # Annualized turnover: (sum of sell values / avg portfolio value) * (252 / trading_days)
    total_sell_value = sum(p["sell_value"] for p in pairs)
    avg_buy_value = sum(t.total_value for t in buys) / max(len(buys), 1)
    avg_sell_value = sum(t.total_value for t in sells) / max(len(sells), 1)
    avg_portfolio_value = (avg_buy_value + avg_sell_value) / 2 if sells else avg_buy_value

    # Determine trading days in the period
    if trades:
        first_trade = trades[0].traded_at
        last_trade = trades[-1].traded_at
        calendar_days = max((last_trade - first_trade).days, 1)
        trading_days = max(int(calendar_days * 252 / 365), 1)
    else:
        trading_days = 252

    if avg_portfolio_value > 0:
        annualized_turnover = (total_sell_value / avg_portfolio_value) * (252 / trading_days)
    else:
        annualized_turnover = 0.0

    # Cost breakdown
    kr_sell_value = sum(p["sell_value"] for p in pairs if p.get("is_kr"))
    total_traded_value = sum(t.total_value for t in trades)

    commission_cost = total_traded_value * _COMMISSION_BPS
    slippage_cost = total_traded_value * _SLIPPAGE_BPS
    kr_tax_cost = kr_sell_value * _KR_TAX_RATE

    total_cost = commission_cost + slippage_cost + kr_tax_cost
    estimated_annual_cost_pct = (
        (total_cost / avg_portfolio_value) * (252 / trading_days) * 100
        if avg_portfolio_value > 0 else 0.0
    )

    # Assessment
    if avg_holding < 7:
        rec = (
            f"Your average holding period is {avg_holding:.1f} days (very short-term). "
            "Consider extending to 30+ days to reduce turnover costs by an estimated 60-70%."
        )
    elif avg_holding < 30:
        rec = (
            f"Your average holding period is {avg_holding:.1f} days. "
            "Consider extending to 30+ days to reduce turnover costs by an estimated 40%."
        )
    elif avg_holding < 90:
        rec = (
            f"Your average holding period is {avg_holding:.1f} days. "
            "Holding periods are reasonable. Consider 90+ days for long-term capital gains benefits."
        )
    else:
        rec = (
            f"Your average holding period is {avg_holding:.1f} days. "
            "Excellent long-term holding discipline. Turnover costs are well-controlled."
        )

    payload = {
        "period": period,
        "total_trades": total_trades,
        "buys": len(buys),
        "sells": len(sells),
        "avg_holding_period_days": round(avg_holding, 1),
        "median_holding_period_days": round(median_holding, 1),
        "annualized_turnover_pct": round(annualized_turnover * 100, 1),
        "estimated_annual_cost_pct": round(estimated_annual_cost_pct, 2),
        "holding_distribution": distribution,
        "cost_breakdown": {
            "commission": round(commission_cost / max(avg_portfolio_value, 1) * (252 / trading_days) * 100, 2),
            "slippage": round(slippage_cost / max(avg_portfolio_value, 1) * (252 / trading_days) * 100, 2),
            "tax_kr": round(kr_tax_cost / max(avg_portfolio_value, 1) * (252 / trading_days) * 100, 2),
        },
        "assessment": rec,
    }
    add_disclaimer(payload, "analysis")
    return jsonify(payload)


# ── Insider Transaction Signal ─────────────────────────────────────────────────

def _compute_insider_signal(transactions):
    """Compute insider sentiment summary and signal strength from FMP data.

    Args:
        transactions: list of dicts from FMP /insider-trading endpoint

    Returns:
        (insider_list, summary, signal_strength)
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff_90d = now - timedelta(days=90)
    cutoff_14d = now - timedelta(days=14)

    insider_list = []
    buys_90d = []
    sells_90d = []
    recent_buyers = []  # for cluster detection (14-day window)

    for tx in transactions:
        tx_type_raw = (tx.get("transactionType") or "").upper()
        acq_disp = (tx.get("acquistionOrDisposition") or "").upper()

        # Classify: P-Purchase / S-Sale, or use A/D flag
        if tx_type_raw.startswith("P") or acq_disp == "A":
            tx_type = "BUY"
        elif tx_type_raw.startswith("S") or acq_disp == "D":
            tx_type = "SELL"
        else:
            continue  # skip grants, exercises, etc.

        shares = tx.get("securitiesTransacted", 0) or 0
        price = tx.get("price", 0) or 0
        value = shares * price

        tx_date_str = tx.get("transactionDate") or tx.get("filingDate") or ""
        try:
            tx_date = datetime.strptime(tx_date_str[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            tx_date = None

        entry = {
            "date": tx_date_str[:10] if tx_date_str else None,
            "insider": tx.get("reportingName", "Unknown"),
            "title": tx.get("typeOfOwner", ""),
            "type": tx_type,
            "shares": shares,
            "value_usd": round(value, 2),
            "price": round(price, 2),
        }
        insider_list.append(entry)

        # Accumulate 90-day stats
        if tx_date and tx_date >= cutoff_90d:
            if tx_type == "BUY":
                buys_90d.append(entry)
                if tx_date >= cutoff_14d:
                    recent_buyers.append(tx.get("reportingName", ""))
            else:
                sells_90d.append(entry)

    # Net value
    buy_value = sum(b["value_usd"] for b in buys_90d)
    sell_value = sum(s["value_usd"] for s in sells_90d)
    net_value = buy_value - sell_value

    buy_count = len(buys_90d)
    sell_count = len(sells_90d)

    # Sentiment
    if buy_count > sell_count and net_value > 0:
        sentiment = "BULLISH"
    elif sell_count > buy_count and net_value < 0:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"

    # Cluster buy: 3+ distinct insiders buying within 14 days
    unique_recent_buyers = set(recent_buyers)
    cluster_buy = len(unique_recent_buyers) >= 3

    # Signal strength (0-100)
    # Factors: buy/sell ratio, net value magnitude, cluster
    score = 50  # baseline
    if buy_count + sell_count > 0:
        ratio = buy_count / (buy_count + sell_count)
        score += (ratio - 0.5) * 60  # -30 to +30

    # Net value factor (capped contribution)
    if net_value > 0:
        score += min(net_value / 1_000_000, 15)  # up to +15 for $1M+ net buying
    elif net_value < 0:
        score -= min(abs(net_value) / 1_000_000, 15)

    if cluster_buy:
        score += 10

    # Volume factor: more transactions = more conviction
    tx_count = buy_count + sell_count
    if tx_count >= 10:
        score += 5
    elif tx_count <= 2:
        score -= 5

    signal_strength = max(0, min(100, int(round(score))))

    summary = {
        "net_insider_sentiment": sentiment,
        "buy_count_90d": buy_count,
        "sell_count_90d": sell_count,
        "net_value_90d": round(net_value, 2),
        "cluster_buy": cluster_buy,
    }

    return insider_list, summary, signal_strength


@quant_bp.route("/signals/insider/<ticker>")
@api_auth
@legal_scrub_response
def insider_signal(ticker):
    """Fetch insider transactions from FMP and compute sentiment signal.

    Returns insider transaction history, 90-day summary, and signal strength.
    """
    import re

    # Validate ticker
    ticker = ticker.upper().strip()
    if not re.match(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$", ticker):
        return jsonify({"error": "Invalid ticker format"}), 400

    # Korean tickers not supported for insider data (SEC/FMP only)
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return jsonify({"error": "Insider data not available for Korean stocks"}), 400

    from services.data import fmp as fmp_service

    raw = fmp_service.get_insider_trades(ticker, limit=50)
    if raw is None:
        return jsonify({"error": "Failed to fetch insider data (API unavailable)"}), 503

    if not raw:
        empty_payload = {
            "ticker": ticker,
            "name": resolve_stock_name(ticker) or ticker,
            "insider_transactions": [],
            "summary": {
                "net_insider_sentiment": "NEUTRAL",
                "buy_count_90d": 0,
                "sell_count_90d": 0,
                "net_value_90d": 0,
                "cluster_buy": False,
            },
            "signal_strength": 50,
        }
        add_disclaimer(empty_payload, "indicator")
        return jsonify(empty_payload)

    insider_list, summary, signal_strength = _compute_insider_signal(raw)

    payload = {
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "insider_transactions": insider_list[:30],  # cap response size
        "summary": summary,
        "signal_strength": signal_strength,
    }
    add_disclaimer(payload, "indicator")
    return jsonify(payload)


# ── GKYZ Volatility Endpoint ────────────────────────────────────────────────

_vol_cache: dict = {}  # {ticker: {"data": ..., "ts": ...}}
_VOL_CACHE_TTL = 300  # 5 minutes


@quant_bp.route("/risk/volatility/<ticker>")
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
        return jsonify({"error": "Invalid ticker format"}), 400

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
        return jsonify({
            "error": f"Insufficient OHLC data for {ticker} (need {window + 1}+ bars)",
        }), 400

    from services.quant.risk_metrics import GKYZVolatility

    opens = hist["Open"].tolist()
    highs = hist["High"].tolist()
    lows = hist["Low"].tolist()
    closes = hist["Close"].tolist()

    result = GKYZVolatility.estimate(opens, highs, lows, closes, window=window)

    if result["vol_gkyz"] is None:
        return jsonify({"error": "Could not compute volatility"}), 500

    payload = {"ticker": ticker, "name": resolve_stock_name(ticker) or ticker, **result}
    add_disclaimer(payload, "indicator")
    _vol_cache[cache_key] = {"data": payload, "ts": now}
    return jsonify(payload)


# ── Component Expected Shortfall Endpoint ────────────────────────────────────

_ces_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_CES_CACHE_TTL = 300  # 5 minutes


@quant_bp.route("/risk/component-es")
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
        return jsonify({"error": "Need at least 2 positions for ES decomposition"}), 400

    # Fetch per-asset daily returns aligned by date
    from services.container import fetcher

    ticker_returns: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    for it in items:
        hist = fetcher.get_price_history(it["ticker"], period=period)
        if hist is None or hist.empty or len(hist) < 2:
            continue
        pct = hist["Close"].pct_change().dropna()
        date_ret = {}
        for dt, ret in pct.items():
            ds = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            if math.isfinite(ret):
                date_ret[ds] = float(ret)
                all_dates.add(ds)
        ticker_returns[it["ticker"]] = date_ret

    if len(ticker_returns) < 2:
        return jsonify({"error": "Insufficient history for ES decomposition"}), 400

    # Align: only dates present for ALL tickers with data
    common_dates = sorted(
        set.intersection(*(set(dr.keys()) for dr in ticker_returns.values()))
    )

    if len(common_dates) < 30:
        return jsonify({
            "error": "Insufficient overlapping trading days (need 30+)",
        }), 400

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
        return jsonify({"error": "Could not compute Expected Shortfall"}), 500

    # Enrich with ticker labels + resolved company name (name primary in UI)
    from services.name_resolver import resolve_stock_name

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


# ── Performance Ledger ────────────────���───────────────────────────────────────

@quant_bp.route("/performance/ledger")
@api_auth
@legal_scrub_response
def performance_ledger():
    """Public performance ledger -- ALL signal results, no cherry-picking.

    Legal: YELLOW -- must show ALL results including losses.

    Query params:
        period: '3m', '6m', '1y', '2y', 'all' (default 'all')
    """
    from collections import defaultdict
    from datetime import datetime, timedelta, timezone
    from models.trade_history import TradeHistory

    period = request.args.get("period", "all")
    period_map = {"3m": 90, "6m": 180, "1y": 365, "2y": 730}
    days = period_map.get(period, None)

    uid = current_user.id
    query = TradeHistory.query.filter_by(user_id=uid)
    if days is not None:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        query = query.filter(TradeHistory.traded_at >= cutoff)
    query = query.order_by(TradeHistory.traded_at.asc())
    trades = query.all()

    if not trades:
        return jsonify({"error": "No trade history found"}), 404

    # ── Aggregate stats ──
    total_signals = len(trades)
    sell_trades = [t for t in trades if t.action == "SELL"]
    buy_trades = [t for t in trades if t.action == "BUY"]
    total_executed = len(sell_trades)

    wins = [t for t in sell_trades if (t.pnl or 0) > 0]
    losses = [t for t in sell_trades if (t.pnl or 0) < 0]
    breakeven = [t for t in sell_trades if (t.pnl or 0) == 0]

    win_rate = round(len(wins) / total_executed * 100, 1) if total_executed > 0 else 0.0
    avg_gain = round(
        sum(t.pnl_pct or 0 for t in wins) / len(wins), 2
    ) if wins else 0.0
    avg_loss = round(
        sum(t.pnl_pct or 0 for t in losses) / len(losses), 2
    ) if losses else 0.0

    total_pnl = sum(t.pnl or 0 for t in sell_trades)
    total_pnl_pct = round(
        sum(t.pnl_pct or 0 for t in sell_trades) / total_executed, 2
    ) if total_executed > 0 else 0.0

    # Profit factor = gross gains / gross losses
    gross_gains = sum(t.pnl or 0 for t in wins)
    gross_losses = abs(sum(t.pnl or 0 for t in losses))
    profit_factor = round(gross_gains / gross_losses, 2) if gross_losses > 0 else 0.0

    # ── Per-strategy attribution (group by ticker) ──
    strategy_stats: dict = defaultdict(lambda: {
        "trades": 0, "wins": 0, "losses": 0,
        "total_pnl": 0.0, "total_pnl_pct": 0.0,
    })
    for t in sell_trades:
        s = strategy_stats[t.ticker]
        s["trades"] += 1
        s["total_pnl"] += t.pnl or 0
        s["total_pnl_pct"] += t.pnl_pct or 0
        if (t.pnl or 0) > 0:
            s["wins"] += 1
        elif (t.pnl or 0) < 0:
            s["losses"] += 1

    per_strategy = []
    for ticker, s in sorted(strategy_stats.items()):
        per_strategy.append({
            "ticker": ticker,
            "name": resolve_stock_name(ticker) or ticker,
            "trades": s["trades"],
            "wins": s["wins"],
            "losses": s["losses"],
            "win_rate": round(
                s["wins"] / s["trades"] * 100, 1
            ) if s["trades"] > 0 else 0.0,
            "total_pnl": round(s["total_pnl"], 2),
            "avg_pnl_pct": round(
                s["total_pnl_pct"] / s["trades"], 2
            ) if s["trades"] > 0 else 0.0,
        })

    # ── Monthly performance breakdown ──
    monthly: dict = defaultdict(lambda: {
        "trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0,
    })
    for t in sell_trades:
        month_key = t.traded_at.strftime("%Y-%m")
        m = monthly[month_key]
        m["trades"] += 1
        m["total_pnl"] += t.pnl or 0
        if (t.pnl or 0) > 0:
            m["wins"] += 1
        elif (t.pnl or 0) < 0:
            m["losses"] += 1

    monthly_breakdown = []
    for month_key in sorted(monthly.keys()):
        m = monthly[month_key]
        monthly_breakdown.append({
            "month": month_key,
            "trades": m["trades"],
            "wins": m["wins"],
            "losses": m["losses"],
            "win_rate": round(
                m["wins"] / m["trades"] * 100, 1
            ) if m["trades"] > 0 else 0.0,
            "total_pnl": round(m["total_pnl"], 2),
        })

    payload = {
        "period": period,
        "total_signals": total_signals,
        "total_buys": len(buy_trades),
        "total_sells": total_executed,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate": win_rate,
        "avg_gain_pct": avg_gain,
        "avg_loss_pct": avg_loss,
        "total_pnl": round(total_pnl, 2),
        "avg_pnl_pct": total_pnl_pct,
        "profit_factor": profit_factor,
        "gross_gains": round(gross_gains, 2),
        "gross_losses": round(gross_losses, 2),
        "per_strategy": per_strategy,
        "monthly_breakdown": monthly_breakdown,
    }
    add_disclaimer(payload, "analysis")
    return jsonify(payload)


# ── Position Sizing Calculator (Kelly Criterion) ──────────────���──────────────

@quant_bp.route("/tools/position-sizing", methods=["POST"])
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
        return jsonify({"error": "Request body required (JSON)"}), 400

    ticker = (data.get("ticker") or "").upper().strip()
    if not ticker or len(ticker) > 20:
        return jsonify({"error": "Invalid or missing ticker"}), 400

    # ── Input validation ──
    try:
        win_prob = float(data.get("win_probability", 0))
        avg_win = float(data.get("avg_win", 0))
        avg_loss = float(data.get("avg_loss", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "win_probability, avg_win, avg_loss must be numbers"}), 400

    if not (0 < win_prob < 1):
        return jsonify({"error": "win_probability must be between 0 and 1 (exclusive)"}), 400
    if avg_win <= 0:
        return jsonify({"error": "avg_win must be positive"}), 400
    if avg_loss <= 0:
        return jsonify({"error": "avg_loss must be positive"}), 400

    # ��─ Kelly Criterion ──
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


# ── Behavioral & Microstructure Signal Models ─────────────────────────────────

_signal_cache: dict = {}  # {f"{endpoint}:{ticker}": {"data": ..., "ts": ...}}
_SIGNAL_CACHE_TTL = 300  # 5 minutes


def _ticker_validate(ticker):
    """Validate and normalize a ticker symbol. Returns (ticker, error_response)."""
    import re as _re
    ticker = (ticker or "").upper().strip()
    if not ticker or not _re.match(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$", ticker):
        return None, (jsonify({"error": "Invalid ticker format"}), 400)
    return ticker, None


def _get_ohlcv(ticker, period="1y"):
    """Fetch OHLCV data for a ticker. Returns (opens, closes, volumes, error_resp)."""
    from services.container import fetcher

    hist = fetcher.get_price_history(ticker, period=period)
    if hist is None or hist.empty or len(hist) < 20:
        return None, None, None, (
            jsonify({"error": f"Insufficient price history for {ticker}"}), 404
        )

    opens = hist["Open"].tolist() if "Open" in hist.columns else None
    closes = hist["Close"].tolist()
    volumes = hist["Volume"].tolist() if "Volume" in hist.columns else None

    return opens, closes, volumes, None


@quant_bp.route("/signals/disposition/<ticker>")
@api_auth
@legal_scrub_response
def signal_disposition(ticker):
    """Disposition Effect (CGO) indicator for a single ticker.

    YELLOW endpoint — data indicator only, no buy/sell direction.
    Uses volume-weighted reference price as proxy for aggregate cost basis.

    Query params:
        window: lookback in trading days (default 252)
    """
    ticker, err = _ticker_validate(ticker)
    if err:
        return err

    now = _time.time()
    cache_key = f"disposition:{ticker}"
    cached = _signal_cache.get(cache_key)
    if cached and now - cached.get("ts", 0) < _SIGNAL_CACHE_TTL:
        return jsonify(cached["data"])

    try:
        window = max(20, min(int(request.args.get("window", "252")), 504))
    except (ValueError, TypeError):
        window = 252

    _, closes, volumes, data_err = _get_ohlcv(ticker, period="2y" if window > 252 else "1y")
    if data_err:
        return data_err

    if volumes is None:
        return jsonify({"error": "Volume data unavailable"}), 404

    from services.quant.signals import DispositionEffect

    result = DispositionEffect.calculate(closes, volumes, window=window)

    payload = {
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "model": "disposition_effect",
        "classification": "YELLOW",
        **result,
        "disclaimer": DISCLAIMERS["indicator"],
    }

    _bounded_set(_signal_cache, cache_key, {"data": payload, "ts": now})
    return jsonify(payload)


@quant_bp.route("/signals/ofi/<ticker>")
@api_auth
@legal_scrub_response
def signal_ofi(ticker):
    """Order Flow Imbalance for a single ticker.

    YELLOW endpoint — data visualization only, no trading direction.
    Approximates OFI from daily OHLCV using close-vs-open as directional proxy.

    Query params:
        window: accumulation window in trading days (default 20)
    """
    ticker, err = _ticker_validate(ticker)
    if err:
        return err

    now = _time.time()
    cache_key = f"ofi:{ticker}"
    cached = _signal_cache.get(cache_key)
    if cached and now - cached.get("ts", 0) < _SIGNAL_CACHE_TTL:
        return jsonify(cached["data"])

    try:
        window = max(5, min(int(request.args.get("window", "20")), 60))
    except (ValueError, TypeError):
        window = 20

    opens, closes, volumes, data_err = _get_ohlcv(ticker, period="6mo")
    if data_err:
        return data_err

    if opens is None or volumes is None:
        return jsonify({"error": "OHLCV data incomplete"}), 404

    from services.quant.signals import OrderFlowImbalance

    result = OrderFlowImbalance.calculate(opens, closes, volumes, window=window)

    payload = {
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "model": "order_flow_imbalance",
        "classification": "YELLOW",
        **result,
        "disclaimer": DISCLAIMERS["indicator"],
    }

    _bounded_set(_signal_cache, cache_key, {"data": payload, "ts": now})
    return jsonify(payload)


@quant_bp.route("/signals/sentiment-divergence/<ticker>")
@api_auth
@legal_scrub_response
def signal_sentiment_divergence(ticker):
    """Sentiment-Price Divergence for a single ticker.

    GREEN endpoint — pure data analysis, no directional guidance.
    Computes rate-of-change for both price and news sentiment, detects divergence.

    Query params:
        window: ROC lookback in trading days (default 21)
    """
    ticker, err = _ticker_validate(ticker)
    if err:
        return err

    now = _time.time()
    cache_key = f"sentdiv:{ticker}"
    cached = _signal_cache.get(cache_key)
    if cached and now - cached.get("ts", 0) < _SIGNAL_CACHE_TTL:
        return jsonify(cached["data"])

    try:
        window = max(5, min(int(request.args.get("window", "21")), 60))
    except (ValueError, TypeError):
        window = 21

    _, closes, _, data_err = _get_ohlcv(ticker, period="6mo")
    if data_err:
        return data_err

    from services.container import fetcher
    from services.quant.signals import SentimentPriceDivergence

    sentiment_score, _ = fetcher.score_news_sentiment(ticker)

    # Create a synthetic sentiment series: use price momentum as proxy for
    # historical sentiment, anchored to the current AI-scored sentiment.
    prices_arr = np.array(closes, dtype=np.float64)
    n = len(prices_arr)
    if n < window + 1:
        return jsonify({"error": "Insufficient data for requested window"}), 400

    pct_changes = np.diff(prices_arr) / prices_arr[:-1]
    synthetic_sentiment = np.full(n, sentiment_score, dtype=np.float64)
    for i in range(n - 2, -1, -1):
        shift = pct_changes[i] * 50  # 1% price move = 0.5 sentiment point
        synthetic_sentiment[i] = np.clip(synthetic_sentiment[i + 1] - shift, 0, 100)

    result = SentimentPriceDivergence.calculate(
        closes, synthetic_sentiment.tolist(), window=window,
    )

    payload = {
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "model": "sentiment_price_divergence",
        "classification": "GREEN",
        "news_sentiment_score": round(sentiment_score, 1),
        **result,
    }

    _bounded_set(_signal_cache, cache_key, {"data": payload, "ts": now})
    return jsonify(payload)


@quant_bp.route("/signals/anchoring/<ticker>")
@api_auth
@legal_scrub_response
def signal_anchoring(ticker):
    """Anchoring Bias indicator for a single ticker.

    YELLOW endpoint — indicator within existing framework.
    Combines 52-week high proximity with CGO for interaction signal.

    Query params:
        window: lookback in trading days (default 252)
    """
    ticker, err = _ticker_validate(ticker)
    if err:
        return err

    now = _time.time()
    cache_key = f"anchoring:{ticker}"
    cached = _signal_cache.get(cache_key)
    if cached and now - cached.get("ts", 0) < _SIGNAL_CACHE_TTL:
        return jsonify(cached["data"])

    try:
        window = max(60, min(int(request.args.get("window", "252")), 504))
    except (ValueError, TypeError):
        window = 252

    _, closes, volumes, data_err = _get_ohlcv(ticker, period="2y" if window > 252 else "1y")
    if data_err:
        return data_err

    if volumes is None:
        return jsonify({"error": "Volume data unavailable"}), 404

    from services.quant.signals import AnchoringBias

    result = AnchoringBias.calculate(closes, volumes, window=window)

    payload = {
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "model": "anchoring_bias",
        "classification": "YELLOW",
        **result,
        "disclaimer": DISCLAIMERS["indicator"],
    }

    _bounded_set(_signal_cache, cache_key, {"data": payload, "ts": now})
    return jsonify(payload)


@quant_bp.route("/signals/herding")
@api_auth
@legal_scrub_response
def signal_herding():
    """Cross-Sectional Herding Intensity indicator.

    YELLOW endpoint — data indicator only, no directional guidance.
    Computes CSAD across a basket of stocks to detect herding behavior.
    Market-level indicator (not per-ticker). Uses SPY as market proxy.

    Query params:
        window: lookback in trading days (default 60)
    """
    now = _time.time()
    cache_key = "herding:market"
    cached = _signal_cache.get(cache_key)
    if cached and now - cached.get("ts", 0) < _SIGNAL_CACHE_TTL:
        return jsonify(cached["data"])

    try:
        window = max(20, min(int(request.args.get("window", "60")), 120))
    except (ValueError, TypeError):
        window = 60

    from services.container import fetcher
    from services.quant.signals import HerdingIntensity

    basket = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "JPM", "JNJ", "XOM", "PG", "NVDA"]
    market_ticker = "SPY"

    mkt_hist = fetcher.get_price_history(market_ticker, period="6mo")
    if mkt_hist is None or mkt_hist.empty or len(mkt_hist) < window + 1:
        return jsonify({"error": "Market data unavailable"}), 503

    mkt_closes = mkt_hist["Close"].values.astype(float)
    mkt_returns = list(np.diff(mkt_closes) / mkt_closes[:-1])

    stock_returns_list = []
    included_tickers = []
    for t in basket:
        try:
            hist = fetcher.get_price_history(t, period="6mo")
            if hist is None or hist.empty or len(hist) < window + 1:
                continue
            sc = hist["Close"].values.astype(float)
            sr = list(np.diff(sc) / sc[:-1])
            stock_returns_list.append(sr)
            included_tickers.append(t)
        except Exception:
            logger.debug("silent-fallback: signal_herding", exc_info=True)
            continue

    if len(stock_returns_list) < 3:
        return jsonify({"error": "Insufficient stock data for herding analysis"}), 503

    result = HerdingIntensity.calculate(stock_returns_list, mkt_returns, window=window)

    payload = {
        "model": "herding_intensity",
        "classification": "YELLOW",
        "basket": included_tickers,
        "market_proxy": market_ticker,
        **result,
        "disclaimer": DISCLAIMERS["indicator"],
    }

    _bounded_set(_signal_cache, cache_key, {"data": payload, "ts": now})
    return jsonify(payload)


# ── Extended Indicators (10 technical + 8 fundamental) ───────────────────────

_indicators_cache: dict = {}  # {ticker: {"data": ..., "ts": ...}}
_INDICATORS_CACHE_TTL = 300   # 5 minutes


@quant_bp.route("/indicators/<ticker>")
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
        return jsonify({"error": "Insufficient price data for indicators"}), 400

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


# ── Correlation Matrix Tool ──────────────────────────────────────────────────

_corr_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_CORR_CACHE_TTL = 300  # 5 minutes


@quant_bp.route("/tools/correlation-matrix")
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
        return jsonify({"error": "Need at least 2 positions for correlation matrix"}), 400

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
        return jsonify({"error": "Insufficient data for correlation (need 2+ tickers with history)"}), 400

    # Align on common dates
    common_dates = sorted(all_dates)
    # Only keep dates where all tickers have data
    for t in included:
        common_dates = [d for d in common_dates if d in ticker_returns[t]]

    if len(common_dates) < 20:
        return jsonify({"error": "Insufficient overlapping trading days (need 20+)"}), 400

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


# ── Sector Heatmap Tool ──────────────────────────────────────────────────────

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


@quant_bp.route("/tools/sector-heatmap")
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
        return jsonify({"error": "Sector data unavailable"}), 500

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


# ── CAN SLIM Screener ───────────────────────────────────────────────────────

@quant_bp.route("/screener/canslim/<ticker>")
@api_auth
@legal_scrub_response
def canslim_screener(ticker):
    """CAN SLIM 7-factor stock screener.

    YELLOW endpoint -- scoring model for informational purposes only.
    Does not constitute a buy/sell signal or investment advice.
    """
    from services.data.fetcher import DataFetcher
    from services.quant.canslim import CANSLIMScreener
    from services.quant.models import RegimeSwitching
    from services.data import fmp as fmp_svc

    ticker = ticker.strip().upper()

    fetcher = DataFetcher()
    hist = fetcher.get_price_history(ticker, period="1y")
    if hist is None or hist.empty or len(hist) < 20:
        return jsonify({"error": f"Insufficient price data for {ticker}"}), 404

    closes = hist["Close"].values.astype(float)
    volumes = hist["Volume"].values.astype(float)

    # Fundamentals from EDGAR (graceful fallback)
    fundamentals = None
    try:
        from services.data.edgar import EdgarService
        fundamentals = EdgarService.get_fundamentals(ticker)
    except Exception:
        logger.debug("silent-fallback: canslim_screener", exc_info=True)
        pass

    # Float shares from FMP profile
    float_shares = None
    try:
        profile = fmp_svc.get_profile(ticker)
        if profile:
            float_shares = profile.get("floatShares") or profile.get("sharesFloat")
    except Exception:
        logger.debug("silent-fallback: canslim_screener", exc_info=True)
        pass

    # Market regime from RegimeSwitching
    regime = None
    try:
        rs = RegimeSwitching.analyze(list(closes))
        if rs:
            regime = rs.get("regime")
    except Exception:
        logger.debug("silent-fallback: canslim_screener", exc_info=True)
        pass

    result = CANSLIMScreener.score(ticker, closes, volumes, fundamentals, regime, float_shares=float_shares)

    payload = {
        "ok": True,
        **result,
    }
    add_disclaimer(payload, "indicator")
    return jsonify(payload)


# ── Interest Rate Regime ────────────────────────────────────────────────────

_ir_regime_cache: dict = {}
_IR_REGIME_CACHE_TTL = 3600  # 1 hour

@quant_bp.route("/regime/interest-rate")
@api_auth
@legal_scrub_response
def interest_rate_regime():
    """4-stage interest rate cycle classification.

    YELLOW endpoint -- macro regime for informational purposes only.
    Uses FRED API data or hardcoded current rates as fallback.
    """
    from services.quant.models import InterestRateRegime

    now = _time.time()
    cached = _ir_regime_cache.get("data")
    if cached and now - _ir_regime_cache.get("ts", 0) < _IR_REGIME_CACHE_TTL:
        return jsonify(cached)

    # Try FRED API first, fall back to hardcoded current rates
    fed_rate_current = None
    fed_rate_6m_ago = None
    gdp_growth = None
    cpi = None

    try:
        import requests as _requests
        # FRED series: FEDFUNDS (effective federal funds rate)
        fred_key = None
        try:
            import os
            fred_key = os.environ.get("FRED_API_KEY")
        except Exception:
            logger.debug("silent-fallback: interest_rate_regime", exc_info=True)
            pass

        if fred_key:
            resp = _requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": "FEDFUNDS",
                    "api_key": fred_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 7,
                },
                timeout=5,
            )
            if resp.ok:
                obs = resp.json().get("observations", [])
                if len(obs) >= 7:
                    fed_rate_current = float(obs[0]["value"])
                    fed_rate_6m_ago = float(obs[6]["value"])
    except Exception:
        logger.debug("silent-fallback: interest_rate_regime", exc_info=True)
        pass

    # Fallback: hardcoded rates (updated periodically)
    if fed_rate_current is None:
        fed_rate_current = 4.33   # As of early 2026
        fed_rate_6m_ago = 4.58    # 6 months prior

    result = InterestRateRegime.classify(
        fed_rate_current, fed_rate_6m_ago, gdp_growth, cpi
    )

    payload = {
        "ok": True,
        **result,
        "data_source": "FRED" if fed_rate_6m_ago != 4.58 else "hardcoded_fallback",
    }
    add_disclaimer(payload, "regime")

    _ir_regime_cache["data"] = payload
    _ir_regime_cache["ts"] = now
    return jsonify(payload)


# ── Risk Defense Status ──────────────────────────────────────────────────────

_defense_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_DEFENSE_CACHE_TTL = 60  # 1 minute


@quant_bp.route("/risk/defense-status")
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
        return jsonify({"error": "No positions in portfolio"}), 400

    fetcher = DataFetcher()

    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    # Build position list with weights, values, sectors
    pos_list = []
    total_value = 0
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        price = sd.get("price", p.avg_cost)
        mv = price * p.shares
        sector = sd.get("sector", "Unknown")
        total_value += mv
        from services.name_resolver import resolve_stock_name
        pos_list.append({
            "ticker": p.ticker,
            "name": canonical_display_name(sd.get("name"), p.ticker),
            "value": mv,
            "sector": sector,
            "weight": 0,  # filled below
        })

    if total_value <= 0:
        return jsonify({"error": "Portfolio value is zero"}), 400

    # Assign weights
    for pos in pos_list:
        pos["weight"] = pos["value"] / total_value

    # Build returns matrix from price history (20-day lookback)
    returns_cols = []
    valid_tickers = []
    for pos in pos_list:
        try:
            hist = fetcher.get_price_history(pos["ticker"], period="3mo")
            if hist is not None and not hist.empty and len(hist) >= 21:
                closes = hist["Close"].values[-21:]
                daily_rets = np.diff(closes) / closes[:-1]
                returns_cols.append(daily_rets)
                valid_tickers.append(pos["ticker"])
        except Exception:
            logger.debug("silent-fallback: risk_defense_status", exc_info=True)
            pass

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
    vix = None
    try:
        from services.quant.models import VIXStrategy
        vix_data = VIXStrategy.analyze()
        if vix_data and "current_vix" in vix_data:
            vix = vix_data["current_vix"]
    except Exception:
        logger.debug("silent-fallback: risk_defense_status", exc_info=True)
        pass

    # Get current regime
    regime = "TRANSITION"
    try:
        from services.quant.models import VolatilityRegime
        regime_data = VolatilityRegime.detect()
        if regime_data and "regime" in regime_data:
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


# ── Additional Risk Analytics (ConditionalDD / TailRatio / SortinoByPosition / LedoitWolf) ──

_cddar_cache: dict = {}
_tailratio_cache: dict = {}
_sortino_cache: dict = {}
_lws_cache: dict = {}
_RISK_X_CACHE_TTL = 300  # 5 minutes


@quant_bp.route("/risk/conditional-drawdown", methods=["POST"])
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
        return jsonify({"error": "No positions to analyze"}), 400

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if not daily_returns or len(daily_returns) < 20:
        return jsonify({"error": "Insufficient history (need 20+ trading days)"}), 400

    # Reconstruct portfolio equity curve from daily returns
    pv = [1.0]
    for r in daily_returns:
        pv.append(pv[-1] * (1.0 + r))

    from services.quant.risk_metrics import ConditionalDrawdown
    result = ConditionalDrawdown.calculate(pv, alpha=alpha)

    if result.get("cddar") is None:
        return jsonify({"error": "Could not compute CDDaR"}), 500

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


@quant_bp.route("/risk/tail-ratio", methods=["POST"])
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
        return jsonify({"error": "No positions to analyze"}), 400

    daily_returns, dates = _get_portfolio_returns(items, total_value, period=period)
    if not daily_returns or len(daily_returns) < 20:
        return jsonify({"error": "Insufficient history (need 20+ trading days)"}), 400

    from services.quant.risk_metrics import TailRatio
    result = TailRatio.calculate(daily_returns)

    if result.get("tail_ratio") is None:
        return jsonify({"error": "Could not compute Tail Ratio"}), 500

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


@quant_bp.route("/risk/sortino-by-position", methods=["POST"])
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
        return jsonify({"error": "No positions to analyze"}), 400

    from services.container import fetcher
    from services.quant.risk_metrics import SortinoByPosition

    positions_out = []
    for it in items:
        hist = fetcher.get_price_history(it["ticker"], period=period)
        if hist is None or hist.empty or len(hist) < 21:
            positions_out.append({
                "ticker": it["ticker"],
                "name": it.get("name") or it["ticker"],
                "sortino": None,
                "error": "insufficient history",
            })
            continue
        rets = hist["Close"].astype(float).pct_change().dropna().tolist()
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


@quant_bp.route("/risk/ledoit-wolf-shrinkage", methods=["POST"])
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
        return jsonify({"error": "Need at least 2 positions for covariance"}), 400

    # Build aligned returns matrix (only dates where ALL tickers have data)
    from services.container import fetcher

    ticker_returns: dict[str, dict[str, float]] = {}
    for it in items:
        hist = fetcher.get_price_history(it["ticker"], period=period)
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
        return jsonify({"error": "Insufficient history for covariance"}), 400

    common_dates = sorted(
        set.intersection(*(set(dr.keys()) for dr in ticker_returns.values()))
    )
    if len(common_dates) < 20:
        return jsonify({"error": "Insufficient overlapping trading days (need 20+)"}), 400

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
        return jsonify({"error": "Could not estimate shrinkage covariance"}), 500

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
