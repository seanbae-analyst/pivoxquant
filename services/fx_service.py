"""USD/KRW exchange rate management.
Priority: KIS API (realtime) → FMP (5s cache) → exchangerate-api (backup) → fallback default.

Design notes:
- `_usdkrw_ts` updates ONLY on successful fetch, so a stale value is clearly
  detectable (previous implementation updated the timestamp even on failure,
  hiding staleness).
- `is_stale()` returns True when the cached rate is older than 10 minutes,
  letting callers (and `/api/fx`) signal degraded data to the frontend.
- `refresh()` is cheap (5s short-cache) and safe to call per request.
- `_refresh_fx_rate(app)` is the APScheduler-friendly entrypoint that logs
  warnings when the rate has been stale for > 10 minutes.
- `get_rate_at(d)` returns the historical USD/KRW rate for a specific date,
  used by counterfactual / dividend / regret simulators where applying the
  *current* rate to a years-old transaction silently drifts results by the
  full USD/KRW path since (single-digit %, sometimes more for long windows).
"""
import logging
import threading
import time
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

_usdkrw = 1380.0
_usdkrw_ts = 0.0  # Last SUCCESSFUL update timestamp (0 = never fetched)
_last_attempt_ts = 0.0  # Last attempt timestamp (for 5s short-cache)
_lock = threading.Lock()

STALE_SECONDS = 600  # 10 minutes — log warning beyond this
SHORT_CACHE_SECONDS = 5  # Avoid hammering APIs on per-request refresh

# ── Historical FX cache ────────────────────────────────────────────
# Per-date USD/KRW close. In-memory dict keyed by ISO date string.
# Bounded; FIFO trim at HIST_MAX. Acceptable for the Railway single-worker
# deployment — swap to Redis/DB when multi-worker.
HIST_MAX = 8000
_hist_cache: dict[str, float] = {}
_hist_lock = threading.Lock()
# Per-date negative cache (timestamp of last failed fetch). Avoids hammering
# upstream when a date legitimately has no quote (weekend / holiday before
# we figured out the nearest-trading-day fallback resolved).
_hist_miss_ts: dict[str, float] = {}
HIST_MISS_TTL = 3600  # 1h between retries for a missing date


def get_rate() -> float:
    """Return the current cached USD/KRW rate."""
    return _usdkrw


def last_updated() -> float:
    """Unix timestamp of the last successful refresh (0 if never)."""
    return _usdkrw_ts


def is_stale() -> bool:
    """True when cached rate is older than 10 minutes (or never fetched)."""
    if _usdkrw_ts == 0.0:
        return True
    return (time.time() - _usdkrw_ts) > STALE_SECONDS


def set_rate(rate: float):
    """Update the cached rate (e.g., from macro endpoint)."""
    global _usdkrw, _usdkrw_ts
    if rate and rate > 1000:
        with _lock:
            _usdkrw = round(float(rate), 2)
            _usdkrw_ts = time.time()


def _fetch_from_fmp() -> float | None:
    """Primary source: FMP."""
    try:
        from services.data.fmp import get_fx_rate
        rate = get_fx_rate("USDKRW")
        if rate and rate > 1000:
            return float(rate)
    except Exception as e:
        logger.debug(f"FMP FX fetch failed: {e}")
    return None


def _fetch_from_exchangerate_api() -> float | None:
    """Backup: exchangerate-api.com (free, no key required)."""
    try:
        import requests
        resp = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            rate = data.get("rates", {}).get("KRW")
            if rate and rate > 1000:
                return float(rate)
    except Exception as e:
        logger.debug(f"exchangerate-api FX fetch failed: {e}")
    return None


def refresh():
    """Refresh USD/KRW rate. FMP → exchangerate-api → keep cached.
    Updates `_usdkrw_ts` ONLY on success so staleness is observable.
    """
    global _usdkrw, _usdkrw_ts, _last_attempt_ts
    now = time.time()
    # 5s short-cache on attempts — prevents API hammering from concurrent callers
    if now - _last_attempt_ts < SHORT_CACHE_SECONDS:
        return
    _last_attempt_ts = now

    rate = _fetch_from_fmp()
    if rate is None:
        rate = _fetch_from_exchangerate_api()

    if rate is not None:
        with _lock:
            _usdkrw = round(rate, 2)
            _usdkrw_ts = now
        logger.debug(f"FX refreshed: {_usdkrw}")
    else:
        # Keep stale rate; do NOT update _usdkrw_ts so is_stale() stays truthful.
        age = int(now - _usdkrw_ts) if _usdkrw_ts else -1
        logger.debug(f"FX refresh failed; using cached rate {_usdkrw} (age {age}s)")


def init_async():
    """Initialize FX rate in background thread on startup."""
    def _fetch():
        global _usdkrw, _usdkrw_ts
        rate = _fetch_from_fmp() or _fetch_from_exchangerate_api()
        if rate is not None:
            with _lock:
                _usdkrw = round(rate, 2)
                _usdkrw_ts = time.time()
            logger.info(f"USD/KRW initialized: {_usdkrw}")
        else:
            logger.warning(f"USD/KRW init failed; using default: {_usdkrw}")
    threading.Thread(target=_fetch, daemon=True).start()


