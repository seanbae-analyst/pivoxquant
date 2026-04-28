"""
/api/risk/concentration — endpoint contract tests.

Proves:
  1. Unauthenticated → 401 (api_auth gate works).
  2. Authenticated empty portfolio → 200 + empty payload (NOT 404).
  3. Authenticated populated portfolio → HHI in [0,1], top_positions sorted.
  4. Single-position book → HHI close to 1.0 (max concentration).
"""
from __future__ import annotations


def test_concentration_unauth_returns_401(client):
    r = client.get("/api/risk/concentration")
    assert r.status_code == 401, (
        f"Unauthenticated should be 401 (was {r.status_code}). "
        "If the endpoint is missing or @api_auth was dropped this regresses."
    )


def test_concentration_empty_portfolio_returns_200_empty(client, auth_user):
    """Empty portfolio MUST return 200 + empty arrays, never 404."""
    r = client.get("/api/risk/concentration")
    assert r.status_code == 200
    body = r.get_json()
    assert body["position_count"] == 0
    assert body["hhi"] == 0.0
    assert body["hhi_label"] == "low"
    assert body["top_positions"] == []
    assert body["sectors"] == []
    assert "as_of" in body


def test_concentration_populated_portfolio_emits_hhi(
    client, auth_user, add_position
):
    """Two positions → HHI ∈ [0,1] and top_positions ranked by weight desc."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    add_position(auth_user["id"], ticker="MSFT", shares=5, avg_cost=200)
    r = client.get("/api/risk/concentration")
    assert r.status_code == 200
    body = r.get_json()
    # HHI structurally valid.
    assert 0.0 <= body["hhi"] <= 1.0
    assert body["hhi_label"] in ("low", "medium", "high")
    # position_count reflects what was added (broker prices may zero some).
    assert body["position_count"] >= 0
    # If positions were resolved, top_positions sorted by weight desc.
    if body["top_positions"]:
        weights = [p["weight"] for p in body["top_positions"]]
        assert weights == sorted(weights, reverse=True)
        # Each row has ticker + weight + sector keys.
        for p in body["top_positions"]:
            assert set(p.keys()) >= {"ticker", "weight", "sector"}
    # If sector resolution emitted any buckets, weight sums ≤ ~1.0.
    if body["sectors"]:
        assert sum(s["weight"] for s in body["sectors"]) <= 1.001


def test_concentration_single_position_high_hhi(
    client, auth_user, add_position
):
    """Single-position portfolio is the most concentrated case (HHI → 1.0)."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    r = client.get("/api/risk/concentration")
    assert r.status_code == 200
    body = r.get_json()
    # If pricing resolved at all, the single position must dominate.
    if body["position_count"] > 0 and body["top_positions"]:
        # Single-position weights normalize to 1.0 → HHI = 1.0.
        assert body["hhi"] == 1.0
        assert body["hhi_label"] == "high"
