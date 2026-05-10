"""
/api/risk/layers — Layer 7 (Cash Buffer) regression tests.

B-05 (2026-05-10 bug-hunter wave): Layer 7 was hardcoded
  cash_w_pct = 0.0  +  status = "GREEN"
so a 0% cash position always reported "Cash buffer observed." (GREEN). This
masked the very risk the layer is supposed to surface.

This suite proves:
  1. Layer 7 status is computed from cash_w_pct vs RiskDefenseSystem config
     (bull_cash_pct as the GREEN threshold — SoT) — no hardcoded "GREEN".
  2. cash 0% (no broker / fetch failure) → RED + neutral observation.
  3. cash 3% (intermediate, default bull=5%) → YELLOW.
  4. cash 10% → GREEN.
  5. Broker fetch failure (Alpaca + KIS both raise) falls back to RED, NOT
     GREEN — fixes the original bug.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ─── Pure helper unit tests (no Flask) ────────────────────────────────────


def test_cash_buffer_status_green_at_threshold():
    """At exactly bull_cash_pct → GREEN (inclusive)."""
    from routes.risk import _cash_buffer_status
    cfg = {"bull_cash_pct": 5}
    assert _cash_buffer_status(5.0, cfg) == "GREEN"
    assert _cash_buffer_status(10.0, cfg) == "GREEN"
    assert _cash_buffer_status(99.0, cfg) == "GREEN"


def test_cash_buffer_status_yellow_band():
    """In [yellow_floor, green_threshold) → YELLOW."""
    from routes.risk import _cash_buffer_status
    cfg = {"bull_cash_pct": 5}
    # green_th=5, yellow_th=max(2, 2.5)=2.5. So 4% in YELLOW band.
    assert _cash_buffer_status(4.0, cfg) == "YELLOW"
    assert _cash_buffer_status(2.5, cfg) == "YELLOW"


def test_cash_buffer_status_red_below_floor():
    """Below YELLOW floor → RED — including 0% (B-05 root case)."""
    from routes.risk import _cash_buffer_status
    cfg = {"bull_cash_pct": 5}
    assert _cash_buffer_status(0.0, cfg) == "RED"
    assert _cash_buffer_status(1.0, cfg) == "RED"
    assert _cash_buffer_status(2.0, cfg) == "RED"  # below 2.5 floor


def test_cash_buffer_status_uses_profile_config():
    """Defensive profile (bull=10%) shifts both bands up — no hardcoded floors."""
    from routes.risk import _cash_buffer_status
    cfg = {"bull_cash_pct": 10}
    assert _cash_buffer_status(10.0, cfg) == "GREEN"
    assert _cash_buffer_status(7.0, cfg) == "YELLOW"  # in [5, 10)
    assert _cash_buffer_status(4.0, cfg) == "RED"     # below 5 floor


def test_cash_buffer_observation_no_broker_neutral():
    """source='none' → neutral message (not pretending we observed buffer)."""
    from routes.risk import _cash_buffer_observation
    cfg = {"bull_cash_pct": 5}
    obs = _cash_buffer_observation(0.0, cfg, "none")
    assert "no broker" in obs.lower() or "not observable" in obs.lower()


def test_cash_buffer_observation_uses_status_text():
    """RED/YELLOW/GREEN map to distinct neutral observation strings."""
    from routes.risk import _cash_buffer_observation
    cfg = {"bull_cash_pct": 5}
    red_obs = _cash_buffer_observation(0.0, cfg, "alpaca")
    yellow_obs = _cash_buffer_observation(3.0, cfg, "alpaca")
    green_obs = _cash_buffer_observation(10.0, cfg, "alpaca")
    assert red_obs != yellow_obs
    assert yellow_obs != green_obs
    # No advice language — observational only
    for obs in (red_obs, yellow_obs, green_obs):
        for banned in ("recommend", "advise", " buy ", " sell "):
            assert banned not in obs.lower(), f"Observation has banned word: {obs!r}"


# ─── /api/risk/layers Layer 7 — endpoint integration ──────────────────────


def _layer7(body):
    """Pull layer no=7 from a /layers response (live or default shape)."""
    layers = body if isinstance(body, list) else body.get("layers", [])
    for l in layers:
        if l.get("no") == 7:
            return l
    return None


def test_layer7_no_broker_zero_cash_returns_red(client, auth_user, add_position):
    """B-05 root case: positions present, no broker → cash=0 → RED, NOT GREEN.

    This is the exact regression the bug-hunter flagged: the layer used to
    return GREEN regardless of cash buffer.
    """
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    # No broker mock — UserAlpacaService / UserKISService both raise on
    # construction (no BrokerConnection in test DB), so cash defaults to 0.
    r = client.get("/api/risk/layers")
    assert r.status_code == 200
    layer7 = _layer7(r.get_json())
    assert layer7 is not None, "Layer 7 missing from response"
    # cash_w_pct = 0 → status must be RED (was GREEN pre-fix)
    assert layer7["status"] == "RED", (
        f"Expected RED (cash=0%, no broker), got {layer7['status']}. "
        "Pre-fix bug B-05: hardcoded GREEN regardless of cash."
    )
    assert "0%" in layer7["metric_value"]


def test_layer7_threshold_string_uses_sot(client, auth_user, add_position):
    """Layer 7 threshold rendered from RiskDefenseSystem.config — no hardcoding."""
    from services.quant.risk_defense import RiskDefenseSystem
    rds = RiskDefenseSystem.from_profile("steady_accumulator")
    cfg = rds.config

    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    r = client.get("/api/risk/layers")
    layer7 = _layer7(r.get_json())
    assert layer7 is not None
    # Threshold string must include bull_cash_pct value from config.
    assert f"{cfg['bull_cash_pct']:.0f}" in layer7["threshold"]


def test_layer7_observation_no_advice_language(client, auth_user, add_position):
    """Layer 7 observation is neutral — no recommend/advise wording."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    r = client.get("/api/risk/layers")
    layer7 = _layer7(r.get_json())
    assert layer7 is not None
    obs = (layer7.get("observation") or "").lower()
    for banned in ("recommend", "advise", "should buy", "should sell"):
        assert banned not in obs, f"Layer 7 observation has banned word '{banned}': {obs!r}"


def test_layer7_broker_fetch_failure_falls_back_to_red(
    client, auth_user, add_position
):
    """If both Alpaca and KIS raise, source='none' and status is RED — never GREEN.

    Pre-fix B-05 would have returned GREEN here because the status was
    literally hardcoded. Post-fix the absence of broker data is treated as
    "no buffer observable → conservative RED".
    """
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)

    def _raise(*a, **kw):
        raise RuntimeError("broker offline")

    with patch(
        "services.broker.user_alpaca_service.UserAlpacaService",
        side_effect=_raise,
    ), patch(
        "services.broker.user_kis_service.UserKISService",
        side_effect=_raise,
    ):
        r = client.get("/api/risk/layers")
    assert r.status_code == 200
    layer7 = _layer7(r.get_json())
    assert layer7 is not None
    assert layer7["status"] == "RED", (
        f"Broker fetch failure must fall back to RED, got {layer7['status']}. "
        "Otherwise the original B-05 hardcoded-GREEN bug is reintroduced."
    )
