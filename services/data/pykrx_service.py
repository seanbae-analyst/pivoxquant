"""
PivoxQuant — KR Alt-Data Service (Deprecated)
=============================================
Foreign-investor flow, institutional flow, and short-interest time series
were previously served by scraping the KRX data portal via the `pykrx`
library. That path was removed on 2026-04-19 for legal compliance — pyKRX
has no commercial-use licence and the KRX portal ToS forbids automated
scraping for a paid SaaS product.

Replacements under evaluation:
  - KRX Open Data Portal (data.krx.co.kr) — free tier exists but requires
    per-dataset approval and an institutional account (not yet set up).
  - KIS public API — publishes per-symbol investor trading breakdowns on
    a read-only commercial licence. Not yet wired into this adapter.
  - DART OpenAPI — has short-interest filings but only at quarterly grain.

Until a replacement is chosen, every method on this service returns an
empty list / dict with ``source="deprecated"``. The `/api/alt-data/kr/*`
routes still respond 200 with an empty ``data`` array so the frontend
degrades gracefully instead of 500-ing. The service keeps the exact
public method names and cache primitives from the old implementation so
callers (routes/alt_data.py, tests) don't need to change.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Retained for backwards compat — tests patch this module-level flag.
_pykrx_stock = None
_PYKRX_AVAILABLE = False


def _normalize_ticker(ticker: str) -> str | None:
    """Normalize '005930.KS' / '005930.kq' / '005930' → '005930'.

    Kept in-module (same contract as before) so `routes/alt_data.py` can
    still import it. Returns None for anything that isn't a 6-digit code.
    """
    if not ticker or not isinstance(ticker, str):
        return None
    t = ticker.strip().upper()
    for suf in (".KS", ".KQ", ".KRX"):
        if t.endswith(suf):
            t = t[: -len(suf)]
            break
    if t.isdigit() and len(t) == 6:
        return t
    return None


class PyKRXService:
    """Deprecated in-process wrapper around the old pyKRX scraper.

    Every method returns an empty container today. The class shape + method
    signatures are preserved so existing routes and tests keep compiling.
    When a licensed replacement ships, we re-enable just the internals
    without touching any caller.
    """

    def __init__(self, cache_ttl: int = 86_400, rate_limit_sleep: float = 0.0):
        # Kept for backwards compat — tests construct with these args.
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_lock = threading.Lock()
        self._last_call_ts: float = 0.0
        self._call_lock = threading.Lock()
        self.cache_ttl = cache_ttl
        self.rate_limit_sleep = rate_limit_sleep

    # ── Cache primitives (unchanged) ─────────────────────────────────────

    def _cache_get(self, key: str) -> Any | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time.time() - entry["ts"] >= self.cache_ttl:
                self._cache.pop(key, None)
                return None
            return entry["data"]

    def _cache_set(self, key: str, data: Any) -> None:
        with self._cache_lock:
            self._cache[key] = {
                "data": data,
                "ts": time.time(),
                "cached_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            }

    def _cache_cached_at(self, key: str) -> str | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            return entry.get("cached_at") if entry else None

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    # ── Public API — all return empty data ───────────────────────────────

    def get_foreign_flow(self, ticker: str, days: int = 30) -> list[dict]:
        """Deprecated. Returns []. See module docstring for why."""
        code = _normalize_ticker(ticker)
        if not code:
            logger.warning("pykrx.get_foreign_flow: invalid ticker %r", ticker)
            return []
        # No external call — just return empty so the frontend renders
        # "no data" instead of a 500.
        return []

    def get_institutional_flow(self, ticker: str, days: int = 30) -> list[dict]:
        """Deprecated. Returns []."""
        return []

    def get_short_interest(self, ticker: str, days: int = 30) -> list[dict]:
        """Deprecated. Returns []."""
        code = _normalize_ticker(ticker)
        if not code:
            logger.warning("pykrx.get_short_interest: invalid ticker %r", ticker)
        return []

    def get_short_balance_ratio(self, ticker: str) -> dict:
        """Deprecated. Returns {}."""
        code = _normalize_ticker(ticker)
        if not code:
            logger.warning("pykrx.get_short_balance_ratio: invalid ticker %r", ticker)
        return {}

    def get_market_flow_summary(self, market: str = "KOSPI", date: str | None = None) -> dict:
        """Deprecated. Returns {}."""
        market = (market or "KOSPI").upper()
        if market not in ("KOSPI", "KOSDAQ"):
            logger.warning("pykrx.get_market_flow_summary: invalid market %r", market)
        return {}

    def cached_at(self, ticker_or_market: str, kind: str, days: int | None = None,
                   date: str | None = None) -> str | None:
        """Deprecated — always None (no live cache entries)."""
        return None


# ── Module-level singleton (unchanged import path) ──────────────────────────
pykrx_service = PyKRXService()
