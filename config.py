"""Application configuration."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

_db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE, 'stockpilot.db')}")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
