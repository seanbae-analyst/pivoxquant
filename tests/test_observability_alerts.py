"""Tests for ``services.observability.alerts`` — cron failure alerting.

Coverage
========
- ``emit_failure`` is a no-op (no raise) when SLACK_WEBHOOK_URL unset.
- ``emit_failure`` bumps the per-job counter on each call.
- ``record_success`` resets the counter.
- 3-strike threshold triggers auto-pause via the registered scheduler.
- ``emit_failure`` never raises, even when Slack / Sentry / scheduler all
  fail simultaneously (defence-in-depth for the alerting path itself).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.observability import alerts  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Each test starts with empty counters + no scheduler + no webhook."""
    alerts._reset_all_for_test()
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    # Ensure no stale scheduler reference between tests.
    alerts._scheduler_ref = None
    yield
    alerts._reset_all_for_test()
    alerts._scheduler_ref = None


def test_emit_failure_no_env_is_silent_noop(caplog):
    """SLACK_WEBHOOK_URL unset → no exception, logger.exception emitted once."""
    caplog.set_level(logging.ERROR, logger="services.observability.alerts")
    # Must not raise.
    alerts.emit_failure("job_x", RuntimeError("boom"))
    # Counter still bumped (so we can detect repeat fails even without Slack).
    assert alerts.get_failure_count("job_x") == 1
    # logger.exception should have been called (it's the cheapest signal).
    assert any("job_x" in r.message for r in caplog.records)


def test_emit_failure_counter_increments_per_call():
    for _ in range(2):
        alerts.emit_failure("job_y", ValueError("nope"))
    assert alerts.get_failure_count("job_y") == 2


def test_record_success_resets_counter():
    alerts.emit_failure("job_z", RuntimeError("transient"))
    assert alerts.get_failure_count("job_z") == 1
    alerts.record_success("job_z")
    assert alerts.get_failure_count("job_z") == 0
    # And subsequent failure starts fresh.
    alerts.emit_failure("job_z", RuntimeError("again"))
    assert alerts.get_failure_count("job_z") == 1


def test_three_strikes_triggers_pause_job():
    """At PAUSE_THRESHOLD consecutive failures, scheduler.pause_job is called."""
    scheduler = MagicMock()
    alerts.register_scheduler(scheduler)

    for _ in range(alerts.PAUSE_THRESHOLD):
        alerts.emit_failure("ops_flaky", RuntimeError("upstream 500"))

    scheduler.pause_job.assert_called_once_with("ops_flaky")


def test_below_threshold_does_not_pause():
    scheduler = MagicMock()
    alerts.register_scheduler(scheduler)
    # 2 fails — under PAUSE_THRESHOLD=3.
    alerts.emit_failure("ops_jitter", RuntimeError("blip"))
    alerts.emit_failure("ops_jitter", RuntimeError("blip"))
    scheduler.pause_job.assert_not_called()


def test_emit_failure_swallows_slack_exception(monkeypatch):
    """Even if Slack POST raises, emit_failure returns cleanly."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://example.invalid/hook")

    def _boom(*_a, **_kw):
        raise RuntimeError("network down")

    # Patch the requests module's post used inside _slack_post.
    import requests  # noqa: PLC0415
    monkeypatch.setattr(requests, "post", _boom)

    # Must NOT raise — alerting path is defence-in-depth.
    alerts.emit_failure("job_q", RuntimeError("orig"))
    assert alerts.get_failure_count("job_q") == 1


def test_emit_failure_swallows_pause_job_exception():
    """Even if pause_job raises (job_id mismatch), emit_failure returns."""
    scheduler = MagicMock()
    scheduler.pause_job.side_effect = RuntimeError("unknown job id")
    alerts.register_scheduler(scheduler)

    # 3 fails — pause attempted but raises; emit_failure must still return.
    for _ in range(alerts.PAUSE_THRESHOLD):
        alerts.emit_failure("ops_bad_id", RuntimeError("x"))

    scheduler.pause_job.assert_called_once_with("ops_bad_id")
    # Counter still at threshold.
    assert alerts.get_failure_count("ops_bad_id") == alerts.PAUSE_THRESHOLD


def test_context_dict_stringified_and_safe():
    """Non-string context values must not break alerting."""
    # Must not raise on int / None / nested dict — all coerced to str.
    alerts.emit_failure(
        "job_ctx",
        RuntimeError("ctx test"),
        context={"attempt": 3, "url": None, "nested": {"a": 1}},
    )
    assert alerts.get_failure_count("job_ctx") == 1
