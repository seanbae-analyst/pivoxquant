"""Morning Brief — daily personalized briefing persistence.

One row per (user_id, brief_date). Content is a JSON blob matching the
structure produced by services/morning_brief_service.py:

    {
        "market_summary":    {sp500, nasdaq, dow, kospi, vix, ...},
        "portfolio_changes": [{ticker, change_pct, direction}, ...],
        "events":            [{ticker, type, title, time}, ...],
        "insight":           "Short neutral Korean one-liner"
    }

No investment advice / no trade recommendations — see morning_brief_service
for the regex validator and Claude Haiku system prompt that enforce this.
"""
from datetime import datetime

from extensions import db


class MorningBrief(db.Model):
    __tablename__ = "morning_briefs"

    id         = db.Column(db.Integer,  primary_key=True)
    user_id    = db.Column(db.Integer,  db.ForeignKey("users.id"), nullable=False, index=True)
    brief_date = db.Column(db.Date,     nullable=False, index=True)
    content    = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "brief_date", name="uq_morning_brief_user_date"),
    )

    def __repr__(self) -> str:
        return f"<MorningBrief user={self.user_id} date={self.brief_date}>"
