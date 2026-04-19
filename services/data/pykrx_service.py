"""
PivoxQuant — pyKRX Alternative Data Service
===========================================
Korean market alternative data for quant models (Foreign Flow Predictor,
Short Squeeze Radar). Wraps the open-source `pykrx` library which scrapes
the Korea Exchange (KRX) public data portal.

Design:
- In-memory TTL cache (24h default). No DB writes.
- Thread-safe (single module-level lock).
- Never raises on pyKRX failure — returns empty list/dict so callers stay
  resilient. Errors are logged at WARNING.
- Rate-limited at 0.3s between external calls to avoid hammering KRX.
- Ticker normalization: accepts "005930", "005930.KS", "005930.KQ",
  lowercase suffixes, etc. Internally always uses the bare 6-digit code.

pyKRX is an optional dependency — if the import fails (not installed),
every public method returns an empty result and logs a single warning
rather than crashing the Flask app.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── Optional pyKRX import ────────────────────────────────────────────────────
try:  # pragma: no cover — import path depends on env
    from pykrx import stock as _pykrx_stock  # type: ignore
    _PYKRX_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    _pykrx_stock = None
    _PYKRX_AVAILABLE = False
    logger.warning("pyKRX not available — KR alt-data endpoints will return empty: %s", _e)


# ── Constants ───────────────────────────────────────────────────────────────
_CACHE_TTL_SECONDS = 86_400        # 24h
_RATE_LIMIT_SLEEP_SECONDS = 0.3    # between external pyKRX calls
_DATE_FMT = "%Y%m%d"


def _normalize_ticker(ticker: str) -> str | None:
    """Normalize '005930.KS' / '005930.kq' / '005930' → '005930'.

    Returns None if ticker is obviously not a 6-digit KR code.
    """
    if not ticker or not isinstance(ticker, str):
        return None
    t = ticker.strip().upper()
    # Strip common suffixes.
    for suf in (".KS", ".KQ", ".KRX"):
        if t.endswith(suf):
            t = t[: -len(suf)]
            break
    if t.isdigit() and len(t) == 6:
        return t
    return None


class PyKRXService:
    """In-process wrapper around pykrx with a 24h memory cache.

    Public methods never raise — they return empty lists/dicts on failure
    so Flask routes stay 200-OK-with-empty-data instead of 500-ing.
    """

    def __init__(self, cache_ttl: int = _CACHE_TTL_SECONDS,
                 rate_limit_sleep: float = _RATE_LIMIT_SLEEP_SECONDS):
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_lock = threading.Lock()
        self._last_call_ts: float = 0.0
        self._call_lock = threading.Lock()
        self.cache_ttl = cache_ttl
        self.rate_limit_sleep = rate_limit_sleep

    # ── Cache primitives ────────────────────────────────────────────────

    def _cache_get(self, key: str) -> Any | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time.time() - entry["ts"] >= self.cache_ttl:
                # Expired — evict lazily.
                self._cache.pop(key, None)
                return None
            return entry["data"]

    def _cache_set(self, key: str, data: Any) -> None:
        with self._cache_lock:
            self._cache[key] = {"data": data, "ts": time.time(), "cached_at": datetime.utcnow().isoformat()}

    def _cache_cached_at(self, key: str) -> str | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            return entry.get("cached_at") if entry else None

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    # ── Rate-limited external call ──────────────────────────────────────

    def _rate_limit(self) -> None:
        """Sleep if we called pyKRX too recently. Thread-safe."""
        with self._call_lock:
            elapsed = time.time() - self._last_call_ts
            if elapsed < self.rate_limit_sleep:
                time.sleep(self.rate_limit_sleep - elapsed)
            self._last_call_ts = time.time()

    # ── Date helpers ────────────────────────────────────────────────────

    @staticmethod
    def _range_dates(days: int) -> tuple[str, str]:
        """Return (fromdate, todate) as YYYYMMDD strings covering `days` back.

        We widen the calendar window by ~1.5x to absorb weekends/holidays
        since pyKRX returns trading days only.
        """
        end = datetime.now()
        # Widen window: ~1.5x calendar days to capture `days` trading days.
        start = end - timedelta(days=int(days * 1.5) + 5)
        return start.strftime(_DATE_FMT), end.strftime(_DATE_FMT)

    # ── Public API ──────────────────────────────────────────────────────

    def get_foreign_flow(self, ticker: str, days: int = 30) -> list[dict]:
        """Foreign-investor net buying (억원) per trading day, most-recent first.

        Returns [] on any error or when pyKRX is unavailable.
        """
        code = _normalize_ticker(ticker)
        if not code or not _PYKRX_AVAILABLE:
            if not code:
                logger.warning("pykrx.get_foreign_flow: invalid ticker %r", ticker)
            return []
        key = f"foreign_flow:{code}:{days}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        fromdate, todate = self._range_dates(days)
        try:
            self._rate_limit()
            df = _pykrx_stock.get_market_trading_value_by_date(  # type: ignore[attr-defined]
                fromdate, todate, code
            )
            if df is None or df.empty:
                self._cache_set(key, [])
                return []
            rows: list[dict] = []
            # Column names returned by pyKRX are Korean: '외국인합계', '기관합계', etc.
            # Values are in KRW — convert to 억원 (divide by 1e8) for readability.
            for idx, row in df.iterrows():
                date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                foreign = float(row.get("외국인합계", 0) or 0) / 1e8
                institutional = float(row.get("기관합계", 0) or 0) / 1e8
                individual = float(row.get("개인", 0) or 0) / 1e8
                rows.append({
                    "date": date_str,
                    "foreign_net_buy_eok": round(foreign, 2),
                    "institutional_net_buy_eok": round(institutional, 2),
                    "individual_net_buy_eok": round(individual, 2),
                })
            rows.sort(key=lambda r: r["date"], reverse=True)
            rows = rows[:days]
            self._cache_set(key, rows)
            return rows
        except Exception as e:
            logger.warning("pykrx.get_foreign_flow failed for %s: %s", code, e)
            return []

    def get_institutional_flow(self, ticker: str, days: int = 30) -> list[dict]:
        """Institutional net-buying (억원) per trading day.

        Reuses the same pyKRX dataset as foreign-flow — we just project a
        narrower view. This keeps the KRX server hit count minimal.
        """
        rows = self.get_foreign_flow(ticker, days)
        return [
            {"date": r["date"], "institutional_net_buy_eok": r["institutional_net_buy_eok"]}
            for r in rows
        ]

    def get_short_interest(self, ticker: str, days: int = 30) -> list[dict]:
        """Short-sale trading volume + short-balance time series.

        Returns daily records with:
          - short_volume (shares sold short that day)
          - short_value_eok (억원)
          - short_balance_shares (outstanding short position, shares)
          - short_balance_eok (억원)
        """
        code = _normalize_ticker(ticker)
        if not code or not _PYKRX_AVAILABLE:
            if not code:
                logger.warning("pykrx.get_short_interest: invalid ticker %r", ticker)
            return []
        key = f"short_interest:{code}:{days}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        fromdate, todate = self._range_dates(days)
        rows: list[dict] = []
        # Short-sale volume (daily flow)
        vol_map: dict[str, dict] = {}
        try:
            self._rate_limit()
            df_vol = _pykrx_stock.get_shorting_volume_by_date(  # type: ignore[attr-defined]
                fromdate, todate, code
            )
            if df_vol is not None and not df_vol.empty:
                for idx, row in df_vol.iterrows():
                    date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                    vol_map[date_str] = {
                        "short_volume": int(row.get("공매도", 0) or 0),
                        "short_value_eok": round(float(row.get("거래대금", 0) or 0) / 1e8, 2),
                    }
        except Exception as e:
            logger.warning("pykrx.get_shorting_volume failed for %s: %s", code, e)

        # Short balance (outstanding short position)
        bal_map: dict[str, dict] = {}
        try:
            self._rate_limit()
            df_bal = _pykrx_stock.get_shorting_balance_by_date(  # type: ignore[attr-defined]
                fromdate, todate, code
            )
            if df_bal is not None and not df_bal.empty:
                for idx, row in df_bal.iterrows():
                    date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                    bal_map[date_str] = {
                        "short_balance_shares": int(row.get("공매도잔고", 0) or 0),
                        "short_balance_eok": round(float(row.get("공매도금액", 0) or 0) / 1e8, 2),
                    }
        except Exception as e:
            logger.warning("pykrx.get_shorting_balance failed for %s: %s", code, e)

        # Merge on date.
        all_dates = sorted(set(vol_map) | set(bal_map), reverse=True)
        for d in all_dates[:days]:
            merged = {"date": d}
            merged.update(vol_map.get(d, {"short_volume": 0, "short_value_eok": 0.0}))
            merged.update(bal_map.get(d, {"short_balance_shares": 0, "short_balance_eok": 0.0}))
            rows.append(merged)

        self._cache_set(key, rows)
        return rows

    def get_short_balance_ratio(self, ticker: str) -> dict:
        """Latest short-balance as % of market cap.

        Returns {} on failure. Otherwise:
          {date, short_balance_shares, short_balance_eok, market_cap_eok, ratio_pct}
        """
        code = _normalize_ticker(ticker)
        if not code or not _PYKRX_AVAILABLE:
            if not code:
                logger.warning("pykrx.get_short_balance_ratio: invalid ticker %r", ticker)
            return {}
        key = f"short_balance_ratio:{code}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        fromdate, todate = self._range_dates(7)
        try:
            self._rate_limit()
            df_bal = _pykrx_stock.get_shorting_balance_by_date(  # type: ignore[attr-defined]
                fromdate, todate, code
            )
            if df_bal is None or df_bal.empty:
                self._cache_set(key, {})
                return {}
            idx = df_bal.index[-1]
            row = df_bal.iloc[-1]
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            short_shares = int(row.get("공매도잔고", 0) or 0)
            short_eok = round(float(row.get("공매도금액", 0) or 0) / 1e8, 2)

            # Market cap for the same day.
            self._rate_limit()
            df_cap = _pykrx_stock.get_market_cap_by_date(  # type: ignore[attr-defined]
                fromdate, todate, code
            )
            market_cap_eok = 0.0
            if df_cap is not None and not df_cap.empty:
                market_cap_eok = round(float(df_cap.iloc[-1].get("시가총액", 0) or 0) / 1e8, 2)

            ratio = round((short_eok / market_cap_eok) * 100, 3) if market_cap_eok else 0.0
            result = {
                "date": date_str,
                "short_balance_shares": short_shares,
                "short_balance_eok": short_eok,
                "market_cap_eok": market_cap_eok,
                "ratio_pct": ratio,
            }
            self._cache_set(key, result)
            return result
        except Exception as e:
            logger.warning("pykrx.get_short_balance_ratio failed for %s: %s", code, e)
            return {}

    def get_market_flow_summary(self, market: str = "KOSPI", date: str | None = None) -> dict:
        """Whole-market investor-type net-buying summary (억원).

        `market` in {"KOSPI", "KOSDAQ"}. `date` as YYYYMMDD or None for most
        recent trading day. Returns {} on failure.
        """
        if not _PYKRX_AVAILABLE:
            return {}
        market = (market or "KOSPI").upper()
        if market not in ("KOSPI", "KOSDAQ"):
            logger.warning("pykrx.get_market_flow_summary: invalid market %r", market)
            return {}

        if date:
            try:
                datetime.strptime(date, _DATE_FMT)
            except ValueError:
                logger.warning("pykrx.get_market_flow_summary: bad date %r", date)
                return {}
            todate = date
            fromdate = (datetime.strptime(date, _DATE_FMT) - timedelta(days=7)).strftime(_DATE_FMT)
        else:
            fromdate, todate = self._range_dates(7)

        key = f"market_flow:{market}:{todate}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        try:
            self._rate_limit()
            df = _pykrx_stock.get_market_trading_value_by_investor(  # type: ignore[attr-defined]
                fromdate, todate, market
            )
            if df is None or df.empty:
                self._cache_set(key, {})
                return {}
            # Pick the net-buy column — pyKRX calls it '순매수' (buy minus sell).
            col = "순매수" if "순매수" in df.columns else df.columns[-1]
            summary = {}
            for investor, value in df[col].items():
                summary[str(investor)] = round(float(value or 0) / 1e8, 2)
            result = {
                "market": market,
                "date": todate,
                "net_buy_eok": summary,
            }
            self._cache_set(key, result)
            return result
        except Exception as e:
            logger.warning("pykrx.get_market_flow_summary failed for %s: %s", market, e)
            return {}

    # ── Introspection for route responses ────────────────────────────────

    def cached_at(self, ticker_or_market: str, kind: str, days: int | None = None,
                   date: str | None = None) -> str | None:
        """Return ISO cached_at timestamp for a given (kind, ticker) pair if any."""
        if kind == "foreign_flow":
            code = _normalize_ticker(ticker_or_market)
            if not code:
                return None
            return self._cache_cached_at(f"foreign_flow:{code}:{days or 30}")
        if kind == "short_interest":
            code = _normalize_ticker(ticker_or_market)
            if not code:
                return None
            return self._cache_cached_at(f"short_interest:{code}:{days or 30}")
        if kind == "market_flow":
            return self._cache_cached_at(f"market_flow:{ticker_or_market.upper()}:{date}")
        return None


# ── Module-level singleton ─────────────────────────────────────────────────
# Routes import this directly. Tests can patch it or instantiate their own.
pykrx_service = PyKRXService()
