"""Quant signal routes: short interest, insider transactions, and behavioral
& microstructure models (Disposition Effect, Order Flow Imbalance, Sentiment
Divergence, Anchoring Bias, Cross-Sectional Herding Intensity).

Split from routes/quant.py (Wave 11 SRP refactor).
All URL paths preserved exactly (`/api/signals/...`). No behaviour change.
"""

import logging
import time as _time

import numpy as np
from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.access_guard import access_denied_response, is_user_allowed_ticker
from services.error_responses import api_error
from services.name_resolver import resolve_stock_name
from .decorators import api_auth, legal_scrub_response
from .quant_helpers import (
    DISCLAIMERS,
    _bounded_set,
    _get_ohlcv,
    _is_kr_ticker,
    _ticker_validate,
    add_disclaimer,
)

logger = logging.getLogger(__name__)

signals_quant_bp = Blueprint("signals_quant", __name__, url_prefix="/api")


def _kr_unsupported(ticker):
    """Clean "Korean stocks not supported" response for US-only data models.

    The behavioral / microstructure models (disposition, OFI, anchoring,
    sentiment-divergence) source from FMP/Alpaca which only cover US
    listings. A KR ticker (e.g. 005930.KS) passes _ticker_validate now,
    so reject it here with a 422 rather than letting it fall through to a
    confusing "insufficient price history" 404. Mirrors the KR-aware
    messaging pattern used elsewhere.
    """
    return api_error(
        en="Korean stocks are not supported by this signal.",
        kr="이 시그널은 한국 종목을 지원하지 않습니다 (미국 상장 종목만 가능).",
        code="SIGNAL_QUANT_KR_UNSUPPORTED",
        status=422,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Short Interest Signal
# ─────────────────────────────────────────────────────────────────────────────

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


@signals_quant_bp.route("/signals/short-interest/<ticker>")
@api_auth
@legal_scrub_response
def short_interest_signal(ticker):
    """Short interest signal for a single ticker.

    Returns current short data, historical chart data, directional signal,
    and short pressure condition analysis.
    """
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 10:
        return api_error(
            en="Invalid ticker",
            kr="유효하지 않은 종목 코드입니다.",
            code="SIGNAL_QUANT_INVALID_INPUT",
            status=400,
        )

    # §101 회피 — per-ticker 분석은 보유/관심 종목으로 한정 (임의 종목 분석 노출 차단).
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

    # per-ticker cache
    now = _time.time()
    cache_entry = _si_cache.get(ticker)
    if cache_entry and now - cache_entry["ts"] < _SI_CACHE_TTL:
        return jsonify(cache_entry["data"])

    from services.data import fmp as fmp

    records = fmp.get_short_interest(ticker)
    if not records:
        return api_error(
            en=f"No short interest data for {ticker}",
            kr=f"{ticker} 종목의 공매도 데이터가 없습니다.",
            code="SIGNAL_QUANT_NOT_FOUND",
            status=404,
        )

    quote = fmp.get_quote(ticker)

    result = _compute_short_signal(records, quote)
    if not result:
        return api_error(
            en="Could not compute short interest signal",
            kr="공매도 시그널을 계산할 수 없습니다.",
            code="SIGNAL_QUANT_COMPUTATION_FAILED",
            status=500,
        )

    payload = {"ticker": ticker, "name": resolve_stock_name(ticker) or ticker, **result}
    add_disclaimer(payload, "indicator")

    _bounded_set(_si_cache, ticker, {"data": payload, "ts": now})
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Insider Transaction Signal
# ─────────────────────────────────────────────────────────────────────────────

def _compute_insider_signal(transactions):
    """Compute insider sentiment summary and signal strength from FMP data.

    Args:
        transactions: list of dicts from FMP /insider-trading/search endpoint

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
        # /insider-trading/search returns correctly-spelled "acquisitionOrDisposition";
        # the legacy /insider-trading path used the misspelled "acquistionOrDisposition".
        # Read both so classification is robust across FMP endpoint versions.
        acq_disp = (tx.get("acquisitionOrDisposition")
                    or tx.get("acquistionOrDisposition") or "").upper()

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


@signals_quant_bp.route("/signals/insider/<ticker>")
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
        return api_error(
            en="Invalid ticker format",
            kr="유효하지 않은 종목 코드 형식입니다.",
            code="SIGNAL_QUANT_INVALID_INPUT",
            status=400,
        )

    # §101 회피 — per-ticker 분석은 보유/관심 종목으로 한정.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

    # Korean tickers not supported for insider data (SEC/FMP only)
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return api_error(
            en="Insider data not available for Korean stocks",
            kr="국내 종목은 내부자 거래 데이터를 제공하지 않습니다.",
            code="SIGNAL_QUANT_INVALID_INPUT",
            status=400,
        )

    from services.data import fmp as fmp_service

    raw = fmp_service.get_insider_trades(ticker, limit=50)
    if raw is None:
        return api_error(
            en="Failed to fetch insider data (API unavailable)",
            kr="내부자 거래 데이터를 가져올 수 없습니다 (API 일시 장애).",
            code="SIGNAL_QUANT_RATE_LIMITED",
            status=503,
        )

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


# ─────────────────────────────────────────────────────────────────────────────
# Behavioral & Microstructure Signal Models
# ─────────────────────────────────────────────────────────────────────────────

_signal_cache: dict = {}  # {f"{endpoint}:{ticker}": {"data": ..., "ts": ...}}
_SIGNAL_CACHE_TTL = 300  # 5 minutes


@signals_quant_bp.route("/signals/disposition/<ticker>")
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
    if _is_kr_ticker(ticker):
        return _kr_unsupported(ticker)

    # §101 회피 — per-ticker 분석은 보유/관심 종목으로 한정.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

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
        return api_error(
            en="Volume data unavailable",
            kr="거래량 데이터가 없습니다.",
            code="SIGNAL_QUANT_INSUFFICIENT_DATA",
            status=404,
        )

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


@signals_quant_bp.route("/signals/ofi/<ticker>")
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
    if _is_kr_ticker(ticker):
        return _kr_unsupported(ticker)

    # §101 회피 — per-ticker 분석은 보유/관심 종목으로 한정.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

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
        return api_error(
            en="OHLCV data incomplete",
            kr="OHLCV 데이터가 불완전합니다.",
            code="SIGNAL_QUANT_INSUFFICIENT_DATA",
            status=404,
        )

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


@signals_quant_bp.route("/signals/sentiment-divergence/<ticker>")
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
    if _is_kr_ticker(ticker):
        return _kr_unsupported(ticker)

    # §101 회피 — per-ticker 분석은 보유/관심 종목으로 한정.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

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
        return api_error(
            en="Insufficient data for requested window",
            kr="요청한 윈도우에 대한 데이터가 부족합니다.",
            code="SIGNAL_QUANT_INSUFFICIENT_DATA",
            status=400,
        )

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


@signals_quant_bp.route("/signals/anchoring/<ticker>")
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
    if _is_kr_ticker(ticker):
        return _kr_unsupported(ticker)

    # §101 회피 — per-ticker 분석은 보유/관심 종목으로 한정.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

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
        return api_error(
            en="Volume data unavailable",
            kr="거래량 데이터가 없습니다.",
            code="SIGNAL_QUANT_INSUFFICIENT_DATA",
            status=404,
        )

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


@signals_quant_bp.route("/signals/herding")
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
        return api_error(
            en="Market data unavailable",
            kr="시장 데이터를 가져올 수 없습니다.",
            code="SIGNAL_QUANT_RATE_LIMITED",
            status=503,
        )

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
        return api_error(
            en="Insufficient stock data for herding analysis",
            kr="허딩 분석에 필요한 종목 데이터가 부족합니다.",
            code="SIGNAL_QUANT_INSUFFICIENT_DATA",
            status=503,
        )

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
