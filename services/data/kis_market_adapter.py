"""PivoxQuant — KIS Market Data adapter (KR OHLCV via public app key).

⚠️ LEGAL STATUS (2026-06-03 audit — CORRECTION; do not rely on the old claim).
This was introduced as a "legal replacement for pyKRX". That premise is WRONG.
A KIS ``KIS_APP_KEY`` registration does NOT grant the right to REDISTRIBUTE
KRX-derived market data to third parties (our users). KIS serves KRX/KOSCOM
market data; third-party display/redistribution requires a SEPARATE KOSCOM
시세 license + KRX 정보이용계약 — which non-제도권 fintechs generally cannot
obtain (KIS Developers provider-info + KOSCOM open-api docs, 2026-06-03).
Using this adapter as the KR market-data feed shown to users (the current
``fetcher.py`` "KR: KIS primary" routing) is a redistribution-license gap and
a SHIP-BLOCKER before paid launch (SHIP_BLOCKERS R7). It is the SAME landmine
that got pyKRX banned, reached through a different door — NOT a legal fix.
Until a vendor/lawyer sign-off lands (legal_question_queue Q-KIS1~4), scope KIS
to surface-1 only (the user's OWN account balance, read-only) and source KR
market quotes from a licensed vendor (FMP Commercial) or 금융위 공공데이터 (T+1).

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
    "1mo": 30, "2mo": 60, "3mo": 90, "6mo": 180,
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

def _single_call(
    code: str,
    start_date: str,
    end_date: str,
    headers: dict,
) -> list[dict[str, Any]]:
    """Single-page KIS chart API call.  Returns raw row dicts or []."""
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }
    url = f"{_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    try:
        _rate_limit()
        resp = requests.get(url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT)
        if not resp.ok:
            logger.info("KIS chart HTTP %s (code=%s)", resp.status_code, code)
            return []
        payload = resp.json()
        if payload.get("rt_cd") != "0":
            logger.info("KIS chart rt_cd=%s for %s: %s",
                        payload.get("rt_cd"), code, payload.get("msg1"))
            return []
        return payload.get("output2") or []
    except Exception as exc:
        logger.info("KIS _single_call(%s) failed: %s", code, exc)
        return []


def _parse_rows(records: list[dict[str, Any]]) -> tuple[list[dict], str | None]:
    """Parse KIS output2 records into row dicts.

    Returns ``(rows, earliest_date_str)`` where ``earliest_date_str`` is
    the minimum ``stck_bsop_date`` seen (``"YYYYMMDD"`` or ``None``).
    """
    rows: list[dict[str, Any]] = []
    earliest: str | None = None
    for item in records:
        raw_date = (item.get("stck_bsop_date") or "").strip()
        if not raw_date or len(raw_date) != 8 or not raw_date.isdigit():
            continue
        if earliest is None or raw_date < earliest:
            earliest = raw_date
        try:
            d = datetime.strptime(raw_date, "%Y%m%d")
            rows.append({
                "Date": d,
                "Open": float(item.get("stck_oprc", 0) or 0),
                "High": float(item.get("stck_hgpr", 0) or 0),
                "Low": float(item.get("stck_lwpr", 0) or 0),
                "Close": float(item.get("stck_clpr", 0) or 0),
                "Volume": int(float(item.get("acml_vol", 0) or 0)),
            })
        except (TypeError, ValueError):
            logger.debug("silent-fallback: _parse_rows", exc_info=True)
    return rows, earliest


def _rows_to_df(rows: list[dict], days: int, today: datetime) -> pd.DataFrame:
    """Convert parsed rows to a cleaned OHLCV DataFrame trimmed to *days*."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates(subset=["Date"])
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df.index.name = "Date"
    cutoff = pd.Timestamp(today) - pd.Timedelta(days=days)
    return df[df.index >= cutoff]


