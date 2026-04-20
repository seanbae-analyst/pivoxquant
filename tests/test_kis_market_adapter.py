"""PivoxQuant — kis_market_adapter tests.

HTTP + token-manager mocked end-to-end so tests stay offline. Covers:
  1. ``_to_code`` normalisation (005930.KS / 005930.kq / invalid)
  2. ``is_available`` reflects env presence
  3. ``get_history`` happy path — maps KIS ``output2`` → OHLCV DataFrame
  4. ``get_history`` safe on empty / error responses
  5. ``get_history`` returns empty when env/keys unset
  6. ``get_name`` happy path + missing-field safety
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.data import kis_market_adapter as kma


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def kis_env(monkeypatch):
    """Pretend the KIS app key/secret are configured."""
    monkeypatch.setenv("KIS_APP_KEY", "fake-app-key")
    monkeypatch.setenv("KIS_APP_SECRET", "fake-app-secret")
    yield
    # monkeypatch auto-cleans on teardown


def _fake_token_manager():
    """Return a token manager whose ``get_token`` returns a fixed string."""
    m = MagicMock()
    m.get_token.return_value = "fake-token"
    return m


# ── 1. Ticker normalisation ──────────────────────────────────────────────────

class TestToCode:
    def test_bare_6_digit(self):
        assert kma._to_code("005930") == "005930"

    def test_ks_suffix(self):
        assert kma._to_code("005930.KS") == "005930"

    def test_kq_suffix_lower(self):
        assert kma._to_code("035720.kq") == "035720"

    def test_invalid_short(self):
        assert kma._to_code("12345") is None

    def test_invalid_alpha(self):
        assert kma._to_code("AAPL") is None

    def test_empty(self):
        assert kma._to_code("") is None


# ── 2. is_available ─────────────────────────────────────────────────────────

class TestIsAvailable:
    def test_true_with_keys(self, kis_env):
        assert kma.is_available() is True

    def test_false_without_keys(self, monkeypatch):
        monkeypatch.delenv("KIS_APP_KEY", raising=False)
        monkeypatch.delenv("KIS_APP_SECRET", raising=False)
        assert kma.is_available() is False


# ── 3. get_history happy path ───────────────────────────────────────────────

class TestGetHistory:
    def _fake_response(self, bars):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        resp.json.return_value = {"rt_cd": "0", "output2": bars}
        return resp

    def test_happy_path(self, kis_env):
        bars = [
            # KIS returns most-recent first.
            {"stck_bsop_date": "20260103", "stck_oprc": "70000",
             "stck_hgpr": "71000", "stck_lwpr": "69500",
             "stck_clpr": "70500", "acml_vol": "12000000"},
            {"stck_bsop_date": "20260102", "stck_oprc": "69000",
             "stck_hgpr": "70200", "stck_lwpr": "68500",
             "stck_clpr": "69800", "acml_vol": "10000000"},
        ]

        with patch("kis_token_manager.get_kis_token_manager",
                    return_value=_fake_token_manager()), \
             patch.object(kma.requests, "get",
                           return_value=self._fake_response(bars)):
            df = kma.get_history("005930.KS", "5y")

        assert not df.empty
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert df.index.name == "Date"
        # Sorted ascending after normalisation.
        assert df.index[0] < df.index[-1]
        assert df["Close"].iloc[-1] == pytest.approx(70500.0)

    def test_empty_output(self, kis_env):
        with patch("kis_token_manager.get_kis_token_manager",
                    return_value=_fake_token_manager()), \
             patch.object(kma.requests, "get",
                           return_value=self._fake_response([])):
            df = kma.get_history("005930.KS", "3mo")
        assert df.empty

    def test_rt_cd_error(self, kis_env):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"rt_cd": "1", "msg1": "invalid ticker"}
        with patch("kis_token_manager.get_kis_token_manager",
                    return_value=_fake_token_manager()), \
             patch.object(kma.requests, "get", return_value=resp):
            df = kma.get_history("999999.KS", "3mo")
        assert df.empty

    def test_http_error(self, kis_env):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 500
        with patch("kis_token_manager.get_kis_token_manager",
                    return_value=_fake_token_manager()), \
             patch.object(kma.requests, "get", return_value=resp):
            df = kma.get_history("005930.KS", "3mo")
        assert df.empty

    def test_request_raises(self, kis_env):
        with patch("kis_token_manager.get_kis_token_manager",
                    return_value=_fake_token_manager()), \
             patch.object(kma.requests, "get",
                           side_effect=RuntimeError("network down")):
            df = kma.get_history("005930.KS", "3mo")
        assert df.empty

    def test_no_keys_returns_empty(self, monkeypatch):
        monkeypatch.delenv("KIS_APP_KEY", raising=False)
        monkeypatch.delenv("KIS_APP_SECRET", raising=False)
        assert kma.get_history("005930.KS", "3mo").empty

    def test_invalid_ticker_short_circuits(self, kis_env):
        # Must not even hit the network.
        with patch.object(kma.requests, "get") as get_mock:
            df = kma.get_history("AAPL", "3mo")
        assert df.empty
        get_mock.assert_not_called()


# ── 4. get_name ──────────────────────────────────────────────────────────────

class TestGetName:
    def test_happy_path(self, kis_env):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        resp.json.return_value = {
            "rt_cd": "0",
            "output": {"hts_kor_isnm": "삼성전자", "prdt_name": "삼성전자보통주"},
        }
        with patch("kis_token_manager.get_kis_token_manager",
                    return_value=_fake_token_manager()), \
             patch.object(kma.requests, "get", return_value=resp):
            name = kma.get_name("005930.KS")
        assert name == "삼성전자"

    def test_missing_name_field(self, kis_env):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"rt_cd": "0", "output": {}}
        with patch("kis_token_manager.get_kis_token_manager",
                    return_value=_fake_token_manager()), \
             patch.object(kma.requests, "get", return_value=resp):
            assert kma.get_name("005930.KS") is None

    def test_invalid_ticker(self, kis_env):
        assert kma.get_name("NOT_A_CODE") is None
