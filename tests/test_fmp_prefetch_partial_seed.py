"""tests/test_fmp_prefetch_partial_seed.py

Locks in the fix for the partial-info cache-poisoning bug in
``services/data/fmp.py::prefetch_fundamentals`` (cache seed guard at ~L1627).

Background:
    ``prefetch_fundamentals`` deliberately skips fetching per-ticker
    ratios/metrics at startup to preserve the daily FMP budget. The info
    record it builds from the profile alone therefore lacks
    PE / EPS / margin / growth.

    The OLD seed guard was::

        has_critical = trailingPE or trailingEps or marketCap
        if is_etf or has_critical:
            _set_cache("info:<t>", info)

    Because profile always carries ``marketCap``, ``has_critical`` was True
    for every non-ETF, so a ratios-less partial record got cached for the
    full 24h TTL. ``get_info()`` then early-returned that partial → every
    DISCOVER_POOL ticker rendered "—" for fundamentals for 24h.

    The FIX seeds the info cache only when ratios AND metrics are actually
    present (or the ticker is an ETF, which legitimately lacks these
    ratios). A non-ETF without cached ratios is left un-seeded so that
    ``get_info()`` performs its correct on-demand fetch on first open.
"""
from __future__ import annotations

import time

from services.data import fmp as fmp_service


def _clear_fmp_cache():
    with fmp_service._cache_lock:
        fmp_service._cache.clear()
        fmp_service._endpoint_402_counts.clear()
        fmp_service._endpoint_402_cooldown.clear()
    fmp_service._daily_calls = 0
    fmp_service._daily_calls_reset = time.time()


def _seed_profile(ticker, *, is_etf=False):
    fmp_service._set_cache(f"profile:{ticker}", {
        "companyName": f"{ticker} Inc",
        "sector": "Tech",
        "industry": "Software",
        "marketCap": 3_000_000_000_000,  # always present → old guard always passed
        "price": 200,
        "range": "180-220",
        "isEtf": is_etf,
    })


def _seed_ratios(ticker):
    fmp_service._set_cache(f"ratios_ttm:{ticker}", {
        "priceToEarningsRatioTTM": 30,
        "netIncomePerShareTTM": 6.5,
        "revenuePerShareTTM": 25.0,
        "netProfitMarginTTM": 0.25,
        "priceToBookRatioTTM": 40,
    })


def _seed_metrics(ticker):
    fmp_service._set_cache(f"metrics_ttm:{ticker}", {"epsTTM": 6.5})


def _info_cached(ticker):
    return fmp_service._get_cache(f"info:{ticker}", fmp_service.TTL_FUNDAMENTAL)


class TestPrefetchInfoSeedGuard:
    """prefetch must NOT pre-seed a ratios-less partial info record."""

    def _run_prefetch(self, monkeypatch, tickers):
        # Prefetch's batch profile/quote calls are network — neutralize them.
        # Profiles are pre-seeded directly via _seed_profile, so these are no-ops.
        monkeypatch.setattr(fmp_service, "get_profiles_batch", lambda chunk: None)
        monkeypatch.setattr(fmp_service, "get_quotes_batch", lambda chunk: None)
        fmp_service.prefetch_fundamentals(tickers)

    def test_non_etf_without_ratios_is_not_seeded(self, monkeypatch):
        """The core bug: marketCap alone must NOT seed the info cache."""
        _clear_fmp_cache()
        _seed_profile("AAPL", is_etf=False)
        # No ratios / metrics cached — mirrors the budget-saving prefetch path.
        self._run_prefetch(monkeypatch, ["AAPL"])
        assert _info_cached("AAPL") is None, (
            "Regression: non-ETF info built from profile alone (no ratios) "
            "was pre-seeded → get_info() would early-return a partial record "
            "and fundamentals render '—' for the full 24h TTL"
        )

    def test_etf_is_still_seeded_from_profile(self, monkeypatch):
        """ETFs legitimately lack PE/EPS ratios → still seed from profile."""
        _clear_fmp_cache()
        _seed_profile("SPY", is_etf=True)
        self._run_prefetch(monkeypatch, ["SPY"])
        cached = _info_cached("SPY")
        assert cached is not None, "ETF info should still be seeded from profile"
        assert cached.get("isEtf") is True

    def test_non_etf_with_ratios_and_metrics_is_seeded(self, monkeypatch):
        """When ratios+metrics are already cached, a full info record IS seeded."""
        _clear_fmp_cache()
        _seed_profile("MSFT", is_etf=False)
        _seed_ratios("MSFT")
        _seed_metrics("MSFT")
        self._run_prefetch(monkeypatch, ["MSFT"])
        cached = _info_cached("MSFT")
        assert cached is not None, (
            "Non-ETF with cached ratios+metrics should be seeded with full info"
        )
        assert cached.get("trailingPE") == 30
        assert cached.get("trailingEps") == 6.5
        assert cached.get("netProfitMargin") == 0.25

    def test_non_etf_with_only_ratios_is_not_seeded(self, monkeypatch):
        """Both ratios AND metrics are required — ratios alone is still partial."""
        _clear_fmp_cache()
        _seed_profile("NVDA", is_etf=False)
        _seed_ratios("NVDA")  # metrics intentionally absent
        self._run_prefetch(monkeypatch, ["NVDA"])
        assert _info_cached("NVDA") is None, (
            "ratios without metrics is still incomplete → must not seed"
        )
