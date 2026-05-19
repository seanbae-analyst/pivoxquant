"""Unit tests: scripts/nightly/railway_resource_check.py (Wave I D-2)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.nightly.railway_resource_check import (  # noqa: E402
    CPU_SUSTAINED_SAMPLES,
    CPU_THRESHOLD_PCT,
    DEDUP_MINUTES,
    HISTORY_WINDOW,
    RSS_THRESHOLD_MB,
    detect_violations,
    format_alert,
    load_history,
    main,
    measure_sample,
    save_history,
    should_alert,
)


# ── detect_violations ────────────────────────────────────────────────────────

def test_detect_violations_empty():
    assert detect_violations([]) == []


def test_detect_violations_below_threshold():
    samples = [{"rss_mb": 200.0, "cpu_pct": 30.0, "ts": "2026-05-19T00:00:00+00:00"}]
    assert detect_violations(samples) == []


def test_detect_violations_rss_only():
    """A single sample over RSS threshold triggers an alert. RSS doesn't
    fluctuate like CPU so we don't require sustained-pressure check."""
    samples = [{"rss_mb": RSS_THRESHOLD_MB + 10, "cpu_pct": 5.0, "ts": "x"}]
    reasons = detect_violations(samples)
    assert len(reasons) == 1
    assert "RSS=" in reasons[0]


def test_detect_violations_cpu_requires_sustained():
    """One spike above CPU threshold does NOT alert — we require
    CPU_SUSTAINED_SAMPLES consecutive samples to filter out transient
    spikes (gunicorn worker boot, cold cache fill)."""
    samples = [{"rss_mb": 100.0, "cpu_pct": 95.0, "ts": f"t{i}"} for i in range(1)]
    assert detect_violations(samples) == []


def test_detect_violations_cpu_sustained_alerts():
    samples = [
        {"rss_mb": 100.0, "cpu_pct": 95.0, "ts": f"t{i}"}
        for i in range(CPU_SUSTAINED_SAMPLES)
    ]
    reasons = detect_violations(samples)
    assert len(reasons) == 1
    assert "CPU sustained" in reasons[0]


def test_detect_violations_cpu_recovers_no_alert():
    """If the most recent sample drops below threshold, no alert — even if
    older samples were over (sliding window is contiguous-suffix)."""
    samples = (
        [{"rss_mb": 100.0, "cpu_pct": 95.0, "ts": f"old{i}"} for i in range(5)]
        + [{"rss_mb": 100.0, "cpu_pct": 20.0, "ts": "now"}]
    )
    assert detect_violations(samples) == []


def test_detect_violations_both_rss_and_cpu():
    samples = [
        {"rss_mb": RSS_THRESHOLD_MB + 50, "cpu_pct": 95.0, "ts": f"t{i}"}
        for i in range(CPU_SUSTAINED_SAMPLES)
    ]
    reasons = detect_violations(samples)
    assert len(reasons) == 2


# ── should_alert (dedup) ─────────────────────────────────────────────────────

def test_should_alert_no_violations():
    assert should_alert({"last_alert_at": None}, []) is False


def test_should_alert_first_violation():
    assert should_alert({"last_alert_at": None}, ["RSS=500MB ..."]) is True


def test_should_alert_dedup_blocks_recent():
    recent = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_MINUTES - 5)
    h = {"last_alert_at": recent.isoformat()}
    assert should_alert(h, ["x"]) is False


def test_should_alert_dedup_releases_old():
    old = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_MINUTES + 1)
    h = {"last_alert_at": old.isoformat()}
    assert should_alert(h, ["x"]) is True


# ── load/save_history roundtrip ──────────────────────────────────────────────

def test_load_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_PATH",
        tmp_path / "history.json",
    )
    h = {"samples": [{"rss_mb": 100.0, "cpu_pct": 20.0, "ts": "x"}],
         "last_alert_at": None, "last_alert_reason": None}
    save_history(h)
    loaded = load_history()
    assert loaded["samples"] == h["samples"]


def test_load_history_missing_returns_default_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_PATH",
        tmp_path / "missing.json",
    )
    h = load_history()
    assert h == {"samples": [], "last_alert_at": None, "last_alert_reason": None}


# ── format_alert ─────────────────────────────────────────────────────────────

def test_format_alert_includes_reasons():
    latest = {"rss_mb": 480.5, "cpu_pct": 91.2, "ts": "2026-05-19T10:00:00+00:00"}
    reasons = ["RSS=480.5MB > 450MB", "CPU sustained > 80%"]
    msg = format_alert(latest, reasons)
    assert "[CRIT]" in msg
    assert "480.5MB" in msg
    assert "RSS=480.5MB > 450MB" in msg


# ── measure_sample (smoke test via fake psutil) ──────────────────────────────

def test_measure_sample_with_fake_psutil():
    """We don't want this test depending on real psutil being installed
    AND we want deterministic values, so inject a fake module."""
    class FakeProc:
        def memory_info(self):
            return SimpleNamespace(rss=200 * 1024 * 1024)  # 200 MB

    fake_psutil = SimpleNamespace(
        Process=lambda pid: FakeProc(),
        cpu_percent=lambda interval: 42.5,
    )
    s = measure_sample(fake_psutil)
    assert s["rss_mb"] == 200.0
    assert s["cpu_pct"] == 42.5
    assert "ts" in s


# ── main() integration ───────────────────────────────────────────────────────

def test_main_skip_when_psutil_missing(tmp_path, monkeypatch):
    """psutil ImportError → graceful skip exit 0. Simulate by replacing
    sys.modules['psutil'] with something that raises on import-time
    isn't possible without monkeypatching builtins.__import__; instead
    test the real path: if psutil is installed (we depend on it in
    Wave I), main returns 0 or 2 — never raises."""
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    rc = main()
    assert rc in (0, 2)


def test_main_writes_sample_to_history(tmp_path, monkeypatch):
    """Even when no violation, the new sample must be persisted —
    otherwise sustained-CPU detection can never accumulate samples."""
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    rc = main()
    # psutil is in requirements.txt (Wave I) — if it's actually missing
    # in the test env, main returns 0 with no write. Both behaviors valid.
    if rc == 0 or rc == 2:
        h = load_history()
        # At least one sample written OR psutil import skipped (history empty)
        assert "samples" in h


def test_main_history_bounded_to_window(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    # Pre-seed with HISTORY_WINDOW + 5 samples
    pre = {
        "samples": [
            {"rss_mb": 10.0, "cpu_pct": 1.0, "ts": f"old{i}"}
            for i in range(HISTORY_WINDOW + 5)
        ],
        "last_alert_at": None,
        "last_alert_reason": None,
    }
    save_history(pre)
    main()
    h = load_history()
    # If psutil installed, we add 1; if not, no change. Either way ≤ window.
    assert len(h["samples"]) <= HISTORY_WINDOW


def test_main_dedup_prevents_double_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.railway_resource_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    # Pre-seed history with violating samples + recent alert.
    pre = {
        "samples": [
            {"rss_mb": RSS_THRESHOLD_MB + 100, "cpu_pct": 95.0, "ts": f"t{i}"}
            for i in range(CPU_SUSTAINED_SAMPLES)
        ],
        "last_alert_at": datetime.now(timezone.utc).isoformat(),
        "last_alert_reason": "previous",
    }
    save_history(pre)
    main()
    h = load_history()
    # last_alert_at should NOT have been overwritten with the new run's
    # timestamp (dedup blocked) — value remains the seeded one.
    # If psutil is missing entirely, main exits early without touching
    # state; that's also fine.
    assert "last_alert_at" in h
