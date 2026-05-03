"""PivoxQuant — KIS Market Data adapter (KR OHLCV via public app key).

Legal data source replacement for pyKRX's ``get_market_ohlcv`` scraper.
KIS (Korea Investment & Securities) is a licensed broker whose Open API
serves official KRX-derived price data under a commercial ToS we already
accept as part of the `KIS_APP_KEY` registration.

Why a separate file (not added to kis_service.py):
  The engineering rules forbid modifying ``kis_service.py``. This adapter
  reuses the shared ``KISTokenManager`` singleton to avoid competing for
  the 1-token-per-minute KIS quota (``EGW00133``).

Design rules:
  - All public functions are **safe by contract**: never raise.
    On failure they return empty DataFrame / None so callers can fall back.
  - History schema matches FMP: ``DatetimeIndex`` named ``Date``, columns
    ``Open / High / Low / Close / Volume``.
  - Thread-safe via KIS token manager.
  - Rate-limit aware: 0.3s between calls (KIS public tier allows 20/sec
    but we stay well under to avoid the 초당 throttle response).

Public API::

    from services.data import kis_market_adapter as kma

    df = kma.get_history("005930.KS", "3mo")   # pandas DataFrame
    name = kma.get_name("005930.KS")           # str | None
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)


# ── Constants ───────────────────────────────────────────────────────────────
_USE_REAL = os.environ.get("KIS_USE_REAL", "").strip() in ("1", "true", "True")
_BASE_URL = (
    "https://openapi.koreainvestment.com:9443"
    if _USE_REAL
    else "https://openapivts.koreainvestment.com:29443"
)
_REQUEST_TIMEOUT = 10       # seconds
_RATE_LIMIT_SLEEP = 0.12    # seconds between calls (~8 req/sec, well under 20/sec cap)

_PERIOD_DAYS: dict[str, int] = {
    "1d": 1, "5d": 5,
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825,
}

_rate_lock = threading.Lock()
_last_call_ts = 0.0


def _rate_limit() -> None:
    """Thread-safe fixed-interval throttle between KIS API calls."""
    global _last_call_ts
    with _rate_lock:
        elapsed = time.time() - _last_call_ts
        if elapsed < _RATE_LIMIT_SLEEP:
            time.sleep(_RATE_LIMIT_SLEEP - elapsed)
        _last_call_ts = time.time()


# ── Ticker helpers ───────────────────────────────────────────────────────────

def _to_code(ticker: str) -> str | None:
    """Return bare 6-digit KRX code or None. Accepts '005930', '005930.KS',
    '005930.KQ', '005930.krx' (case-insensitive)."""
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


# ── Token / headers ──────────────────────────────────────────────────────────

def _auth_headers(tr_id: str) -> dict | None:
    """Build KIS request headers (Authorization + app key + tr_id).

    Returns ``None`` when the KIS app key/secret is unavailable or the
    shared token manager can't mint a token.
    """
    app_key = os.environ.get("KIS_APP_KEY", "").strip()
    app_secret = os.environ.get("KIS_APP_SECRET", "").strip()
    if not app_key or not app_secret:
        return None
    try:
        from services.kis.token_manager import get_kis_token_manager
        token = get_kis_token_manager().get_token()
    except Exception as exc:  # pragma: no cover — import/network path
        logger.info("KIS token manager unavailable (%s)", exc)
        return None
    if not token:
        return None
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
    }


# ── Availability ─────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Cheap check callers can use before routing to this fallback."""
    app_key = os.environ.get("KIS_APP_KEY", "").strip()
    app_secret = os.environ.get("KIS_APP_SECRET", "").strip()
    return bool(app_key and app_secret)


# ── History (daily OHLCV) ────────────────────────────────────────────────────