def get_history(
    ticker: str,
    period: str = "3mo",
    *,
    days: int | None = None,
    paginate: bool = False,
) -> pd.DataFrame:
    """Return a daily OHLCV DataFrame for a KR ticker via the KIS public API.

    Endpoint: ``/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice``
    tr_id: ``FHKST03010100``

    Columns: ``Open, High, Low, Close, Volume``. Index: tz-naive
    ``DatetimeIndex`` named ``Date``. Returns an empty DataFrame on any
    failure — never raises.

    Parameters
    ----------
    ticker:
        KRX ticker — bare 6-digit code or ``NNNNNN.KS`` / ``.KQ`` suffix.
    period:
        Convenience shorthand (``"1mo"``, ``"3mo"``, ``"1y"``, …).  Ignored
        when *days* is supplied explicitly.
    days:
        Exact calendar days to fetch.  Overrides *period*.
    paginate:
        When True, issues up to 15 sequential calls (≈1 500 trading bars)
        to cover long windows (e.g. ``1y``/``2y``).  When False (default),
        a single call is made — suitable for windows ≤ ~100 trading days.

    Notes
    -----
    2026-05-18 Wave H-1 P2 (fetcher.py divergence fix):
        ``fetcher.py:_get_history_kis`` previously re-implemented the auth +
        pagination logic inline, producing up to 1 500 bars while this module
        produced only ~100 bars for the same 1y window.  The pagination
        logic has been consolidated here; fetcher.py is now a thin wrapper
        calling ``get_history(ticker, period, paginate=True)``.
    """
    code = _to_code(ticker)
    if not code:
        return pd.DataFrame()
    if not is_available():
        return pd.DataFrame()

    _days = days if days is not None else _PERIOD_DAYS.get(period, 90)
    today = datetime.now()

    headers = _auth_headers("FHKST03010100")
    if headers is None:
        return pd.DataFrame()

    start_date = (today - timedelta(days=_days)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    if not paginate:
        # Single call — widens window ~1.4× to absorb weekends/holidays.
        from_dt = today - timedelta(days=int(_days * 1.4) + 5)
        records = _single_call(code, from_dt.strftime("%Y%m%d"), end_date, headers)
        rows, _ = _parse_rows(records)
        return _rows_to_df(rows, _days, today)

    # ── Paginated mode (up to 15 pages ≈ 1 500 bars) ────────────────
    all_rows: list[dict] = []
    cursor_end = end_date
    pages_fetched = 0

    for _page in range(15):
        records = _single_call(code, start_date, cursor_end, headers)
        if not records:
            break

        page_rows, earliest = _parse_rows(records)
        if not page_rows:
            break

        all_rows.extend(page_rows)
        pages_fetched = _page + 1

        # Stopping conditions
        if len(records) < 100:
            break  # KIS returned a partial page — no more data
        if earliest and earliest <= start_date:
            break  # Reached or passed the requested start
        if earliest:
            # Move cursor to the day before the earliest record seen
            prev = datetime.strptime(earliest, "%Y%m%d") - timedelta(days=1)
            cursor_end = prev.strftime("%Y%m%d")
        else:
            break

        time.sleep(_RATE_LIMIT_SLEEP)

    df = _rows_to_df(all_rows, _days, today)
    logger.debug("KIS paginated history: %s → %d bars (%d pages)", ticker, len(df), pages_fetched)
    return df


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


def get_52w_range(ticker: str) -> tuple[float, float] | None:
    """Return ``(52w high, 52w low)`` for a KRX ticker, or ``None``.

    Official-source counterpart of FMP's yearHigh/yearLow: FMP's KRX
    coverage is unreliable (services/alert.py FIX 2 2026-05-22 skipped KR
    entirely because of it), while KIS is the exchange-licensed feed. Uses
    the same rate-limited ``inquire-price`` call as :func:`get_name` —
    ``w52_hgpr`` / ``w52_lwpr`` ride along on the quote payload, so the
    cost is one quote request (~120ms behind the module rate limit).

    Never raises; any missing/garbled field returns ``None`` so the alert
    layer's "rather miss than fabricate" rule holds.
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
        try:
            hi = float(output.get("w52_hgpr") or 0)
            lo = float(output.get("w52_lwpr") or 0)
        except (TypeError, ValueError):
            return None
        # hi <= lo (not just hi < lo): a flat 52w window (hi == lo) is a feed
        # artifact the alert layer also rejects (services/alert.py uses <=), so
        # reject it here too rather than hand back a degenerate (X, X) range.
        if hi <= 0 or lo <= 0 or hi <= lo:
            return None
        return hi, lo
    except Exception as exc:
        logger.info("KIS get_52w_range(%s) failed: %s", ticker, exc)
    return None
