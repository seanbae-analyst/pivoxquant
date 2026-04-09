"""Broker connection model — stores OAuth tokens for Alpaca/KIS real account linking."""
from datetime import datetime
from extensions import db


class BrokerConnection(db.Model):
    __tablename__ = "broker_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    broker = db.Column(db.String(20), nullable=False)       # alpaca / kis
    access_token = db.Column(db.Text)                       # encrypted in production
    refresh_token = db.Column(db.Text)                      # encrypted in production
    account_id = db.Column(db.String(50))
    is_paper = db.Column(db.Boolean, default=True)          # True=paper, False=live
    is_active = db.Column(db.Boolean, default=True)
    last_synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "broker": self.broker,
            "account_id": self.account_id,
            "is_paper": self.is_paper,
            "is_active": self.is_active,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
        }
