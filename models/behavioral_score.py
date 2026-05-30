# DEPRECATED 2026-05-30: AI 점수화 폐기(DECISIONS). 크론·API 비활성. 물리 컬럼
# drop 은 prod self-heal 함정 때문에 careful 마이그레이션으로 후속. 거울/export/
# persona benchmark 호환 위해 모델 보존.
"""BehavioralScore — weekly observational behaviour score per user.

Powers Feature 7 (Weekly Behavioural Score). Written by
``services.behavior.scorer.compute_weekly_score`` (Sunday 22:00 KST cron,
or on-demand admin trigger).

Privacy / legal
---------------
- One row per ``(user_id, week_ending)`` — UNIQUE.
- Sub-scores are framed observationally; the ``notes`` text is filtered
  through ``services.legal.forbidden_terms`` before persistence.
- ``persona_avg`` references the public, anonymised PersonaGroupStats
  aggregates which already enforce ``MIN_GROUP_SIZE = 20``.
- Schema is mirrored 1:1 with ``migrations/versions/018_behavioral_scores.py``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from extensions import db


# Sub-score names — kept here as a tuple constant so the service +
# tests share the source of truth without a circular import.
SUB_SCORE_KEYS = (
    "holding_discipline",
    "loss_cut",
    "position_sizing",
    "fomo_resistance",
    "reflection_rate",
)


class BehavioralScore(db.Model):
    __tablename__ = "behavioral_scores"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_ending = db.Column(db.Date, nullable=False)
    overall_score = db.Column(db.Numeric(5, 2), nullable=False)
    # JSON blobs as TEXT — see module docstring.
    sub_scores = db.Column(db.Text, nullable=False)
    persona_avg = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    trade_count = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "week_ending",
            name="uq_behavioral_scores_user_week",
        ),
        db.Index(
            "idx_behavioral_scores_user_week",
            "user_id", "week_ending",
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

    def sub_scores_dict(self) -> dict:
        v = self._decode(self.sub_scores, {})
        return v if isinstance(v, dict) else {}

    def persona_avg_dict(self) -> dict | None:
        if not self.persona_avg:
            return None
        v = self._decode(self.persona_avg, None)
        return v if isinstance(v, dict) else None

    def to_dict(self) -> dict:
        def _f(v):
            if v is None:
                return None
            if isinstance(v, Decimal):
                return float(v)
            return v

        return {
            "id": int(self.id) if self.id is not None else None,
            "week_ending": self.week_ending.isoformat() if self.week_ending else None,
            "overall_score": _f(self.overall_score),
            "sub_scores": self.sub_scores_dict(),
            "persona_avg": self.persona_avg_dict(),
            "notes": self.notes,
            "trade_count": int(self.trade_count or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
