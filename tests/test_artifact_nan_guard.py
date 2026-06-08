"""Regression: artifact PDFs must never render '$nan' / 'nan%'.

Commit 35c08072 ("guard NaN last-close so paid PDFs/detail never show $nan")
hardened the ``_safe_price`` / ``_ticker_last_price`` helpers but left their
SIBLINGS passing non-finite floats straight into rendered numbers:

  * kpi_dashboard ``_ytd_return``           — last-close NaN → mean NaN → "+nan%"
  * weekly_memo  ``_weekly_return_for_ticker`` — last-close NaN → "nan%"
  * capital_allocation ``_to_v3_shape``     — ``is not None`` lets NaN vol/sharpe
                                              through → "nan%" / "nan"

These tests lock the ``math.isfinite`` guards added to close those paths.
A suspended/halted stock can return a price history whose trailing close is
NaN, which is the real-world trigger.
"""
from __future__ import annotations

import math

import pandas as pd


def test_kpi_ytd_return_skips_nan_close(monkeypatch):
    from services.artifacts import kpi_dashboard_service as kpi

    class _P:
        ticker = "AAPL"

    # History whose last close is NaN (suspended-stock data gap).
    monkeypatch.setattr(
        kpi, "_safe_history",
        lambda ticker, period="1y": pd.DataFrame({"Close": [100.0, float("nan")]}),
    )
    assert kpi._ytd_return([_P()]) is None, \
        "NaN last-close must be skipped, not averaged into a nan return"


def test_kpi_ytd_return_clean_when_one_good_one_nan(monkeypatch):
    from services.artifacts import kpi_dashboard_service as kpi

    class _P:
        def __init__(self, t):
            self.ticker = t

    def fake_hist(ticker, period="1y"):
        if ticker == "GOOD":
            return pd.DataFrame({"Close": [100.0, 110.0]})       # +10%
        return pd.DataFrame({"Close": [100.0, float("nan")]})    # → skipped

    monkeypatch.setattr(kpi, "_safe_history", fake_hist)
    out = kpi._ytd_return([_P("GOOD"), _P("BAD")])
    assert out is not None and math.isfinite(out)
    assert abs(out - 10.0) < 1e-6, "only the finite ticker should contribute"


def test_weekly_return_skips_nan_close(monkeypatch):
    from services.artifacts import weekly_memo_service as wm

    monkeypatch.setattr(
        wm, "_safe_fetch_price_history",
        lambda ticker, period="1mo": pd.DataFrame(
            {"Close": [100.0, 101.0, 102.0, 103.0, 104.0, float("nan")]}
        ),
    )
    assert wm._weekly_return_for_ticker("AAPL") is None, \
        "NaN last-close must yield None, not a nan %"


def test_capital_allocation_vol_sharpe_nan_renders_dash():
    from services.artifacts.capital_allocation_service import CapitalAllocationService

    svc = CapitalAllocationService()
    data = {
        "portfolio_ccy": "USD",
        "cash_amount": 1000.0,
        "scenarios": [{
            "label": "Scenario A", "type": "x",
            "tickers": [], "weights": [],
            "return_cagr": float("nan"),
            "volatility": float("nan"),
            "max_dd": float("nan"),
            "sharpe": float("nan"),
            "note": "",
        }],
    }
    shaped = svc._to_v3_shape(data)
    sc = shaped["scenarios"][0]
    assert sc["vol"] == "—"
    assert sc["sharpe"] == "—"
    assert sc["cagr"] == "—"
    assert sc["max_dd"] == "—"
    # belt-and-suspenders: no literal 'nan' leaked into any rendered numeric field
    blob = (sc["vol"] + sc["sharpe"] + sc["cagr"] + sc["max_dd"]).lower()
    assert "nan" not in blob


def test_capital_allocation_finite_vol_sharpe_still_render():
    """Sanity: the guard must NOT swallow legitimate finite values."""
    from services.artifacts.capital_allocation_service import CapitalAllocationService

    svc = CapitalAllocationService()
    data = {
        "portfolio_ccy": "USD",
        "scenarios": [{
            "label": "S", "type": "x", "tickers": [], "weights": [],
            "return_cagr": 12.34, "volatility": 18.5,
            "max_dd": -22.1, "sharpe": 0.67, "note": "",
        }],
    }
    sc = svc._to_v3_shape(data)["scenarios"][0]
    assert sc["vol"] == "18.50%"
    assert sc["sharpe"] == "0.67"
    assert sc["cagr"] == "+12.34%"
