"""AITwinWeeklyReport — Sunday rollup of (user vs twin) paper P&L.

Each row compares the user's REAL trade-history return with the
TWIN's PAPER return for the week ending ``week_ending``. UNIQUE
(user_id, week_ending) prevents the cron + manual triggers from
double-writing the same week.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db
from services.crypto_service import EncryptedText


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AITwinWeeklyReport(db.Model):
    __tablename__ = "ai_twin_weekly_reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_ending = db.Column(db.Date, nullable=False)
    user_return_pct = db.Column(db.Numeric(8, 4), nullable=True)
    twin_return_pct = db.Column(db.Numeric(8, 4), nullable=True)
    diff_pct = db.Column(db.Numeric(8, 4), nullable=True)
    user_trades_count = db.Column(db.Integer, nullable=True)
    twin_trades_count = db.Column(db.Integer, nullable=True)
    # Free-text weekly rationale summary → encrypted at rest (EncryptedText).
    rationale_summary = db.Column(EncryptedText, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now_naive)

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "week_ending",
            name="uq_ai_twin_weekly_reports_user_week",
        ),
        db.Index(
            "idx_twin_reports_user_week",
            "user_id", "week_ending",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": int(self.id),
            "user_id": int(self.user_id),
            "week_ending": self.week_ending.isoformat() if self.week_ending else None,
            "user_return_pct": (
                float(self.user_return_pct) if self.user_return_pct is not None else None
            ),
            "twin_return_pct": (
                float(self.twin_return_pct) if self.twin_return_pct is not None else None
            ),
            "diff_pct": float(self.diff_pct) if self.diff_pct is not None else None,
            "user_trades_count": (
                int(self.user_trades_count) if self.user_trades_count is not None else None
            ),
            "twin_trades_count": (
                int(self.twin_trades_count) if self.twin_trades_count is not None else None
            ),
            "rationale_summary": self.rationale_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
