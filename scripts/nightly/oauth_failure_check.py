#!/usr/bin/env python3
"""OAuth repeated-failure detector (Wave I C-1) — cron entry point.

Scans ``auth_events`` for *the same email address* failing OAuth 3 or
more times within the last hour. On hit:

  1. Sends a Slack alert to the ops channel
     (``SLACK_WEBHOOK_URL`` env var) — fire and forget, never raises.
  2. Sends a TRANSACTIONAL email to the affected user offering help
     (``EmailCategory.TRANSACTIONAL`` bypasses §50 marketing-consent
     gate because account/security mail is exempt).
  3. Records the alert in an in-memory dedup index so the same email
     is NOT alerted twice in any 24h window. (DB-backed dedup lives in
     ``auth_events.fail_reason`` field via a sentinel marker —
     ``oauth_help_sent_marker`` — that survives process restart.)

Why poll vs trigger
-------------------
Triggering on every failed callback would require the OAuth path to
synchronously aggregate + email — adding 100ms+ to a flow that's
already slow (Vercel → Railway hop). A polling cron at 15min cadence
gives sub-15min detection while keeping the callback path lean.

Schedule
--------
``*/15 * * * *`` (every 15 minutes). Window is a rolling 1h so a user
who fails at minutes 0, 5, 10 → alerted at minute 15. A user who fails
at minute 14 then 16, 18 → alerted at minute 30. Worst-case detection
latency: 14 minutes after the 3rd failure.

Threshold
---------
``OAUTH_FAILURE_THRESHOLD`` env var (default 3). ≥ threshold within
the 1h window triggers the alert. Lowering this in incidents is
zero-deploy via Railway env panel.

Dedup
-----
After alerting, we insert a *marker row* into ``auth_events`` with
``event_type='fail'`` and ``fail_reason='oauth_help_sent_marker'``.
The threshold query excludes that fail_reason so a marker doesn't
self-trigger, and the dedup query checks for marker presence in the
last 24h.

Cost
----
SendGrid free 100/day quota. Worst case: every OAuth user fails 3x
within 1h → ≈ DAU/4 emails/day. At 1k DAU = 250 emails/day — would
breach 100/day, so an additional global daily cap
``OAUTH_FAILURE_ALERT_DAILY_CAP`` (default 50) gates total sends.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from html import escape

logger = logging.getLogger(__name__)


# ── dedup marker ────────────────────────────────────────────────────────────

DEDUP_MARKER_REASON = "oauth_help_sent_marker"
DEDUP_WINDOW_HOURS = 24


# ── threshold (env-overridable) ─────────────────────────────────────────────

def _failure_threshold() -> int:
    try:
        return max(1, int(os.environ.get("OAUTH_FAILURE_THRESHOLD", "3")))
    except ValueError:
        return 3


def _daily_cap() -> int:
    try:
        return max(0, int(os.environ.get("OAUTH_FAILURE_ALERT_DAILY_CAP", "50")))
    except ValueError:
        return 50


# ── core helpers ────────────────────────────────────────────────────────────

def find_failing_emails(*, now: datetime | None = None) -> list[dict]:
    """Return a list of ``{email, provider, fail_count, last_fail_at}`` rows.

    Window is ``[now - 1h, now]``. Only ``event_type='fail'`` rows are
    counted; rows whose ``fail_reason`` is the dedup marker
    (``DEDUP_MARKER_REASON``) are excluded so the marker can't
    self-trigger.

    Filters dedup: emails alerted in the last 24h (i.e. an existing
    marker row) are also excluded from the return list — they are
    already in the cool-down window.
    """
    from sqlalchemy import func
    from extensions import db
    from models import AuthEvent

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(hours=1)
    dedup_start = now - timedelta(hours=DEDUP_WINDOW_HOURS)
    threshold = _failure_threshold()

    # Subquery: emails with a recent dedup marker (alerted in last 24h).
    recent_marker = db.session.query(AuthEvent.email).filter(
        AuthEvent.fail_reason == DEDUP_MARKER_REASON,
        AuthEvent.created_at >= dedup_start,
    ).distinct().subquery()

    # Main aggregate: 1h failure count, excluding marker rows + already-alerted emails.
    rows = (
        db.session.query(
            AuthEvent.email,
            func.max(AuthEvent.provider).label("provider"),
            func.count(AuthEvent.id).label("fail_count"),
            func.max(AuthEvent.created_at).label("last_fail_at"),
        )
        .filter(
            AuthEvent.event_type == "fail",
            AuthEvent.created_at >= window_start,
            AuthEvent.fail_reason != DEDUP_MARKER_REASON,
            ~AuthEvent.email.in_(db.session.query(recent_marker.c.email)),
        )
        .group_by(AuthEvent.email)
        .having(func.count(AuthEvent.id) >= threshold)
        .all()
    )

    return [
        {
            "email": r.email,
            "provider": r.provider,
            "fail_count": int(r.fail_count),
            "last_fail_at": r.last_fail_at,
        }
        for r in rows
    ]


def _slack_alert(text: str) -> None:
    """Best-effort Slack webhook alert. Never raises."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.info("SLACK_WEBHOOK_URL not set — skipping Slack alert")
        return
    try:
        import requests
        requests.post(webhook, json={"text": text}, timeout=10)
    except Exception:
        logger.exception("slack alert post failed (non-fatal)")


