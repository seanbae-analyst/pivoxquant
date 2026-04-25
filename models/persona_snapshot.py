"""PersonaSnapshot — frozen point-in-time persona classification per user.

Powers Feature 3 (history persistence) and Feature 4 (Evolution Timeline).
See :mod:`services.profile.persona_history` for the read/write surface.

Privacy posture
---------------
Every row belongs to exactly one user (``user_id`` FK ``ON DELETE
CASCADE``). The historical series is purely the **user's own**
behavioural snapshot — never aggregated across users (that's
:class:`PersonaGroupStats`).

UNIQUE ``(user_id, computed_at)`` prevents accidental double-writes
when the weekly cron coalesces with a manual trigger that fires in the
same second.

Schema parity
-------------
Schema is mirrored 1:1 with ``migrations/versions/016_persona_snapshots.py``.
JSON-shaped columns are stored as TEXT so SQLite + Postgres stay portable;
the helper accessors below decode them lazily.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from extensions import db


# Same 8-persona taxonomy used everywhere else in the profile layer. Re-
# imported here as a tuple constant to avoid a service-layer cycle on
# model load (``models`` is imported by ``services.profile`` itself).
VALID_SNAPSHOT_PERSONAS = (
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
)


class PersonaSnapshot(db.Model):
    __tablename__ = "persona_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # UTC, naive — matches the rest of the codebase.
    computed_at = db.Column(db.DateTime, nullable=False)
    persona = db.Column(db.String(20), nullable=False)
    confidence = db.Column(db.Integer, nullable=False)
    # JSON blobs as TEXT — see module docstring.
    features = db.Column(db.Text, nullable=False)
    present_mask = db.Column(db.Text, nullable=False)
    ranking = db.Column(db.Text, nullable=False)
    breakdown = db.Column(db.Text, nullable=True)
    declared_persona = db.Column(db.String(20), nullable=True)
    trade_count = db.Column(db.Integer, nullable=False, default=0,
                            server_default="0")
    window_days = db.Column(db.Integer, nullable=False, default=90,
                            server_default="90")
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_persona_snapshots_confidence_range",
        ),
        db.UniqueConstraint(
            "user_id", "computed_at",
            name="uq_persona_snapshots_user_time",
        ),
        db.Index(
            "idx_persona_snapshots_user_time",
            "user_id", "computed_at",
        ),
    )

    # ── JSON helpers ─────────────────────────────────────────────────

    @staticmethod
    def _decode(blob: str | None, fallback):
        if not blob:
            return fallback
        try:
            return json.loads(blob)
        except (json.JSONDecodeError, TypeError):
            return fallback

    def features_dict(self) -> dict:
        val = self._decode(self.features, {})
        return val if isinstance(val, dict) else {}

    def present_mask_dict(self) -> dict:
        val = self._decode(self.present_mask, {})
        return val if isinstance(val, dict) else {}

    def ranking_list(self) -> list:
        val = self._decode(self.ranking, [])
        return val if isinstance(val, list) else []

    def breakdown_list(self) -> list:
        val = self._decode(self.breakdown, [])
        return val if isinstance(val, list) else []

    def to_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id is not None else None,
            "user_id": int(self.user_id),
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
            "persona": self.persona,
            "confidence": int(self.confidence or 0),
            "features": self.features_dict(),
            "present_mask": self.present_mask_dict(),
            "ranking": self.ranking_list(),
            "breakdown": self.breakdown_list(),
            "declared_persona": self.declared_persona,
            "trade_count": int(self.trade_count or 0),
            "window_days": int(self.window_days or 90),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
