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
``deleted_at IS NULL`` filter prevents re-processing. If a purge
crashes mid-cascade we restart from the same candidate set on the
next run — but step 3 commits ``deleted_at`` BEFORE the row delete,
so a crash between steps 3 and 4 leaves the row in
``deleted_at NOT NULL`` state which is then skipped on next pass.
(Manual ops cleanup needed for those — logged + Slack-alerted.)

Salt for SHA256 anonymization
-----------------------------
``PIPA_PURGE_SALT`` env var. If missing, defaults to
``SECRET_KEY`` (always set in production) so anonymization is never
unsalted. The salt is per-deployment — DB migration would re-anonymize
with the new salt and break audit linkage, which is the correct
behavior (audit holds historical aggregates only).
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


GRACE_PERIOD_DAYS = 30


# ── helpers ──────────────────────────────────────────────────────────────────

def _purge_salt() -> str:
    return (
        os.environ.get("PIPA_PURGE_SALT")
        or os.environ.get("SECRET_KEY")
        or "pivoxquant-purge-fallback-salt-do-not-use-in-prod"
    )


def _hash_email(email: str) -> str:
    """Return ``sha256(salt + email)`` hex digest (length 64)."""
    salt = _purge_salt().encode("utf-8")
    return hashlib.sha256(salt + (email or "").encode("utf-8")).hexdigest()


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
      * ``deleted_at`` IS NULL
    """
    from models import User

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    threshold = now - timedelta(days=GRACE_PERIOD_DAYS)

    return (
        User.query.filter(
            User.deletion_requested_at.isnot(None),
            User.deletion_requested_at <= threshold,
            User.deleted_at.is_(None),
        )
        .all()
    )


# ── core delete cascade ──────────────────────────────────────────────────────

def _delete_user_cascade(user_id: int, email: str) -> dict:
    """Hard-delete one user + all owned rows. Returns a counts dict.

    Mirrors ``routes/auth.py:delete_account`` per-model list (explicit
    deletes over FK CASCADE for defense in depth on SQLite). The list
    is kept in sync — when a new user-owned model is added, BOTH
    delete paths must be updated.

    The ``auth_events`` table is *anonymized in place* (email → SHA256
    hash) rather than deleted, so the aggregate audit trail (per-provider
    fail rate, hourly OAuth volume) survives the principal.
    """
    from extensions import db
    from models import (
        Position, TradeHistory, Alert, Watchlist,
        InvestmentProfile, BrokerConnection, PushSubscription,
        PortfolioShare,
        Artifact, UserReferral,
        ArtifactFeedback, BehavioralScore,
        AITwinPortfolio, AITwinWeeklyReport,
        PreTradeReflection, PersonaSnapshot, WeeklyPulse,
        ScheduledEmail, NpsFeedback, AuthEvent, User,
    )

    counts: dict[str, int] = {}

    def _cnt(label, q):
        n = q.delete(synchronize_session=False)
        counts[label] = n
        return n

    _cnt("position", Position.query.filter_by(user_id=user_id))
    _cnt("trade_history", TradeHistory.query.filter_by(user_id=user_id))
    _cnt("alert", Alert.query.filter_by(user_id=user_id))
    _cnt("watchlist", Watchlist.query.filter_by(user_id=user_id))
    _cnt("investment_profile", InvestmentProfile.query.filter_by(user_id=user_id))
    _cnt("broker_connection", BrokerConnection.query.filter_by(user_id=user_id))
    _cnt("push_subscription", PushSubscription.query.filter_by(user_id=user_id))
    _cnt("portfolio_share", PortfolioShare.query.filter_by(user_id=user_id))
    _cnt("artifact", Artifact.query.filter_by(user_id=user_id))
    _cnt("user_referral", UserReferral.query.filter_by(user_id=user_id))
    _cnt("artifact_feedback", ArtifactFeedback.query.filter_by(user_id=user_id))
    _cnt("behavioral_score", BehavioralScore.query.filter_by(user_id=user_id))
    _cnt("ai_twin_portfolio", AITwinPortfolio.query.filter_by(user_id=user_id))
    _cnt("ai_twin_weekly_report", AITwinWeeklyReport.query.filter_by(user_id=user_id))
    _cnt("pre_trade_reflection", PreTradeReflection.query.filter_by(user_id=user_id))
    _cnt("persona_snapshot", PersonaSnapshot.query.filter_by(user_id=user_id))
    _cnt("weekly_pulse", WeeklyPulse.query.filter_by(user_id=user_id))
    _cnt("scheduled_email", ScheduledEmail.query.filter_by(user_id=user_id))
    _cnt("nps_feedback", NpsFeedback.query.filter_by(user_id=user_id))

    # ── auth_events: anonymize, do NOT delete ────────────────────────────────
    # PIPA §29 requires retention of access/auth logs for security audit
    # purposes. We satisfy that by hashing the email column so the row
    # survives in unidentifiable form. The hash is salted (per-deployment
    # SECRET_KEY) so cross-instance rainbow tables are useless.
    hashed = _hash_email(email)
    anon_n = (
        AuthEvent.query.filter(AuthEvent.email == email)
        .update({AuthEvent.email: hashed}, synchronize_session=False)
    )
    counts["auth_events_anonymized"] = int(anon_n or 0)

    # ── stamp deleted_at + commit (audit-trail evidence) ─────────────────────
    user = User.query.get(user_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
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
    if user is not None:
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
            except Exception:
                logger.exception("pipa_purge crashed")
                return 1
    finally:
        # Release the transient QueuePool now rather than letting it linger
        # ~300s toward Railway PG's 25-conn ceiling. Harmless standalone.
        try:
            db.engine.dispose()
        except Exception:
            logger.debug("engine dispose failed (non-fatal)", exc_info=True)

    print(f"pipa_purge summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
