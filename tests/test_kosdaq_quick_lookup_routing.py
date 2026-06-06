"""Regression — KOSDAQ exchange routing in DataFetcher.quick_lookup.

Bug (overnight hunt 2026-06-07, LANE 6 BUG-2): quick_lookup hardcoded
``ticker + ".KS"`` for every bare 6-digit KR code, so KOSDAQ stocks
(035760 CJ ENM, 293490 Kakao Games, …) were queried on the KOSPI
exchange. The wrong suffix can resolve to a *different* security or no
data at all. Fix routes 6-digit codes through ``normalize_ticker`` which
consults the KR registry and only falls back to ``.KS`` for unknown codes.
"""

import inspect

from services.data.fetcher import DataFetcher
from services.ticker_normalizer import normalize_ticker


def test_normalize_ticker_routes_kosdaq_to_kq():
    # KOSDAQ → .KQ (the routing quick_lookup now relies on)
    assert normalize_ticker("035760") == "035760.KQ"  # CJ ENM
    assert normalize_ticker("293490") == "293490.KQ"  # Kakao Games
    assert normalize_ticker("247540") == "247540.KQ"  # Ecopro BM


def test_normalize_ticker_keeps_kospi_on_ks():
    assert normalize_ticker("005930") == "005930.KS"  # Samsung Electronics
    assert normalize_ticker("000660") == "000660.KS"  # SK Hynix


def test_quick_lookup_uses_registry_normalization_not_hardcoded_ks():
    """Guard the specific fix: quick_lookup must not re-introduce the
    hardcoded ``.KS`` suffix for 6-digit codes."""
    src = inspect.getsource(DataFetcher.quick_lookup)
    assert "normalize_ticker(" in src, (
        "quick_lookup must route bare 6-digit KR codes via normalize_ticker"
    )
    assert '+ ".KS"' not in src, (
        "quick_lookup must NOT hardcode .KS — it mis-routes every KOSDAQ ticker"
    )
