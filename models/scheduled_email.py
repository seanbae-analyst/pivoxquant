"""
models/scheduled_email.py — D+0/D+3/D+7 onboarding email queue.

Wave G S5. A small queue table the onboarding sequence writes into at
signup time and the email scheduler dispatcher drains every 15 minutes.

See ``migrations/versions/038_scheduled_emails.py`` for the schema
rationale + idempotency model. This module owns:

* ``ScheduledEmail`` ORM rows.
* ``enqueue(user_id, email_type, ...)`` — idempotent insert keyed on
  ``"u{user_id}:{email_type}"``. Returns the row on first call,
  ``None`` on subsequent calls (already queued / already sent).
* ``pending_due(now=...)`` — dispatcher iterator. Same shape as
  ``CheckoutExpiration.pending_due``.
* ``mark_sent`` / ``mark_skipped`` — instance helpers, caller commits.

Email types
-----------
Three slugs are valid (mirrored in
``services.email.onboarding_sequence.SEQUENCE``):

* ``"welcome"`` — TRANSACTIONAL, scheduled at signup (``now``).
* ``"d3_guide"`` — INFORMATION, scheduled at signup (``now + 3 days``).
* ``"d7_pro_nudge"`` — INFORMATION, scheduled at signup (``now + 7 days``).

The enum is enforced at the *services* layer (the sequence definition)
rather than in the schema, so adding a D+14 / D+30 step in a follow-up
wave is a one-line config change in
``services.email.onboarding_sequence.SEQUENCE`` — no migration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.exc import IntegrityError

from extensions import db


def _idempotency_key(user_id: int, email_type: str) -> str:
    """Stable composite key — guarantees one row per (user, email_type)."""
    return f"u{int(user_id)}:{email_type}"


class ScheduledEmail(db.Model):
    """One row per (user, email_type) onboarding queue entry."""

    __tablename__ = "scheduled_emails"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Slug like "welcome", "d3_guide", "d7_pro_nudge". 40 char ceiling
    # leaves room for future ``"d30_..."`` types without a migration.
    email_type = db.Column(db.String(40), nullable=False)

    # "transactional" | "information" — matches EmailCategory.value.
    email_category = db.Column(db.String(20), nullable=False)

    # UTC naive — project convention (Position.opened_at,
    # ProcessedStripeEvent.processed_at, CheckoutExpiration.expired_at).
    scheduled_send_at = db.Column(db.DateTime, nullable=False, index=True)

    # NULL = pending. Set after a provider returned True.
    sent_at = db.Column(db.DateTime, nullable=True)

    # Short reason string for rows the dispatcher chose not to send. See
    # the dispatcher for the closed set of values.
    skipped_reason = db.Column(db.String(80), nullable=True)

    # UNIQUE — the row's only contract with the outside world. Format
    # ``"u{user_id}:{email_type}"``. Survives webhook retries, cron
    # overlap, manual re-enqueue attempts.
    idempotency_key = db.Column(
        db.String(120), unique=True, nullable=False,
    )

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
        email_type: str,
        email_category: str,
        scheduled_send_at: datetime,
    ) -> "ScheduledEmail | None":
        """Insert a new pending row. Idempotent on (user_id, email_type).

        Caller commits. Returns the row on first call, ``None`` if a row
        already exists for the same idempotency_key (caller should
        treat ``None`` as "already queued / already sent — nothing to do").

        ``scheduled_send_at`` may be tz-aware or naive — coerced to naive
        UTC to match the storage convention.
        """
        if not email_type:
            return None
        if scheduled_send_at.tzinfo is not None:
            scheduled_send_at = (
                scheduled_send_at.astimezone(timezone.utc).replace(tzinfo=None)
            )

        key = _idempotency_key(user_id, email_type)
        existing = cls.query.filter_by(idempotency_key=key).first()
        if existing is not None:
            return None

        row = cls(
            user_id=user_id,
            email_type=email_type,
            email_category=email_category,
            scheduled_send_at=scheduled_send_at,
            idempotency_key=key,
        )
        db.session.add(row)
        try:
            db.session.flush()
        except IntegrityError:
            # Concurrent enqueue won the race. Roll the failed insert
            # back so the surrounding session stays clean and return
            # ``None`` — caller treats this as idempotent.
            db.session.rollback()
            return None
        return row

    @classmethod
    def pending_due(
        cls,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> Iterable["ScheduledEmail"]:
        """Yield rows whose ``scheduled_send_at <= now`` AND ``sent_at IS
        NULL`` AND ``skipped_reason IS NULL``. Oldest-first.
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
            .all()
        )

    # ─── Instance helpers ─────────────────────────────────────────────

    def mark_sent(self) -> None:
        """Stamp ``sent_at`` to now (UTC naive). Caller commits."""
        self.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def mark_skipped(self, reason: str) -> None:
        """Close the row permanently with a short reason. Caller commits.

        Clamp to 80 char column width to avoid IntegrityError on a long
        provider exception string.
        """
        self.skipped_reason = (reason or "skipped")[:80]


__all__ = ["ScheduledEmail"]
