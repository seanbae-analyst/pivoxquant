"""Regression guard — React preview-shape adapters in routes/artifacts.py.

Context (2026-05-31): after the fake-data removal (448ebb04), real-position
users saw `render_error` EmptyState on the React kpi-dashboard preview because
the persisted `Artifact.data_json` is raw snake_case while the React
`KpiDashboardData` interface is camelCase + nested. The preview shell cast the
raw blob to the wrong shape → undefined fields → template throw → render_error.

`_kpi_dashboard_preview_shape` converts the raw payload into the React shape
for the LIST endpoint's `data_preview` field, WITHOUT mutating `data_json`.

These tests lock in:
  1. The adapter emits the exact camelCase keys the .tsx interface dereferences,
     filled with REAL values from the raw payload.
  2. The intentionally-deferred arrays stay EMPTY (no fabricated rows).
  3. Missing metrics degrade to honest "—" (never fabricated samples).
  4. `data_json` is never mutated by the adapter.
  5. risk_board / monthly_finance are wired (option-b, 2026-05-31): their React
     interfaces were reduced to the fields the backend actually computes, and
     the shapers supply only those — backend-uncomputed surfaces (risk_board
     `beta`; monthly_finance P&L/balance-sheet/cash-flow) are neither emitted
     nor fabricated.
"""
from __future__ import annotations

from routes.artifacts import (
    _kpi_dashboard_preview_shape,
    _monthly_finance_preview_shape,
    _preview_shape_for,
    _risk_board_preview_shape,
    _PREVIEW_SHAPERS,
)


# The exact set of fields kpi-dashboard.tsx dereferences off `data` (camelCase).
# If the template grows a new required field, this test should be updated in
# lockstep so the adapter never silently under-supplies and re-introduces
# render_error.
_KPI_REQUIRED_KEYS = {
    "doc", "navEom", "navEomDelta", "ytdReturn", "ytdDelta",
    "sharpe", "sharpeDelta", "status", "statusDelta", "issued",
    "scorecard", "decisions", "decisionCards",
}


def _real_kpi_payload() -> dict:
    """Raw kpi_dashboard data_json for a user WITH real positions."""
    return {
        "user_id": 7,
        "user_name": "Tester",
        "as_of": "2026-05-31",
        "generated_at": "2026-05-31T00:00:00Z",
        "portfolio_value": 1_234_567.0,
        "portfolio_ccy": "USD",
        "ytd_return_pct": 12.4,
        "sharpe_annual": 1.83,
        "max_drawdown_pct": -8.1,
        "turnover_ratio": 0.22,
        "cash_pct": 0.15,
        "position_count": 9,
        "disclaimer": "정보 제공 목적이며 투자 권유가 아닙니다.",
    }


def test_kpi_shape_emits_all_required_camelcase_keys():
    out = _kpi_dashboard_preview_shape(_real_kpi_payload())
    assert _KPI_REQUIRED_KEYS.issubset(out.keys()), (
        f"missing keys: {_KPI_REQUIRED_KEYS - set(out.keys())}"
    )


def test_kpi_shape_fills_real_values_not_emdash():
    out = _kpi_dashboard_preview_shape(_real_kpi_payload())
    # Real position data → real values (the whole point of the fix).
    assert out["navEom"] == "$1.23M"
    assert out["ytdReturn"] == "+12.4%"
    assert out["sharpe"] == "1.83"
    assert out["coverMonth"] == "2026-05"
    assert out["issued"].startswith("Issued ·")
    # None of the populated metrics collapsed to em-dash.
    for k in ("navEom", "ytdReturn", "sharpe"):
        assert out[k] != "—", f"{k} should be a real value"


def test_kpi_shape_krw_currency_prefix():
    payload = _real_kpi_payload()
    payload["portfolio_ccy"] = "KRW"
    out = _kpi_dashboard_preview_shape(payload)
    assert out["navEom"].startswith("₩"), out["navEom"]


def test_kpi_shape_deferred_arrays_stay_empty():
    """scorecard/decisions/decisionCards are a separate sprint — must be []
    (never fabricated). Template `.map()`s them, so [] renders cleanly."""
    out = _kpi_dashboard_preview_shape(_real_kpi_payload())
    assert out["scorecard"] == []
    assert out["decisions"] == []
    assert out["decisionCards"] == []


def test_kpi_shape_missing_metrics_degrade_to_emdash_not_fake():
    """Empty/partial payload → honest em-dash, never a sample number."""
    out = _kpi_dashboard_preview_shape({"as_of": "2026-05-31"})
    assert out["navEom"] == "—"
    assert out["ytdReturn"] == "—"
    assert out["sharpe"] == "—"
    # Still structurally complete so the template never throws.
    assert _KPI_REQUIRED_KEYS.issubset(out.keys())
    assert out["scorecard"] == []


