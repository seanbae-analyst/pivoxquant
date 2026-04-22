from datetime import datetime, timedelta, timezone
from extensions import db


class SignalCache(db.Model):
    __tablename__ = "signal_cache"
    ticker     = db.Column(db.String(20), primary_key=True)
    data_json  = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Legacy fallback TTL — retained for code paths that still read this
    # constant directly. Runtime ``is_stale()`` prefers the market-aware
    # helper in ``services.cache_ttl`` so intraday reads refresh at 30s
    # and off-hours reads relax to 120s.
    TTL_SECONDS = 60

    def is_stale(self) -> bool:
        """Return True if the cached record is older than the active TTL.

        Uses ``services.cache_ttl.signal_ttl()`` when importable so the
        window contracts (30s) while any market is tradable and relaxes
        (120s) off-hours. Falls back to ``TTL_SECONDS`` (60s) on import
        failure so scheduler / worker processes that bypass the services
        tree still behave sensibly.
        """
        if self.updated_at is None:
            return True
        try:
            from services.cache_ttl import signal_ttl
            ttl = signal_ttl()
        except Exception:
            ttl = self.TTL_SECONDS
        return datetime.now(timezone.utc).replace(tzinfo=None) - self.updated_at > timedelta(seconds=ttl)
