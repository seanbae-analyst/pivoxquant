"""PivoxQuant — KR fundamentals adapter (KIS licensed path).

FMP Starter has no KRX coverage, so `.KS` / `.KQ` tickers used to come
back with P/E, EPS, and market_cap all null. KIS's `inquire-price`
endpoint (tr_id ``FHKST01010100``) publishes per-symbol PER / EPS /
PBR / 시가총액 under the same commercial ToS we already accept for
OHLCV data — no additional legal review required.

Why a new module:
  - `kis_service.py` is on the backend engineering freeze list.
  - `kis_market_adapter.py` already reuses the shared KIS token
    manager for OHLCV; we add a parallel, single-purpose module for
    fundamentals so callers can route on `.KS`/`.KQ` without
    touching existing services.

Design rules:
  - Safe by contract: every public function returns ``None`` or an
    empty dict on any failure — never raises.
  - Output dict keys match the FMP ``get_info()`` schema
    (`trailingPE`, `forwardPE`, `trailingEps`, `marketCap`,
    `priceToBook`) so callers don't need a second adapter.
  - Thread-safe via the shared KIS rate limiter in
    ``kis_market_adapter``.

Public API::

    from services.data.kr_fundamentals import get_kr_fundamentals

    info = get_kr_fundamentals("005930.KS")
    # {"trailingPE": 12.34, "forwardPE": 12.34, "trailingEps": 5432,
    #  "priceToBook": 1.23, "marketCap": 5.1e14}
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


# KIS endpoint constants (kept local — do not modify kis_service.py).
_USE_REAL = os.environ.get("KIS_USE_REAL", "").strip() in ("1", "true", "True")
_BASE_URL = (
    "https://openapi.koreainvestment.com:9443"
    if _USE_REAL
    else "https://openapivts.koreainvestment.com:29443"
)
_REQUEST_TIMEOUT = 10  # seconds


def _to_code(ticker: str) -> str | None:
    """Return bare 6-digit KRX code, or None for anything else."""
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


def _safe_float(val: Any) -> float | None:
    """Coerce KIS string numeric output to float; None on empty/invalid."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        if not s or s in {"-", "0", "0.00"}:
            # KIS returns "0" / "0.00" for genuinely missing values on
            # some symbols — treat as null rather than a real zero PER.
            # "0" is never a meaningful PER/EPS/market_cap anyway.
            return None
        f = float(s)
        return f if f != 0.0 else None
    except (TypeError, ValueError):
        return None


def _auth_headers(tr_id: str) -> dict | None:
    """Build KIS request headers. None if app key/token unavailable."""
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


def _rate_limit() -> None:
    """Reuse the shared KIS rate limiter from kis_market_adapter."""
    try:
        from services.data import kis_market_adapter as kma
        kma._rate_limit()
    except Exception:
        # If adapter import fails, rely on KIS server-side throttling.
        pass


def get_kr_fundamentals(ticker: str) -> dict | None:
    """Return an FMP-schema fundamentals dict for a KR ticker.

    Keys (subset of FMP ``get_info()`` schema — callers overlay on
    top of whatever partial data US fallbacks produced):

        trailingPE, forwardPE, trailingEps, priceToBook, marketCap

    Any individual field may be ``None`` if KIS didn't populate it
    for that symbol (e.g. ETFs, SPACs, preferreds). Returns ``None``
    when KIS is unavailable or the ticker isn't a valid KRX code —
    distinct from an empty dict so callers can log the miss.

    Endpoint: ``/uapi/domestic-stock/v1/quotations/inquire-price``
    tr_id:    ``FHKST01010100``

    KIS output fields used:
        per     — trailing P/E (float as string)
        eps     — trailing EPS in KRW (float as string)
        pbr     — price-to-book ratio
        hts_avls — 시가총액 (억원 단위; multiply by 1e8 for KRW)
    """
    code = _to_code(ticker)
    if not code:
        return None

    headers = _auth_headers("FHKST01010100")
    if headers is None:
        logger.info(
            "KR fundamentals: KIS credentials unavailable — cannot serve %s",
            ticker,
        )
        return None

    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    url = f"{_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"

    try:
        _rate_limit()
        resp = requests.get(
            url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT,
        )
        if not resp.ok:
            logger.info(
                "KR fundamentals: KIS HTTP %s for %s",
                resp.status_code, ticker,
            )
            return None
        payload = resp.json()
        if payload.get("rt_cd") != "0":
            logger.info(
                "KR fundamentals: KIS rt_cd=%s for %s: %s",
                payload.get("rt_cd"), ticker, payload.get("msg1"),
            )
            return None
        output = payload.get("output", {}) or {}
    except Exception as exc:
        logger.info("KR fundamentals: KIS request failed for %s: %s", ticker, exc)
        return None

    per = _safe_float(output.get("per"))
    eps = _safe_float(output.get("eps"))
    pbr = _safe_float(output.get("pbr"))

    # hts_avls is reported in 억원 (100M KRW); convert to raw KRW to
    # match FMP's USD marketCap convention (raw currency units).
    mcap_uk = _safe_float(output.get("hts_avls"))
    market_cap = mcap_uk * 1e8 if mcap_uk else None

    result = {
        "trailingPE": per,
        "forwardPE": per,      # KIS only publishes trailing — mirror.
        "trailingEps": eps,
        "priceToBook": pbr,
        "marketCap": market_cap,
    }

    # If every field came back null we'd rather return None so the
    # caller can tell "KIS had nothing" apart from "KIS gave partial".
    if not any(v is not None for v in result.values()):
        return None
    return result