def _hist_key(d) -> str:
    """Coerce date|datetime|str → ISO YYYY-MM-DD."""
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]


def _fetch_historical_window(start_iso: str, end_iso: str) -> dict[str, float]:
    """Pull the FMP historical USD/KRW EOD series for [start, end].

    Returns ``{date_iso: close}`` or ``{}`` on any failure. Failures are
    logged at DEBUG only — the caller has a fallback chain.
    """
    try:
        from services.data.fmp import _fmp_get  # noqa: PLC0415  (lazy import)
        # FMP stable historical endpoint. Symbol param accepts USDKRW.
        data = _fmp_get(
            "/historical-price-eod/full",
            {"symbol": "USDKRW", "from": start_iso, "to": end_iso},
        )
    except Exception as e:
        logger.debug(f"FMP historical FX import/fetch failed: {e}")
        return {}

    if not data:
        return {}

    # FMP may return a list of bars or {"historical": [...]}. Handle both.
    if isinstance(data, dict):
        bars = data.get("historical") or []
    elif isinstance(data, list):
        bars = data
    else:
        bars = []

    out: dict[str, float] = {}
    for bar in bars:
        try:
            d = bar.get("date")
            close = bar.get("close") or bar.get("price") or bar.get("adjClose")
            if d and close and float(close) > 100:
                out[str(d)[:10]] = float(close)
        except (TypeError, ValueError):
            continue
    return out


def get_rate_at(d) -> float:
    """Return the USD/KRW rate for the given date.

    Resolution order:
      1. In-memory historical cache (exact date hit).
      2. FMP historical EOD fetch — pulls a 14-day window around the
         requested date, caches each entry, and returns the closest prior
         trading day (handles weekends / holidays).
      3. Negative-cache hit within ``HIST_MISS_TTL`` → fall through to (4)
         without re-fetching.
      4. Current cached spot rate (``get_rate()``) — last-resort so callers
         never see a None / zero rate. The residual error here is the
         USD/KRW drift since ``d``; callers that need exactness should
         refuse to compute when this branch fires (they can detect by
         comparing the result with ``get_rate()`` or by checking whether
         the date is far in the past).

    Never raises.
    """
    if d is None:
        return get_rate()

    key = _hist_key(d)

    # 1. Cache hit
    cached = _hist_cache.get(key)
    if cached:
        return cached

    # If the date is today or in the future, defer to spot.
    try:
        target = date.fromisoformat(key)
    except ValueError:
        return get_rate()
    if target >= date.today():
        return get_rate()

    # 3. Negative cache — recent miss?
    miss_ts = _hist_miss_ts.get(key, 0.0)
    if miss_ts and (time.time() - miss_ts) < HIST_MISS_TTL:
        return get_rate()

    # 2. Fetch a small window so neighbouring dates also populate (cheap)
    start_iso = (target - timedelta(days=7)).isoformat()
    end_iso = (target + timedelta(days=7)).isoformat()
    bars = _fetch_historical_window(start_iso, end_iso)

    if bars:
        with _hist_lock:
            for k, v in bars.items():
                _hist_cache[k] = v
            # FIFO trim
            if len(_hist_cache) > HIST_MAX:
                # drop ~10% oldest entries (insertion-ordered dict)
                drop_n = HIST_MAX // 10
                for k in list(_hist_cache.keys())[:drop_n]:
                    _hist_cache.pop(k, None)

        # Exact date?
        if key in _hist_cache:
            return _hist_cache[key]

        # Closest prior trading day within the fetched window
        for back in range(1, 8):
            prior = (target - timedelta(days=back)).isoformat()
            if prior in _hist_cache:
                # Cache the exact requested date as an alias so future hits
                # are O(1). Aliasing is safe — within a 7-day window the
                # USD/KRW drift is < 1% in practice.
                with _hist_lock:
                    _hist_cache[key] = _hist_cache[prior]
                return _hist_cache[prior]

    # 4. Last-resort: spot rate, mark a miss so we don't hammer
    with _hist_lock:
        _hist_miss_ts[key] = time.time()
    logger.debug(f"FX historical miss for {key}; falling back to spot {get_rate()}")
    return get_rate()


def _refresh_fx_rate(app):
    """APScheduler entrypoint — runs every 5 minutes.
    Logs a WARNING when the rate has been stale for more than 10 minutes.
    """
    global _usdkrw, _usdkrw_ts
    with app.app_context():
        now = time.time()
        rate = _fetch_from_fmp() or _fetch_from_exchangerate_api()
        if rate is not None:
            with _lock:
                _usdkrw = round(rate, 2)
                _usdkrw_ts = now
            logger.info(f"[fx-scheduler] USD/KRW refreshed: {_usdkrw}")
        else:
            age = int(now - _usdkrw_ts) if _usdkrw_ts else -1
            if _usdkrw_ts == 0.0 or age > STALE_SECONDS:
                logger.warning(
                    f"[fx-scheduler] USD/KRW STALE — last successful fetch "
                    f"{age}s ago; using cached {_usdkrw}"
                )
            else:
                logger.info(
                    f"[fx-scheduler] USD/KRW fetch failed; cached {_usdkrw} "
                    f"(age {age}s, still fresh)"
                )
