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

§50 ① 분류 — MARKETING (광고성), 2026-09-07 재분류
------------------------------------------------
Timer-triggered, not user-action-triggered, so not transactional. It was
classified INFORMATION (정보성) on the grounds that the body is usage
guidance. That reading no longer holds.

The other periodic mails were rebuilt to carry the reader's own recorded
counts (services/email/record_summary.py), which is what lets them be a
retrospective statement of fact. **This one cannot**: it is sent precisely
to users who have recorded nothing, so there is no fact to state. What
remains is a message asking someone to come back — 광고성 정보 under
§50 ①. Containing instructions does not make it 정보성.

So it now passes ``EmailCategory.MARKETING`` and carries the full régime:
``(광고)`` in subject and body head, MARKETING consent (not INFORMATION),
the 21:00–08:00 KST night gate (시행령 §61의2), an unsubscribe link, and
the sender-identity block (시행령 §62 ①). ``_send_one`` asserts these at
render time rather than trusting the template to have kept them.

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
            # Same clock the caller passed — the night gate inside
            # _send_one must not read a different one.
            ok = _send_one(user, now=now)
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


def _render_email(
    user_name: str, *, unsubscribe_url: str = "",
) -> tuple[str, str]:
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
        html = (
            html.replace("{{user_name}}", name)
            .replace("{{dashboard_url}}", safe_url)
            .replace("{{unsubscribe_url}}", escape(unsubscribe_url))
        )
    except Exception as exc:
        logger.warning("inactive_nudge.html missing/unreadable (%s); using inline", exc)
        # 폴백도 광고성 규격을 지킨다. 템플릿이 사라진 날 비준수 메일이
        # 나가면 그 폴백이 곧 구멍이다 — (광고) 표시와 수신거부는 필수다.
        html = (
            f"<p>(광고) {name}님, PivoxQuant 를 시작해 보세요.</p>"
            f"<p><a href=\"{safe_url}\">지금 시작하기</a></p>"
            f"<p style=\"font-size:11px;color:#6B6B6B;\">"
            f"PivoxQuant (피복스퀀트) · 사업자등록번호 459-01-03808 · "
            f"support@pivoxquant.com<br/>"
            f"수신거부: <a href=\"{escape(unsubscribe_url)}\">"
            f"{escape(unsubscribe_url)}</a></p>"
        )

    try:
        text = text_path.read_text(encoding="utf-8")
        text = (
            text.replace("{{user_name}}", name)
            .replace("{{dashboard_url}}", safe_url)
            .replace("{{unsubscribe_url}}", unsubscribe_url)
        )
    except Exception as exc:
        logger.warning("inactive_nudge.txt missing/unreadable (%s); using inline", exc)
        text = (
            f"(광고) {name}님, PivoxQuant 를 시작해 보세요.\n"
            f"지금 시작하기: {safe_url}\n\n"
            f"PivoxQuant (피복스퀀트) · 사업자등록번호 459-01-03808\n"
            f"support@pivoxquant.com\n"
            f"수신거부: {unsubscribe_url}\n"
        )

    return html, text


def _send_one(user: Any, *, now: Any = None) -> bool:
    """Send the nudge to a single user. Returns the sender's bool.

    ⚠️ 2026-09-07 — this was reclassified INFORMATION → **MARKETING** (광고성).

    Why: the nudge goes to users who have recorded *nothing*. Every other
    periodic mail was rebuilt to carry the reader's own counts, which is what
    makes those a retrospective statement of fact rather than a solicitation
    (see services/email/record_summary.py). This one structurally cannot do
    that — there is no record to state — so it is, and only ever was, a
    re-engagement message. 정통망법 §50 ① calls that 광고성 정보, and calling
    it 정보성 because it happens to contain usage steps does not change what
    it is. CEO decision 2026-09-07: keep it, ship it honestly.

    Reclassifying is not a label change — it pulls in the full 광고성 régime,
    all of which is asserted below rather than assumed:
      * ``(광고)`` in subject AND body head (시행령 §62 ①)
      * MARKETING consent, not INFORMATION
      * night gate 21:00–08:00 KST (시행령 §61의2)
      * unsubscribe link + sender-identity block in the body

    The sender still enforces the per-category §50 ① gate; the checks here are
    belt-and-braces so a future caller that bypasses ``dispatch_inactive_nudges``
    cannot ship a non-compliant send.
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory
    from services.email.retention_sequence import (
        is_night_kst, _assert_ad_marker, _assert_legal_safe,
    )
    from services.email_token import build_unsubscribe_url

    # 시행령 §61의2 — never at night. Returning False leaves the user in the
    # inactive window for the next hourly tick, which is the desired behaviour.
    if is_night_kst(now):
        return False

    user_name = (getattr(user, "name", "") or "").strip()
    if not user_name:
        email = getattr(user, "email", "") or ""
        user_name = email.split("@")[0] if email else "Investor"

    unsubscribe_url = build_unsubscribe_url(user.id, kind="all")
    html_body, _text_body = _render_email(user_name, unsubscribe_url=unsubscribe_url)
    # EmailSender.send() only accepts ``html_body`` — the underlying
    # transports derive a text-only fallback from the HTML. We still
    # render the text template so cron-mode operators can preview the
    # plain-text body (and so a future EmailSender refactor that
    # accepts ``text_body`` finds it ready).

    subject = "(광고) PivoxQuant 시작하기"

    # Render-time kill switches — same guardrails the retention path uses.
    _assert_ad_marker(subject, html_body, where="inactive_nudge/html")
    _assert_legal_safe(subject, where="inactive_nudge/subject")
    _assert_legal_safe(html_body, where="inactive_nudge/html")

    return EmailSender().send(
        user,
        subject=subject,
        html_body=html_body,
        from_env_var="INACTIVE_NUDGE_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.MARKETING,
    )
