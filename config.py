"""Application configuration."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

_db_url = os.environ.get("DATABASE_URL", "").strip()
if not _db_url:
    # Fallback to SQLite for local development
    _db_url = f"sqlite:///{os.path.join(BASE, 'stockpilot.db')}"

# Heroku / Supabase sometimes use postgres:// which SQLAlchemy 2.x rejects
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

IS_POSTGRES = _db_url.startswith("postgresql")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
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
