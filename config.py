"""Application configuration."""
import os
import logging
import warnings

BASE = os.path.dirname(os.path.abspath(__file__))

_db_url = os.environ.get("DATABASE_URL", "").strip()
if not _db_url:
    # Fallback to SQLite for local development
    _db_url = f"sqlite:///{os.path.join(BASE, 'stockpilot.db')}"

# Heroku / Supabase sometimes use postgres:// which SQLAlchemy 2.x rejects
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

IS_POSTGRES = _db_url.startswith("postgresql")

_IS_PRODUCTION = os.environ.get("FLASK_ENV", "development").lower() == "production"

# SECRET_KEY: MUST be set via env var in production.
# Without a fixed key, every gunicorn worker (and every restart) generates
# a different key, invalidating all existing session cookies → universal 401.
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    if _IS_PRODUCTION:
        warnings.warn(
            "CRITICAL: SECRET_KEY not set in production. "
            "All sessions will be lost on every restart. "
            "Set SECRET_KEY in Railway environment variables.",
            stacklevel=2,
        )
        logging.getLogger(__name__).critical(
            "SECRET_KEY not set — sessions will not persist across workers/restarts"
        )
    _secret = os.urandom(32).hex()


class Config:
    SECRET_KEY = _secret
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection pool settings (only effective for PostgreSQL; SQLite ignores them)
    if IS_POSTGRES:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 1800,      # recycle connections every 30 min
            "pool_pre_ping": True,     # verify connections before use
        }
