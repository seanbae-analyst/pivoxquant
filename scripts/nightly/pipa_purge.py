#!/usr/bin/env python3
"""PIPA §21 30-day automatic purge (Wave I C-2) — cron entry point.

Hard-deletes users whose ``deletion_requested_at`` is ≥ 30 days old
AND whose ``deleted_at`` is still NULL (i.e. not yet purged). For each
candidate:

  1. Delete all user-owned rows via explicit per-model DELETE
     (belt-and-suspenders on top of FK CASCADE; see
     ``routes/auth.py:delete_account`` for the same defensive pattern).
  2. Anonymize ``auth_events`` rows whose ``email`` matches — replaced
     with a salted SHA256 hash so aggregate audit (per-provider fail
     rate, hourly volume) survives without identifying the principal.
  3. Stamp ``users.deleted_at = NOW()`` + commit (audit-trail evidence
     "purge actually ran") then ``DELETE FROM users`` in the next
     transaction. The 2-step commit preserves the ``deleted_at`` row
     in the binlog/WAL even though the row vanishes after.
  4. Send a TRANSACTIONAL "data purged" email (bypasses §50 gate).

PIPA §21 ①  — 회원 탈퇴 시 지체 없이 파기.
PIPA 시행령 §16 ① — 보관·복구 목적의 30일 grace period 허용.
PIPA §29 — 안전성 확보 조치 (audit log 보존).

Schedule
--------
``30 3 * * *`` (daily 03:30 KST). Off-peak so the cascading deletes
don't compete with US trading-hour traffic. The single daily pass is
sufficient because the 30-day threshold has +24h slack — a row
requested at 03:35 yesterday won't be eligible for purge until 04:00
tomorrow.

Idempotency
-----------
Re-running the cascade on the same user is idempotent (child deletes
match 0 rows the 2nd time; the "data purged" email re-send is
suppressed on a retry). Step 3 commits ``deleted_at`` BEFORE the row
delete (the 2-step commit preserves the stamp in the WAL/binlog as
audit evidence). If a crash lands between the two commits the row is
left ``deleted_at NOT NULL`` but still present ("stuck").
``find_purge_candidates`` deliberately RE-INCLUDES such rows so the
next nightly pass completes the purge automatically — they are no
longer stranded. (The old ``deleted_at IS NULL`` filter skipped them
forever → silent PIPA §21 violation.) A fully-purged user has no row,
so it is never re-processed.

Salt for SHA256 anonymization
-----------------------------
``PIPA_PURGE_SALT`` env var. If missing, defaults to
``SECRET_KEY`` (always set in production) so anonymization is never
unsalted. The salt is per-deployment — DB migration would re-anonymize
with the new salt and break audit linkage, which is the correct
behavior (audit holds historical aggregates only).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


GRACE_PERIOD_DAYS = 30


# ── helpers ──────────────────────────────────────────────────────────────────

def _hash_email(email: str) -> str:
    """``sha256(salt + email)`` — services/account_erasure.hash_email 한 벌."""
    from services.account_erasure import hash_email
    return hash_email(email)


def _cancel_stripe_subscription(user) -> None:
    """Cancel the user's live Stripe subscription, if any. Never raises.

    Backstop for the request-time cancel in ``routes/auth.py:delete_request``:
    if that call failed (Stripe outage at request time) the subscription would
    keep billing through the 30-day grace window. We re-attempt here right
    before the row is hard-deleted so Stripe can never bill a purged user
    (전자상거래법 §17 / PIPA §21). Idempotent — an already-cancelled / unknown
    subscription raises ``StripeError`` which we log + swallow.
    """
    sub_id = getattr(user, "stripe_subscription_id", None)
    if not sub_id:
        return
    try:
        import stripe
        if not getattr(stripe, "api_key", None):
            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
        stripe.Subscription.cancel(sub_id)
        logger.info(
            "pipa_purge: stripe subscription cancelled user_id=%s sub=%s",
            getattr(user, "id", "?"), sub_id,
        )
    except Exception:
        logger.exception(
            "pipa_purge: stripe cancel failed (non-fatal) user_id=%s sub=%s",
            getattr(user, "id", "?"), sub_id,
        )


def _slack_alert(text: str) -> None:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    try:
        import requests
        requests.post(webhook, json={"text": text}, timeout=10)
    except Exception:
        logger.exception("slack alert post failed (non-fatal)")


# ── candidates ──────────────────────────────────────────────────────────────

def find_purge_candidates(*, now: datetime | None = None):
    """Return list of User rows eligible for hard-delete.

    Eligibility:
      * ``deletion_requested_at`` is NOT NULL
      * ``deletion_requested_at <= now - 30 days``

    Includes BOTH fresh candidates (``deleted_at`` IS NULL) and "stuck"
    rows from a prior crashed pass (``deleted_at`` IS NOT NULL but the
    row still exists — the 2-step commit stamped ``deleted_at`` then the
    process died before the row delete). Re-running the cascade on a
    stuck row is idempotent and completes the purge, so we no longer
    filter them out (that previously stranded them forever → PIPA §21).
    A successfully-purged user has no row at all, so it can never match.
    """
    from models import User

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    threshold = now - timedelta(days=GRACE_PERIOD_DAYS)

    return (
        User.query.filter(
            User.deletion_requested_at.isnot(None),
            User.deletion_requested_at <= threshold,
        )
        # NOTE: intentionally NOT filtering ``deleted_at IS NULL`` — stuck
        # rows (deleted_at stamped, row not yet deleted) must be re-attempted,
        # and a fully-purged user has no row to match. See module docstring.
        .all()
    )


# ── core delete cascade ──────────────────────────────────────────────────────

def _delete_user_cascade(user_id: int, email: str, *, send_email: bool = True) -> dict:
    """Hard-delete one user + all owned rows. Returns a counts dict.

    The row purge itself is ``services.account_erasure.purge_user_rows`` —
    the same one ``routes/auth.py:delete_account`` calls. A new user-owned
    model goes there, once.

    The ``auth_events`` table is *anonymized in place* (email → SHA256
    hash) rather than deleted, so the aggregate audit trail (per-provider
    fail rate, hourly OAuth volume) survives the principal.
    """
    from extensions import db
    from models import User
    from services.account_erasure import purge_user_rows

    # 명시 목록 → 동적 users-FK 스윕 → 모델 없는 허용 목록 → auth_events
    # 익명화. 표마다 SAVEPOINT 라 한 표의 실패가 이 유저의 파기 전체를 멈추지
    # 않는다 (전에는 savepoint 가 없어 예외 한 번에 유저 전체가 롤백·skip).
    counts, failures = purge_user_rows(user_id, email)
    if failures:
        logger.error(
            "pipa_purge: user_id=%s unpurged tables=%s (continuing to row delete)",
            user_id, failures,
        )

    # ── stamp deleted_at + commit (audit-trail evidence) ─────────────────────
    user = User.query.get(user_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # A user whose deleted_at is already set is a "stuck" retry from a prior
    # crashed pass (find_purge_candidates re-includes those). Track it so the
    # one-time "data purged" email isn't re-sent on the retry.
    is_retry = bool(user is not None and user.deleted_at is not None)
    if user is not None:
        user.deleted_at = now
        db.session.commit()
        logger.info(
            "pipa_purge: deleted_at stamped user_id=%s at=%s "
            "(cascade counts=%s)",
            user_id, now.isoformat(), counts,
        )

    # ── cancel any live Stripe subscription before the row vanishes ──────────
    # Backstop for the request-time cancel; idempotent on already-cancelled.
    if user is not None:
        _cancel_stripe_subscription(user)

    # ── send TRANSACTIONAL "purge complete" email BEFORE deleting row ────────
    # Skip on a stuck-row retry — the email already went out on the first pass.
    if user is not None and not is_retry and send_email:
        try:
            _send_purge_complete_email(user)
        except Exception:
            logger.exception(
                "purge-complete email failed (non-fatal) user_id=%s", user_id,
            )

    # ── final hard delete of the User row ────────────────────────────────────
    if user is not None:
        db.session.delete(user)
        db.session.commit()
        counts["user"] = 1

    return counts


def _send_purge_complete_email(user) -> bool:
    """Send TRANSACTIONAL "data fully purged" email. Bypasses §50 gate."""
    from html import escape
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    user_name = escape((getattr(user, "name", "") or "").strip() or "고객")

    html_body = f"""<!doctype html>
