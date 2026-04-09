from datetime import datetime
from extensions import db


class Position(db.Model):
    __tablename__ = "positions"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker     = db.Column(db.String(20),  nullable=False)
    shares     = db.Column(db.Float,       nullable=False)
    avg_cost   = db.Column(db.Float,       nullable=False)
    buy_fx_rate = db.Column(db.Float,      default=0.0)
    added_at   = db.Column(db.DateTime,    default=datetime.utcnow)
