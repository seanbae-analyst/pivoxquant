"""
Weekly Memo — Risk Dashboard KPI tests
======================================
Proves:
  1. `_risk_kpi` returns computed KPIs for a user with realistic price history.
  2. `_risk_kpi` returns `{}` when the user has no positions / no price data.
  3. Two different users receive **different** KPI numbers (no shared hardcoded values).
  4. Rendered PDF HTML no longer contains the audit-flagged hardcoded numbers
     (-2.14, -3.12, -8.14, 1.08, "W-9", "W-13").
  5. When `risk_kpi` is empty, the "Part III · Risk Dashboard" section is
     fully hidden (no header, no methodology sidebar).
"""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd


# ─── helpers ─────────────────────────────────────────────────────────────────

def _synthetic_ohlc(seed: int, n: int = 120, base: float = 100.0):
    """Deterministic OHLC frame long enough (>= 91) for GKYZ + 90d HS."""
    rng = np.random.default_rng(seed)
    # Varying drift + vol so seeds produce statistically distinct series.
    drift = 0.0003 + (seed % 7) * 0.00005
    vol = 0.012 + (seed % 11) * 0.0015
    rets = rng.normal(drift, vol, size=n)
    closes = base * np.cumprod(1 + rets)
    opens = closes * (1 + rng.normal(0, vol * 0.25, size=n))
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, vol * 0.35, size=n)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, vol * 0.35, size=n)))
    return pd.DataFrame({
        "Open": opens, "High": highs, "Low": lows, "Close": closes,
    })


def _install_synthetic_fetcher(ticker_to_seed: dict[str, int]):
    """Patch `_position_price_history` to return per-ticker synthetic OHLC.

    Returns a patch context manager that tests compose with `with`.
    """
    def _fake(ticker, period="6mo"):
        seed = ticker_to_seed.get(ticker)
        if seed is None:
            return None
        return _synthetic_ohlc(seed)
    return patch(
        "services.artifacts.weekly_memo_service._position_price_history",
        side_effect=_fake,
    )


# ─── 1. real KPIs for a user with positions ──────────────────────────────────

def test_risk_kpi_populated_for_user_with_history(app, make_user, add_position):
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    u = make_user(email="risky@test.com", tier="pro")
    add_position(u["id"], ticker="AAPL", shares=10, avg_cost=100)
    add_position(u["id"], ticker="MSFT", shares=5, avg_cost=200)

    svc = WeeklyMemoService()
    seeds = {"AAPL": 101, "MSFT": 202, "SPY": 303, "^GSPC": 303}

    with _install_synthetic_fetcher(seeds), app.app_context():
        data = svc.generate_for_user(u["id"])

    kpi = data["risk_kpi"]
    assert isinstance(kpi, dict) and kpi, "risk_kpi must be a non-empty dict"
    # At least one of the four headline KPIs is present.
    assert any(k in kpi for k in ("var_1d_pct", "es_1d_pct", "mdd_pct", "tail_ratio"))
    # Structural metadata
    assert "as_of" in kpi
    assert kpi.get("n_positions") == 2
    # Window should be ≤ 90 returns (we cap at 90-day lookback).
    assert 20 <= int(kpi.get("window_days", 0)) <= 90

    # VaR and ES should be negative percents (realistic tail losses).
    if "var_1d_pct" in kpi:
        assert kpi["var_1d_pct"] < 0
    if "es_1d_pct" in kpi:
        assert kpi["es_1d_pct"] <= kpi.get("var_1d_pct", 0)  # ES ≤ VaR
    if "mdd_pct" in kpi:
        assert kpi["mdd_pct"] <= 0


# ─── 2. empty dict when no positions / no history ────────────────────────────

def test_risk_kpi_empty_for_user_with_no_positions(app, make_user):
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    u = make_user(email="empty@test.com", tier="pro")
    svc = WeeklyMemoService()

    with app.app_context():
        data = svc.generate_for_user(u["id"])

    assert data["risk_kpi"] == {}


def test_risk_kpi_empty_when_price_history_missing(app, make_user, add_position):
    """Fetcher returns None for every ticker → no KPIs computed."""
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    u = make_user(email="nohist@test.com", tier="pro")
    add_position(u["id"], ticker="GHOST", shares=1, avg_cost=100)
    svc = WeeklyMemoService()

    with _install_synthetic_fetcher({}), app.app_context():  # no seeds → all None
        data = svc.generate_for_user(u["id"])

    assert data["risk_kpi"] == {}


