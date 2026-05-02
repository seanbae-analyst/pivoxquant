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
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

_usdkrw = 1380.0
_usdkrw_ts = 0.0  # Last SUCCESSFUL update timestamp (0 = never fetched)
_last_attempt_ts = 0.0  # Last attempt timestamp (for 5s short-cache)
_lock = threading.Lock()

STALE_SECONDS = 600  # 10 minutes — log warning beyond this
SHORT_CACHE_SECONDS = 5  # Avoid hammering APIs on per-request refresh


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
