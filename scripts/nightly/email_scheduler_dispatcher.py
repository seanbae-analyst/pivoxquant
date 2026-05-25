#!/usr/bin/env python3
"""PivoxQuant — onboarding email scheduler dispatcher.

Wave G S5 (2026-05-19).

Drains the ``scheduled_emails`` queue every 15 min. For each row whose
``scheduled_send_at <= NOW()`` and ``sent_at IS NULL`` and
``skipped_reason IS NULL``:

* ``PIVOX_ONBOARDING_SEQUENCE_ENABLED=true``  → render + send via
  ``services.email.onboarding_sequence.dispatch_due`` (which uses the
  shared ``EmailSender`` cascade: SendGrid → Brevo → SMTP → skip).
  On provider accept: ``mark_sent``. On permanent failure (no user,
  no email, no consent, provider failed): ``mark_skipped(reason)``.

* ``PIVOX_ONBOARDING_SEQUENCE_ENABLED=false`` (default) → still walks
  the queue but stamps ``skipped_reason="feature_flag_off"`` on each
  due row. Keeps the table from growing unbounded while we wait for
  the variance-flag flip; gives an audit trail.

15-minute cadence
-----------------
The D+0/D+3/D+7 spec only needs ±15min precision — D+0 is "within
minutes of signup", D+3/D+7 are calendar-day nudges. A 15-min cron
gives D+0 a worst-case 15-min lag and D+3/D+7 a sub-1% lag against
their full 3d/7d windows.

Cost
----
- DB: ~1 SELECT per tick + ~3N writes per signup (one row per step).
  Zero marginal cost.
- SendGrid 100/day free + Brevo 300/day free fallback. With 30
  signups/day expected ramp: 30 D+0 + 30 D+3 + 30 D+7 = 90/day worst
  case. SendGrid 100/day alone covers it; Brevo 300/day is the safety
  net.
- 추가 비용 0원.

Exit codes
----------
* 0 — clean run (any number of rows processed, including zero).
* 1 — unexpected exception (caught + logged; Slack alert if env set).

Usage
-----
``./venv/bin/python scripts/nightly/email_scheduler_dispatcher.py``

Cron entry (15-min cadence):
``*/15 * * * *  /path/scripts/cron/run.sh email-scheduler``
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure repo root on path so ``from app import create_app`` resolves
# when invoked from any cwd.
_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("email_scheduler_dispatcher")


def _post_slack(text: str) -> None:
    """Fire-and-forget Slack notification — never raises."""
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        import requests
        requests.post(url, json={"text": text}, timeout=10)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack post failed: %s", exc)


def _drain_once() -> dict[str, int]:
    """Single dispatch pass. Returns combined stats dict.

    Drains TWO independent queues that share the ``scheduled_emails``
    table:

    * Onboarding D+0/D+3/D+7 (Wave G S5) —
      ``services.email.onboarding_sequence.dispatch_due``.
    * Retention D+7/D+30 (Wave G C-R1) —
      ``services.email.retention_sequence.dispatch_retention``.
      Adds the ``skipped_night`` counter (§61의2 21:00-08:00 KST gate).

    All per-row error handling lives inside each module's ``dispatch_*``
    so the cron's outer loop stays trivial. Stats are returned
    namespaced (``onboarding.*`` / ``retention.*``) so Slack logging
    can attribute volume per queue without ambiguity.
    """
    from app import create_app
    from extensions import db
    from services.email.onboarding_sequence import dispatch_due
    from services.email.retention_sequence import dispatch_retention

    # Transient app: ALSO registered into the in-process APScheduler
    # (services/scheduler/cron_jobs.py:_wrap_python_main). The main web app
    # already warmed the cache; suppress the redundant FMP-hitting warmup
    # thread here. create_app reads this env at call time (app.py:355).
    os.environ["POPULATE_CACHE_ON_BOOT"] = "0"
    # Transient CLI/scheduler-tick app: never build the 49-job APScheduler.
    # The advisory lock already prevents a second instance from STARTING, but
    # without this every create_app() still instantiates 49 Job objects +
    # init overhead (same connection-pressure class as POPULATE_CACHE_ON_BOOT).
    # crontab runs these standalone, so the scheduler is never wanted here.
    os.environ.setdefault("RUN_SCHEDULER", "0")

    app = create_app()
    try:
        with app.app_context():
            onboarding_stats = dispatch_due()
            retention_stats = dispatch_retention()
    finally:
        # Release the transient QueuePool now rather than letting it linger
        # ~300s toward Railway PG's 25-conn ceiling. Harmless standalone.
        try:
            db.engine.dispose()
        except Exception:  # noqa: BLE001
            logger.debug("engine dispose failed (non-fatal)", exc_info=True)

    combined: dict[str, int] = {}
    for k, v in onboarding_stats.items():
        combined[f"onboarding.{k}"] = v
    for k, v in retention_stats.items():
        combined[f"retention.{k}"] = v
    # Flat totals for the Slack notification predicate below.
    combined["sent"] = (
        onboarding_stats.get("sent", 0) + retention_stats.get("sent", 0)
    )
    combined["due"] = (
        onboarding_stats.get("due", 0) + retention_stats.get("due", 0)
    )
    return combined


def main() -> int:
    try:
        stats = _drain_once()
    except Exception as exc:  # noqa: BLE001
        logger.exception("email_scheduler_dispatcher fatal: %s", exc)
        _post_slack(
            f":warning: PivoxQuant email-scheduler dispatcher fatal: {exc}"
        )
        return 1

    logger.info("email_scheduler_dispatcher stats=%s", stats)
    if stats.get("sent", 0) > 0:
        _post_slack(
            f":mailbox_with_mail: PivoxQuant onboarding sequence sent "
            f"{stats['sent']}/{stats['due']} (stats: {stats})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
