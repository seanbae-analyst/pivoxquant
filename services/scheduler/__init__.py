"""Scheduler services — APScheduler job registration.

Wave H (2026-05-19) — macOS crontab → Railway in-process APScheduler ingestion.
See ``cron_jobs.py`` for the 19 ops jobs migrated from ``scripts/cron/run.sh``.
The 19 jobs run inside the existing gunicorn web worker (workers=1, gevent),
so no extra Railway process is provisioned — keeps the $5 Hobby credit envelope.
"""
from services.scheduler.cron_jobs import register_cron_jobs

__all__ = ["register_cron_jobs"]