<html lang="ko"><body style="margin:0;padding:24px;background:#F6F3EC;
font-family:'Source Serif 4',Georgia,serif;color:#0A0A0A;">
  <div style="max-width:560px;margin:0 auto;background:#FBFAF6;padding:32px;">
    <p style="margin:0;font-size:11px;letter-spacing:0.28em;
      text-transform:uppercase;color:#B8956A;">PIVOXQUANT &middot; 파기 완료</p>
    <h1 style="margin:16px 0 8px 0;font-size:20px;line-height:1.32;
      font-weight:600;letter-spacing:-0.01em;">
      {user_name}님, 계정 파기가 완료되었습니다.
    </h1>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      개인정보보호법 §21 ① 에 따라 30일 grace period 가 종료되어 모든 개인정보
      및 거래 기록이 영구 파기되었습니다.
    </p>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      보안 감사 목적(§29 안전성 확보 조치) 으로 일부 로그는 SHA256 해시
      형태로 익명 보존되며, 이는 더 이상 회원님을 식별할 수 없는 정보입니다.
    </p>
    <p style="margin:24px 0 0 0;font-size:11px;color:#888;">
      본 메일은 거래 관련(transactional) 정보로 §50 광고성 정보 발신에
      해당하지 않습니다.
    </p>
  </div>
