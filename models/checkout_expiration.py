"""
models/checkout_expiration.py — Stripe checkout abandonment follow-up queue.

Stripe Checkout Sessions expire after a configurable window (default 24h).
When ``checkout.session.expired`` fires we record the abandonment with a
+1h ``scheduled_send_at`` so a transactional follow-up email can land
while the intent is still fresh.

Why a dedicated table (vs piggy-backing on processed_stripe_events)
-------------------------------------------------------------------
``processed_stripe_events`` is an *audit log* with no notion of work
state. The follow-up dispatcher needs (a) a queryable due-time, (b) a
``sent_at`` mutation to mark work complete, and (c) a UNIQUE on Stripe
session id for idempotency across webhook retries. A purpose-built
queue table keeps the audit log immutable + the queue trivial to
inspect during ops triage.

Contract with the webhook handler
---------------------------------
``routes.billing.stripe_webhook`` on event ``checkout.session.expired``:
  1. Resolve User via ``customer`` / metadata.user_id.
  2. ``CheckoutExpiration.enqueue(user_id=..., session_id=...,
     expired_at=...)`` — idempotent on session_id.
  3. ProcessedStripeEvent.record(...) flushes through the surrounding tx.

Contract with the dispatcher (``scripts/nightly/checkout_followup_dispatcher.py``):
  1. ``CheckoutExpiration.pending_due(now=...)`` → row iterator.
  2. For each row: render + send transactional email.
  3. On success: ``row.mark_sent()``. On permanent skip
     (no email / already-active subscription / provider failure):
     ``row.mark_skipped(reason=...)``.
  4. Single commit per row to keep failures local.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.exc import IntegrityError

from extensions import db


# Delay between Stripe's ``expired_at`` and our follow-up dispatch. 1h is
# the spec — short enough to land while the user remembers the abandoned
# checkout, long enough to filter out transient session expirations from
# users who just closed the tab to think about it.
FOLLOWUP_DELAY = timedelta(hours=1)


class CheckoutExpiration(db.Model):
    """One row per abandoned Stripe Checkout Session.

    Idempotency anchor: ``session_id`` UNIQUE. Stripe never reissues an
    expired event for the same session, but webhook retries can deliver
    the same payload up to 3 days; the UNIQUE collapses duplicates to a
    single queue entry.
    """

    __tablename__ = "checkout_expirations"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ``cs_test_...`` / ``cs_live_...`` (Stripe ids cap < 100 chars; 255
    # mirrors processed_stripe_events.event_id for buffer parity).
    session_id = db.Column(
        db.String(255), unique=True, nullable=False, index=True,
    )

    # All timestamps are naive UTC — matches the project convention used
    # by Position.opened_at, ProcessedStripeEvent.processed_at, etc.
    expired_at = db.Column(db.DateTime, nullable=False)
    scheduled_send_at = db.Column(db.DateTime, nullable=False, index=True)

    # NULL = pending. Set after a provider call returned success.
    sent_at = db.Column(db.DateTime, nullable=True)

    # When the dispatcher gives up on a row permanently. Short enum-ish
    # strings (e.g. "feature_flag_off", "no_email", "already_subscribed",
    # "provider_failed"). NULL = no skip recorded.
    skipped_reason = db.Column(db.String(80), nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    # ─── Class helpers ────────────────────────────────────────────────

    @classmethod
    def enqueue(
        cls,
        *,
        user_id: int,
        session_id: str,
        expired_at: datetime,
    ) -> "CheckoutExpiration | None":
        """Insert a new pending row.

        Returns the row on success, ``None`` if a row with the same
        ``session_id`` already exists (idempotent re-enqueue from a
        webhook retry).

        Caller is responsible for the surrounding commit; this method
        only flushes through ``db.session.add``.

        ``expired_at`` may be a tz-aware or naive datetime — converted
        to naive UTC to match the storage convention.
        """
        if not session_id:
            return None

        # Normalize to naive UTC.
        if expired_at.tzinfo is not None:
            expired_at = expired_at.astimezone(timezone.utc).replace(tzinfo=None)

        existing = cls.query.filter_by(session_id=session_id).first()
        if existing is not None:
            return None  # idempotent — webhook retry

        row = cls(
            user_id=user_id,
            session_id=session_id,
            expired_at=expired_at,
            scheduled_send_at=expired_at + FOLLOWUP_DELAY,
        )
        db.session.add(row)
        try:
            db.session.flush()
        except IntegrityError:
            # Race: another concurrent webhook inserted between the
            # ``filter_by`` and the flush. Roll the failed insert back
            # so the surrounding session stays clean.
            db.session.rollback()
            return None
        return row

    @classmethod
    def pending_due(
        cls,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> Iterable["CheckoutExpiration"]:
        """Yield rows whose ``scheduled_send_at <= now`` AND ``sent_at IS
        NULL`` AND ``skipped_reason IS NULL``.

        Caller pattern: iterate, send, mutate. The ``limit`` is a soft
        cap so a backlog doesn't OOM the dispatcher — successive cron
        ticks drain remaining rows.

        Bug C#4 fix: ``.with_for_update(skip_locked=True)`` row-locks the
        returned rows for the fetching transaction and SKIPs rows already
        locked by a concurrent dispatcher tick, so two overlapping cron
        runs pick disjoint row sets and the same abandoned-checkout
        follow-up email can never be sent twice. ``with_for_update`` is a
        documented no-op on SQLite (single-threaded local/test path).
        """
        if now is None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
        elif now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)

        return (
            cls.query
            .filter(cls.scheduled_send_at <= now)
            .filter(cls.sent_at.is_(None))
            .filter(cls.skipped_reason.is_(None))
            .order_by(cls.scheduled_send_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
            .all()
        )

    # ─── Instance helpers ─────────────────────────────────────────────

    def mark_sent(self) -> None:
        """Stamp ``sent_at`` to now (UTC naive). Caller commits."""
        self.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def mark_skipped(self, reason: str) -> None:
        """Close the row permanently with a short ``reason``. Caller commits.

        Clamp to column width (80) to avoid surprise IntegrityError on a
        long provider error string.
        """
        self.skipped_reason = (reason or "skipped")[:80]


__all__ = ["CheckoutExpiration", "FOLLOWUP_DELAY"]
