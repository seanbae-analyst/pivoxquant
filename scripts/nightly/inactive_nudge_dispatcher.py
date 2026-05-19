#!/usr/bin/env python3
"""24-hour onboarding nudge dispatcher (Wave G C-S2).

Purpose
-------
Re-engage signups that never created a brag-card / artefact within
their first 24h. The email is a 5-minute getting-started guide — no
discount language, no promotional copy — but because the trigger is a
*timer* (not a user action), this is classified as INFORMATION under
정통망법 §50 ①, NOT transactional. Consent is required.

§50 분류 / 발송 게이트
---------------------
- ``EmailCategory.INFORMATION`` — surfaces the per-category gate in
  ``services.email.sender.EmailSender.send``.
- Feature flag ``PIVOX_CS1_CONSENT_ENABLED=true`` AND user has
  ``marketing_consent_information_at`` set (and not revoked) → send.
- Either condition off → skip the user (logged but not failed).
- An additional dispatcher-level kill switch
  ``PIVOX_INACTIVE_NUDGE_ENABLED=true`` (default false) gates the
  whole script — out-of-the-box this cron is dormant until the
  lawyer's Q-S1 answer arrives.

Why two switches?
-----------------
The schema-level switch (``PIVOX_CS1_CONSENT_ENABLED``) controls
sender enforcement for every category-aware send across the app. The
dispatcher-level switch (``PIVOX_INACTIVE_NUDGE_ENABLED``) lets us
roll out C-S2 in isolation without touching artefact mailers. Both
must be true for a nudge to leave the building.

Schedule
--------
``0 * * * *`` (every hour, on the hour). One run scans the rolling
24h–25h signup window — the 1h granularity matches the cron cadence
so no signup falls between two scans.

Idempotency
-----------
Per-user ``users.inactive_nudge_sent_at`` column is set on success.
The query filters ``inactive_nudge_sent_at IS NULL`` so the same
user is never re-nudged even on cron overlap. The column is added by
migration 038 (linear from 037).

Activity definition
-------------------
"Activity" = any non-empty count of
  - ``Artifact`` rows (any type) belonging to the user, OR
  - ``Position`` rows, OR
  - ``TradeHistory`` rows.
If any is non-zero, the user is considered active and skipped.

Cost
----
SendGrid 100/day free quota — see top-of-file budget analysis in the
companion docstring at ``services/customer/__init__.py``. Worst case
at 1k users with even ramp = ~30 nudges/day. Well under quota.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

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


# ── activity probe ──────────────────────────────────────────────────────────

def _is_active(user_id: int) -> bool:
    """Return True iff the user has any artefact / position / trade row.

    Cheap COUNT(*) queries — three of them, but indexed on ``user_id``
    so the per-user cost is sub-millisecond. We could compound them
    into a single SQL ``EXISTS`` chain, but readability + the small
    user-window size (24h–25h slice) make this fine.
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
        return True  # fail-closed: never send when probe is uncertain
    return False


# ── window query ─────────────────────────────────────────────────────────────

def _signup_window_users(now: datetime) -> list[Any]:
    """Return users whose ``created_at`` lies in the 24h–25h-ago slice.

    The bounds are inclusive on the lower side and exclusive on the
    upper side: ``[now - 25h, now - 24h)``. Combined with the
    ``inactive_nudge_sent_at IS NULL`` filter this gives every user
    exactly one shot at receiving the nudge.

    The query is intentionally light — `User.query` with the time
    window — so cron-overlap (which would scan the same row twice)
    is cheap.
    """
    from models import User

    lower = now - timedelta(hours=25)
    upper = now - timedelta(hours=24)

    q = User.query.filter(
        User.created_at >= lower,
        User.created_at < upper,
        User.is_simulated == False,  # noqa: E712 — SQLAlchemy boolean compare
    )

    # ``inactive_nudge_sent_at`` is added by migration 038. Guard the
    # column reference so a stale schema (column missing) doesn't crash
    # the dispatcher — it'll just skip the IS NULL filter and rely on
    # the per-send opt-out gate.
    try:
        q = q.filter(User.inactive_nudge_sent_at.is_(None))
    except Exception as exc:
        logger.warning(
            "inactive_nudge_sent_at filter unavailable (%s); skipping cron run",
            exc,
        )
        return []

    return q.all()


# ── send helper ──────────────────────────────────────────────────────────────

def _render_html(user_name: str) -> str:
    """Plain neutral guide copy — no marketing language.

    Inline-CSS only so we can ship this without pulling the Jinja env
    into the cron path. Keeps the script's surface minimal.
    """
    from html import escape

    name = escape(user_name or "Investor")
    dashboard_url = os.environ.get(
        "PIVOX_DASHBOARD_URL", "https://pivoxquant.com/home",
    )
    safe_url = escape(dashboard_url)

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:24px;background:#F6F3EC;
  font-family:'Source Serif 4',Georgia,serif;color:#0A0A0A;">
