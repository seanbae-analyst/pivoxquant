"""USD/KRW exchange rate management.
Priority: KIS API (realtime) → FMP (5s cache) → fallback default.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

_usdkrw = 1380.0
_usdkrw_ts = 0.0


def get_rate() -> float:
    """Return the current cached USD/KRW rate."""
    return _usdkrw


def set_rate(rate: float):
    """Update the cached rate (e.g., from macro endpoint)."""
    global _usdkrw, _usdkrw_ts
    if rate > 1000:
        _usdkrw = round(rate, 2)
        _usdkrw_ts = time.time()


def refresh():
    """Refresh USD/KRW rate. KIS → FMP → cached value."""
    global _usdkrw, _usdkrw_ts
    now = time.time()
    if now - _usdkrw_ts < 5:  # 5s cache for near-realtime
        return
    _usdkrw_ts = now

    # Try FMP first (fast REST call)
    try:
        from fmp_service import get_fx_rate
        rate = get_fx_rate("USDKRW")
        if rate and rate > 1000:
            _usdkrw = round(rate, 2)
            return
    except Exception:
        pass

    # Fallback: keep existing rate
    logger.debug(f"FX refresh using cached rate: {_usdkrw}")


def init_async():
    """Initialize FX rate in background thread on startup."""
    def _fetch():
        global _usdkrw, _usdkrw_ts
        try:
            from fmp_service import get_fx_rate
            rate = get_fx_rate("USDKRW")
            if rate and rate > 1000:
                _usdkrw = round(rate, 2)
                _usdkrw_ts = time.time()
                logger.info(f"USD/KRW initialized: {_usdkrw}")
                return
        except Exception:
            pass
        logger.info(f"USD/KRW using default: {_usdkrw}")
    threading.Thread(target=_fetch, daemon=True).start()
