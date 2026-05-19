"""AuthEvent — OAuth lifecycle event log (Wave I C-1).

One row per OAuth start / success / fail. Used by
``scripts/nightly/oauth_failure_check.py`` to detect users stuck in
repeat-fail loops (same email, ≥3 failures in the last hour) so we
can alert ops AND email the user before they give up.

Schema source-of-truth: ``migrations/versions/040_auth_events.py``.
Constants below mirror the CHECK constraint so calling code can
import them as enums instead of stringly-typed literals.

PIPA classification
-------------------
``email`` is PIPA-personal-data. On user hard-delete the row is NOT
deleted — instead the ``email`` column is overwritten with a salted
SHA256 hash so aggregate audit (per-provider fail rate, hourly
volume) survives without identifying the principal. See
``scripts/nightly/pipa_purge.py:_anonymize_auth_events``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


# Mirrors CHECK constraint in migration 040.
EVENT_TYPE_START = "start"
EVENT_TYPE_SUCCESS = "success"
EVENT_TYPE_FAIL = "fail"
VALID_EVENT_TYPES = (EVENT_TYPE_START, EVENT_TYPE_SUCCESS, EVENT_TYPE_FAIL)

PROVIDER_GOOGLE = "google"
PROVIDER_KAKAO = "kakao"
VALID_PROVIDERS = (PROVIDER_GOOGLE, PROVIDER_KAKAO)


class AuthEvent(db.Model):
    __tablename__ = "auth_events"

    id = db.Column(db.Integer, primary_key=True)
    # ``email`` is store-key. Deliberately NOT FK'd to ``users.id`` —
    # an OAuth fail can fire BEFORE the user row exists, and the row
    # may also outlive the user (we anonymize, not delete, on purge).
    email = db.Column(db.String(255), nullable=False, index=True)
    provider = db.Column(db.String(16), nullable=False)
    event_type = db.Column(db.String(16), nullable=False)
    fail_reason = db.Column(db.String(64), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    __table_args__ = (
        db.CheckConstraint(
            "event_type IN ('start', 'success', 'fail')",
            name="ck_auth_events_event_type",
        ),
        db.CheckConstraint(
            "provider IN ('google', 'kakao')",
            name="ck_auth_events_provider",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "provider": self.provider,
            "event_type": self.event_type,
            "fail_reason": self.fail_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
