"""DART Open API — KR insider (large-holding) transaction fetcher.

Thin wrapper around https://opendart.fss.or.kr.

All functions return an empty list on failure (network error, missing
API key, parse error) — this module is intentionally **best-effort**;
the callers must continue to function when DART is unavailable.

Environment
-----------
- ``DART_API_KEY`` — optional. When absent, every call short-circuits
  to ``[]`` and logs at debug level. Do **not** raise.

Endpoints used
--------------
- ``list.json``             — company filing list (used to derive corp_code
                              from a ticker if not already cached).
- ``majorstock.json``       — 대량보유상황보고 (>5% 지분 변동)
- ``elestock.json``         — 임원·주요주주 소유주식변동 (executive /
                              10% holder share changes)

Response schemas are per DART's public docs (2022+ v1).

"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

try:
    import requests as _requests
except ImportError:  # pragma: no cover
    _requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_DART_BASE = "https://opendart.fss.or.kr/api"
_TIMEOUT = 8.0
_MIN_INTERVAL = 0.12  # DART 20k/day free, self-throttle to ~8 req/s
_rate_lock = threading.Lock()
_last_ts: float = 0.0

# Cache (TTL 24h — insider filings are T+1 day level fresh).
_CACHE_TTL_SECONDS = 24 * 3600
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _has_key() -> bool:
    return bool(os.environ.get("DART_API_KEY"))


def _throttle() -> None:
    global _last_ts
    with _rate_lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_ts)
        if wait > 0:
            time.sleep(wait)
        _last_ts = time.monotonic()


def _cache_get(key: str):
    with _cache_lock:
        hit = _cache.get(key)
        if not hit:
            return None
        ts, val = hit
        if time.time() - ts > _CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        return val


def _cache_set(key: str, val: Any) -> None:
    with _cache_lock:
        _cache[key] = (time.time(), val)


def _get(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    if _requests is None or not _has_key():
        return None
    api_key = os.environ.get("DART_API_KEY") or ""
    q = dict(params, crtfc_key=api_key)
    try:
        _throttle()
        r = _requests.get(f"{_DART_BASE}/{path}", params=q, timeout=_TIMEOUT)
        if r.status_code != 200:
            logger.debug("DART %s HTTP %s", path, r.status_code)
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None
        # DART status: "000" success, "013" no-data (treat as empty).
        status = str(data.get("status", ""))
        if status not in ("000", "013"):
            logger.debug("DART %s status=%s message=%s",
                         path, status, data.get("message"))
            return None
        return data
    except Exception as exc:
        logger.debug("DART %s failed: %s", path, exc)
        return None


# ── public ──────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """True iff DART_API_KEY is set. Callers should skip gracefully when False."""
    return _has_key()


def get_insider_trades(
    corp_code: str,
    *,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Return executive/insider share-change disclosures for ``corp_code``.

    Params
    ------
    corp_code : str   — 8-digit DART corp code (zero-padded).
    days      : int   — look-back window in days (the API filters by
                        begin/end date, not transaction date, but the
                        two are ~same-day for insider filings).

    Returns
    -------
    list of {
        "ticker":           str (stock_code),
        "company":          str (corp_name),
        "insider":          str (reporter),
        "relationship":     str ("임원" / "주요주주" / ...),
        "transaction_date": str (YYYY-MM-DD),
        "transaction_code": str ("P" buy / "S" sale),
        "shares":           int (change in shares, absolute),
        "direction":        str ("buy" / "sell"),
        "accession":        str (rcept_no — DART filing id),
        "disclosure_url":   str,
    }
    """
    if not is_configured():
        return []
    code = (corp_code or "").strip()
    if not code or not code.isdigit():
        return []
    cache_key = f"dart_elestock:{code}:{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    end = datetime.now(timezone.utc).date()
    begin = end - timedelta(days=max(1, days))
    params = {
        "corp_code": code.zfill(8),
        "bgn_de":    begin.strftime("%Y%m%d"),
        "end_de":    end.strftime("%Y%m%d"),
    }
    data = _get("elestock.json", params)
    trades: list[dict[str, Any]] = []
    if data is None:
        _cache_set(cache_key, trades)
        return trades

    for row in data.get("list") or []:
        try:
            stock_code = str(row.get("stock_code") or "").strip()
            ticker = f"{stock_code}.KS" if stock_code else ""
            isu = str(row.get("isu_exctn") or "").strip()  # 거래유형
            # Normalise into buy/sell. DART 거래유형 examples:
            # "장내매수", "장내매도", "장외매수", "장외매도", "증여", "상속" 등
            direction = "buy" if "매수" in isu else ("sell" if "매도" in isu else "other")
            tx_code = "P" if direction == "buy" else ("S" if direction == "sell" else "")
            try:
                shares = int(str(row.get("isu_stock") or "0").replace(",", ""))
            except ValueError:
                shares = 0
            tx_date_raw = str(row.get("trd_dd") or "").strip()
            if len(tx_date_raw) == 8 and tx_date_raw.isdigit():
                tx_date = f"{tx_date_raw[:4]}-{tx_date_raw[4:6]}-{tx_date_raw[6:]}"
            else:
                tx_date = tx_date_raw
            rcept = str(row.get("rcept_no") or "").strip()
            trades.append({
                "ticker":           ticker,
                "company":          str(row.get("corp_name") or ""),
                "insider":          str(row.get("repror") or ""),
                "relationship":     str(row.get("isu_rel") or ""),
                "transaction_date": tx_date,
                "transaction_code": tx_code,
                "shares":           abs(shares),
                "direction":        direction,
                "price":            None,  # not provided by elestock
                "value_krw":        None,
                "accession":        rcept,
                "disclosure_url":   (f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}"
                                     if rcept else ""),
                "source":           "DART",
            })
        except Exception as exc:
            logger.debug("DART elestock row parse failed: %s", exc)
            continue

    trades.sort(key=lambda r: r.get("transaction_date") or "", reverse=True)
    _cache_set(cache_key, trades)
    return trades


def ticker_to_corp_code(ticker: str) -> str | None:
    """Map a KR ticker → DART 8-digit corp_code.

    Delegates to :mod:`services.data.dart_corp_code`, which downloads and
    caches DART's ``CORPCODE.xml`` master file. Returns ``None`` when the
    API key is missing, the ticker is non-KR, or the symbol is not listed.
    """
    if not is_configured():
        return None
    t = (ticker or "").upper().strip()
    if not (t.endswith(".KS") or t.endswith(".KQ")):
        return None
    try:
        from services.data import dart_corp_code
    except Exception as exc:  # pragma: no cover
        logger.debug("dart_corp_code import failed: %s", exc)
        return None
    try:
        return dart_corp_code.corp_code_for(t)
    except Exception as exc:
        logger.debug("dart_corp_code.corp_code_for(%s) raised: %s", t, exc)
        return None
