"""Import Inbox Phase 2 — personal access tokens for the import webhook.

Design: docs/product/IMPORT_INBOX_DESIGN.md §Phase 2 v3-A (2026-09-13).

One row per token the user issued from /settings. The raw token
(``"pvx_" + secrets.token_urlsafe(24)``) is shown exactly once, in the
issuance response; the database keeps only ``token_hash = sha256(raw)``
plus a 12-character ``prefix`` for display. A token is looked up by hash
and is usable while ``revoked_at`` is NULL.

``consent_at`` is the upload consent the user gave when issuing the token;
every batch the webhook creates with this token inherits it.

Schema is mirrored 1:1 in ``migrations/versions/052_import_tokens.py``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db

TOKEN_PREFIX = "pvx_"
TOKEN_PREFIX_DISPLAY_LEN = 12
TOKEN_NAME_MAX = 60
ACTIVE_TOKEN_LIMIT = 5
TOKEN_DAILY_BATCH_LIMIT = 200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


class ImportToken(db.Model):
    __tablename__ = "import_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(TOKEN_NAME_MAX), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    prefix = db.Column(db.String(16), nullable=False)
    consent_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def to_dict(self, batches_today: int = 0) -> dict:
        """Listing DTO — never includes the raw token or its hash."""
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "created_at": _iso(self.created_at),
            "last_used_at": _iso(self.last_used_at),
            "revoked_at": _iso(self.revoked_at),
            "batches_today": int(batches_today or 0),
        }


__all__ = [
    "ImportToken",
    "TOKEN_PREFIX",
    "TOKEN_PREFIX_DISPLAY_LEN",
    "TOKEN_NAME_MAX",
    "ACTIVE_TOKEN_LIMIT",
    "TOKEN_DAILY_BATCH_LIMIT",
]
