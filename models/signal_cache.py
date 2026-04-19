from datetime import datetime, timedelta
from extensions import db


class SignalCache(db.Model):
    __tablename__ = "signal_cache"
    ticker     = db.Column(db.String(20), primary_key=True)
    data_json  = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    TTL_SECONDS = 60

    def is_stale(self) -> bool:
        """Return True if the cached record is older than TTL_SECONDS."""
        if self.updated_at is None:
            return True
        return datetime.utcnow() - self.updated_at > timedelta(seconds=self.TTL_SECONDS)