</body></html>"""

    return EmailSender().send(
        user,
        subject="[PivoxQuant] 계정 파기 완료 안내 (PIPA §21)",
        html_body=html_body,
        from_env_var="PURGE_COMPLETE_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.TRANSACTIONAL,
    )


# ── main dispatch ────────────────────────────────────────────────────────────

def run_once(*, now: datetime | None = None) -> dict[str, int]:
    """Single pass. Returns summary dict.

    Keys:
      - ``candidates``    : count eligible (≥ 30d, deleted_at NULL)
      - ``purged``        : count successfully hard-deleted
      - ``errors``        : count of candidates that raised mid-cascade
      - ``rows_deleted``  : total dependent rows removed across all users
      - ``auth_events_anon``: total auth_events rows anonymized
    """
    from extensions import db

    summary = {
        "candidates": 0,
        "purged": 0,
        "errors": 0,
        "rows_deleted": 0,
        "auth_events_anon": 0,
    }

    candidates = find_purge_candidates(now=now)
    summary["candidates"] = len(candidates)
    if not candidates:
        logger.info("pipa_purge: no candidates over 30d threshold")
        return summary

    for user in candidates:
        try:
            counts = _delete_user_cascade(user.id, user.email)
            summary["purged"] += 1
            summary["rows_deleted"] += sum(
                v for k, v in counts.items()
                if k not in ("user", "auth_events_anonymized")
            )
            summary["auth_events_anon"] += counts.get("auth_events_anonymized", 0)
        except Exception:
            db.session.rollback()
            logger.exception(
                "pipa_purge: cascade failed for user_id=%s — skipped",
                user.id,
            )
            summary["errors"] += 1

    if summary["errors"] > 0:
        _slack_alert(
            f"PivoxQuant pipa_purge errors={summary['errors']} "
            f"purged={summary['purged']}/{summary['candidates']}",
        )

    logger.info("pipa_purge summary: %s", summary)
    return summary


def main() -> int:
    """CLI entry. Returns 0 on success, 1 on crash."""
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

    # Transient app — built inside the live web process when the in-process
    # APScheduler runs this job (services/scheduler/cron_jobs.py:
    # _wrap_python_main), and standalone by crontab. Either way: no cache
    # warmup (the web app already warmed it; FMP quota) and never a second
    # APScheduler. Pass it as keywords, NOT os.environ — prod has
    # RUN_SCHEDULER=1, so setdefault("RUN_SCHEDULER","0") was a no-op and
    # each tick's scheduler replaced the live one in observability.alerts.

    try:
        app = create_app(start_scheduler=False, populate_cache=False)
    except Exception as exc:
        logger.error("create_app() failed: %s", exc)
        return 1

    try:
        with app.app_context():
            try:
                summary = run_once()
            except Exception:
                logger.exception("pipa_purge crashed")
                return 1
    finally:
        # Release the transient QueuePool now rather than letting it linger
        # ~300s toward Railway PG's 25-conn ceiling. Harmless standalone.
        try:
            # db.engine resolves through the app context, which the `with`
            # above has already popped — without re-entering it this raised
            # "Working outside of application context" into the except below
            # and the pool was never released.
            with app.app_context():
                db.engine.dispose()
        except Exception:
            logger.debug("engine dispose failed (non-fatal)", exc_info=True)

    print(f"pipa_purge summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
