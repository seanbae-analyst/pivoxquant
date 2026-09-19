"""Market data routes: overview, macro, sectors, news, prices, chart, etc."""
from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from security import general_rate_limit
from services import fx_service
from services.error_responses import api_error
from services.market_display import (
    market_data_display_disabled_error,
    market_data_display_enabled,
)
from services.name_resolver import resolve_stock_name
from services.ticker_normalizer import normalize_ticker
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

market_bp = Blueprint("market", __name__, url_prefix="/api")

# Index-snapshot machinery lives in services/data/indices.py — 659 lines of
# upstream fetching and caching that had no business in a routing module.
# `_indices_cache` is imported by name and shared by identity: readers here
# mutate and read the same dict the service writes.
from services.data.indices import (  # noqa: E402
    _indices_cache,
    _indices_ttl,
    warm_indices_cache,
)

_macro_cache: dict = {"data": None, "ts": 0.0}





@market_bp.route("/search")
@api_auth
def search_stocks():
    """Fuzzy stock search — supports company names, partial tickers, Korean names.
    Uses FMP search API for US + local KOREAN_NAMES registry for KR stocks."""
    query = (request.args.get("q") or "").strip()
    # Cap query length before it touches any path (KR registry, 6-digit
    # passthrough, FMP HTTP). A caller (or a hostile client) could otherwise
    # send a multi-KB string straight to FMP's API. 50 chars covers any real
    # company name or ticker; longer input is truncated, not rejected, so the
    # search box stays forgiving.
    if len(query) > 50:
        query = query[:50]
    # Client-supplied limit (Cmd+K palette asks for 10). Clamp so a malformed
    # or hostile value can't blow the response size.
    try:
        limit = int(request.args.get("limit", "15"))
    except (TypeError, ValueError):
        limit = 15
    limit = max(1, min(limit, 25))
    if len(query) < 1:
        return jsonify({"results": []})
    ql = query.lower()  # used by US fallback matcher below

    results = []
    seen = set()

    # 1) Search Korean stock registry (top ~250 KOSPI/KOSDAQ stocks)
    from services import kr_stock_registry
    for hit in kr_stock_registry.search(query, limit=15):
        if hit["ticker"] not in seen:
            results.append(hit)
            seen.add(hit["ticker"])

    # 1b) Allow raw 6-digit codes as a passthrough (any KRX ticker, even
    # if not in the static registry — KIS will resolve at lookup time).
    # Use normalize_ticker so 035760 (CJ ENM, KOSDAQ) routes to .KQ.
    bare = query.strip()
    if bare.isdigit() and len(bare) == 6:
        candidate = normalize_ticker(bare)
        if candidate and candidate not in seen:
            results.append({
                "ticker":    candidate,
                # Resolve the company name (삼성전자) for 6-digit codes outside
                # the curated registry too — previously echoed the bare ticker
                # as the name → naked code in search results (2026-05-24).
                "name":      resolve_stock_name(candidate) or candidate,
                "exchange":  "KOSDAQ" if candidate.endswith(".KQ") else "KOSPI",
                "currency":  "KRW",
                "is_korean": True,
            })
            seen.add(candidate)

    # 2) FMP search API for US/global stocks
    # NOTE: FMP's v3 endpoint (`/api/v3/search`) was deprecated 2025-08-31.
    # It still returns HTTP 200 but the body is `{"Error Message": "Legacy
    # Endpoint ..."}` — the old `isinstance(parsed, list)` guard silently
    # filtered that out, so search was completely broken for US/global
    # tickers. Switched to the stable endpoint (`/stable/search-symbol`),
    # which remains a `list[dict]` on success. The stable response schema
    # keeps the same keys we consume here (symbol / name / exchange /
    # currency / exchangeShortName) so downstream parsing is unchanged.
    import os
    fmp_key = os.environ.get("FMP_API_KEY", "")
    fmp_ok = False
    if fmp_key:
        try:
            import requests as _req
            # Pass query/key as params so requests URL-encodes them. A raw
            # f-string let a query containing '&' / '=' / '#' inject or
            # clobber FMP parameters (e.g. q="x&apikey=...") — params={} is
            # the safe boundary. The apikey is never echoed in our response.
            resp = _req.get(
                "https://financialmodelingprep.com/stable/search-symbol",
                params={"query": query, "limit": 10, "apikey": fmp_key},
                timeout=5,
            )
            if resp.status_code == 200:
                try:
                    parsed = resp.json()
                except Exception as e:
                    logger.warning("FMP search JSON parse failed: %s", e)
                    parsed = None
                # Stable returns list[dict] on success. Legacy v3 would
                # have returned {"Error Message": ...}; guard both.
                if isinstance(parsed, list) and parsed:
                    added = 0
                    for item in parsed:
                        sym = item.get("symbol", "")
                        if sym and sym not in seen:
                            results.append({
                                "ticker": sym,
                                "name": item.get("name", sym),
                                "exchange": item.get("exchange")
                                    or item.get("exchangeShortName")
                                    or item.get("stockExchange", ""),
                                "currency": item.get("currency", "USD"),
                                "is_korean": False,
                            })
                            seen.add(sym)
                            added += 1
                    if added > 0:
                        fmp_ok = True
                elif isinstance(parsed, dict) and parsed.get("Error Message"):
                    logger.warning(
                        f"FMP search returned error payload: {parsed.get('Error Message')}"
                    )
            else:
                logger.warning("FMP search HTTP %s", resp.status_code)
        except Exception as e:
            logger.warning("FMP search failed: %s", e)

    # 3) Fallback: match popular US tickers locally when FMP unavailable
    if not fmp_ok:
        _US_POPULAR = {
            "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "GOOGL": "Alphabet Inc.",
            "AMZN": "Amazon.com Inc.", "NVDA": "NVIDIA Corp.", "META": "Meta Platforms Inc.",
            "TSLA": "Tesla Inc.", "NFLX": "Netflix Inc.", "AMD": "Advanced Micro Devices",
            "INTC": "Intel Corp.", "AVGO": "Broadcom Inc.", "CRM": "Salesforce Inc.",
            "ORCL": "Oracle Corp.", "QCOM": "Qualcomm Inc.", "ADBE": "Adobe Inc.",
            "COST": "Costco Wholesale", "PEP": "PepsiCo Inc.", "KO": "The Coca-Cola Co.",
            "DIS": "The Walt Disney Co.", "PYPL": "PayPal Holdings",
            "BA": "Boeing Co.", "V": "Visa Inc.", "MA": "Mastercard Inc.",
            "JPM": "JPMorgan Chase", "BAC": "Bank of America",
            "WMT": "Walmart Inc.", "JNJ": "Johnson & Johnson",
            "PG": "Procter & Gamble", "UNH": "UnitedHealth Group",
            "XOM": "Exxon Mobil Corp.", "CVX": "Chevron Corp.",
            "SPY": "SPDR S&P 500 ETF", "QQQ": "Invesco QQQ Trust",
            "PLTR": "Palantir Technologies", "COIN": "Coinbase Global",
            "SOFI": "SoFi Technologies", "UBER": "Uber Technologies",
            "SNOW": "Snowflake Inc.", "SQ": "Block Inc.",
        }
        for sym, name_us in _US_POPULAR.items():
            if sym in seen:
                continue
            if ql in sym.lower() or ql in name_us.lower():
                results.append({
                    "ticker": sym, "name": name_us,
                    "exchange": "NASDAQ", "currency": "USD", "is_korean": False,
                })
                seen.add(sym)

    return jsonify({"results": results[:limit]})


