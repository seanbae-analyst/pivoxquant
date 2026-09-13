"""Import Inbox — uploaded fills waiting for the user's own reason.

Design: docs/product/IMPORT_INBOX_DESIGN.md (2026-09-13).

Two tables:

``import_batches``
    One row per upload (CSV / XLSX / pasted notification text). Stores
    only counts, the consent timestamp and a broker guess — never the
    file or the full text (LOCAL_AGENT_LEGAL_RISK §5).

``pending_trades``
    One row per parsed fill. A row stays ``pending`` until the user
    attaches a thesis and approves it (→ ``trade_history`` / ``positions``
    via ``services.imports.ledger``), rejects it, or it was flagged
    ``duplicate`` at parse time. Nothing here touches the mirror until
    approval (design §원칙 2), and nothing here ever moves seed capital
    (§원칙 3).

Privacy
-------
``raw_snippet`` holds at most 300 characters of the source row/line with
account-number patterns masked (``services.imports.mask_sensitive``).
``approved_thesis`` is the user's own free text → encrypted at rest.

Schema is mirrored 1:1 in ``migrations/versions/051_import_inbox.py``
(``token_id``: ``052_import_tokens.py``).
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db
from services.crypto_service import EncryptedText


SOURCE_CSV = "csv"
SOURCE_SCREENSHOT_TEXT = "screenshot_text"
SOURCE_WEBHOOK = "webhook"
VALID_SOURCES = (SOURCE_CSV, SOURCE_SCREENSHOT_TEXT, SOURCE_WEBHOOK)

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_DUPLICATE = "duplicate"
VALID_STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_DUPLICATE)

RAW_SNIPPET_MAX = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


class ImportBatch(db.Model):
    __tablename__ = "import_batches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = db.Column(db.String(20), nullable=False)  # csv | screenshot_text | webhook
    # Phase 2 — set when the batch arrived through the PAT webhook
    # (models/import_token.py). NULL for session uploads.
    token_id = db.Column(
        db.Integer,
        db.ForeignKey("import_tokens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    broker_guess = db.Column(db.String(40), nullable=False, default="unknown")
    filename = db.Column(db.String(255), nullable=True)
    row_count = db.Column(db.Integer, nullable=False, default=0)
    parsed_count = db.Column(db.Integer, nullable=False, default=0)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    unresolved_count = db.Column(db.Integer, nullable=False, default=0)
    consent_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "token_id": self.token_id,
            "broker_guess": self.broker_guess,
            "filename": self.filename,
            "row_count": self.row_count,
            "parsed_count": self.parsed_count,
            "duplicate_count": self.duplicate_count,
            "unresolved_count": self.unresolved_count,
            "consent_at": _iso(self.consent_at),
            "created_at": _iso(self.created_at),
        }


class PendingTrade(db.Model):
    __tablename__ = "pending_trades"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker = db.Column(db.String(20), nullable=True)          # canonical (.KS/.KQ/US)
    name = db.Column(db.String(100), nullable=False, default="")
    action = db.Column(db.String(4), nullable=False)          # BUY | SELL (data field)
    shares = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), nullable=False, default="KRW")
    traded_at = db.Column(db.DateTime, nullable=False)
    confidence = db.Column(db.Float, nullable=False, default=1.0)
    status = db.Column(db.String(12), nullable=False, default=STATUS_PENDING, index=True)
    dedupe_key = db.Column(db.String(64), nullable=False, index=True)
    needs_ticker = db.Column(db.Boolean, nullable=False, default=False)
    raw_snippet = db.Column(db.String(RAW_SNIPPET_MAX), nullable=True)
    pre_trade_reflection_id = db.Column(
        db.Integer,
        db.ForeignKey("pre_trade_reflections.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_thesis = db.Column(EncryptedText, nullable=True)
    approved_trade_id = db.Column(db.Integer, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict:
        """PendingTradeDTO (design §API)."""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "ticker": self.ticker,
            "name": self.name,
            "action": self.action,
            "shares": self.shares,
            "price": self.price,
            "currency": self.currency,
            "traded_at": _iso(self.traded_at),
            "confidence": self.confidence,
            "status": self.status,
            "needs_ticker": bool(self.needs_ticker),
            "pre_trade_reflection_id": self.pre_trade_reflection_id,
            "raw_snippet": self.raw_snippet,
            "approved_trade_id": self.approved_trade_id,
            "approved_at": _iso(self.approved_at),
        }
