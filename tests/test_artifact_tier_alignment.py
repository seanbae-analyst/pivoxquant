"""Pricing-page ↔ code tier alignment gate (B2, 2026-06-10).

The business-model audit (docs/strategy/business_model_audit_2026-06-10.md)
found NINE mismatches between what the pricing page sells per tier and what
the code actually gates: six artifacts advertised under Pro were
Premium-gated in both the cron fan-out and the on-demand routes, and three
advertised under Premium were Pro-gated. Had billing flipped on, the first
Pro subscriber would have been denied half the advertised artifacts
(표시광고법 §3 exposure).

Resolution direction (CEO order "다 진행해봐", 2026-06-11): the CODE was
aligned to the PRICING PAGE — honouring the advertised promise is the most
legally defensible direction, and billing is still gated off so revenue
impact today is zero. If the CEO re-cuts the tiers before launch, update
EXPECTED_TIER below together with frontend/src/app/pricing/page.tsx — this
test exists precisely so the four surfaces (pricing copy, cron fan-out,
on-demand gates, unified /generate _ARTIFACT_MIN_TIER) can never drift
apart silently again.

Deliberately ungated (absent from EXPECTED_TIER): brag_card / monthly_brag
(viral share loop) and sp500_backtest (universal observation record) are
free for every tier by design — see _ARTIFACT_MIN_TIER's comment. The
pricing page currently lists "Brag Card" under Premium and "S&P 500
Backtest" under Pro; whether to keep advertising free features as paid
perks is a CEO pricing-copy call (flagged in HANDOVER), not a code gate.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

# ── The expected tier per artifact — MUST match the pricing page ───────────
# frontend/src/app/pricing/page.tsx: Pro list (line ~97) / Premium list (~114).
# Keys are the service module basenames under services/artifacts/.
EXPECTED_TIER: dict[str, str] = {
    # Pro (₩9,900) — advertised "twelve Pro artifacts"
    "weekly_memo": "pro",            # "Weekly Memo (full)" — abridged is free
    "earnings_prebrief": "pro",
    "dd_checklist": "pro",
    "insider_mirror": "pro",
    "risk_board": "pro",
    "dividend_income": "pro",
    "quarterly_self_report": "pro",
    "self_audit": "pro",
    "portfolio_segment": "pro",
    # Premium (₩19,900)
    "capital_allocation": "premium",
    "credit_rating": "premium",
    "burn_rate": "premium",
    "monthly_finance": "premium",
    "kpi_dashboard": "premium",
    "year_end_letter": "premium",
}

_TIER_SET_NAME = {
    "pro": "PAID_TIERS_PRO_AND_UP",
    "premium": "PAID_TIERS_PREMIUM_AND_UP",
}

# On-demand route prefixes per artifact (require_tier-gated GET surfaces).
# Trigger endpoints are admin-secret-gated and some downloads are
# owner-scoped by CEO policy — only the gated prefixes below are asserted.
ROUTE_PREFIXES: dict[str, list[str]] = {
    "insider_mirror": ["/insider-mirror/preview", "/insider-mirror/download"],
    "risk_board": ["/risk-board/preview", "/risk-board/download"],
    "dividend_income": ["/dividend-income/preview", "/dividend-income/download"],
    "quarterly_self_report": ["/quarterly-self/preview", "/quarterly-self/download"],
    "self_audit": ["/self-audit/preview"],  # download is owner-scoped (2026-05-28)
    "portfolio_segment": ["/portfolio-segment/preview", "/portfolio-segment/download"],
    "credit_rating": ["/credit-rating/preview"],
    "burn_rate": ["/burn-rate/preview", "/burn-rate/download"],
    "kpi_dashboard": ["/kpi-dashboard/preview"],
}

_ROUTES_SRC = (
    Path(__file__).resolve().parent.parent / "routes" / "artifacts.py"
).read_text(encoding="utf-8")


@pytest.mark.parametrize("mod_name,tier", sorted(EXPECTED_TIER.items()))
def test_cron_fanout_matches_pricing_page(mod_name: str, tier: str):
    """Each artifact service's _PAID_TIERS frozenset must be the canonical
    set for the tier the pricing page sells it under."""
    from services.artifacts import _tiers

    mod = importlib.import_module(f"services.artifacts.{mod_name}_service")
    expected = getattr(_tiers, _TIER_SET_NAME[tier])
    actual = getattr(mod, "_PAID_TIERS")
    assert actual == expected, (
        f"{mod_name}: cron fan-out gates {sorted(actual)} but the pricing "
        f"page sells it as {tier.upper()} ({_TIER_SET_NAME[tier]})"
    )


@pytest.mark.parametrize(
    "mod_name,prefixes",
    sorted(ROUTE_PREFIXES.items()),
)
def test_on_demand_gates_match_pricing_page(mod_name: str, prefixes: list[str]):
    """Each require_tier-gated on-demand route must gate on the advertised
    tier (source-level check: route decorator followed by require_tier)."""
    tier = EXPECTED_TIER[mod_name]
    for prefix in prefixes:
        pat = re.compile(
            r'@artifacts_bp\.route\("' + re.escape(prefix) + r'"[^\n]*\)\n'
            r'(?:@[^\n]+\n){0,2}?@require_tier\("(\w+)"\)'
        )
        m = pat.search(_ROUTES_SRC)
        assert m, f"{prefix}: route or its require_tier gate not found"
        assert m.group(1) == tier, (
            f"{prefix}: gated @require_tier('{m.group(1)}') but the pricing "
            f"page sells {mod_name} as {tier.upper()}"
        )


def test_risk_board_force_fire_uses_pro_set():
    """The VIX force-fire fan-out must use the same tier set as the cron —
    one tier truth per artifact (2026-06-10 alignment)."""
    assert "PAID_TIERS_PRO_AND_UP" in _ROUTES_SRC.split(
        'def risk_board_trigger', 1
    )[1].split("def ", 1)[0]


def test_unified_generate_min_tier_matches_pricing_page():
    """Fourth surface: the unified /generate endpoint gates through
    _ARTIFACT_MIN_TIER (each artifact's individual route is bypassed there),
    so that map must carry the advertised tier for every gated artifact."""
    from routes.artifacts import _ARTIFACT_MIN_TIER

    mismatches = {
        mod: (got, want)
        for mod, want in EXPECTED_TIER.items()
        if (got := _ARTIFACT_MIN_TIER.get(mod)) != want
    }
    assert not mismatches, (
        "unified /generate _ARTIFACT_MIN_TIER disagrees with the pricing "
        f"page: {mismatches} (format: module: (gate, advertised))"
    )
    # And nothing gated in the map is missing from the pricing expectation —
    # a new paid artifact must be added to BOTH (keeps the gate test honest).
    unexpected = set(_ARTIFACT_MIN_TIER) - set(EXPECTED_TIER)
    assert not unexpected, (
        f"artifacts gated in _ARTIFACT_MIN_TIER but absent from "
        f"EXPECTED_TIER / the pricing page: {sorted(unexpected)}"
    )
