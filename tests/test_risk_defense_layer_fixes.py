"""Regression net for the 2026-05-26 Risk Defense / Risk Board fixes (R#1-R#6).

Each test pins behavior that was silently broken before:

  R#1  VIX key mismatch  — defense-status read "current_vix" but VIXStrategy
        returns "vix", so Layer 3 (VIX) never fired.
  R#2  regime always TRANSITION — defense-status called a non-existent
        VolatilityRegime.detect(); RegimeSwitching.analyze() now drives regime.
  R#3  PDF Layer 7 label mismatch — risk_board_service mapped "L7_REGIME" but
        risk_defense appends "L7_CASH_MGMT", so L7 always rendered as passed.
  R#4  tail-ratio BREACH dead code — `if t<0.7 ... elif t<0.5` made BREACH
        unreachable; order is now stricter-first.
  R#5  PDF mixed-portfolio FX — native KRW + USD values were summed raw,
        corrupting total_mv and every weight-derived metric.
  R#6  PDF "$" hardcoded for KRW books.

These are pure-Python / formula-level checks: no network, no DB.
"""
from __future__ import annotations

import numpy as np
import pytest

from services.artifacts import risk_board_service as rb
from services.quant import models as qm
from services.quant.risk_defense import RiskDefenseSystem


# ─────────────────────────────────────────────────────────────────────────────
# R#1 — VIX key contract + Layer 3 fires
# ─────────────────────────────────────────────────────────────────────────────

def test_r1_vixstrategy_returns_vix_key_not_current_vix(monkeypatch):
    """VIXStrategy.analyze() must expose the level under 'vix' (the key
    routes/risk_quant now reads), not 'current_vix'."""
    closes = list(np.linspace(20.0, 28.0, 70))  # >= 20 rows, simple ramp

    import pandas as pd
    df = pd.DataFrame({"Close": closes})

    def _fake_get_history(ticker, period=None):
        assert ticker == "^VIX"
        return df

    monkeypatch.setattr("services.data.fmp.get_history", _fake_get_history)
    out = qm.VIXStrategy.analyze()
    assert out is not None
    assert "vix" in out, "VIXStrategy must return 'vix' key"
    assert "current_vix" not in out, "key is 'vix' — risk_quant reads 'vix'"
    assert out["vix"] == pytest.approx(closes[-1], abs=0.1)


def test_r1_layer3_fires_when_vix_panic():
    """With a real VIX value above the panic threshold, Layer 3 triggers.
    Before R#1 vix was always None → L3 silent."""
    rds = RiskDefenseSystem()
    res = rds.check_all({
        "positions": [{"ticker": "AAPL", "weight": 1.0, "value": 1000}],
        "portfolio_value": 1000,
        "daily_return": 0.0,
        "vix": 40.0,  # >= vix_panic
        "regime": "TRANSITION",
        "returns_matrix": None,
    })
    assert "L3_VIX_PANIC" in res["layers_triggered"]


def test_r1_layer3_silent_when_vix_none():
    """Sanity: None vix (the OLD permanent state) → L3 must NOT fire,
    proving the fix is what makes L3 reachable, not the test harness."""
    rds = RiskDefenseSystem()
    res = rds.check_all({
        "positions": [{"ticker": "AAPL", "weight": 1.0, "value": 1000}],
        "portfolio_value": 1000,
        "daily_return": 0.0,
        "vix": None,
        "regime": "TRANSITION",
        "returns_matrix": None,
    })
    assert "L3_VIX_PANIC" not in res["layers_triggered"]
    assert "L3_VIX_CAUTION" not in res["layers_triggered"]


# ─────────────────────────────────────────────────────────────────────────────
# R#2 — regime not pinned to TRANSITION
# ─────────────────────────────────────────────────────────────────────────────

def test_r2_volatilityregime_has_no_detect():
    """The old code called VolatilityRegime.detect() which never existed.
    Pin that it still doesn't, and the analyze() it should use is present."""
    assert not hasattr(qm.VolatilityRegime, "detect")
    assert hasattr(qm.RegimeSwitching, "analyze")


def test_r2_regimeswitching_produces_bull_on_uptrend():
    """A clean upward series must classify as a bull regime (not TRANSITION),
    proving the regime input can now be non-TRANSITION."""
    # Strong, low-noise uptrend → high Sharpe → BULL/MILD_BULL
    closes = list(100.0 * np.exp(np.linspace(0, 0.30, 120)))
    out = qm.RegimeSwitching.analyze(closes)
    assert out is not None
    assert out["regime"] in ("BULL", "MILD_BULL")


def test_r2_regimeswitching_produces_bear_on_downtrend():
    closes = list(100.0 * np.exp(np.linspace(0, -0.30, 120)))
    out = qm.RegimeSwitching.analyze(closes)
    assert out is not None
    assert out["regime"] in ("BEAR", "MILD_BEAR")


# ─────────────────────────────────────────────────────────────────────────────
# R#3 — Layer 7 label matches SoT; PDF marks L7 failed when fired
# ─────────────────────────────────────────────────────────────────────────────

def test_r3_layer_labels_match_risk_defense_sot():
    """Every code in risk_board_service._LAYER_LABELS must be a label that
    risk_defense.py actually appends (L3 panic merges into caution)."""
    sot = {
        "L1_VAR", "L2_CORRELATION", "L3_VIX_PANIC", "L3_VIX_CAUTION",
        "L4_TAIL_RISK", "L5_DAILY_LOSS", "L6_SECTOR_CONCENTRATION",
        "L7_CASH_MGMT",
    }
    for code, _label in rb._LAYER_LABELS:
        assert code in sot, f"label '{code}' not appended by risk_defense"
    # L7 specifically must be the CASH_MGMT code (the bug), not L7_REGIME.
    codes = {c for c, _ in rb._LAYER_LABELS}
    assert "L7_CASH_MGMT" in codes
    assert "L7_REGIME" not in codes


