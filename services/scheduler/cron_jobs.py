"""Wave H — Railway 자율화 (APScheduler 19 jobs 통합).

배경
====
macOS crontab 에 19개의 ops 작업이 박혀 있었으나 ``노트북이 꺼지면 멈춤``
이 단일 장애점이었다. Railway 가 24/7 띄워 주는 gunicorn web 프로세스
(workers=1, gevent) 안의 APScheduler 에 동일 19개 job 을 등록해
macOS 의존성을 제거한다.

비용 0원 보장
=============
- Railway 플랜 변경 없음 — 기존 web 프로세스 안에서 실행.
- Procfile / railway.json 의 ``--workers 1`` 가 dupe 방지를 보장 (멀티 워커
  였다면 N회 실행 위험).  Procfile 변경 시 cron_jobs 도 함께 점검 필요.
- Vercel cron (Pro $20/월) 미사용.

실행 게이팅
============
``RUN_SCHEDULER=1`` env 가 켜진 단일 프로세스에서만 등록된다 — ``app.py``
의 기존 ``_init_scheduler()`` 가 이미 같은 env 로 게이팅하고 있으며,
``register_cron_jobs()`` 는 그 안에서 호출된다.  로컬 dev 에서는 default
off — 이중 실행 위험 없음.

타임존
======
모든 cron trigger 는 ``timezone="Asia/Seoul"`` 명시.  Railway 컨테이너의
기본 timezone 은 UTC 이므로 KST 명시가 안 되면 9시간 어긋남.

shell 스크립트 4개
=================
``db_backup.sh / ssl_expiry_check.sh / vercel_canary.sh / daily_regression.sh``
4개는 bash → Python 포팅 비용이 커서 ``subprocess.run`` 으로 호출.
나머지 15개는 ``scripts.nightly.*.main()`` 또는
``scripts.morning_brief.build_brief_kpi.main()`` 직접 호출 (subprocess
오버헤드 + 환경변수 propagation 회피).

api-health
==========
macOS crontab 의 ``api-health`` 는 ``curl https://pivoxquant.com/api/health``
self-check 였는데, Railway 안에서 자기 자신의 health endpoint 를 polling
하는 것은 redundant 하다 — Railway 자체가 ``healthcheckPath=/api/health``
를 30s timeout 으로 감시하고 실패 시 자동 재시작한다.  그래도 ops 모니터링
용 Slack alert 신호는 유지하기 위해 가벼운 in-process health-probe 로 변환.

멱등성
======
모든 job 은 ``max_instances=1`` + ``coalesce=True`` 로 등록 — 워커 재시작
혹은 잠시 지연되어도 missed run 이 쌓이지 않는다.  각 dispatcher 는 이미
DB 쿼리 기반 멱등 처리 (예: ``checkout_followup_dispatcher`` 는
``EmailQueue.status`` flag 로 중복 발송 차단).

테스트
======
``tests/test_scheduler_cron_jobs.py`` — 19 jobs 등록 검증 + trigger spec
(cron expression, timezone='Asia/Seoul') 검증 + ``RUN_SCHEDULER`` 게이팅.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

KST = "Asia/Seoul"

# Repo root — ``services/scheduler/cron_jobs.py`` 에서 부모 3단계 위로.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ── Wrappers (Python 직접 호출) ──────────────────────────────────────────────

def _wrap_python_main(
    module_path: str,
    func_name: str = "main",
    job_id: str | None = None,
) -> Callable[[], None]:
    """Wrap a ``scripts/.../foo.py:main()`` for APScheduler call-once dispatch.

    Why a closure: APScheduler stores the function reference; importing at
    registration time would slow boot and pull in service modules even when
    ``RUN_SCHEDULER=0``. Deferring the import to first run keeps cold start
    minimal and lets ``main()`` raise on env-missing without breaking the
    scheduler thread.

    ``job_id``: when provided, failures route through
    ``services.observability.alerts.emit_failure`` so they surface on
    Slack / Sentry + trigger 3-strike auto-pause. Without it we fall back
    to logger.exception-only (legacy behaviour, no on-call signal).
    """

    def _runner():
        try:
            mod = __import__(module_path, fromlist=[func_name])
            fn = getattr(mod, func_name)
            rc = fn()
            if rc not in (None, 0):
                logger.warning(
                    "[cron] %s.%s exit=%s (non-zero)",
                    module_path, func_name, rc,
                )
                if job_id:
                    # Non-zero exit IS a failure — alert + bump counter.
                    try:
                        from services.observability.alerts import emit_failure
                        emit_failure(
                            job_id,
                            RuntimeError(f"exit code {rc}"),
                            context={"module": module_path, "func": func_name},
                        )
                    except Exception:  # alert path must not raise
                        logger.exception("[cron] emit_failure swallowed")
            else:
                logger.info("[cron] %s.%s OK", module_path, func_name)
                if job_id:
                    try:
                        from services.observability.alerts import record_success
                        record_success(job_id)
                    except Exception:
                        pass
        except SystemExit as e:
            # ``main()`` may sys.exit(); treat 0 as success, else warn.
            code = getattr(e, "code", 0) or 0
            if code != 0:
                logger.warning(
                    "[cron] %s.%s SystemExit=%s", module_path, func_name, code,
                )
                if job_id:
                    try:
                        from services.observability.alerts import emit_failure
                        emit_failure(
                            job_id,
                            SystemExit(code),
                            context={"module": module_path, "exit": str(code)},
                        )
                    except Exception:
                        logger.exception("[cron] emit_failure swallowed")
            elif job_id:
                try:
                    from services.observability.alerts import record_success
                    record_success(job_id)
                except Exception:
                    pass
        except Exception as exc:
            # Never let one job's failure kill the scheduler thread.
            logger.exception(
                "[cron] %s.%s raised — swallowed", module_path, func_name,
            )
            if job_id:
                try:
                    from services.observability.alerts import emit_failure
                    emit_failure(
                        job_id, exc,
                        context={"module": module_path, "func": func_name},
                    )
                except Exception:
                    logger.exception("[cron] emit_failure swallowed")

    _runner.__name__ = f"cron_{module_path.replace('.', '_')}"
    return _runner


# ── Wrappers (shell script subprocess) ──────────────────────────────────────

def _wrap_shell_script(
    script_rel: str,
    label: str,
    job_id: str | None = None,
) -> Callable[[], None]:
    """Wrap a ``scripts/nightly/foo.sh`` via subprocess.

    Why subprocess (not bash → Python port): the 4 shell scripts wrap
    standard ops tooling (pg_dump, openssl s_client, curl) where rewriting
    in Python would duplicate platform-tested logic.  Subprocess overhead
    (~50ms) is negligible at cron cadence (minutes).

    ``job_id``: when provided, failures (non-zero exit / timeout / exception)
    route through ``services.observability.alerts.emit_failure`` so they
    surface on Slack / Sentry + trigger 3-strike auto-pause. Success path
    resets the failure counter via ``record_success``. Without ``job_id``
    we fall back to logger.warning-only (legacy behaviour, no on-call signal).
    """
    script_path = REPO_ROOT / script_rel

    def _runner():
        if not script_path.exists():
            logger.warning("[cron] shell script not found: %s — skipped", script_path)
            return
        try:
            res = subprocess.run(
                ["bash", str(script_path)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=600,  # 10min cap so a hung script can't block other jobs
            )
            if res.returncode != 0:
                logger.warning(
                    "[cron] %s exit=%s stderr=%s",
                    label, res.returncode, (res.stderr or "")[:500],
                )
                if job_id:
                    try:
                        from services.observability.alerts import emit_failure
                        emit_failure(
                            job_id,
                            RuntimeError(f"shell exit {res.returncode}"),
                            context={
                                "label": label,
                                "script": script_rel,
                                "stderr": (res.stderr or "")[:200],
                            },
                        )
                    except Exception:
                        logger.exception("[cron] emit_failure swallowed")
            else:
                logger.info("[cron] %s OK", label)
                if job_id:
                    try:
                        from services.observability.alerts import record_success
                        record_success(job_id)
                    except Exception:
                        pass
        except subprocess.TimeoutExpired as exc:
            logger.warning("[cron] %s TIMEOUT after 600s", label)
            if job_id:
                try:
                    from services.observability.alerts import emit_failure
                    emit_failure(
                        job_id, exc,
                        context={"label": label, "script": script_rel, "timeout": "600s"},
                    )
                except Exception:
                    logger.exception("[cron] emit_failure swallowed")
        except Exception as exc:
            logger.exception("[cron] %s raised — swallowed", label)
            if job_id:
                try:
                    from services.observability.alerts import emit_failure
                    emit_failure(
                        job_id, exc,
                        context={"label": label, "script": script_rel},
                    )
                except Exception:
                    logger.exception("[cron] emit_failure swallowed")

    _runner.__name__ = f"cron_shell_{label.replace('-', '_')}"
    return _runner


# ── api-health (in-process) ──────────────────────────────────────────────────

def _api_health_probe() -> None:
    """In-process health probe.

    Railway already auto-restarts on /api/health failure (healthcheckPath +
    restartPolicyType=ON_FAILURE), so this job's job is the *Slack alert*
    side — surface degraded state to ops before Railway's restart kicks in.

    Routes failures through ``services.observability.alerts.emit_failure`` so
    a sustained 3-strike outage auto-pauses the noisy alerter (the underlying
    Railway restart loop is the real recovery — this cron should not page
    every 6h forever once we know the site is down).
    """
    job_id = "ops_api_health"
    try:
        import requests  # local import — keeps boot path light
    except ImportError:
        logger.warning("[cron] api-health skipped — requests not installed")
        return

    url = os.environ.get("PIVOX_HEALTH_URL", "https://pivoxquant.com/api/health")
    try:
        r = requests.get(url, timeout=15, allow_redirects=True)
        if 200 <= r.status_code < 300:
            logger.info("[cron] api-health %s OK", r.status_code)
            try:
                from services.observability.alerts import record_success
                record_success(job_id)
            except Exception:
                pass
            return
        logger.warning("[cron] api-health %s FAIL", r.status_code)
        try:
            from services.observability.alerts import emit_failure
            emit_failure(
                job_id,
                RuntimeError(f"health probe HTTP {r.status_code}"),
                context={"url": url, "status": str(r.status_code)},
            )
        except Exception:
            # Fall back to legacy Slack-only path if observability import fails.
            _slack_alert(f"PivoxQuant api-health FAIL: status={r.status_code}")
    except Exception as exc:
        logger.warning("[cron] api-health exception=%s", exc)
        try:
            from services.observability.alerts import emit_failure
            emit_failure(job_id, exc, context={"url": url})
        except Exception:
            _slack_alert(f"PivoxQuant api-health EXCEPTION: {exc}")


def _slack_alert(text: str) -> None:
    """Best-effort Slack webhook alert."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    try:
        import requests
        requests.post(webhook, json={"text": text}, timeout=10)
    except Exception:
        logger.exception("[cron] slack alert failed")


