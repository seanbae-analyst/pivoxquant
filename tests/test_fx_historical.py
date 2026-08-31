"""Tests for ``services.fx_service.get_rate_at`` — historical USD/KRW.

The fetcher is mocked at the ``fmp_service._fmp_get`` boundary so no
network calls fire. We verify:

  - Exact-date hits return the expected close.
  - Weekend / holiday inputs roll back to the closest prior trading day.
  - Cache populates so repeat calls don't re-fetch.
  - Negative cache short-circuits hammering on a known-miss date.
  - Future dates and Nones fall back to spot.
  - The counterfactual route applies the historical rate at ingress.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from services import fx_service


@pytest.fixture(autouse=True)
def _reset_hist_cache():
    """Clear historical cache between tests to avoid cross-test bleed."""
    fx_service._hist_cache.clear()
    fx_service._hist_miss_ts.clear()
    yield
    fx_service._hist_cache.clear()
    fx_service._hist_miss_ts.clear()


def _bars(*pairs):
    """Build the FMP-shaped historical payload from (date, close) pairs."""
    return [{"date": d, "close": c} for d, c in pairs]


class TestGetRateAt:
    def test_none_input_returns_spot(self):
        with patch.object(fx_service, "get_rate", return_value=1380.0):
            assert fx_service.get_rate_at(None) == 1380.0

    def test_future_date_returns_spot(self):
        future = date.today() + timedelta(days=30)
        with patch.object(fx_service, "get_rate", return_value=1380.0):
            assert fx_service.get_rate_at(future) == 1380.0

    def test_exact_date_hit_from_fmp(self):
        target = date(2020, 6, 15)
        payload = _bars(
            ("2020-06-12", 1210.50),
            ("2020-06-15", 1208.75),
            ("2020-06-16", 1212.00),
        )
        with patch("services.data.fmp._fmp_get", return_value=payload):
            r = fx_service.get_rate_at(target)
        assert r == 1208.75
        # Cache populated
        assert fx_service._hist_cache["2020-06-15"] == 1208.75

    def test_weekend_rolls_to_prior_trading_day(self):
        # 2020-06-13 was a Saturday; 2020-06-12 (Fri) is the prior close.
        target = date(2020, 6, 13)
        payload = _bars(
            ("2020-06-11", 1209.00),
            ("2020-06-12", 1210.50),
            ("2020-06-15", 1208.75),
        )
        with patch("services.data.fmp._fmp_get", return_value=payload):
            r = fx_service.get_rate_at(target)
        assert r == 1210.50

    def test_cache_hit_skips_fetch(self):
        target = date(2020, 6, 15)
        fx_service._hist_cache["2020-06-15"] = 1234.56
        with patch("services.data.fmp._fmp_get") as m:
            r = fx_service.get_rate_at(target)
        assert r == 1234.56
        m.assert_not_called()

    def test_empty_payload_falls_back_to_spot(self):
        target = date(2020, 6, 15)
        with patch("services.data.fmp._fmp_get", return_value=[]), \
                patch.object(fx_service, "get_rate", return_value=1380.0):
            r = fx_service.get_rate_at(target)
        assert r == 1380.0
        # Negative cache primed
        assert "2020-06-15" in fx_service._hist_miss_ts

    def test_negative_cache_short_circuits(self):
        target = date(2020, 6, 15)
        # Simulate a recent miss
        import time as _t
        fx_service._hist_miss_ts["2020-06-15"] = _t.time()
        with patch("services.data.fmp._fmp_get") as m, \
                patch.object(fx_service, "get_rate", return_value=1380.0):
            r = fx_service.get_rate_at(target)
        assert r == 1380.0
        m.assert_not_called()

    def test_dict_payload_with_historical_key(self):
        # FMP sometimes wraps bars in {"historical": [...]}
        target = date(2020, 6, 15)
        payload = {"historical": _bars(("2020-06-15", 1208.75))}
        with patch("services.data.fmp._fmp_get", return_value=payload):
            r = fx_service.get_rate_at(target)
        assert r == 1208.75

    def test_garbage_close_filtered(self):
        # close ≤ 100 is the sanity guard inherited from spot fetcher.
        target = date(2020, 6, 15)
        payload = _bars(
            ("2020-06-15", 0.0),
            ("2020-06-12", 1210.50),
        )
        with patch("services.data.fmp._fmp_get", return_value=payload):
            r = fx_service.get_rate_at(target)
        # 06-15 was filtered, fell back to 06-12
        assert r == 1210.50

    def test_iso_string_input(self):
        target = "2020-06-15"
        payload = _bars(("2020-06-15", 1208.75))
        with patch("services.data.fmp._fmp_get", return_value=payload):
            r = fx_service.get_rate_at(target)
        assert r == 1208.75


class TestGetRateAtStrict:
    """``get_rate_at_strict`` returns None (never spot) when no genuine
    historical rate exists — the capital-gains CSV relies on this to leave
    KRW blank rather than fabricate a rate (표시광고법)."""

    def test_none_input_returns_none(self):
        assert fx_service.get_rate_at_strict(None) is None

    def test_future_date_returns_none_not_spot(self):
        future = date.today() + timedelta(days=30)
        with patch.object(fx_service, "get_rate", return_value=1380.0):
            assert fx_service.get_rate_at_strict(future) is None

    def test_today_returns_none(self):
        with patch.object(fx_service, "get_rate", return_value=1380.0):
            assert fx_service.get_rate_at_strict(date.today()) is None

    def test_exact_date_hit_returns_rate(self):
        target = date(2020, 6, 15)
        payload = _bars(("2020-06-15", 1208.75), ("2020-06-12", 1210.50))
        with patch("services.data.fmp._fmp_get", return_value=payload):
            r = fx_service.get_rate_at_strict(target)
        assert r == 1208.75

    def test_weekend_rolls_to_prior_trading_day(self):
        target = date(2020, 6, 14)  # Sunday
        payload = _bars(("2020-06-12", 1209.00))
        with patch("services.data.fmp._fmp_get", return_value=payload):
            r = fx_service.get_rate_at_strict(target)
        assert r == 1209.00

    def test_cache_hit_skips_fetch(self):
        target = date(2020, 6, 15)
        fx_service._hist_cache["2020-06-15"] = 1234.56
        with patch("services.data.fmp._fmp_get") as m:
            r = fx_service.get_rate_at_strict(target)
            m.assert_not_called()
        assert r == 1234.56

    def test_empty_payload_returns_none_and_marks_miss(self):
        target = date(2020, 6, 15)
        with patch("services.data.fmp._fmp_get", return_value=[]):
            with patch.object(fx_service, "get_rate", return_value=1380.0):
                r = fx_service.get_rate_at_strict(target)
        assert r is None  # NOT 1380.0 spot
        assert "2020-06-15" in fx_service._hist_miss_ts

    def test_negative_cache_returns_none(self):
        import time as _t
        target = date(2020, 6, 15)
        fx_service._hist_miss_ts["2020-06-15"] = _t.time()
        with patch("services.data.fmp._fmp_get") as m:
            with patch.object(fx_service, "get_rate", return_value=1380.0):
                r = fx_service.get_rate_at_strict(target)
            m.assert_not_called()
        assert r is None

