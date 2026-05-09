"""
models/processed_stripe_event.py — Stripe webhook idempotency tracking.

Stripe retries failed webhooks for up to 3 days (exponential backoff).
Without an idempotency record, the same event can be processed twice:
  - checkout.session.completed → user.subscription_tier set twice (idempotent
    but emits duplicate logger.info, double-charges metrics dashboards)
  - customer.subscription.updated → tier downgrade then immediate re-upgrade
    if events arrive out of order
  - invoice.paid → duplicate revenue logger entries

This table records every processed Stripe event by `event["id"]`. The webhook
handler short-circuits with ACK 200 + `{"deduped": true}` if it has already
processed the event. Records are pruned by a separate maintenance job (90-day
TTL is plenty — Stripe retries cap at 3 days).

Stripe contract reference: https://docs.stripe.com/webhooks#handle-duplicate-events

Why a dedicated table (vs reusing CompanionWaitlist's UNIQUE-key pattern)
------------------------------------------------------------------------
The waitlist row carries business meaning that we want to upgrade on a race;
Stripe events are inert audit records — once we've seen the event id, we never
update the row, only short-circuit. A simple dedicated table keeps the schema
intent obvious to ops: anything in this table = "Stripe already paid us".
"""

from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


# Status enum — kept as String to avoid an Alembic ENUM migration on Postgres.
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
VALID_STATUSES = {STATUS_SUCCESS, STATUS_ERROR}


class ProcessedStripeEvent(db.Model):
    """Idempotency record for a single Stripe webhook delivery.

    The unique key is `event_id` — Stripe guarantees a stable id per event
    across delivery retries, so a UNIQUE constraint there is the canonical
    dedupe boundary. We never look up by row id; the PK is convenience only.
    """

    __tablename__ = "processed_stripe_events"

    id = db.Column(db.Integer, primary_key=True)

    # Stripe event id (e.g. "evt_1AbcXyZ..."). Capped at 255 to align with
    # Stripe's published id length plus generous buffer for any future schema
    # changes. Indexed UNIQUE so the dedupe lookup is O(log n).
    event_id = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # Stripe event type (e.g. "checkout.session.completed"). Stored for ops
    # filtering / dashboards — the handler dispatches on the live `event["type"]`,
    # not this column.
    event_type = db.Column(db.String(80), nullable=False)

    # When we finished processing (or hit the catch-all). Used for retention.
    processed_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # success / error. "error" rows are still recorded so we don't infinitely
    # reprocess a poison event — Stripe will stop retrying after 3 days
    # regardless, but recording the error gives ops a single place to look.
    status = db.Column(db.String(16), nullable=False, default=STATUS_SUCCESS)

    # Optional: short error fingerprint for ops triage. No raw exception
    # body — that lives in the Sentry / Railway log stream. 200-char clamp
    # mirrors the SEC-F traceback gate convention.
    error_message = db.Column(db.String(200), nullable=True)

    @classmethod
    def already_processed(cls, event_id: str) -> bool:
        """Return True if this event_id has already been recorded.

        Caller pattern: check before dispatch, short-circuit with ACK 200
        if True. The race window between this check and the INSERT is
        closed by the UNIQUE constraint — the second insert hits
        IntegrityError and the caller treats it as deduped.
        """
        if not event_id:
            return False
        return db.session.query(
            cls.query.filter_by(event_id=event_id).exists()
        ).scalar()

    @classmethod
    def record(
        cls,
        *,
        event_id: str,
        event_type: str,
        status: str = STATUS_SUCCESS,
        error_message: str | None = None,
    ) -> "ProcessedStripeEvent":
        """Create + flush a record. Caller must commit the surrounding tx.

        Status validation is defensive — Stripe sends thousands of event
        types, but our `status` column is a closed enum.
        """
        if status not in VALID_STATUSES:
            status = STATUS_ERROR
        # Clamp error message to column width to avoid surprise IntegrityError.
        clamped_error = (error_message or "")[:200] or None
        row = cls(
            event_id=event_id,
            event_type=event_type[:80] if event_type else "unknown",
            status=status,
            error_message=clamped_error,
        )
        db.session.add(row)
        return row
