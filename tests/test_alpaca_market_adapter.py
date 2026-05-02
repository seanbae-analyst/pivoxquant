"""PivoxQuant — alpaca_market_adapter tests.

Replaces the legacy ``test_yfinance_adapter`` suite. Deliberately no
network: the Alpaca SDK client is patched everywhere so tests stay
offline, deterministic, and < 1 second.

Contract covered:
  1. ``get_quote`` returns a dict with numeric ``price`` on success
  2. ``get_quote`` returns ``None`` when Alpaca returns no bars
  3. ``get_quote`` returns ``None`` when the SDK call raises
  4. ``get_history`` returns a DataFrame with OHLCV columns on success
  5. ``get_history`` returns an *empty* DataFrame on failure (never raises)
  6. ``get_earnings_calendar`` always returns [] (Alpaca has no endpoint)
  7. ``is_available`` reflects whether the API keys + SDK are available
  8. ``fmp_service.get_quote`` routes to Alpaca when FMP returns None
  9. KR tickers skip the Alpaca fallback (KIS handles those)
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.data import fmp as fmp_service
from services.data import alpaca_market_adapter as ama


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fake_bar(ts, *, o=180.0, h=182.0, low=179.0, c=181.5, v=50_000_000):
    """Mimic the shape of an alpaca-py Bar object (attribute access)."""
    return SimpleNamespace(
        timestamp=pd.Timestamp(ts, tz="UTC"),
        open=o, high=h, low=low, close=c, volume=v,
    )


def _fake_bars_response(ticker, bars):
    """Mimic ``StockBarsResponse`` — we only use the ``.data`` mapping."""
    return SimpleNamespace(data={ticker: bars})


# ── 1. get_quote ─────────────────────────────────────────────────────────────

class TestGetQuote:
    def test_happy_path(self):
        fake_client = MagicMock()
        fake_client.get_stock_bars.return_value = _fake_bars_response(
            "AAPL",
            [
                _fake_bar("2026-04-17", c=189.00),
                _fake_bar("2026-04-18", c=190.55, o=189.5, h=191.0, low=188.0,
                          v=52_000_000),
            ],
        )
        with patch.object(ama, "_client", return_value=fake_client):
            q = ama.get_quote("AAPL")
        assert q is not None
        assert q["symbol"] == "AAPL"
        assert q["price"] == pytest.approx(190.55)
        assert q["previousClose"] == pytest.approx(189.00)
        assert q["change"] == pytest.approx(1.55, rel=1e-3)
        assert q["changesPercentage"] > 0
        assert q["source"] == "alpaca"

    def test_empty_string_returns_none(self):
        fake_client = MagicMock()
        with patch.object(ama, "_client", return_value=fake_client):
            assert ama.get_quote("") is None
            fake_client.get_stock_bars.assert_not_called()

    def test_no_bars_returns_none(self):
        fake_client = MagicMock()
        fake_client.get_stock_bars.return_value = _fake_bars_response("ZZZ", [])
        with patch.object(ama, "_client", return_value=fake_client):
            assert ama.get_quote("ZZZ") is None

    def test_raises_returns_none(self):
        fake_client = MagicMock()
        fake_client.get_stock_bars.side_effect = RuntimeError("network down")
        with patch.object(ama, "_client", return_value=fake_client):
            assert ama.get_quote("AAPL") is None

    def test_client_missing_returns_none(self):
        with patch.object(ama, "_client", return_value=None):
            assert ama.get_quote("AAPL") is None


# ── 2. get_history ───────────────────────────────────────────────────────────

class TestGetHistory:
    def _bars(self):
        return [
            _fake_bar("2026-01-02", o=180.0, h=182.0, low=179.0, c=181.5),
            _fake_bar("2026-01-03", o=181.0, h=183.0, low=180.0, c=182.5),
            _fake_bar("2026-01-06", o=182.0, h=184.0, low=181.0, c=183.5),
        ]

    def test_happy_path(self):
        fake_client = MagicMock()
        fake_client.get_stock_bars.return_value = _fake_bars_response("AAPL", self._bars())
        with patch.object(ama, "_client", return_value=fake_client):
            # period="5y" ensures cutoff doesn't trim our 2026-01 test data.
            df = ama.get_history("AAPL", "5y")
        assert not df.empty
        for col in ("Open", "High", "Low", "Close", "Volume"):
            assert col in df.columns
        assert df.index.name == "Date"
        assert len(df) == 3

    def test_empty_bars_returns_empty_df(self):
        fake_client = MagicMock()
        fake_client.get_stock_bars.return_value = _fake_bars_response("ZZ", [])
        with patch.object(ama, "_client", return_value=fake_client):
            df = ama.get_history("ZZ", "3mo")
        assert df.empty

    def test_raises_returns_empty_df(self):
        fake_client = MagicMock()
        fake_client.get_stock_bars.side_effect = RuntimeError("timeout")
        with patch.object(ama, "_client", return_value=fake_client):
            df = ama.get_history("AAPL", "3mo")
        assert df.empty

    def test_client_missing_returns_empty_df(self):
        with patch.object(ama, "_client", return_value=None):
            df = ama.get_history("AAPL", "3mo")
        assert df.empty


# ── 3. get_earnings_calendar ────────────────────────────────────────────────

class TestEarningsCalendar:
    def test_always_empty(self):
        # Alpaca has no earnings endpoint — contract is ``[]`` so callers
        # fall through to FMP's /earnings-calendar without crashing.
        assert ama.get_earnings_calendar("AAPL") == []
        assert ama.get_earnings_calendar("") == []


# ── 4. is_available ─────────────────────────────────────────────────────────

class TestIsAvailable:
    def test_true_with_keys_and_sdk(self):
        with patch.object(ama, "_client", return_value=MagicMock()):
            assert ama.is_available() is True

    def test_false_when_client_none(self):
        with patch.object(ama, "_client", return_value=None):
            assert ama.is_available() is False

    def test_false_without_keys(self, monkeypatch):
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        # Use the real _client now — should short-circuit to None
        # because the env vars are gone.
        assert ama._client() is None
        assert ama.is_available() is False


# ── 5. fmp_service.get_quote fallback integration ───────────────────────────

class TestFmpFallback:
    """Verify the FMP → Alpaca fallback wire-up without hitting the network."""

    def setup_method(self):
        with fmp_service._cache_lock:
            fmp_service._cache.clear()

    def test_fmp_miss_falls_back_to_alpaca(self):
        with patch.object(fmp_service, "_fmp_get", return_value=None):
            fake_quote = {
                "symbol": "AAPL", "price": 195.2, "previousClose": 193.0,
                "change": 2.2, "changesPercentage": 1.14, "source": "alpaca",
            }
            fake_ama = MagicMock()
            fake_ama.get_quote.return_value = fake_quote
            with patch.object(fmp_service, "_ama", return_value=fake_ama):
                result = fmp_service.get_quote("AAPL")
        assert result is not None
        assert result["source"] == "alpaca"
        assert result["price"] == pytest.approx(195.2)

    def test_fmp_miss_and_alpaca_miss_returns_none(self):
        with patch.object(fmp_service, "_fmp_get", return_value=None):
            fake_ama = MagicMock()
            fake_ama.get_quote.return_value = None
            with patch.object(fmp_service, "_ama", return_value=fake_ama):
                assert fmp_service.get_quote("ZZZZ") is None

    def test_kr_ticker_skips_alpaca(self):
        # KR tickers must route through KIS (get_history branch), NOT Alpaca.
        with patch.object(fmp_service, "_fmp_get", return_value=None):
            fake_ama = MagicMock()
            with patch.object(fmp_service, "_ama", return_value=fake_ama):
                fmp_service.get_quote("005930.KS")
            fake_ama.get_quote.assert_not_called()
