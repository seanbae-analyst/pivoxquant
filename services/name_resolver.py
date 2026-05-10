"""Unified company-name resolver.

Returns a human-friendly company name for any ticker we display. Used by
every serializer/response builder that emits a stock so the frontend can
render the name large and the ticker small — on every page.

Resolution order (per ticker)
-----------------------------
Korean tickers (suffix .KS / .KQ):
  1. ``kr_stock_registry.get_name()`` — curated KOSPI/KOSDAQ + full
     KRX master JSON (~2,770 names, offline)
  2. ``SignalCache`` "name" blob — populated by KIS / data_fetcher live
     calls; covers ETFs, recent IPOs, anything not in the static JSON
  3. KIS API fallback (``services.data.kis_market_adapter``) — paid
     quota, last resort for the long tail
US tickers (everything else):
  1. ``us_stock_registry.get_name()`` — Alpaca asset master (~12,700)
  2. ``SignalCache`` "name" blob — covers small-cap or recently listed
     symbols not in the Alpaca master at build time

Fallback
--------
When nothing resolves, returns ``None``. Callers should default to the
ticker itself — keeping current behaviour is the explicit contract so
adding this helper is always safe.

Observability (B8 / B10)
------------------------
Every miss is logged at ``DEBUG`` with the ticker and the rung that
fired, so rerunning a session at ``-v --log-cli-level=DEBUG`` pinpoints
which registries are missing entries. The log channel is
``services.name_resolver``.

Design notes
------------
- Pure-function by default. ``resolve_stock_name`` makes no DB calls.
- ``resolve_stock_name_with_db`` is the opt-in extension that uses the
  SignalCache rung; pass it from inside Flask request handlers that
  already hold an app context. ``lookup_name_from_signal_cache`` is
  retained for callers that want only the cache rung.
- All lookups are case-insensitive via ``.upper()`` in the underlying
  registries.
- Legacy note: the pyKRX name fallback was removed (2026-04-19) — pyKRX
  scrapes KRX in a legal grey area. The curated JSON plus KIS API
  cover the same ground without the ToS risk.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional
import logging

logger = logging.getLogger(__name__)


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
        logger.debug("silent-fallback: _kis_name", exc_info=True)
        return None


@lru_cache(maxsize=4096)
def resolve_stock_name(ticker: str) -> Optional[str]:
    """Return the display name for ``ticker``, or ``None`` if unresolvable.

    Pure: no DB, no app context. Falls through static registries only.
    Use ``resolve_stock_name_with_db`` from inside a request when the
    SignalCache rung is desired (covers KRX ETFs, recent IPOs, etc).

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
            # 1. Curated registry (fast, ~2,770 names, no network)
            from services import kr_stock_registry
            name = kr_stock_registry.get_name(t)
            if name:
                return name
            # 2. KIS API fallback — covers every KRX-listed ticker
            name = _kis_name(t)
            if name:
                return name
            logger.debug("name_resolver miss (KR, all rungs): ticker=%s", t)
            return None
        # US ticker
        from services import us_stock_registry
        name = us_stock_registry.get_name(t)
        if name:
            return name
        logger.debug("name_resolver miss (US, registry): ticker=%s", t)
        return None
    except Exception:
        logger.debug("silent-fallback: resolve_stock_name", exc_info=True)
        # Registries load JSON at import time; any import/IO failure here
        # should never break a response. Swallow and fall through to None
        # so callers use the ticker fallback.
        return None


def resolve_stock_name_with_db(ticker: str) -> Optional[str]:
    """Full-fallback resolver — adds the SignalCache DB rung.

    Use this from request handlers that already hold an app context.
    Order:
      1. Static registry (curated + full master)
      2. SignalCache blob (broker-populated names, covers ETFs / new IPOs)
      3. KIS API for KRX (live)

    Returns ``None`` when every rung misses.
    """
    if not ticker:
        return None
    t = ticker.strip()
    if not t:
        return None

    try:
        if _is_korean(t):
            from services import kr_stock_registry
            name = kr_stock_registry.get_name(t)
            if name:
                return name
            # New rung — DB cache often has the name even when registries
            # don't (e.g. KODEX 200 ETF, recent IPOs).
            name = lookup_name_from_signal_cache(t)
            if name:
                logger.debug(
                    "name_resolver fallback hit (SignalCache): ticker=%s name=%s",
                    t, name,
                )
                return name
            name = _kis_name(t)
            if name:
                return name
            logger.debug("name_resolver miss (KR, all rungs): ticker=%s", t)
            return None
        # US ticker
        from services import us_stock_registry
        name = us_stock_registry.get_name(t)
        if name:
            return name
        name = lookup_name_from_signal_cache(t)
        if name:
            logger.debug(
                "name_resolver fallback hit (SignalCache): ticker=%s name=%s",
                t, name,
            )
            return name
        logger.debug("name_resolver miss (US, all rungs): ticker=%s", t)
        return None
    except Exception:
        logger.debug("silent-fallback: resolve_stock_name_with_db", exc_info=True)
        return None


def name_or_ticker(ticker: str) -> str:
    """Convenience: resolve to name, fall back to ticker. Never None."""
    return resolve_stock_name(ticker) or ticker


def canonical_display_name(cached_name, ticker: str) -> str:
    """Return the canonical display name for ``ticker``.

    Defensive follow-up to BUG-01 (PR #227, 2026-05-10). PR #227 fixed
    the *source* — ``services/data/fetcher.py`` now queries
    ``kr_stock_registry`` first, so new SignalCache rows store
    "삼성전자" instead of "Samsung Electronics". But rows persisted
    **before** that PR still hold the English label. Until those rows
    are re-cached, route handlers that read from SignalCache would
    surface English on the detail H1.

    Policy
    ------
    - KR tickers (``.KS`` / ``.KQ``): Korean from ``kr_stock_registry``
      ALWAYS wins, regardless of any cached value.
    - US tickers: cached/snapshot English wins; fall back to resolver,
      then ticker.

    User has repeatedly directed (memory ``feedback_ticker_display``)
    that KR stocks must render in Korean throughout the product.
    """
    t = (ticker or "").strip()
    if not t:
        return ticker or ""
    if _is_korean(t):
        kr = resolve_stock_name(t)
        if kr:
            return kr
    if cached_name and cached_name != t:
        return cached_name
    return resolve_stock_name(t) or t


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
        logger.debug("silent-fallback: lookup_name_from_signal_cache", exc_info=True)
        return None
    try:
        row = db.session.get(SignalCache, ticker)
        if not row or not row.data_json:
            return None
        name = json.loads(row.data_json).get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    except Exception:
        logger.debug("silent-fallback: lookup_name_from_signal_cache", exc_info=True)
        return None
    return None
