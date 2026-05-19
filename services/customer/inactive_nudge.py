"""24-hour onboarding inactive-nudge service (Wave G C-S2).

Library surface for the C-S2 nudge — the cron entry point lives at
``scripts/nightly/inactive_nudge_dispatcher.py`` and delegates to the
two public helpers here:

* :func:`find_inactive_users` — query the rolling 24h-25h signup
  window for users with zero activity and a NULL
  ``inactive_nudge_sent_at`` column.
* :func:`dispatch_inactive_nudges` — render the email template, hand it
  to :class:`EmailSender` (which enforces the per-category §50 ① consent
  gate), and stamp ``users.inactive_nudge_sent_at`` on success.

Why a thin service wrapper around the dispatcher?
-------------------------------------------------
The cron script needs:
  * a single ``main()`` for crontab,
  * a single ``run_once()`` for tests.
The Flask app needs:
  * the underlying query for an admin "preview pending nudges" pane,
  * the dispatch helper for an admin "send now" button (post-launch).

Splitting them lets the admin panes import without dragging in the
cron-level ``argparse``/``logging.basicConfig`` boilerplate.

§50 ① 분류
----------
Onboarding nudges are timer-triggered, not user-action-triggered, so
they are NOT transactional. They fall under INFORMATION (정보성) and
require the user's information-consent boolean
(``marketing_consent_information_at``) on top of the umbrella
``marketing_consent_at``. The EmailSender's category gate enforces
this — we just pass ``EmailCategory.INFORMATION``.

Feature flags (both required to fire)
-------------------------------------
* ``PIVOX_INACTIVE_NUDGE_ENABLED``  — dispatcher kill switch
* ``PIVOX_CS1_CONSENT_ENABLED``     — global §50 consent enforcement

With either flag off, the dispatcher short-circuits BEFORE the
query — the goal is to avoid burning DB budget on a no-op pass.

Idempotency
-----------
Each successful send writes ``users.inactive_nudge_sent_at = now()``;
:func:`find_inactive_users` filters ``IS NULL`` so a user can be
nudged at most once. The column is added by migration
``038_inactive_nudge_sent_at``.

Activity probe
--------------
A "no activity" user has ZERO rows across
``Artifact``, ``Position``, ``TradeHistory``. The probe runs three
indexed COUNT queries; for cron-window sizes (~30 rows/day in the
worst case) this is sub-millisecond per user.

Cost
----
SendGrid free tier = 100 sends/day. At 1k DAU with even ramp the
worst-case daily volume of this nudge is ~30 sends — well inside
quota. Brevo provides a 300/day fallback if SendGrid 4xx's.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Email template directory — keep next to other customer templates so
# the Phase 7 Jinja loader (services/email/templates/) finds them.
_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "email" / "templates" / "customer"


# ── public surface ──────────────────────────────────────────────────────────


def find_inactive_users(
    now: datetime | None = None,
    *,
    window_lower_hours: float = 25.0,
    window_upper_hours: float = 24.0,
) -> list[Any]:
    """Return users in the inactive-nudge eligible cohort.

    A user is eligible iff ALL of:
      * ``created_at`` ∈ ``[now - lower, now - upper)``  (default 24h-25h)
      * ``is_simulated`` is False
      * ``inactive_nudge_sent_at`` is NULL
      * activity probe returns False (no artefact / position / trade)

    The first three conditions are SQL filters (cheap); the activity
    probe is per-row (still cheap — ~30 rows/day worst case).

    Args:
        now: timestamp for window math. Defaults to ``utcnow()``
            (naive UTC to match ``User.created_at`` storage).
        window_lower_hours: how far back the window extends (default 25h).
        window_upper_hours: how recent the window cuts off (default 24h).
            Must be < ``window_lower_hours``.

    Returns:
        List of User ORM rows. Empty if column missing, no rows
        match, or both flags off (caller checks flags separately).
    """
    if window_upper_hours >= window_lower_hours:
        raise ValueError(
            "window_upper_hours must be smaller than window_lower_hours "
            f"(got upper={window_upper_hours}, lower={window_lower_hours})"
        )

    from models import User

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    lower = now - timedelta(hours=window_lower_hours)
    upper = now - timedelta(hours=window_upper_hours)

    q = User.query.filter(
        User.created_at >= lower,
        User.created_at < upper,
        User.is_simulated == False,  # noqa: E712 — SQLAlchemy boolean
    )

    # ``inactive_nudge_sent_at`` is added by migration 038. Guard the
    # filter so a stale schema doesn't crash the whole run — log and
    # skip (caller treats empty list as a no-op).
    try:
        q = q.filter(User.inactive_nudge_sent_at.is_(None))
    except Exception as exc:
        logger.warning(
            "inactive_nudge_sent_at column unavailable (%s); "
            "alembic migration 038 may not be applied — returning empty cohort",
            exc,
        )
        return []

    rows = q.all()

    # Per-row activity probe. Could collapse into SQL EXISTS, but
    # readability + tiny N make this fine.
    return [u for u in rows if not _is_active(u.id)]


def dispatch_inactive_nudges(
    now: datetime | None = None,
    users: Iterable[Any] | None = None,
) -> dict[str, int]:
    """Send the inactive-nudge email to each eligible user.

    Args:
        now: timestamp stamped onto ``inactive_nudge_sent_at`` on
            success. Defaults to ``utcnow()``.
        users: optional iterable to override the query (admin "send
            now" / test). When None, calls :func:`find_inactive_users`.

    Returns:
        Summary dict::

            {
              "candidates":    int,  # rows passed to send loop
              "sent":          int,  # EmailSender accepted
              "skipped_send":  int,  # EmailSender refused (opt-out / consent / no transport)
              "errors":        int,  # exception in send path
            }

        Caller (cron / admin) adds higher-level keys
        (``window_users``, ``skipped_active``, ``flag_off``).
    """
    from extensions import db

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if users is None:
        # Note: ``find_inactive_users`` already filters out active users,
        # so ``candidates`` == "post-activity-probe cohort size".
        users = find_inactive_users(now=now)

    summary = {
        "candidates":   0,
        "sent":         0,
        "skipped_send": 0,
        "errors":       0,
    }

    for user in users:
        summary["candidates"] += 1
        try:
            ok = _send_one(user)
        except Exception as exc:
            logger.exception(
                "inactive_nudge send raised for user %s: %s", user.id, exc,
            )
            summary["errors"] += 1
            continue

        if not ok:
            summary["skipped_send"] += 1
            continue

        summary["sent"] += 1

        # Idempotency stamp — done OUTSIDE the send so a provider
        # latency spike doesn't roll back the write. Per-user commit
        # keeps the stamp atomic with the sender result.
        try:
            user.inactive_nudge_sent_at = now
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.warning(
                "inactive_nudge_sent_at write failed for user %s: %s",
                user.id, exc,
            )

    logger.info("inactive_nudge dispatch summary: %s", summary)
    return summary


# ── internals ───────────────────────────────────────────────────────────────


def _is_active(user_id: int) -> bool:
    """Return True iff the user has any artefact / position / trade row.

    Fail-closed: if the probe raises (DB hiccup), treat the user as
    active so we never send during uncertainty. §50 ① compliance >
    a stray send.
    """
    from models import Artifact, Position, TradeHistory

    try:
        if Artifact.query.filter_by(user_id=user_id).count() > 0:
            return True
        if Position.query.filter_by(user_id=user_id).count() > 0:
            return True
        if TradeHistory.query.filter_by(user_id=user_id).count() > 0:
            return True
    except Exception as exc:
        logger.warning(
            "activity probe failed for user %s: %s — assuming active "
            "(fail-closed for §50 safety)",
            user_id, exc,
        )
        return True
    return False


def _render_email(user_name: str) -> tuple[str, str]:
    """Render the HTML + text bodies. Returns ``(html, text)``.

    Templates are loaded from disk so copy edits don't require a
    code change. Falls back to an inline minimal HTML / text if a
    template is missing (resilience > prettiness in a cron path).
    """
    name = escape((user_name or "").strip() or "Investor")
    dashboard_url = os.environ.get(
        "PIVOX_DASHBOARD_URL", "https://pivoxquant.com/home",
    )
    safe_url = escape(dashboard_url)

    html_path = _TEMPLATE_DIR / "inactive_nudge.html"
    text_path = _TEMPLATE_DIR / "inactive_nudge.txt"

    try:
        html = html_path.read_text(encoding="utf-8")
        html = html.replace("{{user_name}}", name).replace(
            "{{dashboard_url}}", safe_url
        )
    except Exception as exc:
        logger.warning("inactive_nudge.html missing/unreadable (%s); using inline", exc)
        html = (
            f"<p>{name}님, PivoxQuant 시작 가이드를 안내드립니다.</p>"
            f"<p><a href=\"{safe_url}\">지금 시작하기</a></p>"
        )

    try:
        text = text_path.read_text(encoding="utf-8")
        text = text.replace("{{user_name}}", name).replace(
            "{{dashboard_url}}", safe_url
        )
    except Exception as exc:
        logger.warning("inactive_nudge.txt missing/unreadable (%s); using inline", exc)
        text = (
            f"{name}님, PivoxQuant 시작 가이드를 안내드립니다.\n"
            f"지금 시작하기: {safe_url}\n"
        )

    return html, text


def _send_one(user: Any) -> bool:
    """Send the nudge to a single user. Returns the sender's bool.

    The sender enforces the per-category §50 ① gate; we don't second-
    guess it here. A False return means the sender refused (opt-out,
    missing INFORMATION consent, or no transport configured) and is
    NOT an error — caller increments ``skipped_send``.
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    user_name = (getattr(user, "name", "") or "").strip()
    if not user_name:
        email = getattr(user, "email", "") or ""
        user_name = email.split("@")[0] if email else "Investor"

    html_body, _text_body = _render_email(user_name)
    # EmailSender.send() only accepts ``html_body`` — the underlying
    # transports derive a text-only fallback from the HTML. We still
    # render the text template so cron-mode operators can preview the
    # plain-text body (and so a future EmailSender refactor that
    # accepts ``text_body`` finds it ready).

    return EmailSender().send(
        user,
        subject="5분 가이드: PivoxQuant 시작하기",
        html_body=html_body,
        from_env_var="INACTIVE_NUDGE_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.INFORMATION,
    )
