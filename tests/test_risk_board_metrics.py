"""Numeric correctness guard for risk_board_service Sharpe/Sortino/Calmar.

Regression net for the 2026-05-23 fix: these three helpers had diverged
from the canonical formulas in services/quant/backtester.py (no risk-free
subtraction, 0-anchored downside, arithmetic annualization). They feed the
Risk Board PDF/HTML delivered to Premium users, and NO test covered their
numerical output — only that the deck rendered. This file pins the math.

The reference values are computed independently with numpy here, mirroring
backtester.py:475-502, so a future edit that re-breaks the formulas fails
loudly instead of silently shipping wrong Sharpe/Sortino/Calmar.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from services.artifacts import risk_board_service as rb

_RF = 0.045  # annual risk-free rate (must match backtester.py + risk_board)


def _ref_sharpe(rets: list[float]) -> float:
    a = np.array(rets, dtype=float)
    mean_annual = a.mean() * 252
    std_annual = a.std(ddof=1) * math.sqrt(252)
    return round((mean_annual - _RF) / std_annual, 2)


def _ref_sortino(rets: list[float]) -> float:
    a = np.array(rets, dtype=float)
    rf_daily = _RF / 252
    downside = np.minimum(a - rf_daily, 0.0)
    down_std_annual = math.sqrt(float(np.mean(downside ** 2))) * math.sqrt(252)
    return round((a.mean() * 252 - _RF) / down_std_annual, 2)


# Deterministic-but-non-trivial return series (fixed seed, no network).
_SERIES = [
    [round(x, 6) for x in np.random.default_rng(seed).normal(0.0006, 0.013, 260)]
    for seed in (1, 7, 42, 99)
]


@pytest.mark.parametrize("rets", _SERIES)
def test_sharpe_matches_canonical(rets):
    assert rb._sharpe(rets) == _ref_sharpe(rets)


@pytest.mark.parametrize("rets", _SERIES)
def test_sortino_matches_canonical(rets):
    out = rb._sortino(rets)
    # Both None or both equal (down_std could be 0 in a pathological set).
    assert out == _ref_sortino(rets)


def test_sharpe_subtracts_risk_free():
    """The discriminator the old `mean/std` formula failed.

    A series whose mean daily return is EXACTLY the daily risk-free rate
    has zero excess return, so a correct Sharpe is ~0. The pre-fix
    `(mean/std)*sqrt(252)` form returned a clearly positive number.
    """
    rf_daily = _RF / 252
    rets = []
    for i in range(60):
        rets.append(rf_daily + (0.002 if i % 2 == 0 else -0.002))
    # mean == rf_daily exactly → annualized excess == 0 → Sharpe == 0.0
    assert rb._sharpe(rets) == 0.0


def test_sortino_anchors_downside_at_mar():
    """Days that beat the MAR (rf) must NOT count as downside.

    A series that is always >= rf_daily has zero target-downside, so
    Sortino is undefined (None). The old `r < 0` form would also have
    returned None here, so pair with a mixed series to pin the anchor.
    """
    rf_daily = _RF / 252
    # All returns strictly above the MAR → no downside → None.
    assert rb._sortino([rf_daily + 0.001] * 40) is None
    # A return that is positive but BELOW the MAR must register as
    # downside (the old 0-anchored form would have missed it).
    below_mar = rf_daily * 0.5  # positive, but under the risk-free hurdle
    mixed = [0.01, below_mar] * 30
    assert rb._sortino(mixed) is not None


def test_calmar_is_geometric_not_arithmetic():
    """Calmar uses compound annualized return / |max drawdown|.

    For a constant positive daily return the geometric annualization
    diverges from the old arithmetic `mean*252` form; pin the compound
    value so the period-dependent arithmetic bug can't return.
    """
    r = 0.001
    rets = [r] * 252
    mdd = rb._max_dd(rets)  # monotonic up → ~0 drawdown
    # Monotonic-up series has no drawdown, so Calmar is undefined.
    assert rb._calmar(rets, mdd) is None
    # Inject one down day to create a real (negative) max drawdown.
    rets2 = [r] * 100 + [-0.05] + [r] * 151
    mdd2 = rb._max_dd(rets2)
    assert mdd2 is not None and mdd2 < 0
    cum = 1.0
    for x in rets2:
        cum *= (1.0 + x)
    expected = round(((cum ** (252 / len(rets2))) - 1) * 100 / abs(mdd2), 2)
    assert rb._calmar(rets2, mdd2) == expected


def test_short_series_returns_none():
    assert rb._sharpe([0.01] * 5) is None
    assert rb._sortino([0.01] * 5) is None
    assert rb._calmar([0.01] * 5, -10.0) is None