def test_kpi_shape_does_not_mutate_input():
    payload = _real_kpi_payload()
    snapshot = dict(payload)
    _kpi_dashboard_preview_shape(payload)
    assert payload == snapshot, "adapter must not mutate the raw data_json"


def test_preview_shape_for_dispatches_kpi():
    out = _preview_shape_for("kpi_dashboard", _real_kpi_payload())
    assert out is not None
    assert out["navEom"] == "$1.23M"


# ─────────────────────────── risk_board ────────────────────────────────────

# camelCase keys risk-board.tsx dereferences without a guard. `beta` is GONE
# (backend never computes a portfolio beta — dropped, not faked). pairwiseCorr
# is optional (the template elides the card when absent).
_RISK_BOARD_REQUIRED_KEYS = {"weekTag", "asOfStamp", "var95", "maxDD", "sharpe", "vix"}


def _real_risk_board_payload() -> dict:
    """Raw risk_board data_json for a user WITH real positions."""
    return {
        "user_id": 7,
        "period_label": "May 2026",
        "trigger": "monthly",
        "portfolio_value": 1_234_567.0,
        "portfolio_ccy": "USD",
        "var95_pct": 2.7,
        "var99_pct": 4.1,
        "sharpe_annual": 1.42,
        "max_drawdown_pct": -8.3,
        "vix_current": 18.6,
        "defense_status": "GREEN",
        "sector_breakdown": [
            {"sector": "Technology", "weight_pct": 42.0},
            {"sector": "Financials", "weight_pct": 18.0},
        ],
    }


def test_risk_board_shape_emits_required_keys_with_real_values():
    out = _risk_board_preview_shape(_real_risk_board_payload())
    assert _RISK_BOARD_REQUIRED_KEYS.issubset(out.keys()), (
        f"missing keys: {_RISK_BOARD_REQUIRED_KEYS - set(out.keys())}"
    )
    # `beta` must NOT be emitted — it was dropped from the interface.
    assert "beta" not in out
    # Real metrics → real values, signed/percent-formatted.
    assert out["var95"]["value"] == "-2.7%"
    assert out["sharpe"]["value"] == "1.42"
    assert out["maxDD"]["value"] == "-8.3%"
    assert out["vix"]["value"] == "18.6"
    # Tones are valid heat enums.
    for k in ("var95", "maxDD", "sharpe", "vix"):
        assert out[k]["tone"] in {"green", "amber", "red"}


def test_risk_board_shape_pairwise_corr_from_sectors():
    out = _risk_board_preview_shape(_real_risk_board_payload())
    assert "pairwiseCorr" in out
    # top_w 0.42 → 0.10 + 0.42*1.10 = 0.562
    assert out["pairwiseCorr"]["value"] == "0.56"
    assert 0 <= out["pairwiseCorr"]["gauge"] <= 100


def test_risk_board_shape_no_sectors_elides_corr():
    payload = _real_risk_board_payload()
    payload["sector_breakdown"] = []
    out = _risk_board_preview_shape(payload)
    # No sector data → no fabricated correlation; template elides the card.
    assert "pairwiseCorr" not in out


def test_risk_board_shape_missing_metrics_degrade_to_emdash():
    out = _risk_board_preview_shape({"period_label": "May 2026"})
    assert out["var95"]["value"] == "—"
    assert out["sharpe"]["value"] == "—"
    assert out["maxDD"]["value"] == "—"
    assert out["vix"]["value"] == "—"
    assert _RISK_BOARD_REQUIRED_KEYS.issubset(out.keys())


def test_risk_board_shape_does_not_mutate_input():
    payload = _real_risk_board_payload()
    snapshot = {k: (list(v) if isinstance(v, list) else v) for k, v in payload.items()}
    _risk_board_preview_shape(payload)
    assert payload == snapshot, "adapter must not mutate the raw data_json"


# ───────────────────────── monthly_finance ─────────────────────────────────

# camelCase keys monthly-finance.tsx dereferences without a guard. The P&L /
# balance-sheet / cash-flow fields (income/bsAssets/liabilities/cashFlow/etc)
# are GONE (backend never computes them — removed, not faked).
_MONTHLY_REQUIRED_KEYS = {"doc", "asOf", "issued", "navEom", "costRows", "taxRows"}