# ── Job spec table ──────────────────────────────────────────────────────────
#
# Mirrors the macOS crontab 19 entries from scripts/cron/run.sh.  Each entry
# is (id, trigger, runner_factory).  When adding a new ops cron, append here
# AND update scripts/cron/run.sh (kept as fallback during the 1-week
# parallel-run validation window) — both must stay in sync until macOS
# crontab is retired.

# Job specs — declared as a function returning a list so tests can introspect
# the table without forcing import-time side effects.
def _job_specs() -> list[tuple[str, CronTrigger | IntervalTrigger, Callable[[], None]]]:
    return [
        # 0 */6 * * * — api-health (every 6 hours)
        (
            "ops_api_health",
            CronTrigger(hour="*/6", minute=0, timezone=KST),
            _api_health_probe,
        ),
        # 0 2 * * * — db-backup (daily 02:00)
        (
            "ops_db_backup",
            CronTrigger(hour=2, minute=0, timezone=KST),
            _wrap_shell_script(
                "scripts/nightly/db_backup.sh", "db-backup",
                job_id="ops_db_backup",
            ),
        ),
        # 0 9 * * 1 — ssl-expiry (Mon 09:00)
        (
            "ops_ssl_expiry",
            CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=KST),
            _wrap_shell_script(
                "scripts/nightly/ssl_expiry_check.sh", "ssl-expiry",
                job_id="ops_ssl_expiry",
            ),
        ),
        # */30 * * * * — vercel-canary (every 30 min)
        (
            "ops_vercel_canary",
            CronTrigger(minute="*/30", timezone=KST),
            _wrap_shell_script(
                "scripts/nightly/vercel_canary.sh", "vercel-canary",
                job_id="ops_vercel_canary",
            ),
        ),
        # 0 6 * * * — daily-regression (daily 06:00)
        (
            "ops_daily_regression",
            CronTrigger(hour=6, minute=0, timezone=KST),
            _wrap_shell_script(
                "scripts/nightly/daily_regression.sh", "daily-regression",
                job_id="ops_daily_regression",
            ),
        ),
        # 0 14 * * * — sendgrid-quota (daily 14:00 KST)
        (
            "ops_sendgrid_quota",
            CronTrigger(hour=14, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.sendgrid_quota_check",
                job_id="ops_sendgrid_quota",
            ),
        ),
        # 5 6 * * * — morning-brief-kpi (daily 06:05)
        (
            "ops_morning_brief_kpi",
            CronTrigger(hour=6, minute=5, timezone=KST),
            _wrap_python_main(
                "scripts.morning_brief.build_brief_kpi",
                job_id="ops_morning_brief_kpi",
            ),
        ),
        # */5 * * * * — signup-funnel (every 5 min)
        (
            "ops_signup_funnel",
            CronTrigger(minute="*/5", timezone=KST),
            _wrap_python_main(
                "scripts.nightly.signup_funnel_check",
                job_id="ops_signup_funnel",
            ),
        ),
        # 0 10 * * * — credentials-expiry (daily 10:00)
        (
            "ops_credentials_expiry",
            CronTrigger(hour=10, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.credentials_expiry_check",
                job_id="ops_credentials_expiry",
            ),
        ),
        # 0 11 * * 1 — env-audit (Mon 11:00)
        (
            "ops_env_audit",
            CronTrigger(day_of_week="mon", hour=11, minute=0, timezone=KST),
            _wrap_shell_script(
                "scripts/nightly/env_sync_audit.sh", "env-audit",
                job_id="ops_env_audit",
            ),
        ),
        # */5 * * * * — error-rate (every 5 min)
        (
            "ops_error_rate",
            CronTrigger(minute="*/5", timezone=KST),
            _wrap_python_main(
                "scripts.nightly.error_rate_check",
                job_id="ops_error_rate",
            ),
        ),
        # 30 6 * * * — ticker-name-audit (daily 06:30)
        (
            "ops_ticker_name_audit",
            CronTrigger(hour=6, minute=30, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.ticker_name_audit",
                job_id="ops_ticker_name_audit",
            ),
        ),
        # 0 12 * * 1 — email-compliance (Mon 12:00)
        (
            "ops_email_compliance",
            CronTrigger(day_of_week="mon", hour=12, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.email_compliance_check",
                job_id="ops_email_compliance",
            ),
        ),
        # 0 7 * * * — section101-check (daily 07:00)
        (
            "ops_section101_check",
            CronTrigger(hour=7, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.section101_compliance_check",
                job_id="ops_section101_check",
            ),
        ),
        # */15 * * * * — checkout-followup (every 15 min)
        (
            "ops_checkout_followup",
            CronTrigger(minute="*/15", timezone=KST),
            _wrap_python_main(
                "scripts.nightly.checkout_followup_dispatcher",
                job_id="ops_checkout_followup",
            ),
        ),
        # */15 * * * * — email-scheduler (every 15 min, offset +1 to avoid
        # exact same tick as checkout-followup — both touch EmailQueue)
        (
            "ops_email_scheduler",
            CronTrigger(minute="1-59/15", timezone=KST),
            _wrap_python_main(
                "scripts.nightly.email_scheduler_dispatcher",
                job_id="ops_email_scheduler",
            ),
        ),
        # 0 * * * * — inactive-nudge (hourly)
        (
            "ops_inactive_nudge",
            CronTrigger(minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.inactive_nudge_dispatcher",
                job_id="ops_inactive_nudge",
            ),
        ),
        # 0 9 * * 0 — finance-weekly-check (Sun 09:00)
        (
            "ops_finance_weekly_check",
            CronTrigger(day_of_week="sun", hour=9, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.finance_weekly_check",
                job_id="ops_finance_weekly_check",
            ),
        ),
        # ── Wave I P0 (2026-05-19) ───────────────────────────────────────────
        # 0 * * * * — FX staleness check (hourly)
        # 24h+ stale KRW/USD → Slack + Sentry. portfolio +52,281% 재발 방지.
        (
            "ops_fx_staleness_check",
            CronTrigger(minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.fx_staleness_check", "check_fx_staleness",
                job_id="ops_fx_staleness_check",
            ),
        ),
        # 0 22 * * * — Anthropic cost estimate (daily 22:00 KST)
        # 오늘 사용량 + MTD 집계. 80%/100% 시 Slack 경고. SWOT 500 재발 방지.
        (
            "ops_anthropic_cost_estimate",
            CronTrigger(hour=22, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.anthropic_cost_estimate", "run_cost_estimate",
                job_id="ops_anthropic_cost_estimate",
            ),
        ),
        # */2 * * * * — Railway resource pressure (Wave I D-2).
        # RSS > 450MB (Hobby 512MB의 88%) OR CPU > 80% sustained 5min →
        # Slack alert. 2-min cadence는 sustained-pressure 검출(≥ 3 sample)의 floor.
        # cpu_percent(interval=1.0) blocking 1s × 30회/hr = 0.8% overhead.
        (
            "ops_railway_resource",
            CronTrigger(minute="*/2", timezone=KST),
            _wrap_python_main(
                "scripts.nightly.railway_resource_check",
                job_id="ops_railway_resource",
            ),
        ),
        # 30 9 1 * * — pivoxquant.com WHOIS expiry (Wave I E-2, monthly).
        # 매월 1일 09:30 KST. 도메인 만료는 분 단위로 안 바뀌므로 매월 1회
        # 충분 + WHOIS rate limit(가비아 ~10 req/min/IP) 안전. 09:30 offset
        # 으로 09:00 cluster (ssl-expiry/finance-weekly) 회피.
        (
            "ops_domain_expiry",
            CronTrigger(day=1, hour=9, minute=30, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.domain_expiry_check",
                job_id="ops_domain_expiry",
            ),
        ),
        # 0 9 1 * * — commerce-registration (1st of month 09:00 KST) [Wave I L-3]
        # 통신판매업 신고 미완 상태일 때 월 1회 Slack/stdout 알림. 전자상거래법 §12
        # 의무 위반 → §44 ② 1호 (3년 이하 징역 OR 1억원 이하 벌금) 위험.
        # feature flag ``PIVOX_COMMERCE_REGISTERED=true`` 면 스크립트 내부에서
        # 즉시 exit 0 — 알림 자동 중단. 동월 dedup 으로 중복 발송 차단.
        (
            "ops_commerce_registration",
            CronTrigger(day=1, hour=9, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.commerce_registration_reminder",
                job_id="ops_commerce_registration",
            ),
        ),
        # ── Wave I C-1/C-2 (2026-05-19) ──────────────────────────────────────
        # */15 * * * * — OAuth failure check (every 15 min)
        # auth_events 에서 동일 email 1h 내 fail ≥ 3 회 → Slack + TRANSACTIONAL
        # 도움 메일. dedup marker 로 24h cooldown.
        (
            "ops_oauth_failure_check",
            CronTrigger(minute="*/15", timezone=KST),
            _wrap_python_main(
                "scripts.nightly.oauth_failure_check",
                job_id="ops_oauth_failure_check",
            ),
        ),
        # 30 3 * * * — PIPA §21 30-day purge (daily 03:30 KST)
        # deletion_requested_at >= 30d 인 user 의 모든 데이터 cascade hard-delete
        # + auth_events anonymize (PIPA §29). 오프피크 시간대.
        (
            "ops_pipa_purge",
            CronTrigger(hour=3, minute=30, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.pipa_purge",
                job_id="ops_pipa_purge",
            ),
        ),
        # ── Viral loop (2026-05-26) ──────────────────────────────────────────
        # 30 9 * * 1 — 주간 퍼널 스냅샷 (월 09:30 KST).
        # funnel_events 7일 집계 + K-factor + WAMR → Slack. 09:00 cluster
        # (ssl-expiry/env-audit) 회피 위해 09:30 offset. 자체 DB query only +
        # Slack webhook → 0원.
        (
            "ops_weekly_funnel_snapshot",
            CronTrigger(day_of_week="mon", hour=9, minute=30, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.weekly_funnel_snapshot",
                job_id="ops_weekly_funnel_snapshot",
            ),
        ),
        # ── Marketing autopost (2026-05-26) ──────────────────────────────────
        # 0 8 * * * — 마케팅 일일 디스패치 (매일 08:00 KST).
        # content-bank.json 에서 오늘 항목 읽어 §101 게이트 통과 후 Slack
        # 인스타 리마인더 + (토큰시) Threads/Bluesky 자동 발행. cron 에서 LLM
        # 호출 0건 (캡션은 미리 작성된 파일) → 추가 비용 0원. 08:00 슬롯은
        # 06:xx/07:00 (regression/brief/section101) 및 09:xx (ssl/funnel)
        # cluster 회피. 기본 OFF — PIVOX_MARKETING_AUTOPOST_ENABLED 미설정 시
        # main() 이 즉시 exit 0 (기존 prod 잡에 영향 0).
        (
            "ops_marketing_daily_dispatch",
            CronTrigger(hour=8, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.marketing_daily_dispatch",
                job_id="ops_marketing_daily_dispatch",
            ),
        ),
        # ── Launch coordinator audit (T9, 2026-05-28) ────────────────────────
        # 0 6 * * * — SHIP_BLOCKERS.md 일일 audit (06:00 KST, morning-briefing
        # 06:27 prepend 직전). 변호사 큐 카운트 + ship-blocker 카테고리별
        # 카운트 + env 기반 carry-over status 측정. /tmp/ship_blockers_status.json
        # 갱신 + SHIP_BLOCKERS.md 헤더 "최근 갱신" 1줄만 patch (본문 무손상).
        # 외부 API 호출 0건 — local file/env grep 만. 추가 비용 0원.
        (
            "ops_ship_blockers_daily",
            CronTrigger(hour=6, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.ship_blockers_audit",
                job_id="ops_ship_blockers_daily",
            ),
        ),
        # ── Data integrity sweep (T10, 2026-05-28) ───────────────────────────
        # 0 4 * * * — 3축 invariant 일일 sanity (04:00 KST, bug-hunter 03:37
        # 직후 슬롯). fx_service / cache_ttl / price_overlay / risk_snapshot_cache
        # cross-user isolation 검증. 회귀 발견 시 Slack alert (cron 자체는 항상 0 exit).
        # 외부 API 호출 0건 — in-process import + 1 round-trip cache write/read.
        # fx-consistency-guard / data-freshness-monitor / cache-poisoning-sentinel
        # 3 agent 의 자동 회귀 게이트. wave-data-integrity workflow 보조.
        (
            "ops_data_integrity_sweep",
            CronTrigger(hour=4, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.nightly.data_integrity_sweep",
                job_id="ops_data_integrity_sweep",
            ),
        ),
        # ── Lawyer packet weekly (T11, 2026-05-28) ───────────────────────────
        # sun 21:00 KST — legal_question_queue.md (21건) + git log 1주 + SHIP_BLOCKERS
        # RELEASE-BLOCKER 인용 → ~/Desktop/취준/변호사상담_PivoxQuant/weekly_packet_<date>.md
        # 외부 API 0건. file I/O + subprocess git log only. 추가 비용 0원.
        (
            "ops_lawyer_packet_weekly",
            CronTrigger(day_of_week="sun", hour=21, minute=0, timezone=KST),
            _wrap_python_main(
                "scripts.legal.lawyer_packet_build",
                job_id="ops_lawyer_packet_weekly",
            ),
        ),
        # ── 월간 거울 리포트 (2026-09-17) ────────────────────────────────────
        # 30 8 1 * * — 매월 1일 08:30 KST. 지난 30일의 기록을 PDF 로 묶어
        # 알림 설정에서 켜 둔 + 정보성 수신 동의가 있는 사용자에게 발송
        # (정통망법 §50 ① 정보성). 08:30 슬롯은 08:00 (marketing-dispatch) 과
        # 09:00 / 09:30 의 1일 cluster (commerce-registration / domain-expiry)
        # 사이의 빈 자리다. 발송 대상이 없으면 그냥 0건으로 끝난다.
        # scripts/ 가 아니라 services/ 모듈을 직접 부른다 — 이 잡은 ops
        # 점검이 아니라 제품 발송이고, 온디맨드 라우트와 같은 코드를 쓴다.
        (
            "ops_monthly_mirror_report",
            CronTrigger(day=1, hour=8, minute=30, timezone=KST),
            _wrap_python_main(
                "services.reports_delivery",
                job_id="ops_monthly_mirror_report",
            ),
        ),
    ]


