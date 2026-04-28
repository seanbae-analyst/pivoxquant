"""
PivoxQuant — FMP (Financial Modeling Prep) Service
Official FMP API for market data.
Premium $29 plan: 750 req/min, no daily cap. We keep an env-configurable
soft daily limit (FMP_DAILY_SOFT_LIMIT, default 10000) as a runaway-usage
safety net. Set FMP_DAILY_SOFT_LIMIT=250 if downgrading to Starter $14.
"""

import os
import time
import logging
import requests
import threading
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/stable"
FMP_KEY = os.environ.get("FMP_API_KEY", "")

# FMP Premium $29 plan: 750 req/min, no daily cap. We keep a soft daily limit
# as a safety net against runaway usage (bug/attack) — env-configurable.
_FMP_DAILY_SOFT_LIMIT = int(os.environ.get("FMP_DAILY_SOFT_LIMIT", "10000"))
_FMP_BUDGET_STALE_PCT = float(os.environ.get("FMP_BUDGET_STALE_PCT", "0.88"))  # 88% → stale fallback
_FMP_BUDGET_HARD_STOP_PCT = float(os.environ.get("FMP_BUDGET_HARD_STOP_PCT", "0.99"))  # 99% → block

# ── Cache TTL Constants ─────────────────────────────────────────
# Price-adjacent TTLs (quote/intraday/fx) are market-aware at the call
# site via ``services.cache_ttl``. The constants below are fallbacks
# used only when the helper import fails (e.g. scheduler warm-up).
TTL_QUOTE      = 30          # off-hours fallback — helper returns 5s intraday
TTL_INTRADAY   = 60          # off-hours fallback — helper returns 10s intraday
TTL_PRICE_HIST = 3600        # 1 hour — historical bars (unchanged)
TTL_NEWS       = 6 * 3600    # 6 hours — news is low-weight (3%), no need for frequent refresh
TTL_FUNDAMENTAL = 24 * 3600  # 24 hours — ratios, metrics, earnings
TTL_PROFILE    = 7 * 24 * 3600  # 7 days — company profile rarely changes
TTL_SECTOR     = 30 * 60     # 30 minutes
TTL_FX         = 5           # off-hours fallback — helper returns 5s intraday, 30s closed


def _quote_ttl() -> int:
    """Market-aware quote TTL — helper import guarded for bootstrap paths."""
    try:
        from services.cache_ttl import quote_ttl
        return quote_ttl()
    except Exception:
        return TTL_QUOTE


def _intraday_ttl() -> int:
    try:
        from services.cache_ttl import intraday_ttl
        return intraday_ttl()
    except Exception:
        return TTL_INTRADAY


def _fx_ttl() -> int:
    try:
        from services.cache_ttl import fx_ttl
        return fx_ttl()
    except Exception:
        return TTL_FX

# ── In-memory cache ─────────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()
_daily_calls = 0
_daily_calls_reset = 0.0

# 402 tracking — plan-gated endpoints should short-circuit after repeated failures
# so callers can fall back to Alpaca/KIS without wasting network calls.
_endpoint_402_counts = {}       # {endpoint_path: count}
_endpoint_402_cooldown = {}     # {endpoint_path: unix_ts until cooldown expires}
_ENDPOINT_402_THRESHOLD = 3     # After 3 consecutive 402s, block endpoint
_ENDPOINT_402_COOLDOWN = 1800   # 30 min cooldown

# Budget thresholds — Premium $29 plan default (10k/day soft cap).
# Override via FMP_DAILY_SOFT_LIMIT env var (e.g. set to 250 if downgrading to Starter).
_BUDGET_STALE_THRESHOLD = int(_FMP_DAILY_SOFT_LIMIT * _FMP_BUDGET_STALE_PCT)
_BUDGET_HARD_STOP = int(_FMP_DAILY_SOFT_LIMIT * _FMP_BUDGET_HARD_STOP_PCT)

# Defensive: misconfigured env (e.g. STALE_PCT > HARD_STOP_PCT) would let
# stale-mode trigger before exhaustion, leaving hard_stop unreachable. Force
# stale_threshold ≤ hard_stop and hard_stop ≥ 1 to fail-fast at import time.
if _BUDGET_STALE_THRESHOLD > _BUDGET_HARD_STOP:
    logger.error(
        f"FMP budget config inverted (stale={_BUDGET_STALE_THRESHOLD} > hard_stop={_BUDGET_HARD_STOP}); "
        f"clamping stale to hard_stop. Check FMP_BUDGET_STALE_PCT vs FMP_BUDGET_HARD_STOP_PCT."
    )
    _BUDGET_STALE_THRESHOLD = _BUDGET_HARD_STOP
if _BUDGET_HARD_STOP < 1:
    logger.error(
        f"FMP_DAILY_SOFT_LIMIT={_FMP_DAILY_SOFT_LIMIT} produces hard_stop<1; "
        f"forcing minimum 1 to avoid blocking every call."
    )
    _BUDGET_HARD_STOP = 1
    _BUDGET_STALE_THRESHOLD = min(_BUDGET_STALE_THRESHOLD, 1)


def _get_cache(key, max_age):
    """Return cached data if within max_age. Returns None otherwise."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() - entry["ts"] < max_age:
            return entry["data"]
    return None


def _get_cache_stale(key):
    """Return cached data regardless of age (stale-while-revalidate).
    Used when API budget is running low to avoid 429 errors."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry:
            return entry["data"]
    return None


def _set_cache(key, data):
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}


def _is_budget_stale():
    """True when we should prefer stale cache over fresh API calls."""
    return _daily_calls >= _BUDGET_STALE_THRESHOLD


def _is_budget_exhausted():
    """True when we must stop making API calls entirely."""
    return _daily_calls >= _BUDGET_HARD_STOP


def _track_call():
    global _daily_calls, _daily_calls_reset
    now = time.time()
    if now - _daily_calls_reset > 86400:
        _daily_calls = 0
        _daily_calls_reset = now
    _daily_calls += 1
    if _daily_calls >= _BUDGET_HARD_STOP:
        logger.warning(f"FMP HARD STOP: {_daily_calls}/{_FMP_DAILY_SOFT_LIMIT} calls used — blocking further API calls")
    elif _daily_calls >= _BUDGET_STALE_THRESHOLD:
        logger.warning(f"FMP budget low: {_daily_calls}/{_FMP_DAILY_SOFT_LIMIT} calls — returning stale cache when available")


def _is_endpoint_blocked(endpoint):
    """Returns True if this endpoint hit 3+ consecutive 402s and is in cooldown."""
    with _cache_lock:
        until = _endpoint_402_cooldown.get(endpoint, 0)
        return time.time() < until


def _record_402(endpoint):
    """Track 402 responses per endpoint. Trip cooldown after threshold."""
    with _cache_lock:
        count = _endpoint_402_counts.get(endpoint, 0) + 1
        _endpoint_402_counts[endpoint] = count
        if count >= _ENDPOINT_402_THRESHOLD:
            _endpoint_402_cooldown[endpoint] = time.time() + _ENDPOINT_402_COOLDOWN
            logger.warning(
                f"FMP endpoint {endpoint} disabled for {_ENDPOINT_402_COOLDOWN}s "
                f"after {count} consecutive 402s — callers should use Alpaca/KIS fallback"
            )