def test_r3_layer7_marked_failed_when_fired():
    """When risk_defense fires L7_CASH_MGMT, the PDF layer table must show it
    as NOT passed. Before R#3 the lookup key never matched → always passed."""
    rows = rb._layer_table({"layers_triggered": ["L7_CASH_MGMT"]})
    l7 = next(r for r in rows if r["code"] == "L7_CASH_MGMT")
    assert l7["passed"] is False


def test_r3_layer7_passed_when_not_fired():
    rows = rb._layer_table({"layers_triggered": []})
    l7 = next(r for r in rows if r["code"] == "L7_CASH_MGMT")
    assert l7["passed"] is True


# ─────────────────────────────────────────────────────────────────────────────
# R#4 — tail-ratio BREACH reachable
# ─────────────────────────────────────────────────────────────────────────────

def _tail_status(svc, t):
    """Drive _to_v3_shape with only a tail_ratio and read the tail limit row."""
    data = {"tail_ratio": t}
    v3 = svc._to_v3_shape(data)
    row = next(r for r in v3["limits"] if r["name"] == "Tail ratio")
    return row["status_text"], row["fill_state"]


def test_r4_tail_ratio_breach_below_0_5():
    svc = rb.RiskBoardService()
    status, fill = _tail_status(svc, 0.3)
    assert status == "BREACH"
    assert fill == "breach"


def test_r4_tail_ratio_over_between_0_5_and_0_7():
    svc = rb.RiskBoardService()
    status, fill = _tail_status(svc, 0.6)
    assert status == "OVER"
    assert fill == "warn"


def test_r4_tail_ratio_ok_above_0_7():
    svc = rb.RiskBoardService()
    status, fill = _tail_status(svc, 1.0)
    assert status == "OK"
    assert fill == ""


# ─────────────────────────────────────────────────────────────────────────────
# R#5 — mixed-portfolio FX normalization in _fetch_position_returns
# ─────────────────────────────────────────────────────────────────────────────

class _Pos:
    def __init__(self, ticker, shares, avg_cost):
        self.ticker = ticker
        self.shares = shares
        self.avg_cost = avg_cost


def test_r5_mixed_portfolio_weights_fx_normalized(monkeypatch):
    """A US position and a KR position of equal *economic* value must end up
    with ~equal weights. Before R#5 the KRW raw value (~1300x larger) gave
    the KR holding ~100% weight, corrupting VaR/Sharpe/ES."""
    FX = 1300.0
    # _fetch_position_returns does `from services import fx_service`, so patch
    # the canonical module attribute.
    import services.fx_service as fxs
    monkeypatch.setattr(fxs, "get_rate", lambda: FX)

    # US: 10 shares @ $100 = $1000 → 1,300,000 KRW
    # KR: price 1,300,000 KRW, 1 share = 1,300,000 KRW  → equal economic value
    prices = {"AAPL": 100.0, "005930.KS": 1_300_000.0}

    def _fake_safe_price(t):
        return prices[t]

    # Deterministic returns so a matrix is built (need >= 10 closes).
    import pandas as pd
    rng = np.random.default_rng(3)

    def _fake_safe_history(t, period=None):
        base = prices[t]
        vals = base * np.cumprod(1 + rng.normal(0.0, 0.01, 80))
        return pd.DataFrame({"Close": vals})

    monkeypatch.setattr(rb, "_safe_price", _fake_safe_price)
    monkeypatch.setattr(rb, "_safe_history", _fake_safe_history)
    monkeypatch.setattr(rb, "_safe_snapshot", lambda t: {"sector": "Tech"})

    positions = [_Pos("AAPL", 10, 100.0), _Pos("005930.KS", 1, 1_300_000.0)]
    _tickers, pos_records, _matrix = rb._fetch_position_returns(positions)

    w = {p["ticker"]: p["weight"] for p in pos_records}
    assert w["AAPL"] == pytest.approx(0.5, abs=0.02), (
        f"US weight should be ~0.5 after FX, got {w['AAPL']}")
    assert w["005930.KS"] == pytest.approx(0.5, abs=0.02)
    # And the KRW-normalized values must be close, not 1300x apart.
    v = {p["ticker"]: p["value"] for p in pos_records}
    assert v["AAPL"] == pytest.approx(v["005930.KS"], rel=0.02)


# ─────────────────────────────────────────────────────────────────────────────
# R#6 — currency symbol follows portfolio_ccy
# ─────────────────────────────────────────────────────────────────────────────

def test_r6_krw_portfolio_uses_won_symbol():
    svc = rb.RiskBoardService()
    data = {
        "portfolio_ccy": "KRW",
        "portfolio_value": 100_000_000,
        "var99_pct": -3.0,
    }
    v3 = svc._to_v3_shape(data)
    assert "₩" in v3["stress_worst"]
    assert "$" not in v3["stress_worst"]


def test_r6_usd_portfolio_uses_dollar_symbol():
    svc = rb.RiskBoardService()
    data = {
        "portfolio_ccy": "USD",
        "portfolio_value": 100_000,
        "var99_pct": -3.0,
    }
    v3 = svc._to_v3_shape(data)
    assert "$" in v3["stress_worst"]
    assert "₩" not in v3["stress_worst"]