# ── Public entrypoint ────────────────────────────────────────────────────────

def register_cron_jobs(sched: BackgroundScheduler, app=None) -> list[str]:
    """Register the ops cron jobs onto an existing APScheduler.

    Job count grows as Wave I/J etc. add more — see ``_job_specs()`` and
    ``tests/test_scheduler_cron_jobs.py:EXPECTED_JOB_COUNT`` for the
    current source-of-truth count.

    Parameters
    ----------
    sched
        APScheduler instance — created by ``app.py:_init_scheduler``.
    app
        Optional Flask app for app_context — currently unused (all wrapped
        scripts manage their own session/DB binding via env vars).
        Reserved for future jobs that need ``with app.app_context():``.

    Returns
    -------
    list[str]
        IDs of registered jobs (for ops verification / Railway log diagnostic).

    Gating
    ------
    This function does NOT check ``RUN_SCHEDULER`` — that's enforced upstream
    by ``app.py:_init_scheduler``'s ``if os.environ.get("RUN_SCHEDULER")==1``
    guard.  Tests bypass the gate to exercise registration directly.
    """
    # Wire the scheduler into observability so emit_failure can pause jobs
    # at the 3-strike threshold. Best-effort — never raise from boot.
    try:
        from services.observability.alerts import register_scheduler
        register_scheduler(sched)
    except Exception:
        logger.exception("[cron] observability.register_scheduler failed (continuing)")

    registered: list[str] = []
    for job_id, trigger, runner in _job_specs():
        sched.add_job(
            runner,
            trigger=trigger,
            id=job_id,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        registered.append(job_id)
    logger.info(
        "[cron] Wave H registered %d ops jobs: %s",
        len(registered), registered,
    )
    return registered
