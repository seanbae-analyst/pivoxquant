"""
PivoxQuant — pyKRX service tests
================================
Unit tests for `services.data.pykrx_service.PyKRXService`.

We deliberately avoid hitting the real KRX servers. All tests either:
  - patch the underlying `pykrx.stock` module with MagicMock, or
  - exercise pure Python paths (ticker normalization, cache TTL).

Tests assert:
  1. Ticker normalization (005930, 005930.KS, 005930.KQ, invalid)
  2. Cache hit / miss (second call does not re-invoke pyKRX)
  3. Empty list + WARNING log on pyKRX exception
  4. get_foreign_flow success path with synthetic DataFrame
  5. get_short_balance_ratio success + divide-by-zero safe
  6. get_market_flow_summary with invalid market
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.data import pykrx_service as mod
from services.data.pykrx_service import PyKRXService, _normalize_ticker


# ── 1. Ticker normalization ─────────────────────────────────────────────────

class TestNormalizeTicker:
    def test_bare_6_digit(self):
        assert _normalize_ticker("005930") == "005930"

    def test_with_ks_suffix(self):
        assert _normalize_ticker("005930.KS") == "005930"

    def test_with_kq_suffix_lowercase(self):
        assert _normalize_ticker("035720.kq") == "035720"

    def test_with_krx_suffix(self):
        assert _normalize_ticker("000660.KRX") == "000660"

    def test_invalid_too_short(self):
        assert _normalize_ticker("12345") is None

    def test_invalid_alpha(self):
        assert _normalize_ticker("AAPL") is None

    def test_invalid_empty(self):
        assert _normalize_ticker("") is None

    def test_invalid_none(self):
        assert _normalize_ticker(None) is None  # type: ignore[arg-type]


# ── 2. Cache behavior ───────────────────────────────────────────────────────

class TestCache:
    def test_cache_hit_avoids_second_external_call(self):
        """Second call within TTL must NOT re-invoke pyKRX."""
        svc = PyKRXService(cache_ttl=3600, rate_limit_sleep=0)

        fake_df = pd.DataFrame(
            {"외국인합계": [1e9], "기관합계": [2e9], "개인": [-3e9]},
            index=pd.to_datetime(["2026-04-17"]),
        )
        fake_stock = MagicMock()
        fake_stock.get_market_trading_value_by_date.return_value = fake_df

        with patch.object(mod, "_pykrx_stock", fake_stock), \
             patch.object(mod, "_PYKRX_AVAILABLE", True):
            r1 = svc.get_foreign_flow("005930", days=30)
            r2 = svc.get_foreign_flow("005930", days=30)

        assert r1 == r2
        assert len(r1) == 1
        assert r1[0]["foreign_net_buy_eok"] == 10.0  # 1e9 / 1e8
        # External call fired exactly once across the two invocations.
        assert fake_stock.get_market_trading_value_by_date.call_count == 1

    def test_clear_cache_forces_refetch(self):
        svc = PyKRXService(cache_ttl=3600, rate_limit_sleep=0)
        fake_df = pd.DataFrame(
            {"외국인합계": [1e9], "기관합계": [0], "개인": [0]},
            index=pd.to_datetime(["2026-04-17"]),
        )
        fake_stock = MagicMock()
        fake_stock.get_market_trading_value_by_date.return_value = fake_df

        with patch.object(mod, "_pykrx_stock", fake_stock), \
             patch.object(mod, "_PYKRX_AVAILABLE", True):
            svc.get_foreign_flow("005930", days=30)
            svc.clear_cache()
            svc.get_foreign_flow("005930", days=30)

        assert fake_stock.get_market_trading_value_by_date.call_count == 2


# ── 3. Error handling ──────────────────────────────────────────────────────

class TestErrorHandling:
    def test_pykrx_exception_returns_empty_list_and_warns(self, caplog):
        svc = PyKRXService(rate_limit_sleep=0)
        fake_stock = MagicMock()
        fake_stock.get_market_trading_value_by_date.side_effect = RuntimeError("network down")

        with patch.object(mod, "_pykrx_stock", fake_stock), \
             patch.object(mod, "_PYKRX_AVAILABLE", True), \
             caplog.at_level(logging.WARNING, logger=mod.logger.name):
            result = svc.get_foreign_flow("005930", days=30)

        assert result == []
        assert any("get_foreign_flow failed" in rec.message for rec in caplog.records)

    def test_invalid_ticker_short_circuits_without_pykrx_call(self):
        svc = PyKRXService(rate_limit_sleep=0)
        fake_stock = MagicMock()
        with patch.object(mod, "_pykrx_stock", fake_stock), \
             patch.object(mod, "_PYKRX_AVAILABLE", True):
            result = svc.get_foreign_flow("AAPL", days=30)
        assert result == []
        fake_stock.get_market_trading_value_by_date.assert_not_called()

    def test_pykrx_unavailable_returns_empty(self):
        svc = PyKRXService(rate_limit_sleep=0)
        with patch.object(mod, "_PYKRX_AVAILABLE", False):
            assert svc.get_foreign_flow("005930") == []
            assert svc.get_short_interest("005930") == []
            assert svc.get_short_balance_ratio("005930") == {}
            assert svc.get_market_flow_summary("KOSPI") == {}


# ── 4. get_short_balance_ratio ──────────────────────────────────────────────

class TestShortBalanceRatio:
    def test_success_path(self):
        svc = PyKRXService(cache_ttl=3600, rate_limit_sleep=0)

        df_bal = pd.DataFrame(
            {"공매도잔고": [1000], "공매도금액": [5e9]},  # 50 억원
            index=pd.to_datetime(["2026-04-17"]),
        )
        df_cap = pd.DataFrame(
            {"시가총액": [5e11]},  # 5000 억원
            index=pd.to_datetime(["2026-04-17"]),
        )
        fake_stock = MagicMock()
        fake_stock.get_shorting_balance_by_date.return_value = df_bal
        fake_stock.get_market_cap_by_date.return_value = df_cap

        with patch.object(mod, "_pykrx_stock", fake_stock), \
             patch.object(mod, "_PYKRX_AVAILABLE", True):
            result = svc.get_short_balance_ratio("005930.KS")

        assert result["short_balance_eok"] == 50.0
        assert result["market_cap_eok"] == 5000.0
        assert result["ratio_pct"] == 1.0  # 50/5000 * 100

    def test_zero_market_cap_safe(self):
        """Divide-by-zero must not crash."""
        svc = PyKRXService(cache_ttl=3600, rate_limit_sleep=0)
        df_bal = pd.DataFrame(
            {"공매도잔고": [1000], "공매도금액": [5e9]},
            index=pd.to_datetime(["2026-04-17"]),
        )
        df_cap = pd.DataFrame(
            {"시가총액": [0]},
            index=pd.to_datetime(["2026-04-17"]),
        )
        fake_stock = MagicMock()
        fake_stock.get_shorting_balance_by_date.return_value = df_bal
        fake_stock.get_market_cap_by_date.return_value = df_cap

        with patch.object(mod, "_pykrx_stock", fake_stock), \
             patch.object(mod, "_PYKRX_AVAILABLE", True):
            result = svc.get_short_balance_ratio("005930")

        assert result["ratio_pct"] == 0.0


# ── 5. get_market_flow_summary ──────────────────────────────────────────────

class TestMarketFlow:
    def test_invalid_market(self):
        svc = PyKRXService(rate_limit_sleep=0)
        with patch.object(mod, "_PYKRX_AVAILABLE", True):
            assert svc.get_market_flow_summary(market="NASDAQ") == {}

    def test_bad_date_format(self):
        svc = PyKRXService(rate_limit_sleep=0)
        with patch.object(mod, "_PYKRX_AVAILABLE", True):
            assert svc.get_market_flow_summary(market="KOSPI", date="not-a-date") == {}

    def test_success_path(self):
        svc = PyKRXService(cache_ttl=3600, rate_limit_sleep=0)
        df = pd.DataFrame(
            {"순매수": [1e10, -2e10, 3e9]},
            index=["외국인", "기관", "개인"],
        )
        fake_stock = MagicMock()
        fake_stock.get_market_trading_value_by_investor.return_value = df

        with patch.object(mod, "_pykrx_stock", fake_stock), \
             patch.object(mod, "_PYKRX_AVAILABLE", True):
            result = svc.get_market_flow_summary(market="KOSPI")

        assert result["market"] == "KOSPI"
        assert result["net_buy_eok"]["외국인"] == 100.0  # 1e10 / 1e8
        assert result["net_buy_eok"]["기관"] == -200.0