@market_bp.route("/market/fx")
@api_auth
def get_fx_rates():
    """Return the live USD/KRW exchange rate.

    NOT gated by MARKET_DATA_DISPLAY_ENABLED — deliberately. The rate comes
    from open.er-api.com, whose terms permit commercial use, and a
    multi-currency COST basis cannot be added up without it. (Attribution is
    the frontend's job.)

    The backend scheduler refreshes this value every 1 minute, so the
    frontend can poll at 30s intervals for near-realtime cross-currency
    math (portfolio KRW equivalence, target allocation rebalancing, etc.).

    Response:
        ok (bool): Always true when served.
        usd_krw (float): Most recent USD/KRW rate (rounded to 2 decimals).
        last_updated (str|float): ISO-8601 UTC timestamp of the last
            successful fetch (falls back to unix epoch 0 when never fetched).
        age_seconds (int): Seconds since the last successful fetch (-1 if never).
        is_stale (bool): True when the rate is older than 10 minutes —
            frontend can display a warning indicator.
        stale (bool): Deprecated alias for is_stale (kept for compatibility).
        ttl_seconds (int): Expected refresh cadence hint for clients (60s).
    """
    try:
        # Opportunistic refresh — cheap (5s internal short-cache).
        fx_service.refresh()
        ts = fx_service.last_updated()
        age = int(_time.time() - ts) if ts else -1
        stale = fx_service.is_stale()

        # ISO-8601 for easy frontend parsing; raw unix ts kept available
        # via age_seconds. Emit epoch 0 as empty-string sentinel only when
        # truly never fetched.
        if ts:
            last_updated_iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            last_updated_iso = None

        return jsonify({
            "ok": True,
            "usd_krw": fx_service.get_rate(),
            "last_updated": last_updated_iso,
            "last_updated_ts": ts,
            "age_seconds": age,
            "is_stale": stale,
            "stale": stale,  # deprecated — remove after frontend migration
            "ttl_seconds": 60,
        })
    except Exception as e:
        logger.error("FX endpoint error: %s", e)
        return api_error(
            en="Unable to fetch FX rate",
            kr="환율 정보를 가져올 수 없습니다.",
            code="MARKET_FX_UNAVAILABLE",
            status=500,
        )


