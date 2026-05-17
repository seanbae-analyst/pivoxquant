"""tests/test_fmp_rate_limit.py — sliding-window per-minute throttle.

Wave 13 P1 (PR #440) — pre-fix the FMP wrapper enforced only the DAILY
soft cap; a bursty prefetch could exceed the 750 req/min plan ceiling,
trigger a 429, and disable FMP for the rest of the day via the
reactive ``_daily_calls = max(_daily_calls, _BUDGET_HARD_STOP)`` clamp.
The new ``_throttle_per_minute`` keeps callers inside the window.

These tests use module-level state monkeypatching so we don't hit the
real network. Each test resets the deque + the rate limit constant
before exercising so they don't leak state to each other.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_fmp_state():
    """Drain the deque between tests so each starts clean."""
    from services.data import fmp as fmp_mod
    fmp_mod._recent_call_ts.clear()
    yield
    fmp_mod._recent_call_ts.clear()


def test_throttle_no_sleep_when_window_has_room(monkeypatch):
    """Default condition: window has slots → no sleep."""
    from services.data import fmp as fmp_mod
    monkeypatch.setattr(fmp_mod, "_RATE_LIMIT_PER_MIN", 10)

    with patch.object(fmp_mod.time, "sleep") as mock_sleep:
        for _ in range(5):
            fmp_mod._throttle_per_minute()

    mock_sleep.assert_not_called()
    assert len(fmp_mod._recent_call_ts) == 5


def test_throttle_sleeps_when_window_full(monkeypatch):
    """When the per-minute slot is full, we sleep just enough to age
    the oldest call out of the window — not the full window length."""
    from services.data import fmp as fmp_mod
    monkeypatch.setattr(fmp_mod, "_RATE_LIMIT_PER_MIN", 3)
    # Ceiling > the expected sleep so the throttle actually sleeps
    # instead of bailing through the safety-valve.
    monkeypatch.setattr(fmp_mod, "_RATE_MAX_SLEEP_SEC", 60.0)

    # Pre-load 3 calls 5 seconds apart starting 30s ago — oldest is 30s
    # in the past, so the throttle should sleep 30s (60-30).
    now = time.time()
    for offset in (30.0, 25.0, 20.0):
        fmp_mod._recent_call_ts.append(now - offset)

    with patch.object(fmp_mod.time, "sleep") as mock_sleep:
        fmp_mod._throttle_per_minute()

    # First call to sleep should be ~30s (60 - 30 since oldest), bounded.
    mock_sleep.assert_called()
    sleep_arg = mock_sleep.call_args_list[0].args[0]
    # Tolerance for the time.time() in between.
    assert 29.0 <= sleep_arg <= 31.0, f"sleep arg {sleep_arg} outside expected range"


def test_throttle_bails_when_required_sleep_exceeds_ceiling(monkeypatch):
    """Defensive ceiling: if the throttle would sleep > _RATE_MAX_SLEEP_SEC,
    let the call through immediately rather than wedging the request
    thread. The existing 429 path absorbs the overflow."""
    from services.data import fmp as fmp_mod
    monkeypatch.setattr(fmp_mod, "_RATE_LIMIT_PER_MIN", 3)
    monkeypatch.setattr(fmp_mod, "_RATE_MAX_SLEEP_SEC", 2.0)

    now = time.time()
    # Oldest call just 1s ago → would need to sleep 59s. Way over ceiling.
    for offset in (1.0, 0.5, 0.1):
        fmp_mod._recent_call_ts.append(now - offset)

    with patch.object(fmp_mod.time, "sleep") as mock_sleep:
        fmp_mod._throttle_per_minute()

    # Sleep must NOT have been called — the ceiling guard returned early.
    mock_sleep.assert_not_called()


def test_throttle_drops_aged_timestamps(monkeypatch):
    """Slot ages > window must be dropped from the deque so they don't
    permanently occupy a slot."""
    from services.data import fmp as fmp_mod
    monkeypatch.setattr(fmp_mod, "_RATE_LIMIT_PER_MIN", 5)

    now = time.time()
    # 3 stale (>60s) + 2 fresh (<60s) = window starts with 2 effective slots.
    for offset in (120.0, 100.0, 90.0, 10.0, 5.0):
        fmp_mod._recent_call_ts.append(now - offset)

    with patch.object(fmp_mod.time, "sleep") as mock_sleep:
        fmp_mod._throttle_per_minute()

    # No sleep expected — capacity 5, 2 fresh + the new one = 3 ≤ 5.
    mock_sleep.assert_not_called()
    # Stale ones were dropped during the cleanup.
    assert len(fmp_mod._recent_call_ts) == 3
    # All surviving timestamps must be within the window.
    cutoff = time.time() - fmp_mod._RATE_WINDOW_SEC
    assert all(ts >= cutoff for ts in fmp_mod._recent_call_ts)


def test_throttle_env_var_override(monkeypatch):
    """Module constant honors FMP_RATE_LIMIT_PER_MIN at import time;
    we patch it directly to verify the ceiling actually drives behavior.
    """
    from services.data import fmp as fmp_mod
    monkeypatch.setattr(fmp_mod, "_RATE_LIMIT_PER_MIN", 1)

    with patch.object(fmp_mod.time, "sleep") as mock_sleep:
        # First call slips in.
        fmp_mod._throttle_per_minute()
        assert mock_sleep.call_count == 0
        # Second call hits the ceiling but ages the only slot since
        # the deque only holds 1 call. Pre-load an old slot so we
        # also see the aged-drop path.
        fmp_mod._recent_call_ts.appendleft(time.time() - 120)
        fmp_mod._throttle_per_minute()
        # Still no sleep because the manual-aged slot dropped + the
        # in-window slot is the only one left.
        assert mock_sleep.call_count == 0
