"""Discover route — scans a pool of tickers for opportunities.

Also serves the /api/discover/* sub-endpoints consumed by the editorial
Discover page (market-overview / movers / sectors / screeners). These
share a 2h cache and degrade to the mock fallback in
``services.mock_data.discover_fallback`` when FMP hits 402/5xx.

Language stays observational — no BUY/SELL/recommend/advice/bullish/bearish.
"""
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, request, jsonify
from flask_login import current_user

from models import Position
from services import fx_service, cache_service
from services.container import engine, fetcher
from services.name_resolver import resolve_stock_name
from services.mock_data import discover_fallback as mock
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

discover_bp = Blueprint("discover", __name__, url_prefix="/api")


@discover_bp.route("/discover")
@api_auth
@legal_scrub_response
def discover():
    now = time.time()
    uid = current_user.id
    force = request.args.get("force") == "1"
    uc = cache_service.discover_cache.get(uid, {"data": None, "ts": 0})
    if not force and uc["data"] and now - uc["ts"] < cache_service.DISCOVER_TTL:
        return jsonify({"results": uc["data"], "cached": True,
                        "cached_at": datetime.fromtimestamp(uc["ts"]).isoformat()})

    cap_usd = current_user.available_capital or 0.0
    cap_krw = getattr(current_user, "available_capital_krw", 0.0) or 0.0
    owned = {p.ticker for p in Position.query.filter_by(user_id=current_user.id).all()}
    pool = engine.DISCOVER_POOL

    def _analyze_one(ticker):
        try:
            r = engine.analyze(ticker, cap_usd, cap_krw, fx_rate=fx_service.get_rate())
            if r:
                r["already_owned"] = ticker in owned
                # Backfill name for long-tail listings whose snapshot returns
                # only a ticker (pyKRX / us_stock_registry cover all KRX/US).
                if not r.get("name") or r.get("name") == ticker:
                    r["name"] = resolve_stock_name(ticker) or ticker
            return r
        except Exception as e:
            logger.warning(f"Discover skip {ticker}: {e}")
            return None

    results = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_analyze_one, t): t for t in pool}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    order = {"POSITIVE": 0, "NEUTRAL": 1, "NEGATIVE": 2}
    results.sort(key=lambda x: (order.get(x.get("signal", ""), 9), -x.get("priority", 0)))
    cache_service.discover_cache[uid] = {"data": results, "ts": now}
    return jsonify({"results": results, "cached": False})


# ── Section endpoints ─────────────────────────────────────────────

# Market-aware cache: intraday we tighten to 10min so movers/sectors
# visibly refresh while users watch; off-hours we hold 2h so we don't
# churn FMP for data that isn't moving.
_section_cache: dict = {}          # key -> {"ts": float, "data": ...}
_SECTION_TTL = 7200                # off-hours fallback — see _section_ttl()


def _section_ttl() -> int:
    try:
        from services.cache_ttl import discover_ttl
        return discover_ttl()
    except Exception:
        return _SECTION_TTL


def _section_get(key: str):
    e = _section_cache.get(key)
    if e and time.time() - e["ts"] < _section_ttl():
        return e["data"]
    return None


def _section_set(key: str, data) -> None:
    _section_cache[key] = {"ts": time.time(), "data": data}


