"""Performance analytics quant routes: regime-conditional performance report,
benchmark-relative analytics, turnover report, performance ledger.

Split from routes/quant.py (Wave 11 SRP refactor).
All URL paths preserved exactly (`/api/analytics/...`, `/api/performance/...`).
No behaviour change.
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
from .decorators import api_auth, legal_scrub_response
from .quant_helpers import (
    _RISK_FREE,
    _VALID_PERIODS,
    _bounded_set,
    _get_portfolio_returns,
    _load_positions_with_prices,
    add_disclaimer,
)

logger = logging.getLogger(__name__)

performance_quant_bp = Blueprint("performance_quant", __name__, url_prefix="/api")

# ─────────────────────────────────────────────────────────────────────────────
# Caches
# ─────────────────────────────────────────────────────────────────────────────

_regime_cache: dict = {}  # {user_id: {"data": ..., "ts": ..., "key": ...}}
_REGIME_CACHE_TTL = 300  # 5 minutes

_bench_cache: dict = {}  # {user_id: {"data": ..., "ts": ..., "key": ...}}
_BENCH_CACHE_TTL = 300  # 5 minutes


def _finite_floats(obj):
    """Recursively coerce any non-finite float (nan/inf/-inf) to 0.0.

    Defense-in-depth: json.dumps emits literal `NaN`/`Infinity` for these,
    which is invalid JSON and crashes JSON.parse on the frontend. Any quant
    payload built from numpy stats can produce them (zero-variance corrcoef,
    0/0 ratios). Run the final payload through this before jsonify so a
    single missed guard can never ship a non-parseable response.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else 0.0
    if isinstance(obj, dict):
        return {k: _finite_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_finite_floats(v) for v in obj]
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Regime-Conditional Performance Report
# ─────────────────────────────────────────────────────────────────────────────

@performance_quant_bp.route("/analytics/regime-report")
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
            return api_error(
                en="No positions in portfolio",
                kr="포트폴리오에 보유 종목이 없습니다.",
                code="PERFORMANCE_NO_POSITIONS",
                status=400,
            )

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
        return api_error(
            en="No tickers to test",
            kr="테스트할 종목이 없습니다.",
            code="PERFORMANCE_NO_TICKERS",
            status=400,
        )

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


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark-Relative Analytics
# ─────────────────────────────────────────────────────────────────────────────

@performance_quant_bp.route("/analytics/benchmark")
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
        return api_error(
            en="Invalid benchmark ticker",
            kr="유효하지 않은 벤치마크 종목입니다.",
            code="PERFORMANCE_BENCHMARK_INVALID",
            status=400,
        )

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
        return api_error(
            en="No positions in portfolio",
            kr="포트폴리오에 보유 종목이 없습니다.",
            code="PERFORMANCE_NO_POSITIONS",
            status=400,
        )

    port_daily, port_dates = _get_portfolio_returns(items, total_value, period=period)
    if len(port_daily) < 20:
        return api_error(
            en="Insufficient portfolio history (need 20+ trading days)",
            kr="포트폴리오 이력이 부족합니다 (최소 20거래일 필요).",
            code="PERFORMANCE_INSUFFICIENT_HISTORY",
            status=400,
        )

    # ── Fetch benchmark returns ──
    bench_hist = fetcher.get_price_history(benchmark_ticker, period=period)
    if bench_hist is None or bench_hist.empty or len(bench_hist) < 20:
        return api_error(
            en=f"Insufficient benchmark data for {benchmark_ticker}",
            kr=f"{benchmark_ticker} 벤치마크 데이터가 부족합니다.",
            code="PERFORMANCE_INSUFFICIENT_BENCHMARK",
            status=400,
        )

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
    # np.corrcoef returns nan when either series has zero variance (identical or
    # flat returns). nan serializes to literal `NaN` via json.dumps which is
    # invalid JSON — JSON.parse on the frontend throws and crashes the page.
    # Coerce to 0.0 (no measurable divergence), mirroring the vol>1e-9 guard
    # used for the Sharpe denominators above.
    if not math.isfinite(correlation):
        correlation = 0.0
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
    payload = _finite_floats(payload)
    _bounded_set(_bench_cache, uid, {"data": payload, "ts": now, "key": cache_key})
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Turnover Report
# ─────────────────────────────────────────────────────────────────────────────

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


@performance_quant_bp.route("/analytics/turnover")
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
        return api_error(
            en="No trade history found for the selected period",
            kr="선택한 기간에 거래 이력이 없습니다.",
            code="PERFORMANCE_NO_TRADES_PERIOD",
            status=404,
        )

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


# ─────────────────────────────────────────────────────────────────────────────
# Performance Ledger
# ─────────────────────────────────────────────────────────────────────────────

@performance_quant_bp.route("/performance/ledger")
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
        return api_error(
            en="No trade history found",
            kr="거래 이력이 없습니다.",
            code="PERFORMANCE_NO_TRADES",
            status=404,
        )

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
