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
    """Single dispatch pass. Returns stats dict.

    All per-row error handling lives inside
    ``onboarding_sequence.dispatch_due`` so the cron's outer loop
    stays trivial.
    """
    from app import create_app
    from services.email.onboarding_sequence import dispatch_due

    app = create_app()
    with app.app_context():
        return dispatch_due()


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
