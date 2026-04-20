"""PivoxQuant — yfinance adapter (FMP fallback).

Thin wrapper around the ``yfinance`` package so the rest of the codebase can
treat Yahoo! Finance as a drop-in fallback for FMP when the free/Starter tier
returns 402, hits daily budget, or is down entirely.

Design rules:
  - All functions are **safe by contract**: never raise to the caller.
    On any failure they return ``None`` / empty containers so the call site
    can short-circuit to the next fallback (e.g. stale cache, SEC EDGAR).
  - Results are normalised to the same shape FMP returns so
    ``fmp_service.get_quote/get_history/...`` can use the fallback without
    changes to downstream consumers (``engine.py``, ``quant_models.py`` etc.).
  - TTL caching lives in ``fmp_service`` — this module is stateless.
  - The ``yfinance`` import is deferred to call-time so missing installs
    degrade gracefully (fallback simply disables itself).

Usage::

    from services.data import yfinance_adapter as yfa

    q = yfa.get_quote("AAPL")          # dict like FMP /quote item or None
    df = yfa.get_history("AAPL", "3mo") # pandas.DataFrame (OHLCV) or empty
    info = yfa.get_info("AAPL")        # dict subset of fmp_service.get_info
    cal = yfa.get_earnings_calendar("AAPL")  # list[dict] or []
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ── Period mapping ────────────────────────────────────────────────────────────
# Accept the same period strings fmp_service.get_history uses so the caller
# doesn't have to translate.
_YF_PERIOD_MAP = {
    "1d": "1d", "5d": "5d",
    "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
    "1y": "1y", "2y": "2y", "5y": "5y",
    "max": "max",
}


def _yf():
    """Import yfinance lazily. Returns the module or ``None``.

    Deferred so missing installs / import-time errors don't break the whole
    data pipeline — the fallback simply disables itself.
    """
    try:
        import yfinance as yf  # type: ignore[import-not-found]
        return yf
    except Exception as exc:  # pragma: no cover — import path
        logger.info("yfinance unavailable (%s) — fallback disabled", exc)
        return None


def is_available() -> bool:
    """Cheap check callers can use before routing to the fallback."""
    return _yf() is not None


# ── Quote ─────────────────────────────────────────────────────────────────────

def get_quote(ticker: str) -> dict | None:
    """Return a dict shaped like an FMP ``/quote`` item (subset).

    Keys: ``symbol``, ``name``, ``price``, ``change``, ``changesPercentage``,
    ``previousClose``, ``dayLow``, ``dayHigh``, ``volume``, ``marketCap``,
    ``exchange``. Missing values are omitted rather than zero-padded so the
    caller can distinguish "not returned" from a genuine zero.

    Returns ``None`` on any failure (bad ticker, network error, etc.).
    """
    yf = _yf()
    if yf is None or not ticker:
        return None
    try:
        tk = yf.Ticker(ticker)
        # ``fast_info`` is cached on first access and avoids the slow
        # ``.info`` dict (which scrapes HTML). We only fall back to
        # ``.info`` for fields ``fast_info`` doesn't expose.
        fi = tk.fast_info
        price = fi.get("last_price") if hasattr(fi, "get") else getattr(fi, "last_price", None)
        prev = fi.get("previous_close") if hasattr(fi, "get") else getattr(fi, "previous_close", None)
        if price is None:
            return None
        price = float(price)
        prev_f = float(prev) if prev else 0.0
        change = price - prev_f if prev_f else 0.0
        change_pct = (change / prev_f * 100.0) if prev_f else 0.0

        def _safe(attr, default=None):
            try:
                v = fi.get(attr) if hasattr(fi, "get") else getattr(fi, attr, None)
                return v if v is not None else default
            except Exception:
                return default

        out: dict[str, Any] = {
            "symbol": ticker,
            "price": price,
            "previousClose": prev_f if prev_f else None,
            "change": round(change, 6),
            "changesPercentage": round(change_pct, 6),
            "dayLow": _safe("day_low"),
            "dayHigh": _safe("day_high"),
            "volume": _safe("last_volume"),
            "marketCap": _safe("market_cap"),
            "exchange": _safe("exchange"),
            "source": "yfinance",
        }
        # Drop keys whose values are None so downstream ``.get()`` semantics
        # match FMP (absent vs. explicitly None).
        return {k: v for k, v in out.items() if v is not None}
    except Exception as exc:
        logger.info("yfinance get_quote(%s) failed: %s", ticker, exc)
        return None


# ── History ───────────────────────────────────────────────────────────────────

def get_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Return a daily OHLCV DataFrame matching the FMP schema.

    Columns: ``Open, High, Low, Close, Volume`` (plus ``Adj Close`` when
    available). Index is a ``DatetimeIndex`` named ``Date``.

    Returns an **empty DataFrame** on any failure so callers can safely
    check ``.empty`` without try/except.
    """
    yf = _yf()
    if yf is None or not ticker:
        return pd.DataFrame()
    yf_period = _YF_PERIOD_MAP.get(period, "3mo")
    try:
        # auto_adjust=False preserves the raw Close + separate Adj Close so
        # backtester / indicators that want raw prices aren't surprised.
        df = yf.download(
            ticker,
            period=yf_period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if df is None or df.empty:
            return pd.DataFrame()

        # yfinance may return a MultiIndex for single-ticker requests in
        # newer releases (columns = [(Open, AAPL), ...]). Flatten it.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        # Ensure index is tz-naive DatetimeIndex named 'Date' (FMP schema).
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "Date"
        df = df.sort_index()

        # Guarantee required columns exist (defensive)
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col not in df.columns:
                df[col] = 0

        keep = [c for c in ("Open", "High", "Low", "Close", "Adj Close", "Volume") if c in df.columns]
        return df[keep]
    except Exception as exc:
        logger.info("yfinance get_history(%s, %s) failed: %s", ticker, period, exc)
        return pd.DataFrame()


# ── Info / profile ────────────────────────────────────────────────────────────

def get_info(ticker: str) -> dict:
    """Return a subset of company info shaped like ``fmp_service.get_info``.

    Only fields yfinance reliably provides are populated. Returns ``{}`` on
    failure. The call may be slow (yfinance scrapes HTML for ``.info``), so
    callers should cache results just like they do for FMP.
    """
    yf = _yf()
    if yf is None or not ticker:
        return {}
    try:
        tk = yf.Ticker(ticker)
        # ``get_info()`` is the stable accessor in yfinance >= 0.2.30; older
        # versions expose ``.info``. Try both.
        info_raw: dict = {}
        try:
            info_raw = tk.get_info() or {}
        except Exception:
            info_raw = getattr(tk, "info", {}) or {}
        if not isinstance(info_raw, dict) or not info_raw:
            return {}

        price = info_raw.get("currentPrice") or info_raw.get("regularMarketPrice") or 0
        last_div = info_raw.get("lastDividendValue") or info_raw.get("dividendRate") or 0
        div_yield = info_raw.get("dividendYield") or (last_div / price if price else 0)

        out = {
            "source": "yfinance",
            "shortName": info_raw.get("shortName") or ticker,
            "longName": info_raw.get("longName") or info_raw.get("shortName") or ticker,
            "longBusinessSummary": info_raw.get("longBusinessSummary") or "",
            "sector": info_raw.get("sector") or "",
            "industry": info_raw.get("industry") or "",
            "marketCap": info_raw.get("marketCap") or 0,
            "beta": info_raw.get("beta") or 1.0,
            "price": price,
            "website": info_raw.get("website") or "",
            "fullTimeEmployees": info_raw.get("fullTimeEmployees") or 0,
            "country": info_raw.get("country") or "",
            "exchange": info_raw.get("exchange") or "",
            "currency": info_raw.get("currency") or "USD",
            "52WeekHigh": info_raw.get("fiftyTwoWeekHigh") or 0,
            "52WeekLow": info_raw.get("fiftyTwoWeekLow") or 0,
            "dividendYield": div_yield,
            "trailingPE": info_raw.get("trailingPE") or 0,
            "forwardPE": info_raw.get("forwardPE") or 0,
            "priceToBook": info_raw.get("priceToBook") or 0,
            "trailingEps": info_raw.get("trailingEps") or 0,
            "floatShares": info_raw.get("floatShares") or info_raw.get("sharesOutstanding"),
        }
        return out
    except Exception as exc:
        logger.info("yfinance get_info(%s) failed: %s", ticker, exc)
        return {}


# ── Earnings calendar ─────────────────────────────────────────────────────────

def get_earnings_calendar(ticker: str) -> list[dict]:
    """Return upcoming earnings events for a single ticker.

    Shape matches FMP ``/earnings-calendar`` items (subset):
      ``{symbol, date, epsEstimated, revenueEstimated}``.

    Returns ``[]`` on failure. yfinance only exposes the **next** earnings
    event per ticker, so callers that want a multi-ticker calendar should
    iterate.
    """
    yf = _yf()
    if yf is None or not ticker:
        return []
    try:
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        if cal is None:
            return []

        # yfinance returns either a dict (new) or a DataFrame (old).
        if isinstance(cal, dict):
            earnings_dates = cal.get("Earnings Date") or cal.get("earningsDate") or []
            # The field can be a list (range) or a single datetime.
            if earnings_dates and not isinstance(earnings_dates, list):
                earnings_dates = [earnings_dates]
            if not earnings_dates:
                return []
            # Use the first (earliest) date in the range.
            raw_dt = earnings_dates[0]
            try:
                dt_str = (
                    raw_dt.strftime("%Y-%m-%d")
                    if hasattr(raw_dt, "strftime")
                    else str(raw_dt)[:10]
                )
            except Exception:
                return []
            eps_est = cal.get("Earnings Average") or cal.get("epsEstimated") or None
            rev_est = cal.get("Revenue Average") or cal.get("revenueEstimated") or None
            return [{
                "symbol": ticker,
                "date": dt_str,
                "epsEstimated": float(eps_est) if eps_est is not None else None,
                "revenueEstimated": float(rev_est) if rev_est is not None else None,
                "source": "yfinance",
            }]

        # DataFrame path (yfinance < 0.2.30)
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            col = cal.iloc[:, 0]
            raw_dt = col.get("Earnings Date") if hasattr(col, "get") else None
            if raw_dt is None:
                return []
            dt_str = (
                raw_dt.strftime("%Y-%m-%d")
                if hasattr(raw_dt, "strftime")
                else str(raw_dt)[:10]
            )
            return [{
                "symbol": ticker,
                "date": dt_str,
                "epsEstimated": None,
                "revenueEstimated": None,
                "source": "yfinance",
            }]
    except Exception as exc:
        logger.info("yfinance get_earnings_calendar(%s) failed: %s", ticker, exc)
    return []


# ── Helper: timestamp for callers logging fallback events ─────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
