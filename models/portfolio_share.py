import secrets
from datetime import datetime
from extensions import db


class PortfolioShare(db.Model):
    __tablename__ = "portfolio_shares"
    id         = db.Column(db.Integer,     primary_key=True)
    user_id    = db.Column(db.Integer,     db.ForeignKey("users.id"), nullable=False)
    token      = db.Column(db.String(64),  unique=True, nullable=False,
                           default=lambda: secrets.token_urlsafe(16))
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)
    expires_at = db.Column(db.DateTime,    nullable=False)
