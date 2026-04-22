"""
Price freshness overlay.

Fetches the latest prices for a batch of tickers via
realtime_service.get_prices_batch and returns a dict
{ticker: {price, change_pct, observed_at, source}} — used to overlay
stale SignalCache data in portfolio/watchlist responses so users never
see a "current" price that's actually days old.

Priority per ticker:
  1) realtime_service (Alpaca latest trade/quote, KIS WS/REST) — always fresh
  2) SignalCache row, only if not stale (TTL_SECONDS window, see models.SignalCache)
  3) Omitted from response (caller falls back to avg_cost / last known)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

from services.container import realtime
from services import cache_service

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def overlay_prices(tickers: Iterable[str]) -> dict:
    """Return {ticker: {price, change_pct, observed_at, source}}.

    Never raises. Missing tickers are simply absent from the returned dict
    so the caller can apply its own fallback (avg_cost, 0, etc).
    """
    tickers = [t for t in (tickers or []) if t]
    out: dict = {}
    if not tickers:
        return out

    now = _now_iso()

    # ── 1) realtime first (Alpaca latest trade / KIS WS+REST) ──
    rt: dict = {}
    try:
        rt = realtime.get_prices_batch(tickers) or {}
    except Exception:
        logger.exception("overlay_prices: realtime batch failed")
        rt = {}

    for t in tickers:
        r = rt.get(t) or rt.get(t.upper()) or {}
        price = r.get("price")
        if price:
            try:
                chg = float(r.get("change_pct") or 0)
            except (TypeError, ValueError):
                chg = 0.0
            out[t] = {
                "price": float(price),
                "change_pct": chg,
                "observed_at": r.get("timestamp") or now,
                "source": "realtime",
            }
            continue

        # ── 2) SignalCache, only if NOT stale ──
        try:
            cached = cache_service.get_signal(t)  # returns None when stale
        except Exception:
            logger.exception("overlay_prices: cache lookup failed ticker=%s", t)
            cached = None
        if cached and cached.data_json:
            try:
                sd = json.loads(cached.data_json)
            except (TypeError, ValueError):
                sd = {}
            cp = sd.get("price")
            if cp:
                try:
                    chg = float(sd.get("change_pct") or 0)
                except (TypeError, ValueError):
                    chg = 0.0
                out[t] = {
                    "price": float(cp),
                    "change_pct": chg,
                    "observed_at": cached.updated_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                    if cached.updated_at else now,
                    "source": "cache",
                }

    return out
