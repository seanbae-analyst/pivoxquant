"""Unit tests: scripts/nightly/error_rate_check.py (O-A)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.nightly.error_rate_check import (  # noqa: E402
    SAMPLES_PER_DAY,
    MAX_SAMPLES,
    DEFAULT_BASELINE_DAYS,
    baseline_ready,
    compute_threshold,
    fetch_sentry_events_5min,
    load_state,
    main,
    save_state,
)


# ── _FakeResponse helper ─────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


# ── fetch_sentry_events_5min ─────────────────────────────────────────────────

def test_fetch_sentry_events_sums_counts(monkeypatch):
    # Sentry stats: [[ts, count], ...]
    body = json.dumps([[1700000000, 5], [1700000010, 3], [1700000020, 2]]).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: _FakeResponse(body),
    )
    assert fetch_sentry_events_5min("tok", "org", "proj") == 10


def test_fetch_sentry_events_empty(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: _FakeResponse(b"[]"),
    )
    assert fetch_sentry_events_5min("tok", "org", "proj") == 0


def test_fetch_sentry_events_http_error(monkeypatch):
    import urllib.error

    def _raise(*a, **kw):
        raise urllib.error.HTTPError(None, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    assert fetch_sentry_events_5min("bad", "org", "proj") == -1


def test_fetch_sentry_events_network_error(monkeypatch):
    import urllib.error

    def _raise(*a, **kw):
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    assert fetch_sentry_events_5min("tok", "org", "proj") == -1


# ── baseline_ready / compute_threshold ───────────────────────────────────────

def test_baseline_ready_below_required():
    samples = [{"events": 0}] * (SAMPLES_PER_DAY - 1)
    assert baseline_ready(samples, baseline_days=1) is False


def test_baseline_ready_meets_required():
    samples = [{"events": 0}] * SAMPLES_PER_DAY
    assert baseline_ready(samples, baseline_days=1) is True


def test_compute_threshold_insufficient_samples():
    """< 1 day of samples → None."""
    samples = [{"events": 1}] * 10
    assert compute_threshold(samples) is None


def test_compute_threshold_with_data():
    # All zeros → median = 0, MAD = 0 → threshold = 0.
    samples = [{"events": 0}] * SAMPLES_PER_DAY
    threshold = compute_threshold(samples)
    assert threshold is not None
    assert threshold == 0.0


def test_compute_threshold_robust_to_outliers():
    # 99% baseline at 1, 1% spike at 100 → median ≈ 1, threshold modest.
    samples = [{"events": 1}] * (SAMPLES_PER_DAY - 3) + [{"events": 100}] * 3
    threshold = compute_threshold(samples)
    assert threshold is not None
    # Spike should still be above threshold.
    assert threshold < 100
    # Threshold above the bulk-baseline.
    assert threshold >= 1


# ── main() integration ───────────────────────────────────────────────────────

def _seed_env(monkeypatch, tmp_path, mode="baseline"):
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "fake")
    monkeypatch.setenv("SENTRY_ORG_SLUG", "org")
    monkeypatch.setenv("SENTRY_PROJECT_SLUG", "proj")
    monkeypatch.setenv("PIVOX_ERROR_RATE_MODE", mode)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.STATE_PATH",
        tmp_path / "error_rate_history.json",
    )


def test_main_missing_sentry_env_skips(monkeypatch, tmp_path):
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.STATE_PATH",
        tmp_path / "e.json",
    )
    rc = main()
    assert rc == 0  # graceful skip


def test_main_baseline_mode_never_alerts(monkeypatch, tmp_path):
    _seed_env(monkeypatch, tmp_path, mode="baseline")
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.fetch_sentry_events_5min",
        lambda *a: 999,  # huge spike
    )

    called = {"slack": 0}

    def _fake_slack(_):
        called["slack"] += 1
        return True

    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.post_slack", _fake_slack
    )

    rc = main()
    assert rc == 0
    assert called["slack"] == 0  # never alerts in baseline mode

    # Sample was recorded.
    state = load_state()
    assert len(state["samples"]) == 1
    assert state["samples"][0]["events"] == 999
    assert state["mode"] == "baseline"


def test_main_alert_mode_skips_without_baseline(monkeypatch, tmp_path):
    """Alert mode requested but no baseline → no alert, just store sample."""
    _seed_env(monkeypatch, tmp_path, mode="alert")
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.fetch_sentry_events_5min",
        lambda *a: 999,
    )
    called = {"slack": 0}
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.post_slack",
        lambda _: called.__setitem__("slack", called["slack"] + 1) or True,
    )
    rc = main()
    assert rc == 0
    assert called["slack"] == 0


def test_main_alert_mode_with_baseline_fires(monkeypatch, tmp_path):
    """Alert mode + sufficient baseline + spike → alert fires."""
    _seed_env(monkeypatch, tmp_path, mode="alert")
    monkeypatch.setenv("PIVOX_ERROR_RATE_BASELINE_DAYS", "1")

    # Pre-seed state with 1 day of baseline samples at events=0.
    seed_samples = [{"ts": "2026-01-01T00:00:00+00:00", "events": 0}] * SAMPLES_PER_DAY
    save_state({
        "samples": seed_samples,
        "mode": "alert",
        "last_alert_at": None,
    })

    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.fetch_sentry_events_5min",
        lambda *a: 500,  # huge spike vs all-zero baseline
    )
    called = {"slack": 0}
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.post_slack",
        lambda _: called.__setitem__("slack", called["slack"] + 1) or True,
    )

    rc = main()
    assert rc == 2
    assert called["slack"] == 1
    state = load_state()
    assert state["last_alert_at"] is not None


def test_main_sample_cap_enforced(monkeypatch, tmp_path):
    """state.samples is capped at MAX_SAMPLES (oldest dropped)."""
    _seed_env(monkeypatch, tmp_path, mode="baseline")

    # Pre-seed at the cap.
    seed = [{"ts": f"2026-01-01T00:{i:02d}:00+00:00", "events": 0} for i in range(60)]
    seed = seed * (MAX_SAMPLES // 60 + 1)
    seed = seed[:MAX_SAMPLES]
    save_state({"samples": seed, "mode": "baseline", "last_alert_at": None})

    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.fetch_sentry_events_5min",
        lambda *a: 7,
    )
    rc = main()
    assert rc == 0
    state = load_state()
    assert len(state["samples"]) == MAX_SAMPLES  # didn't grow
    assert state["samples"][-1]["events"] == 7  # newest at tail


def test_main_fetch_failure_returns_1(monkeypatch, tmp_path):
    _seed_env(monkeypatch, tmp_path, mode="baseline")
    monkeypatch.setattr(
        "scripts.nightly.error_rate_check.fetch_sentry_events_5min",
        lambda *a: -1,
    )
    rc = main()
    assert rc == 1
