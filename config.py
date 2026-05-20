"""Application configuration."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

_IS_PRODUCTION = os.environ.get("FLASK_ENV", "development").lower() == "production"

_db_url = os.environ.get("DATABASE_URL", "").strip()
if not _db_url:
    if _IS_PRODUCTION:
        # Fail-fast in production. Silently falling back to a local SQLite file
        # in production would mean each Railway container writes to its own
        # ephemeral disk → silent data loss.
        raise RuntimeError(
            "DATABASE_URL must be set in production. "
            "Configure it in Railway environment variables."
        )
    # Fallback to SQLite for local development
    _db_url = f"sqlite:///{os.path.join(BASE, 'pivoxquant.db')}"

# Heroku / Supabase sometimes use postgres:// which SQLAlchemy 2.x rejects
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

IS_POSTGRES = _db_url.startswith("postgresql")

# SECRET_KEY: MUST be set via env var in production.
# Without a fixed key, every gunicorn worker (and every restart) generates
# a different key, invalidating all existing session cookies → universal 401.
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    if _IS_PRODUCTION:
        # Fail-fast: refuse to boot the server with a random per-process
        # SECRET_KEY in production. With multiple gunicorn workers each
        # generating their own key, cookies signed by worker A would be
        # rejected by worker B → universal 401 on every restart/scale event.
        raise RuntimeError(
            "SECRET_KEY must be set in production. "
            "Configure it in Railway environment variables."
        )
    _secret = os.urandom(32).hex()


# ── Feature flags ─────────────────────────────────────────────────────────────
# ALPACA_ENABLED — kill switch for SYSTEM-WIDE Alpaca usage (server-owned keys).
#
# Default: "0" (disabled). 2026-04-27 (per CEO + legal):
# PivoxQuant operates on a BYO (Bring Your Own Key) Alpaca model. Each user
# connects THEIR OWN Alpaca paper account; we only forward read-only requests
# under the user's own Alpaca license. We DO NOT redistribute Alpaca market
# data — there is no commercial-data-license obligation on us.
#
# This server-side ALPACA_ENABLED flag therefore stays OFF in production.
# Per-user Alpaca runs through `services/broker/user_alpaca_service.py`
# (encrypted credentials, paper-only) and is independent of this flag.
#
# Autotrade reference removed 2026-04-27 alongside the autotrade feature
# (투자일임업 등록 회피).
#
# Consumed by:
#   - routes/broker_oauth.py  (/api/broker/alpaca/* endpoints → 503 when off)
#   - data_fetcher.py         (Alpaca disabled as US price source when off)
#   - realtime_service.py     (Alpaca disabled as realtime source when off)
#   - daytrade_service.py     (Alpaca disabled as US scanner when off)
#
# IMPORTANT: Flipping this to 1 re-enables the server-key path which would
# require us to hold an Alpaca commercial data license. Do NOT enable in
# production without legal sign-off.
ALPACA_ENABLED = os.environ.get("ALPACA_ENABLED", "0").strip() in ("1", "true", "True", "TRUE", "yes")


class Config:
    SECRET_KEY = _secret
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mirror the module-level flag onto the Flask config so request handlers
    # can read it via `current_app.config["ALPACA_ENABLED"]`.
    ALPACA_ENABLED = ALPACA_ENABLED

    # Connection pool settings (only effective for PostgreSQL; SQLite ignores them)
    if IS_POSTGRES:
        # 2026-05-20: Railway PG "too many clients already"로 모든 배포가 부팅
        # 실패(워커가 커넥션 못 얻음). 1-worker(gevent) + in-process 스케줄러(26잡)
        # 환경에서 풀을 대폭 축소해 footprint를 줄임 (구 15 → 5). 배포 시 old/new
        # 인스턴스 동시 실행 overlap에서도 PG max_connections 내에 들어오게 함.
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 3,
            "max_overflow": 2,
            "pool_timeout": 20,
            "pool_recycle": 300,       # 5분마다 recycle — 유휴 커넥션 빨리 반환
            "pool_pre_ping": True,     # verify connections before use
        }
