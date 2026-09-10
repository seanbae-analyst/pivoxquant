"""The indices cache-warm contract.

``warm_indices_cache`` sits between the /api/market/indices request path and
the APScheduler job in app.py, and until 2026-09-10 it had no direct test —
nor did ``_compute_indices_snapshot`` or ``_indices_ttl``. Its docstring makes
three promises that are easy to break in a refactor and invisible when broken:

  1. TTL-gated. Inside the window and unforced, it must NOT hit upstream —
     the whole point of a scheduler tick every 60s against a 15s/300s
     market-aware TTL.
  2. It never caches an empty result. Caching a thin failure would lock every
     reader into empty data for the rest of the window; leaving the older
     entry in place degrades instead.
  3. Region is normalised, and the cache key carries a ``_v2`` suffix.

These are characterisation tests: they describe what the function does today,
so that moving it out of the routes layer can be shown to change nothing.
"""
from __future__ import annotations

import pytest

# Imported from its new home. The same eighteen assertions ran green
# against routes.market before the 2026-09-10 extraction, which is what
# makes them evidence the move changed nothing.
from services.data import indices as mkt


@pytest.fixture(autouse=True)
def _clean_cache():
    mkt._indices_cache.clear()
    yield
    mkt._indices_cache.clear()


def _stub_snapshot(monkeypatch, rows, counter=None):
    def fake(region):
        if counter is not None:
            counter.append(region)
        return list(rows)
    monkeypatch.setattr(mkt, "_compute_indices_snapshot", fake)


ROW = {"ticker": "^GSPC", "display": "S&P 500", "price": 1.0}


class TestTtlGate:
    def test_fetches_when_cache_is_empty(self, monkeypatch):
        calls: list[str] = []
        _stub_snapshot(monkeypatch, [ROW], calls)
        assert mkt.warm_indices_cache("us") == 1
        assert calls == ["us"]

    def test_skips_upstream_inside_the_ttl(self, monkeypatch):
        calls: list[str] = []
        _stub_snapshot(monkeypatch, [ROW], calls)
        mkt.warm_indices_cache("us")
        mkt.warm_indices_cache("us")           # second call, still fresh
        assert calls == ["us"], "second call hit upstream inside the TTL"

    def test_force_bypasses_the_gate(self, monkeypatch):
        calls: list[str] = []
        _stub_snapshot(monkeypatch, [ROW], calls)
        mkt.warm_indices_cache("us")
        mkt.warm_indices_cache("us", force=True)
        assert calls == ["us", "us"]

    def test_refetches_once_the_entry_has_aged_out(self, monkeypatch):
        calls: list[str] = []
        _stub_snapshot(monkeypatch, [ROW], calls)
        mkt.warm_indices_cache("us")
        # Age the entry past any plausible TTL rather than sleeping.
        mkt._indices_cache["us_v2"]["ts"] -= 10_000
        mkt.warm_indices_cache("us")
        assert calls == ["us", "us"]


class TestNeverCacheAFailure:
    def test_empty_result_does_not_overwrite_a_good_entry(self, monkeypatch):
        _stub_snapshot(monkeypatch, [ROW])
        mkt.warm_indices_cache("us")
        good_ts = mkt._indices_cache["us_v2"]["ts"]

        _stub_snapshot(monkeypatch, [])         # upstream now failing
        n = mkt.warm_indices_cache("us", force=True)

        assert n == 1, "reported a count it no longer holds"
        assert mkt._indices_cache["us_v2"]["data"] == [ROW]
        assert mkt._indices_cache["us_v2"]["ts"] == good_ts, (
            "an empty fetch refreshed the timestamp, which would hide the "
            "staleness of the data still being served"
        )

    def test_empty_result_with_no_prior_entry_returns_zero(self, monkeypatch):
        _stub_snapshot(monkeypatch, [])
        assert mkt.warm_indices_cache("us") == 0
        assert "us_v2" not in mkt._indices_cache


class TestRegionHandling:
    @pytest.mark.parametrize("given,expected", [
        ("us", "us"), ("kr", "kr"), ("US", "us"), ("KR", "kr"),
        ("", "us"), (None, "us"), ("jp", "us"), ("nonsense", "us"),
    ])
    def test_region_is_normalised(self, monkeypatch, given, expected):
        calls: list[str] = []
        _stub_snapshot(monkeypatch, [ROW], calls)
        mkt.warm_indices_cache(given)
        assert calls == [expected]

    def test_cache_key_keeps_the_v2_suffix(self, monkeypatch):
        """The suffix is a schema marker — a reader of the old shape must miss."""
        _stub_snapshot(monkeypatch, [ROW])
        mkt.warm_indices_cache("kr")
        assert set(mkt._indices_cache) == {"kr_v2"}

    def test_regions_do_not_share_an_entry(self, monkeypatch):
        _stub_snapshot(monkeypatch, [ROW])
        mkt.warm_indices_cache("us")
        mkt.warm_indices_cache("kr")
        assert set(mkt._indices_cache) == {"us_v2", "kr_v2"}


class TestTtlSource:
    def test_ttl_comes_from_the_market_aware_helper(self):
        """_indices_ttl must defer to services.cache_ttl, not hard-code a
        number — the 15s intraday / 300s off-hours split is what makes a
        fixed-interval scheduler tick correct."""
        from services import cache_ttl
        assert mkt._indices_ttl() == cache_ttl.indices_ttl()

    def test_ttl_is_a_positive_int(self):
        ttl = mkt._indices_ttl()
        assert isinstance(ttl, int) and ttl > 0
