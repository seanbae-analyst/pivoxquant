"""웹 프로세스 안에서 도는 야간 잡의 임시 create_app() 이 스케줄러를 또 만들지 않는다.

배경 (2026-09-29)
=================
``_wrap_python_main`` 이 인프로세스 APScheduler 에서 부르는 잡들은 매 틱마다
``create_app()`` 으로 임시 앱을 세운다. 이들은 ``os.environ.setdefault(
"RUN_SCHEDULER", "0")`` 로 스케줄러를 끄려 했지만, prod 웹 프로세스엔 이미
``RUN_SCHEDULER=1`` 이 있어서 setdefault 는 아무것도 하지 않았다. 그러면 임시
앱마다 ``_init_scheduler`` 가 돌아 두 번째 스케줄러를 만들고
``register_scheduler(sched)`` 가 살아있는 ``alerts._scheduler_ref`` 를 시작도 안 한
스케줄러로 바꿔치기했다 → 3-strike 자동 정지가 죽은 스케줄러를 멈췄다.

환경변수는 프로세스 전역이라 고쳐 쓰면 안 된다 — ``create_app`` 키워드로 끈다.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class _Stop(Exception):
    pass


def _capture_create_app_kwargs(call):
    """``app.create_app`` 을 가로채 kwargs 만 기록하고 즉시 멈춘다."""
    import app as app_module

    seen: dict = {}

    def _fake(*a, **kw):
        seen.update(kw)
        raise _Stop()

    with patch.object(app_module, "create_app", _fake), \
         patch.dict(os.environ, {"RUN_SCHEDULER": "1",
                                 "POPULATE_CACHE_ON_BOOT": "1"}):
        try:
            call()
        except _Stop:
            pass
        # 프로세스 전역 env 를 건드리지 않는다.
        assert os.environ["RUN_SCHEDULER"] == "1"
        assert os.environ["POPULATE_CACHE_ON_BOOT"] == "1"
    return seen


def _reports_delivery():
    from services import reports_delivery
    return reports_delivery.main()


def _pipa_purge():
    from scripts.nightly import pipa_purge
    return pipa_purge.main()


def _oauth_failure_check():
    from scripts.nightly import oauth_failure_check
    return oauth_failure_check.main()


def _email_scheduler():
    from scripts.nightly import email_scheduler_dispatcher
    return email_scheduler_dispatcher._drain_once()


def _checkout_followup():
    from scripts.nightly import checkout_followup_dispatcher
    return checkout_followup_dispatcher._drain_once_locked()


def _inactive_nudge():
    from scripts.nightly import inactive_nudge_dispatcher
    return inactive_nudge_dispatcher.main()


def _friction_outcome_report():
    # 수동 CLI 리포트 — 스케줄러 틱이 아니어도 임시 앱은 같은 키워드로 끈다
    # (.env 가 override=True 라 셸의 RUN_SCHEDULER=0 도 덮인다, CLAUDE.md 함정 2).
    import sys

    from scripts import friction_outcome_report
    with patch.object(sys, "argv", ["friction_outcome_report.py"]):
        return friction_outcome_report.main()


@pytest.mark.parametrize("call", [
    _reports_delivery, _pipa_purge, _oauth_failure_check,
    _email_scheduler, _checkout_followup, _inactive_nudge,
    _friction_outcome_report,
], ids=lambda f: f.__name__.lstrip("_"))
def test_transient_callers_disable_scheduler_and_warmup(app, call):
    kw = _capture_create_app_kwargs(call)
    assert kw.get("start_scheduler") is False, kw
    assert kw.get("populate_cache") is False, kw


def test_create_app_start_scheduler_false_beats_env():
    """RUN_SCHEDULER=1 인 프로세스에서도 start_scheduler=False 면 안 만든다."""
    import app as app_module

    with patch.dict(os.environ, {"RUN_SCHEDULER": "1",
                                 "POPULATE_CACHE_ON_BOOT": "1"}), \
         patch.object(app_module, "_init_scheduler") as mock_init, \
         patch.object(app_module, "_populate_cache") as mock_pop:
        app_module.create_app(start_scheduler=False, populate_cache=False)
    mock_init.assert_not_called()
    mock_pop.assert_not_called()


def test_create_app_default_still_follows_env():
    """키워드 없이 부르면 옛 동작(env) 그대로."""
    import app as app_module

    with patch.dict(os.environ, {"RUN_SCHEDULER": "1",
                                 "POPULATE_CACHE_ON_BOOT": "0"}), \
         patch.object(app_module, "_init_scheduler") as mock_init:
        app_module.create_app()
    mock_init.assert_called_once()
