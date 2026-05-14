"""Market data routes: overview, macro, sectors, news, prices, chart, etc."""
from __future__ import annotations

import json
import logging
import time as _time
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Position, SignalCache
from security import general_rate_limit
from services import fx_service
from services.container import fetcher, realtime
from services.market_status import get_market_status
from services.name_resolver import resolve_stock_name, canonical_display_name
from services.ticker_normalizer import normalize_ticker
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

market_bp = Blueprint("market", __name__, url_prefix="/api")

_macro_cache: dict = {"data": None, "ts": 0.0}

# Market-aware cache for /api/market/indices. Intraday: 15s so the KOSPI /
# S&P tiles feel live. Off-hours: 300s so we don't spin upstreams while
# levels aren't moving. See services.cache_ttl.indices_ttl().
_indices_cache: dict = {}  # region -> {"ts": float, "data": [...]}


def _indices_ttl() -> int:
    try:
        from services.cache_ttl import indices_ttl
        return indices_ttl()
    except Exception:
        return 300


@market_bp.route("/search")
@api_auth
def search_stocks():
    """Fuzzy stock search — supports company names, partial tickers, Korean names.
    Uses FMP search API for US + local KOREAN_NAMES registry for KR stocks."""
    query = (request.args.get("q") or "").strip()
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
                "name":      candidate,
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
            url = (
                "https://financialmodelingprep.com/stable/search-symbol"
                f"?query={query}&limit=10&apikey={fmp_key}"
            )
            resp = _req.get(url, timeout=5)
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


@market_bp.route("/lookup/<ticker>")
@general_rate_limit
def lookup_ticker(ticker):
    # 2026-05-08 (NEW-C): Removed @api_auth so the /simulator/what-if viral
    # acquisition funnel can resolve tickers (symbol/name/price/currency —
    # all public market data) without forcing a login. Upstream quota is
    # protected by:
    #   - @general_rate_limit (per-IP request budget; see security.py)
    #   - DataFetcher cache layers in fmp_service / Alpaca
    # Earlier SEC-009 hardening required auth here, but the quick_lookup
    # response carries no PII / portfolio data — only what every public
    # quote page exposes — so the trade-off favors UX.
    result = fetcher.quick_lookup(ticker.strip().upper())
    if result:
        return jsonify(result)
    return jsonify({"ok": False, "error": f"Ticker '{ticker}' not found"}), 404


@market_bp.route("/prices")
@api_auth
def get_prices_fast():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"prices": {}})

    prices = realtime.get_prices_batch(tickers)
    for ticker, pdata in prices.items():
        c = db.session.get(SignalCache, ticker)
        if c and c.data_json:
            try:
                sd = json.loads(c.data_json)
                sd["price"] = pdata["price"]
                sd["price_display"] = pdata.get("price_display", sd.get("price_display"))
                if pdata.get("change_pct") is not None:
                    sd["change_pct"] = pdata["change_pct"]
                c.data_json = json.dumps(sd, ensure_ascii=False)
                c.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            except Exception:
                logger.debug("silent-fallback: get_prices_fast", exc_info=True)
                pass
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Cache update is a side-effect; the prices payload is what matters.
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "market.get_prices_fast cache-update commit failed"
        )
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Ensure every ticker payload carries observed_at so the frontend
    # can render per-row freshness chips without a separate lookup.
    for t, pdata in prices.items():
        if isinstance(pdata, dict) and not pdata.get("observed_at"):
            pdata["observed_at"] = pdata.get("timestamp") or now_iso
    return jsonify({"prices": prices,
                    "updated_at": now_iso,
                    "observed_at": now_iso,
                    "sources": {t: p.get("source", "?") for t, p in prices.items()}})


