"""Market-aware TTL helpers for price/quote/index/fx caches.

When either US or KR market is tradable (regular / pre / after),
caches refresh aggressively (5–30s) so users see near-live prices.
When all markets are closed, TTLs relax to reduce API/compute pressure
without loss of meaningful data freshness.

Callers are expected to invoke these helpers per-request rather than
memoizing — the cost is a single ``datetime.now()`` + a few dict
lookups, which is negligible compared with the network calls these
TTLs are guarding.

Every helper is defensive: if ``market_status.get_market_status()``
raises (unlikely, but guarded for scheduler-import paths), the
closed-market TTL is returned so we never accidentally stampede an
upstream API on a broken status probe.
"""
from __future__ import annotations

import logging

from services.market_status import get_market_status

logger = logging.getLogger(__name__)


def _is_market_open() -> bool:
    """Return True when US or KR markets are tradable (any session)."""
    try:
        status = get_market_status() or {}
        us = (status.get("us") or {}).get("tradable", False)
        kr = (status.get("kr") or {}).get("tradable", False)
        return bool(us or kr)
    except Exception:
        # Never let a status probe failure cascade into TTL=0 hammering.
        logger.debug("cache_ttl: market_status probe failed; assuming closed")
        return False


def quote_ttl() -> int:
    """Quote/price cache TTL: 5s intraday, 30s off-hours."""
    return 5 if _is_market_open() else 30


def intraday_ttl() -> int:
    """Intraday bar cache TTL: 10s intraday, 60s off-hours."""
    return 10 if _is_market_open() else 60


def signal_ttl() -> int:
    """SignalCache TTL: 30s intraday, 120s off-hours."""
    return 30 if _is_market_open() else 120


def indices_ttl() -> int:
    """Market indices cache TTL: 15s intraday, 300s off-hours."""
    return 15 if _is_market_open() else 300


def fx_ttl() -> int:
    """FX rate cache TTL: 5s intraday, 30s off-hours."""
    return 5 if _is_market_open() else 30
