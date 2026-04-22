from datetime import datetime, timezone
from extensions import db


class Watchlist(db.Model):
    __tablename__ = "watchlist"
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker   = db.Column(db.String(20), nullable=False)
    # Free-text user memo — "observations only", never a recommendation.
    note     = db.Column(db.String(500))
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
