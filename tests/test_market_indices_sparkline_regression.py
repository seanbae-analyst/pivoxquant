"""
PivoxQuant — Market indices sparkline regression suite.
========================================================
Guards against the stale-data regression pattern observed in PR #343 audit:
  - SNAPSHOT_DATE in market-ticker.tsx was 18 days stale (2026-04-24 → 2026-05-12)
  - KOSPI showed 2,755 on the landing (pre-pandemic level, capital-markets-law risk)
  - /api/market/indices?region=kr sparkline_30d was <=1 entry (incomplete)

This file is marked `live_api` — default-SKIPPED so the normal `pytest tests/`
suite (unit/integration with mocked backends) is unaffected.  To run manually
against a live backend:

    # 1. Start backend
    cd /Users/seanbae/Desktop/취준/pivoxquant && python3 run.py

    # 2. In another terminal:
    pytest tests/test_market_indices_sparkline_regression.py -m live_api -v

Memory rule [feedback_official_data_only]: KIS API only for KR data — no
pykrx / yfinance / Naver Finance.
"""
from __future__ import annotations

import pytest
import requests

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:5050"
TIMEOUT = 15  # seconds — KIS upstream can be slow

# Sanity bounds for index levels (post-B-06 fix; mirrors routes/market.py).
# A value outside these bounds is a unit-confusion bug (e.g. KOSPI returned
# as KOSPI-200, or a pre-pandemic stale snapshot leaking into the live path).
LEVEL_BOUNDS: dict[str, tuple[float, float]] = {
    "kospi":   (1_500,  50_000),   # Current KOSPI ~7,600; old 2,755 catches stale
    "kosdaq":  (  500,  50_000),   # Current KOSDAQ ~1,179
    "usdkrw":  (  900,   2_000),   # USD/KRW reasonable corridor
}

# Minimum sparkline entries required (or is_stale must be True).
MIN_SPARKLINE_LEN = 20


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _kr_indices() -> dict:
    """GET /api/market/indices?region=kr and return the parsed JSON body."""
    resp = requests.get(f"{BASE_URL}/api/market/indices", params={"region": "kr"}, timeout=TIMEOUT)
    assert resp.status_code == 200, (
        f"/api/market/indices?region=kr returned {resp.status_code}: {resp.text[:300]}"
    )
    data = resp.json()
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.live_api
class TestMarketIndicesSparklineRegression:
    """Live-backend regression guards for /api/market/indices?region=kr."""

    def test_endpoint_returns_200(self):
        """Baseline: endpoint is reachable and returns HTTP 200."""
        resp = requests.get(
            f"{BASE_URL}/api/market/indices", params={"region": "kr"}, timeout=TIMEOUT
        )
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}. Is the backend running on {BASE_URL}?"
        )

    def test_kospi_sparkline_length_or_stale_flag(self):
        """KOSPI sparkline_30d must have >= 20 entries, or is_stale must be True.

        Regression: PR #343 audit found sparkline_30d with only 1 entry because
        the KIS historical endpoint was returning a single-day response.
        """
        data = _kr_indices()
        assert "kospi" in data, f"'kospi' key missing from response: {list(data.keys())}"
        kospi = data["kospi"]
        sparkline = kospi.get("sparkline_30d", [])
        is_stale = kospi.get("is_stale", False)
        assert len(sparkline) >= MIN_SPARKLINE_LEN or is_stale, (
            f"KOSPI sparkline_30d has only {len(sparkline)} entries "
            f"(expected >= {MIN_SPARKLINE_LEN}) and is_stale={is_stale}. "
            "KIS historical endpoint may be returning a truncated response."
        )

    def test_kosdaq_sparkline_length_or_stale_flag(self):
        """KOSDAQ sparkline_30d must have >= 20 entries, or is_stale must be True."""
        data = _kr_indices()
        assert "kosdaq" in data, f"'kosdaq' key missing from response: {list(data.keys())}"
        kosdaq = data["kosdaq"]
        sparkline = kosdaq.get("sparkline_30d", [])
        is_stale = kosdaq.get("is_stale", False)
        assert len(sparkline) >= MIN_SPARKLINE_LEN or is_stale, (
            f"KOSDAQ sparkline_30d has only {len(sparkline)} entries "
            f"(expected >= {MIN_SPARKLINE_LEN}) and is_stale={is_stale}."
        )

    def test_usdkrw_sparkline_length_or_stale_flag(self):
        """USDKRW sparkline_30d must have >= 20 entries, or is_stale must be True."""
        data = _kr_indices()
        assert "usdkrw" in data, f"'usdkrw' key missing from response: {list(data.keys())}"
        usdkrw = data["usdkrw"]
        sparkline = usdkrw.get("sparkline_30d", [])
        is_stale = usdkrw.get("is_stale", False)
        assert len(sparkline) >= MIN_SPARKLINE_LEN or is_stale, (
            f"USDKRW sparkline_30d has only {len(sparkline)} entries "
            f"(expected >= {MIN_SPARKLINE_LEN}) and is_stale={is_stale}."
        )

    def test_kospi_level_sanity_bounds(self):
        """KOSPI level must be in [1500, 50000] — catches stale 2,755 or unit-confusion.

        Regression: The pre-PR #343 landing showed KOSPI 2,755 (pre-pandemic
        snapshot from 2026-04-24) — an 18-day stale value that constituted an
        active capital-markets-law misrepresentation risk (top-ticker.tsx §93-97).
        The live endpoint should never return a value this far from reality.
        """
        data = _kr_indices()
        kospi = data.get("kospi", {})
        level = kospi.get("level")
        lo, hi = LEVEL_BOUNDS["kospi"]
        assert level is not None, "KOSPI 'level' field is missing from response"
        try:
            level_f = float(str(level).replace(",", ""))
        except (ValueError, TypeError) as exc:
            pytest.fail(f"KOSPI level '{level}' is not numeric: {exc}")
        assert lo <= level_f <= hi, (
            f"KOSPI level {level_f} is outside sanity bounds [{lo}, {hi}]. "
            "Possible causes: stale snapshot, unit-confusion (KOSPI vs KOSPI-200), "
            "or wrong index code returned by KIS."
        )

    def test_kosdaq_level_sanity_bounds(self):
        """KOSDAQ level must be in [500, 50000]."""
        data = _kr_indices()
        kosdaq = data.get("kosdaq", {})
        level = kosdaq.get("level")
        lo, hi = LEVEL_BOUNDS["kosdaq"]
        assert level is not None, "KOSDAQ 'level' field is missing from response"
        try:
            level_f = float(str(level).replace(",", ""))
        except (ValueError, TypeError) as exc:
            pytest.fail(f"KOSDAQ level '{level}' is not numeric: {exc}")
        assert lo <= level_f <= hi, (
            f"KOSDAQ level {level_f} is outside sanity bounds [{lo}, {hi}]."
        )

    def test_usdkrw_level_sanity_bounds(self):
        """USDKRW level must be in [900, 2000] — guards against unit-confusion (e.g. 0.00068)."""
        data = _kr_indices()
        usdkrw = data.get("usdkrw", {})
        level = usdkrw.get("level")
        lo, hi = LEVEL_BOUNDS["usdkrw"]
        assert level is not None, "USDKRW 'level' field is missing from response"
        try:
            level_f = float(str(level).replace(",", ""))
        except (ValueError, TypeError) as exc:
            pytest.fail(f"USDKRW level '{level}' is not numeric: {exc}")
        assert lo <= level_f <= hi, (
            f"USDKRW level {level_f} is outside sanity bounds [{lo}, {hi}]."
        )
