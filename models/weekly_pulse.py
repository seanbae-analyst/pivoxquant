"""WeeklyPulse — user mood/confidence self-reports for Layer 2 CFO dashboard.

Part of Living CFO Layer 2 (see reports/product/PERSONA_SPEC_2026-04-23.md
and frontend/src/lib/cfo/hooks.ts ``PulseResponse``).

One row per submission. The cadence (weekly/biweekly/monthly) is stored
on each row so the user can change it without a separate settings
migration; the read path uses the most recent row's cadence for
``next_due_at`` calculation.

Fields map 1:1 to the ``PulseEntry`` frontend type:
    mood / confidence  — 1..5 Likert integers
    worry              — short free-text (max 500)
    topics             — JSON array of tag strings
    learn              — short free-text (max 500)
"""
import json
from datetime import datetime, timezone

from extensions import db


VALID_CADENCES = ("weekly", "biweekly", "monthly")


class WeeklyPulse(db.Model):
    __tablename__ = "weekly_pulse"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mood = db.Column(db.Integer, nullable=False)          # 1..5
    confidence = db.Column(db.Integer, nullable=False)    # 1..5
    worry = db.Column(db.String(500), default="")
    # Stored as JSON text for portability (SQLite + Postgres).
    topics = db.Column(db.Text, default="[]")
    learn = db.Column(db.String(500), default="")
    cadence = db.Column(db.String(16), default="weekly", nullable=False)
    submitted_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
    )

    def topics_list(self) -> list:
        """Safely decode the topics JSON column."""
        try:
            val = json.loads(self.topics or "[]")
            if isinstance(val, list):
                # Coerce every item to str and drop non-strings/empty.
                return [str(x) for x in val if x is not None and str(x).strip()]
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self) -> dict:
        return {
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "mood": int(self.mood or 0),
            "confidence": int(self.confidence or 0),
            "worry": self.worry or "",
            "topics": self.topics_list(),
            "learn": self.learn or "",
        }