_EARNINGS_ETF_TICKERS = ('TSLL', 'ETHU', 'SPY', 'QQQ', 'TLT', 'GLD', 'USO', 'UUP')














@market_bp.route("/market/indices")
@api_auth
@legal_scrub_response
def market_indices():
    """Headline indices for the ``/market`` tab.

    Query params:
        region: "us" (default) or "kr"

    Response: list of index snapshots with
        ticker, name, level, change_1d_pct, range_52w:[lo,hi],
        sparkline_30d:[...], observed_at, is_stale

    Cache-key version bump: the v1 key may contain an empty-array payload
    produced by the regressed ``ama.get_quote``-only snapshot (commit
    80c7d26). Versioning the key guarantees we bypass any poisoned entry
    instead of waiting for the TTL to expire.
    """
    # MARKET_DATA_DISPLAY_ENABLED (config.py): index levels, 52-week ranges
    # and sparklines ARE the vendor payload — there is no cost-basis version
    # of this response, so the route refuses rather than degrades.
    if not market_data_display_enabled():
        return market_data_display_disabled_error()

    region = (request.args.get("region") or "us").lower()
    if region not in ("us", "kr"):
        region = "us"

    cache_key = f"{region}_v2"
    entry = _indices_cache.get(cache_key)
    now = _time.time()
    if entry and now - entry["ts"] < _indices_ttl():
        return jsonify(entry["data"])

    # Cache miss / stale — refresh through the shared warm path so the
    # request and the scheduler job share one upstream code path.
    warm_indices_cache(region, force=True)
    entry = _indices_cache.get(cache_key)
    return jsonify(entry["data"] if entry else [])


