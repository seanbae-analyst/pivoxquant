"""Shared helpers for the quant_* blueprints.

These helpers are imported by routes/signals_quant.py, routes/risk_quant.py,
routes/performance_quant.py, routes/tools_quant.py, and routes/strategy_quant.py.

History: extracted from routes/quant.py (3464-line god-file) during
Wave 11 SRP split. Behaviour is byte-identical to the original.
"""

import json
import logging
import math

import numpy as np
from flask_login import current_user

from services.name_resolver import canonical_display_name

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Legal Disclaimers (YELLOW endpoints)
# ─────────────────────────────────────────────────────────────────────────────

DISCLAIMERS = {
    # 2026-05-17 P2-04: KO + EN bilingual per CLAUDE.md domestic-first rule.
    # Korean users are the primary audience; English suffix supports overseas
    # beta testers + audit/legal review.
    "simulation": (
        "포트폴리오 시뮬레이션 — 교육 목적의 참고 자료입니다. "
        "투자자문 또는 포트폴리오 배분 권유가 아닙니다. "
        "Portfolio simulation for educational reference only. "
        "Does not constitute investment advice or portfolio allocation guidance."
    ),
    "indicator": (
        "분석 지표 — 정보 제공 목적만 입니다. "
        "특정 매매 행위를 권유하는 것이 아닙니다. "
        "Market analysis indicator for informational purposes only. "
        "Does not suggest any specific trading action."
    ),
    "analysis": (
        "과거 데이터와 수학적 모델에 기반한 분석입니다. "
        "과거 성과는 미래 수익을 보장하지 않습니다. "
        "Analysis based on historical data and mathematical models. "
        "Past performance does not guarantee future results."
    ),
    "tax": (
        "세금 정보는 추정치이며 참고용입니다. "
        "실제 세무 자문은 공인 세무사와 상담하시기 바랍니다. "
        "Tax information is estimated and for reference only. "
        "Consult a licensed tax professional for actual tax advice."
    ),
    "regime": (
        "거시 국면 분류 및 과거 섹터 성과 데이터로, 정보 제공 목적입니다. "
        "특정 섹터를 권유하지 않습니다. "
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
# memory steady.
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


# ─────────────────────────────────────────────────────────────────────────────
# Distribution helpers (used by risk_quant)
# ─────────────────────────────────────────────────────────────────────────────

def _safe_skew(arr):
    """Compute skewness without scipy dependency."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio loaders (used by risk_quant + performance_quant + tools_quant)
# ─────────────────────────────────────────────────────────────────────────────

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

    # Wave H-4 P0 (2026-05-18): pre-fix was serial fetcher.get_price_history
    # per position — N positions × ~800ms FMP RTT = 10 positions ≈ 8s wall.
    # Every risk_quant / performance_quant endpoint paid this cost. Now
    # parallel via ThreadPoolExecutor (PR #395 signal_detail timeout 패턴
    # mirror). Bounded max_workers to 8 — typical Pro portfolio <30 positions
    # but FMP per-second limit + Railway dyno CPU make 8 a safe upper.
    import concurrent.futures
    ticker_returns: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()
    tickers = [it["ticker"] for it in items]

    def _fetch_one(tk: str):
        try:
            return tk, fetcher.get_price_history(tk, period=period)
        except Exception:
            return tk, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(tickers)))) as ex:
        for tk, hist in ex.map(_fetch_one, tickers):
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
            ticker_returns[tk] = date_ret

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


# ─────────────────────────────────────────────────────────────────────────────
# Signal helpers (used by signals_quant for behavioral models)
# ─────────────────────────────────────────────────────────────────────────────

def _ticker_validate(ticker):
    """Validate and normalize a ticker symbol. Returns (ticker, error_response)."""
    import re as _re
    from flask import jsonify
    ticker = (ticker or "").upper().strip()
    if not ticker or not _re.match(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$", ticker):
        return None, (jsonify({"error": "Invalid ticker format"}), 400)
    return ticker, None


def _get_ohlcv(ticker, period="1y"):
    """Fetch OHLCV data for a ticker. Returns (opens, closes, volumes, error_resp)."""
    from flask import jsonify
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


# ─────────────────────────────────────────────────────────────────────────────
# Common constants
# ─────────────────────────────────────────────────────────────────────────────

_VALID_PERIODS = {"3mo", "6mo", "1y", "2y"}
_RISK_FREE = 0.045  # annualized risk-free rate
