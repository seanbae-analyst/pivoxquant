"""Render Free keep-awake through the KST day window (2026-10-10).

``app._self_keepalive_ping`` requests the service's own public URL so Render
counts inbound traffic and does not spin the instance down; ``_init_scheduler``
fires it every 10 minutes from 08:00 to 23:50 KST.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

import app as app_module


class _Resp:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_no_render_url_is_a_no_op(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    with patch("requests.get") as get:
        assert app_module._self_keepalive_ping() is None
    get.assert_not_called()


def test_pings_own_health_endpoint(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://pivoxquant-api.onrender.com/")
    with patch("requests.get", return_value=_Resp(200)) as get:
        assert app_module._self_keepalive_ping() == 200
    get.assert_called_once_with("https://pivoxquant-api.onrender.com/api/health", timeout=10)


def test_refuses_a_non_https_url(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "http://example.internal")
    with patch("requests.get") as get:
        assert app_module._self_keepalive_ping() is None
    get.assert_not_called()


def test_a_failed_request_never_raises(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://pivoxquant-api.onrender.com")
    with patch("requests.get", side_effect=OSError("network down")):
        assert app_module._self_keepalive_ping() is None


def _scheduled_jobs():
    from apscheduler.schedulers.background import BackgroundScheduler

    captured = {}
    real_init = BackgroundScheduler.__init__

    def _capture_init(self, *a, **kw):
        real_init(self, *a, **kw)
        captured["sched"] = self

    with patch.object(BackgroundScheduler, "__init__", _capture_init), \
         patch.object(BackgroundScheduler, "start", lambda self, *a, **k: None), \
         patch.object(app_module, "_try_acquire_scheduler_lock", return_value=True):
        app_module._init_scheduler(app_module.app)
    return {j.id: j for j in captured["sched"].get_jobs()}


def test_registered_every_10_minutes_08_to_24_kst():
    from apscheduler.triggers.cron import CronTrigger

    job = _scheduled_jobs()["self_keepalive"]
    assert isinstance(job.trigger, CronTrigger)
    assert str(job.trigger.timezone) == "Asia/Seoul"
    assert job.max_instances == 1
    assert job.coalesce is True

    seoul = ZoneInfo("Asia/Seoul")
    fire = job.trigger.get_next_fire_time(None, datetime(2026, 10, 10, 7, 55, tzinfo=seoul))
    assert (fire.hour, fire.minute) == (8, 0)
    fire = job.trigger.get_next_fire_time(None, datetime(2026, 10, 10, 13, 1, tzinfo=seoul))
    assert (fire.hour, fire.minute) == (13, 10)
    # Last ping 23:50; the instance may sleep after ~00:05 until the next morning.
    fire = job.trigger.get_next_fire_time(None, datetime(2026, 10, 10, 23, 51, tzinfo=seoul))
    assert (fire.day, fire.hour, fire.minute) == (11, 8, 0)


# ── Deploy overlap: the new instance keeps trying for the scheduler lock ──


def test_lock_lost_at_boot_is_retried_and_the_scheduler_starts():
    class _Sched:
        started = 0

        def start(self):
            self.started += 1

    sched = _Sched()
    answers = iter([False, False, True])
    with patch.object(app_module, "_try_acquire_scheduler_lock", side_effect=lambda **_: next(answers)):
        t = app_module._retry_scheduler_lock_in_background(sched, interval_s=0.01, window_s=5)
        t.join(timeout=5)
    assert sched.started == 1


def test_lock_retry_gives_up_after_its_window():
    class _Sched:
        started = 0

        def start(self):
            self.started += 1

    sched = _Sched()
    with patch.object(app_module, "_try_acquire_scheduler_lock", return_value=False):
        t = app_module._retry_scheduler_lock_in_background(sched, interval_s=0.01, window_s=0.05)
        t.join(timeout=5)
    assert not t.is_alive()
    assert sched.started == 0


def test_init_scheduler_retries_when_the_lock_is_held_elsewhere():
    from apscheduler.schedulers.background import BackgroundScheduler

    with patch.object(BackgroundScheduler, "start", lambda self, *a, **k: None), \
         patch.object(app_module, "_try_acquire_scheduler_lock", return_value=False), \
         patch.object(app_module, "_retry_scheduler_lock_in_background") as retry:
        app_module._init_scheduler(app_module.app)
    retry.assert_called_once()


# ── 2026-10-15: an error during the retry never starts a lockless scheduler ──


class _FakeCursor:
    def __init__(self, held: bool):
        self.held = held

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a):
        pass

    def fetchone(self):
        return (not self.held,)


class _FakeConn:
    autocommit = False

    def __init__(self, held: bool):
        self.held = held

    def cursor(self):
        return _FakeCursor(self.held)

    def close(self):
        pass


def _fake_pg(monkeypatch, script):
    """``psycopg2.connect`` answers from ``script``: "held" (another process
    has the lock), "free" (we get it) or "error" (the pooler drops us)."""
    import config
    import psycopg2

    steps = iter(script)

    def _connect(*a, **k):
        step = next(steps, "held")
        if step == "error":
            raise psycopg2.OperationalError("server closed the connection unexpectedly")
        return _FakeConn(held=step == "held")

    monkeypatch.setattr(config, "IS_POSTGRES", True)
    monkeypatch.setattr(psycopg2, "connect", _connect)
    monkeypatch.setattr(app_module, "_SCHEDULER_LOCK_CONN", None)


def test_boot_attempt_keeps_its_fail_safe(monkeypatch):
    """Boot cannot tell whether anyone holds the lock → start (never lose crons)."""
    _fake_pg(monkeypatch, ["error"])
    assert app_module._try_acquire_scheduler_lock() is True
    assert app_module._SCHEDULER_LOCK_CONN is None


def test_retry_error_while_the_lock_is_held_does_not_start(monkeypatch):
    """Deploy overlap: boot saw the lock held (2 attempts), then the pooler
    drops one retry. That must not start a second scheduler without the lock."""
    _fake_pg(monkeypatch, ["held", "held", "held", "held", "error", "held", "held"])

    class _Sched:
        started = 0

        def start(self):
            self.started += 1

    assert app_module._try_acquire_scheduler_lock() is False
    sched = _Sched()
    t = app_module._retry_scheduler_lock_in_background(sched, interval_s=0.01, window_s=0.3)
    t.join(timeout=5)
    assert not t.is_alive()
    assert sched.started == 0
    assert app_module._SCHEDULER_LOCK_CONN is None


def test_retry_after_an_error_starts_once_the_lock_is_free(monkeypatch):
    _fake_pg(monkeypatch, ["held", "held", "error", "free"])

    class _Sched:
        started = 0

        def start(self):
            self.started += 1

    assert app_module._try_acquire_scheduler_lock() is False
    sched = _Sched()
    t = app_module._retry_scheduler_lock_in_background(sched, interval_s=0.01, window_s=5)
    t.join(timeout=5)
    assert sched.started == 1
    assert app_module._SCHEDULER_LOCK_CONN is not None


def test_errored_attempt_closes_its_connection(monkeypatch):
    """An error after connecting (the lock query dies) holds no lock — the
    connection is closed, so repeated errored retries do not pile up open
    connections against the pooler's limit."""
    import config
    import psycopg2

    closed = []

    class _DyingCursor(_FakeCursor):
        def execute(self, *a):
            raise psycopg2.OperationalError("SSL SYSCALL error: EOF detected")

    class _DyingConn(_FakeConn):
        def cursor(self):
            return _DyingCursor(self.held)

        def close(self):
            closed.append(self)

    monkeypatch.setattr(config, "IS_POSTGRES", True)
    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: _DyingConn(held=True))
    monkeypatch.setattr(app_module, "_SCHEDULER_LOCK_CONN", None)

    with pytest.raises(psycopg2.OperationalError):
        app_module._try_acquire_scheduler_lock(fail_safe=False)
    assert len(closed) == 1
    assert app_module._try_acquire_scheduler_lock() is True  # boot keeps its fail-safe
    assert len(closed) == 2
    assert app_module._SCHEDULER_LOCK_CONN is None
