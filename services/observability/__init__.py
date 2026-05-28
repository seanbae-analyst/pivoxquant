"""Observability — cross-cutting failure alerting + circuit breaker.

Why this package exists
=======================
Railway in-process scheduler runs 52 jobs (28 ``ops_*`` from
``services/scheduler/cron_jobs.py`` + 26 ``_scheduled_*`` from
``app.py:_init_scheduler``). Each job currently swallows exceptions via
``logger.exception(...)`` so a silent fail leaves no on-call signal —
only a buried Railway log line that nobody reads.

``emit_failure(job_id, exc)`` is the SoT helper: best-effort Slack
webhook + Sentry capture, with a 3-strike auto-pause circuit breaker
so a permanently broken job stops paging on every tick.
"""

from services.observability.alerts import emit_failure, record_success

__all__ = ["emit_failure", "record_success"]
