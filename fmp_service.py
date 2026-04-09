"""
StockPilot — FMP (Financial Modeling Prep) Service
Replaces yfinance with official FMP API.
Free tier: 250 calls/day, 10/sec.
"""

import os
import time
import logging
import requests
import threading
import pandas as pd
from datetime import datetime, timedelta
from functools import lru_cache

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"
FMP_KEY = os.environ.get("FMP_API_KEY", "")

# ── In-memory cache ─────────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()
_daily_calls = 0
_daily_calls_reset = 0.0


def _get_cache(key, max_age):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() - entry["ts"] < max_age:
            return entry["data"]
    return None


def _set_cache(key, data):
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}


def _track_call():
    global _daily_calls, _daily_calls_reset
    now = time.time()
    if now - _daily_calls_reset > 86400:
        _daily_calls = 0
        _daily_calls_reset = now
    _daily_calls += 1
    if _daily_calls > 240:
        logger.warning(f"FMP daily calls: {_daily_calls}/250 — nearing limit")


def _fmp_get(endpoint, params=None, timeout=10):
    """Core FMP API caller with rate tracking."""
    if not FMP_KEY:
        logger.error("FMP_API_KEY not set")
        return None
    _track_call()
    url = f"{FMP_BASE}{endpoint}"
    p = {"apikey": FMP_KEY}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"FMP {endpoint} returned {r.status_code}")
        return None
    except Exception as e:
        logger.warning(f"FMP {endpoint} failed: {e}")
        return None


# ── Quote (realtime-ish price) ──────────────────────────────────

