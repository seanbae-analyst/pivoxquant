"""
models/companion_waitlist.py — Personal Journal Companion waitlist.

Collects sign-ups from the landing-page Companion teaser while the feature
is in Closed Beta (AGENT_ENABLED=False). Once legal counsel signs off, we
email this cohort first.

Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.exc import IntegrityError

from extensions import db


class CompanionWaitlist(db.Model):
    """A single expression of interest for Journal Companion access.

    Collected from:
      - landing teaser section (anonymous visitors allowed)
      - /companion page (authenticated users hitting the Closed-Beta gate)

    Privacy posture:
      - email stored hashed (sha256) by default unless user opts in for
        direct notification. Opt-in stores raw email in a separate column
        with explicit consent timestamp.
      - no other PII collected.
      - right-to-delete implemented via `purge_by_email_hash()`.
    """

    __tablename__ = "companion_waitlist"

    id = db.Column(db.Integer, primary_key=True)

    # SHA256(email) — always present. Used for dedup + right-to-delete.
    email_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Raw email only if the user explicitly opted in to direct notification.
    # NULL = hashed-only, will not be notified directly.
    email_plaintext = db.Column(db.String(255), nullable=True)
    email_consent_at = db.Column(db.DateTime, nullable=True)

    # Optional linkage to logged-in user (if signed up while authenticated).
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Source attribution for funnel analysis (not personally identifying).
    source = db.Column(db.String(40), default="landing-teaser")  # e.g. "landing-teaser", "companion-gate", "pricing-page"

    # Persona declared at signup (optional — helps beta invite prioritization).
    persona_interest = db.Column(db.String(20), nullable=True)  # one of VALID_PERSONAS or NULL

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Admin fields — set when we invite this row to the beta.
    invited_at = db.Column(db.DateTime, nullable=True)
    activated_at = db.Column(db.DateTime, nullable=True)

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def hash_email(email: str) -> str:
        """Stable case-insensitive sha256 of a normalized email."""
        normalized = email.strip().lower().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()

    @classmethod
    def enroll(
        cls,
        *,
        email: str,
        consent_direct_email: bool = False,
        user_id: Optional[int] = None,
        source: str = "landing-teaser",
        persona_interest: Optional[str] = None,
    ) -> Tuple["CompanionWaitlist", bool]:
        """Idempotent enrollment — returns ``(row, created)``.

        Return semantics:
          - ``(row, True)``  — a brand-new row was inserted for this email hash.
          - ``(row, False)`` — an existing row was found (or won the concurrent
            insert race) and updated with upgrade-only consent metadata.

        Race-condition handling (P0-2 / audit-code GAP-1):
        The obvious "query → if missing, insert" pattern is vulnerable when two
        concurrent requests submit the same email within the same transaction
        window. Both see ``row is None``, both attempt the INSERT, and the
        second hits the UNIQUE constraint on ``email_hash`` → SQLAlchemy raises
        ``IntegrityError`` → the caller's catch-all returns 500.

        The fix: after the pre-check misses, wrap the INSERT in a try/except so
        that a UNIQUE violation is treated as "someone else just enrolled us" —
        we roll back, re-fetch the winning row, and return it as (row, False)
        exactly as if our own pre-check had seen it. Any OTHER IntegrityError
        (a different column, a schema mismatch) is re-raised so the caller's
        observability path is not silently swallowed.

        Never-downgrade consent: when we find an existing row (whether from the
        pre-check or the race-recovery path), we only *upgrade* consent fields
        — raw email, consent timestamp, user_id linkage, persona attribution.
        First-touch source attribution is preserved.
        """
        h = cls.hash_email(email)
        now = datetime.now(timezone.utc)

        existing: Optional[CompanionWaitlist] = (
            cls.query.filter_by(email_hash=h).first()
        )
        if existing is not None:
            cls._apply_upgrades(
                existing,
                email=email,
                consent_direct_email=consent_direct_email,
                user_id=user_id,
                persona_interest=persona_interest,
                now=now,
            )
            db.session.commit()
            return existing, False

        # Pre-check miss — attempt insert. Another session may race us; we catch
        # the resulting UNIQUE violation and fall back to the upgrade path.
        row = cls(
            email_hash=h,
            email_plaintext=email.strip() if consent_direct_email else None,
            email_consent_at=now if consent_direct_email else None,
            user_id=user_id,
            source=source,
            persona_interest=persona_interest,
            created_at=now,
        )
        db.session.add(row)
        try:
            # flush() surfaces the IntegrityError *before* commit() — lets us
            # recover inside the same logical request without tainting a
            # user-triggered commit path higher up the stack.
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            # Race: a concurrent request inserted the same email_hash between
            # our pre-check and our flush. Re-fetch and treat as duplicate.
            winner = cls.query.filter_by(email_hash=h).first()
            if winner is None:
                # IntegrityError from something *other* than our UNIQUE key —
                # re-raise so the caller can observe the real failure.
                raise
            cls._apply_upgrades(
                winner,
                email=email,
                consent_direct_email=consent_direct_email,
                user_id=user_id,
                persona_interest=persona_interest,
                now=now,
            )
            db.session.commit()
            return winner, False

        db.session.commit()
        return row, True

    @classmethod
    def _apply_upgrades(
        cls,
        row: "CompanionWaitlist",
        *,
        email: str,
        consent_direct_email: bool,
        user_id: Optional[int],
        persona_interest: Optional[str],
        now: datetime,
    ) -> None:
        """Upgrade-only metadata merge for an existing waitlist row.

        Centralised so the pre-check path and the race-recovery path share the
        exact same semantics — no downgrade of consent, no overwrite of the
        first-touch source attribution, no clobber of an already-linked user.
        """
        if consent_direct_email and row.email_plaintext is None:
            row.email_plaintext = email.strip()
            row.email_consent_at = now
        if user_id and row.user_id is None:
            row.user_id = user_id
        if persona_interest and not row.persona_interest:
            row.persona_interest = persona_interest
        # ``source`` is kept as first-touch attribution — not upgraded.

    @classmethod
    def purge_by_email(cls, email: str) -> int:
        """Right-to-erasure. Returns rows deleted."""
        h = cls.hash_email(email)
        deleted = cls.query.filter_by(email_hash=h).delete(synchronize_session=False)
        db.session.commit()
        return deleted

    @classmethod
    def stats(cls) -> dict[str, int]:
        """Ops dashboard metrics."""
        return {
            "total": cls.query.count(),
            "consented": cls.query.filter(cls.email_plaintext.isnot(None)).count(),
            "invited": cls.query.filter(cls.invited_at.isnot(None)).count(),
            "activated": cls.query.filter(cls.activated_at.isnot(None)).count(),
        }