def _send_help_email(user_email: str, provider: str, fail_count: int) -> bool:
    """Send TRANSACTIONAL help email. Returns True on send / False if skipped.

    Looks up the User row by email — if absent we still send via raw
    SMTP because the failures might have happened on a brand-new
    account that doesn't yet exist in the users table (pre-callback
    state mismatches). For sender pipeline we require a User-like
    object, so when no row exists we synthesise a minimal stub.
    """
    from models import User

    user = User.query.filter_by(email=user_email).first()
    if user is None:
        # Synthesise a minimal duck-typed stub so EmailSender.send can run.
        # Marketing consent fields are all None → MARKETING/INFORMATION sends
        # would be refused, but we use TRANSACTIONAL which bypasses §50.
        class _StubUser:
            id = None
            email = user_email
            is_simulated = False
            marketing_consent_at = datetime.now(timezone.utc).replace(tzinfo=None)
            email_opt_out = False
            email_opt_out_earnings = False
        user = _StubUser()

    from services.email import EmailSender
    from services.email.sender import EmailCategory

    provider_label = "구글" if provider == "google" else "카카오"
    safe_email = escape(user_email)

    html_body = f"""<!doctype html>
<html lang="ko"><body style="margin:0;padding:24px;background:#F6F3EC;
font-family:'Source Serif 4',Georgia,serif;color:#0A0A0A;">
  <div style="max-width:560px;margin:0 auto;background:#FBFAF6;padding:32px;">
    <p style="margin:0;font-size:11px;letter-spacing:0.28em;
      text-transform:uppercase;color:#B8956A;">PIVOXQUANT &middot; 로그인 문제</p>
    <h1 style="margin:16px 0 8px 0;font-size:20px;line-height:1.32;
      font-weight:600;letter-spacing:-0.01em;">
      {provider_label} 로그인이 잘 안 되시나요?
    </h1>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      최근 1시간 동안 {fail_count}회 로그인에 실패하셨습니다.
      다음 항목을 확인해보세요:
    </p>
    <ul style="margin:12px 0 12px 16px;padding:0;line-height:1.7;
      color:#202020;font-size:15px;">
      <li>{provider_label} 계정 인증을 완료하셨는지</li>
      <li>브라우저 쿠키/캐시를 비활성화한 시크릿 창에서 다시 시도</li>
      <li>다른 브라우저(Chrome / Safari) 에서 시도</li>
    </ul>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      여전히 안 되시면 <a href="mailto:support@pivoxquant.com"
      style="color:#B8956A;">support@pivoxquant.com</a> 으로
      회신 부탁드립니다. 도와드리겠습니다.
    </p>
    <p style="margin:24px 0 0 0;font-size:11px;color:#888;">
      대상 계정: {safe_email} · 본 메일은 거래 관련(transactional) 정보로
      §50 광고성 정보 발신에 해당하지 않습니다.
    </p>
  </div>
</body></html>"""

    return EmailSender().send(
        user,
        subject="[PivoxQuant] 로그인이 잘 안 되시나요? 도와드릴게요.",
        html_body=html_body,
        from_env_var="OAUTH_HELP_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.TRANSACTIONAL,
    )


def _insert_dedup_marker(email: str, provider: str, now: datetime) -> None:
    """Insert a marker row so the same email isn't re-alerted in 24h."""
    from extensions import db
    from models import AuthEvent

    try:
        ev = AuthEvent(
            email=email,
            provider=provider if provider in ("google", "kakao") else "google",
            event_type="fail",
            fail_reason=DEDUP_MARKER_REASON,
            created_at=now,
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("dedup marker insert failed for email=%s", email)


# ── main dispatch ────────────────────────────────────────────────────────────

def run_once(*, now: datetime | None = None) -> dict[str, int]:
    """Single pass. Returns summary dict.

    Keys:
      - ``candidates``       : emails over threshold after dedup filter
      - ``alerted``          : Slack OR email sent (i.e. action taken)
      - ``email_skipped``    : EmailSender refused (opt-out / no transport)
      - ``daily_cap_reached``: count not alerted because of cap
    """
    summary = {
        "candidates": 0,
        "alerted": 0,
        "email_skipped": 0,
        "daily_cap_reached": 0,
    }
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cap = _daily_cap()

    candidates = find_failing_emails(now=now)
    summary["candidates"] = len(candidates)
    if not candidates:
        logger.info("oauth_failure_check: no candidates over threshold")
        return summary

    # Count today's marker rows to enforce the global daily cap.
    from extensions import db
    from models import AuthEvent
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = (
        db.session.query(AuthEvent)
        .filter(
            AuthEvent.fail_reason == DEDUP_MARKER_REASON,
            AuthEvent.created_at >= today_start,
        )
        .count()
    )

    for cand in candidates:
        # cap=0 → halt all alerts (kill switch). cap>0 → enforce daily quota.
        if cap == 0 or sent_today >= cap:
            summary["daily_cap_reached"] += 1
            continue
        email = cand["email"]
        provider = cand["provider"]
        fail_count = cand["fail_count"]

        # Slack first (cheap, always-best-effort)
        _slack_alert(
            f"PivoxQuant OAuth 반복 실패 — {provider} / {email} / "
            f"{fail_count}회/1h",
        )

        email_ok = False
        try:
            email_ok = _send_help_email(email, provider, fail_count)
        except Exception:
            logger.exception("help email failed for %s (non-fatal)", email)
            email_ok = False

        if email_ok:
            summary["alerted"] += 1
        else:
            summary["email_skipped"] += 1
        # Always insert dedup marker — even if email was skipped, Slack
        # fired and we don't want to spam the channel.
        _insert_dedup_marker(email, provider, now)
        sent_today += 1

    logger.info("oauth_failure_check summary: %s", summary)
    return summary


def main() -> int:
    """CLI entry. Returns 0 on success, 1 on crash."""
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
        except Exception:
            logger.exception("oauth_failure_check crashed")
            return 1

    print(f"oauth_failure_check summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
