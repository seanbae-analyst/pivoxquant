"""Inquiry — customer support ticket (고객문의센터).

One row per support request. Created two ways:

1. **User-initiated** via ``POST /api/support/inquiries`` (the contact
   form) — category/subject/body supplied by the user.
2. **Chatbot auto-escalation** via ``POST /api/support/chat`` — when the
   support chatbot cannot answer (or surfaces anything that needs a human:
   refunds, account deletion, billing errors), it files an Inquiry with
   ``category="other"`` so a human follows up.

Compliance note
---------------
The chatbot path NEVER stores or relays investment advice. Investment
questions are short-circuited before any model call (see
``services/support/chatbot.py``), so an Inquiry body only ever contains
support-domain text or a flagged-for-human message.

``email_snapshot`` captures the user's email at creation time so an
operator can reply even if the account is later soft-deleted (PIPA 30-day
grace) — the FK is ``ondelete CASCADE`` so a *hard* delete still removes
the row, but the snapshot survives the soft-delete window.

Idempotency / lifecycle
------------------------
status transitions: ``open`` → ``answered`` (operator replied) → ``closed``
(optional terminal). ``answered_at`` is stamped when the operator replies.
"""
from datetime import datetime, timezone

from extensions import db


VALID_STATUSES = ("open", "answered", "closed")
VALID_CATEGORIES = ("billing", "account", "technical", "other")


def _utcnow_naive() -> datetime:
    # Mirrors models/user.py created_at convention (tz-naive UTC).
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Inquiry(db.Model):
    __tablename__ = "inquiries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = db.Column(db.String(32), nullable=False, default="other")
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    admin_reply = db.Column(db.Text, nullable=True)
    # Email at creation time so an operator can reply post soft-delete.
    email_snapshot = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=_utcnow_naive,
        nullable=False,
    )
    answered_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self, detail: bool = False) -> dict:
        out = {
            "id": self.id,
            "category": self.category,
            "subject": self.subject,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
            "has_reply": bool(self.admin_reply),
        }
        if detail:
            out["body"] = self.body
            out["admin_reply"] = self.admin_reply
        return out
