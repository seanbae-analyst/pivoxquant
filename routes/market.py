"""Market data routes: overview, macro, sectors, news, prices, chart, etc."""
import json
import logging
import time as _time
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Position, SignalCache
from services import fx_service
from services.container import engine, fetcher, realtime
from services.market_status import get_market_status
from services.name_resolver import resolve_stock_name
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
    bare = query.strip()
    if bare.isdigit() and len(bare) == 6:
        candidate = f"{bare}.KS"
        if candidate not in seen:
            results.append({
                "ticker":    candidate,
                "name":      candidate,
                "exchange":  "KOSPI",
                "currency":  "KRW",
                "is_korean": True,
            })
            seen.add(candidate)

    # 2) FMP search API for US/global stocks
    import os
    fmp_key = os.environ.get("FMP_API_KEY", "")
    fmp_ok = False
    if fmp_key:
        try:
            import requests as _req
            url = f"https://financialmodelingprep.com/api/v3/search?query={query}&limit=10&apikey={fmp_key}"
            resp = _req.get(url, timeout=5)
            if resp.status_code == 200:
                try:
                    parsed = resp.json()
                except Exception as e:
                    logger.warning(f"FMP search JSON parse failed: {e}")
                    parsed = None
                if isinstance(parsed, list) and parsed:
                    added = 0
                    for item in parsed:
                        sym = item.get("symbol", "")
                        if sym and sym not in seen:
                            results.append({
                                "ticker": sym,
                                "name": item.get("name", sym),
                                "exchange": item.get("stockExchange", item.get("exchangeShortName", "")),
                                "currency": item.get("currency", "USD"),
                                "is_korean": False,
                            })
                            seen.add(sym)
                            added += 1
                    if added > 0:
                        fmp_ok = True
            else:
                logger.warning(f"FMP search HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"FMP search failed: {e}")

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
def lookup_ticker(ticker):
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


@market_bp.route("/morning-brief")
@api_auth
def morning_brief():
    brief = fetcher.get_wall_street_brief()
    macro = fetcher.get_macro_data()
    gs_view = fetcher.generate_gs_view(macro)
    return jsonify({**brief, "gs_view": gs_view})


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
        logger.error(f"FX endpoint error: {e}")
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


@market_bp.route("/chart/<ticker>")
@api_auth
def chart_data(ticker):
    period = request.args.get("period", "6mo")
    if period not in ("1mo", "3mo", "6mo", "1y", "2y", "1d", "5d"):
        period = "6mo"
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")

    # US intraday (1d/5d) — Alpaca primary, FMP fallback
    if not is_kr and realtime.alpaca_available and period in ("1d", "5d"):
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            tf = TimeFrame.Minute if period == "1d" else TimeFrame(5, "Min")
            days = 1 if period == "1d" else 5
            start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=tf, start=start, limit=500)
            bars = realtime.alpaca_client.get_stock_bars(req)
            data = [{"date": bar.timestamp.strftime("%Y-%m-%d %H:%M"),
                     "close": round(float(bar.close), 2),
                     "volume": int(bar.volume)} for bar in bars[ticker]]
            if data:
                return jsonify({
                    "ticker": ticker, "period": period, "data": data,
                    "source": "alpaca",
                    # Last-bar timestamp is the true observation time.
                    "observed_at": data[-1]["date"] if data else None,
                })
        except Exception as e:
            logger.warning(f"Alpaca intraday chart failed {ticker}: {e}")

    # US daily (1mo+) — Alpaca primary via fetcher.get_price_history() (which already
    # routes Alpaca -> FMP fallback). For KR, same fetcher routes KIS -> FMP fallback.
    if not ticker.startswith("^"):
        try:
            h = fetcher.get_price_history(ticker, period=period)
            if h is not None and not h.empty:
                data = [{"date": (date.strftime("%Y-%m-%d %H:%M") if hasattr(date, 'hour')
                                  and (date.hour or date.minute) else date.strftime("%Y-%m-%d")),
                         "close": round(float(row["Close"]), 2),
                         "volume": int(row.get("Volume", 0))} for date, row in h.iterrows()]
                # Identify source: Alpaca for US, KIS for KR, FMP fallback otherwise
                source = "alpaca" if not is_kr else "kis"
                return jsonify({"ticker": ticker, "period": period,
                                "data": data, "source": source,
                                "observed_at": data[-1]["date"] if data else None})
        except Exception as e:
            logger.warning(f"Primary chart source failed {ticker}: {e}")

    # Final fallback — FMP directly (indices, or when primaries failed)
    try:
        import fmp_service as fmp
        h = fmp.get_history(ticker, period=period)
        if h is None or h.empty:
            # Return friendly empty state rather than 404 so frontend can show
            # "No chart data available" instead of an error card.
            return jsonify({
                "ticker": ticker,
                "period": period,
                "data": [],
                "source": "none",
                "message": "Chart data temporarily unavailable",
            })
        data = [{"date": date.strftime("%Y-%m-%d"),
                 "close": round(float(row["Close"]), 2),
                 "volume": int(row.get("Volume", 0))} for date, row in h.iterrows()]
        return jsonify({"ticker": ticker, "period": period, "data": data, "source": "fmp",
                        "observed_at": data[-1]["date"] if data else None})
    except Exception as e:
        logger.error(f"Chart error {ticker}: {e}")
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
    import fmp_service as fmp
    positions = Position.query.filter_by(user_id=current_user.id).all()
    earnings = []

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
                        c = db.session.get(SignalCache, p.ticker)
                        sd = json.loads(c.data_json) if c and c.data_json else {}
                        earnings.append({
                            "ticker": p.ticker,
                            "name": sd.get("name") or resolve_stock_name(p.ticker) or p.ticker,
                            "date": ds, "signal": sd.get("signal", "—"),
                            "score": sd.get("score", 0),
                        })
        except Exception:
            pass
    earnings.sort(key=lambda x: x.get("date", "9999"))
    return jsonify({"earnings": earnings})