def _real_monthly_payload() -> dict:
    """Raw monthly_finance data_json for a user WITH real cash/trades."""
    return {
        "user_id": 7,
        "month_label": "2026-04",
        "generated_at": "2026-05-01T00:00:00Z",
        "period_end": "2026-04-30",
        "cash": {"total_krw": 5_000_000.0, "total_usd": 3_600.0},
        "positions_mv": {"total_krw": 20_000_000.0},
        "liquidity_ratio": 0.2,
        "runway_months": 8.5,
        "cost_breakdown": {
            "us_commission_usd": 12.5,
            "kr_commission_krw": 30_000.0,
            "kr_transaction_tax_krw": 40_000.0,
            "fx_spread_krw": 50_000.0,
            "total_krw": 137_000.0,
        },
        "tax_estimate": {
            "us_capital_gains_krw": 220_000.0,
            "dividend_withholding_krw": 15_400.0,
            "total_estimated_krw": 235_400.0,
        },
    }


def test_monthly_shape_emits_required_keys():
    out = _monthly_finance_preview_shape(_real_monthly_payload())
    assert _MONTHLY_REQUIRED_KEYS.issubset(out.keys()), (
        f"missing keys: {_MONTHLY_REQUIRED_KEYS - set(out.keys())}"
    )
    # The removed corporate-statement fields must NOT be emitted.
    for gone in ("income", "totalNetPnl", "bsAssets", "liabilities",
                 "cashFlow", "netCashChange", "ratios", "liquidityTiers",
                 "monthReturn", "ytdReturn", "netPnlMtd", "alphaVsBench"):
        assert gone not in out, f"{gone} must not be fabricated"


def test_monthly_shape_real_nav_and_kpis():
    out = _monthly_finance_preview_shape(_real_monthly_payload())
    # NAV = cash 5M + MV 20M = 25M KRW.
    assert out["navEom"] == "₩25.00M"
    assert out["navEomKpi"]["value"] == "₩25.00M"
    assert out["cashKpi"]["value"] == "₩5.00M"
    assert out["liquidityKpi"]["value"] == "0.20"
    assert out["runwayKpi"]["value"] == "8.5"
    assert out["coverMonth"] == "2026-04"


def test_monthly_shape_cost_and_tax_rows_real_nonzero():
    out = _monthly_finance_preview_shape(_real_monthly_payload())
    cost_labels = {r["label"] for r in out["costRows"]}
    assert "Transaction Tax (KR)" in cost_labels
    assert "Total Cost" in cost_labels
    tax_labels = {r["label"] for r in out["taxRows"]}
    assert "US Capital Gains (est)" in tax_labels
    # Each emitted row carries a formatted amount, never blank.
    for r in out["costRows"] + out["taxRows"]:
        assert r["amount"] not in ("", "—")


def test_monthly_shape_zero_ledger_emits_no_rows():
    """A user with no trades → empty cost/tax ledgers (no zero-value rows)."""
    payload = _real_monthly_payload()
    payload["cost_breakdown"] = {"total_krw": 0.0}
    payload["tax_estimate"] = {"total_estimated_krw": 0.0}
    out = _monthly_finance_preview_shape(payload)
    assert out["costRows"] == []
    assert out["taxRows"] == []
    # Template `.map()`s empty arrays cleanly.


def test_monthly_shape_missing_metrics_elide_kpis():
    out = _monthly_finance_preview_shape({"month_label": "2026-04"})
    assert out["navEom"] == "—"
    # No cash/mv/liquidity/runway → those KPI cards are omitted, not faked.
    assert "navEomKpi" not in out
    assert "cashKpi" not in out
    assert "liquidityKpi" not in out
    assert "runwayKpi" not in out
    assert out["costRows"] == []
    assert out["taxRows"] == []
    assert _MONTHLY_REQUIRED_KEYS.issubset(out.keys())


def test_monthly_shape_does_not_mutate_input():
    payload = _real_monthly_payload()
    import copy
    snapshot = copy.deepcopy(payload)
    _monthly_finance_preview_shape(payload)
    assert payload == snapshot, "adapter must not mutate the raw data_json"


def test_preview_shape_for_dispatches_risk_board_and_monthly():
    rb = _preview_shape_for("risk_board", _real_risk_board_payload())
    assert rb is not None and rb["var95"]["value"] == "-2.7%"
    mf = _preview_shape_for("monthly_finance", _real_monthly_payload())
    assert mf is not None and mf["navEom"] == "₩25.00M"
    assert "risk_board" in _PREVIEW_SHAPERS
    assert "monthly_finance" in _PREVIEW_SHAPERS


def test_preview_shape_for_isolates_adapter_exceptions():
    """A shaper raising must not bubble — returns None so the list response
    survives (per-row isolation)."""
    def _boom(_data):
        raise RuntimeError("kaboom")

    _PREVIEW_SHAPERS["__test_boom__"] = _boom
    try:
        assert _preview_shape_for("__test_boom__", {}) is None
    finally:
        _PREVIEW_SHAPERS.pop("__test_boom__", None)
