"""Regression tests for Wave 11 SRP split of routes/quant.py.

Ensures:
1. All 5 new blueprints are registered (signals_quant, risk_quant,
   performance_quant, tools_quant, strategy_quant).
2. Every URL from the original /api/quant.py is preserved exactly.
3. routes/quant.py is NOT recreated (dead-file guard).
"""

from __future__ import annotations

import pathlib

import pytest


# All 30 URLs that were defined in the original routes/quant.py.
# (Wave 11 PR description audit-code A.2 A-01/A-02 source list.)
EXPECTED_URLS: list[str] = [
    # strategy_quant_bp (5)
    "/api/vix-strategy",
    "/api/cross-asset",
    "/api/stat-arb",
    "/api/screener/canslim/<ticker>",
    "/api/regime/interest-rate",
    # signals_quant_bp (7)
    "/api/signals/short-interest/<ticker>",
    "/api/signals/insider/<ticker>",
    "/api/signals/disposition/<ticker>",
    "/api/signals/ofi/<ticker>",
    "/api/signals/sentiment-divergence/<ticker>",
    "/api/signals/anchoring/<ticker>",
    "/api/signals/herding",
    # risk_quant_bp (10)
    "/api/risk/var",
    "/api/risk/drawdown",
    "/api/risk/stress-test",
    "/api/risk/volatility/<ticker>",
    "/api/risk/component-es",
    "/api/risk/defense-status",
    "/api/risk/conditional-drawdown",
    "/api/risk/tail-ratio",
    "/api/risk/sortino-by-position",
    "/api/risk/ledoit-wolf-shrinkage",
    # performance_quant_bp (4)
    "/api/analytics/regime-report",
    "/api/analytics/benchmark",
    "/api/analytics/turnover",
    "/api/performance/ledger",
    # tools_quant_bp (4)
    "/api/tools/position-sizing",
    "/api/tools/correlation-matrix",
    "/api/tools/sector-heatmap",
    "/api/indicators/<ticker>",
]

EXPECTED_BLUEPRINTS = {
    "signals_quant",
    "risk_quant",
    "performance_quant",
    "tools_quant",
    "strategy_quant",
}


@pytest.fixture(scope="module")
def flask_app():
    from app import create_app

    app = create_app()
    return app


def test_all_5_blueprints_registered(flask_app):
    """Every new quant blueprint must be registered on the app."""
    registered = set(flask_app.blueprints.keys())
    missing = EXPECTED_BLUEPRINTS - registered
    assert not missing, f"Missing blueprints: {missing}"


def test_old_quant_bp_not_registered(flask_app):
    """The original monolithic `quant` blueprint must be gone."""
    assert "quant" not in flask_app.blueprints, (
        "Old `quant` blueprint should not be registered after Wave 11 split."
    )


def test_all_30_urls_preserved(flask_app):
    """Every URL from the original routes/quant.py must still resolve.

    This is the load-bearing test: frontend endpoints.ts depends on these
    exact paths. Any breakage = frontend regression.
    """
    rules = {str(rule) for rule in flask_app.url_map.iter_rules()}
    missing = [url for url in EXPECTED_URLS if url not in rules]
    assert not missing, (
        f"URL preservation failed. Missing {len(missing)} URLs after split:\n"
        + "\n".join(f"  {u}" for u in missing)
    )


def test_routes_quant_file_does_not_exist():
    """Dead-file guard: routes/quant.py must NOT come back.

    If a future PR reintroduces routes/quant.py this test fails, forcing
    the author to either delete it again or update this guard with a
    deliberate change.
    """
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    quant_py = repo_root / "routes" / "quant.py"
    assert not quant_py.exists(), (
        f"routes/quant.py exists at {quant_py}. The Wave 11 SRP split "
        "moved its contents to routes/{signals,risk,performance,tools,"
        "strategy}_quant.py + routes/quant_helpers.py. Do not reintroduce."
    )


def test_blueprint_route_counts(flask_app):
    """Per-blueprint route counts must match the Wave 11 mapping table."""
    counts: dict[str, int] = {}
    for rule in flask_app.url_map.iter_rules():
        bp = rule.endpoint.split(".")[0]
        if bp in EXPECTED_BLUEPRINTS:
            counts[bp] = counts.get(bp, 0) + 1

    expected = {
        "signals_quant": 7,
        "risk_quant": 10,
        "performance_quant": 4,
        "tools_quant": 4,
        "strategy_quant": 5,
    }
    assert counts == expected, (
        f"Route count mismatch.\nExpected: {expected}\nActual:   {counts}"
    )
