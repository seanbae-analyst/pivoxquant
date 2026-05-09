"""Broker connection model — stores OAuth tokens for Alpaca/KIS real account linking.

Week 1 (2026-04-18): Added AES-256-GCM encrypted columns for per-user KIS/Kiwoom
credentials. Existing `access_token` / `refresh_token` columns are retained for
backward compatibility with Alpaca and legacy code paths; new KIS flow writes
into the `encrypted_*` columns via `services.crypto_service`.
"""
from datetime import datetime, timezone
from extensions import db


class BrokerConnection(db.Model):
    __tablename__ = "broker_connections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    broker = db.Column(db.String(20), nullable=False)       # alpaca / kis / kiwoom
    access_token = db.Column(db.Text)                       # legacy (Alpaca)
    refresh_token = db.Column(db.Text)                      # legacy (Alpaca)
    account_id = db.Column(db.String(50))                   # legacy public account id
    is_paper = db.Column(db.Boolean, default=True)          # True=paper/mock, False=live
    is_active = db.Column(db.Boolean, default=True)
    last_synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # ── Week 1: Per-user KIS/Kiwoom encrypted credentials ────────────────
    # All values are AES-256-GCM base64 ciphertext (via services.crypto_service).
    encrypted_app_key = db.Column(db.Text, nullable=True)
    encrypted_app_secret = db.Column(db.Text, nullable=True)
    encrypted_account_no = db.Column(db.Text, nullable=True)
    account_prod = db.Column(db.String(4), nullable=True, default="01")
    encrypted_access_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    encryption_key_version = db.Column(db.SmallInteger, nullable=False, default=1)
    display_name = db.Column(db.String(100), nullable=True)
    last_sync_status = db.Column(db.String(20), nullable=True)   # ok/token_expired/rate_limited/broker_down/revoked
    last_sync_error = db.Column(db.Text, nullable=True)
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "broker": self.broker,
            "account_id": self.account_id,
            "is_paper": self.is_paper,
            "is_active": self.is_active,
            "display_name": self.display_name,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "last_sync_status": self.last_sync_status,
            "consecutive_failures": self.consecutive_failures or 0,
            "has_credentials": bool(self.encrypted_app_key and self.encrypted_app_secret),
        }

    __table_args__ = (
        # One row per (user, broker). Enforced at the DB layer in
        # migration 026.
        db.UniqueConstraint("user_id", "broker",
                             name="uq_broker_connections_user_broker"),
    )
