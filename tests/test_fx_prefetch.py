"""fx_service.prefetch_range — bulk historical-FX cache warm (PERF).

portfolio_history() warms the whole equity-curve window in ONE fetch instead of
~N/14 *sequential* lazy 14-day-window fetches (≈7s cold on a 6mo curve). The
prefetch must populate the SAME ``_hist_cache`` that :func:`get_rate_at` reads,
with the SAME values — it is a pure performance change, never an FX-value change
(FX consistency is load-bearing — see the +593,259% / +52,281% history bugs).
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import services.fx_service as fx


def test_prefetch_range_warms_cache_then_get_rate_at_hits_without_refetch(monkeypatch):
    monkeypatch.setattr(fx, "_hist_cache", {})
    monkeypatch.setattr(fx, "_hist_miss_ts", {})

    bars = {"2026-05-01": 1360.0, "2026-05-02": 1362.5, "2026-05-05": 1365.0}
    with patch.object(fx, "_fetch_historical_window", return_value=bars) as m:
        n = fx.prefetch_range("2026-05-01", "2026-05-05")

    assert n == 3
    m.assert_called_once_with("2026-05-01", "2026-05-05")
    assert fx._hist_cache["2026-05-02"] == 1362.5

    # get_rate_at now returns the warmed value with NO further upstream fetch.
    with patch.object(fx, "_fetch_historical_window") as m2:
        assert fx.get_rate_at(date(2026, 5, 2)) == 1362.5
        m2.assert_not_called()


def test_prefetch_range_empty_upstream_is_safe(monkeypatch):
    monkeypatch.setattr(fx, "_hist_cache", {})
    with patch.object(fx, "_fetch_historical_window", return_value={}):
        assert fx.prefetch_range("2026-05-01", "2026-05-05") == 0


def test_prefetch_range_accepts_date_objects(monkeypatch):
    monkeypatch.setattr(fx, "_hist_cache", {})
    with patch.object(
        fx, "_fetch_historical_window", return_value={"2026-05-01": 1360.0}
    ) as m:
        fx.prefetch_range(date(2026, 5, 1), date(2026, 5, 5))
    m.assert_called_once_with("2026-05-01", "2026-05-05")
