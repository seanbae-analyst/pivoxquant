"""Unified company-name resolver.

Returns a human-friendly company name for any ticker we display. Used by
every serializer/response builder that emits a stock so the frontend can
render the name large and the ticker small — on every page.

Resolution order
----------------
1. Korean registries (ticker endswith .KS / .KQ)
     - kr_stock_registry.get_name()  → curated ~2,500 names (offline JSON)
     - KIS API fallback for the long tail (rate-limited, paid quota)
2. US registry (everything else)
     - us_stock_registry.get_name()  → Alpaca asset master (~12,700 rows)
3. Module-level LRU cache for `lookup_name_from_signal_cache`
   (SignalCache blobs already carry "name" populated by the live fetchers)

Fallback
--------
When nothing resolves, returns None. Callers should default to the ticker
itself — keeping current behaviour is the explicit contract so adding this
helper is always safe.

Design notes
------------
- Pure-function by default. No DB session use in `resolve_stock_name`.
- `lookup_name_from_signal_cache` is a separate, opt-in helper because it
  requires a Flask app-context + DB session. Callers that already hold one
  use it; pure serializers don't.
- All lookups are case-insensitive via `.upper()` in the underlying
  registries.
- Legacy note: the pyKRX name fallback was removed (2026-04-19) — pyKRX
  scrapes KRX in a legal grey area. The curated JSON plus KIS API cover
  the same ground without the ToS risk.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional


def _is_korean(ticker: str) -> bool:
    t = ticker.upper()
    return t.endswith(".KS") or t.endswith(".KQ")


@lru_cache(maxsize=4096)
def _kis_name(ticker: str) -> Optional[str]:
    """Resolve any KRX ticker via the KIS public API. Covers the long tail
    that isn't in the curated kr_stock_registry. LRU-cached so repeat
    hits stay free after the first call.
    """
    try:
        from services.data import kis_market_adapter as kma
        return kma.get_name(ticker)
    except Exception:
        return None


@lru_cache(maxsize=4096)
def resolve_stock_name(ticker: str) -> Optional[str]:
    """Return the display name for `ticker`, or None if unresolvable.

    Never raises — a bad input just returns None. Caller is expected to
    fall back to the ticker itself.
    """
    if not ticker:
        return None
    t = ticker.strip()
    if not t:
        return None

    try:
        if _is_korean(t):
            # 1. Curated registry (fast, ~2,500 names, no network)
            from services import kr_stock_registry
            name = kr_stock_registry.get_name(t)
            if name:
                return name
            # 2. KIS API fallback — covers every KRX-listed ticker
            return _kis_name(t)
        from services import us_stock_registry
        return us_stock_registry.get_name(t)
    except Exception:
        # Registries load JSON at import time; any import/IO failure here
        # should never break a response. Swallow and fall through to None
        # so callers use the ticker fallback.
        return None


def name_or_ticker(ticker: str) -> str:
    """Convenience: resolve to name, fall back to ticker. Never None."""
    return resolve_stock_name(ticker) or ticker


def lookup_name_from_signal_cache(ticker: str) -> Optional[str]:
    """Fetch name from the SignalCache blob if present.

    Requires an active Flask app context + DB session. Prefer this when
    you already hold one (e.g. inside a route handler): the SignalCache
    "name" field is populated by live fetchers and often carries the
    broker-provided name, which we want to win over the static registry.
    """
    try:
        import json
        from extensions import db
        from models import SignalCache
    except Exception:
        return None
    try:
        row = db.session.get(SignalCache, ticker)
        if not row or not row.data_json:
            return None
        name = json.loads(row.data_json).get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    except Exception:
        return None
    return None