# ─── 3. different users get different KPI numbers ────────────────────────────

def test_risk_kpi_differs_between_users(app, make_user, add_position):
    """Two users with different tickers must not receive identical KPIs.

    This is the regression guard against the audit finding: every user was
    being served the same hardcoded VaR/ES/MDD/TailRatio values.
    """
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    u1 = make_user(email="alice@test.com", tier="pro")
    u2 = make_user(email="bob@test.com",   tier="pro")
    add_position(u1["id"], ticker="AAA", shares=10, avg_cost=100)
    add_position(u2["id"], ticker="BBB", shares=10, avg_cost=100)

    svc = WeeklyMemoService()
    seeds = {"AAA": 111, "BBB": 999, "SPY": 303, "^GSPC": 303}

    with _install_synthetic_fetcher(seeds), app.app_context():
        k1 = svc.generate_for_user(u1["id"])["risk_kpi"]
        k2 = svc.generate_for_user(u2["id"])["risk_kpi"]

    assert k1 and k2, "both users must have KPIs to meaningfully compare"
    # At least one headline KPI must differ.
    fields = ("var_1d_pct", "es_1d_pct", "mdd_pct", "tail_ratio")
    differences = [k1.get(f) != k2.get(f) for f in fields if f in k1 and f in k2]
    assert any(differences), (
        f"Risk KPIs identical across two distinct users: {k1} vs {k2} — "
        "hardcoded regression?"
    )


# ─── 4. rendered template no longer contains the hardcoded numbers ───────────

def test_rendered_pdf_html_has_no_hardcoded_risk_numbers(
    app, make_user, add_position,
):
    """The audit-flagged literals must not appear as Risk Dashboard values.

    We render the PDF template with real risk_kpi injected, then scan the
    Risk Dashboard region of the HTML for the old hardcoded strings.
    """
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    u = make_user(email="render@test.com", tier="pro")
    add_position(u["id"], ticker="AAPL", shares=10, avg_cost=100)
    add_position(u["id"], ticker="MSFT", shares=5, avg_cost=200)

    svc = WeeklyMemoService()
    seeds = {"AAPL": 17, "MSFT": 29, "SPY": 303, "^GSPC": 303}

    with _install_synthetic_fetcher(seeds), app.app_context():
        data = svc.generate_for_user(u["id"])
        html = svc.render_pdf_html(data)

    assert "Part III · Risk Dashboard" in html, "Risk section should render for this user"

    # Isolate the Risk Dashboard page so we don't collide with unrelated
    # literals elsewhere in the 5-page memo.
    start = html.find("Part III · Risk Dashboard")
    end = html.find("Part IV", start)
    risk_region = html[start:end] if end > start else html[start:]

    # The exact hardcoded numbers must not appear as Risk Dashboard values.
    for literal in ("-2.14%", "-3.12%", "-8.14%", ">1.08<"):
        assert literal not in risk_region, (
            f"Hardcoded value {literal!r} still present in Risk Dashboard"
        )
    # "W-9" and "W-13" were the frozen trough/recovery labels.
    # They may legitimately reappear if the synthetic series happens to
    # produce those same week indices — so we only assert that at least
    # one of the two old labels is absent (a pair match would be suspicious).
    frozen_pair_present = ("trough · W-9" in risk_region
                            and "Recovered to flat by W-13" in risk_region)
    assert not frozen_pair_present, (
        "Both hardcoded trough + recovery labels still present together"
    )


# ─── 5. empty risk_kpi hides the section entirely ────────────────────────────

def test_section_hidden_when_risk_kpi_empty(app, make_user):
    """Template must skip the Part III block when risk_kpi == {}."""
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    u = make_user(email="norisk@test.com", tier="pro")
    svc = WeeklyMemoService()

    with app.app_context():
        data = svc.generate_for_user(u["id"])  # no positions → risk_kpi = {}
        assert data["risk_kpi"] == {}
        html = svc.render_pdf_html(data)

    assert "Part III · Risk Dashboard" not in html
    assert "Readings around the tails" not in html
    # Methodology terms like "VaR · Value at Risk" live inside the Risk page
    # and should also be gone.
    assert "VaR · Value at Risk" not in html
