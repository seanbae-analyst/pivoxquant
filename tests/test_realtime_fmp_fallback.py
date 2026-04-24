"""
PivoxQuant — Tests for realtime_service FMP stale-cache fallback (2026-04-24)

Regression coverage for the FMP 250-call budget / 402 cooldown / connection
failure bug where cache-miss tickers returned 404 for ALL symbols.

Scenarios covered:
  1. FMP returns None + stale cache exists  → stale-flagged payload
  2. FMP returns None + no stale cache       → None (route → 503 or 404)
  3. FMP budget exhausted                    → fmp_is_throttled() == True
  4. Route layer: 503 when throttled, 404 when genuinely missing
  5. FMP returns fresh quote                 → normal (no stale flag)
"""
from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pytest

import fmp_service
from realtime_service import RealtimeService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clear_fmp_cache():
    with fmp_service._cache_lock:
        fmp_service._cache.clear()
        fmp_service._endpoint_402_counts.clear()
        fmp_service._endpoint_402_cooldown.clear()
    # Reset global budget counter to a clean state
    fmp_service._daily_calls = 0
    fmp_service._daily_calls_reset = time.time()


def _seed_stale_cache(ticker: str, price: float, age_seconds: float = 3600.0):
    """Insert a stale quote entry whose timestamp is older than any TTL."""
    cache_key = f"quote:{ticker}"
    with fmp_service._cache_lock:
        fmp_service._cache[cache_key] = {
            "data": {"symbol": ticker, "price": price},
            "ts": time.time() - age_seconds,
        }


# ── 1. realtime_service._get_fmp_price — unit tests ─────────────────────────

class TestGetFmpPriceFallback:

    def setup_method(self):
        _clear_fmp_cache()

    def test_fresh_fmp_quote_returns_live_payload(self):
        """Happy path: FMP returns a fresh quote → no stale flag."""
        rt = RealtimeService()
        fresh = {"symbol": "AAPL", "price": 195.2}
        with patch.object(fmp_service, "get_quote", return_value=fresh):
            out = rt._get_fmp_price("AAPL")
        assert out is not None
        assert out["source"] == "fmp"
        assert out["price"] == pytest.approx(195.2)
        assert "stale" not in out

    def test_fmp_none_with_stale_cache_serves_stale(self):
        """Budget-exhausted / 402 cooldown: get_quote=None + stale cache → serve stale."""
        rt = RealtimeService()
        _seed_stale_cache("AAPL", 180.5, age_seconds=7200)
        # Force get_quote to return None — simulates fmp_service skipping
        # its own stale fallback (e.g. a refactor regression).
        with patch.object(fmp_service, "get_quote", return_value=None):
            out = rt._get_fmp_price("AAPL")
        assert out is not None, "stale cache must be returned, not None"
        assert out["stale"] is True
        assert out["source"] == "fmp_stale"
        assert out["price"] == pytest.approx(180.5)
        assert "stale_at" in out

    def test_fmp_none_with_no_cache_returns_none(self):
        """FMP fails AND no cache → None (caller decides 404 vs 503)."""
        rt = RealtimeService()
        with patch.object(fmp_service, "get_quote", return_value=None):
            out = rt._get_fmp_price("ZZZZ")
        assert out is None

    def test_fmp_zero_price_with_stale_cache_serves_stale(self):
        """FMP returned {price: 0} (garbage) + stale cache → serve stale."""
        rt = RealtimeService()
        _seed_stale_cache("AAPL", 180.5)
        with patch.object(fmp_service, "get_quote", return_value={"symbol": "AAPL", "price": 0}):
            out = rt._get_fmp_price("AAPL")
        assert out is not None
        assert out["stale"] is True
        assert out["price"] == pytest.approx(180.5)

    def test_fmp_exception_with_stale_cache_serves_stale(self):
        """fmp.get_quote raises + stale cache exists → serve stale, don't propagate."""
        rt = RealtimeService()
        _seed_stale_cache("AAPL", 180.5)
        with patch.object(fmp_service, "get_quote", side_effect=RuntimeError("boom")):
            out = rt._get_fmp_price("AAPL")
        assert out is not None
        assert out["stale"] is True

    def test_kr_ticker_formatted_as_krw(self):
        """KR ticker stale fallback uses ₩ formatting + KRW currency."""
        rt = RealtimeService()
        _seed_stale_cache("005930.KS", 72000.0)
        with patch.object(fmp_service, "get_quote", return_value=None):
            out = rt._get_fmp_price("005930.KS")
        assert out is not None
        assert out["currency"] == "KRW"
        assert out["price_display"].startswith("₩")


# ── 2. fmp_is_throttled — provider health signal ────────────────────────────

class TestFmpIsThrottled:

    def setup_method(self):
        _clear_fmp_cache()

    def test_healthy_when_budget_ok(self):
        rt = RealtimeService()
        fmp_service._daily_calls = 10
        assert rt.fmp_is_throttled() is False

    def test_throttled_when_budget_exhausted(self):
        rt = RealtimeService()
        fmp_service._daily_calls = fmp_service._BUDGET_HARD_STOP + 1
        try:
            assert rt.fmp_is_throttled() is True
        finally:
            fmp_service._daily_calls = 0

    def test_throttled_when_quote_blocked_and_budget_stale(self):
        rt = RealtimeService()
        fmp_service._daily_calls = fmp_service._BUDGET_STALE_THRESHOLD + 1
        with fmp_service._cache_lock:
            fmp_service._endpoint_402_cooldown["/quote"] = time.time() + 600
        try:
            assert rt.fmp_is_throttled() is True
        finally:
            fmp_service._daily_calls = 0
            with fmp_service._cache_lock:
                fmp_service._endpoint_402_cooldown.clear()


# ── 3. Route layer: /api/realtime/price/<ticker> ────────────────────────────

class TestRealtimePriceRoute:
    """The 404→503 UX fix: data_provider_throttled vs ticker_not_found."""

    def setup_method(self):
        _clear_fmp_cache()

    def test_200_when_price_available(self, client, auth_user):
        quote = {
            "ticker": "AAPL", "price": 195.2,
            "price_display": "$195.20", "currency": "USD",
            "source": "fmp", "timestamp": "2026-04-24T00:00:00",
        }
        mock_rt = MagicMock()
        mock_rt.get_price.return_value = quote
        mock_rt.fmp_is_throttled.return_value = False
        with patch("routes.realtime.realtime", mock_rt):
            r = client.get("/api/realtime/price/AAPL")
        assert r.status_code == 200
        body = r.get_json()
        assert body["price"] == pytest.approx(195.2)

    def test_404_when_ticker_missing_and_provider_healthy(self, client, auth_user):
        mock_rt = MagicMock()
        mock_rt.get_price.return_value = None
        mock_rt.fmp_is_throttled.return_value = False
        with patch("routes.realtime.realtime", mock_rt):
            r = client.get("/api/realtime/price/ZZZZ")
        assert r.status_code == 404
        body = r.get_json()
        assert body["error"] == "ticker_not_found"

    def test_503_when_provider_throttled(self, client, auth_user):
        """Budget-exhausted / all-providers-down → 503 not 404."""
        mock_rt = MagicMock()
        mock_rt.get_price.return_value = None
        mock_rt.fmp_is_throttled.return_value = True
        with patch("routes.realtime.realtime", mock_rt):
            r = client.get("/api/realtime/price/AAPL")
        assert r.status_code == 503
        body = r.get_json()
        assert body["error"] == "data_provider_throttled"
        assert body["ticker"] == "AAPL"
