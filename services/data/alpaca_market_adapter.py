"""PivoxQuant — Alpaca Market Data adapter (FMP fallback).

Legal data source replacement for the legacy ``yfinance_adapter``. yfinance
scrapes Yahoo Finance and its ToS forbids commercial use — Alpaca, by
contrast, is an actual US broker whose market-data API is licensed for
commercial redistribution (we already subscribe as part of the brokerage
relationship).

Design rules (match the old adapter so callers don't have to change):
  - All public functions are **safe by contract**: never raise to the caller.
    On any failure they return ``None`` / empty containers so the call site
    can short-circuit to the next fallback (e.g. stale cache, SEC EDGAR).
  - Results are normalised to the same shape FMP returns so
    ``fmp_service.get_quote/get_history/...`` can use the fallback without
    changes to downstream consumers (``engine.py``, ``quant_models.py`` etc.).
  - TTL caching lives in ``fmp_service`` — this module is stateless.
  - The alpaca-py import is deferred to call-time so missing installs
    degrade gracefully (fallback simply disables itself).

Tier notes:
  - Free IEX feed: 15-min delayed consolidated-tape proxy. Sufficient for
    MVP analytics (we are not HFT) and for overnight backtests.
  - Earnings calendar is NOT provided by Alpaca Market Data. ``get_earnings_calendar``
    returns ``[]`` — caller falls through to FMP's calendar endpoint.

Usage::

    from services.data import alpaca_market_adapter as ama

    q = ama.get_quote("AAPL")          # dict like FMP /quote item or None
    df = ama.get_history("AAPL", "3mo") # pandas.DataFrame (OHLCV) or empty
    info = ama.get_info("AAPL")        # dict subset of fmp_service.get_info
    cal = ama.get_earnings_calendar("AAPL")  # always [] (no Alpaca endpoint)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ── Period mapping ────────────────────────────────────────────────────────────
# Accept the same period strings fmp_service.get_history uses so the caller
# doesn't have to translate. Mapped to number of calendar days.
_PERIOD_DAYS: dict[str, int] = {
    "1d": 1, "5d": 5,
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825,
    "max": 3650,   # ~10y — Alpaca history depth cap on free tier
}


# ── Lazy SDK imports (fail soft if alpaca-py missing / keys unset) ───────────

def _client():
    """Return an Alpaca ``StockHistoricalDataClient`` or None.

    Deferred so missing installs / missing keys / import errors don't
    break the whole data pipeline — the fallback simply disables itself.

    Also short-circuits when ``ALPACA_ENABLED=0`` (the default kill switch —
    see config.py / Dockerfile). This is a defense-in-depth check: callers
    like ``data_fetcher.py`` already gate the fallback, but anyone importing
    this module directly still gets safe None.
    """
    # Re-read each call so tests can flip the flag via monkeypatch.
    if os.environ.get("ALPACA_ENABLED", "0").strip() not in (
        "1", "true", "True", "TRUE", "yes",
    ):
        return None
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if not key or not secret:
        return None
    try:
        from alpaca.data.historical import StockHistoricalDataClient  # type: ignore
        return StockHistoricalDataClient(key, secret)
    except Exception as exc:  # pragma: no cover — import path
        logger.info("alpaca-py unavailable (%s) — fallback disabled", exc)
        return None


def is_available() -> bool:
    """Cheap check callers can use before routing to the fallback."""
    return _client() is not None


# ── Quote ─────────────────────────────────────────────────────────────────────

def get_quote(ticker: str) -> dict | None:
    """Return a dict shaped like an FMP ``/quote`` item (subset).

    Keys: ``symbol``, ``price``, ``change``, ``changesPercentage``,
    ``previousClose``, ``dayLow``, ``dayHigh``, ``volume``, ``source``.
    Missing values are omitted rather than zero-padded so the caller can
    distinguish "not returned" from a genuine zero.

    Strategy: ``latest_bar`` gives us today's OHLCV + ``close`` (= price).
    For change vs previous close we pull the last 2 daily bars — one
    network call via ``stock-bars`` with limit=2.

    Returns ``None`` on any failure (bad ticker, network error, etc.).
    """
    client = _client()
    if client is None or not ticker:
        return None
    try:
        from alpaca.data.requests import StockBarsRequest  # type: ignore
        from alpaca.data.timeframe import TimeFrame  # type: ignore

        # Pull last ~5 trading days of daily bars to compute change vs
        # previous close. We ask for a 10-day window to absorb weekends/
        # holidays and slice the last 2 bars.
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=10)
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=5,
        )
        bars_resp = client.get_stock_bars(req)
        bars = bars_resp.data.get(ticker) if hasattr(bars_resp, "data") else None
        if not bars:
            return None
        last = bars[-1]
        prev = bars[-2] if len(bars) >= 2 else None

        price = float(last.close) if last.close is not None else None
        if price is None:
            return None
        prev_close = float(prev.close) if prev and prev.close is not None else 0.0
        change = price - prev_close if prev_close else 0.0
        change_pct = (change / prev_close * 100.0) if prev_close else 0.0

        out: dict[str, Any] = {
            "symbol": ticker,
            "price": price,
            "previousClose": prev_close if prev_close else None,
            "change": round(change, 6),
            "changesPercentage": round(change_pct, 6),
            "dayLow": float(last.low) if last.low is not None else None,
            "dayHigh": float(last.high) if last.high is not None else None,
            "volume": int(last.volume) if last.volume is not None else None,
            "source": "alpaca",
        }
        # Drop keys whose values are None so downstream ``.get()`` semantics
        # match FMP (absent vs. explicitly None).
        return {k: v for k, v in out.items() if v is not None}
    except Exception as exc:
        logger.info("alpaca get_quote(%s) failed: %s", ticker, exc)
        return None


# ── History ───────────────────────────────────────────────────────────────────

def get_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Return a daily OHLCV DataFrame matching the FMP schema.

    Columns: ``Open, High, Low, Close, Volume``. Index is a ``DatetimeIndex``
    named ``Date`` (tz-naive).

    Returns an **empty DataFrame** on any failure so callers can safely
    check ``.empty`` without try/except.
    """
    client = _client()
    if client is None or not ticker:
        return pd.DataFrame()
    days = _PERIOD_DAYS.get(period, 90)
    try:
        from alpaca.data.requests import StockBarsRequest  # type: ignore
        from alpaca.data.timeframe import TimeFrame  # type: ignore

        end = datetime.now(timezone.utc)
        # Widen window ~1.3x to absorb weekends/holidays (trading days only).
        start = end - timedelta(days=int(days * 1.3) + 5)

        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars_resp = client.get_stock_bars(req)
        bars = bars_resp.data.get(ticker) if hasattr(bars_resp, "data") else None
        if not bars:
            return pd.DataFrame()

        rows = []
        for bar in bars:
            rows.append({
                "Date": bar.timestamp,
                "Open": float(bar.open) if bar.open is not None else 0.0,
                "High": float(bar.high) if bar.high is not None else 0.0,
                "Low": float(bar.low) if bar.low is not None else 0.0,
                "Close": float(bar.close) if bar.close is not None else 0.0,
                "Volume": int(bar.volume) if bar.volume is not None else 0,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["Date"] = pd.to_datetime(df["Date"])
        # Alpaca returns tz-aware timestamps; strip tz for FMP parity.
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.set_index("Date").sort_index()
        df.index.name = "Date"

        # Trim to the requested window (caller slices by len(), so keep it tight).
        cutoff = pd.Timestamp(datetime.now()) - pd.Timedelta(days=days)
        df = df[df.index >= cutoff]
        return df
    except Exception as exc:
        logger.info("alpaca get_history(%s, %s) failed: %s", ticker, period, exc)
        return pd.DataFrame()


# ── Info / profile ────────────────────────────────────────────────────────────

def get_info(ticker: str) -> dict:
    """Return a subset of company info shaped like ``fmp_service.get_info``.

    Alpaca does NOT expose full company fundamentals — only basic asset
    metadata (name, exchange, tradable). For anything richer the caller
    should stay on FMP (primary) or SEC EDGAR (US fundamentals fallback).

    Returns ``{}`` on failure.
    """
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if not key or not secret or not ticker:
        return {}
    try:
        # alpaca-py trading client exposes the asset master.
        from alpaca.trading.client import TradingClient  # type: ignore

        tc = TradingClient(key, secret, paper=True)
        asset = tc.get_asset(ticker)
        if asset is None:
            return {}
        return {
            "source": "alpaca",
            "shortName": getattr(asset, "name", "") or ticker,
            "longName": getattr(asset, "name", "") or ticker,
            "exchange": str(getattr(asset, "exchange", "") or ""),
            "currency": "USD",
            "symbol": ticker,
        }
    except Exception as exc:
        logger.info("alpaca get_info(%s) failed: %s", ticker, exc)
        return {}


# ── Earnings calendar ─────────────────────────────────────────────────────────

def get_earnings_calendar(ticker: str) -> list[dict]:
    """Alpaca Market Data does NOT publish an earnings calendar.

    Kept for API parity with the old yfinance adapter — always returns
    ``[]`` so ``fmp_service.get_earnings_calendar`` falls through to its
    primary (FMP) endpoint. Tiingo free-tier / EDGAR 8-K calendar could
    be wired here later if needed.
    """
    return []


# ── Helper: timestamp for callers logging fallback events ─────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
