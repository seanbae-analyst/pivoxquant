"""Wave H — APScheduler 19 ops cron jobs 등록 검증.

배경
====
macOS crontab 19 entries → Railway in-process APScheduler 이전.
``services/scheduler/cron_jobs.py:register_cron_jobs()`` 가 정확히 19개
job 을 등록하고, 모든 cron trigger 가 ``timezone='Asia/Seoul'`` 을 명시하며,
``RUN_SCHEDULER=0`` 환경에서는 ``app.py:_init_scheduler`` 가 호출되지 않아
ops job 도 등록되지 않음을 검증.

테스트 범위
===========
- 19 jobs 정확히 등록 (overcount/undercount 회귀 방지)
- 모든 cron trigger 에 timezone='Asia/Seoul' 명시 (Railway UTC default 회귀 방지)
- 각 job 의 trigger 가 macOS crontab 의 cron expression 과 일치 (시간 슬롯
  변경 회귀 방지)
- max_instances=1 + coalesce=True (멱등성 회귀 방지)
- job id 가 ``ops_`` prefix (artifact 스케줄러 job 과 namespace 충돌 방지)
- subprocess wrapper 가 존재하지 않는 shell script 에도 graceful (return,
  not raise) — Railway 컨테이너에 scripts/ 누락 시에도 scheduler 안 죽음
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Ensure repo root on sys.path (mirrors conftest pattern).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.scheduler import register_cron_jobs  # noqa: E402
from services.scheduler.cron_jobs import _job_specs  # noqa: E402


# ── Expected 19 jobs ────────────────────────────────────────────────────────

EXPECTED_JOB_IDS = {
    # Wave H — 19 macOS crontab → Railway APScheduler 이전
    "ops_api_health",
    "ops_db_backup",
    "ops_ssl_expiry",
    "ops_vercel_canary",
    "ops_daily_regression",
    "ops_sendgrid_quota",
    "ops_morning_brief_kpi",
    "ops_signup_funnel",
    "ops_credentials_expiry",
    "ops_env_audit",
    "ops_error_rate",
    "ops_ticker_name_audit",
    "ops_email_compliance",
    "ops_section101_check",
    "ops_checkout_followup",
    "ops_email_scheduler",
    "ops_inactive_nudge",
    "ops_caus_daily_sweep",
    "ops_finance_weekly_check",
    # Wave I — 추가 4개 (FX staleness / Anthropic cost / Railway resource / Domain WHOIS)
    "ops_fx_staleness_check",
    "ops_anthropic_cost_estimate",
    "ops_railway_resource",
    "ops_domain_expiry",
    # Wave I L-3 — 통신판매업 신고 D-day 월간 알림 (feature-flagged via
    # PIVOX_COMMERCE_REGISTERED). 1st of month 09:00 KST.
    "ops_commerce_registration",
    # Wave I C-1/C-2 — OAuth failure detector + PIPA §21 30-day purge.
    "ops_oauth_failure_check",
    "ops_pipa_purge",
    # Viral loop (2026-05-26) — 주간 퍼널 스냅샷 (K-factor/WAMR → Slack).
    "ops_weekly_funnel_snapshot",
}
# 19 (Wave H) + 4 (Wave I) + 1 (L-3) + 2 (C-1/C-2) + 1 (viral) = 27
EXPECTED_JOB_COUNT = 27


@pytest.fixture
def fresh_sched():
    """Fresh APScheduler — not started, so no background threads leak."""
    s = BackgroundScheduler(timezone="UTC")
    yield s
    # Don't call shutdown() — never started.


def test_register_returns_expected_job_ids(fresh_sched):
    ids = register_cron_jobs(fresh_sched)
    assert len(ids) == EXPECTED_JOB_COUNT, (
        f"expected {EXPECTED_JOB_COUNT} ops jobs, got {len(ids)}: {ids}"
    )
    assert set(ids) == EXPECTED_JOB_IDS


def test_all_jobs_registered_on_scheduler(fresh_sched):
    register_cron_jobs(fresh_sched)
    job_ids = {j.id for j in fresh_sched.get_jobs()}
    assert EXPECTED_JOB_IDS.issubset(job_ids)


def test_all_cron_triggers_use_asia_seoul(fresh_sched):
    """Railway containers default to UTC.  Missing timezone='Asia/Seoul' →
    every KST cron fires 9 hours late (e.g. 06:00 KST job fires at 15:00 KST).
    """
    register_cron_jobs(fresh_sched)
    for job in fresh_sched.get_jobs():
        trigger = job.trigger
        if isinstance(trigger, CronTrigger):
            tz_str = str(trigger.timezone)
            assert tz_str == "Asia/Seoul", (
                f"{job.id} uses tz={tz_str!r}; must be 'Asia/Seoul'"
            )


def test_all_jobs_idempotent_safety(fresh_sched):
    """max_instances=1 + coalesce=True prevents missed-run stacking after
    worker restart or transient scheduler pause.  Without these flags, a
    20-minute scheduler outage on a */5 cron would queue 4 catch-up runs
    that all fire simultaneously when the worker resumes.
    """
    register_cron_jobs(fresh_sched)
    for job in fresh_sched.get_jobs():
        assert job.max_instances == 1, f"{job.id} max_instances={job.max_instances}"
        assert job.coalesce is True, f"{job.id} coalesce={job.coalesce}"


def test_job_ids_use_ops_namespace(fresh_sched):
    """ops_ prefix prevents collision with the artifact cron job ids
    registered earlier in app.py:_init_scheduler (refresh, weekly_memo_sunday,
    brag_card_monthly, fx_rate_refresh, ...).  Without namespace separation,
    replace_existing=True could accidentally overwrite an artifact job.
    """
    ids = register_cron_jobs(fresh_sched)
    for jid in ids:
        assert jid.startswith("ops_"), f"{jid} missing ops_ namespace prefix"


def test_register_is_idempotent(fresh_sched):
    """replace_existing=True means double-register is safe — useful for
    test isolation and for hypothetical scheduler hot-reload paths.
    """
    ids1 = register_cron_jobs(fresh_sched)
    ids2 = register_cron_jobs(fresh_sched)
    assert ids1 == ids2
    # Scheduler should still have exactly EXPECTED_JOB_COUNT jobs, not 2x.
    job_ids = {j.id for j in fresh_sched.get_jobs() if j.id.startswith("ops_")}
    assert len(job_ids) == EXPECTED_JOB_COUNT


# ── Cron expression mapping ─────────────────────────────────────────────────
# These mirror the macOS crontab entries from scripts/cron/run.sh — any
# change to the cron schedule MUST update both crontab + this test.

EXPECTED_TRIGGER_FIELDS = {
    "ops_api_health":         {"hour": "*/6", "minute": "0"},
    "ops_db_backup":          {"hour": "2", "minute": "0"},
    "ops_ssl_expiry":         {"day_of_week": "mon", "hour": "9", "minute": "0"},
    "ops_vercel_canary":      {"minute": "*/30"},
    "ops_daily_regression":   {"hour": "6", "minute": "0"},
    "ops_sendgrid_quota":     {"hour": "14", "minute": "0"},
    "ops_morning_brief_kpi":  {"hour": "6", "minute": "5"},
    "ops_signup_funnel":      {"minute": "*/5"},
    "ops_credentials_expiry": {"hour": "10", "minute": "0"},
    "ops_env_audit":          {"day_of_week": "mon", "hour": "11", "minute": "0"},
    "ops_error_rate":         {"minute": "*/5"},
    "ops_ticker_name_audit":  {"hour": "6", "minute": "30"},
    "ops_email_compliance":   {"day_of_week": "mon", "hour": "12", "minute": "0"},
    "ops_section101_check":   {"hour": "7", "minute": "0"},
    "ops_checkout_followup":  {"minute": "*/15"},
    "ops_email_scheduler":    {"minute": "1-59/15"},
    "ops_inactive_nudge":     {"minute": "0"},
    "ops_caus_daily_sweep":   {"hour": "3", "minute": "0"},
    "ops_finance_weekly_check": {"day_of_week": "sun", "hour": "9", "minute": "0"},
    # Wave I additions
    "ops_fx_staleness_check":    {"minute": "0"},
    "ops_anthropic_cost_estimate": {"hour": "22", "minute": "0"},
    "ops_railway_resource":      {"minute": "*/2"},
    "ops_domain_expiry":         {"day": "1", "hour": "9", "minute": "30"},
    # Wave I L-3 — 1st of month 09:00 KST
    "ops_commerce_registration": {"day": "1", "hour": "9", "minute": "0"},
    # Wave I C-1/C-2 — OAuth failure detector + PIPA purge
    "ops_oauth_failure_check":   {"minute": "*/15"},
    "ops_pipa_purge":            {"hour": "3", "minute": "30"},
}


def test_cron_expressions_match_macos_crontab(fresh_sched):
    """Defensive: a typo like hour=14 vs hour=4 silently shifts the run
    by 10 hours.  We verify the key trigger fields equal the macOS crontab
    source-of-truth string.
    """
    register_cron_jobs(fresh_sched)
    for job in fresh_sched.get_jobs():
        if job.id not in EXPECTED_TRIGGER_FIELDS:
            continue
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger), (
            f"{job.id} expected CronTrigger, got {type(trigger).__name__}"
        )
        # APScheduler stores fields as a list of CronField objects.
        field_map = {f.name: str(f) for f in trigger.fields}
        for fname, expected in EXPECTED_TRIGGER_FIELDS[job.id].items():
            actual = field_map.get(fname)
            assert actual == expected, (
                f"{job.id} field {fname!r} expected {expected!r}, got {actual!r}"
            )


# ── Job spec table introspection ────────────────────────────────────────────

def test_job_specs_table_length():
    specs = _job_specs()
    assert len(specs) == EXPECTED_JOB_COUNT


def test_job_specs_unique_ids():
    specs = _job_specs()
    ids = [s[0] for s in specs]
    assert len(ids) == len(set(ids)), "duplicate job ids in _job_specs()"


def test_job_specs_runners_callable():
    """Each runner must be callable so APScheduler can dispatch it."""
    specs = _job_specs()
    for jid, _trigger, runner in specs:
        assert callable(runner), f"{jid} runner not callable: {runner!r}"


# ── Defensive: shell wrapper survives missing script ────────────────────────

def test_shell_wrapper_missing_script_does_not_raise(tmp_path, caplog):
    """Railway image rebuild that accidentally drops scripts/nightly/db_backup.sh
    must NOT crash the scheduler thread — the wrapper logs warning + returns.
    """
    from services.scheduler.cron_jobs import _wrap_shell_script
    runner = _wrap_shell_script("scripts/nightly/__nonexistent__.sh", "missing")
    # Must not raise.
    runner()


def test_python_wrapper_swallows_exceptions(monkeypatch, caplog):
    """A failing main() must NOT escape the wrapper — otherwise APScheduler's
    job-dispatch thread dies and ALL ops jobs stop firing until next worker
    restart (silent outage).
    """
    from services.scheduler.cron_jobs import _wrap_python_main
    # Build a fake module that raises.
    import types
    fake_mod = types.ModuleType("scripts.__fake_test_mod__")
    def _boom():
        raise RuntimeError("simulated job failure")
    fake_mod.main = _boom
    sys.modules["scripts.__fake_test_mod__"] = fake_mod
    try:
        runner = _wrap_python_main("scripts.__fake_test_mod__")
        # Must not raise.
        runner()
    finally:
        del sys.modules["scripts.__fake_test_mod__"]
