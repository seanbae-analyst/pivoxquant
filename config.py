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
# Shared truthy-env vocabulary so every boolean flag parses identically.
_TRUTHY_ENV = ("1", "true", "True", "TRUE", "yes")

# ALPACA_ENABLED — kill switch for the Alpaca market-data FALLBACK adapter
# (server-owned keys). The user-facing Alpaca broker integration (connect/sync
# UI, per-user credentials, /api/broker/alpaca/* routes) was fully removed on
# 2026-05-27 — it had been kill-switched and unused, and listing an unused
# broker in the Terms/Privacy created a 표시광고법 §3 mismatch risk.
#
# What remains gated by this flag is purely an internal US-price FALLBACK in the
# data pipeline (services/data/alpaca_market_adapter.py). Default "0" (disabled)
# in production → US prices come from FMP exclusively. There is no user surface.
#
# Consumed by:
#   - services/data/alpaca_market_adapter.py  (client short-circuits to None)
#   - services/data/fetcher.py                (US price fallback gated off)
#   - services/data/realtime.py               (realtime fallback gated off)
#   - services/trading/daytrade.py            (US scanner fallback gated off)
#   - services/artifacts/data_source_resolver.py (provenance claim gated off)
#
# IMPORTANT: Flipping this to 1 re-enables the server-key fallback which would
# require holding an Alpaca commercial data license. Do NOT enable in
# production without legal sign-off.
ALPACA_ENABLED = os.environ.get("ALPACA_ENABLED", "0").strip() in _TRUTHY_ENV

# MARKET_DATA_DISPLAY_ENABLED — kill switch for every route that DISPLAYS a
# vendor market quote (or a number derived from one) to an end user.
#
# Default "0" (disabled). An UNSET env var means OFF, and render.yaml
# deliberately does NOT set it: "off" must be the production default, so a
# fresh deploy can never accidentally start redistributing vendor prices.
#
# 켜는 조건 (the ONLY condition): an executed **FMP Data Display Agreement**.
#   - FMP ToS §2.2.2 forbids displaying their data to end users without that
#     agreement — a free closed beta is NOT exempt.
#   - FMP ToS §2.2 additionally requires prior written approval for derived
#     works, which is why anything COMPUTED from a quote (market value, NAV,
#     day P&L, unrealized P&L, equity curve, benchmark overlay, 52-week
#     high/low alerts) is gated by this same flag, not just raw prices.
#   - 2026-09-19 sweep found no free+legal substitute: 금융위 공공데이터 4유형
#     and KRX Open API both restrict redistribution, and all six free US EOD
#     sources are personal-use only.
# Until that agreement is signed the product runs on COST BASIS
# (avg_cost x shares), which is the user's own data and carries no vendor
# licence at all.
#
# NOT gated by this flag (deliberate):
#   - /api/market/fx  — open.er-api.com permits commercial use, and the FX
#     rate is required to add up a multi-currency COST basis.
#   - /api/search     — returns ticker/name/exchange reference data, no quote.
#     Gating it would make it impossible to record a new position.
#   - Internal/operator paths: SignalCache warming, the operator's own KIS
#     read-only account, and every scheduler job that does not emit a price to
#     a user. This flag turns off USER DISPLAY, not the fetch layer.
#
# Read it through ``services.market_display.market_data_display_enabled()``
# (never ``os.environ`` directly) so request handlers and tests can override
# it via ``current_app.config``.
#
# Consumed by:
#   - services/market_display.py   (single read point + shared 503 error)
#   - routes/portfolio.py          (portfolio / positions / summary / history)
#   - routes/market.py             (indices, public snapshot; fx exempt)
#   - routes/realtime.py           (price, portfolio-stream, status flag)
#   - routes/data_status.py        (stale banner -> "not displayed" state)
#   - routes/notifications.py      (hides the price_52w row while muted)
#   - app.py::_scheduled_price_alerts (skips the 52w sweep; concentration
#                                      keeps running — it is cost-basis only)
MARKET_DATA_DISPLAY_ENABLED = os.environ.get("MARKET_DATA_DISPLAY_ENABLED", "0").strip() in _TRUTHY_ENV


class Config:
    SECRET_KEY = _secret
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mirror the module-level flag onto the Flask config so request handlers
    # can read it via `current_app.config["ALPACA_ENABLED"]`.
    ALPACA_ENABLED = ALPACA_ENABLED

    # Mirrored for the same reason — request handlers and tests read/override
    # it via `current_app.config["MARKET_DATA_DISPLAY_ENABLED"]`.
    MARKET_DATA_DISPLAY_ENABLED = MARKET_DATA_DISPLAY_ENABLED

    # Connection pool settings (only effective for PostgreSQL; SQLite ignores them)
    if IS_POSTGRES:
        # 2026-05-20: Railway PG "too many clients already"로 모든 배포가 부팅
        # 실패(워커가 커넥션 못 얻음). 1-worker(gevent) + in-process 스케줄러(26잡)
        # 환경에서 풀을 대폭 축소해 footprint를 줄임 (구 15 → 5). 배포 시 old/new
        # 인스턴스 동시 실행 overlap에서도 PG max_connections 내에 들어오게 함.
        #
        # 2026-05-20 (CONN-001) — pool 상향(5→10) 검토 후 보류 결정.
        #   라이브 실측: monorail.proxy.rlwy.net:44311 으로 단일 read 커넥션
        #   조차 5회 연속 ``FATAL: sorry, too many clients already`` 거절 —
        #   즉 PG max_connections 가 *현재* 완전히 소진된 상태라 SHOW
        #   max_connections / pg_stat_activity 조차 못 읽음. Railway Hobby PG
        #   default 는 25 로 알려져 있고(메모리 추정과 일치) 확인 불가.
        #   이 상황에서 per-process 풀 ceiling 을 5→10 으로 올리면 deploy
        #   overlap(2 process × 10 = 20) + advisory-lock conn + 누수분으로
        #   소진을 *악화*시킨다. 병목은 풀 ceiling 이 아니라 (a) 스케줄러가
        #   느린 외부 API 호출 동안 커넥션을 점유하던 것(app.py CONN-001 에서
        #   loop 전 db.session.remove() 로 해소) + (b) deploy overlap 시 이중
        #   스케줄러(app.py CONN-001 PG advisory lock 으로 단일화)였다.
        #   따라서 풀은 그대로 5 로 유지하고 holding/overlap 을 코드로 줄였다.
        #   추후 max_connections 헤드룸 실측이 가능해지면 재검토.
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": 3,
            "max_overflow": 2,
            "pool_timeout": 20,
            "pool_recycle": 300,       # 5분마다 recycle — 유휴 커넥션 빨리 반환
            "pool_pre_ping": True,     # verify connections before use
        }
