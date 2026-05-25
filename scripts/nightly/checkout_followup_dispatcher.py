#!/usr/bin/env python3
"""PivoxQuant — Stripe checkout abandonment 1h follow-up dispatcher.

Wave G C-M1 (2026-05-19).

Drains the ``checkout_expirations`` queue every cron tick (15 min) and
sends a transactional follow-up email per row whose
``scheduled_send_at <= NOW()`` and ``sent_at IS NULL`` and
``skipped_reason IS NULL``.

Behaviour
---------

* ``PIVOX_CHECKOUT_FOLLOWUP_ENABLED=true``  → for each due row,
  resolve User, suppress already-active subscribers (race window between
  webhook and dispatcher), call
  ``services.billing_followup.send_checkout_followup``. On success
  ``mark_sent``; on permanent failure ``mark_skipped("provider_failed")``
  so the row never re-enters the queue.

* ``PIVOX_CHECKOUT_FOLLOWUP_ENABLED=false`` (default) → still walks the
  queue but stamps ``skipped_reason="feature_flag_off"`` on each due
  row. This keeps the table from growing unbounded while we wait for
  the variance-flag flip + gives an audit trail.

15-minute cadence
-----------------
The +1h delay only needs ±15min precision — the email is a friendly
nudge, not a tightly-timed automation. A 15-min cron lands every
expired row within 1h–1h15min of its expiry, which is well within the
"fresh enough to remember" UX window.

Cost
----
- Database: ~1 query per tick (96 ticks/day). Zero cost.
- SendGrid 100/day free + Brevo 300/day free fallback.
- 추가 비용 0원.

Exit codes
----------
* 0 — clean run (any number of rows processed, including zero).
* 1 — unexpected exception (caught + logged; Slack alert if env set).
* 2 — DB/app boot failure.

Usage
-----
``./venv/bin/python scripts/nightly/checkout_followup_dispatcher.py``

Cron entry (15-min cadence):
``*/15 * * * *  /path/scripts/cron/run.sh checkout-followup``
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure repo root on path so ``from app import create_app`` resolves
# when invoked from any cwd (cron uses /path/to/repo as cwd, but
# defensive sys.path keeps direct invocation working).
_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("checkout_followup_dispatcher")


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
    """Process all due rows in one tick. Returns stats dict."""
    from app import create_app
    from extensions import db
    from models import CheckoutExpiration, User
    from services.billing_followup import (
        followup_enabled,
        send_checkout_followup,
    )

    stats = {
        "due": 0,
        "sent": 0,
        "skipped_flag_off": 0,
        "skipped_no_user": 0,
        "skipped_already_active": 0,
        "skipped_provider_failed": 0,
        "skipped_no_email": 0,
    }

    # Transient app: this dispatcher is ALSO registered into the in-process
    # APScheduler (services/scheduler/cron_jobs.py:_wrap_python_main), so each
    # 15-min tick calls create_app() from a scheduler thread. The main web app
    # already warmed the cache — a second warmup thread here would just burn
    # FMP quota. Suppress it. (create_app reads this env at call time, app.py:355.)
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
            rows = list(CheckoutExpiration.pending_due(limit=100))
            stats["due"] = len(rows)
            if not rows:
                logger.info("no due rows — clean exit")
                return stats

            flag_on = followup_enabled()
            if not flag_on:
                logger.info(
                    "PIVOX_CHECKOUT_FOLLOWUP_ENABLED is off — marking %d "
                    "due rows as feature_flag_off",
                    len(rows),
                )

            for row in rows:
                # Each row processed in its own try/commit so a bad row
                # doesn't poison the rest. Match the per-row resilience
                # used in the artifacts nightly aggregator.
                try:
                    if not flag_on:
                        row.mark_skipped("feature_flag_off")
                        db.session.commit()
                        stats["skipped_flag_off"] += 1
                        continue

                    user = db.session.get(User, row.user_id)
                    if user is None or not getattr(user, "email", None):
                        row.mark_skipped("no_user_or_email")
                        db.session.commit()
                        stats["skipped_no_email"] += 1
                        continue

                    # User completed checkout between expired and now —
                    # don't pester them. ``past_due`` also has a live
                    # subscription (Stripe retrying), so a "finish your
                    # subscription" nudge would be wrong there too.
                    if getattr(user, "subscription_status", None) in ("active", "past_due"):
                        row.mark_skipped("already_subscribed")
                        db.session.commit()
                        stats["skipped_already_active"] += 1
                        continue

                    ok = send_checkout_followup(user=user)
                    if ok:
                        row.mark_sent()
                        stats["sent"] += 1
                    else:
                        row.mark_skipped("provider_failed")
                        stats["skipped_provider_failed"] += 1
                    db.session.commit()
                except Exception as exc:  # noqa: BLE001
                    # Roll back this row's mutation only — others already
                    # committed. Log + continue (cron will retry next tick
                    # but the row is unchanged, so no double-send risk).
                    db.session.rollback()
                    logger.exception(
                        "checkout_followup row failed (id=%s session=%s): %s",
                        row.id, row.session_id, exc,
                    )
    finally:
        # Release the transient QueuePool immediately. Under the in-process
        # scheduler each tick spins a new pool (size 3 + overflow 2 = 5 conns)
        # that would otherwise linger ~300s (pool_recycle) toward Railway PG's
        # 25-conn ceiling. Dispose closes it now. Harmless under standalone
        # crontab (short-lived process exits anyway).
        try:
            db.engine.dispose()
        except Exception:  # noqa: BLE001
            logger.debug("engine dispose failed (non-fatal)", exc_info=True)

    return stats


def main() -> int:
    try:
        stats = _drain_once()
    except Exception as exc:  # noqa: BLE001
        logger.exception("checkout_followup_dispatcher fatal: %s", exc)
        _post_slack(
            f":warning: PivoxQuant checkout-followup dispatcher fatal: {exc}"
        )
        return 1

    logger.info("checkout_followup_dispatcher stats=%s", stats)
    if stats.get("sent", 0) > 0:
        _post_slack(
            f":mailbox_with_mail: PivoxQuant checkout-followup sent "
            f"{stats['sent']}/{stats['due']} (stats: {stats})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
