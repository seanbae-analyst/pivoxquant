from datetime import datetime, timezone
from extensions import db


class TradeHistory(db.Model):
    __tablename__ = "trade_history"
    id              = db.Column(db.Integer,  primary_key=True)
    user_id         = db.Column(db.Integer,  db.ForeignKey("users.id", ondelete="CASCADE"),
                                  nullable=False, index=True)
    ticker          = db.Column(db.String(20))
    name            = db.Column(db.String(100), default="")
    action          = db.Column(db.String(10))   # BUY | SELL
    shares          = db.Column(db.Float)
    price_per_share = db.Column(db.Float)
    total_value     = db.Column(db.Float)
    pnl             = db.Column(db.Float, default=0.0)
    pnl_pct         = db.Column(db.Float, default=0.0)
    currency        = db.Column(db.String(5), default="USD")
    traded_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
