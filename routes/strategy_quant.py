"""Strategy-level quant routes: VIX, cross-asset momentum, stat-arb,
CAN SLIM screener, interest-rate regime.

Split from routes/quant.py (Wave 11 SRP refactor).
All URL paths preserved exactly (`/api/...`). No behaviour change.
"""

import logging
import time as _time

from flask import Blueprint, jsonify
from flask_login import current_user

from .decorators import api_auth, legal_scrub_response
from .quant_helpers import _bounded_set, add_disclaimer

logger = logging.getLogger(__name__)

strategy_quant_bp = Blueprint("strategy_quant", __name__, url_prefix="/api")

_ca_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_sa_cache: dict = {}  # {user_id: {"data": ..., "ts": ...}}
_ir_regime_cache: dict = {}
_IR_REGIME_CACHE_TTL = 3600  # 1 hour


@strategy_quant_bp.route("/vix-strategy")
@api_auth
@legal_scrub_response
def vix_strategy():
    from services.quant.models import VIXStrategy
    result = VIXStrategy.analyze()
    if result:
        return jsonify(result)
    return jsonify({"error": "VIX data unavailable"}), 500


@strategy_quant_bp.route("/cross-asset")
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


@strategy_quant_bp.route("/stat-arb")
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


@strategy_quant_bp.route("/screener/canslim/<ticker>")
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

    # Float shares + sector from FMP profile
    float_shares = None
    sector = None
    try:
        profile = fmp_svc.get_profile(ticker)
        if profile:
            float_shares = profile.get("floatShares") or profile.get("sharesFloat")
            sector = profile.get("sector") or None  # e.g. "Technology"
    except Exception:
        logger.debug("silent-fallback: canslim_screener", exc_info=True)
        pass

    # Market regime from RegimeSwitching.
    # 2026-05-17 P1-01: regime MUST be derived from a market *index*, not from
    # the candidate ticker's own price series. Passing per-ticker closes here
    # made every uptrending stock auto-pass M, defeating the point of the M
    # filter (the M in CAN SLIM is explicitly "Market direction", not "stock
    # direction"). Use ^GSPC (S&P 500) for US tickers and ^KS11 (KOSPI) for
    # Korean tickers.
    regime = None
    try:
        is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")
        market_index = "^KS11" if is_kr else "^GSPC"
        market_hist = fetcher.get_price_history(market_index, period="1y")
        if market_hist is not None and not market_hist.empty and len(market_hist) >= 80:
            market_closes = market_hist["Close"].values.astype(float)
            rs = RegimeSwitching.analyze(list(market_closes))
            if rs:
                regime = rs.get("regime")
    except Exception:
        logger.debug("silent-fallback: canslim_screener_market_regime", exc_info=True)
        pass

    result = CANSLIMScreener.score(ticker, closes, volumes, fundamentals, regime, float_shares=float_shares, sector=sector)

    payload = {
        "ok": True,
        **result,
    }
    add_disclaimer(payload, "indicator")
    return jsonify(payload)


@strategy_quant_bp.route("/regime/interest-rate")
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
