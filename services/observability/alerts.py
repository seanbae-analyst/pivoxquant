"""Cron-job failure alerting + 3-strike auto-pause circuit breaker.

Behaviour
---------
``emit_failure(job_id, exc, context=None)``:

1. Logs the exception via ``logger.exception`` (always — no-op-free).
2. Best-effort ``sentry_sdk.capture_exception`` if Sentry SDK present
   AND ``SENTRY_DSN`` was set at app boot (init lives in ``app.py``).
   Never re-inits Sentry — that's app.py's job.
3. Best-effort Slack webhook POST if ``SLACK_WEBHOOK_URL`` set.
4. Bumps an in-memory failure counter for ``job_id``. On the 3rd
   consecutive failure, tries to pause the APScheduler job via the
   registered ``BackgroundScheduler`` and posts a Slack escalation.

``record_success(job_id)``: resets the counter for ``job_id``. Call this
from the wrapper's success branch so transient failures don't accumulate
indefinitely.

Design constraints (per project memory)
---------------------------------------
- Zero additional cost: env-gated, no new vendors.
- Silent no-op when env vars absent (dev / CI / first-boot before CEO
  configures the webhook).
- Never raises — alerting must not break the caller.
- Thread-safe counter (APScheduler uses worker threads).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ── Module-level state ──────────────────────────────────────────────────────
#
# In-memory counter is sufficient: a Railway redeploy resets to 0, which is
# the correct semantic (a fresh deploy might have fixed the issue). Redis /
# DB persistence would add cost and a failure surface for an alerting path
# that MUST not itself fail.
_lock = threading.Lock()
_failure_counts: dict[str, int] = {}

# Threshold at which a job is auto-paused. 3 = one transient + two
# consecutive = real outage signal; below 3 stays as plain Slack alert.
PAUSE_THRESHOLD = 3

# Optional reference to the live APScheduler instance, set by app.py /
# services/scheduler/__init__.py during boot. Without it, auto-pause is
# best-effort no-op (alerts still emit).
_scheduler_ref: Any | None = None


def register_scheduler(scheduler: Any) -> None:
    """Wire the live scheduler so emit_failure can pause jobs at threshold.

    Called once from ``services/scheduler/__init__.py:register_cron_jobs``
    and from ``app.py:_init_scheduler`` (whichever boots first wins; both
    point to the same APScheduler instance in prod).
    """
    global _scheduler_ref
    _scheduler_ref = scheduler


def _slack_post(text: str) -> bool:
    """Best-effort Slack webhook POST. Returns True on 2xx, else False."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        return False
    try:
        import requests  # local import — cold-start safe
    except Exception:
        logger.debug("alerts: requests not installed — Slack skipped")
        return False
    try:
        resp = requests.post(webhook, json={"text": text}, timeout=10)
        return 200 <= resp.status_code < 300
    except Exception:
        # NEVER let alerting raise — caller is already in an except branch.
        logger.exception("alerts: Slack POST failed")
        return False


def _sentry_capture(exc: BaseException, tags: dict[str, str] | None = None) -> None:
    """Best-effort Sentry capture. No-op if SDK missing or DSN unset."""
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except Exception:
        return
    try:
        if tags:
            for k, v in tags.items():
                try:
                    sentry_sdk.set_tag(k, v)
                except Exception:
                    pass
        sentry_sdk.capture_exception(exc)
    except Exception:
        logger.exception("alerts: Sentry capture failed")


def emit_failure(
    job_id: str,
    exc: BaseException,
    context: dict[str, Any] | None = None,
) -> None:
    """Standard cron-job failure handler.

    Parameters
    ----------
    job_id : str
        APScheduler job id (e.g. ``"ops_api_health"`` or
        ``"sched_scheduled_self_audit"``). Used as the dedup / counter key
        and as the Slack message subject.
    exc : BaseException
        The caught exception. Caller is responsible for being inside the
        ``except`` branch; we do not re-raise.
    context : dict | None
        Optional structured context (e.g. ``{"module": "scripts.foo"}``)
        merged into the Slack message + Sentry tags. Values stringified.

    Never raises. Safe to call from any exception handler.
    """
    # 1. Always log — the cheapest signal, never gated.
    safe_ctx = {k: str(v) for k, v in (context or {}).items()}
    logger.exception(
        "[alerts] cron job FAILED job_id=%s ctx=%s", job_id, safe_ctx
    )

    # 2. Bump counter (thread-safe).
    with _lock:
        _failure_counts[job_id] = _failure_counts.get(job_id, 0) + 1
        n = _failure_counts[job_id]

    # 3. Sentry — silent no-op if SDK / DSN missing.
    _sentry_capture(exc, tags={"cron_job_id": job_id, **safe_ctx})

    # 4. Slack — silent no-op if webhook unset.
    ctx_line = ""
    if safe_ctx:
        ctx_line = "\n• context: " + ", ".join(
            f"`{k}={v}`" for k, v in safe_ctx.items()
        )
    text = (
        f":rotating_light: *Cron 실패* (#{n})\n"
        f"• job: `{job_id}`\n"
        f"• error: `{type(exc).__name__}: {str(exc)[:200]}`"
        f"{ctx_line}"
    )
    _slack_post(text)

    # 5. 3-strike auto-pause + escalation.
    if n >= PAUSE_THRESHOLD:
        _maybe_pause_and_escalate(job_id, n)


def _maybe_pause_and_escalate(job_id: str, n: int) -> None:
    """Pause the job (best effort) and post a louder Slack message."""
    if _scheduler_ref is None:
        # No scheduler wired (e.g. unit test path) — escalate anyway.
        _slack_post(
            f":octagonal_sign: *Cron AUTO-PAUSE 시도 실패* — scheduler 미연결\n"
            f"• job: `{job_id}` (연속 {n}회 실패)\n"
            f"• 수동 점검 필요"
        )
        return

    paused = False
    try:
        # APScheduler exposes pause_job on BackgroundScheduler.
        _scheduler_ref.pause_job(job_id)
        paused = True
    except Exception as exc:
        # Common: job_id mismatch (we got the function name not the
        # registered id). Escalate without pausing.
        logger.warning(
            "[alerts] pause_job(%s) failed: %s", job_id, exc
        )

    msg = (
        f":octagonal_sign: *Cron AUTO-PAUSE* — 연속 {n}회 실패\n"
        f"• job: `{job_id}`\n"
        f"• 상태: {'paused (재배포까지 비활성)' if paused else 'pause 실패 — 수동 정지 필요'}\n"
        f"• 다음 액션: Railway 로그 확인 → 원인 fix → resume_job 또는 재배포"
    )
    _slack_post(msg)


def record_success(job_id: str) -> None:
    """Reset the failure counter for ``job_id`` on a successful run.

    Wrappers should call this in their success branch — otherwise a job
    that fails twice in a week then runs fine for 6 months would still
    auto-pause on the next failure.
    """
    with _lock:
        if job_id in _failure_counts:
            _failure_counts.pop(job_id, None)


def get_failure_count(job_id: str) -> int:
    """Test / introspection helper. Returns 0 if never seen."""
    with _lock:
        return _failure_counts.get(job_id, 0)


def _reset_all_for_test() -> None:
    """Test-only: clear all counters between cases."""
    with _lock:
        _failure_counts.clear()