def _record_success(endpoint):
    """Reset 402 counter on successful call."""
    with _cache_lock:
        if endpoint in _endpoint_402_counts:
            _endpoint_402_counts[endpoint] = 0


def _fmp_get(endpoint, params=None, timeout=5):
    """Core FMP API caller with rate tracking and budget enforcement.

    Returns None on any failure. Callers should treat None as "try fallback source"
    rather than "no data". Use stale cache where appropriate for defensive reads.

    timeout capped at 5s (was 10s) — Railway default request timeout is 30s and
    serial FMP fallback chains were causing 10-17s endpoint latencies.
    """
    global _daily_calls
    if not FMP_KEY:
        logger.error("FMP_API_KEY not set")
        return None
    if _is_budget_exhausted():
        logger.warning(f"FMP call blocked (budget exhausted at {_daily_calls}/{_FMP_DAILY_SOFT_LIMIT}): {endpoint}")
        return None
    if _is_endpoint_blocked(endpoint):
        # Endpoint is in 402 cooldown — short-circuit without network call
        logger.debug(f"FMP {endpoint} skipped (402 cooldown active)")
        return None
    _track_call()
    url = f"{FMP_BASE}{endpoint}"
    p = {"apikey": FMP_KEY}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=timeout)
        if r.status_code == 200:
            _record_success(endpoint)
            return r.json()
        if r.status_code == 429:
            logger.error(f"FMP 429 rate limited on {endpoint} — stopping further calls this cycle")
            _daily_calls = max(_daily_calls, _BUDGET_HARD_STOP)
        elif r.status_code == 402:
            # 402 = FMP plan-gated endpoint OR per-second rate limit (10/sec on free plan).
            # Don't count this against the daily budget — the call wasn't served.
            with _cache_lock:
                _daily_calls = max(0, _daily_calls - 1)
            _record_402(endpoint)
            logger.warning(
                f"FMP {endpoint} returned 402 (plan-gated or rate limited) — "
                f"caller should fall back to Alpaca/KIS"
            )
        else:
            logger.warning(f"FMP {endpoint} returned {r.status_code}")
        return None
    except Exception as e:
        logger.warning(f"FMP {endpoint} failed: {e}")
        return None


def endpoint_is_blocked(endpoint):
    """Public helper — callers can proactively skip FMP if endpoint is cooling down."""
    return _is_endpoint_blocked(endpoint)


# ── Alpaca Market Data fallback (lazy import) ───────────────────
# Replaces the old yfinance adapter. Alpaca is a licensed US broker whose
# market-data API is explicitly cleared for commercial use — yfinance
# scrapes Yahoo and violates that ToS for a paid service.
# Imported lazily so unit tests that never exercise the fallback path
# don't pay the SDK import cost.

def _ama():
    """Return the Alpaca market-data adapter module or None (import errors swallowed)."""
    try:
        from services.data import alpaca_market_adapter as ama
        return ama
    except Exception as exc:  # pragma: no cover — import path
        logger.info("alpaca_market_adapter unavailable (%s) — fallback disabled", exc)
        return None


# Backwards-compat alias: a few tests still patch `_yfa` by name. Keeping
# the name pointed at the new adapter is safer than a rename sweep that
# might miss a patch site and silently disable the fallback.
_yfa = _ama


def _is_us_ticker(ticker):
    """Alpaca Market Data covers US-listed equities (NYSE/NASDAQ/ARCA).
    KR tickers route through the KIS adapter instead — Alpaca has no
    KRX coverage and Yahoo's KR data was the old (illegal) path."""
    if not isinstance(ticker, str):
        return False
    return not (ticker.endswith(".KS") or ticker.endswith(".KQ"))


def _class_share_alt(ticker):
    """Return the alternative class-share form of ``ticker``, or None.

    FMP's stable endpoints are inconsistent about class-share separators:
    ``/quote?symbol=BRK.B`` returns ``[]`` while ``BRK-B`` returns data,
    but on some endpoints (historical, profile) only the dotted form
    resolves. When a fetch comes back empty, the caller can retry with
    the alternate form. Returns None for tickers where a class-share
    retry would be meaningless (Korean, indices, plain symbols).

    Mapping:
      ``BRK.B`` → ``BRK-B``
      ``BRK-B`` → ``BRK.B``
      ``AAPL``  → None
      ``005930.KS`` → None  (KR suffix, not a class share)
      ``^GSPC`` → None
    """
    if not isinstance(ticker, str) or not ticker:
        return None
    if ticker.startswith("^"):
        return None
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return None
    if "." in ticker:
        # Dot form (BRK.B) — convert to dash. Only treat the last single
        # alphabetic suffix as a class share; anything longer (BRK.AXY)
        # is not a class share and shouldn't be rewritten.
        base, _, suffix = ticker.rpartition(".")
        if base and len(suffix) == 1 and suffix.isalpha():
            return f"{base}-{suffix}"
        return None
    if "-" in ticker:
        base, _, suffix = ticker.rpartition("-")
        if base and len(suffix) == 1 and suffix.isalpha():
            return f"{base}.{suffix}"
        return None
    return None


# ── Quote (realtime-ish price) ──────────────────────────────────

