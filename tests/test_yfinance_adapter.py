"""PivoxQuant — yfinance_adapter tests.

Deliberately no network: the yfinance module is patched everywhere so
tests stay offline, deterministic, and < 1s. We cover the contract the
fallback chain in ``fmp_service`` depends on:

  1. ``get_quote`` returns a dict with numeric ``price`` on success
  2. ``get_quote`` returns ``None`` when the ticker is unknown
  3. ``get_quote`` returns ``None`` when yfinance itself raises
  4. ``get_history`` returns a DataFrame with OHLCV columns on success
  5. ``get_history`` returns an *empty* DataFrame on failure (never raises)
  6. ``get_earnings_calendar`` returns a list of dicts or []
  7. ``is_available()`` reflects whether the module imports
  8. ``fmp_service.get_quote`` routes to yfinance when FMP returns None
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import fmp_service
from services.data import yfinance_adapter as yfa


# ── Helpers ──────────────────────────────────────────────────────────────────

class _FastInfo(dict):
    """Mimic yfinance ``fast_info`` which supports both attr + dict access."""
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def _mock_ticker(fast_info=None, raises=False):
    tk = MagicMock()
    if raises:
        type(tk).fast_info = MagicMock(side_effect=RuntimeError("boom"))
    else:
        tk.fast_info = _FastInfo(fast_info or {})
    return tk


# ── 1. get_quote success ─────────────────────────────────────────────────────

class TestGetQuote:
    def test_happy_path(self):
        fake_yf = MagicMock()
        fake_yf.Ticker.return_value = _mock_ticker({
            "last_price": 190.55,
            "previous_close": 189.00,
            "day_low": 188.0,
            "day_high": 191.0,
            "last_volume": 52_000_000,
            "market_cap": 3_000_000_000_000,
            "exchange": "NASDAQ",
        })
        with patch.object(yfa, "_yf", return_value=fake_yf):
            q = yfa.get_quote("AAPL")
        assert q is not None
        assert q["symbol"] == "AAPL"
        assert q["price"] == pytest.approx(190.55)
        assert q["previousClose"] == pytest.approx(189.00)
        assert q["change"] == pytest.approx(1.55, rel=1e-3)
        assert q["changesPercentage"] > 0
        assert q["exchange"] == "NASDAQ"
        assert q["source"] == "yfinance"

    def test_empty_string_returns_none(self):
        # Never construct a Ticker for bogus input — contract.
        fake_yf = MagicMock()
        with patch.object(yfa, "_yf", return_value=fake_yf):
            assert yfa.get_quote("") is None
            fake_yf.Ticker.assert_not_called()

    def test_unknown_ticker_returns_none(self):
        # yfinance returns last_price=None for dead tickers — we must too.
        fake_yf = MagicMock()
        fake_yf.Ticker.return_value = _mock_ticker({"last_price": None})
        with patch.object(yfa, "_yf", return_value=fake_yf):
            assert yfa.get_quote("ZZZZZZ") is None

    def test_yf_raises_returns_none(self):
        fake_yf = MagicMock()
        fake_yf.Ticker.side_effect = RuntimeError("network down")
        with patch.object(yfa, "_yf", return_value=fake_yf):
            assert yfa.get_quote("AAPL") is None

    def test_module_missing_returns_none(self):
        with patch.object(yfa, "_yf", return_value=None):
            assert yfa.get_quote("AAPL") is None


# ── 2. get_history ───────────────────────────────────────────────────────────

class TestGetHistory:
    def _df(self):
        idx = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-06"])
        return pd.DataFrame(
            {
                "Open":  [180.0, 181.0, 182.0],
                "High":  [182.0, 183.0, 184.0],
                "Low":   [179.0, 180.0, 181.0],
                "Close": [181.5, 182.5, 183.5],
                "Adj Close": [181.5, 182.5, 183.5],
                "Volume": [50_000_000, 48_000_000, 55_000_000],
            },
            index=idx,
        )

    def test_happy_path(self):
        fake_yf = MagicMock()
        fake_yf.download.return_value = self._df()
        with patch.object(yfa, "_yf", return_value=fake_yf):
            df = yfa.get_history("AAPL", "3mo")
        assert not df.empty
        assert list(df.columns)[:5] == ["Open", "High", "Low", "Close", "Adj Close"]
        assert df.index.name == "Date"
        assert len(df) == 3

    def test_empty_download_returns_empty_df(self):
        fake_yf = MagicMock()
        fake_yf.download.return_value = pd.DataFrame()
        with patch.object(yfa, "_yf", return_value=fake_yf):
            df = yfa.get_history("ZZZZ", "3mo")
        assert df.empty

    def test_raises_returns_empty_df(self):
        fake_yf = MagicMock()
        fake_yf.download.side_effect = RuntimeError("timeout")
        with patch.object(yfa, "_yf", return_value=fake_yf):
            df = yfa.get_history("AAPL", "3mo")
        assert df.empty

    def test_multiindex_columns_flattened(self):
        # yfinance > 0.2.40 sometimes returns columns as MultiIndex for a
        # single-ticker request. We must flatten so downstream .Close works.
        idx = pd.to_datetime(["2026-01-02", "2026-01-03"])
        multi = pd.DataFrame(
            {
                ("Open",   "AAPL"): [180.0, 181.0],
                ("High",   "AAPL"): [182.0, 183.0],
                ("Low",    "AAPL"): [179.0, 180.0],
                ("Close",  "AAPL"): [181.5, 182.5],
                ("Volume", "AAPL"): [50_000_000, 48_000_000],
            },
            index=idx,
        )
        multi.columns = pd.MultiIndex.from_tuples(multi.columns)
        fake_yf = MagicMock()
        fake_yf.download.return_value = multi
        with patch.object(yfa, "_yf", return_value=fake_yf):
            df = yfa.get_history("AAPL", "3mo")
        assert not df.empty
        assert "Close" in df.columns
        assert df["Close"].iloc[-1] == pytest.approx(182.5)


# ── 3. get_earnings_calendar ────────────────────────────────────────────────

class TestEarningsCalendar:
    def test_dict_shape(self):
        fake_yf = MagicMock()
        tk = MagicMock()
        tk.calendar = {
            "Earnings Date": [pd.Timestamp("2026-05-01"), pd.Timestamp("2026-05-03")],
            "Earnings Average": 1.75,
            "Revenue Average": 95_000_000_000,
        }
        fake_yf.Ticker.return_value = tk
        with patch.object(yfa, "_yf", return_value=fake_yf):
            out = yfa.get_earnings_calendar("AAPL")
        assert len(out) == 1
        assert out[0]["symbol"] == "AAPL"
        assert out[0]["date"] == "2026-05-01"
        assert out[0]["epsEstimated"] == pytest.approx(1.75)
        assert out[0]["source"] == "yfinance"

    def test_none_returns_empty(self):
        fake_yf = MagicMock()
        tk = MagicMock()
        tk.calendar = None
        fake_yf.Ticker.return_value = tk
        with patch.object(yfa, "_yf", return_value=fake_yf):
            assert yfa.get_earnings_calendar("AAPL") == []


# ── 4. is_available ──────────────────────────────────────────────────────────

class TestIsAvailable:
    def test_true_when_import_succeeds(self):
        with patch.object(yfa, "_yf", return_value=MagicMock()):
            assert yfa.is_available() is True

    def test_false_when_import_fails(self):
        with patch.object(yfa, "_yf", return_value=None):
            assert yfa.is_available() is False


# ── 5. fmp_service.get_quote fallback integration ────────────────────────────

class TestFmpFallback:
    """Verify the FMP → yfinance fallback wire-up without hitting the network."""

    def setup_method(self):
        # Nuke caches between tests so each scenario starts clean.
        with fmp_service._cache_lock:
            fmp_service._cache.clear()

    def test_fmp_miss_falls_back_to_yfinance(self):
        # FMP's network layer returns None (402 / budget-out / network fail).
        with patch.object(fmp_service, "_fmp_get", return_value=None):
            # yfinance returns a clean quote.
            fake_yf_quote = {
                "symbol": "AAPL", "price": 195.2, "previousClose": 193.0,
                "change": 2.2, "changesPercentage": 1.14, "source": "yfinance",
            }
            fake_yfa = MagicMock()
            fake_yfa.get_quote.return_value = fake_yf_quote
            with patch.object(fmp_service, "_yfa", return_value=fake_yfa):
                result = fmp_service.get_quote("AAPL")
        assert result is not None
        assert result["source"] == "yfinance"
        assert result["price"] == pytest.approx(195.2)

    def test_fmp_miss_and_yf_miss_returns_none(self):
        with patch.object(fmp_service, "_fmp_get", return_value=None):
            fake_yfa = MagicMock()
            fake_yfa.get_quote.return_value = None
            with patch.object(fmp_service, "_yfa", return_value=fake_yfa):
                assert fmp_service.get_quote("ZZZZ") is None

    def test_kr_ticker_skips_yfinance(self):
        # Korean tickers must NOT hit yfinance (we use pyKRX instead).
        with patch.object(fmp_service, "_fmp_get", return_value=None):
            fake_yfa = MagicMock()
            with patch.object(fmp_service, "_yfa", return_value=fake_yfa):
                fmp_service.get_quote("005930.KS")
            fake_yfa.get_quote.assert_not_called()
