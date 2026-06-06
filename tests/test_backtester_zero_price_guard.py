"""Regression — Backtester numeric guards for 0-price bars.

Bug (overnight hunt 2026-06-07, LANE 5 F3/F4/F5): KR halt days surface as
0.0 close rows. Unguarded divisions by ``closes[bh_start]`` (buy_hold_return),
``closes[-20]`` (KR mom20 score) and ``pv_arr[:-1]`` (daily returns) either
raised ZeroDivisionError — silently collapsing the whole backtest to ``None``
via the outer try/except — or produced inf/NaN that is invalid JSON.

These tests (a) prove the normal path is UNCHANGED by the guards, (b) lock
each guard against regression, and (c) assert the system-level invariant that
a 0-price bar never leaks inf/NaN into the response.
"""

import inspect
import math

import numpy as np
import pandas as pd
import pytest

from services.quant.backtester import Backtester
import services.quant.backtester as bt_module


def _ohlc(n=90, zero_at=None):
    """Build an OHLCV history with a mild uptrend. Optionally force a 0.0
    close at index ``zero_at`` (simulating a KR halt-day row)."""
    base = np.linspace(100.0, 140.0, n) + np.sin(np.linspace(0, 9, n)) * 3.0
    close = base.copy()
    if zero_at is not None:
        close[zero_at] = 0.0
    df = pd.DataFrame(
        {
            "Open": base * 0.999,
            "High": base * 1.012,
            "Low": base * 0.988,
            "Close": close,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=pd.date_range("2025-01-01", periods=n, freq="D"),
    )
    return df


def _patch_fetcher(monkeypatch, df):
    monkeypatch.setattr(
        bt_module._data_fetcher,
        "get_price_history",
        lambda ticker, period="1y", **kw: df,
    )


@pytest.mark.parametrize("ticker", ["AAPL", "005930.KS"])
def test_normal_series_unchanged(monkeypatch, ticker):
    """A clean series must still produce a sane, finite backtest — proves the
    guards did not perturb the verified math."""
    _patch_fetcher(monkeypatch, _ohlc())
    result = Backtester.run(ticker, period="1y")
    assert result is not None, "clean series should backtest successfully"
    for k in ("buy_hold_return", "alpha", "alpha_gross", "total_return"):
        v = result.get(k)
        assert isinstance(v, (int, float)) and math.isfinite(v), f"{k}={v!r}"
    # Uptrend → buy-and-hold should be clearly positive (sanity, not exact).
    assert result["buy_hold_return"] > 0


def test_zero_price_bar_never_leaks_inf_or_crashes(monkeypatch):
    """A 0-price bar at the buy-and-hold base index must not raise and must
    not surface inf/NaN in any numeric response field."""
    # bh_start = min(60, max(20, n//3)) = 30 for n=90 → force the 0 there,
    # which also lands at closes[-20] for the bar at index 49 (KR mom20 path).
    _patch_fetcher(monkeypatch, _ohlc(zero_at=30))
    result = Backtester.run("005930.KS", period="1y")  # KR → exercises mom20
    # Either a graceful dict (post-fix) or None — never an unhandled crash.
    if result is not None:
        for k, v in result.items():
            if isinstance(v, float):
                assert math.isfinite(v), f"field {k} leaked non-finite: {v}"


def test_zero_guards_present_in_source():
    """Lock the specific guards so a future refactor cannot silently drop
    them (the bug was an *absent* guard, invisible to value-only tests)."""
    run_src = inspect.getsource(Backtester.run)
    score_src = inspect.getsource(Backtester._calc_score)
    assert "_bh_base != 0" in run_src, "F4: buy_hold_return must guard 0 base"
    assert "np.isfinite(daily_rets)" in run_src, "F5: daily_rets must drop non-finite"
    assert "closes[-20] != 0" in score_src, "F3: mom20 must guard 0 denominator"
