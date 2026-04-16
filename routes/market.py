"""Market data routes: overview, macro, sectors, news, prices, chart, etc."""
import json
import logging
import time as _time
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Position, SignalCache
from services import fx_service
from services.container import engine, fetcher, realtime
from .decorators import api_auth

logger = logging.getLogger(__name__)

market_bp = Blueprint("market", __name__, url_prefix="/api")

_macro_cache: dict = {"data": None, "ts": 0.0}


@market_bp.route("/search")
@api_auth
def search_stocks():
    """Fuzzy stock search — supports company names, partial tickers, Korean names.
    Uses FMP search API for US + local KOREAN_NAMES registry for KR stocks."""
    query = (request.args.get("q") or "").strip()
    if len(query) < 1:
        return jsonify({"results": []})

    results = []
    seen = set()

    # 1) Search Korean stock registry (name + ticker match)
    from data_fetcher import KOREAN_NAMES
    # Korean display names for Korean-language search
    _KR_NAMES = {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스",
        "035420.KS": "네이버", "035720.KS": "카카오",
        "005380.KS": "현대자동차", "000270.KS": "기아",
        "005490.KS": "포스코홀딩스", "051910.KS": "LG화학",
        "066570.KS": "LG전자", "068270.KS": "셀트리온",
        "373220.KS": "LG에너지솔루션", "207940.KS": "삼성바이오로직스",
        "003550.KS": "LG", "096770.KS": "SK이노베이션",
        "017670.KS": "SK텔레콤", "030200.KS": "KT",
        "105560.KS": "KB금융", "086790.KS": "하나금융지주",
        "055550.KS": "신한지주", "000810.KS": "삼성화재",
        "032830.KS": "삼성생명", "009150.KS": "삼성전기",
        "028260.KS": "삼성물산", "010140.KS": "삼성중공업",
        "047050.KS": "크래프톤", "263750.KS": "펄어비스",
        "035900.KQ": "JYP Ent.", "041510.KQ": "에스엠",
        "122870.KQ": "YG Ent.", "352820.KS": "하이브",
        "377300.KS": "카카오페이", "403550.KS": "카카오뱅크",
    }
    ql = query.lower()
    for ticker_code, name_en in KOREAN_NAMES.items():
        code_only = ticker_code.replace(".KS", "").replace(".KQ", "")
        name_kr = _KR_NAMES.get(ticker_code, "")
        if (ql in name_en.lower() or ql in name_kr or ql in code_only
                or ql in ticker_code.lower()):
            results.append({
                "ticker": ticker_code, "name": f"{name_kr} ({name_en})" if name_kr else name_en,
                "exchange": "KOSDAQ" if ticker_code.endswith(".KQ") else "KOSPI",
                "currency": "KRW", "is_korean": True,
            })
            seen.add(ticker_code)

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

    return jsonify({"results": results[:15]})


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
                c.updated_at = datetime.utcnow()
            except Exception:
                pass
    db.session.commit()
    return jsonify({"prices": prices, "updated_at": datetime.utcnow().isoformat(),
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
    result = {"macro": macro, "gs_view": gs_view, "cached_at": datetime.utcnow().isoformat()}
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
            last_updated_iso = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
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
@api_auth
def market_status():
    from zoneinfo import ZoneInfo
    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))

    US_HOLIDAYS = {
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
        "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    }
    KR_HOLIDAYS = {
        "2026-01-01", "2026-01-28", "2026-01-29", "2026-01-30",
        "2026-03-01", "2026-05-05", "2026-05-24", "2026-06-06",
        "2026-08-15", "2026-09-24", "2026-09-25", "2026-09-26",
        "2026-10-03", "2026-10-09", "2026-12-25",
    }

    et = now_utc.astimezone(ZoneInfo("America/New_York"))
    us_min = et.hour * 60 + et.minute
    us_date = et.strftime("%Y-%m-%d")
    if et.weekday() >= 5 or us_date in US_HOLIDAYS:
        us_status = "CLOSED"
        us_label = "Holiday" if us_date in US_HOLIDAYS else "Weekend"
    elif 570 <= us_min < 960:
        us_status, us_label = "OPEN", "Market Open"
    elif 240 <= us_min < 570:
        us_status, us_label = "PRE_MARKET", "Pre-Market"
    elif 960 <= us_min < 1200:
        us_status, us_label = "AFTER_HOURS", "After Hours"
    else:
        us_status, us_label = "CLOSED", "Closed"

    kst = now_utc.astimezone(ZoneInfo("Asia/Seoul"))
    kr_min = kst.hour * 60 + kst.minute
    kr_date = kst.strftime("%Y-%m-%d")
    if kst.weekday() >= 5 or kr_date in KR_HOLIDAYS:
        kr_status = "CLOSED"
        kr_label = "Holiday" if kr_date in KR_HOLIDAYS else "Weekend"
    elif 540 <= kr_min < 930:
        kr_status, kr_label = "OPEN", "Market Open"
    else:
        kr_status, kr_label = "CLOSED", "Closed"

    return jsonify({
        "us": {"status": us_status, "label": us_label, "time": et.strftime("%H:%M ET")},
        "kr": {"status": kr_status, "label": kr_label, "time": kst.strftime("%H:%M KST")},
    })


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
            start = datetime.utcnow() - timedelta(days=days)
            req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=tf, start=start, limit=500)
            bars = realtime.alpaca_client.get_stock_bars(req)
            data = [{"date": bar.timestamp.strftime("%Y-%m-%d %H:%M"),
                     "close": round(float(bar.close), 2),
                     "volume": int(bar.volume)} for bar in bars[ticker]]
            if data:
                return jsonify({"ticker": ticker, "period": period, "data": data, "source": "alpaca"})
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
                                "data": data, "source": source})
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
        return jsonify({"ticker": ticker, "period": period, "data": data, "source": "fmp"})
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
                            "ticker": p.ticker, "name": sd.get("name", p.ticker),
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
                    "ticker": sc.ticker, "name": sd.get("name", sc.ticker),
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
    try:
        import fmp_service as fmp
        info = fmp.get_info(ticker)
        return jsonify({
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "summary": info.get("longBusinessSummary", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "website": info.get("website", ""),
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country", ""),
            "market_cap": info.get("marketCap"),
            "currency": "KRW" if ticker.endswith(".KS") or ticker.endswith(".KQ") else "USD",
        })
    except Exception as e:
        logger.error(f"Profile error {ticker}: {e}")
        return jsonify({"error": "Unable to fetch company profile"}), 500


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