def get_quote(ticker):
    """Get current quote. Cache 30s. Stale-while-revalidate when budget low.

    Fallback chain (US tickers only):
      1. 30s TTL cache
      2. FMP /quote
      3. Alpaca Market Data — when FMP returns None / 402 / budget-out
      4. Stale cache (any age)
    """
    cache_key = f"quote:{ticker}"
    cached = _get_cache(cache_key, _quote_ttl())
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/quote", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result

    # Class-share retry: FMP's stable /quote resolves BRK-B but not BRK.B
    # (confirmed: dotted form returns [], dash form returns full payload).
    # Parallel logic to get_history's retry block — identical guards.
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/quote", {"symbol": alt})
        if data and isinstance(data, list) and len(data) > 0:
            result = data[0]
            logger.info("FMP quote resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, result)
            return result

    # FMP miss → Alpaca fallback (US tickers only)
    if _is_us_ticker(ticker):
        ama = _ama()
        if ama is not None:
            a_quote = ama.get_quote(ticker)
            if a_quote:
                logger.info("FMP quote miss for %s — served via Alpaca fallback", ticker)
                _set_cache(cache_key, a_quote)
                return a_quote

    # Final resort: any stale cache rather than None so callers can show *something*.
    stale = _get_cache_stale(cache_key)
    if stale:
        return stale
    return None


def get_quotes_batch(tickers):
    """Get multiple quotes. Cache 30s. Stale-while-revalidate when budget low.
    Tries comma-separated batch first (paid plans); falls back to per-ticker calls.
    Also populates per-ticker quote cache so subsequent get_quote(ticker) calls are free.
    """
    if not tickers:
        return {}
    symbols = ",".join(tickers)
    cache_key = f"batch_quote:{symbols}"
    cached = _get_cache(cache_key, _quote_ttl())
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale

    # Try batch first (works on paid plans with comma-separated symbols)
    data = _fmp_get("/quote", {"symbol": symbols})
    if data and isinstance(data, list) and len(data) > 0:
        result = {item["symbol"]: item for item in data}
        _set_cache(cache_key, result)
        for item in data:
            sym = item.get("symbol", "")
            if sym:
                _set_cache(f"quote:{sym}", item)
        return result

    # Fallback: per-ticker calls (free plan doesn't support comma-separated)
    result = {}
    for ticker in tickers:
        q = get_quote(ticker)
        if q:
            result[q.get("symbol", ticker)] = q
    if result:
        _set_cache(cache_key, result)
    return result


def get_price(ticker):
    """Get last price for a ticker. Returns float or None."""
    q = get_quote(ticker)
    if q:
        return q.get("price")
    return None


# ── Historical OHLCV ────────────────────────────────────────────

def _get_history_kr(ticker, period="3mo"):
    """Korean stocks (.KS/.KQ) historical OHLCV via the KIS public API.

    Replaces the legacy pyKRX path. KIS is a licensed broker whose Open
    API is commercial-use-cleared; pyKRX scraped the KRX data portal in
    a legal grey area. The DataFrame schema is identical to FMP:
    index=DatetimeIndex, columns=[Open, High, Low, Close, Volume].

    Cache key + TTL + stale-while-revalidate are shared with the FMP
    history cache so a 3mo window for a Korean ticker is only fetched
    once per hour. Returns an empty DataFrame on any failure — never raises.
    """
    cache_key = f"history:{ticker}:{period}"
    cached = _get_cache(cache_key, TTL_PRICE_HIST)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale

    try:
        from services.data import kis_market_adapter as kma
    except Exception as exc:  # pragma: no cover — import path
        logger.warning(f"kis_market_adapter unavailable: {exc}")
        _set_cache(cache_key, pd.DataFrame())
        return pd.DataFrame()

    df = kma.get_history(ticker, period)
    if df is None or df.empty:
        _set_cache(cache_key, pd.DataFrame())
        return pd.DataFrame()

    # kis_market_adapter already returns [Open, High, Low, Close, Volume]
    # with a DatetimeIndex named 'Date' — cache as-is.
    _set_cache(cache_key, df)
    return df


# Backwards-compat alias — a handful of tests import this by its old name.
_get_history_pykrx = _get_history_kr


def get_history(ticker, period="3mo"):
    """Get historical daily OHLCV. Returns pandas DataFrame with standard OHLCV columns.
    Cache 1 hour. Stale-while-revalidate when budget low.

    Korean tickers (.KS/.KQ) are dispatched to pyKRX since FMP does not
    cover KRX — this keeps engine.portfolio_analytics() working for mixed
    US/KR portfolios (Sharpe/MaxDD/AnnVol were previously null).
    """
    # Korean tickers → KIS adapter (FMP doesn't cover KRX)
    if isinstance(ticker, str) and (ticker.endswith(".KS") or ticker.endswith(".KQ")):
        return _get_history_kr(ticker, period)

    cache_key = f"history:{ticker}:{period}"
    cached = _get_cache(cache_key, TTL_PRICE_HIST)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale

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

    # Stable API: both index (^GSPC) and stock tickers use the same endpoint
    data = _fmp_get("/historical-price-eod/full", {
        "symbol": ticker, "from": from_date, "to": to_date
    })

    # Class-share retry: some FMP endpoints resolve BRK.B but not BRK-B
    # (or vice versa). If the first form returns empty, retry with the
    # alternate. Shares logic with /quote, /profile, etc. via
    # _class_share_alt() so the rule stays identical across endpoints.
    if not data:
        alt = _class_share_alt(ticker)
        if alt:
            data = _fmp_get("/historical-price-eod/full", {
                "symbol": alt, "from": from_date, "to": to_date
            })
            if data:
                logger.info("FMP history resolved %s via class-share alt %s", ticker, alt)

    if not data:
        # FMP returned nothing (402 plan-gated, index symbol, or network
        # failure). Alpaca Market Data covers all US-listed equities and
        # major ETFs — try it before giving up. Indices (^GSPC/^IXIC) are
        # not supported by Alpaca; those stay on FMP or stale cache.
        ama = _ama()
        if ama is not None:
            a_df = ama.get_history(ticker, period)
            if a_df is not None and not a_df.empty:
                logger.info(
                    "FMP history miss for %s (%s) — served via Alpaca fallback",
                    ticker, period,
                )
                _set_cache(cache_key, a_df)
                return a_df
        _set_cache(cache_key, pd.DataFrame())
        return pd.DataFrame()

    # FMP returns {"historical": [...]} or direct list
    records = data.get("historical", data) if isinstance(data, dict) else data
    if not isinstance(records, list) or len(records) == 0:
        _set_cache(cache_key, pd.DataFrame())
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Standardize column names to match expected OHLCV format
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
    """Get company profile (name, sector, marketCap, beta, etc). Cache 7 days."""
    cache_key = f"profile:{ticker}"
    cached = _get_cache(cache_key, TTL_PROFILE)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/profile", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result
    # Class-share retry (BRK.B ⇄ BRK-B etc).
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/profile", {"symbol": alt})
        if data and isinstance(data, list) and len(data) > 0:
            result = data[0]
            logger.info("FMP profile resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, result)
            return result
    return {}


def get_profiles_batch(tickers):
    """Get profiles for up to 50 tickers. Populates per-ticker cache.
    Tries comma-separated batch first (paid plans); falls back to per-ticker calls.
    Returns dict {symbol: profile_dict}.
    """
    if not tickers:
        return {}
    # Check which tickers already have cached profiles
    uncached = []
    result = {}
    for t in tickers[:50]:
        cached = _get_cache(f"profile:{t}", TTL_PROFILE)
        if cached:
            result[t] = cached
        else:
            uncached.append(t)
    if not uncached:
        return result

    # Try batch first (works on paid plans with comma-separated symbols)
    symbols = ",".join(uncached)
    data = _fmp_get("/profile", {"symbol": symbols})
    if data and isinstance(data, list) and len(data) > 0:
        for item in data:
            sym = item.get("symbol", "")
            if sym:
                _set_cache(f"profile:{sym}", item)
                result[sym] = item
        return result

    # Fallback: per-ticker calls (free plan doesn't support comma-separated)
    for t in uncached:
        profile = get_profile(t)
        if profile:
            result[t] = profile
    return result


def get_info(ticker):
    """Get unified stock info dict. Combines profile + ratios. Cache 24h (fundamental data)."""
    cache_key = f"info:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale

    profile = get_profile(ticker)
    ratios = get_ratios_ttm(ticker)
    metrics = get_key_metrics_ttm(ticker)

    info = {}
    if profile:
        # Stable API field names: marketCap (was mktCap), lastDividend (was lastDiv),
        # exchange (was exchangeShortName)
        last_div = profile.get("lastDividend") or profile.get("lastDiv") or 0
        price = profile.get("price", 0)
        info.update({
            "shortName": profile.get("companyName", ticker),
            "longName": profile.get("companyName", ticker),
            "longBusinessSummary": profile.get("description", ""),
            "sector": profile.get("sector", ""),
            "industry": profile.get("industry", ""),
            "marketCap": profile.get("marketCap") or profile.get("mktCap") or 0,
            "beta": profile.get("beta", 1.0),
            "price": price,
            "website": profile.get("website", ""),
            "ceo": profile.get("ceo", ""),
            "fullTimeEmployees": profile.get("fullTimeEmployees", 0),
            "country": profile.get("country", ""),
            "exchange": profile.get("exchangeShortName") or profile.get("exchange", ""),
            "currency": profile.get("currency", "USD"),
            "ipoDate": profile.get("ipoDate", ""),
            "image": profile.get("image", ""),
            "52WeekHigh": profile.get("range", "").split("-")[-1].strip() if profile.get("range") else 0,
            "52WeekLow": profile.get("range", "").split("-")[0].strip() if profile.get("range") else 0,
            "dividendYield": last_div / price if price else 0,
            "isEtf": profile.get("isEtf", False),
            "floatShares": profile.get("floatShares") or profile.get("sharesFloat"),
        })
    if ratios:
        # Stable API: peRatioTTM -> priceToEarningsRatioTTM,
        # debtEquityRatioTTM -> debtToEquityRatioTTM
        info.update({
            "trailingPE": ratios.get("priceToEarningsRatioTTM") or ratios.get("peRatioTTM") or 0,
            "forwardPE": ratios.get("priceToEarningsRatioTTM") or ratios.get("peRatioTTM") or 0,
            "priceToBook": ratios.get("priceToBookRatioTTM", 0),
            "debtToEquity": ratios.get("debtToEquityRatioTTM") or ratios.get("debtEquityRatioTTM") or 0,
            "returnOnEquity": ratios.get("returnOnEquityTTM", 0),
            "currentRatio": ratios.get("currentRatioTTM", 0),
            "netProfitMargin": ratios.get("netProfitMarginTTM", 0),
            "grossProfitMargin": ratios.get("grossProfitMarginTTM", 0),
            "operatingProfitMargin": ratios.get("operatingProfitMarginTTM", 0),
        })
    if metrics:
        # Stable API: epsTTM not in key-metrics; use netIncomePerShareTTM from ratios
        # revenuePerShareTTM moved to ratios-ttm
        eps = (ratios or {}).get("netIncomePerShareTTM") or metrics.get("epsTTM") or 0
        rev_per_share = (ratios or {}).get("revenuePerShareTTM") or metrics.get("revenuePerShareTTM") or 0
        # NOTE: revenueGrowth must be a YoY growth RATE (e.g. 0.12 = +12%), not an
        # absolute revenue-per-share figure. /key-metrics-ttm + /ratios-ttm do not
        # publish a TTM growth rate — populating revenueGrowth with revenuePerShare
        # was an upstream mismapping that surfaced as nonsense % values in the UI
        # (frontend renders `(value * 100).toFixed(1) + "%"`). Until we wire up
        # /income-statement-growth, leave revenueGrowth null so the UI renders "—"
        # honestly. revenuePerShare keeps the absolute figure for any callers that
        # actually want it.
        info.update({
            "trailingEps": eps,
            "revenueGrowth": None,
            "revenuePerShare": rev_per_share,
        })

    # ── Fundamentals fallback ──────────────────────────────────────
    # FMP Starter occasionally returns partial /ratios-ttm responses where
    # peRatioTTM / priceToEarningsRatioTTM are absent (observed on mega-cap
    # US tickers like AAPL/TSLA/NVDA/MSFT while BRK-B works). When that
    # happens, fall back to the /quote payload's `pe` + `eps` fields which
    # derive from the same underlying TTM series.
    if not info.get("trailingPE") or not info.get("trailingEps"):
        try:
            q = _fmp_get("/quote", {"symbol": ticker})
            if q and isinstance(q, list) and len(q) > 0:
                qr = q[0] or {}
                q_pe = qr.get("pe") or qr.get("peRatio")
                q_eps = qr.get("eps") or qr.get("earningsPerShare")
                if q_pe and not info.get("trailingPE"):
                    info["trailingPE"] = q_pe
                    info["forwardPE"] = info.get("forwardPE") or q_pe
                if q_eps and not info.get("trailingEps"):
                    info["trailingEps"] = q_eps
        except Exception as e:
            logger.debug(f"fundamentals quote-fallback failed for {ticker}: {e}")

    # ── KR fundamentals routing ────────────────────────────────────
    # FMP Starter has no KRX coverage, so US equities fallback-chain
    # above always comes back empty for `.KS` / `.KQ` tickers. Route
    # KR tickers through the licensed KIS `inquire-price` path which
    # publishes PER/EPS/PBR/시가총액 on a commercial ToS. Overlays on
    # any US fallback already populated above — never overwrites a
    # non-null value.
    if isinstance(ticker, str) and (ticker.endswith(".KS") or ticker.endswith(".KQ")):
        try:
            from services.data.kr_fundamentals import get_kr_fundamentals
            kr = get_kr_fundamentals(ticker)
            if kr:
                for k, v in kr.items():
                    if v is not None and not info.get(k):
                        info[k] = v
        except Exception as e:
            logger.debug(f"KR fundamentals routing failed for {ticker}: {e}")

    # ── Alpha Vantage fallback (US equities only) ─────────────────
    # FMP Starter omits P/E + EPS on NVDA/MSFT/TSLA/etc. AV free tier
    # (25 req/day) covers the gap. No-op when ALPHAVANTAGE_API_KEY is
    # unset, so this code is safe to ship before key provisioning.
    is_us_equity = isinstance(ticker, str) and not (
        ticker.endswith(".KS") or ticker.endswith(".KQ")
    )
    still_missing = not info.get("trailingPE") or not info.get("trailingEps")
    not_etf = not bool(info.get("isEtf"))
    if is_us_equity and still_missing and not_etf:
        try:
            from services.data.alpha_vantage_fundamentals import get_av_fundamentals
            av = get_av_fundamentals(ticker)
            if av:
                # Map AV schema (snake_case) onto FMP internal camelCase.
                av_map = {
                    "pe_ratio":       "trailingPE",
                    "forward_pe":     "forwardPE",
                    "eps":            "trailingEps",
                    "market_cap":     "marketCap",
                    "profit_margin":  "profitMargin",
                    "revenue_growth": "revenueGrowth",
                    "debt_equity":    "debtToEquity",
                }
                for av_key, fmp_key in av_map.items():
                    v = av.get(av_key)
                    if v is not None and not info.get(fmp_key):
                        info[fmp_key] = v
        except Exception as e:
            logger.debug(f"AV fundamentals routing failed for {ticker}: {e}")

    # ── Null-cache guard (US only) ─────────────────────────────────
    # If the critical fundamentals are still null for a non-ETF US
    # ticker, skip caching so the next request gets a fresh try.
    # ETFs legitimately lack P/E + EPS — caching null for them is
    # correct; we only want to retry when FMP returned a partial
    # payload for a regular equity.
    is_etf = bool(info.get("isEtf"))
    has_critical = bool(info.get("trailingPE")) or bool(info.get("trailingEps")) or bool(info.get("marketCap"))
    should_cache = is_etf or has_critical
    if should_cache:
        _set_cache(cache_key, info)
    else:
        logger.info(
            f"FMP get_info({ticker}): critical fundamentals all null + not ETF — "
            f"skipping cache so next request retries"
        )
    return info


# ── Financial Ratios ────────────────────────────────────────────

def get_ratios_ttm(ticker):
    """Trailing 12-month ratios. Cache 24h (fundamental data changes at most daily)."""
    cache_key = f"ratios_ttm:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/ratios-ttm", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/ratios-ttm", {"symbol": alt})
        if data and isinstance(data, list) and len(data) > 0:
            result = data[0]
            logger.info("FMP ratios-ttm resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, result)
            return result
    return {}


def get_key_metrics_ttm(ticker):
    """Key metrics TTM. Cache 24h (fundamental data changes at most daily)."""
    cache_key = f"metrics_ttm:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/key-metrics-ttm", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        result = data[0]
        _set_cache(cache_key, result)
        return result
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/key-metrics-ttm", {"symbol": alt})
        if data and isinstance(data, list) and len(data) > 0:
            result = data[0]
            logger.info("FMP key-metrics-ttm resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, result)
            return result
    return {}


# ── CAN SLIM fundamentals helpers ───────────────────────────────

def get_quarterly_income(ticker, quarters=8):
    """Get quarterly income statement records ordered most-recent-first.

    Returns list of dicts with keys like: date, period (Q1-Q4),
    calendarYear, eps, epsdiluted, revenue, netIncome, symbol.
    Returns [] on failure / 402 / budget-exhausted (caller should fallback).

    Cache 24h (quarterly data updates infrequently).
    """
    try:
        quarters = int(quarters)
    except (TypeError, ValueError):
        quarters = 8
    quarters = max(1, min(quarters, 40))

    cache_key = f"income_q:{ticker}:{quarters}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale

    data = _fmp_get("/income-statement", {
        "symbol": ticker, "period": "quarter", "limit": quarters,
    })
    if data and isinstance(data, list) and len(data) > 0:
        _set_cache(cache_key, data)
        return data
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/income-statement", {
            "symbol": alt, "period": "quarter", "limit": quarters,
        })
        if data and isinstance(data, list) and len(data) > 0:
            logger.info("FMP quarterly income resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, data)
            return data

    _set_cache(cache_key, [])
    return []


def get_annual_income(ticker, years=4):
    """Get annual income statement records ordered most-recent-first.

    Returns list of dicts (same shape as get_quarterly_income, period="FY").
    Cache 24h.
    """
    try:
        years = int(years)
    except (TypeError, ValueError):
        years = 4
    years = max(1, min(years, 20))

    cache_key = f"income_a:{ticker}:{years}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale

    data = _fmp_get("/income-statement", {
        "symbol": ticker, "period": "annual", "limit": years,
    })
    if data and isinstance(data, list) and len(data) > 0:
        _set_cache(cache_key, data)
        return data
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/income-statement", {
            "symbol": alt, "period": "annual", "limit": years,
        })
        if data and isinstance(data, list) and len(data) > 0:
            logger.info("FMP annual income resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, data)
            return data

    _set_cache(cache_key, [])
    return []


def get_quarterly_eps(ticker, quarters=8):
    """Return a list of {date, period, eps} dicts most-recent-first.

    Prefers `epsdiluted` when available (CAN SLIM convention), falls back
    to `eps`. Skips rows with missing EPS so callers can rely on numeric
    values. Returns [] when FMP data is unavailable.
    """
    rows = get_quarterly_income(ticker, quarters=quarters)
    out = []
    for r in rows or []:
        eps = r.get("epsdiluted")
        if eps in (None, 0):
            eps = r.get("eps")
        if eps is None:
            continue
        try:
            eps_f = float(eps)
        except (TypeError, ValueError):
            continue
        out.append({
            "date": r.get("date"),
            "period": r.get("period"),
            "calendarYear": r.get("calendarYear"),
            "eps": eps_f,
        })
    return out


def get_annual_eps(ticker, years=4):
    """Return a list of {date, calendarYear, eps} dicts most-recent-first."""
    rows = get_annual_income(ticker, years=years)
    out = []
    for r in rows or []:
        eps = r.get("epsdiluted")
        if eps in (None, 0):
            eps = r.get("eps")
        if eps is None:
            continue
        try:
            eps_f = float(eps)
        except (TypeError, ValueError):
            continue
        out.append({
            "date": r.get("date"),
            "calendarYear": r.get("calendarYear"),
            "eps": eps_f,
        })
    return out


def get_institutional_ownership(ticker):
    """Fetch institutional ownership summary if FMP plan allows.

    Tries the `symbol-ownership` summary endpoint first (returns a time
    series of institutional metrics). Falls back to the `institutional-holder`
    endpoint which lists individual holders — in that case we synthesize a
    summary from the list length and recent shares deltas.

    Returns a dict like::

        {
            "available": True/False,
            "holder_count": int or None,
            "ownership_pct": float or None,     # % of shares held by institutions
            "ownership_change": float or None,  # QoQ change in ownership %
            "source": "symbol-ownership" | "institutional-holder" | None,
        }

    When the endpoint is plan-gated (402) or cooling down, returns
    ``{"available": False, ...}`` so callers can route to the price/volume
    proxy. Cache 24h.
    """
    cache_key = f"inst_own:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale

    result = {
        "available": False,
        "holder_count": None,
        "ownership_pct": None,
        "ownership_change": None,
        "source": None,
    }

    # Try the time-series summary (most useful — gives QoQ delta).
    summary = _fmp_get(
        "/institutional-ownership/symbol-ownership",
        {"symbol": ticker, "includeCurrentQuarter": "true"},
    )
    if summary and isinstance(summary, list) and len(summary) >= 1:
        latest = summary[0] or {}
        prev = summary[1] if len(summary) > 1 else {}
        own_pct = latest.get("ownershipPercent") or latest.get("ownership")
        prev_pct = prev.get("ownershipPercent") or prev.get("ownership")
        try:
            own_pct_f = float(own_pct) if own_pct is not None else None
            prev_pct_f = float(prev_pct) if prev_pct is not None else None
        except (TypeError, ValueError):
            own_pct_f, prev_pct_f = None, None

        change = None
        if own_pct_f is not None and prev_pct_f is not None:
            change = own_pct_f - prev_pct_f

        try:
            holder_count = int(latest.get("investorsHolding") or latest.get("holders") or 0) or None
        except (TypeError, ValueError):
            holder_count = None

        result.update({
            "available": True,
            "holder_count": holder_count,
            "ownership_pct": own_pct_f,
            "ownership_change": change,
            "source": "symbol-ownership",
        })
        _set_cache(cache_key, result)
        return result

    # Fallback: individual holder list (free-plan friendly on some accounts).
    holders = _fmp_get("/institutional-holder", {"symbol": ticker})
    if holders and isinstance(holders, list) and len(holders) > 0:
        total_shares = 0.0
        total_change = 0.0
        for h in holders:
            try:
                total_shares += float(h.get("shares") or 0)
                total_change += float(h.get("change") or 0)
            except (TypeError, ValueError):
                continue
        change_pct = None
        if total_shares > 0:
            change_pct = (total_change / total_shares) * 100.0
        result.update({
            "available": True,
            "holder_count": len(holders),
            "ownership_pct": None,  # raw holder list can't give total %
            "ownership_change": change_pct,
            "source": "institutional-holder",
        })
        _set_cache(cache_key, result)
        return result

    _set_cache(cache_key, result)
    return result


# ── Balance Sheet & Income Statement ────────────────────────────
# Used for Current Ratio (totalCurrentAssets / totalCurrentLiabilities)
# and Interest Coverage (operatingIncome / interestExpense).
# Returns:
#   list[dict] on success (most-recent period first)
#   None on 402 / network errors (caller treats as "try fallback" / DATA_UNAVAILABLE)
#   [] when FMP returns empty payload (caller treats as NO_DATA)

def _edgar_fundamentals_fallback(ticker):
    """Convert SEC EDGAR ``companyfacts`` into a single FMP-shaped record.

    EDGAR gives us annual (10-K) values only through the
    ``EdgarService.get_fundamentals`` helper, so the shape is much sparser
    than FMP's full statement. Returns a **list with one dict** (to match
    FMP's list-of-statements contract) or an empty list when EDGAR has no
    data. Never raises.
    """
    try:
        from edgar_service import EdgarService
    except Exception as exc:  # pragma: no cover — import path
        logger.info("EDGAR fallback unavailable (%s)", exc)
        return []
    try:
        fund = EdgarService.get_fundamentals(ticker)
    except Exception as exc:
        logger.info("EDGAR fallback failed for %s: %s", ticker, exc)
        return []
    if not fund:
        return []
    return [fund]


def get_balance_sheet(ticker):
    """Latest balance sheet statements for a ticker.

    Cache 24h (fundamental data changes at most once per reporting period).
    Returns a list of statement dicts, most-recent first. None on failure
    so callers can distinguish "plan-gated / network error" from "no data"
    (empty list) -- downstream indicators map this to DATA_UNAVAILABLE vs NO_DATA.

    Fallback: when FMP returns None (plan-gated / network error) and the
    ticker is US, SEC EDGAR ``companyfacts`` provides the debt/equity
    numbers that downstream indicators depend on.
    """
    cache_key = f"balance_sheet:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale
    data = _fmp_get("/balance-sheet-statement", {"symbol": ticker})
    if isinstance(data, list) and data:
        _set_cache(cache_key, data)
        return data
    # Class-share retry before falling to EDGAR.
    alt = _class_share_alt(ticker)
    if alt:
        alt_data = _fmp_get("/balance-sheet-statement", {"symbol": alt})
        if isinstance(alt_data, list) and alt_data:
            logger.info("FMP balance-sheet resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, alt_data)
            return alt_data
    # FMP returned None or [] — try EDGAR for US tickers.
    if _is_us_ticker(ticker):
        edgar = _edgar_fundamentals_fallback(ticker)
        if edgar:
            logger.info("FMP balance-sheet miss for %s — served via EDGAR fallback", ticker)
            _set_cache(cache_key, edgar)
            return edgar
    if data is None:
        return None
    # Cache the empty FMP response so we don't retry in-session.
    _set_cache(cache_key, data)
    return data


def get_income_statement(ticker):
    """Latest income statements for a ticker.

    Cache 24h. Returns a list of statement dicts, most-recent first. None on
    failure (distinguishable from empty list -- see get_balance_sheet).

    Fallback: SEC EDGAR ``companyfacts`` for US tickers when FMP is gated.
    """
    cache_key = f"income_statement:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale
    data = _fmp_get("/income-statement", {"symbol": ticker})
    if isinstance(data, list) and data:
        _set_cache(cache_key, data)
        return data
    # Class-share retry before falling to EDGAR.
    alt = _class_share_alt(ticker)
    if alt:
        alt_data = _fmp_get("/income-statement", {"symbol": alt})
        if isinstance(alt_data, list) and alt_data:
            logger.info("FMP income-statement resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, alt_data)
            return alt_data
    # FMP miss → EDGAR fallback (US tickers only)
    if _is_us_ticker(ticker):
        edgar = _edgar_fundamentals_fallback(ticker)
        if edgar:
            logger.info("FMP income-statement miss for %s — served via EDGAR fallback", ticker)
            _set_cache(cache_key, edgar)
            return edgar
    if data is None:
        return None
    _set_cache(cache_key, data)
    return data


def prefetch_fundamentals(tickers):
    """Pre-warm cache for a batch of tickers using minimal FMP calls.

    Strategy:
    - Profiles: 1 batch call per 50 tickers (FMP supports comma-separated)
    - Quotes: 1 batch call per 50 tickers (already supported)
    - Ratios/Metrics: only fetch for tickers not already cached (24h TTL)
    - Uses threading to parallelize the per-ticker ratios/metrics calls

    For 50 tickers, worst case:
    - 1 batch profile call + 1 batch quote call + N uncached ratios + N uncached metrics
    - Best case (all cached from previous day): 2 calls total
    - Typical case (first run of day): 2 batch + ~50*2 individual = ~102 calls
    - BUT: ratios/metrics have 24h TTL, so subsequent runs use 0 calls

    The key savings come from:
    1. Profile batch: 50 tickers in 1 call instead of 50
    2. Quote batch: 50 tickers in 1 call instead of 50
    3. get_info() reuses cached profile/ratios/metrics instead of re-fetching
    """
    if not tickers:
        return

    # Filter to US tickers only (Korean tickers not on FMP)
    us_tickers = [t for t in tickers if not t.endswith(".KS") and not t.endswith(".KQ")]
    if not us_tickers:
        return

    logger.info(f"FMP prefetch: warming cache for {len(us_tickers)} US tickers")

    # 1. Batch profiles (1 call per 50 tickers)
    for i in range(0, len(us_tickers), 50):
        chunk = us_tickers[i:i+50]
        get_profiles_batch(chunk)

    # 2. Batch quotes (1 call per 50 tickers)
    for i in range(0, len(us_tickers), 50):
        chunk = us_tickers[i:i+50]
        get_quotes_batch(chunk)

    # 3. Per-ticker ratios and metrics — SKIPPED at startup to preserve daily budget.
    # On the FMP Premium plan (10k/day soft cap), 50 ratios + 50 metrics = 100 calls consumed
    # upfront wastes budget when most tickers are never opened in a session.
    # Ratios/metrics are fetched on-demand with 24h TTL — the first analyze() call for each
    # ticker will populate these caches and subsequent calls within 24h are free.
    uncached_ratios = [t for t in us_tickers if not _get_cache(f"ratios_ttm:{t}", TTL_FUNDAMENTAL)]
    uncached_metrics = [t for t in us_tickers if not _get_cache(f"metrics_ttm:{t}", TTL_FUNDAMENTAL)]
    if uncached_ratios or uncached_metrics:
        logger.info(f"FMP prefetch: {len(uncached_ratios)} ratios + {len(uncached_metrics)} metrics skipped (on-demand fetch preserves daily budget)")

    # 4. Build get_info() cache from already-fetched components
    # This avoids get_info() making 3 sub-calls per ticker later
    for t in us_tickers:
        cache_key = f"info:{t}"
        if _get_cache(cache_key, TTL_FUNDAMENTAL):
            continue
        profile = _get_cache(f"profile:{t}", TTL_PROFILE)
        ratios = _get_cache(f"ratios_ttm:{t}", TTL_FUNDAMENTAL)
        metrics = _get_cache(f"metrics_ttm:{t}", TTL_FUNDAMENTAL)
        if profile:
            info = {}
            last_div = profile.get("lastDividend") or profile.get("lastDiv") or 0
            price = profile.get("price", 0)
            info.update({
                "shortName": profile.get("companyName", t),
                "longName": profile.get("companyName", t),
                "longBusinessSummary": profile.get("description", ""),
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
                "marketCap": profile.get("marketCap") or profile.get("mktCap") or 0,
                "beta": profile.get("beta", 1.0),
                "price": price,
                "website": profile.get("website", ""),
                "ceo": profile.get("ceo", ""),
                "fullTimeEmployees": profile.get("fullTimeEmployees", 0),
                "country": profile.get("country", ""),
                "exchange": profile.get("exchangeShortName") or profile.get("exchange", ""),
                "currency": profile.get("currency", "USD"),
                "ipoDate": profile.get("ipoDate", ""),
                "image": profile.get("image", ""),
                "52WeekHigh": profile.get("range", "").split("-")[-1].strip() if profile.get("range") else 0,
                "52WeekLow": profile.get("range", "").split("-")[0].strip() if profile.get("range") else 0,
                "dividendYield": last_div / price if price else 0,
                "isEtf": profile.get("isEtf", False),
                "floatShares": profile.get("floatShares") or profile.get("sharesFloat"),
            })
            if ratios:
                info.update({
                    "trailingPE": ratios.get("priceToEarningsRatioTTM") or ratios.get("peRatioTTM") or 0,
                    "forwardPE": ratios.get("priceToEarningsRatioTTM") or ratios.get("peRatioTTM") or 0,
                    "priceToBook": ratios.get("priceToBookRatioTTM", 0),
                    "debtToEquity": ratios.get("debtToEquityRatioTTM") or ratios.get("debtEquityRatioTTM") or 0,
                    "returnOnEquity": ratios.get("returnOnEquityTTM", 0),
                    "currentRatio": ratios.get("currentRatioTTM", 0),
                    "netProfitMargin": ratios.get("netProfitMarginTTM", 0),
                    "grossProfitMargin": ratios.get("grossProfitMarginTTM", 0),
                    "operatingProfitMargin": ratios.get("operatingProfitMarginTTM", 0),
                })
            if metrics:
                eps = (ratios or {}).get("netIncomePerShareTTM") or metrics.get("epsTTM") or 0
                rev_per_share = (ratios or {}).get("revenuePerShareTTM") or metrics.get("revenuePerShareTTM") or 0
                # See get_info() above: revenueGrowth must be a YoY rate, not an
                # absolute revenue-per-share figure. Mirror the same null fix here
                # so the prefetch path doesn't pre-seed a wrong value into cache.
                info.update({
                    "trailingEps": eps,
                    "revenueGrowth": None,
                    "revenuePerShare": rev_per_share,
                })
            # Mirror get_info()'s null-cache guard so the prefetch path
            # doesn't pre-seed partial (all-null) records into cache.
            is_etf = bool(info.get("isEtf"))
            has_critical = (
                bool(info.get("trailingPE"))
                or bool(info.get("trailingEps"))
                or bool(info.get("marketCap"))
            )
            if is_etf or has_critical:
                _set_cache(cache_key, info)

    cached_count = sum(1 for t in us_tickers if _get_cache(f"info:{t}", TTL_FUNDAMENTAL))
    logger.info(f"FMP prefetch complete: {cached_count}/{len(us_tickers)} tickers cached, "
                f"{_daily_calls}/{_FMP_DAILY_SOFT_LIMIT} API calls used today")


# ── News ────────────────────────────────────────────────────────

def get_news(ticker, limit=15):
    """Per-ticker news. Cache 30min. Stale-while-revalidate when budget low."""
    cache_key = f"news:{ticker}"
    cached = _get_cache(cache_key, TTL_NEWS)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/news/stock", {"symbol": ticker, "limit": limit})
    if data and isinstance(data, list) and len(data) > 0:
        _set_cache(cache_key, data)
        return data
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/news/stock", {"symbol": alt, "limit": limit})
        if data and isinstance(data, list) and len(data) > 0:
            logger.info("FMP news resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, data)
            return data
    return []


def get_general_news(limit=15):
    """General market news. FMP aggregates licensed news feeds
    (Reuters, MarketWatch, Bloomberg, etc.) so commercial use is OK.

    Returns list of dicts with keys: title, text/summary, publishedDate,
    url/link, site/source, image. Empty list on failure.
    Cache TTL_NEWS (6h). Stale-while-revalidate when budget low.
    """
    cache_key = "news:general"
    cached = _get_cache(cache_key, TTL_NEWS)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/news/general", {"limit": limit})
    if data and isinstance(data, list):
        _set_cache(cache_key, data)
        return data
    return []


# ── Forex (Exchange Rate) ──────────────────────────────────────

def get_fx_rate(pair="USDKRW"):
    """Get forex rate. Cache 5s for near-realtime. Stale-while-revalidate when budget low."""
    cache_key = f"fx:{pair}"
    cached = _get_cache(cache_key, _fx_ttl())
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/quote", {"symbol": pair})
    if data and isinstance(data, list) and len(data) > 0:
        rate = data[0].get("price", 0) or data[0].get("ask", 0)
        if rate > 100:  # Sanity check for USDKRW
            _set_cache(cache_key, rate)
            return rate
    return None


# ── Earnings Calendar ───────────────────────────────────────────

def get_earnings_calendar(ticker=None, days_ahead=30):
    """Get upcoming earnings. Cache 24h. Stale-while-revalidate when budget low."""
    cache_key = f"earnings:{ticker or 'all'}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale

    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    params = {"from": today, "to": future}
    if ticker:
        params["symbol"] = ticker

    data = _fmp_get("/earnings-calendar", params)
    if data and isinstance(data, list) and len(data) > 0:
        _set_cache(cache_key, data)
        return data

    # Class-share retry when a specific ticker was requested.
    if ticker:
        alt = _class_share_alt(ticker)
        if alt:
            alt_params = dict(params, symbol=alt)
            alt_data = _fmp_get("/earnings-calendar", alt_params)
            if alt_data and isinstance(alt_data, list) and len(alt_data) > 0:
                logger.info(
                    "FMP earnings-calendar resolved %s via class-share alt %s",
                    ticker, alt,
                )
                _set_cache(cache_key, alt_data)
                return alt_data

    # FMP miss — Alpaca does NOT publish earnings calendars, so no
    # fallback here today. The adapter returns [] deliberately; future
    # work could wire Tiingo/EDGAR 8-K for US earnings calendar parity.
    if ticker and _is_us_ticker(ticker):
        ama = _ama()
        if ama is not None:
            cal = ama.get_earnings_calendar(ticker)
            if cal:
                logger.info(
                    "FMP earnings-calendar miss for %s — served via Alpaca fallback",
                    ticker,
                )
                _set_cache(cache_key, cal)
                return cal
    return []


# ── Dividends ───────────────────────────────────────────────────

def get_dividends(ticker):
    """Get dividend data. Cache 24h. Stale-while-revalidate when budget low."""
    cache_key = f"dividends:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale
    data = _fmp_get("/dividends", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        _set_cache(cache_key, data)
        return data
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/dividends", {"symbol": alt})
        if data and isinstance(data, list) and len(data) > 0:
            logger.info("FMP dividends resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, data)
            return data
    return []


# ── Intraday (1min bars) ───────────────────────────────────────

def get_intraday(ticker, interval="1min"):
    """Get intraday bars. Cache 60s. Stale-while-revalidate when budget low."""
    cache_key = f"intraday:{ticker}:{interval}"
    cached = _get_cache(cache_key, _intraday_ttl())
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale

    # Map interval
    interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1hour"}
    fmp_interval = interval_map.get(interval, interval)

    data = _fmp_get(f"/historical-chart/{fmp_interval}", {"symbol": ticker})
    if not (data and isinstance(data, list) and len(data) > 0):
        alt = _class_share_alt(ticker)
        if alt:
            alt_data = _fmp_get(f"/historical-chart/{fmp_interval}", {"symbol": alt})
            if alt_data and isinstance(alt_data, list) and len(alt_data) > 0:
                logger.info("FMP intraday resolved %s via class-share alt %s", ticker, alt)
                data = alt_data
    if data and isinstance(data, list) and len(data) > 0:
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
    """Get sector performance. Cache 30min. Stale-while-revalidate when budget low.
    Uses /stable/sector-performance-snapshot which requires a date param.
    Tries the most recent trading day (today, then yesterday, etc.)
    and aggregates per-exchange results into a single average per sector.
    Returns list of dicts: [{sector, changesPercentage}, ...]
    """
    cache_key = "sector_perf"
    cached = _get_cache(cache_key, TTL_SECTOR)
    if cached:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale:
            return stale

    # Try last 5 days to find a trading day with data
    data = None
    for days_back in range(0, 5):
        check_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        data = _fmp_get("/sector-performance-snapshot", {"date": check_date})
        if data and isinstance(data, list) and len(data) > 0:
            break
        data = None

    if not data:
        return []

    # Aggregate: average across exchanges for each sector
    from collections import defaultdict
    sector_totals = defaultdict(lambda: {"total": 0.0, "count": 0})
    for item in data:
        s = item.get("sector", "")
        if s:
            sector_totals[s]["total"] += item.get("averageChange", 0)
            sector_totals[s]["count"] += 1

    result = []
    for sector, vals in sector_totals.items():
        avg = vals["total"] / vals["count"] if vals["count"] else 0
        result.append({
            "sector": sector,
            "changesPercentage": f"{avg:.4f}%",
        })
    result.sort(key=lambda x: float(x["changesPercentage"].rstrip("%")), reverse=True)

    _set_cache(cache_key, result)
    return result


# ── Insider Transactions ───────────────────────────────────────

TTL_INSIDER = 3600  # 1 hour — insider filings update infrequently


def get_insider_trades(ticker, limit=50):
    """Get insider transactions for a ticker. Cache 1 hour.

    FMP endpoint: /insider-trading?symbol=TICKER
    Returns list of dicts with keys:
        symbol, filingDate, transactionDate, reportingName, typeOfOwner,
        transactionType (P-Purchase, S-Sale), acquistionOrDisposition (A/D),
        securitiesTransacted, price, securitiesOwned, link
    """
    cache_key = f"insider:{ticker}"
    cached = _get_cache(cache_key, TTL_INSIDER)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale

    data = _fmp_get("/insider-trading", {"symbol": ticker, "limit": limit})
    if data and isinstance(data, list) and len(data) > 0:
        _set_cache(cache_key, data)
        return data
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/insider-trading", {"symbol": alt, "limit": limit})
        if data and isinstance(data, list) and len(data) > 0:
            logger.info("FMP insider-trading resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, data)
            return data

    _set_cache(cache_key, [])
    return []


# ── Short Interest ─────────────────────────────────────────────

def get_short_interest(ticker):
    """Get historical short interest data. Cache 24h (fundamental-level refresh).
    FMP endpoint: /historical/short-interest?symbol=AAPL
    Returns list of dicts with date, shortInterest, floatShort, etc.
    """
    cache_key = f"short_interest:{ticker}"
    cached = _get_cache(cache_key, TTL_FUNDAMENTAL)
    if cached is not None:
        return cached
    if _is_budget_stale():
        stale = _get_cache_stale(cache_key)
        if stale is not None:
            return stale
    data = _fmp_get("/historical/short-interest", {"symbol": ticker})
    if data and isinstance(data, list) and len(data) > 0:
        _set_cache(cache_key, data)
        return data
    alt = _class_share_alt(ticker)
    if alt:
        data = _fmp_get("/historical/short-interest", {"symbol": alt})
        if data and isinstance(data, list) and len(data) > 0:
            logger.info("FMP short-interest resolved %s via class-share alt %s", ticker, alt)
            _set_cache(cache_key, data)
            return data
    _set_cache(cache_key, [])
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
    now = time.time()
    blocked = {ep: max(0, int(until - now))
               for ep, until in _endpoint_402_cooldown.items()
               if until > now}
    return {
        "daily_calls": _daily_calls,
        "daily_limit": _FMP_DAILY_SOFT_LIMIT,
        "remaining": max(0, _FMP_DAILY_SOFT_LIMIT - _daily_calls),
        "cache_entries": len(_cache),
        "stale_mode": _is_budget_stale(),
        "hard_stopped": _is_budget_exhausted(),
        "stale_threshold": _BUDGET_STALE_THRESHOLD,
        "hard_stop_threshold": _BUDGET_HARD_STOP,
        "blocked_endpoints": blocked,   # {path: seconds_remaining}
        "402_counts": dict(_endpoint_402_counts),
    }


def is_available():
    """Check if FMP API key is configured."""
    return bool(FMP_KEY)
