"""
Risk portfolio-snapshot cache (Perf P0-2, 2026-05-10).

Proves:
  1. Two calls to _portfolio_snapshot() within TTL hit the cache —
     fetcher.get_price_history is called only on the first.
  2. Cache invalidates when positions change (different signature).
  3. Cache expires after TTL — second call past TTL re-fetches.
  4. risk_snapshot_cache_get returns None for unknown keys.
  5. LRU prune kicks in when entries exceed MAX_ENTRIES.
"""
from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pytest


# ─── Pure cache-helper unit tests (no Flask context required) ──────────────


def test_cache_get_unknown_key_returns_none():
    from services.cache_service import (
        risk_snapshot_cache_clear,
        risk_snapshot_cache_get,
    )
    risk_snapshot_cache_clear()
    assert risk_snapshot_cache_get(1, "nope") is None


def test_cache_set_then_get_roundtrip():
    from services.cache_service import (
        risk_snapshot_cache_clear,
        risk_snapshot_cache_get,
        risk_snapshot_cache_set,
    )
    risk_snapshot_cache_clear()
    payload = ({"x": 1}, ["AAPL"], None, None)
    risk_snapshot_cache_set(42, "sig-a", payload)
    got = risk_snapshot_cache_get(42, "sig-a")
    assert got == payload


def test_cache_isolated_per_user_and_signature():
    from services.cache_service import (
        risk_snapshot_cache_clear,
        risk_snapshot_cache_get,
        risk_snapshot_cache_set,
    )
    risk_snapshot_cache_clear()
    risk_snapshot_cache_set(1, "sig-a", "payload-1")
    risk_snapshot_cache_set(2, "sig-a", "payload-2")
    risk_snapshot_cache_set(1, "sig-b", "payload-3")
    assert risk_snapshot_cache_get(1, "sig-a") == "payload-1"
    assert risk_snapshot_cache_get(2, "sig-a") == "payload-2"
    assert risk_snapshot_cache_get(1, "sig-b") == "payload-3"
    assert risk_snapshot_cache_get(99, "sig-a") is None


def test_cache_ttl_expiry_returns_none_after_window():
    """Force-expire via monkey-patching time.time forward past TTL."""
    from services import cache_service
    cache_service.risk_snapshot_cache_clear()
    cache_service.risk_snapshot_cache_set(1, "sig-x", "stale")

    real_time = cache_service.time.time
    fake_now = real_time() + cache_service.RISK_SNAPSHOT_TTL + 1
    with patch.object(cache_service.time, "time", return_value=fake_now):
        assert cache_service.risk_snapshot_cache_get(1, "sig-x") is None


def test_cache_lru_prune_drops_oldest_quartile_when_overflow():
    from services import cache_service
    cache_service.risk_snapshot_cache_clear()

    # Fill to MAX_ENTRIES exactly with sequential timestamps.
    max_n = cache_service.RISK_SNAPSHOT_MAX_ENTRIES
    base = cache_service.time.time()
    for i in range(max_n):
        # Backdate each entry so .ts ordering is deterministic.
        cache_service._risk_snapshot_cache[(i, "s")] = {
            "payload": f"p-{i}", "ts": base - (max_n - i),
        }
    # One more triggers prune (drops oldest 25%).
    cache_service.risk_snapshot_cache_set(99999, "s", "p-new")

    assert len(cache_service._risk_snapshot_cache) <= max_n
    # The oldest entry (i=0, lowest ts) should be gone after prune.
    assert (0, "s") not in cache_service._risk_snapshot_cache
    # The freshly inserted one survives.
    assert cache_service.risk_snapshot_cache_get(99999, "s") == "p-new"


def test_cache_clear_drops_all():
    from services.cache_service import (
        risk_snapshot_cache_clear,
        risk_snapshot_cache_get,
        risk_snapshot_cache_set,
    )
    risk_snapshot_cache_set(1, "s", "x")
    assert risk_snapshot_cache_get(1, "s") == "x"
    risk_snapshot_cache_clear()
    assert risk_snapshot_cache_get(1, "s") is None


