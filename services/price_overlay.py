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
  3) SignalCache `price_display` string ("$402.91", "₩42,100") parsed — last
     line of defense before we hand the caller a 0 that would render as "$0".
     This covers the Bug C regression where realtime was dead, SignalCache
     was stale (so `price` = None via get_signal), but the blob still had
     a human-readable `price_display` from an earlier scan. The caller
     marked the row as "stale" which is honest; we just stop it rendering
     as `$0`.
  4) Omitted from response (caller falls back to avg_cost / last known)
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from models import SignalCache
from services.container import realtime
from services import cache_service

logger = logging.getLogger(__name__)

# Matches an unsigned/signed number with optional commas + decimal inside a
# currency-decorated string like "$402.91", "₩42,100", "€1,234.56", "-$3.14".
# We strip currency symbols and thousands-separator commas before float().
_PRICE_DISPLAY_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def parse_price_display(display: Optional[str]) -> Optional[float]:
    """Parse "$402.91" / "₩42,100" / "1,234.56" → float.

    Returns None on any shape we can't confidently parse ("—", "", "N/A", None).
    Callers should treat None as "no fallback available".
    """
    if not display or not isinstance(display, str):
        return None
    s = display.strip()
    if not s or s in ("—", "-", "N/A", "n/a", "null", "None"):
        return None
    m = _PRICE_DISPLAY_RE.search(s)
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v


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

    # For tier-3 (stale-cache price_display parse), we need the raw
    # SignalCache row even when get_signal() returns None because the row
    # is beyond its TTL. Batch-load once to avoid N+1.
    stale_map: dict = {}
    try:
        rows = SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
        stale_map = {r.ticker: r for r in rows}
    except Exception:
        logger.exception("overlay_prices: SignalCache batch load failed")

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
                continue

        # ── 3) Stale-cache price_display parse fallback (Bug C) ──
        # Even when SignalCache row is beyond TTL, a human-readable
        # price_display like "$402.91" is better than 0 / "—".
        stale_row = stale_map.get(t)
        if stale_row and stale_row.data_json:
            try:
                sd2 = json.loads(stale_row.data_json)
            except (TypeError, ValueError):
                sd2 = {}
            parsed = parse_price_display(sd2.get("price_display")) or parse_price_display(str(sd2.get("price") or ""))
            if parsed:
                try:
                    chg2 = float(sd2.get("change_pct") or 0)
                except (TypeError, ValueError):
                    chg2 = 0.0
                out[t] = {
                    "price": parsed,
                    "change_pct": chg2,
                    "observed_at": stale_row.updated_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                    if stale_row.updated_at else None,
                    "source": "stale_display",
                }

    return out
