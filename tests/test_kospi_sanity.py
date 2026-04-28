"""KOSPI/KOSDAQ sanity guard — protects users from KIS scaling glitches.

2026-04-28: KIS API briefly returned KOSPI = 6,641.02 (~2x historical high).
The sanity guard in `data_fetcher.get_enhanced_macro` drops readings outside
[1500, 3500] (KOSPI) and [500, 1500] (KOSDAQ) by default.

Override via env (after externally verifying with KRX/Yahoo):
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
def test_kospi_out_of_range_dropped(mock_fmp):
    """KOSPI 6,641.02 (2x historical max) → dropped, not published."""
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

    # KOSPI must NOT appear in macro (out-of-range reading dropped).
    assert "kospi" not in m, (
        "KOSPI 6,641 must be rejected — historical max ~3,316. "
        "Override only via PIVOX_KOSPI_RANGE after external verification."
    )
    # KOSDAQ in range still published.
    assert m.get("kosdaq", {}).get("price") == pytest.approx(880.12)


@patch.dict(os.environ, {"PIVOX_KOSPI_RANGE": "1000,8000"})
@patch("data_fetcher.fmp")
def test_kospi_env_override_widens_range(mock_fmp):
    """Operator can widen the bounds explicitly via env after verifying upstream."""
    from data_fetcher import DataFetcher

    mock_fmp.get_quote.return_value = None
    mock_fmp.get_quotes_batch.return_value = {}
    mock_fmp.get_fx_rate.return_value = None

    f = DataFetcher()
    with patch("services.container.realtime") as mock_rt, \
         patch("kis_service.KISService") as MockKis:
        mock_rt.kis_available = True
        MockKis.return_value.get_index_price.side_effect = lambda code: (
            {"price": 6641.02, "change_pct": 0.42} if code == "0001" else None
        )
        m = f.get_enhanced_macro()

    # With override KOSPI 6641 falls inside [1000, 8000] → published.
    assert m.get("kospi", {}).get("price") == pytest.approx(6641.02)
