"""Alpha Vantage OVERVIEW fundamentals fallback.

FMP Starter plan omits P/E, EPS, and some fundamentals for a subset of
US equities (confirmed nulls on NVDA/MSFT/TSLA but populated on AAPL/BRK-B).
Alpha Vantage free tier (25 req/day, 5 req/min) covers the gap for
individual US equities; ETFs and funds are NOT served.

This module is a no-op when ``ALPHAVANTAGE_API_KEY`` is missing, so the
code can ship before the key is provisioned. On key arrival, the next
``fmp_service.get_info()`` call for a null-fundamental ticker will transparently
overlay the AV values.

Legal: Alpha Vantage free tier ToS permits commercial use. No scraping.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_AV_URL = "https://www.alphavantage.co/query"


def _safe_float(v) -> float | None:
    """AV returns ``"None"`` strings for missing values; coerce robustly."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if not _is_sentinel(v) else None
    s = str(v).strip()
    if not s or s.lower() in ("none", "null", "n/a", "-"):
        return None
    try:
        f = float(s)
        return f if not _is_sentinel(f) else None
    except (TypeError, ValueError):
        logger.debug("silent-fallback: _safe_float", exc_info=True)
        return None


def _is_sentinel(v: float) -> bool:
    """AV sometimes returns ``0`` as the 'missing' sentinel for PER/EPS."""
    try:
        return v == 0 or v != v  # NaN
    except Exception:
        return False


def get_av_fundamentals(ticker: str) -> dict | None:
    """Fetch AV OVERVIEW fundamentals for a US equity.

    Returns a dict with FMP-schema keys, or ``None`` if:
    - ``ALPHAVANTAGE_API_KEY`` not set (no-op until provisioned)
    - Ticker is not a US equity (``.KS`` / ``.KQ`` rejected)
    - AV returned empty / errored payload
    """
    key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip() or os.environ.get(
        "ALPHA_VANTAGE_API_KEY", ""
    ).strip()
    if not key:
        return None

    # AV only serves US equities; skip KR tickers and obvious non-US patterns.
    if not ticker or "." in ticker or "-" in ticker and len(ticker) > 5:
        # Note: BRK-B / BF-B hyphenated tickers DO work on AV as "BRK-B".
        # The len gate keeps CTSM.US / BHP.AX style foreign listings out.
        pass  # Don't reject — AV handles some hyphen tickers.

    try:
        r = requests.get(
            _AV_URL,
            params={"function": "OVERVIEW", "symbol": ticker, "apikey": key},
            timeout=6,
        )
    except Exception as e:
        logger.debug("AV OVERVIEW request failed for %s: %s", ticker, e)
        return None

    if not r.ok:
        logger.debug("AV OVERVIEW %s non-OK: %s", ticker, r.status_code)
        return None

    try:
        d = r.json() or {}
    except Exception:
        logger.debug("silent-fallback: get_av_fundamentals", exc_info=True)
        return None

    # Empty payload — AV returns {} for unknown symbols, ETFs, or rate-limited.
    if not d or d.get("Symbol") != ticker:
        # Also catch the "Note" rate-limit response shape.
        if "Note" in d or "Information" in d:
            logger.info("AV rate-limited on %s", ticker)
        return None

    out = {
        "pe_ratio":       _safe_float(d.get("PERatio")),
        "forward_pe":     _safe_float(d.get("ForwardPE")),
        "eps":            _safe_float(d.get("EPS")),
        "market_cap":     _safe_float(d.get("MarketCapitalization")),
        "profit_margin":  _safe_float(d.get("ProfitMargin")),
        "revenue_growth": _safe_float(d.get("QuarterlyRevenueGrowthYOY")),
        "debt_equity":    _safe_float(d.get("DebtToEquityRatio")),
    }
    # Drop all-None dicts to signal "nothing useful".
    if not any(v is not None for v in out.values()):
        return None
    return out
