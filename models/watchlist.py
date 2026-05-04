from datetime import datetime, timezone
from extensions import db


class Watchlist(db.Model):
    __tablename__ = "watchlist"
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    ticker   = db.Column(db.String(20), nullable=False)
    # Free-text user memo — "observations only", never a recommendation.
    note     = db.Column(db.String(500))
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    __table_args__ = (
        # Prevent duplicate watchlist entries for the same (user, ticker).
        # Enforced at the DB layer in migration 026.
        db.UniqueConstraint("user_id", "ticker",
                             name="uq_watchlist_user_ticker"),
    )
