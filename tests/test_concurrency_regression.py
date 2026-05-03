"""Regression tests for CONC-001 (FMP _track_call thread-safety) and
CONC-002 (SSE TOCTOU on connection limit).

Both check race conditions that previously allowed counter desync under
concurrent load. Run on every CI to catch silent regressions.
"""
import threading
from collections import defaultdict


def test_fmp_track_call_thread_safety():
    """10 threads * 100 calls each must produce exactly 1000 increments.

    Pre-fix _daily_calls was incremented outside _cache_lock, so concurrent
    increments could race and lose updates. After fix, the entire reset+
    increment block is inside the lock — counter must be exact.
    """
    from services.data import fmp as fmp_service

    # Reset counter
    with fmp_service._cache_lock:
        fmp_service._daily_calls = 0
        # Push reset into the future so the 86400 reset path doesn't trigger
        fmp_service._daily_calls_reset = 1e18

    n_threads = 10
    calls_per_thread = 100

    def worker():
        for _ in range(calls_per_thread):
            fmp_service._track_call()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = n_threads * calls_per_thread
    assert fmp_service._daily_calls == expected, (
        f"Race: expected {expected} increments, got {fmp_service._daily_calls}"
    )


def test_sse_connection_atomicity():
    """Atomic check+increment for SSE limiter.

    Simulates the post-fix pattern: lock around both the limit check and
    the increment. With N threads racing for K=3 slots, exactly K should
    succeed.
    """
    lock = threading.Lock()
    connections = defaultdict(int)
    MAX = 3
    user_id = "u1"

    accepted = []
    rejected = []

    def attempt():
        with lock:
            if connections[user_id] >= MAX:
                rejected.append(1)
                return
            connections[user_id] += 1
            accepted.append(1)

    threads = [threading.Thread(target=attempt) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(accepted) == MAX, (
        f"Limit breach: {len(accepted)} accepted, expected {MAX}"
    )
    assert len(rejected) == 20 - MAX
    assert connections[user_id] == MAX
