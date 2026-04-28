"""KOSPI/KOSDAQ sanity guard — protects users from KIS scaling glitches.

2026-04-29: CEO confirmed KOSPI ~6,600 (2026 re-rated). Sanity guard now
allows [1500, 8000] (KOSPI) and [500, 2500] (KOSDAQ). Values outside
these bounds are still dropped — protects against KIS API scaling glitches
or unit confusion.

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
         patch("kis_service.KISService") as MockKis:
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
         patch("kis_service.KISService") as MockKis:
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
    """KOSPI 50,000 (clearly a unit glitch) → still dropped, not published."""
    from data_fetcher import DataFetcher

    mock_fmp.get_quote.return_value = None
    mock_fmp.get_quotes_batch.return_value = {}
    mock_fmp.get_fx_rate.return_value = None

    f = DataFetcher()
    with patch("services.container.realtime") as mock_rt, \
         patch("kis_service.KISService") as MockKis:
        mock_rt.kis_available = True
        MockKis.return_value.get_index_price.side_effect = lambda code: (
            {"price": 50000.0, "change_pct": 0.42} if code == "0001"
            else {"price": 880.12, "change_pct": -0.18}
        )
        m = f.get_enhanced_macro()

    # 50,000 is far beyond the 8,000 ceiling → dropped (unit-confusion guard).
    assert "kospi" not in m
    # KOSDAQ in range still published.
    assert m.get("kosdaq", {}).get("price") == pytest.approx(880.12)


@patch.dict(os.environ, {"PIVOX_KOSPI_RANGE": "10000,20000"})
@patch("data_fetcher.fmp")
def test_kospi_env_override_widens_range(mock_fmp):
    """Operator can widen the bounds explicitly via env after verifying upstream.

    Useful if KRX further re-rates KOSPI above the default ceiling.
    """
    from data_fetcher import DataFetcher

    mock_fmp.get_quote.return_value = None
    mock_fmp.get_quotes_batch.return_value = {}
    mock_fmp.get_fx_rate.return_value = None

    f = DataFetcher()
    with patch("services.container.realtime") as mock_rt, \
         patch("kis_service.KISService") as MockKis:
        mock_rt.kis_available = True
        MockKis.return_value.get_index_price.side_effect = lambda code: (
            {"price": 12500.0, "change_pct": 0.42} if code == "0001" else None
        )
        m = f.get_enhanced_macro()

    # With override KOSPI 12,500 falls inside [10000, 20000] → published.
    assert m.get("kospi", {}).get("price") == pytest.approx(12500.0)
