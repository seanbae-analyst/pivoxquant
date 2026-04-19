"""UserReferral — per-user referral code (1:1 with User).

Why a separate table?
---------------------
`models/user.py` is treated as immutable in the current codebase (see
CLAUDE.md "기존 백엔드 서비스 파일 수정 금지"), so we attach the referral
code via a side-table with a UNIQUE FK back to users.

The code itself is an 8-char URL-safe token (alphabet excludes confusing
characters like `0/O/1/l/I`). Collisions are retried with a bounded
loop — the keyspace is ~32^8 ≈ 10^12 so a handful of retries is enough
even at millions of users.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from extensions import db


# URL-safe alphabet, de-confused (no 0/O/1/I/l) — easier to read aloud
# and transcribe from a screenshot of a shared brag card.
_REFERRAL_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_REFERRAL_LEN = 8
_MAX_GENERATION_ATTEMPTS = 25


def generate_referral_code() -> str:
    """Return a random 8-char code from the de-confused alphabet.

    Uniqueness is enforced at the DB layer; callers should retry on
    IntegrityError (see `UserReferral.get_or_create`).
    """
    return "".join(secrets.choice(_REFERRAL_ALPHABET) for _ in range(_REFERRAL_LEN))


class UserReferral(db.Model):
    __tablename__ = "user_referrals"

    id            = db.Column(db.Integer,    primary_key=True)
    user_id       = db.Column(db.Integer,    db.ForeignKey("users.id"),
                              nullable=False, unique=True, index=True)
    referral_code = db.Column(db.String(16), nullable=False, unique=True, index=True)
    created_at    = db.Column(db.DateTime,   default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    invited_count = db.Column(db.Integer,    default=0, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "user_id":       self.user_id,
            "referral_code": self.referral_code,
            "created_at":    self.created_at.isoformat() + "Z"
                             if self.created_at else None,
            "invited_count": self.invited_count or 0,
        }

    @classmethod
    def get_or_create(cls, user_id: int) -> "UserReferral":
        """Return existing referral row for `user_id`, creating one if needed.

        Uses a small retry loop on the unique-code constraint so concurrent
        first-time access for two users cannot collide. Commits on creation.
        """
        existing = cls.query.filter_by(user_id=user_id).first()
        if existing:
            return existing

        last_exc: Exception | None = None
        for _ in range(_MAX_GENERATION_ATTEMPTS):
            code = generate_referral_code()
            row = cls(user_id=user_id, referral_code=code)
            db.session.add(row)
            try:
                db.session.commit()
                return row
            except Exception as exc:  # pragma: no cover — depends on DB driver
                db.session.rollback()
                last_exc = exc
                # retry with a new code — could be user_id race OR code race;
                # if it's the user_id race the next filter catches it cleanly.
                dup = cls.query.filter_by(user_id=user_id).first()
                if dup:
                    return dup
                continue
        raise RuntimeError(
            f"Failed to allocate unique referral code after "
            f"{_MAX_GENERATION_ATTEMPTS} attempts"
        ) from last_exc

    def __repr__(self) -> str:
        return (f"<UserReferral id={self.id} user={self.user_id} "
                f"code={self.referral_code!r}>")