@discover_bp.route("/discover/market-overview")
@api_auth
@legal_scrub_response
def market_overview():
    """Five-index headline cards. Falls back to static mock on upstream failure."""
    cached = _section_get("overview")
    if cached:
        return jsonify(cached)

    result = []
    try:
        macro = fetcher.get_enhanced_macro()
        for key, display in [("sp500", "S&P 500"), ("nasdaq", "Nasdaq"),
                             ("dow", "Dow"), ("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
            data = macro.get(key) or {}
            price = data.get("price")
            if price is None:
                continue
            result.append({
                "name":       display,
                "symbol":     key,
                "level":      round(float(price), 2),
                "change_pct": round(float(data.get("change_pct", 0) or 0), 2),
            })
    except Exception as e:
        logger.warning(f"discover.market-overview upstream failed: {e}")

    if len(result) < 3:
        logger.info("FMP rate limit or empty overview — returning cached/mock fallback")
        # Flag mock rows so the frontend can surface a "stale data" banner
        # instead of silently showing 2024 snapshots.
        result = [{**r, "is_mock": True} for r in mock.MARKET_OVERVIEW]

    _section_set("overview", result)
    return jsonify(result)


@discover_bp.route("/discover/movers")
@api_auth
@legal_scrub_response
def movers():
    """Top gainers/losers (10 each) for US or KR. Mock fallback on failure."""
    region = (request.args.get("region") or "us").lower()
    if region not in ("us", "kr"):
        region = "us"

    cache_key = f"movers:{region}"
    cached = _section_get(cache_key)
    if cached:
        return jsonify(cached)

    # Primary path: the quant engine already scans a universe — reuse its
    # per-ticker %change snapshot when available (no extra FMP calls).
    gainers: list[dict] = []
    losers: list[dict] = []
    try:
        uid = current_user.id
        uc = cache_service.discover_cache.get(uid)
        rows = (uc or {}).get("data") or []
        is_kr = region == "kr"
        filtered = [r for r in rows
                    if bool(r.get("is_korean")) == is_kr
                    and r.get("change_pct") is not None
                    and r.get("price") is not None]
        filtered.sort(key=lambda r: r.get("change_pct", 0), reverse=True)
        def _fmt(r):
            return {
                "ticker":     r.get("ticker", ""),
                "name":       r.get("name") or r.get("ticker", ""),
                "price":      float(r.get("price") or 0),
                "change_pct": float(r.get("change_pct") or 0),
            }
        gainers = [_fmt(r) for r in filtered[:10]]
        losers  = [_fmt(r) for r in list(reversed(filtered))[:10]]
    except Exception as e:
        logger.debug(f"discover.movers live path skip: {e}")

    if len(gainers) < 3 or len(losers) < 3:
        logger.info("FMP rate limit — returning mock movers fallback")
        if region == "us":
            gainers = [{**r, "is_mock": True} for r in mock.US_GAINERS]
            losers  = [{**r, "is_mock": True} for r in mock.US_LOSERS]
        else:
            gainers = [{**r, "is_mock": True} for r in mock.KR_GAINERS]
            losers  = [{**r, "is_mock": True} for r in mock.KR_LOSERS]

    observed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "region": region,
        "gainers": gainers,
        "losers": losers,
        "observed_at": observed_at,
    }
    _section_set(cache_key, payload)
    return jsonify(payload)


@discover_bp.route("/discover/sectors")
@api_auth
@legal_scrub_response
def sectors():
    """11 GICS sectors with 1D/5D/1M observation. Mock on upstream failure."""
    cached = _section_get("sectors")
    if cached:
        return jsonify(cached)

    rows: list[dict] = []
    try:
        live = fetcher.get_sector_performance() or []
        # fetcher returns {sector, changesPercentage:"1.23%"} — only 1D there.
        # Emit d1 from that; d5/m1 placeholder until a richer source is wired.
        for r in live:
            sector = r.get("sector")
            if not sector:
                continue
            pct_str = (r.get("changesPercentage") or "0%").rstrip("%")
            try:
                d1 = float(pct_str)
            except Exception:
                d1 = 0.0
            rows.append({
                "sector": sector,
                "d1":     round(d1, 2),
                "d5":     round(d1 * 2.5, 2),   # coarse scaled placeholder
                "m1":     round(d1 * 5.0, 2),
            })
    except Exception as e:
        logger.warning(f"discover.sectors upstream failed: {e}")

    if len(rows) < 5:
        logger.info("FMP rate limit — returning mock sectors fallback")
        rows = list(mock.SECTORS)

    _section_set("sectors", rows)
    return jsonify(rows)


@discover_bp.route("/discover/screeners")
@api_auth
@legal_scrub_response
def screeners():
    """Thematic observation lists. Mock-only for now (pre-compute TODO)."""
    cached = _section_get("screeners")
    if cached:
        return jsonify(cached)

    payload = {
        "oversold_rsi":   list(mock.OVERSOLD_RSI),
        "highs_52w":      list(mock.HIGHS_52W),
        "earnings_beats": list(mock.EARNINGS_BEATS),
    }
    _section_set("screeners", payload)
    return jsonify(payload)
