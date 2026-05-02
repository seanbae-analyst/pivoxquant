"""
FRED (Federal Reserve Economic Data) Service
=============================================
Macro economic data layer for PivoxQuant's Macro Scenario Stress Test model.

Data source: https://fred.stlouisfed.org/
API docs:    https://fred.stlouisfed.org/docs/api/fred/
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html

Design
------
- Direct HTTP calls via `requests` (no extra dep vs. fredapi; FRED's REST API
  is simple, well-versioned, and we already rely on `requests` in other
  services — keeps the dependency surface tight).
- Memory TTL cache (6h) — FRED updates most series daily.
- Graceful degradation when FRED_API_KEY is unset: `self.available = False`,
  empty dicts returned, warning logged. No exceptions bubble to callers.

Thread-safety
-------------
Cache access is guarded by a single RLock. Flask dev server / gunicorn sync
workers access this sequentially per-request; we still lock because the
scheduler thread can also call `get_macro_snapshot()`.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


# ── Series catalog ────────────────────────────────────────────────────────────
# Each entry: FRED series_id → (human label, units, notes)
FRED_SERIES: dict[str, dict[str, str]] = {
    "FEDFUNDS":   {"label": "Federal Funds Rate",        "units": "percent",   "freq": "monthly"},
    "DGS10":      {"label": "10-Year Treasury Yield",    "units": "percent",   "freq": "daily"},
    "T10Y2Y":     {"label": "10Y-2Y Spread",             "units": "percent",   "freq": "daily"},
    "CPIAUCSL":   {"label": "CPI (All Urban Consumers)", "units": "index",     "freq": "monthly"},
    "UNRATE":     {"label": "Unemployment Rate",         "units": "percent",   "freq": "monthly"},
    "DCOILWTICO": {"label": "WTI Crude Oil Price",       "units": "usd/bbl",   "freq": "daily"},
    "DEXKOUS":    {"label": "USD/KRW Exchange Rate",     "units": "krw/usd",   "freq": "daily"},
    "DTWEXBGS":   {"label": "Broad Dollar Index",        "units": "index",     "freq": "daily"},
    "VIXCLS":     {"label": "CBOE Volatility Index",     "units": "index",     "freq": "daily"},
    "SP500":      {"label": "S&P 500 Index",             "units": "index",     "freq": "daily"},
}

# Regime detection thresholds
_T10Y2Y_INVERSION_THRESHOLD = 0.0   # negative = yield curve inverted
_VIX_STRESS_THRESHOLD = 25.0        # VIX above this = elevated stress
_UNRATE_RECESSION_THRESHOLD = 5.5   # rough threshold; combined with trend
_CACHE_TTL_SECONDS = 6 * 3600       # 6 hours
_DEFAULT_LIMIT = 365
_API_BASE = "https://api.stlouisfed.org/fred/series/observations"
_HTTP_TIMEOUT = 10  # seconds


class FREDService:
    """FRED macro data client with in-memory TTL cache and safe degradation."""

    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = _CACHE_TTL_SECONDS):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "").strip() or None
        self.available = bool(self.api_key)
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = cache_ttl
        self._lock = threading.RLock()

        if not self.available:
            logger.warning(
                "FRED_API_KEY not set — FRED service disabled. "
                "Register free at https://fred.stlouisfed.org/docs/api/api_key.html"
            )

    # ── cache helpers ────────────────────────────────────────────────────────
    def _cache_get(self, key: str) -> Any:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            ts, value = entry
            if time.time() - ts > self._cache_ttl:
                # Stale — drop it.
                self._cache.pop(key, None)
                return None
            return value

    def _cache_put(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = (time.time(), value)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    # ── core fetch ───────────────────────────────────────────────────────────
    def _fetch_observations(
        self,
        series_id: str,
        start: Optional[str] = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """Raw FRED API call. Returns sorted-ascending list of {date, value}.

        Non-numeric sentinel "." is skipped. Network/HTTP errors return [].
        """
        if not self.available:
            return []

        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": max(1, min(int(limit or _DEFAULT_LIMIT), 10_000)),
        }
        if start:
            params["observation_start"] = start

        try:
            resp = requests.get(_API_BASE, params=params, timeout=_HTTP_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as e:
            logger.warning("FRED fetch failed for %s: %s", series_id, e)
            return []
        except ValueError as e:  # JSON decode
            logger.warning("FRED JSON decode failed for %s: %s", series_id, e)
            return []

        observations = payload.get("observations") or []
        cleaned: list[dict[str, Any]] = []
        for obs in observations:
            raw_val = obs.get("value")
            if raw_val in (None, ".", ""):
                continue
            try:
                val = float(raw_val)
            except (TypeError, ValueError):
                logger.debug("silent-fallback: _fetch_observations", exc_info=True)
                continue
            cleaned.append({"date": obs.get("date"), "value": val})

        # Return ascending by date for downstream charting / regime logic.
        cleaned.sort(key=lambda d: d["date"] or "")
        return cleaned

    # ── public API ───────────────────────────────────────────────────────────
    def get_series(
        self,
        series_id: str,
        start: Optional[str] = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Full time series for a FRED series_id.

        Returns {series_id, label, units, observations: [{date, value}, ...]}.
        Empty dict on error / missing key.
        """
        if not self.available:
            return {}

        sid = (series_id or "").strip().upper()
        if not sid:
            return {}

        cache_key = f"series:{sid}:{start or ''}:{limit}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        meta = FRED_SERIES.get(sid, {"label": sid, "units": "", "freq": ""})
        obs = self._fetch_observations(sid, start=start, limit=limit)
        if not obs:
            # Don't cache empty/error results — lets transient failures recover
            # without waiting for the 6h TTL.
            return {}

        result = {
            "series_id": sid,
            "label": meta.get("label", sid),
            "units": meta.get("units", ""),
            "freq": meta.get("freq", ""),
            "observations": obs,
            "count": len(obs),
        }
        self._cache_put(cache_key, result)
        return result

    def get_latest(self, series_id: str) -> dict[str, Any]:
        """Latest value + absolute & pct change vs prior observation.

        Returns {} if unavailable / no data.
        """
        if not self.available:
            return {}

        sid = (series_id or "").strip().upper()
        if not sid:
            return {}

        cache_key = f"latest:{sid}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Pull a small tail — 5 observations is plenty for "latest + prior".
        # Use series call to benefit from cache hits across endpoints.
        series = self.get_series(sid, limit=5)
        obs = series.get("observations") or []
        if not obs:
            return {}

        latest = obs[-1]
        prev = obs[-2] if len(obs) >= 2 else None
        change = None
        pct_change = None
        if prev and prev.get("value") not in (None, 0):
            change = latest["value"] - prev["value"]
            try:
                pct_change = (change / prev["value"]) * 100.0
            except ZeroDivisionError:
                pct_change = None

        meta = FRED_SERIES.get(sid, {"label": sid, "units": "", "freq": ""})
        result = {
            "series_id": sid,
            "label": meta.get("label", sid),
            "units": meta.get("units", ""),
            "date": latest.get("date"),
            "value": latest.get("value"),
            "prev_date": prev.get("date") if prev else None,
            "prev_value": prev.get("value") if prev else None,
            "change": change,
            "pct_change": pct_change,
        }
        self._cache_put(cache_key, result)
        return result

    def get_macro_snapshot(self) -> dict[str, Any]:
        """Latest value for each of the ~10 main FRED_SERIES entries.

        Shape: {"available": bool, "indicators": {series_id: {...}}, "as_of": ts}.
        On missing key → {"available": False, "indicators": {}}.
        """
        if not self.available:
            return {"available": False, "indicators": {}, "reason": "FRED_API_KEY not configured"}

        cache_key = "snapshot:all"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        indicators: dict[str, Any] = {}
        for sid in FRED_SERIES.keys():
            latest = self.get_latest(sid)
            if latest:
                indicators[sid] = latest

        result = {
            "available": True,
            "indicators": indicators,
            "count": len(indicators),
            "as_of": int(time.time()),
        }
        self._cache_put(cache_key, result)
        return result

    def detect_regime(self) -> dict[str, Any]:
        """Simple macro regime classifier.

        Signals combined:
          - 10Y-2Y inverted (T10Y2Y < 0)  → recession leading indicator
          - VIX elevated    (VIXCLS > 25) → market stress
          - Unemployment rising above ~5.5 → late-cycle / recession

        Output:
          {
            "regime": "recession" | "stress" | "expansion" | "neutral" | "unknown",
            "signals": {...},
            "flags": [...],
            "available": bool,
          }
        """
        if not self.available:
            return {"available": False, "regime": "unknown", "signals": {}, "flags": []}

        signals: dict[str, Any] = {}
        flags: list[str] = []

        t10y2y = self.get_latest("T10Y2Y")
        vix = self.get_latest("VIXCLS")
        unrate = self.get_latest("UNRATE")
        fedfunds = self.get_latest("FEDFUNDS")

        inverted = False
        if t10y2y and t10y2y.get("value") is not None:
            signals["t10y2y"] = t10y2y["value"]
            inverted = t10y2y["value"] < _T10Y2Y_INVERSION_THRESHOLD
            if inverted:
                flags.append("yield_curve_inverted")

        high_vix = False
        if vix and vix.get("value") is not None:
            signals["vix"] = vix["value"]
            high_vix = vix["value"] > _VIX_STRESS_THRESHOLD
            if high_vix:
                flags.append("vix_elevated")

        unemployment_rising = False
        if unrate and unrate.get("value") is not None:
            signals["unrate"] = unrate["value"]
            if unrate.get("change") is not None and unrate["change"] > 0:
                unemployment_rising = True
                flags.append("unemployment_rising")
            if unrate["value"] > _UNRATE_RECESSION_THRESHOLD:
                flags.append("unemployment_above_threshold")

        if fedfunds and fedfunds.get("value") is not None:
            signals["fedfunds"] = fedfunds["value"]

        # Classification: require at least inverted curve + one other signal
        # before calling recession. VIX alone → stress. Otherwise expansion.
        if inverted and (high_vix or unemployment_rising):
            regime = "recession"
        elif inverted:
            regime = "stress"
        elif high_vix:
            regime = "stress"
        elif signals:
            regime = "expansion"
        else:
            regime = "neutral"

        return {
            "available": True,
            "regime": regime,
            "signals": signals,
            "flags": flags,
            "as_of": int(time.time()),
        }


# Module-level singleton — cheap to import, lazy on first call.
_default_service: Optional[FREDService] = None
_default_lock = threading.Lock()


def get_fred_service() -> FREDService:
    """Lazy singleton accessor for the default service."""
    global _default_service
    if _default_service is None:
        with _default_lock:
            if _default_service is None:
                _default_service = FREDService()
    return _default_service
