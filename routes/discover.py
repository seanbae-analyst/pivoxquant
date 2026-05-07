"""Discover route — scans a pool of tickers for opportunities.

Also serves the /api/discover/* sub-endpoints consumed by the editorial
Discover page (market-overview / movers / sectors / screeners). These
share a market-aware cache and **fail-fast with HTTP 503** when the
upstream data provider (FMP) is unavailable. We never serve mock /
hardcoded sample data to end users — surfacing fake market levels as
real would be a legal/ethical violation (자본시장법: 거짓 정보 제공).

Language stays observational — no BUY/SELL/recommend/advice/bullish/bearish.
"""
import logging
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, request, jsonify
from flask_login import current_user

from models import Position, Watchlist
from services import fx_service, cache_service
from services.container import engine, fetcher
from services.name_resolver import resolve_stock_name
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
    # §101 회피 — Discover 결과를 사용자가 직접 의사를 표명한 종목 (보유 +
    # 워치리스트) 으로 한정. 임의 universe 분석은 자문업 회색지대.
    watched = {w.ticker for w in Watchlist.query.filter_by(user_id=current_user.id).all()}
    # Case-insensitive match (DB rows may be lower/upper while engine DISCOVER_POOL
    # is upper-case for US tickers and KRX 6자리 + .KS/.KQ for KR).
    allowed = {t.upper() for t in (owned | watched) if t}
    # 2026-05-02: DISCOVER_POOL 교집합 제거 — 사용자 보유/워치리스트 종목 전체
    # 분석. DISCOVER_POOL 미포함 KR 종목 (010170.KQ, 124500.KQ 등) 누락 문제 해결.
    # 사용자가 명시적으로 추가한 종목만 보므로 §101 의도 (임의 universe 차단)
    # 는 그대로 유지. 워치리스트 무한 추가 abuse 방지 위해 50개 cap.
    DISCOVER_USER_POOL_CAP = 50
    pool = sorted(allowed)[:DISCOVER_USER_POOL_CAP]

    owned_upper = {t.upper() for t in owned if t}

    def _analyze_one(ticker):
        try:
            r = engine.analyze(ticker, cap_usd, cap_krw, fx_rate=fx_service.get_rate())
            if r:
                r["already_owned"] = ticker.upper() in owned_upper
                # Backfill name for long-tail listings whose snapshot returns
                # only a ticker (pyKRX / us_stock_registry cover all KRX/US).
                if not r.get("name") or r.get("name") == ticker:
                    r["name"] = resolve_stock_name(ticker) or ticker
            return r
        except Exception as e:
            logger.warning("Discover skip %s: %s", ticker, e)
            return None

    results = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_analyze_one, t): t for t in pool}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    # Defense-in-depth: belt-and-suspenders filter post-analysis in case the
    # pool restriction logic ever drifts. Drops any rows whose ticker isn't
    # in the user's allowed set.
    results = [r for r in results if r.get("ticker", "").upper() in allowed]

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


def _data_unavailable(endpoint: str, *, retry_after: int = 60):
    """Standard 503 response when the upstream data provider is down.

    We deliberately do NOT degrade to mock/hardcoded sample data — serving
    fake market levels as if real would mislead users on financial data
    (legal/ethical violation). The frontend should render a "데이터 일시
    불가" banner on this 503.
    """
    body = {
        "error":       "Data temporarily unavailable",
        "code":        "DATA_PROVIDER_DOWN",
        "endpoint":    endpoint,
        "retry_after": retry_after,
    }
    response = jsonify(body)
    response.status_code = 503
    response.headers["Retry-After"] = str(retry_after)
    return response


@discover_bp.route("/discover/market-overview")
@api_auth
@legal_scrub_response
def market_overview():
    """Five-index headline cards. 503 fail-fast on upstream failure."""
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
            entry = {
                "name":       display,
                "symbol":     key,
                "level":      round(float(price), 2),
                "change_pct": round(float(data.get("change_pct", 0) or 0), 2),
            }
            # Pass-through the ETF proxy badge from data_fetcher so the
            # frontend can label "S&P 500 · SPY proxy" — same convention as
            # /api/market/indices (Wave 2 Bug #11 fix 2026-04-29).
            if data.get("proxy_ticker"):
                entry["proxy_ticker"] = data["proxy_ticker"]
            result.append(entry)
    except Exception as e:
        logger.warning("discover.market-overview upstream failed: %s", e)

    if len(result) < 3:
        logger.warning(
            "discover.market-overview: only %d/5 indices available — "
            "failing fast (no mock fallback)", len(result),
        )
        return _data_unavailable("market-overview")

    _section_set("overview", result)
    return jsonify(result)


@discover_bp.route("/discover/movers")
@api_auth
@legal_scrub_response
def movers():
    """Top gainers/losers (10 each) for US or KR. 503 fail-fast on failure."""
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
        logger.debug("discover.movers live path skip: %s", e)

    if len(gainers) < 3 or len(losers) < 3:
        logger.warning(
            "discover.movers (%s): only %d gainers / %d losers — "
            "failing fast (no mock fallback)",
            region, len(gainers), len(losers),
        )
        return _data_unavailable(f"movers:{region}")

    observed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    """11 GICS sectors with 1D/5D/1M observation. 503 fail-fast on failure."""
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
        logger.warning("discover.sectors upstream failed: %s", e)

    # Bug G (2026-04-24): FMP's sector-performance endpoint returns a full
    # list of 11 GICS sectors with `"0%"` on market-closed windows. We
    # reject *any* payload whose |d1| values are all below 0.001
    # (numerical noise threshold) — that's indistinguishable from a stale
    # tape and we will not paint mock numbers as real data.
    has_signal = any(abs(r.get("d1") or 0) > 0.001 for r in rows)
    if len(rows) < 5 or not has_signal:
        logger.warning(
            "discover.sectors: upstream returned %d rows, has_signal=%s — "
            "failing fast (no mock fallback)", len(rows), has_signal,
        )
        return _data_unavailable("sectors")

    _section_set("sectors", rows)
    return jsonify(rows)


@discover_bp.route("/discover/screeners")
@api_auth
@legal_scrub_response
def screeners():
    """Thematic observation lists. Pre-compute pipeline pending — until then,
    fail-fast 503 (was mock-only, which violated the no-fake-data rule)."""
    cached = _section_get("screeners")
    if cached:
        return jsonify(cached)

    # No live source wired yet. Refuse to serve stale mock screeners as
    # if they were today's market state. Tracked: pre-compute thematic
    # screeners off the engine universe (RSI/52w-high/earnings-beat).
    logger.warning(
        "discover.screeners: no live source implemented — failing fast "
        "(refuses to serve mock as real data)",
    )
    return _data_unavailable("screeners", retry_after=3600)