# ─────────────────────────────────────────────────────────────────────
# Public, cache-only market snapshot for the UNAUTHENTICATED landing page.
#
# Why this exists (Bug #1 root fix):
#   The landing page ticker (frontend market-ticker.tsx) used to hardcode
#   KOSPI / KOSDAQ / S&P / NASDAQ / USDKRW / VIX snapshot values, which
#   guarantees staleness. The landing page is unauthenticated and cannot
#   call /api/market/indices (it sits behind @api_auth). This endpoint
#   gives the landing page a public, abuse-safe source.
#
# Hard rules baked in:
#   * NO @api_auth — must be reachable without a login.
#   * CACHE-ONLY — never triggers a synchronous KIS/FMP/Alpaca fetch.
#     It reads ONLY the in-process _indices_cache (populated as a
#     side-effect of authenticated /api/market/indices calls) and
#     fx_service (refreshed by the background scheduler tick). On a
#     cache miss it returns 200 with whatever it has (possibly empty),
#     each item flagged is_stale — never a paid-API call from an
#     unauthenticated path (abuse + cost protection).
#   * @general_rate_limit — per-IP budget, abuse defense for a public route.
#   * §101 compliance — generalized macro data only (index levels, FX,
#     volatility). No individual-stock data, no specificity, no
#     recommendations. Index levels are general information published in
#     every news outlet.
#
# Cache-warming dependency (documented for the parent agent):
#   _indices_cache is filled by /api/market/indices, which runs whenever
#   ANY authenticated user opens the /market tab. fx_service is filled by
#   the background scheduler (refreshes USD/KRW every ~60s on app boot +
#   tick). So as long as the app has had at least one authenticated
#   /market visitor since boot, the index tiles are warm; FX is always
#   warm. If a deployment has zero authenticated traffic, the index
#   portion returns empty (200, is_stale implied by absence) until the
#   first /market visit. A dedicated scheduled cache-warm job for indices
#   would close that gap — see report. No new infra cost required; it
#   would reuse the existing APScheduler.
# ─────────────────────────────────────────────────────────────────────
@market_bp.route("/public/market-snapshot")
@general_rate_limit
def public_market_snapshot():
    """Public (no-auth), cache-only macro snapshot for the landing ticker.

    Returns generalized macro market data — index levels, FX, volatility —
    read straight from the in-process caches. Never performs a live
    upstream fetch (see module comment above).

    Response (always HTTP 200):
        {
          "ok": true,
          "items": [
            {
              "symbol": "^KS11",        # stable identifier
              "name": "KOSPI",          # display label
              "value": 7981.23,         # level / rate / VIX value
              "change_pct": 0.42,       # 1d % change (0.0 when unknown)
              "direction": "up",        # "up" | "down" | "flat"
              "is_stale": false,        # true when cache is cold/aged
              "observed_at": "2026-05-15T01:23:45Z",  # ISO-8601 UTC, or null
              "proxy_ticker": null      # ETF ticker if `value` is an ETF
                                        # proxy price (e.g. "SPY" for
                                        # ^GSPC). Capital-markets-law
                                        # disclosure (Bug #3, PR #343).
            },
            ...
          ],
          "generated_at": "2026-05-15T01:24:00Z",
          "cache_warm": true            # false ⇒ index cache cold (FX only)
        }

    Symbols emitted: ^KS11 (KOSPI), ^KQ11 (KOSDAQ), ^GSPC (S&P 500 via SPY
    proxy), ^IXIC (Nasdaq via QQQ proxy), ^VIX (volatility via VIXY proxy),
    USDKRW. Any symbol whose cache entry is missing is still emitted with
    value=null, is_stale=true so the frontend renders a stable row count.
    """
    # MARKET_DATA_DISPLAY_ENABLED (config.py): index levels and the VIX are
    # vendor quotes no matter how generalised — unauthenticated display is
    # still display. The USD/KRW row rides along in this payload, so the whole
    # endpoint refuses; the authenticated /api/market/fx stays available.
    if not market_data_display_enabled():
        return market_data_display_disabled_error()

    now = _time.time()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ttl = _indices_ttl()

    def _direction(change_pct) -> str:
        try:
            v = float(change_pct)
        except (TypeError, ValueError):
            return "flat"
        if v > 0.001:
            return "up"
        if v < -0.001:
            return "down"
        return "flat"

    # Map cache ticker -> (display name, proxy_ticker) for the symbols the
    # landing ticker needs. US entries live under cache_key "us_v2", KR
    # under "kr_v2" — the exact keys /api/market/indices writes.
    #
    # 2026-05-15 (Bug #3 + PR #343 regression on landing): the US index
    # values served here are ETF-proxy levels (SPY/QQQ/VIXY) — FMP $29
    # plan 402s on caret-prefixed index symbols. Without a `proxy_ticker`
    # field on the response, the landing ticker would render
    # "S&P 500 748.17" against the SPY price (real S&P 500 ≈ 5,700) — a
    # capital-markets-law misrepresentation risk for unauthenticated
    # visitors. We emit `proxy_ticker` so the frontend can render a "VIA
    # SPY" disclosure chip mirroring the dashboard top-ticker pattern
    # (PR #379). The ^IXIC display label is also corrected to "Nasdaq
    # 100" (QQQ tracks NASDAQ 100, not NASDAQ Composite — bare "NASDAQ"
    # was the same misrepresentation issue closed for /market in PR
    # #343, but the landing ticker was never re-aligned).
    _WANTED = [
        ("kr_v2", "^KS11",  "KOSPI",      None),
        ("kr_v2", "^KQ11",  "KOSDAQ",     None),
        ("kr_v2", "USDKRW", "USD / KRW",  None),
        ("us_v2", "^GSPC",  "S&P 500",    "SPY"),
        ("us_v2", "^IXIC",  "Nasdaq 100", "QQQ"),
        ("us_v2", "^VIX",   "VIX",        "VIXY"),
    ]

    # Pull each region's cached list once. Cache-only: if absent or aged
    # past TTL we simply treat it as cold — we do NOT recompute.
    region_data: dict = {}
    region_fresh: dict = {}
    for region_key in ("us_v2", "kr_v2"):
        entry = _indices_cache.get(region_key)
        if entry and isinstance(entry.get("data"), list):
            by_ticker = {}
            for snap in entry["data"]:
                if isinstance(snap, dict) and snap.get("ticker"):
                    by_ticker[snap["ticker"]] = snap
            region_data[region_key] = by_ticker
            region_fresh[region_key] = (now - entry.get("ts", 0)) < ttl
        else:
            region_data[region_key] = {}
            region_fresh[region_key] = False

    items: list[dict] = []
    index_cache_warm = False
    for region_key, ticker, display, proxy_ticker in _WANTED:
        snap = region_data.get(region_key, {}).get(ticker)
        if snap is not None:
            index_cache_warm = True
            # is_stale: honor the snapshot's own flag, OR mark stale when
            # the region cache itself has aged past TTL.
            stale = bool(snap.get("is_stale")) or not region_fresh.get(region_key, False)
            change_pct = snap.get("change_1d_pct")
            items.append({
                "symbol": ticker,
                "name": display,
                "value": snap.get("level"),
                "change_pct": (
                    round(float(change_pct), 2) if change_pct is not None else None
                ),
                "direction": _direction(change_pct),
                "is_stale": stale,
                "observed_at": snap.get("observed_at"),
                "proxy_ticker": proxy_ticker,
            })
        else:
            # Cache miss for this symbol — emit a placeholder row so the
            # frontend keeps a stable layout. Never a live fetch.
            items.append({
                "symbol": ticker,
                "name": display,
                "value": None,
                "change_pct": None,
                "direction": "flat",
                "is_stale": True,
                "observed_at": None,
                "proxy_ticker": proxy_ticker,
            })

    # USD/KRW: fx_service is refreshed by the background scheduler, so it is
    # effectively always warm even with zero authenticated traffic. Prefer
    # it over the kr_v2 cache entry when available — it is the freshest
    # cache-resident source and still requires NO live fetch here.
    try:
        fx_rate = float(fx_service.get_rate() or 0) or None
    except Exception:
        fx_rate = None
    if fx_rate is not None:
        try:
            fx_ts = fx_service.last_updated()
        except Exception:
            fx_ts = None
        try:
            fx_stale = bool(fx_service.is_stale())
        except Exception:
            fx_stale = True
        fx_observed = (
            datetime.fromtimestamp(fx_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if fx_ts else None
        )
        # Replace the USDKRW row (sourced from kr_v2 above) with the
        # fresher fx_service value. Keep the kr_v2 change_pct if present.
        for it in items:
            if it["symbol"] == "USDKRW":
                kr_change = it.get("change_pct", 0.0)
                it.update({
                    "value": round(fx_rate, 2),
                    "is_stale": fx_stale,
                    "observed_at": fx_observed,
                    # change_pct only available from kr_v2 history; keep it.
                    "change_pct": kr_change,
                    "direction": _direction(kr_change),
                })
                break

    return jsonify({
        "ok": True,
        "items": items,
        "generated_at": now_iso,
        "cache_warm": index_cache_warm,
    })
