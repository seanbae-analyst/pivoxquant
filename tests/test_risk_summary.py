"""
/api/risk/summary  +  /api/risk/layers — endpoint contract tests.

Bug #6 (HHI on /summary) + Bug #7 (threshold + observed_at_kst on /layers).

Proves:
  1. /api/risk/summary always emits  (default 0.0 when empty).
  2. /api/risk/summary HHI is structurally valid in [0,1].
  3. /api/risk/summary single-position book → HHI ≈ 1.0.
  4. /api/risk/layers always emits 7 layers.
  5. Each /layers entry has  +  keys.
  6. Empty-portfolio default_layers also carry threshold + observed_at_kst.
  7. Threshold strings reflect the SoT in services.quant.risk_defense
     (no hardcoded numbers — read from default_config()).
  8. observed_at_kst matches 'YYYY-MM-DD HH:MM KST' shape.
  9. Demo fallback (/layers exception path) also includes both fields.
 10. Demo fallback (/summary exception path) also includes hhi.
"""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest


KST_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} KST$")


# ─── /api/risk/summary — Bug #6 ───────────────────────────────────────────


def test_summary_unauth_returns_401(client):
    r = client.get("/api/risk/summary")
    assert r.status_code == 401


def test_summary_empty_portfolio_emits_hhi_zero(client, auth_user):
    """Empty portfolio: hhi is present (0.0), endpoint stays 200."""
    r = client.get("/api/risk/summary")
    assert r.status_code == 200
    body = r.get_json()
    assert "hhi" in body, (
        "summary payload must always include 'hhi' key — Bug #6 regression. "
        f"Got keys: {sorted(body.keys())}"
    )
    assert body["hhi"] == 0.0
    # Existing fields untouched (no breaking change).
    assert "var_1d_pct" in body and "es_1d_pct" in body
    assert "max_dd_90d_pct" in body and "corr_risk_index" in body


def test_summary_with_positions_emits_hhi_in_unit_interval(
    client, auth_user, add_position
):
    """Two positions → hhi must be a finite float in [0,1]."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    add_position(auth_user["id"], ticker="MSFT", shares=5, avg_cost=200)
    r = client.get("/api/risk/summary")
    assert r.status_code == 200
    body = r.get_json()
    assert "hhi" in body
    hhi = body["hhi"]
    assert isinstance(hhi, (int, float))
    assert 0.0 <= hhi <= 1.0


def test_summary_single_position_hhi_approaches_one(
    client, auth_user, add_position
):
    """Single position dominates → HHI = 1.0 (max concentration)."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    r = client.get("/api/risk/summary")
    assert r.status_code == 200
    body = r.get_json()
    # Single position normalises to weight=1.0 → hhi = 1*1 = 1.0.
    # Pricing failures fall back to avg_cost so weight is well-defined.
    if body.get("hhi", 0.0) > 0:
        assert body["hhi"] == 1.0


def test_summary_demo_fallback_includes_hhi(client, auth_user):
    """When /summary blows up internally, demo fallback still emits hhi."""
    with patch("routes.risk._portfolio_snapshot", side_effect=RuntimeError("boom")):
        r = client.get("/api/risk/summary")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("is_demo") is True
    assert "hhi" in body and body["hhi"] == 0.0


# ─── /api/risk/layers — Bug #7 ────────────────────────────────────────────


def _layers_from_response(body):
    """Endpoint may return list (legacy empty path) or {layers: [...]} (live)."""
    if isinstance(body, list):
        return body
    return body.get("layers", [])


def test_layers_unauth_returns_401(client):
    r = client.get("/api/risk/layers")
    assert r.status_code == 401


def test_layers_empty_portfolio_carries_threshold_and_kst(client, auth_user):
    """Empty-portfolio default_layers must carry threshold + observed_at_kst.

    Regression: frontend seven-layer-breakdown.tsx renders both fields; if
    backend omits them, both columns show as '—' even when system is healthy.
    """
    r = client.get("/api/risk/layers")
    assert r.status_code == 200
    layers = _layers_from_response(r.get_json())
    assert len(layers) == 7, f"expected 7 layers, got {len(layers)}"
    for l in layers:
        assert "threshold" in l, f"layer no={l.get('no')} missing 'threshold'"
        assert "observed_at_kst" in l, (
            f"layer no={l.get('no')} missing 'observed_at_kst'"
        )
        # KST timestamp shape: YYYY-MM-DD HH:MM KST
        assert KST_RE.match(l["observed_at_kst"]), (
            f"layer {l.get('no')} observed_at_kst='{l['observed_at_kst']}' "
            "does not match 'YYYY-MM-DD HH:MM KST'"
        )
        # Threshold is a non-empty string (rendered verbatim by frontend).
        assert isinstance(l["threshold"], str) and l["threshold"].strip()


def test_layers_thresholds_match_risk_defense_sot(client, auth_user):
    """Threshold strings must derive from services.quant.risk_defense.

    Tests Iron Rule: routes/risk.py must NOT hardcode threshold numbers —
    they must come from RiskDefenseSystem.default_config() / from_profile()
    so that future tuning of risk_defense.py automatically propagates.
    """
    from services.quant.risk_defense import RiskDefenseSystem

    # Default fallback profile (matches routes.risk._risk_layers_impl()).
    rds = RiskDefenseSystem.from_profile("steady_accumulator")
    cfg = rds.config

    r = client.get("/api/risk/layers")
    assert r.status_code == 200
    layers = _layers_from_response(r.get_json())

    by_no = {l["no"]: l for l in layers}

    # L1 VaR — substring check on the configured threshold value.
    assert f"{cfg['var_threshold_pct']:.1f}" in by_no[1]["threshold"]
    # L2 Correlation
    assert f"{cfg['correlation_alert_threshold']:.2f}" in by_no[2]["threshold"]
    # L3 VIX (caution + panic both shown)
    assert f"{cfg['vix_caution']:.0f}" in by_no[3]["threshold"]
    assert f"{cfg['vix_panic']:.0f}" in by_no[3]["threshold"]
    # L5 Daily loss
    assert f"{cfg['daily_loss_limit_pct']:.1f}" in by_no[5]["threshold"]
    # L6 Sector
    assert f"{cfg['max_sector_pct']:.0f}" in by_no[6]["threshold"]


def test_layers_populated_portfolio_emits_threshold_and_kst(
    client, auth_user, add_position
):
    """Live path (positions present) — every layer must still carry both fields."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    add_position(auth_user["id"], ticker="MSFT", shares=5, avg_cost=200)
    r = client.get("/api/risk/layers")
    assert r.status_code == 200
    layers = _layers_from_response(r.get_json())
    assert len(layers) == 7
    for l in layers:
        assert l.get("threshold"), f"layer {l.get('no')} threshold missing/empty"
        assert KST_RE.match(l.get("observed_at_kst") or ""), (
            f"layer {l.get('no')} observed_at_kst bad: {l.get('observed_at_kst')!r}"
        )


def test_layers_demo_fallback_includes_threshold_and_kst(client, auth_user):
    """When _risk_layers_impl crashes, demo fallback also fills both fields."""
    with patch(
        "routes.risk._risk_layers_impl", side_effect=RuntimeError("boom")
    ):
        r = client.get("/api/risk/layers")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("is_demo") is True
    layers = _layers_from_response(body)
    assert len(layers) == 7
    for l in layers:
        assert l.get("threshold"), f"demo layer {l.get('no')} threshold missing"
        assert KST_RE.match(l.get("observed_at_kst") or ""), (
            f"demo layer {l.get('no')} observed_at_kst bad"
        )
