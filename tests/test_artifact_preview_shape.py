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
  5. risk_board / monthly_finance are NOT shaped here (their React interfaces
     require fields the backend does not compute; partial shapes would still
     throw). The whitelist fallback path must keep working for them.
"""
from __future__ import annotations

from routes.artifacts import (
    _kpi_dashboard_preview_shape,
    _preview_shape_for,
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


def test_preview_shape_for_returns_none_for_unwired_types():
    """risk_board / monthly_finance have NO adapter — their React interfaces
    require backend-uncomputed fields (risk_board.beta; monthly P&L/BS/CF),
    so a partial shape would still throw render_error. They must fall through
    to the legacy whitelist (None here), not get a fabricated camelCase blob."""
    assert "risk_board" not in _PREVIEW_SHAPERS
    assert "monthly_finance" not in _PREVIEW_SHAPERS
    assert _preview_shape_for("risk_board", {"period_label": "May 2026"}) is None
    assert _preview_shape_for("monthly_finance", {"month_label": "May 2026"}) is None


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
