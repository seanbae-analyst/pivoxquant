"""KOSPI/KOSDAQ sanity guard — protects users from KIS scaling glitches.

2026-04-29: CEO directive — ceiling raised to 50,000 for both indices to
absorb future re-rates. Sanity guard now allows [1500, 50000] (KOSPI) and
[500, 50000] (KOSDAQ). Values outside these bounds are still dropped —
protects against 100x unit-confusion glitches (e.g. KOSPI = 660,000).

Override via env:
    PIVOX_KOSPI_RANGE=lo,hi
    PIVOX_KOSDAQ_RANGE=lo,hi
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def _make_fetcher_with_kis_quote(kis_price: float):
    """Build a DataFetcher whose KIS index_price returns a single value."""
    from data_fetcher import DataFetcher

    f = DataFetcher()
    return f, kis_price


@patch("data_fetcher.fmp")
def test_kospi_in_range_published(mock_fmp):
    """KOSPI 2,650 (normal) → published to macro."""
    from data_fetcher import DataFetcher

    mock_fmp.get_quote.return_value = None
    mock_fmp.get_quotes_batch.return_value = {}
    mock_fmp.get_fx_rate.return_value = None

    f = DataFetcher()
    with patch("services.container.realtime") as mock_rt, \
         patch("services.kis.service.KISService") as MockKis:
        mock_rt.kis_available = True
        MockKis.return_value.get_index_price.side_effect = lambda code: (
            {"price": 2650.45, "change_pct": 0.42} if code == "0001"
            else {"price": 880.12, "change_pct": -0.18}
        )
        m = f.get_enhanced_macro()

    assert m.get("kospi", {}).get("price") == pytest.approx(2650.45)
    assert m.get("kosdaq", {}).get("price") == pytest.approx(880.12)


@patch("data_fetcher.fmp")
def test_kospi_in_2026_range_published(mock_fmp):
    """KOSPI 6,641 (2026 re-rated) → published. Within [1500, 8000]."""
    from data_fetcher import DataFetcher

    mock_fmp.get_quote.return_value = None
    mock_fmp.get_quotes_batch.return_value = {}
    mock_fmp.get_fx_rate.return_value = None

    f = DataFetcher()
    with patch("services.container.realtime") as mock_rt, \
         patch("services.kis.service.KISService") as MockKis:
        mock_rt.kis_available = True
        MockKis.return_value.get_index_price.side_effect = lambda code: (
            {"price": 6641.02, "change_pct": 0.42} if code == "0001"
            else {"price": 880.12, "change_pct": -0.18}
        )
        m = f.get_enhanced_macro()

    # KOSPI 6,641 is the 2026 re-rated level — must be published.
    assert m.get("kospi", {}).get("price") == pytest.approx(6641.02)
    assert m.get("kosdaq", {}).get("price") == pytest.approx(880.12)


@patch("data_fetcher.fmp")
def test_kospi_extreme_glitch_still_dropped(mock_fmp):
    """KOSPI 660,000 (100x unit glitch) → still dropped, not published."""
    from data_fetcher import DataFetcher

    mock_fmp.get_quote.return_value = None
    mock_fmp.get_quotes_batch.return_value = {}
    mock_fmp.get_fx_rate.return_value = None

    f = DataFetcher()
    with patch("services.container.realtime") as mock_rt, \
         patch("services.kis.service.KISService") as MockKis:
        mock_rt.kis_available = True
        MockKis.return_value.get_index_price.side_effect = lambda code: (
            {"price": 660000.0, "change_pct": 0.42} if code == "0001"
            else {"price": 880.12, "change_pct": -0.18}
        )
        m = f.get_enhanced_macro()

    # 660,000 is far beyond the 50,000 ceiling → dropped (100x unit-glitch guard).
    assert "kospi" not in m
    # KOSDAQ in range still published.
    assert m.get("kosdaq", {}).get("price") == pytest.approx(880.12)


@patch.dict(os.environ, {"PIVOX_KOSPI_RANGE": "60000,80000"})
@patch("data_fetcher.fmp")
def test_kospi_env_override_widens_range(mock_fmp):
    """Operator can widen the bounds explicitly via env after verifying upstream."""
    from data_fetcher import DataFetcher

    mock_fmp.get_quote.return_value = None
    mock_fmp.get_quotes_batch.return_value = {}
    mock_fmp.get_fx_rate.return_value = None

    f = DataFetcher()
    with patch("services.container.realtime") as mock_rt, \
         patch("services.kis.service.KISService") as MockKis:
        mock_rt.kis_available = True
        MockKis.return_value.get_index_price.side_effect = lambda code: (
            {"price": 70000.0, "change_pct": 0.42} if code == "0001" else None
        )
        m = f.get_enhanced_macro()

    # With override KOSPI 70,000 falls inside [60000, 80000] → published.
    assert m.get("kospi", {}).get("price") == pytest.approx(70000.0)