@market_bp.route("/peers/<ticker>")
@api_auth
def peer_comparison(ticker):
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    c = db.session.get(SignalCache, ticker)
    if not c or not c.data_json:
        return jsonify({"error": "Analyze this stock first"}), 404
    target = json.loads(c.data_json)
    sector = target.get("sector", "Unknown")
    if sector in ("Unknown", "ETF"):
        return jsonify({"peers": [], "sector": sector, "message": "No sector peers available"})

    all_cached = SignalCache.query.all()
    peers = []
    for sc in all_cached:
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == sector:
                peers.append({
                    "ticker": sc.ticker,
                    "name": sd.get("name") or resolve_stock_name(sc.ticker) or sc.ticker,
                    "score": sd.get("score", 0), "signal": sd.get("signal", "—"),
                    "price": sd.get("price", 0), "price_display": sd.get("price_display", "—"),
                    "change_pct": sd.get("change_pct", 0),
                    "pe_ratio": sd.get("snapshot", {}).get("pe_ratio"),
                    "is_target": sc.ticker == ticker,
                })
        except Exception:
            pass
    peers.sort(key=lambda x: -x.get("score", 0))
    rank = next((i + 1 for i, p in enumerate(peers) if p["is_target"]), 0)
    return jsonify({"peers": peers[:10], "sector": sector, "rank": rank, "total": len(peers)})


@market_bp.route("/profile/<ticker>")
@api_auth
def company_profile(ticker):
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    is_korean = ticker.endswith(".KS") or ticker.endswith(".KQ")
    try:
        import fmp_service as fmp
        info = fmp.get_info(ticker)
        sector = info.get("sector", "")
        if is_korean and not sector:
            from data_fetcher import KOREAN_SECTORS
            sector = KOREAN_SECTORS.get(ticker, "")
        return jsonify({
            "ticker": ticker,
            "name": info.get("shortName") or resolve_stock_name(ticker) or ticker,
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
        logger.error(f"Profile error {ticker}: {e}")
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
        logger.debug(f"market.indices lookup {etf} failed: {e}")

    # 2) History for sparkline + 52W + fallback level / change.
    #    Same engine as /api/chart/<ticker>?period=1y.
    sparkline: list[float] = []
    range_52w = [0.0, 0.0]
    try:
        h = fetcher.get_price_history(etf, period="1y")
        if h is not None and not h.empty and "Close" in h.columns:
            closes = h["Close"].astype(float).dropna()
            if len(closes):
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
    except Exception as e:
        logger.debug(f"market.indices history {etf} failed: {e}")

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
        "is_stale":      False,
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

    # 1) Live KIS quote (best — includes native d/d%).
    try:
        from services.container import realtime as _rt
        if getattr(_rt, "kis_available", False):
            from kis_service import KISService
            idx = KISService().get_index_price(kis_code)
            if idx and idx.get("price"):
                level = float(idx["price"])
                change_pct = float(idx.get("change_pct") or 0)
    except Exception as e:
        logger.debug(f"market.indices KIS {kis_code} failed: {e}")

    # 2) History for sparkline + 52W + fallback level / change.
    sparkline: list[float] = []
    range_52w = [0.0, 0.0]
    try:
        h = fetcher.get_price_history(ticker, period="1y")
        if h is not None and not h.empty and "Close" in h.columns:
            closes = h["Close"].astype(float).dropna()
            if len(closes):
                if level is None:
                    level = float(closes.iloc[-1])
                if change_pct == 0.0 and len(closes) >= 2:
                    prev = float(closes.iloc[-2])
                    if prev:
                        change_pct = (float(closes.iloc[-1]) - prev) / prev * 100.0
                sparkline = [round(float(v), 4) for v in closes.tail(30).tolist()]
                range_52w = [round(float(closes.min()), 2),
                             round(float(closes.max()), 2)]
    except Exception:
        pass

    if level is None:
        return None

    return {
        "ticker":        ticker,
        "name":          display,
        "level":         round(level, 2),
        "change_1d_pct": round(change_pct, 2),
        "range_52w":     range_52w,
        "sparkline_30d": sparkline,
        "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_stale":      False,
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
                pass
        if usdkrw_level:
            out.append({
                "ticker":        "USDKRW",
                "name":          "USD / KRW",
                "level":         round(usdkrw_level, 2),
                "change_1d_pct": 0.0,  # fx_service doesn't track d/d yet
                "range_52w":     [0.0, 0.0],
                "sparkline_30d": [],
                "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "is_stale":      False,
            })

    # Only cache successful responses. Caching a thin failure for 30s locks
    # users into mock-looking data for the whole cache window — better to
    # re-try upstream on every request until it succeeds.
    if out:
        _indices_cache[cache_key] = {"ts": now, "data": out}

    return jsonify(out)


@market_bp.route("/dividend/<ticker>")
@api_auth
def dividend_data(ticker):
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    try:
        import fmp_service as fmp
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
        logger.error(f"Dividend error {ticker}: {e}")
        return jsonify({"has_dividend": False, "error": "Unable to fetch dividend data"})
