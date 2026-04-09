from datetime import datetime
from extensions import db


class Alert(db.Model):
    __tablename__ = "alerts"
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker         = db.Column(db.String(20))
    message        = db.Column(db.Text,    nullable=False)
    signal         = db.Column(db.String(10))
    score          = db.Column(db.Float,   default=0)
    rec_shares     = db.Column(db.Integer, default=0)
    rec_investment = db.Column(db.Float,   default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    is_read        = db.Column(db.Boolean,  default=False)