def get_quote(ticker):
    """Get current quote. Cache 30s."""
    cache_key = f"quote:{ticker}"
    cached = _get_cache(cache_key, 30)
    if cached:
        return cached
    data = _fmp_get(f"/quote", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result
    return None


def get_quotes_batch(tickers):
    """Get multiple quotes in one call. Cache 30s."""
    symbols = ",".join(tickers)
    cache_key = f"batch_quote:{symbols}"
    cached = _get_cache(cache_key, 30)
    if cached:
        return cached
    data = _fmp_get(f"/quote", {"symbol": symbols})
    if data and isinstance(data, list):
        result = {item["symbol"]: item for item in data}
        _set_cache(cache_key, result)
        return result
    return {}


def get_price(ticker):
    """Get last price for a ticker. Returns float or None."""
    q = get_quote(ticker)
    if q:
        return q.get("price")
    return None


# ── Historical OHLCV ────────────────────────────────────────────

def get_history(ticker, period="3mo"):
    """Get historical daily OHLCV. Returns pandas DataFrame like yfinance.
    Cache 1 hour.
    """
    cache_key = f"history:{ticker}:{period}"
    cached = _get_cache(cache_key, 3600)
    if cached is not None:
        return cached

    # Map period to date range
    today = datetime.now()
    period_map = {
        "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825,
        "5d": 5, "1d": 1,
    }
    days = period_map.get(period, 90)
    from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    # Check if it's an index
    if ticker.startswith("^"):
        data = _fmp_get("/index-historical-price-eod/full", {
            "symbol": ticker, "from": from_date, "to": to_date
        })
    else:
        data = _fmp_get("/historical-price-eod/full", {
            "symbol": ticker, "from": from_date, "to": to_date
        })

    if not data:
        _set_cache(cache_key, pd.DataFrame())
        return pd.DataFrame()

    # FMP returns {"historical": [...]} or direct list
    records = data.get("historical", data) if isinstance(data, dict) else data
    if not isinstance(records, list) or len(records) == 0:
        _set_cache(cache_key, pd.DataFrame())
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Standardize column names to match yfinance format
    col_map = {
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "adjClose": "Adj Close",
        "volume": "Volume",
    }
    df = df.rename(columns=col_map)

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()

    # Ensure required columns exist
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = 0

    _set_cache(cache_key, df)
    return df


def get_history_batch(tickers, period="5d"):
    """Get history for multiple tickers. Returns dict of DataFrames."""
    result = {}
    for ticker in tickers:
        result[ticker] = get_history(ticker, period)
    return result


# ── Company Profile ─────────────────────────────────────────────

def get_profile(ticker):
    """Get company profile (name, sector, marketCap, beta, etc). Cache 6h."""
    cache_key = f"profile:{ticker}"
    cached = _get_cache(cache_key, 6 * 3600)
    if cached:
        return cached
    data = _fmp_get("/profile", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result
    return {}


def get_info(ticker):
    """Mimic yfinance .info dict. Combines profile + ratios. Cache 6h."""
    cache_key = f"info:{ticker}"
    cached = _get_cache(cache_key, 6 * 3600)
    if cached:
        return cached

    profile = get_profile(ticker)
    ratios = get_ratios_ttm(ticker)
    metrics = get_key_metrics_ttm(ticker)

    info = {}
    if profile:
        info.update({
            "shortName": profile.get("companyName", ticker),
            "longName": profile.get("companyName", ticker),
            "longBusinessSummary": profile.get("description", ""),
            "sector": profile.get("sector", ""),
            "industry": profile.get("industry", ""),
            "marketCap": profile.get("mktCap", 0),
            "beta": profile.get("beta", 1.0),
            "price": profile.get("price", 0),
            "website": profile.get("website", ""),
            "ceo": profile.get("ceo", ""),
            "fullTimeEmployees": profile.get("fullTimeEmployees", 0),
            "country": profile.get("country", ""),
            "exchange": profile.get("exchangeShortName", ""),
            "currency": profile.get("currency", "USD"),
            "ipoDate": profile.get("ipoDate", ""),
            "image": profile.get("image", ""),
            "52WeekHigh": profile.get("range", "").split("-")[-1].strip() if profile.get("range") else 0,
            "52WeekLow": profile.get("range", "").split("-")[0].strip() if profile.get("range") else 0,
            "dividendYield": profile.get("lastDiv", 0) / profile.get("price", 1) if profile.get("price") else 0,
            "isEtf": profile.get("isEtf", False),
        })
    if ratios:
        info.update({
            "trailingPE": ratios.get("peRatioTTM", 0),
            "forwardPE": ratios.get("peRatioTTM", 0),  # TTM as proxy
            "priceToBook": ratios.get("priceToBookRatioTTM", 0),
            "debtToEquity": ratios.get("debtEquityRatioTTM", 0),
            "returnOnEquity": ratios.get("returnOnEquityTTM", 0),
            "currentRatio": ratios.get("currentRatioTTM", 0),
            "netProfitMargin": ratios.get("netProfitMarginTTM", 0),
            "grossProfitMargin": ratios.get("grossProfitMarginTTM", 0),
            "operatingProfitMargin": ratios.get("operatingProfitMarginTTM", 0),
        })
    if metrics:
        info.update({
            "trailingEps": metrics.get("epsTTM", 0),
            "revenueGrowth": metrics.get("revenuePerShareTTM", 0),
            "revenuePerShare": metrics.get("revenuePerShareTTM", 0),
        })

    _set_cache(cache_key, info)
    return info


# ── Financial Ratios ────────────────────────────────────────────

def get_ratios_ttm(ticker):
    """Trailing 12-month ratios. Cache 6h."""
    cache_key = f"ratios_ttm:{ticker}"
    cached = _get_cache(cache_key, 6 * 3600)
    if cached:
        return cached
    data = _fmp_get("/ratios-ttm", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result
    return {}


def get_key_metrics_ttm(ticker):
    """Key metrics TTM. Cache 6h."""
    cache_key = f"metrics_ttm:{ticker}"
    cached = _get_cache(cache_key, 6 * 3600)
    if cached:
        return cached
    data = _fmp_get("/key-metrics-ttm", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result
    return {}


# ── News ────────────────────────────────────────────────────────

def get_news(ticker, limit=15):
    """Per-ticker news. Cache 30min."""
    cache_key = f"news:{ticker}"
    cached = _get_cache(cache_key, 30 * 60)
    if cached:
        return cached
    data = _fmp_get("/news/stock", {"symbol": ticker, "limit": limit})
    if data and isinstance(data, list):
        _set_cache(cache_key, data)
        return data
    return []


# ── Forex (Exchange Rate) ──────────────────────────────────────

def get_fx_rate(pair="USDKRW"):
    """Get forex rate. Cache 5s for near-realtime."""
    cache_key = f"fx:{pair}"
    cached = _get_cache(cache_key, 5)
    if cached:
        return cached
    data = _fmp_get("/fx", {"symbol": pair})
    if data and isinstance(data, list) and len(data) > 0:
        rate = data[0].get("price", 0) or data[0].get("ask", 0)
        if rate > 100:  # Sanity check for USDKRW
            _set_cache(cache_key, rate)
            return rate
    return None


# ── Earnings Calendar ───────────────────────────────────────────

def get_earnings_calendar(ticker=None, days_ahead=30):
    """Get upcoming earnings. Cache 6h."""
    cache_key = f"earnings:{ticker or 'all'}"
    cached = _get_cache(cache_key, 6 * 3600)
    if cached:
        return cached

    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    params = {"from": today, "to": future}
    if ticker:
        params["symbol"] = ticker

    data = _fmp_get("/earnings-calendar", params)
    if data and isinstance(data, list):
        _set_cache(cache_key, data)
        return data
    return []


# ── Dividends ───────────────────────────────────────────────────

def get_dividends(ticker):
    """Get dividend data. Cache 6h."""
    cache_key = f"dividends:{ticker}"
    cached = _get_cache(cache_key, 6 * 3600)
    if cached:
        return cached
    data = _fmp_get("/dividends", {"symbol": ticker})
    if data and isinstance(data, list):
        _set_cache(cache_key, data)
        return data
    return []


# ── Intraday (1min bars) ───────────────────────────────────────

def get_intraday(ticker, interval="1min"):
    """Get intraday bars. Cache 60s."""
    cache_key = f"intraday:{ticker}:{interval}"
    cached = _get_cache(cache_key, 60)
    if cached is not None:
        return cached

    # Map interval
    interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1hour"}
    fmp_interval = interval_map.get(interval, interval)

    data = _fmp_get(f"/historical-chart/{fmp_interval}/{ticker}")
    if data and isinstance(data, list):
        df = pd.DataFrame(data)
        if "date" in df.columns:
            df["Date"] = pd.to_datetime(df["date"])
            df = df.set_index("Date").sort_index()
            col_map = {"open": "Open", "high": "High", "low": "Low",
                       "close": "Close", "volume": "Volume"}
            df = df.rename(columns=col_map)
        _set_cache(cache_key, df)
        return df

    _set_cache(cache_key, pd.DataFrame())
    return pd.DataFrame()


# ── Sector Performance ──────────────────────────────────────────

def get_sector_performance():
    """Get sector performance. Cache 30min."""
    cache_key = "sector_perf"
    cached = _get_cache(cache_key, 30 * 60)
    if cached:
        return cached
    data = _fmp_get("/sector-performance")
    if data and isinstance(data, list):
        _set_cache(cache_key, data)
        return data
    return []


# ── Korean Stock Helper ─────────────────────────────────────────

def normalize_ticker(ticker):
    """Convert Korean ticker format for FMP.
    Korean stocks (.KS/.KQ) are NOT supported on FMP free tier.
    Use KIS API instead. This returns None for Korean tickers.
    """
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return None  # Signal to use KIS API
    return ticker


# ── API Health ──────────────────────────────────────────────────

def get_api_usage():
    """Return current API usage stats."""
    return {
        "daily_calls": _daily_calls,
        "daily_limit": 250,
        "remaining": max(0, 250 - _daily_calls),
        "cache_entries": len(_cache),
    }


def is_available():
    """Check if FMP API key is configured."""
    return bool(FMP_KEY)
