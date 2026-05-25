#!/usr/bin/env python3
"""24-hour onboarding nudge dispatcher (Wave G C-S2) — cron entry point.

Thin wrapper around :mod:`services.customer.inactive_nudge`.

Purpose
-------
Re-engage signups that never created a brag-card / artefact within
their first 24h. The email is a 5-minute getting-started guide — no
discount language, no promotional copy — but because the trigger is a
*timer* (not a user action), this is classified as INFORMATION under
정통망법 §50 ①, NOT transactional. Consent is required.

§50 분류 / 발송 게이트
---------------------
- :class:`EmailCategory.INFORMATION` — surfaces the per-category gate
  in :meth:`services.email.sender.EmailSender.send`.
- Feature flag ``PIVOX_CS1_CONSENT_ENABLED=true`` AND user has
  ``marketing_consent_information_at`` set → send.
- Either condition off → skip the user (logged, not failed).
- Additional dispatcher-level kill switch
  ``PIVOX_INACTIVE_NUDGE_ENABLED=true`` (default false) gates the
  whole script — out-of-the-box this cron is dormant until the
  lawyer's Q-S1 answer arrives.

Why two switches?
-----------------
The schema-level switch (``PIVOX_CS1_CONSENT_ENABLED``) controls
sender enforcement for every category-aware send across the app. The
dispatcher-level switch (``PIVOX_INACTIVE_NUDGE_ENABLED``) lets us
roll out C-S2 in isolation. Both must be true for a nudge to leave
the building.

Schedule
--------
``0 * * * *`` (every hour, on the hour). One run scans the rolling
24h-25h signup window — the 1h granularity matches the cron cadence
so no signup falls between two scans.

Idempotency
-----------
Per-user ``users.inactive_nudge_sent_at`` column is set on success.
The service-layer query filters ``IS NULL`` so the same user is
never re-nudged even on cron overlap. The column is added by
migration ``038_inactive_nudge_sent_at``.

Cost
----
SendGrid 100/day free quota. Worst case at 1k DAU = ~30 nudges/day.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ── feature flags ────────────────────────────────────────────────────────────

def _dispatcher_enabled() -> bool:
    val = os.environ.get(
        "PIVOX_INACTIVE_NUDGE_ENABLED", "false",
    ).strip().lower()
    return val in ("true", "1", "yes", "on")


def _cs1_consent_enabled() -> bool:
    val = os.environ.get(
        "PIVOX_CS1_CONSENT_ENABLED", "false",
    ).strip().lower()
    return val in ("true", "1", "yes", "on")


# ── main dispatch ────────────────────────────────────────────────────────────

def run_once(now: datetime | None = None) -> dict[str, int]:
    """Single dispatch pass. Returns a summary dict.

    Summary keys:
      - ``window_users``   : count of rows in the 24h-25h slice
                              (post-activity-probe)
      - ``skipped_active`` : had artefact/position/trade activity
      - ``sent``           : email accepted by EmailSender
      - ``skipped_send``   : sender returned False (opt-out / consent / no transport)
      - ``flag_off``       : dispatcher or CS1 flag is off
    """
    summary = {
        "window_users":   0,
        "skipped_active": 0,
        "sent":           0,
        "skipped_send":   0,
        "flag_off":       0,
    }

    if not _dispatcher_enabled():
        logger.info(
            "PIVOX_INACTIVE_NUDGE_ENABLED off — dispatcher dormant",
        )
        summary["flag_off"] = 1
        return summary

    if not _cs1_consent_enabled():
        # CS1 framework gates INFORMATION sends. Without it the sender
        # would refuse anyway — short-circuit here to avoid burning the
        # query budget.
        logger.info(
            "PIVOX_CS1_CONSENT_ENABLED off — INFORMATION sends would be "
            "blocked by sender gate; dispatcher short-circuit",
        )
        summary["flag_off"] = 1
        return summary

    # Lazy import: pulls Flask app context dependencies (models /
    # extensions) only when the flags are actually on. Keeps the
    # dormant-cron import surface minimal.
    from services.customer.inactive_nudge import (
        dispatch_inactive_nudges,
        find_inactive_users,
    )
    from models import User
    from datetime import timedelta

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # Pre-probe count — how many rows fall in the window BEFORE the
    # activity filter, so we can split ``skipped_active`` cleanly.
    # The service collapses these two passes for callers that don't
    # need the breakdown; here we want the breakdown for the cron
    # summary.
    lower = now - timedelta(hours=25)
    upper = now - timedelta(hours=24)
    try:
        pre_probe = User.query.filter(
            User.created_at >= lower,
            User.created_at < upper,
            User.is_simulated == False,  # noqa: E712
            User.inactive_nudge_sent_at.is_(None),
        ).count()
    except Exception as exc:
        logger.warning(
            "pre-probe count failed (%s) — migration 038 may be missing",
            exc,
        )
        pre_probe = 0

    eligible = find_inactive_users(now=now)
    # ``window_users`` is the pre-activity-probe count (how many rows
    # are in the time window at all) — gives operators an at-a-glance
    # signup volume number even when everyone is active.
    summary["window_users"] = pre_probe
    summary["skipped_active"] = max(0, pre_probe - len(eligible))

    result = dispatch_inactive_nudges(now=now, users=eligible)
    summary["sent"] = result["sent"]
    summary["skipped_send"] = result["skipped_send"] + result["errors"]

    logger.info("inactive_nudge run summary: %s", summary)
    return summary


def main() -> int:
    """CLI entry point — wired into ``scripts/cron/run.sh``.

    Builds a minimal app context so ``models.*.query`` works outside of
    a request handler. Returns 0 on success, 1 on any unhandled
    exception (cron wrapper captures + logs).
    """
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        from app import create_app
        from extensions import db
    except Exception as exc:
        logger.error("create_app import failed: %s", exc)
        return 1

    # Transient app: ALSO registered into the in-process APScheduler
    # (services/scheduler/cron_jobs.py:_wrap_python_main). Suppress the
    # redundant FMP-hitting cache warmup — the main web app already warmed it.
    # create_app reads this env at call time (app.py:355).
    os.environ["POPULATE_CACHE_ON_BOOT"] = "0"
    # Transient CLI/scheduler-tick app: never build the 49-job APScheduler.
    # The advisory lock already prevents a second instance from STARTING, but
    # without this every create_app() still instantiates 49 Job objects +
    # init overhead (same connection-pressure class as POPULATE_CACHE_ON_BOOT).
    # crontab runs these standalone, so the scheduler is never wanted here.
    os.environ.setdefault("RUN_SCHEDULER", "0")

    try:
        app = create_app()
    except Exception as exc:
        logger.error("create_app() failed: %s", exc)
        return 1

    try:
        with app.app_context():
            try:
                summary = run_once()
            except Exception as exc:
                logger.exception("inactive_nudge dispatcher crashed: %s", exc)
                return 1
    finally:
        # Release the transient QueuePool now rather than letting it linger
        # ~300s toward Railway PG's 25-conn ceiling. Harmless standalone.
        try:
            db.engine.dispose()
        except Exception:
            logger.debug("engine dispose failed (non-fatal)", exc_info=True)

    print(f"inactive_nudge summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
