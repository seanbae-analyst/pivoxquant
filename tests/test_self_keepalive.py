"""Render Free keep-awake through the KST day window (2026-10-10).

``app._self_keepalive_ping`` requests the service's own public URL so Render
counts inbound traffic and does not spin the instance down; ``_init_scheduler``
fires it every 10 minutes from 08:00 to 23:50 KST.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

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