@market_bp.route("/market/overview")
@api_auth
def market_overview():
    now = _time.time()
    if _macro_cache["data"] and now - _macro_cache["ts"] < 90:
        resp = jsonify(_macro_cache["data"])
        age = int(now - _macro_cache["ts"])
        resp.headers["Cache-Control"] = f"public, max-age={max(90 - age, 0)}, stale-while-revalidate=60"
        return resp
    macro = fetcher.get_enhanced_macro()
    gs_view = fetcher.generate_gs_view(macro)
    if macro.get("usdkrw", {}).get("price"):
        fx_service.set_rate(macro["usdkrw"]["price"])
    result = {"macro": macro, "gs_view": gs_view, "cached_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}
    _macro_cache["data"] = result
    _macro_cache["ts"] = now
    resp = jsonify(result)
    resp.headers["Cache-Control"] = "public, max-age=90, stale-while-revalidate=60"
    return resp


@market_bp.route("/market/fx")
@api_auth
def get_fx_rates():
    """Return the live USD/KRW exchange rate.

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
        return jsonify({"error": "Unable to fetch FX rate"}), 500


@market_bp.route("/macro")
@api_auth
def get_macro():
    resp = jsonify(fetcher.get_macro_data())
    resp.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=30"
    return resp


@market_bp.route("/sectors")
@api_auth
def get_sectors():
    resp = jsonify(fetcher.get_sector_performance())
    resp.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=60"
    return resp


@market_bp.route("/news/<ticker>")
@api_auth
def get_news(ticker):
    return jsonify({"news": fetcher.get_news(ticker.upper())})


@market_bp.route("/market/status")
def market_status_route():
    """Public endpoint — KST-based market status for US + KR (tradable + next event)."""
    return jsonify(get_market_status())


def _normalize_ticker_for_alpaca(ticker: str) -> str:
    """Alpaca uses slash notation for share classes (BRK/B, BF/B).
    Convert hyphenated tickers like BRK-B → BRK/B so Alpaca resolves correctly.
    FMP accepts both BRK-B and BRK.B — we leave the original for FMP paths.
    """
    if "-" in ticker and not ticker.startswith("^"):
        return ticker.replace("-", "/")
    return ticker


@market_bp.route("/chart/<ticker>")
@api_auth
def chart_data(ticker):
    period = request.args.get("period", "6mo")
    if period not in ("1mo", "3mo", "6mo", "1y", "2y", "1d", "5d"):
        period = "6mo"
    # Normalize at the input boundary — handles bare 6-digit codes,
    # routes KOSDAQ to .KQ instead of the legacy .KS default.
    ticker = normalize_ticker(ticker)
    is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")

    # Normalize hyphenated class-share tickers for Alpaca (BRK-B → BRK/B).
    # Alpaca rejects BRK-B silently, causing a full Alpaca timeout before FMP fallback.
    # FMP path still receives the original ticker (hyphen form is accepted by FMP stable).
    alpaca_ticker = _normalize_ticker_for_alpaca(ticker)

    def _fetch_chart():
        """Inner fetch — called inside a 6s hard-timeout thread."""
        # US intraday (1d/5d) — Alpaca primary, FMP fallback
        if not is_kr and realtime.alpaca_available and period in ("1d", "5d"):
            try:
                from alpaca.data.requests import StockBarsRequest
                from alpaca.data.timeframe import TimeFrame
                tf = TimeFrame.Minute if period == "1d" else TimeFrame(5, "Min")
                days = 1 if period == "1d" else 5
                start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
                req = StockBarsRequest(symbol_or_symbols=alpaca_ticker, timeframe=tf, start=start, limit=500)
                bars = realtime.alpaca_client.get_stock_bars(req)
                raw = bars.get(alpaca_ticker) or bars.get(ticker) or []
                data = [{"date": bar.timestamp.strftime("%Y-%m-%d %H:%M"),
                         "close": round(float(bar.close), 2),
                         "volume": int(bar.volume)} for bar in raw]
                if data:
                    return {
                        "ticker": ticker, "period": period, "data": data,
                        "source": "alpaca",
                        "observed_at": data[-1]["date"] if data else None,
                    }
            except Exception as e:
                logger.warning("Alpaca intraday chart failed %s: %s", ticker, e)

        # US daily (1mo+) — Alpaca primary via fetcher.get_price_history() (which already
        # routes Alpaca -> FMP fallback). For KR, same fetcher routes KIS -> FMP fallback.
        if not ticker.startswith("^"):
            try:
                # Pass normalized ticker for Alpaca path; fetcher handles routing internally.
                h = fetcher.get_price_history(alpaca_ticker if alpaca_ticker != ticker else ticker, period=period)
                if h is not None and not h.empty:
                    data = [{"date": (date.strftime("%Y-%m-%d %H:%M") if hasattr(date, 'hour')
                                      and (date.hour or date.minute) else date.strftime("%Y-%m-%d")),
                             "close": round(float(row["Close"]), 2),
                             "volume": int(row.get("Volume", 0))} for date, row in h.iterrows()]
                    source = "alpaca" if not is_kr else "kis"
                    return {"ticker": ticker, "period": period,
                            "data": data, "source": source,
                            "observed_at": data[-1]["date"] if data else None}
            except Exception as e:
                logger.warning("Primary chart source failed %s: %s", ticker, e)

        # Final fallback — FMP directly (indices, or when primaries failed).
        # Use original ticker — FMP stable accepts BRK-B and BRK.B forms.
        try:
            from services.data import fmp as fmp
            h = fmp.get_history(ticker, period=period)
            if h is None or h.empty:
                return {
                    "ticker": ticker, "period": period, "data": [],
                    "source": "none", "message": "Chart data temporarily unavailable",
                }
            data = [{"date": date.strftime("%Y-%m-%d"),
                     "close": round(float(row["Close"]), 2),
                     "volume": int(row.get("Volume", 0))} for date, row in h.iterrows()]
            return {"ticker": ticker, "period": period, "data": data, "source": "fmp",
                    "observed_at": data[-1]["date"] if data else None}
        except Exception as e:
            logger.error("Chart FMP fallback error %s: %s", ticker, e)
            return None

    # Run chart fetch with a 6s hard wall-clock deadline.
    # Without this, Alpaca timeout (default ~10s) + FMP timeout (5s) stacks to 15s+.
    # On deadline miss we return an empty-data friendly payload immediately.
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_fetch_chart)
            result = fut.result(timeout=6)
    except FuturesTimeout:
        logger.warning("chart_data hard timeout (6s) for %s/%s", ticker, period)
        result = None
    except Exception as e:
        logger.error("Chart error %s: %s", ticker, e)
        result = None

    if result:
        return jsonify(result)
    return jsonify({
        "ticker": ticker,
        "period": period,
        "data": [],
        "source": "none",
        "message": "Unable to fetch chart data",
    })


@market_bp.route("/earnings")
@api_auth
def earnings_calendar():
    from services.data import fmp as fmp
    positions = Position.query.filter_by(user_id=current_user.id).all()
    earnings = []

    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    for p in positions:
        try:
            is_etf = p.ticker in ('TSLL', 'ETHU', 'SPY', 'QQQ', 'TLT', 'GLD', 'USO', 'UUP') or 'ETF' in (p.ticker or '')
            if is_etf:
                continue
            cal = fmp.get_earnings_calendar(ticker=p.ticker, days_ahead=90)
            if cal:
                for entry in cal[:1]:  # Take the nearest earnings date
                    ds = entry.get("date", "")[:10]
                    if ds:
                        c = cache_map.get(p.ticker)
                        sd = json.loads(c.data_json) if c and c.data_json else {}
                        earnings.append({
                            "ticker": p.ticker,
                            "name": canonical_display_name(sd.get("name"), p.ticker),
                            "date": ds, "signal": sd.get("signal", "—"),
                            "score": sd.get("score", 0),
                        })
        except Exception:
            logger.debug("silent-fallback: earnings_calendar", exc_info=True)
            pass
    earnings.sort(key=lambda x: x.get("date", "9999"))
    return jsonify({"earnings": earnings})


@market_bp.route("/peers/<ticker>")
@api_auth
def peer_comparison(ticker):
    ticker = normalize_ticker(ticker)
    c = db.session.get(SignalCache, ticker)
    if not c or not c.data_json:
        return jsonify({"error": "Analyze this stock first"}), 404
    target = json.loads(c.data_json)
    sector = target.get("sector", "Unknown")
    if sector in ("Unknown", "ETF"):
        return jsonify({"peers": [], "sector": sector, "message": "No sector peers available"})

    # Intentional global scan: peer comparison ranks every ticker in the
    # target sector. Single query (not N+1). A sector column on SignalCache
    # would let this become an indexed filter; deferred to schema migration.
    all_cached = SignalCache.query.all()
    peers = []
    for sc in all_cached:
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == sector:
                peers.append({
                    "ticker": sc.ticker,
                    "name": canonical_display_name(sd.get("name"), sc.ticker),
                    "score": sd.get("score", 0), "signal": sd.get("signal", "—"),
                    "price": sd.get("price", 0), "price_display": sd.get("price_display", "—"),
                    "change_pct": sd.get("change_pct", 0),
                    "pe_ratio": sd.get("snapshot", {}).get("pe_ratio"),
                    "is_target": sc.ticker == ticker,
                })
        except Exception:
            logger.debug("silent-fallback: peer_comparison", exc_info=True)
            pass
    peers.sort(key=lambda x: -x.get("score", 0))
    rank = next((i + 1 for i, p in enumerate(peers) if p["is_target"]), 0)
    return jsonify({"peers": peers[:10], "sector": sector, "rank": rank, "total": len(peers)})


@market_bp.route("/market/profile/<ticker>")
@api_auth
def company_profile(ticker):
    ticker = normalize_ticker(ticker)
    is_korean = ticker.endswith(".KS") or ticker.endswith(".KQ")
    try:
        from services.data import fmp as fmp
        info = fmp.get_info(ticker)
        sector = (info.get("sector") or "").strip()
        # "Unknown" is a common upstream placeholder when FMP has no KRX
        # coverage — treat it the same as an empty string so the
        # KOREAN_SECTORS curated table can supply the real sector.
        if is_korean and (not sector or sector.lower() == "unknown"):
            from services.data.fetcher import KOREAN_SECTORS
            sector = KOREAN_SECTORS.get(ticker, "") or sector
        # KR canonical name (BUG-01 follow-up 2026-05-10): for .KS/.KQ
        # tickers, the Korean name from kr_stock_registry must win over
        # FMP shortName (English label). For US the FMP shortName remains
        # source of truth.
        if is_korean:
            display_name = resolve_stock_name(ticker) or info.get("shortName") or ticker
        else:
            display_name = info.get("shortName") or resolve_stock_name(ticker) or ticker
        return jsonify({
            "ticker": ticker,
            "name": display_name,
            "summary": info.get("longBusinessSummary", ""),
            "sector": sector,
            "industry": info.get("industry", ""),
            "website": info.get("website", ""),
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country", ""),
            "market_cap": info.get("marketCap"),
            "currency": "KRW" if is_korean else "USD",
        })
    except Exception as e:
        logger.error("Profile error %s: %s", ticker, e)
        return jsonify({"error": "Unable to fetch company profile"}), 500


# US indices → liquid ETF proxies. FMP Starter and Alpaca both refuse to
# serve caret-prefixed index symbols (^GSPC, ^IXIC…). The ETFs track the
# indices within ±0.02% intraday, so level + 1d%change + 52W range +
# sparkline are all mathematically honest when published in ETF units.
# The UI renders a single number so the unit difference (SPY=$708 vs
# GSPC=5800) is invisible. Do NOT attempt a "ratio conversion" — the
# ratio drifts over time and would inject wrong values.
_US_INDEX_PROXY = {
    "^GSPC": ("SPY",  "S&P 500"),
    "^IXIC": ("QQQ",  "Nasdaq 100"),
    "^DJI":  ("DIA",  "Dow Jones"),
    "^RUT":  ("IWM",  "Russell 2000"),
    "^VIX":  ("VIXY", "Volatility (VIXY)"),
}

_KR_INDEX_SPEC = [
    # ticker,    display,       kis_code, macro_key
    ("^KS11",    "KOSPI",       "0001",   "kospi"),
    ("^KQ11",    "KOSDAQ",      "1001",   "kosdaq"),
    ("^KS200",   "KOSPI 200",   "2001",   None),
    ("^KQ150",   "KOSDAQ 150",  "2203",   None),
    # USDKRW handled separately via fx_service / macro
]



def _etf_snapshot(etf: str, display: str, ticker_alias: str) -> dict | None:
    """Build the standard index entry from a liquid ETF proxy.

    Uses the SAME fallback chain as ``/api/lookup/<ticker>`` — namely
    ``fetcher.quick_lookup`` (Alpaca realtime → FMP quote → FMP profile)
    for the live level, then ``fetcher.get_price_history`` (same engine
    as ``/api/chart/<ticker>``) for the sparkline + 52W range + the 1d%
    fallback when the live quote payload lacks it.

    Previous implementation used ``services.data.alpaca_market_adapter.get_quote``
    which hits Alpaca's ``get_stock_bars`` daily endpoint — on the free IEX
    tier this returns empty bars for many sessions and silently drops the
    whole index payload (regression #80c7d26). The ``/api/lookup`` path
    already survives that case via Alpaca realtime trade/quote/bar →
    FMP → FMP profile chain, so we reuse it verbatim.

    Returns None only when BOTH live quote AND history are unavailable —
    partial data is more honest than hardcoded mocks.
    """
    level: float | None = None
    change_pct: float = 0.0

    # 1) Live quote — identical code path as /api/lookup/<ticker>.
    try:
        q = fetcher.quick_lookup(etf)
        if q and q.get("price"):
            level = float(q["price"])
    except Exception as e:
        logger.debug("market.indices lookup %s failed: %s", etf, e)

    # 2) History for sparkline + 52W + fallback level / change.
    #    Same engine as /api/chart/<ticker>?period=1y.
    sparkline: list[float] = []
    range_52w: list[float] | None = [0.0, 0.0]
    is_stale = False
    closes = None
    try:
        h = fetcher.get_price_history(etf, period="1y")
        if h is not None and not h.empty and "Close" in h.columns:
            c = h["Close"].astype(float).dropna()
            if len(c):
                closes = c
    except Exception as e:
        logger.debug("market.indices history %s failed: %s", etf, e)

    # Staleness guard (same policy as `_kis_index_snapshot`): reject any
    # history whose tail diverges from the live level by >30%. Protects
    # against FMP returning year-old data on Starter-tier quiet windows.
    if closes is not None and len(closes) and level is not None and level > 0:
        last_hist = float(closes.iloc[-1])
        if abs(last_hist - level) / level > 0.30:
            logger.warning(
                "market.indices %s (%s) history stale: tail=%.2f vs "
                "live level=%.2f — discarding series",
                ticker_alias, etf, last_hist, level,
            )
            closes = None
            is_stale = True

    if closes is not None and len(closes):
        if level is None:
            level = float(closes.iloc[-1])
        if len(closes) >= 2:
            prev = float(closes.iloc[-2])
            if prev:
                last = float(closes.iloc[-1])
                # Prefer history-derived change: even when live quote
                # has a value, lookup doesn't surface a d/d%, so
                # closes.iloc[-1]/[-2] is our only source.
                change_pct = (last - prev) / prev * 100.0
        sparkline = [round(float(v), 4) for v in closes.tail(30).tolist()]
        range_52w = [round(float(closes.min()), 2),
                     round(float(closes.max()), 2)]
    else:
        sparkline = []
        range_52w = None

    if level is None:
        return None  # truly nothing to show — caller skips this entry

    return {
        "ticker":        ticker_alias,
        "proxy_ticker":  etf,
        "name":          display,
        "level":         round(level, 2),
        "change_1d_pct": round(change_pct, 2),
        "range_52w":     range_52w,
        "sparkline_30d": sparkline,
        "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_stale":      is_stale,
    }


def _kis_index_snapshot(kis_code: str, ticker: str, display: str) -> dict | None:
    """Build standard index entry from a KIS index code.

    Strategy mirrors ``_etf_snapshot``: live KIS quote if available,
    otherwise fall back to price history for level + sparkline + 52W.
    Many KIS index codes (2001/2203) lack historical endpoints so
    sparkline may be empty, but we still return a valid entry as long as
    EITHER the KIS quote OR the history engine produced a level.
    """
    level: float | None = None
    change_pct: float = 0.0

    # Candidate KIS index codes. KIS's `inquire-index-price` endpoint is
    # documented with 0001/1001 for KOSPI/KOSDAQ and 2001/2203 for
    # KOSPI200/KOSDAQ150 — but the 2xxx codes have been observed returning
    # rt_cd!=0 on the Starter plan. When the primary code yields no data we
    # retry a known alternate (some regional docs use "201"/"301"). First
    # non-empty hit wins.
    _kis_code_candidates = {
        "2001": ["2001", "0201"],   # KOSPI 200 alternatives
        "2203": ["2203", "1150"],   # KOSDAQ 150 alternatives
    }.get(kis_code, [kis_code])

    # 1) Live KIS quote (best — includes native d/d%).
    # Bug D (2026-04-24): previously gated on `_rt.kis_available`, but that
    # flag is a realtime-service-side init signal that can go False during a
    # restart window even when the KIS keys are valid. KISService.__init__
    # performs its own credential check (see `self.available` in
    # kis_service.py) so we always *attempt* KIS here and let the service
    # short-circuit internally. Keeps the KR-indices tiles alive when
    # realtime init is briefly degraded.
    kis_level_raw: float | None = None      # raw KIS level for diagnostic
    kis_passed_sanity: bool = False         # did KIS level pass per-ticker bounds?
    try:
        from services.kis.service import KISService
        _svc = KISService()
        for _code in _kis_code_candidates:
            idx = _svc.get_index_price(_code)
            if idx and idx.get("price"):
                level = float(idx["price"])
                kis_level_raw = level
                change_pct = float(idx.get("change_pct") or 0)
                if _code != kis_code:
                    logger.info(
                        "market.indices KIS primary code %s empty; "
                        "resolved via alternate %s", kis_code, _code,
                    )
                break
    except Exception as e:
        logger.debug("market.indices KIS %s failed: %s", kis_code, e)

    # 2) History for sparkline + 52W + fallback level / change.
    #
    # KR-index history source policy (2026-04-24, fix for BUG #RANGE-STALE):
    #   KIS *live* quote is authoritative for `level` (e.g., KOSPI 6475.63
    #   matches Yahoo/Investing). FMP `^KS11`/`^KQ11` history is known to
    #   lag by quarters on the Starter plan — using it for sparkline/range
    #   while `level` is KIS-live produced self-contradictory payloads
    #   where `level > sparkline.max()` by >2x and `range_52w[1] < level`.
    #
    # New policy: for KR indices we *prefer KIS* `inquire-index-daily-price`
    # (FHPUP02120000) since it shares units with the live quote. FMP is
    # only used as a fallback, and any FMP series whose tail diverges from
    # the live level by more than 30% is rejected as stale.
    sparkline: list[float] = []
    range_52w: list[float] | None = [0.0, 0.0]
    closes = None
    hist_source = None  # "kis" | "fmp" | None — for logging + stale guard
    is_stale = False

    # 2a) KIS history FIRST (unit-consistent with live quote).
    # Bug D (2026-04-24): attempt KIS directly without the realtime-side
    # `kis_available` gate — KISService has its own credential check and
    # returns None cleanly when keys are missing. The prior gate hid the
    # history endpoint whenever realtime init was degraded, sending us to
    # the unit-divergent FMP path.
    try:
        from services.kis.service import KISService
        _svc = KISService()
        for _code in _kis_code_candidates:
            hist = _svc.get_index_history(_code, period="1y")
            if hist:
                vals = [float(row.get("close"))
                        for row in hist
                        if row and row.get("close") is not None]
                if vals:
                    import pandas as _pd
                    closes = _pd.Series(vals)
                    hist_source = "kis"
                    break
    except Exception as e:
        logger.debug("market.indices KIS history %s failed: %s", kis_code, e)

    # 2b) FMP fallback ONLY when KIS history unavailable.
    if closes is None or len(closes) == 0:
        try:
            h = fetcher.get_price_history(ticker, period="1y")
            if h is not None and not h.empty and "Close" in h.columns:
                c = h["Close"].astype(float).dropna()
                if len(c):
                    closes = c
                    hist_source = "fmp"
        except Exception as e:
            logger.debug("market.indices fmp history %s failed: %s", ticker, e)

    # 2c) Staleness guard — source-aware (Bug B fix, 2026-05-13).
    #
    # The 30% divergence guard was originally added (PR #196) to protect
    # against FMP caret-prefixed KR index tickers on the Starter tier
    # serving year-old snapshots. In 2026-Q2 the Korean market re-rated
    # sharply (KOSPI 5,052 → 7,643, verified via PR #234 B-06 live KIS
    # probe), which the 30% guard incorrectly flagged as stale because
    # `tail(history) vs live` exceeded 30% for completely legitimate
    # monotonic uptrends — silently discarding real KIS data and
    # producing the empty-sparkline / null-range_52w symptom CEO saw
    # on 2026-05-12.
    #
    # Fix: trust KIS daily-history (broker-issued, unit-consistent with
    # the live KIS quote — confirmed via B-06). Keep the divergence
    # guard only for non-KIS history sources (FMP today, future
    # providers). For KIS we still flag is_stale when the live level
    # disagrees with the tail in a way that *cannot* be explained by a
    # monotonic uptrend (allows down-trend stale detection too).
    if closes is not None and len(closes) and level is not None:
        last_hist = float(closes.iloc[-1])
        divergence = abs(last_hist - level) / level if level > 0 else 0.0
        if hist_source == "kis":
            # KIS is trustworthy: only flag stale on extreme unit-confusion
            # (100% = 2x apart, which is what a 0001-vs-0001-x-3 quirk
            # would produce). Sanity bound below catches pure unit errors;
            # this layer catches subtler stale-cache anomalies.
            if divergence > 1.0:
                logger.warning(
                    "market.indices %s KIS history extreme divergence: "
                    "tail=%.2f vs live=%.2f (%.1f%%) — discarding",
                    ticker, last_hist, level, divergence * 100.0,
                )
                closes = None
                is_stale = True
        else:
            # Non-KIS (FMP / future): keep 30% guard.
            if divergence > 0.30:
                logger.warning(
                    "market.indices %s history (%s) stale: tail=%.2f vs "
                    "live level=%.2f (diff %.1f%%) — discarding series",
                    ticker, hist_source or "?", last_hist, level,
                    divergence * 100.0,
                )
                closes = None
                is_stale = True

    if closes is not None and len(closes):
        if level is None:
            level = float(closes.iloc[-1])
        if change_pct == 0.0 and len(closes) >= 2:
            prev = float(closes.iloc[-2])
            if prev:
                change_pct = (float(closes.iloc[-1]) - prev) / prev * 100.0
        sparkline = [round(float(v), 4) for v in closes.tail(30).tolist()]
        range_52w = [round(float(closes.min()), 2),
                     round(float(closes.max()), 2)]

        # Bug #2 (2026-05-14): stale-window cross-validation.
        #
        # Phase-0 finding: the KIS "0001" current level (~7,981 on
        # 2026-05-14) is REAL — KOSPI hit an all-time high ~7,844 on
        # 2026-05-13 (AI-chip rally, +31% MoM). There is NO 3x scaling
        # bug; the wide sanity bounds are correct and must NOT be
        # tightened (a 4,500 ceiling would reject the real index).
        #
        # The genuine defect: KIS's `inquire-index-daily-price` endpoint
        # lags — on 2026-05-14 its newest row was 2026-04-14 (5,967.75),
        # a full month behind the live quote. The history is internally
        # consistent (a legitimate uptrend), just from an older window.
        # When `level` sits well above the whole sparkline, the frontend
        # would draw a chart whose every point is below the headline
        # number — visually a "contradiction" even though both values
        # are real. This is the symptom the live bug-hunt flagged.
        #
        # Fix: when the live level exceeds the sparkline max by >15%,
        # tag `is_stale=true` so the consumer can suppress / annotate
        # the lagging chart. We keep the real `level` and the real
        # (stale) sparkline — no data is discarded, the consumer just
        # gets an honest staleness signal.
        if level is not None and sparkline:
            spark_max = max(sparkline)
            if spark_max > 0 and level > spark_max * 1.15:
                logger.info(
                    "market.indices %s: live level %.2f exceeds sparkline "
                    "max %.2f by >15%% — KIS daily-history window lags the "
                    "live quote; tagging is_stale",
                    ticker, level, spark_max,
                )
                is_stale = True
    else:
        # No trustworthy history — return null range so the frontend
        # renders "N/A" rather than [0.0, 0.0] (which the bar chart
        # would otherwise draw as a degenerate point).
        sparkline = []
        range_52w = None

    # Per-ticker sanity bounds. These exist only to catch gross unit
    # confusion (e.g. KOSPI returned as 749,800 — a 100x scaling glitch),
    # NOT to second-guess a high-but-real index level.
    #
    # 2026-05-14 (Bug #2 Phase-0, DEFINITIVE): the KIS "0001" level of
    # ~7,981 IS the real KOSPI. Confirmed against external press
    # (KOSPI all-time high ~7,844 on 2026-05-13; +31% MoM, +197% YoY on
    # the AI-chipmaker rally). The earlier "~3x scaled KOSPI-200" and
    # "real index trades 2,500–3,200" comments were a WRONG hypothesis —
    # they have been removed to stop misleading future readers. KIS
    # `0001` live and KIS `0001` daily-history are the same product;
    # the only real defect is the daily-history endpoint lagging by ~1
    # month (handled by the is_stale tag above). Bounds stay wide.
    _PER_TICKER_BOUNDS = {
        "^KS11":  (1_500.0, 50_000.0),  # KOSPI composite — head-room to 50k
        "^KQ11":  (500.0,   50_000.0),  # KOSDAQ composite
        "^KS200": (300.0,   10_000.0),  # KOSPI 200
        "^KQ150": (500.0,   10_000.0),  # KOSDAQ 150
    }
    lo, hi = _PER_TICKER_BOUNDS.get(ticker, (100.0, 50_000.0))

    def _in_bound(v: float | None) -> bool:
        return v is not None and lo <= v <= hi

    kis_passed_sanity = _in_bound(level)

    # 2026-05-09 P0 graceful-degradation: when the KIS-derived level either
    # is missing or fails the per-ticker sanity bound (the dominant failure
    # mode is the KIS `0001`/`2001`/`2203` unit/code quirk that returns
    # values like 7498 for KOSPI — see PR #188), attempt FMP as a fallback
    # source for the live level. Sanity bound is then *re-applied* to the
    # FMP value — only realistic values surface, so the defensive guard
    # introduced by PR #188 is fully preserved.
    #
    # KNOWN LIMITATION (recorded for parent agent on 2026-05-09): on the
    # current FMP Premium ($29) plan, caret-prefixed KR index symbols
    # (`^KS11`, `^KQ11`, `^KS200`, `^KQ150`) all return HTTP 402 from both
    # `/quote` and `/historical-price-eod/full`. This fallback path is
    # therefore architectural — it engages cleanly the moment FMP's plan
    # permits index symbols (or an alternate symbol mapping is added).
    # On today's plan the entry remains dropped when KIS sanity fails;
    # behavior matches PR #188 for the failing tickers.
    if not kis_passed_sanity:
        try:
            from services.data import fmp as _fmp
            q = _fmp.get_quote(ticker)
            if q and q.get("price"):
                fmp_price = float(q["price"])
                if _in_bound(fmp_price):
                    logger.info(
                        "market.indices %s: KIS level %s sanity-failed "
                        "(bound [%.0f,%.0f]); FMP fallback succeeded with "
                        "%.2f",
                        ticker,
                        f"{kis_level_raw:.2f}" if kis_level_raw is not None
                        else "missing",
                        lo, hi, fmp_price,
                    )
                    level = fmp_price
                    # Prefer FMP-derived d/d% when present, otherwise keep
                    # whatever change_pct we already had (KIS or 0).
                    fmp_change = q.get("changesPercentage") or q.get("change_pct")
                    if fmp_change is not None:
                        try:
                            change_pct = float(fmp_change)
                        except (TypeError, ValueError):
                            pass
                    # Re-validate any sparkline/range derived from the
                    # earlier (sanity-failed) level. The 30% staleness
                    # check at line ~781 ran against the bogus KIS level —
                    # a series that "passed" relative to KIS 7498 may now
                    # diverge wildly from the trustworthy FMP 2540. Drop
                    # those artifacts so we don't render
                    # level=2540 / range_52w=[5700,6800] together.
                    if sparkline:
                        spark_max = max(sparkline) if sparkline else 0.0
                        spark_min = min(sparkline) if sparkline else 0.0
                        # If either end of the series is outside the
                        # per-ticker sanity bound, the series came from the
                        # KIS-quirk path and must not co-exist with the
                        # FMP-derived level. Discard.
                        if not (_in_bound(spark_max) and _in_bound(spark_min)):
                            logger.warning(
                                "market.indices %s: sparkline/range from "
                                "pre-fallback path (min=%.2f max=%.2f) "
                                "incompatible with FMP level %.2f — "
                                "discarding history series",
                                ticker, spark_min, spark_max, fmp_price,
                            )
                            sparkline = []
                            range_52w = None
                            is_stale = True
                else:
                    logger.warning(
                        "market.indices %s: FMP fallback level %.2f also "
                        "outside sanity bound [%.0f,%.0f] — dropping",
                        ticker, fmp_price, lo, hi,
                    )
        except Exception as e:
            logger.debug(
                "market.indices %s FMP fallback failed: %s", ticker, e,
            )

    if level is None:
        return None

    if not _in_bound(level):
        logger.warning(
            "market.indices %s level %.2f outside sanity bound [%.0f,%.0f]; "
            "dropping entry (KIS quirk + no FMP fallback available)",
            ticker, level, lo, hi,
        )
        return None

    return {
        "ticker":        ticker,
        "name":          display,
        "level":         round(level, 2),
        "change_1d_pct": round(change_pct, 2),
        "range_52w":     range_52w,
        "sparkline_30d": sparkline,
        "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_stale":      is_stale,
    }


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

    Sources:
        - US: Alpaca ETF proxies (SPY/QQQ/DIA/IWM/VIXY) — FMP refuses
          index symbols on Starter tier and Alpaca does not serve raw ^GSPC.
        - KR: KIS index API for KOSPI/KOSDAQ (codes 0001/1001) and
          KOSPI200/KOSDAQ150 (codes 2001/2203); fx_service / macro for USD/KRW.
        - Partial failure: skip the failing ticker. Never mock.
    """
    region = (request.args.get("region") or "us").lower()
    if region not in ("us", "kr"):
        region = "us"

    # Cache-key version bump: the v1 key may contain an empty-array payload
    # produced by the regressed ``ama.get_quote``-only snapshot (commit
    # 80c7d26). Versioning the key guarantees we bypass any poisoned entry
    # instead of waiting for the TTL to expire.
    cache_key = f"{region}_v2"
    entry = _indices_cache.get(cache_key)
    now = _time.time()
    if entry and now - entry["ts"] < _indices_ttl():
        return jsonify(entry["data"])

    out: list[dict] = []

    if region == "us":
        for raw_ticker, (etf, display) in _US_INDEX_PROXY.items():
            snap = _etf_snapshot(etf, display, raw_ticker)
            if snap is not None:
                out.append(snap)
    else:
        # KR indices via KIS
        for raw_ticker, display, kis_code, _macro_key in _KR_INDEX_SPEC:
            snap = _kis_index_snapshot(kis_code, raw_ticker, display)
            if snap is not None:
                out.append(snap)

        # USD/KRW — fx_service is always live (refreshed on app boot +
        # background tick). Fall back to macro payload if fx_service empty.
        usdkrw_level = None
        try:
            usdkrw_level = float(fx_service.get_rate() or 0) or None
        except Exception:
            usdkrw_level = None
        if usdkrw_level is None:
            try:
                macro = fetcher.get_enhanced_macro() or {}
                mv = macro.get("usdkrw") or {}
                if mv.get("price"):
                    usdkrw_level = float(mv["price"])
            except Exception:
                logger.debug("silent-fallback: market_indices", exc_info=True)
                pass
        if usdkrw_level:
            # Pull 1y FX history from FMP for sparkline + 52W range + d/d%.
            # fmp_service.get_history("USDKRW") returns a standard OHLCV
            # DataFrame; gracefully fall back to empty on any failure so a
            # history miss never drops the level tile.
            #
            # Symbol fallback ladder (2026-04-24):
            #   USDKRW  → FMP canonical. Empty on Starter tier during most
            #             windows.
            #   USDKRW=X → Yahoo-style alias; FMP sometimes resolves it.
            #   KRW=X    → Last-ditch inversion attempt.
            # If ALL three are empty, range_52w becomes None so the
            # frontend can render "N/A" instead of the buggy [0,0] hardcode.
            fx_change_pct = 0.0
            fx_sparkline: list[float] = []
            fx_range_52w: list[float] | None = None
            fx_is_stale = False
            fx_closes = None
            try:
                from services.data import fmp as _fmp
                for _sym in ("USDKRW", "USDKRW=X", "KRW=X"):
                    try:
                        fx_hist = _fmp.get_history(_sym, period="1y")
                    except Exception:
                        fx_hist = None
                    if fx_hist is not None and not fx_hist.empty \
                            and "Close" in fx_hist.columns:
                        c = fx_hist["Close"].astype(float).dropna()
                        if len(c):
                            fx_closes = c
                            break
            except Exception as e:
                logger.debug("market.indices USDKRW history failed: %s", e)

            if fx_closes is not None and len(fx_closes):
                # Staleness guard mirrors the KR-index one: FMP USDKRW is
                # notorious for returning year-old tails during the Starter
                # plan's quiet windows. If the last close diverges from the
                # live rate by >10%, treat it as stale.
                last_fx = float(fx_closes.iloc[-1])
                if usdkrw_level > 0 and abs(last_fx - usdkrw_level) / usdkrw_level > 0.10:
                    logger.warning(
                        "market.indices USDKRW history stale: tail=%.2f "
                        "vs live level=%.2f — discarding series",
                        last_fx, usdkrw_level,
                    )
                    fx_closes = None
                    fx_is_stale = True

            if fx_closes is not None and len(fx_closes):
                if len(fx_closes) >= 2:
                    fx_prev = float(fx_closes.iloc[-2])
                    if fx_prev:
                        fx_change_pct = (
                            (float(fx_closes.iloc[-1]) - fx_prev)
                            / fx_prev * 100.0
                        )
                fx_sparkline = [
                    round(float(v), 4)
                    for v in fx_closes.tail(30).tolist()
                ]
                fx_range_52w = [
                    round(float(fx_closes.min()), 2),
                    round(float(fx_closes.max()), 2),
                ]

            out.append({
                "ticker":        "USDKRW",
                "name":          "USD / KRW",
                "level":         round(usdkrw_level, 2),
                "change_1d_pct": round(fx_change_pct, 2),
                "range_52w":     fx_range_52w,
                "sparkline_30d": fx_sparkline,
                "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "is_stale":      fx_is_stale,
            })

    # Only cache successful responses. Caching a thin failure for 30s locks
    # users into mock-looking data for the whole cache window — better to
    # re-try upstream on every request until it succeeds.
    if out:
        _indices_cache[cache_key] = {"ts": now, "data": out}

    return jsonify(out)


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
              "observed_at": "2026-05-15T01:23:45Z"  # ISO-8601 UTC, or null
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

    # Map cache ticker -> (display name) for the symbols the landing ticker
    # needs. US entries live under cache_key "us_v2", KR under "kr_v2" —
    # the exact keys /api/market/indices writes.
    _WANTED = [
        ("kr_v2", "^KS11", "KOSPI"),
        ("kr_v2", "^KQ11", "KOSDAQ"),
        ("kr_v2", "USDKRW", "USD / KRW"),
        ("us_v2", "^GSPC", "S&P 500"),
        ("us_v2", "^IXIC", "NASDAQ"),
        ("us_v2", "^VIX", "VIX"),
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
    for region_key, ticker, display in _WANTED:
        snap = region_data.get(region_key, {}).get(ticker)
        if snap is not None:
            index_cache_warm = True
            # is_stale: honor the snapshot's own flag, OR mark stale when
            # the region cache itself has aged past TTL.
            stale = bool(snap.get("is_stale")) or not region_fresh.get(region_key, False)
            change_pct = snap.get("change_1d_pct", 0.0) or 0.0
            items.append({
                "symbol": ticker,
                "name": display,
                "value": snap.get("level"),
                "change_pct": round(float(change_pct), 2),
                "direction": _direction(change_pct),
                "is_stale": stale,
                "observed_at": snap.get("observed_at"),
            })
        else:
            # Cache miss for this symbol — emit a placeholder row so the
            # frontend keeps a stable layout. Never a live fetch.
            items.append({
                "symbol": ticker,
                "name": display,
                "value": None,
                "change_pct": 0.0,
                "direction": "flat",
                "is_stale": True,
                "observed_at": None,
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


@market_bp.route("/dividend/<ticker>")
@api_auth
def dividend_data(ticker):
    ticker = normalize_ticker(ticker)
    try:
        from services.data import fmp as fmp
        info = fmp.get_info(ticker)
        div_yield = info.get("dividendYield", 0)
        dividends = fmp.get_dividends(ticker)
        if not div_yield and not dividends:
            return jsonify({"has_dividend": False, "ticker": ticker})
        last_div = dividends[0] if dividends else {}
        return jsonify({
            "has_dividend": True, "ticker": ticker,
            "dividend_yield": round(div_yield * 100, 2) if div_yield else None,
            "dividend_rate": last_div.get("dividend"),
            "ex_dividend_date": last_div.get("date"),
            "payout_ratio": None,
            "five_yr_avg_yield": None,
        })
    except Exception as e:
        logger.error("Dividend error %s: %s", ticker, e)
        return jsonify({"has_dividend": False, "error": "Unable to fetch dividend data"})