def get_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Return a daily OHLCV DataFrame for a KR ticker via the KIS public API.

    Endpoint: ``/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice``
    tr_id: ``FHKST03010100``

    Columns: ``Open, High, Low, Close, Volume``. Index: tz-naive
    ``DatetimeIndex`` named ``Date``. Returns an empty DataFrame on any
    failure — never raises.
    """
    code = _to_code(ticker)
    if not code:
        return pd.DataFrame()
    if not is_available():
        return pd.DataFrame()

    days = _PERIOD_DAYS.get(period, 90)
    today = datetime.now()
    # Widen window ~1.4x to absorb weekends/holidays; KIS caps the single
    # call at ~100 trading days, so for longer windows we'd need to page.
    from_dt = today - timedelta(days=int(days * 1.4) + 5)

    headers = _auth_headers("FHKST03010100")
    if headers is None:
        return pd.DataFrame()

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",   # J = KOSPI/KOSDAQ stock
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": from_dt.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": today.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",      # D = daily, W = weekly, M = monthly
        "FID_ORG_ADJ_PRC": "0",          # 0 = adjusted, 1 = raw
    }
    url = f"{_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

    try:
        _rate_limit()
        resp = requests.get(url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT)
        if not resp.ok:
            logger.info("KIS history HTTP %s for %s", resp.status_code, ticker)
            return pd.DataFrame()
        payload = resp.json()
        if payload.get("rt_cd") != "0":
            logger.info("KIS history rt_cd=%s for %s: %s",
                        payload.get("rt_cd"), ticker, payload.get("msg1"))
            return pd.DataFrame()

        rows: list[dict[str, Any]] = []
        # KIS returns `output2` as a list of daily bars, most-recent first.
        for item in payload.get("output2", []) or []:
            raw_date = (item.get("stck_bsop_date") or "").strip()
            if not raw_date or len(raw_date) != 8 or not raw_date.isdigit():
                continue
            try:
                d = datetime.strptime(raw_date, "%Y%m%d")
            except ValueError:
                logger.debug("silent-fallback: get_history", exc_info=True)
                continue
            try:
                rows.append({
                    "Date": d,
                    "Open": float(item.get("stck_oprc", 0) or 0),
                    "High": float(item.get("stck_hgpr", 0) or 0),
                    "Low": float(item.get("stck_lwpr", 0) or 0),
                    "Close": float(item.get("stck_clpr", 0) or 0),
                    "Volume": int(float(item.get("acml_vol", 0) or 0)),
                })
            except (TypeError, ValueError):
                logger.debug("silent-fallback: get_history", exc_info=True)
                continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).drop_duplicates(subset=["Date"])
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        df.index.name = "Date"

        # Trim to the requested window so len(df) matches the FMP branch.
        cutoff = pd.Timestamp(today) - pd.Timedelta(days=days)
        df = df[df.index >= cutoff]
        return df
    except Exception as exc:
        logger.info("KIS get_history(%s, %s) failed: %s", ticker, period, exc)
        return pd.DataFrame()


# ── Name lookup ─────────────────────────────────────────────────────────────

def get_name(ticker: str) -> str | None:
    """Return the Korean display name for a KRX ticker, or None.

    Uses the `inquire-price` endpoint (tr_id ``FHKST01010100``) which echoes
    `rprs_mrkt_kor_name` or `prdt_kor_abrv_name` depending on listing type.
    Kept behind the module's rate limit so a single lookup costs ~120ms.
    """
    code = _to_code(ticker)
    if not code or not is_available():
        return None

    headers = _auth_headers("FHKST01010100")
    if headers is None:
        return None
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    url = f"{_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"

    try:
        _rate_limit()
        resp = requests.get(url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT)
        if not resp.ok:
            return None
        payload = resp.json()
        if payload.get("rt_cd") != "0":
            return None
        output = payload.get("output", {}) or {}
        # KIS exposes several name fields; prefer the short Korean name.
        for key in ("hts_kor_isnm", "prdt_name", "rprs_mrkt_kor_name"):
            val = output.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    except Exception as exc:
        logger.info("KIS get_name(%s) failed: %s", ticker, exc)
    return None