<div style="max-width:560px;margin:0 auto;background:#FBFAF6;padding:32px;">
  <p style="margin:0;font-size:11px;letter-spacing:0.28em;
    text-transform:uppercase;color:#B8956A;">
    PIVOXQUANT &middot; 시작 가이드</p>
  <h1 style="margin:16px 0 8px 0;font-size:20px;line-height:1.32;
    font-weight:600;letter-spacing:-0.01em;">
    {name}님, 5분 가이드: PivoxQuant 시작하기</h1>
  <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
    가입 후 첫 brag-card 까지 보통 5분이 걸립니다. 아래 단계를 따라
    이번 달 거래 기록을 정리해보세요.</p>
  <ol style="margin:16px 0;padding-left:20px;line-height:1.8;color:#202020;font-size:15px;">
    <li>온보딩 질문 20문항을 완료합니다 (3분).</li>
    <li>증권사 연결 또는 수동으로 첫 포지션을 입력합니다 (1분).</li>
    <li>월간 brag-card 자동 생성 또는 수동 트리거로 카드를 받습니다 (1분).</li>
  </ol>
  <p style="margin:24px 0;">
    <a href="{safe_url}"
      style="display:inline-block;padding:14px 28px;
        background:#0A0A0A;color:#F6F3EC;text-decoration:none;
        font-family:'Source Serif 4',Georgia,serif;font-size:14px;
        letter-spacing:0.04em;">지금 시작하기</a></p>
  <p style="margin:24px 0;font-size:12px;color:#6B6B6B;line-height:1.55;">
    이 메일은 가입 후 24시간 이내 활동이 없는 신규 사용자에게 발송되는
    정보성 안내입니다 (정통망법 §50 ① INFORMATION). 수신을 원치 않으시면
    footer 의 unsubscribe 링크 또는 settings 의 수신 동의에서 정보성
    수신을 해지할 수 있습니다.</p>
</div>
</body></html>"""


def _send_nudge(user: Any) -> bool:
    """Dispatch one nudge. Returns ``True`` on accepted send.

    The send call passes ``email_category=EmailCategory.INFORMATION``
    so the sender's category gate enforces per-user consent when the
    feature flag is on. With the flag off we still short-circuit
    here at the dispatcher level (caller checks ``_cs1_consent_enabled``
    before iterating) so this function is only reached in
    enforcement mode.
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    user_name = (getattr(user, "name", "") or "").strip()
    if not user_name:
        email = getattr(user, "email", "") or ""
        user_name = email.split("@")[0] if email else "Investor"
    html_body = _render_html(user_name)

    return EmailSender().send(
        user,
        subject="5분 가이드: PivoxQuant 시작하기",
        html_body=html_body,
        from_env_var="INACTIVE_NUDGE_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.INFORMATION,
    )


# ── main dispatch ────────────────────────────────────────────────────────────

def run_once(now: datetime | None = None) -> dict[str, int]:
    """Single dispatch pass. Returns a summary dict.

    Summary keys:
      - ``window_users``  : count of rows in the 24h–25h slice
      - ``skipped_active``: had artefact/position/trade activity
      - ``sent``          : email accepted by the EmailSender
      - ``skipped_send``  : sender returned False (opt-out / consent / no transport)
      - ``flag_off``      : dispatcher or CS1 flag is off
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

    from extensions import db

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    users = _signup_window_users(now)
    summary["window_users"] = len(users)

    for user in users:
        if _is_active(user.id):
            summary["skipped_active"] += 1
            continue
        try:
            ok = _send_nudge(user)
        except Exception as exc:
            logger.exception(
                "inactive nudge raised for user %s: %s", user.id, exc,
            )
            ok = False
        if not ok:
            summary["skipped_send"] += 1
            continue
        summary["sent"] += 1
        # Mark the user as nudged so the next hourly run skips them.
        # Done OUTSIDE the send to keep the column write decoupled
        # from provider latency. ``commit`` per-user keeps each
        # write atomic against the sender result.
        try:
            user.inactive_nudge_sent_at = now
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.warning(
                "inactive_nudge_sent_at write failed for user %s: %s",
                user.id, exc,
            )

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
    except Exception as exc:
        logger.error("create_app import failed: %s", exc)
        return 1

    try:
        app = create_app()
    except Exception as exc:
        logger.error("create_app() failed: %s", exc)
        return 1

    with app.app_context():
        try:
            summary = run_once()
        except Exception as exc:
            logger.exception("inactive_nudge dispatcher crashed: %s", exc)
            return 1

    print(f"inactive_nudge summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