def test_cache_rejects_falsy_keys():
    """Defensive: empty signatures / None user_ids must not poison cache."""
    from services.cache_service import (
        risk_snapshot_cache_clear,
        risk_snapshot_cache_get,
        risk_snapshot_cache_set,
    )
    risk_snapshot_cache_clear()
    risk_snapshot_cache_set(None, "sig", "p")
    risk_snapshot_cache_set(1, "", "p")
    risk_snapshot_cache_set(1, "sig", None)
    assert risk_snapshot_cache_get(None, "sig") is None
    assert risk_snapshot_cache_get(1, "") is None


# ─── End-to-end: risk endpoint actually consults the cache ─────────────────


def test_risk_summary_second_call_skips_price_history_fetch(
    client, auth_user, add_position, app
):
    """First /summary call fetches price history; second call within TTL
    must re-use the cached snapshot — fetcher.get_price_history NOT called.
    """
    from services.cache_service import risk_snapshot_cache_clear
    risk_snapshot_cache_clear()

    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150)

    import pandas as pd
    fake_history = pd.DataFrame(
        {"Close": [100.0 + i * 0.5 for i in range(60)]},
        index=pd.date_range("2026-01-01", periods=60, freq="D"),
    )
    fetch_calls = {"count": 0}

    def fake_get_price_history(t, period="3mo"):
        fetch_calls["count"] += 1
        return fake_history

    with patch("routes.risk.fetcher") as mock_fetcher, \
         patch("services.container.realtime") as mock_rt:
        mock_fetcher.get_price_history.side_effect = fake_get_price_history
        mock_fetcher.get_macro_data.return_value = {"vix": 18.0}
        mock_rt.get_prices_batch.return_value = {"AAPL": {"price": 175.0}}

        r1 = client.get("/api/risk/summary")
        assert r1.status_code == 200
        first_count = fetch_calls["count"]
        assert first_count >= 1, "First call must hit the fetcher"

        r2 = client.get("/api/risk/summary")
        assert r2.status_code == 200

    # Cache hit on second call — no additional fetcher calls.
    assert fetch_calls["count"] == first_count, (
        f"Cache miss on 2nd call — fetcher hit {fetch_calls['count']} times "
        f"total (expected {first_count}). Cache regression."
    )


def test_risk_cache_invalidates_when_positions_change(
    client, auth_user, add_position, app
):
    """Adding a position changes _positions_signature → cache miss → fetch
    triggers again. Proves no stale data after a trade."""
    from services.cache_service import risk_snapshot_cache_clear
    risk_snapshot_cache_clear()

    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150)

    import pandas as pd
    fake_history = pd.DataFrame(
        {"Close": [100.0 + i * 0.5 for i in range(60)]},
        index=pd.date_range("2026-01-01", periods=60, freq="D"),
    )
    fetch_calls = {"count": 0}

    def fake_get_price_history(t, period="3mo"):
        fetch_calls["count"] += 1
        return fake_history

    with patch("routes.risk.fetcher") as mock_fetcher, \
         patch("services.container.realtime") as mock_rt:
        mock_fetcher.get_price_history.side_effect = fake_get_price_history
        mock_fetcher.get_macro_data.return_value = {"vix": 18.0}
        mock_rt.get_prices_batch.return_value = {
            "AAPL": {"price": 175.0},
            "MSFT": {"price": 350.0},
        }

        # Prime cache with 1 position.
        client.get("/api/risk/summary")
        baseline = fetch_calls["count"]

        # Add a 2nd position → signature changes → cache invalidates.
        add_position(auth_user["id"], ticker="MSFT", shares=5, avg_cost=300)

        client.get("/api/risk/summary")
        assert fetch_calls["count"] > baseline, (
            "Adding a position must invalidate the cache (signature change). "
            f"baseline={baseline} after_change={fetch_calls['count']}"
        )
