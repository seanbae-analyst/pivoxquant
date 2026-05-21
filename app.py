"""
PivoxQuant — Flask Backend v2
Quant Engine + AI-powered portfolio & trading dashboard.
Supports US + Korean equities.
"""

import os
import uuid
import logging
import threading

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

import sentry_sdk
from flask import Flask, redirect, request, jsonify
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from extensions import db, login_manager, migrate
from routes import register_blueprints
from security import init_security
from services import container as svc
from services import fx_service, cache_service, alert_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Sentry filter ─────────────────────────────────────────────────────────────

# Sensitive header names (lowercased) — must NEVER reach Sentry/logs.
# Broker headers (appkey/appsecret) were added after the Wave 1 KIS OAuth work
# introduced services/broker/user_kis_service.py::_auth_headers(), which embeds
# the user's raw KIS credentials in outbound HTTP headers. Without masking, any
# exception raised during a KIS request would ship those credentials to Sentry.
SENSITIVE_HEADERS = frozenset({
    "authorization", "cookie", "set-cookie",
    "x-csrf-token", "x-api-key",
    "appkey", "appsecret",                # KIS broker credentials
    "tr_id",                              # KIS transaction id (not secret, but contextless in Sentry)
    "proxy-authorization",
})
_SENSITIVE_ENV_KEYS = frozenset({
    "HTTP_AUTHORIZATION", "HTTP_COOKIE",
    "HTTP_APPKEY", "HTTP_APPSECRET",
    "HTTP_X_CSRF_TOKEN", "HTTP_X_API_KEY",
})


def _mask_headers(headers: dict) -> None:
    """In-place: redact any sensitive header value to '***'.
    Case-insensitive match against SENSITIVE_HEADERS.
    """
    if not headers:
        return
    for key in list(headers.keys()):
        if key.lower() in SENSITIVE_HEADERS:
            headers[key] = "***"


def _sentry_filter(event, hint):
    # Strip sensitive headers from request data
    if "request" in event:
        headers = event["request"].get("headers", {})
        _mask_headers(headers)
        # Also strip from env if present
        env = event["request"].get("env", {})
        for key in _SENSITIVE_ENV_KEYS:
            env.pop(key, None)

    # Noise filtering — suppress noisy non-actionable errors
    msg = str(event.get("logentry", {}).get("message", "")) + str(hint.get("log_record", {}) if hint else "")
    noise = ["possibly delisted", "No price data found", "currentTradingPeriod",
             "No fundamentals data", "quoteSummary", "Expecting value",
             "Failed to get ticker", "Snapshot failed", "HTTP Error 404",
             "No data found"]
    all_text = msg + str(event.get("message", "")) + str(
        event.get("exception", {}).get("values", [{}])[0].get("value", "")
        if event.get("exception") else "")
    if any(n in all_text for n in noise):
        return None
    exc = hint.get("exc_info")
    if exc:
        if any(n in str(exc[1] or "") for n in noise):
            return None
    if str(event.get("logger", "")) in ("data_fetcher",):
        return None
    return event


_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    sentry_sdk.init(dsn=_sentry_dsn, traces_sample_rate=0.2,
                    send_default_pii=False, before_send=_sentry_filter)


def _set_sentry_user_type_tag() -> str:
    """Emit the ``user_type`` Sentry tag for the current request.

    Returns the tag value chosen (``"sim"`` / ``"real"`` / ``"anon"``) so
    unit tests can assert the classification without standing up a full
    Sentry initialisation. The tag itself goes through ``sentry_sdk.set_tag``
    which is a no-op when Sentry isn't initialised (no DSN) — safe in dev
    and tests.

    Continuous User Simulation Phase 1: sim user errors must be distinguishable
    from real-user errors in the dashboard so the simulation harness doesn't
    drown out genuine production issues.
    """
    try:
        from flask_login import current_user
        if not getattr(current_user, "is_authenticated", False):
            sentry_sdk.set_tag("user_type", "anon")
            return "anon"
        user_type = "sim" if bool(
            getattr(current_user, "is_simulated", False)
        ) else "real"
        sentry_sdk.set_tag("user_type", user_type)
        return user_type
    except Exception:
        # Sentry tagging must never break a request. Best-effort.
        logger.debug("sentry user_type tag failed", exc_info=True)
        return "anon"


# ── App factory ───────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Trusted proxy chain (W5.2 — 2026-05-11) ───────────────────────────
    # PivoxQuant runs behind a single trusted reverse proxy in production:
    # Vercel Edge → Railway gunicorn (apex) and Railway → gunicorn (api
    # subdomain). Without ProxyFix every request appears to originate from
    # the proxy's internal IP (10.x.x.x / Railway egress), which:
    #
    #   1. Collapses every visitor onto the same flask-limiter bucket so
    #      `get_remote_address` can no longer rate-limit per real client →
    #      rate limits are silently bypassed AND legitimate users get
    #      429-blocked because of someone else's traffic on the same proxy.
    #   2. Reports every request as `request.scheme == "http"`, so any
    #      `url_for(..., _external=True)` (used by OAuth callback, email
    #      unsubscribe links, brag-card share links) emits an `http://`
    #      URL that browsers / OAuth providers reject or downgrade.
    #   3. Logs the proxy IP in audit trails (routes/agent.py waitlist
    #      `remote_addr` JSON field) instead of the actual client.
    #
    # We trust exactly ONE hop: x_for=1, x_proto=1, x_host=1, x_prefix=1.
    # Trusting more hops than the deployment actually has would let an
    # attacker spoof headers in the trusted slot. Production = Vercel/Railway
    # both terminate at one proxy in front of gunicorn, so 1 is correct.
    #
    # Gated on `FLASK_ENV=production` so local dev (no proxy) and pytest
    # (which builds its own factory in tests/conftest.py) get untouched
    # `request.remote_addr`.
    if os.environ.get("FLASK_ENV", "development").lower() == "production":
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_prefix=1,
        )
        logger.info("SECURITY: ProxyFix enabled (1 trusted proxy hop)")

        # 2026-05-15 (launch prep): emit a boot-time inventory of every
        # env var that, if missing, silently degrades a real product
        # feature. Logs CRITICAL/WARNING per-var so Railway "Deploy
        # Logs" surfaces it. Reference: services/launch_prep.py +
        # docs/ops/email-setup.md.
        try:
            from services.launch_prep import check_env
            check_env(production=True)
        except Exception as exc:
            # Never let env validation crash boot.
            logger.warning("launch_prep.check_env failed: %s", exc)

    # Security middleware (CORS, Rate Limiting, CSRF, Session, Headers)
    init_security(app)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "index"

    # User loader
    from models import User

    @login_manager.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    # ── Global exception handler ──────────────────────────────────────────
    # Catches every unhandled exception bubbling out of a view/before-request
    # hook before Werkzeug turns it into an opaque 500 HTML page.
    #
    # Behaviour:
    #   • HTTPException (abort(4xx/5xx), NotFound, MethodNotAllowed, …)
    #       → let Flask render its default handler; only attach a request_id
    #         + log if it's a 5xx. The rate-limit 429 handler in security.py
    #         stays authoritative (errorhandler(429) registered earlier wins).
    #   • Anything else (unhandled exception)
    #       → rollback any dangling DB transaction so the worker's session
    #         isn't poisoned for the next request.
    #       → log with request_id so Railway logs can be correlated with the
    #         client-visible error.
    #       → Sentry gets the full exception automatically (sentry_sdk.init
    #         above registers a Flask integration).
    #       → API callers (/api/*) get a JSON error envelope matching the
    #         shape used elsewhere (`error`, `code`, `request_id`).
    #       → Browser callers are bounced to /login?error=server_error with
    #         the request_id in the query string for support tickets.
    #
    # NOTE: @app.errorhandler(Exception) does NOT override the specific
    # @app.errorhandler(429) registered in security.init_security — Flask
    # dispatches to the most specific handler first.
    @app.errorhandler(Exception)
    def _handle_unhandled_exception(exc):
        # HTTPException (incl. 404/405/401/403/429) — preserve Flask's default
        # rendering. Only annotate 5xx HTTP errors with a request_id.
        if isinstance(exc, HTTPException):
            if exc.code and exc.code >= 500:
                request_id = uuid.uuid4().hex[:12]
                logger.exception(
                    "HTTP %s on %s %s — request_id=%s",
                    exc.code, request.method, request.path, request_id,
                )
            return exc

        request_id = uuid.uuid4().hex[:12]

        # Roll back any dangling DB transaction. A SQLAlchemyError leaves
        # the session in a "transaction aborted" state; subsequent queries
        # on the same worker will all fail with InvalidRequestError until
        # we rollback(). Best-effort — never let rollback itself 500.
        try:
            db.session.rollback()
        except Exception:  # pragma: no cover — defensive
            logger.exception("Rollback failed in global error handler (request_id=%s)", request_id)

        logger.exception(
            "Unhandled exception on %s %s — request_id=%s",
            request.method, request.path, request_id,
        )

        # API callers get JSON; browser callers get a friendly redirect.
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "Internal server error. Please try again.",
                "error_kr": "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            }), 500

        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        return redirect(f"{frontend_url}/login?error=server_error&rid={request_id}")

    # ── Sentry user-type tag (Continuous User Simulation Phase 1) ─────────
    # Tag every Sentry event with ``user_type=sim`` / ``real`` / ``anon``
    # so the dashboard can filter / alert separately. Sim user errors are
    # expected (the Sunday 04:30 KST simulation deliberately exercises edge
    # cases) and would otherwise drown the real-user signal in noise.
    # ``send_default_pii=False`` (line 98) keeps email/id out of payloads —
    # we only emit the boolean classification.
    @app.before_request
    def _sentry_user_type_tag():
        _set_sentry_user_type_tag()

    @app.after_request
    def no_cache(r):
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        r.headers["Pragma"] = "no-cache"
        return r

    @app.route("/")
    def index():
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        return redirect(frontend_url)

    # Register all blueprints
    register_blueprints(app)

    # Google OAuth
    from routes.auth import init_oauth
    init_oauth(app)

    # FX rate
    fx_service.init_async()

    # Database init & migrations
    with app.app_context():
        db.create_all()
        _run_migrations(app)

    # Cache warm-up — off the boot path.
    # Originally this ran synchronously and called FMP/Alpaca per ticker,
    # pushing boot time past Railway's 30s healthcheck and doubling the API
    # quota burn when gunicorn ran 2+ workers. Now it runs in a daemon thread
    # so the HTTP server binds immediately, and is gated by POPULATE_CACHE_ON_BOOT
    # (default "1"; set "0" to skip entirely — e.g., for worker #2).
    if os.environ.get("POPULATE_CACHE_ON_BOOT", "1") == "1":
        threading.Thread(
            target=_populate_cache,
            args=(app,),
            daemon=True,
            name="cache-warmup",
        ).start()

    # Background scheduler — opt-in to avoid duplicate execution under
    # multi-worker gunicorn (each worker would otherwise spin up its own
    # scheduler, causing weekly_memo / refresh jobs to fire N times).
    # Default off. Set RUN_SCHEDULER=1 in exactly one process (e.g. a
    # dedicated worker dyno, or when Procfile is pinned to --workers 1).
    if os.environ.get("RUN_SCHEDULER", "0") == "1":
        _init_scheduler(app)

    return app


def _run_migrations(app):
    """Run safe column-addition migrations for both SQLite and PostgreSQL.

    PostgreSQL rolls back the entire transaction on ALTER TABLE errors,
    so we check column existence first instead of relying on try/except.

    When running on PostgreSQL with multiple workers (gunicorn on Railway),
    we acquire a session-level advisory lock so that only one worker performs
    the check-then-act migration. Other workers block until it completes,
    then see the columns already exist and no-op. SQLite stays single-process
    so the lock is skipped.
    """
    dialect = db.engine.dialect.name

    if dialect == "postgresql":
        # Acquire advisory lock on a DEDICATED connection so it's isolated
        # from the ALTER TABLE work in `_do_migrations()`. Previous impl used
        # `db.session` for both lock and unlock — a single failed migration
        # would abort the session's transaction, causing the final unlock
        # to raise `InFailedSqlTransaction` and leave the lock stuck until
        # the worker exits. Isolation here makes the unlock path bullet-proof.
        with db.engine.connect() as lock_conn:
            # Use autocommit so lock/unlock aren't bundled into an implicit txn
            # that could be poisoned by unrelated failures.
            lock_conn = lock_conn.execution_options(isolation_level="AUTOCOMMIT")
            lock_conn.execute(text(
                "SELECT pg_advisory_lock(hashtext('pivoxquant_migrate'))"
            ))
            try:
                _do_migrations()
            except Exception:
                # Leave the advisory lock release to `finally`; re-raise so
                # the caller can log the root cause and fail fast if needed.
                raise
            finally:
                try:
                    lock_conn.execute(text(
                        "SELECT pg_advisory_unlock(hashtext('pivoxquant_migrate'))"
                    ))
                except Exception:  # pragma: no cover — best-effort cleanup
                    logger.debug("silent-fallback: _run_migrations", exc_info=True)
                    pass
    else:
        # SQLite — single process, no contention possible.
        _do_migrations()


def _do_migrations():
    """Idempotent column-addition migrations. Safe to call concurrently only
    when protected by an external lock (see _run_migrations)."""
    from sqlalchemy import inspect as _inspect

    inspector = _inspect(db.engine)

    def _existing_columns(table_name):
        try:
            return {col["name"] for col in inspector.get_columns(table_name)}
        except Exception:
            return set()

    is_postgres = db.engine.dialect.name == "postgresql"

    def _add_column_if_missing(
        table, column, col_type, default=None, unique=False, not_null=False,
    ):
        existing = _existing_columns(table)
        if column in existing:
            return
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        if default is not None:
            # PostgreSQL is strict: BOOLEAN columns reject integer defaults
            # (e.g. `DEFAULT 0`). Translate 0/1 → false/true for BOOLEAN
            # targets on PG; SQLite accepts both forms.
            resolved_default = default
            if is_postgres and col_type.upper().startswith("BOOLEAN"):
                if str(default).strip() in ("0", "'0'"):
                    resolved_default = "false"
                elif str(default).strip() in ("1", "'1'"):
                    resolved_default = "true"
            sql += f" DEFAULT {resolved_default}"
        # NOT NULL must come AFTER DEFAULT so existing rows are backfilled
        # by the server default (otherwise PG aborts the ALTER).
        if not_null:
            sql += " NOT NULL"
        # PostgreSQL supports UNIQUE inline; SQLite does not (raises OperationalError)
        if unique and is_postgres:
            sql += " UNIQUE"
        with db.engine.begin() as conn:
            conn.execute(text(sql))
            # For SQLite (and as a fallback), create the unique index separately
            if unique and not is_postgres:
                idx_name = f"uq_{table}_{column}"
                conn.execute(text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} ON {table}({column})"
                ))
        logger.info(f"Migration: added {table}.{column}")

    # Users table — full coverage of User model columns so any DB
    # (new PG instance, restored snapshot, legacy SQLite dev box) can
    # boot without ProgrammingError / OperationalError on SELECT.
    _add_column_if_missing("users", "available_capital", "FLOAT", default="0.0")
    _add_column_if_missing("users", "available_capital_krw", "FLOAT", default="0.0")
    _add_column_if_missing("users", "risk_profile", "VARCHAR(20)", default="'balanced'")
    _add_column_if_missing("users", "profile_changes_left", "INTEGER", default="3")
    _add_column_if_missing("users", "subscription_tier", "VARCHAR(10)", default="'free'")
    _add_column_if_missing("users", "onboarding_completed", "BOOLEAN", default="0")
    _add_column_if_missing("users", "google_id", "VARCHAR(100)", unique=True)
    _add_column_if_missing("users", "avatar_url", "VARCHAR(500)")
    _add_column_if_missing("users", "oauth_provider", "VARCHAR(20)")
    _add_column_if_missing("users", "kakao_id", "VARCHAR(100)", unique=True)
    _add_column_if_missing("users", "stripe_customer_id", "VARCHAR(100)")
    _add_column_if_missing("users", "stripe_subscription_id", "VARCHAR(100)")
    _add_column_if_missing("users", "subscription_status", "VARCHAR(20)", default="'inactive'")
    # MVP #2 Brag Card — anonymous-mode toggle. Added via Alembic
    # migration 008_brag_card_fields; this runtime hook covers boxes
    # that booted without running Alembic (and legacy local dev DBs).
    _add_column_if_missing("users", "privacy_mode", "BOOLEAN", default="0")
    # Viral-loop referral code mirror. Nullable + unique.
    _add_column_if_missing("users", "referral_code", "VARCHAR(16)", unique=True)
    # MVP #3 Earnings Pre-Brief — per-channel email opt-out. Added via
    # migration 009_earnings_prebrief; this runtime hook covers existing
    # local dev DBs that boot without running Alembic.
    _add_column_if_missing("users", "email_opt_out_earnings", "BOOLEAN", default="0")
    # Global marketing/transactional email opt-out (정통망법 §50). Added via
    # migration 021_email_opt_out / 022_alerts_watchlist_dd_columns; this
    # runtime hook is the P0 hotfix for legacy DBs (incl. Railway prod) that
    # boot before Alembic completes — without this column the User SELECT
    # raises ProgrammingError, causing /api/auth/login + /register 500s.
    _add_column_if_missing("users", "email_opt_out", "BOOLEAN", default="0")
    # 정통망법 §50 ① marketing-consent evidentiary record. Added via
    # migration 023_marketing_consent; this runtime hook covers boxes that
    # boot without running Alembic (legacy local SQLite, fresh Railway
    # services that race the alembic step). Both columns are nullable
    # DateTimes — NULL on marketing_consent_at means "never consented",
    # which is the safest default for the §50 default-deny posture.
    _add_column_if_missing("users", "marketing_consent_at", "TIMESTAMP")
    _add_column_if_missing("users", "marketing_consent_revoked_at", "TIMESTAMP")
    # 정통망법 §50 ① 정보성/광고성 분리 동의 (Wave D Sub-wave 1, C-S1).
    # Alembic migration 037_marketing_consent_split. application layer 는
    # PIVOX_CS1_CONSENT_ENABLED 플래그 (default false) 에 게이트되어 dormant 이지만,
    # User SELECT 는 ORM 매핑상 항상 이 4개 컬럼을 조회하므로 컬럼 자체가 누락되면
    # 모든 인증/프로비저닝 SELECT 가 ProgrammingError 로 500 (= provisioning_failed).
    # alembic 미실행 박스(Railway prod, 레거시 SQLite)를 위한 boot-time self-heal.
    _add_column_if_missing("users", "marketing_consent_information_at", "TIMESTAMP")
    _add_column_if_missing("users", "marketing_consent_information_revoked_at", "TIMESTAMP")
    _add_column_if_missing("users", "marketing_consent_marketing_at", "TIMESTAMP")
    _add_column_if_missing("users", "marketing_consent_marketing_revoked_at", "TIMESTAMP")
    # PIPA §28-8 (2024-09 시행) 국외이전 별도 동의 타임스탬프. Anthropic
    # PBC / Stripe / Vercel / Railway (미국) 으로의 이전·위탁에 대한 명시적
    # 별도 동의가 §28-8 의무이며, 본 컬럼이 NULL 이면 동의 미수령으로
    # 간주한다. Managed via migration 024_cross_border_consent — 본 fallback
    # 은 Alembic 미실행 박스(레거시 로컬 dev DB)를 위한 안전망이다.
    _add_column_if_missing("users", "cross_border_consent_at", "TIMESTAMP")
    _add_column_if_missing("users", "cross_border_consent_revoked_at", "TIMESTAMP")
    # PIPA §22 ⑥ (만 14세 미만 법정대리인 동의) — server-side birthdate 검증.
    # Alembic migration 031_user_birthdate (PR #283)로 추가했으나 prod 코드베이스는
    # alembic 미사용 (db.create_all() + _add_column_if_missing 패턴). 누락으로
    # 인해 prod에서 SELECT users.birthdate ProgrammingError 발생 (2026-05-12
    # bug-hunter 발견, Railway logs). 본 fallback은 prod safety net.
    _add_column_if_missing("users", "birthdate", "DATE")
    # Continuous User Simulation (CAUS) Phase 1 — sim/real user 격리 플래그.
    # Alembic migration 032_users_is_simulated (PR #351). prod 가 alembic 미적용
    # 상태로 운영되어 (alembic_version 테이블 부재 — 2026-05-13 발견) 본 컬럼이
    # 누락된 채 sim-onboard endpoint 500 발생 (UndefinedColumn: users.is_simulated).
    # 본 runtime fallback 으로 alembic 실행 여부와 무관하게 boot 시 안전하게 추가.
    # NOT NULL DEFAULT FALSE 로 backfill — 기존 user 는 모두 real user 로 분류.
    _add_column_if_missing(
        "users", "is_simulated", "BOOLEAN", default="false", not_null=True,
    )
    # Onboarding partial-save draft slot. Alembic migration 035_user_onboarding_draft
    # (PR #427). 본 runtime fallback 은 prod alembic 미실행 박스 보호 — "계정 프로비저닝"
    # 에러 (psycopg2.errors.UndefinedColumn: users.onboarding_draft_json) hotfix.
    # 2026-05-17 Railway prod logs 직접 cite.
    _add_column_if_missing("users", "onboarding_draft_json", "TEXT")
    # Wave G C-S2 (2026-05-19) — 24h inactive nudge idempotency timestamp.
    # Alembic migration 038_inactive_nudge_sent_at. nullable DateTime (NULL =
    # never nudged). 본 컬럼이 ORM 매핑에 존재하므로 누락 시 User SELECT
    # ProgrammingError → OAuth provisioning_failed. alembic 미실행 박스 self-heal.
    _add_column_if_missing("users", "inactive_nudge_sent_at", "TIMESTAMP")
    # Wave I C-2 (2026-05-19) — PIPA §21 30-day soft-delete grace period.
    # Alembic migration 041_user_deletion_request. 두 컬럼 모두 nullable DateTime.
    # google_callback / kakao_callback 이 로그인 직후 user.deletion_requested_at
    # 을 직접 읽으므로(2026-05-19 soft-delete reject), 컬럼 누락 시 provisioning
    # SELECT 가 아니라 로그인 직후 attribute access 에서 터지거나 SELECT 자체가
    # ProgrammingError 로 실패한다. alembic 미실행 박스 self-heal.
    _add_column_if_missing("users", "deletion_requested_at", "TIMESTAMP")
    _add_column_if_missing("users", "deleted_at", "TIMESTAMP")
    # Settings v2 notification matrix persistence (2026-05-21). Alembic
    # migration 043_notification_prefs. nullable JSON (NULL = use code-level
    # NOTIFICATION_PREF_DEFAULTS). 본 컬럼이 ORM 매핑에 존재하므로 누락 시
    # 모든 User SELECT 가 ProgrammingError → OAuth provisioning_failed.
    # alembic 미실행 박스(Railway prod, 레거시 SQLite) self-heal.
    _add_column_if_missing("users", "notification_prefs", "JSON")

    # Positions table — full coverage of Position model columns.
    # thesis_* columns were added in commit c6644c2 (Thesis Tracker) but
    # _do_migrations() was never updated, causing ProgrammingError on
    # INSERT when Railway PostgreSQL does not have these columns.
    _add_column_if_missing("positions", "buy_fx_rate", "FLOAT", default="0.0")
    _add_column_if_missing("positions", "thesis", "VARCHAR(500)")
    _add_column_if_missing("positions", "thesis_created_at", "TIMESTAMP")
    _add_column_if_missing("positions", "thesis_last_checked", "TIMESTAMP")
    _add_column_if_missing("positions", "thesis_status", "VARCHAR(20)", default="'pending'")
    _add_column_if_missing("positions", "thesis_reason", "VARCHAR(500)")

    # Alerts table — full coverage of Alert model columns.
    # Added defensively because post-creation column additions (score, signal,
    # rec_shares, rec_investment, is_read) must survive legacy DBs that were
    # created before those columns existed.
    _add_column_if_missing("alerts", "ticker", "VARCHAR(20)")
    _add_column_if_missing("alerts", "signal", "VARCHAR(10)")
    _add_column_if_missing("alerts", "score", "FLOAT", default="0")
    _add_column_if_missing("alerts", "rec_shares", "INTEGER", default="0")
    _add_column_if_missing("alerts", "rec_investment", "FLOAT", default="0")
    _add_column_if_missing("alerts", "is_read", "BOOLEAN", default="0")
    # 2026-04-22 — NotificationDropdown bell fields (kind/title/body/link/read_at).
    _add_column_if_missing("alerts", "kind", "VARCHAR(40)")
    _add_column_if_missing("alerts", "title", "VARCHAR(200)")
    _add_column_if_missing("alerts", "body", "TEXT")
    _add_column_if_missing("alerts", "link", "VARCHAR(300)")
    _add_column_if_missing("alerts", "read_at", "TIMESTAMP")

    # Artifacts table — full coverage of Artifact model columns.
    # `share_token` was added post-initial-creation (MVP#2 Brag Card public
    # share); other cols are base but safe to declare idempotently.
    _add_column_if_missing("artifacts", "data_json", "JSON")
    _add_column_if_missing("artifacts", "pdf_path", "VARCHAR(500)")
    _add_column_if_missing("artifacts", "sent_at", "TIMESTAMP")
    _add_column_if_missing("artifacts", "opened_at", "TIMESTAMP")
    _add_column_if_missing("artifacts", "share_token", "VARCHAR(32)")
    # Migration 025 (SendGrid Event Webhook tracking) — keep the runtime
    # ADD COLUMN guard in sync so legacy SQLite DBs (created before
    # alembic was the canonical migrator) don't blow up on the first
    # write to ``bounced_at`` / ``unsubscribed_at`` / ``sg_message_id``.
    _add_column_if_missing("artifacts", "bounced_at", "TIMESTAMP")
    _add_column_if_missing("artifacts", "unsubscribed_at", "TIMESTAMP")
    _add_column_if_missing("artifacts", "sg_message_id", "VARCHAR(128)")

    # Broker connections — Week 1 (2026-04-18) added AES-256-GCM encrypted
    # credential columns. HIGH RISK of ProgrammingError on legacy DBs.
    _add_column_if_missing("broker_connections", "access_token", "TEXT")
    _add_column_if_missing("broker_connections", "refresh_token", "TEXT")
    _add_column_if_missing("broker_connections", "account_id", "VARCHAR(50)")
    _add_column_if_missing("broker_connections", "is_paper", "BOOLEAN", default="1")
    _add_column_if_missing("broker_connections", "is_active", "BOOLEAN", default="1")
    _add_column_if_missing("broker_connections", "last_synced_at", "TIMESTAMP")
    _add_column_if_missing("broker_connections", "encrypted_app_key", "TEXT")
    _add_column_if_missing("broker_connections", "encrypted_app_secret", "TEXT")
    _add_column_if_missing("broker_connections", "encrypted_account_no", "TEXT")
    _add_column_if_missing("broker_connections", "account_prod", "VARCHAR(4)", default="'01'")
    _add_column_if_missing("broker_connections", "encrypted_access_token", "TEXT")
    _add_column_if_missing("broker_connections", "token_expires_at", "TIMESTAMP")
    _add_column_if_missing("broker_connections", "encryption_key_version", "SMALLINT", default="1")
    _add_column_if_missing("broker_connections", "display_name", "VARCHAR(100)")
    _add_column_if_missing("broker_connections", "last_sync_status", "VARCHAR(20)")
    _add_column_if_missing("broker_connections", "last_sync_error", "TEXT")
    _add_column_if_missing("broker_connections", "consecutive_failures", "INTEGER", default="0")

    # Trade history — post-creation columns: pnl, pnl_pct, name, currency.
    _add_column_if_missing("trade_history", "name", "VARCHAR(100)", default="''")
    _add_column_if_missing("trade_history", "pnl", "FLOAT", default="0.0")
    _add_column_if_missing("trade_history", "pnl_pct", "FLOAT", default="0.0")
    _add_column_if_missing("trade_history", "currency", "VARCHAR(5)", default="'USD'")

    # Investment profiles — covers onboarding answers + auto-calc quant params.
    _add_column_if_missing("investment_profiles", "experience_level", "VARCHAR(20)", default="'beginner'")
    _add_column_if_missing("investment_profiles", "investment_goal", "VARCHAR(30)", default="'growth'")
    _add_column_if_missing("investment_profiles", "risk_tolerance", "INTEGER", default="5")
    _add_column_if_missing("investment_profiles", "time_horizon", "VARCHAR(20)", default="'medium'")
    _add_column_if_missing("investment_profiles", "preferred_markets", "VARCHAR(10)", default="'both'")
    _add_column_if_missing("investment_profiles", "preferred_sectors", "TEXT", default="'[]'")
    _add_column_if_missing("investment_profiles", "auto_trade_preference", "VARCHAR(20)", default="'manual'")
    _add_column_if_missing("investment_profiles", "daily_time", "VARCHAR(20)", default="'moderate'")
    _add_column_if_missing("investment_profiles", "profile_type", "VARCHAR(20)", default="'balanced'")
    _add_column_if_missing("investment_profiles", "tech_weight", "FLOAT", default="0.50")
    _add_column_if_missing("investment_profiles", "fund_weight", "FLOAT", default="0.30")
    _add_column_if_missing("investment_profiles", "news_weight", "FLOAT", default="0.20")
    _add_column_if_missing("investment_profiles", "tp_min", "FLOAT", default="8.0")
    _add_column_if_missing("investment_profiles", "tp_max", "FLOAT", default="15.0")
    _add_column_if_missing("investment_profiles", "sl_min", "FLOAT", default="5.0")
    _add_column_if_missing("investment_profiles", "sl_max", "FLOAT", default="8.0")
    _add_column_if_missing("investment_profiles", "max_positions", "INTEGER", default="15")
    _add_column_if_missing("investment_profiles", "buy_threshold", "FLOAT", default="70.0")
    _add_column_if_missing("investment_profiles", "sell_threshold", "FLOAT", default="25.0")
    _add_column_if_missing("investment_profiles", "ai_coaching_style", "VARCHAR(20)", default="'balanced'")
    _add_column_if_missing("investment_profiles", "alert_frequency", "VARCHAR(20)", default="'daily'")
    _add_column_if_missing("investment_profiles", "updated_at", "TIMESTAMP")
    # Feature 1 (Quant Composer) — TEXT JSON columns. Empty list/dict default so
    # the engine stays backward compatible for users who never opted in.
    _add_column_if_missing("investment_profiles", "enabled_quant_models", "TEXT", default="'[]'")
    _add_column_if_missing("investment_profiles", "model_weights", "TEXT", default="'{}'")

    # User referrals — `invited_count` is the one post-create candidate.
    _add_column_if_missing("user_referrals", "invited_count", "INTEGER", default="0")

    # Watchlist — `note` is a free-text memo (2026-04-22). Added post-create
    # so legacy DBs need an idempotent ALTER here.
    _add_column_if_missing("watchlist", "note", "VARCHAR(500)")

    # 2026-04-19 — position_dd_checks: create the table if absent.
    # The model is covered by `db.create_all()` on first boot, but we
    # also guard here so live DBs that were migrated before this table
    # existed don't need a manual `flask db upgrade` step.
    try:
        existing_tables = set(inspector.get_table_names())
    except Exception:
        existing_tables = set()
    if "position_dd_checks" not in existing_tables:
        try:
            from models.position_dd_check import PositionDDCheck  # noqa: F401
            db.metadata.tables["position_dd_checks"].create(bind=db.engine)
            logger.info("Migration: created table position_dd_checks")
        except Exception as exc:
            logger.warning("Migration: could not create position_dd_checks: %s", exc)
    else:
        # Idempotent column backfill — matches the pattern used for
        # other tables above.
        _add_column_if_missing("position_dd_checks", "financials_checked", "BOOLEAN", default="0")
        _add_column_if_missing("position_dd_checks", "moat_checked",       "BOOLEAN", default="0")
        _add_column_if_missing("position_dd_checks", "management_checked", "BOOLEAN", default="0")
        _add_column_if_missing("position_dd_checks", "valuation_checked",  "BOOLEAN", default="0")
        _add_column_if_missing("position_dd_checks", "risks_checked",      "BOOLEAN", default="0")
        _add_column_if_missing("position_dd_checks", "note",               "VARCHAR(500)")

    # Portfolio shares / push subscriptions / signal_cache / watchlist —
    # all their current columns are in the initial create_all snapshot.
    # No post-creation additions observed. Declared here as a no-op safety
    # net so future model additions auto-get a migration hook.

    # Backfill FX rates
    from models import Position
    try:
        rate = fx_service.get_rate()
        us_positions = Position.query.filter(
            ~Position.ticker.endswith('.KS'),
            ~Position.ticker.endswith('.KQ'),
            (Position.buy_fx_rate == None) | (Position.buy_fx_rate == 0)
        ).all()
        if us_positions:
            for p in us_positions:
                p.buy_fx_rate = rate
            db.session.commit()
            logger.info(f"Backfilled buy_fx_rate for {len(us_positions)} US positions (rate: {rate})")
    except Exception:
        logger.debug("silent-fallback: _do_migrations", exc_info=True)
        pass


def _populate_cache(app):
    """Warm the signal cache for currently-held tickers.

    Runs in a daemon thread off the boot path, so it enters its own
    app context. Failures here must never kill the worker.
    """
    from models import Position, SignalCache
    with app.app_context():
        try:
            positions = Position.query.all()
            tickers = list(set(p.ticker for p in positions))
            cached = set(c.ticker for c in SignalCache.query.all())
            missing = [t for t in tickers if t not in cached]
            if missing:
                logger.info(f"[cache-warmup] populating signal cache for {len(missing)} tickers...")
                for ticker in missing:
                    try:
                        r = svc.engine.analyze(ticker, 10000)
                        if r:
                            cache_service.save_signal(ticker, r)
                            logger.info(f"[cache-warmup]   cached: {ticker}")
                    except Exception as e:
                        logger.error(f"[cache-warmup]   failed {ticker}: {e}")
                logger.info("[cache-warmup] complete.")
        except Exception as e:
            logger.error(f"[cache-warmup] error: {e}")


# ── CONN-001: scheduler advisory-lock state ────────────────────────────────
# Holds the dedicated psycopg2 connection that owns the PG session advisory
# lock for the lifetime of this process. MUST stay referenced at module scope
# — if it were garbage-collected the connection would close and PostgreSQL
# would release the lock, letting a second process also start the scheduler.
_SCHEDULER_LOCK_CONN = None
# Arbitrary but stable 64-bit key shared across all PivoxQuant processes.
_SCHEDULER_LOCK_KEY = 0x50_49_56_4F_58  # "PIVOX" hex — any constant works.


def _try_acquire_scheduler_lock() -> bool:
    """Return True if THIS process should own the scheduler.

    On PostgreSQL: opens a dedicated connection and calls
    ``pg_try_advisory_lock`` (non-blocking). The lock is held for the process
    lifetime via ``_SCHEDULER_LOCK_CONN`` and auto-released by PG on
    disconnect (i.e. when the old container dies during a deploy).

    On SQLite / any error: returns True (fail-safe — never lose crons).
    """
    global _SCHEDULER_LOCK_CONN
    try:
        from config import IS_POSTGRES
    except Exception:
        return True
    if not IS_POSTGRES:
        # Local dev (SQLite) has no advisory locks and no deploy overlap.
        return True
    try:
        # A raw psycopg2 connection — deliberately OUTSIDE the SQLAlchemy pool
        # so it is never recycled/returned (which would drop the lock).
        import psycopg2
        import time as _time
        from config import _db_url  # already postgres://→postgresql:// normalised
        # CONN-001 P2: connect_timeout + keepalives so a half-dead socket from a
        # SIGKILLed container doesn't hang the boot, and PG reaps the dead lock
        # holder promptly. Retry once after a short backoff to cover the narrow
        # deploy-overlap window where the previous container's advisory lock has
        # not yet been released by PG when the new container boots.
        for _attempt in range(2):
            conn = psycopg2.connect(
                _db_url,
                connect_timeout=5,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (_SCHEDULER_LOCK_KEY,))
                got = bool(cur.fetchone()[0])
            if got:
                # Keep the connection (and therefore the lock) alive for the
                # process lifetime.
                _SCHEDULER_LOCK_CONN = conn
                return True
            # Lost the race — release this short-lived connection immediately,
            # then retry once (the old container may still be releasing).
            conn.close()
            if _attempt == 0:
                _time.sleep(0.5)
        return False
    except Exception:
        logger.exception(
            "scheduler advisory-lock acquire failed — falling back to "
            "starting the scheduler (fail-safe)"
        )
        return True


def _init_scheduler(app):
    def _scheduled_refresh():
        from models import Position, User
        with app.app_context():
            # CONN-001 (2026-05-20): release the DB connection BEFORE the slow
            # external-API analyse loop. Previously this held one pooled
            # connection checked out for the ENTIRE loop body — each
            # ``svc.engine.analyze()`` call hits FMP/Alpaca (multiple seconds)
            # while still pinning the connection. With pool max 5 and an
            # in-process scheduler (26 jobs) plus a deploy-overlap second
            # scheduler instance, that pinned connection was a primary driver
            # of ``FATAL: sorry, too many clients already`` → cold 500 burst.
            #
            # Strategy: read everything we need into plain Python objects, then
            # ``db.session.remove()`` so the connection returns to the pool
            # while the (connection-free) external API calls run. The per-
            # ticker write path (save_signal / maybe_generate) lazily
            # re-acquires a SHORT connection from the pool and we release it
            # again at the end of each iteration so no connection is ever held
            # across an ``analyze()`` call.
            positions = Position.query.all()
            # Continuous User Simulation Phase 1 — exclude ``is_simulated=True``
            # from the alert-generation refresh. Sim users would otherwise
            # trigger real Alert rows + push/email side effects via
            # alert_service.maybe_generate. The push/email layers also
            # short-circuit per-row, but excluding here saves the engine
            # analyse loop overhead. Position rows owned by a sim user
            # fall through with available_capital=10_000 default (no user
            # row found) and produce a signal only when a *real* user also
            # holds the same ticker — which is the intended behaviour.
            cap_by_uid = {u.id: u.available_capital for u in
                          User.query.filter_by(is_simulated=False).all()}
            tku: dict[str, list[int]] = {}
            for p in positions:
                tku.setdefault(p.ticker, []).append(p.user_id)
            # Materialise to plain tuples so nothing below touches a detached
            # ORM instance after the session is removed.
            work = list(tku.items())
            # Release the connection before any external API work.
            db.session.remove()

            for ticker, uids in work:
                cap = cap_by_uid.get(uids[0], 10_000)
                try:
                    # No DB connection held here — analyze() may take seconds.
                    r = svc.engine.analyze(ticker, cap)
                    if r:
                        # Quick writes only; these lazily re-acquire a
                        # connection from the pool.
                        cache_service.save_signal(ticker, r)
                        for uid in uids:
                            alert_service.maybe_generate(uid, r)
                except Exception as e:
                    logger.error(f"Scheduler failed {ticker}: {e}")
                finally:
                    # Return the (re-acquired) connection to the pool before the
                    # next iteration's analyze() call so it is never pinned
                    # across slow external I/O.
                    db.session.remove()
            logger.info(f"Scheduled refresh done — {len(work)} tickers")

    def _scheduled_indices_cache_warm():
        """Keep the headline-index cache warm for the public landing ticker.

        The unauthenticated ``GET /api/public/market-snapshot`` endpoint is
        strictly cache-only — it reads ``routes.market._indices_cache`` and
        never fetches upstream itself. That cache used to be filled ONLY
        when an authenticated user opened the ``/market`` tab, so a
        deployment with zero authenticated traffic left the landing ticker
        cold (is_stale / null rows).

        This job closes that gap: a controlled background refresh (NOT a
        per-request fetch) of both regions via the shared
        ``warm_indices_cache`` path. It is TTL-gated inside that helper, so
        with the market-aware ``indices_ttl`` an upstream fetch only
        actually fires roughly every 15s during market hours and every
        ~5min off-hours — the fixed 60s tick below is just the upper bound.

        No new infra / cost: reuses the existing KIS + Alpaca licenses and
        the existing APScheduler. A failure here (KIS down, etc.) is logged
        and swallowed so it never takes down the scheduler or the app.
        """
        with app.app_context():
            try:
                from routes.market import warm_indices_cache
                us_n = warm_indices_cache("us")
                kr_n = warm_indices_cache("kr")
                logger.info(
                    "Indices cache-warm done — us=%s kr=%s rows", us_n, kr_n
                )
            except Exception as e:
                logger.error(f"Indices cache-warm scheduler failed: {e}")

    def _scheduled_weekly_memo():
        """Generate + email the weekly investor memo to Pro+ users.

        Fires Sunday 08:00 Asia/Seoul. Free users are silently skipped.
        Empty portfolios are skipped. Failure of one user never blocks
        the others — see WeeklyMemoService.run_weekly.
        """
        from services.artifacts.weekly_memo_service import WeeklyMemoService
        with app.app_context():
            try:
                summary = WeeklyMemoService().run_weekly()
                logger.info(f"Weekly memo scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Weekly memo scheduler failed: {e}")

    def _scheduled_monthly_brag():
        """Generate + email the monthly brag card to every user.

        Fires 1st of each month 09:00 Asia/Seoul. Unlike the weekly memo
        this runs for Free users too — the brag card is the viral loop
        input. Empty portfolios receive a "welcome" variant so new
        signups aren't excluded from the habit.
        """
        from services.artifacts.monthly_brag_service import MonthlyBragService
        with app.app_context():
            try:
                summary = MonthlyBragService().run_monthly()
                logger.info(f"Monthly brag scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Monthly brag scheduler failed: {e}")

    def _scheduled_brag_card():
        """Generate + email the Playwright-rendered brag card (MVP #2).

        Same cadence as `_scheduled_monthly_brag` (1st of month, 09:00
        KST) but calls the newer `BragCardService` which renders a 9:16
        HTML card via headless Chromium. The two schedulers run side by
        side during the rollout — operators can disable whichever they
        prefer by removing the relevant `sched.add_job` call below.
        """
        from services.artifacts.brag_card_service import BragCardService
        with app.app_context():
            try:
                summary = BragCardService().run_monthly()
                logger.info(f"Brag card scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Brag card scheduler failed: {e}")

    def _scheduled_kpi_dashboard():
        """Daily 08:00 KST — 5-metric KPI email (Pro+).

        Short HTML email, no PDF. Empty portfolios are skipped. Per-user
        failures never block the rest — see KPIDashboardService.run_daily.
        """
        from services.artifacts.kpi_dashboard_service import KPIDashboardService
        with app.app_context():
            try:
                summary = KPIDashboardService().run_daily()
                logger.info(f"KPI dashboard scheduler run: {summary}")
            except Exception as e:
                logger.error(f"KPI dashboard scheduler failed: {e}")

    def _scheduled_self_audit():
        """DEPRECATED (2026-04-19) — absorbed into Quarterly Self Report.

        The standalone Self Audit job was retired when the 15-page
        Quarterly Self Report (`quarterly_self_report_service`) was
        introduced. Part 2 (P8-P11) of the new report re-uses
        `SelfAuditService.generate_for_user(...)` internally, so every
        user still receives the same decision-quality analysis — just
        inside the larger quarterly deliverable instead of a separate
        email.

        This function is kept as a no-op; the sched.add_job registration
        below is commented out to disable the duplicate cron.
        """
        logger.info(
            "self_audit standalone job is deprecated — "
            "see quarterly_self_report"
        )

    def _scheduled_quarterly_self_report():
        """Quarterly (1/7, 4/7, 7/7, 10/7) 10:00 KST — Premium 15-page
        Self 10-K + Thesis Reality Check.

        Wraps the old Self Audit (Part 2) and adds a full Self 10-K
        narrative (Part 1) + watch items. The service resolves the
        quarter that just closed via `_quarter_bounds`.
        """
        from services.artifacts.quarterly_self_report_service import (
            QuarterlySelfReportService,
        )
        with app.app_context():
            try:
                summary = QuarterlySelfReportService().run_quarterly()
                logger.info(f"Quarterly self report scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Quarterly self report scheduler failed: {e}")

    def _scheduled_year_end_letter():
        """Annual (12/31) 10:00 KST — Premium 6-page Year-End Investor
        Letter (Buffett tone).

        Download-only surface — no share link. Empty-trade users are
        skipped inside `run_for_user`.
        """
        from services.artifacts.year_end_letter_service import (
            YearEndLetterService,
        )
        with app.app_context():
            try:
                summary = YearEndLetterService().run_annual()
                logger.info(f"Year-end letter scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Year-end letter scheduler failed: {e}")

    def _scheduled_dd_checklist():
        """Daily 08:00 KST — T+3 post-entry DD checklist email (Pro+).

        Idempotent via the one-row-per-position DDCheck UNIQUE constraint,
        so a second firing on the same day is a no-op for already-checked
        positions.
        """
        from services.artifacts.dd_checklist_service import DDChecklistService
        with app.app_context():
            try:
                summary = DDChecklistService().run_daily()
                logger.info(f"DD checklist scheduler run: {summary}")
            except Exception as e:
                logger.error(f"DD checklist scheduler failed: {e}")

    def _scheduled_burn_rate():
        """Monthly (day=1) 09:00 KST — Burn Rate Report PDF (Pro+).

        Calls `run_monthly(target_month=date.today())` which resolves the
        *previous* calendar month via `_prev_month_bounds`. Empty-trade
        users are skipped inside `run_for_user`.
        """
        from services.artifacts.burn_rate_service import BurnRateService
        with app.app_context():
            try:
                summary = BurnRateService().run_monthly()
                logger.info(f"Burn rate scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Burn rate scheduler failed: {e}")

    def _scheduled_credit_rating():
        """Monthly (day=15) 09:00 KST — Credit Rating email (Pro+).

        Empty portfolios are skipped. Per-user failures never block the
        rest — see `CreditRatingService.run_monthly`.
        """
        from services.artifacts.credit_rating_service import CreditRatingService
        with app.app_context():
            try:
                summary = CreditRatingService().run_monthly()
                logger.info(f"Credit rating scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Credit rating scheduler failed: {e}")

    def _scheduled_dividend_income():
        """Monthly (day=1) 10:00 KST — Dividend Income Statement PDF (Premium).

        Resolves the *prior* calendar month internally via `_prev_month`.
        Empty-portfolio users are skipped inside `run_for_user`.
        """
        from services.artifacts.dividend_income_service import (
            DividendIncomeService,
        )
        with app.app_context():
            try:
                summary = DividendIncomeService().run_monthly()
                logger.info(f"Dividend income scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Dividend income scheduler failed: {e}")

    def _scheduled_monthly_finance():
        """Monthly (day=1) 11:00 KST — Monthly Finance Report PDF (Premium).

        Cash Runway + Cost/Tax Ledger + Watch Items combined. Scheduled
        1h after the Dividend Statement to avoid resource contention on
        the shared FMP budget. Empty book + zero cash users are skipped.
        """
        from services.artifacts.monthly_finance_service import (
            MonthlyFinanceService,
        )
        with app.app_context():
            try:
                summary = MonthlyFinanceService().run_monthly()
                logger.info(f"Monthly finance scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Monthly finance scheduler failed: {e}")

    def _scheduled_risk_board_monthly():
        """Monthly (day=15) 09:30 KST — Risk Board Meeting Deck (Premium).

        Regular monthly edition — service runs over every Premium user
        with at least one position. Empty portfolios are skipped; per-user
        failures never block the rest. The event-driven VIX spike
        edition is fired by `_scheduled_vix_spike_monitor` below.
        """
        from services.artifacts.risk_board_service import RiskBoardService
        with app.app_context():
            try:
                summary = RiskBoardService().run_monthly()
                logger.info(f"Risk board monthly scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Risk board monthly scheduler failed: {e}")

    def _scheduled_vix_spike_monitor():
        """Hourly (minute=30) — fire the Risk Board deck when VIX first
        crosses above 25.

        The service stores the last observed VIX in a tiny on-disk JSON
        state file so a restart in the middle of a spike episode doesn't
        re-notify. When VIX is already elevated this call is a cheap
        no-op.
        """
        from services.artifacts.risk_board_service import RiskBoardService
        with app.app_context():
            try:
                result = RiskBoardService().run_vix_spike_check()
                logger.info(f"Risk board VIX spike monitor: {result}")
            except Exception as e:
                logger.error(f"Risk board VIX spike monitor failed: {e}")

    def _scheduled_portfolio_segment():
        """Quarterly (month=1,4,7,10 day=7) 10:00 KST — Portfolio Segment
        Report PDF (Premium).

        Fires 7 days into each quarter to audit the one that just closed —
        mirrors the Self Audit cadence so both reports land in the same
        post-quarter window. Empty portfolios are skipped.
        """
        from services.artifacts.portfolio_segment_service import (
            PortfolioSegmentService,
        )
        with app.app_context():
            try:
                summary = PortfolioSegmentService().run_quarterly()
                logger.info(f"Portfolio segment scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Portfolio segment scheduler failed: {e}")

    def _scheduled_capital_allocation_reminder():
        """Quarterly +14 days (1/14, 4/14, 7/14, 10/14) 09:00 KST.

        Sends an **email reminder only** — nudges Premium users to revisit
        the on-demand What-If Capital Allocation Calculator. No calculation
        is performed on the server. This decoupling is deliberate: we never
        push allocation suggestions; the user must opt into the calculator.
        """
        from services.artifacts.capital_allocation_service import (
            CapitalAllocationService,
        )
        with app.app_context():
            try:
                summary = CapitalAllocationService().send_quarterly_reminder()
                logger.info(f"Capital allocation reminder run: {summary}")
            except Exception as e:
                logger.error(f"Capital allocation reminder failed: {e}")

    def _scheduled_insider_mirror_weekly():
        """Weekly (Mon) 09:00 KST — Insider Transaction Mirror PDF (Premium).

        Aggregates SEC Form 4 (US) and DART 임원·주요주주 공시 (KR, optional)
        for each Premium user's tracked tickers. Factual event feed only —
        no signals, no hit-rate analytics. Empty portfolios are skipped.
        When DART_API_KEY is unset the KR section collapses silently.
        """
        from services.artifacts.insider_mirror_service import (
            InsiderMirrorService,
        )
        with app.app_context():
            try:
                summary = InsiderMirrorService().run_weekly()
                logger.info(f"Insider mirror weekly run: {summary}")
            except Exception as e:
                logger.error(f"Insider mirror weekly failed: {e}")

    # ── Feature 5 — AI Trader Twin (paper-only) ─────────────────────────
    # Twin runs daily decision passes and a Sunday weekly comparison.
    # Every job operates on initialized twins only — uninitialized users
    # get a no-op pass so the cron never grows broker-style state.
    def _scheduled_twin_decisions_kr():
        """Run Twin decisions after KOSPI/KOSDAQ close (16:30 KST).

        Iterates every active AITwinPortfolio and invokes
        ``run_twin_decisions``. Per-user failures never block the rest.
        """
        from models import AITwinPortfolio
        from services.twin import run_twin_decisions
        with app.app_context():
            try:
                # CONN-001: materialise the active user-ids then release the
                # connection before the per-twin analyse loop. Each
                # run_twin_decisions() call hits FMP/KIS (engine.analyze) for
                # seconds and manages its own short session internally — we
                # must not pin the list-query connection across that loop.
                uids = [int(uid) for (uid,) in
                        AITwinPortfolio.query
                        .filter_by(is_active=True)
                        .with_entities(AITwinPortfolio.user_id).all()]
                db.session.remove()
                for uid in uids:
                    try:
                        run_twin_decisions(uid)
                    except Exception as e:
                        logger.error(f"Twin KR decisions failed user={uid}: {e}")
                    finally:
                        db.session.remove()
                logger.info(f"Twin KR daily run: {len(uids)} twins scanned")
            except Exception as e:
                logger.error(f"Twin KR scheduler failed: {e}")

    def _scheduled_twin_decisions_us():
        """Run Twin decisions after the NYSE close (06:30 KST = 21:30 EST)."""
        from models import AITwinPortfolio
        from services.twin import run_twin_decisions
        with app.app_context():
            try:
                # CONN-001: see _scheduled_twin_decisions_kr — release the
                # connection before the slow per-twin analyse loop.
                uids = [int(uid) for (uid,) in
                        AITwinPortfolio.query
                        .filter_by(is_active=True)
                        .with_entities(AITwinPortfolio.user_id).all()]
                db.session.remove()
                for uid in uids:
                    try:
                        run_twin_decisions(uid)
                    except Exception as e:
                        logger.error(f"Twin US decisions failed user={uid}: {e}")
                    finally:
                        db.session.remove()
                logger.info(f"Twin US daily run: {len(uids)} twins scanned")
            except Exception as e:
                logger.error(f"Twin US scheduler failed: {e}")

    def _scheduled_twin_weekly():
        """Sunday 21:00 KST — user-vs-twin weekly comparison row."""
        from models import AITwinPortfolio
        from services.twin import generate_weekly_report
        with app.app_context():
            try:
                # CONN-001: release the connection before the per-twin report
                # loop; generate_weekly_report manages its own session.
                uids = [int(uid) for (uid,) in
                        AITwinPortfolio.query
                        .filter_by(is_active=True)
                        .with_entities(AITwinPortfolio.user_id).all()]
                db.session.remove()
                for uid in uids:
                    try:
                        generate_weekly_report(uid)
                    except Exception as e:
                        logger.error(f"Twin weekly report failed user={uid}: {e}")
                    finally:
                        db.session.remove()
                logger.info(f"Twin weekly run: {len(uids)} twins reported")
            except Exception as e:
                logger.error(f"Twin weekly scheduler failed: {e}")

    def _scheduled_earnings_prebrief():
        """Scan every 15 min for positions whose earnings fire in ~30 min.

        2026-05-01 redesign — switched from per-ticker `run_scan` to
        user-grouped `run_scan_digest`: one consolidated email per user
        listing all matched tickers (CEO 평: '종목 하나당 이메일 하나
        ㅈㄴ많아 — 하나에 모든 종목이 오게끔'). Daily dedup at user
        level so even if scan fires multiple times in a day, each user
        receives at most one digest per UTC day. Per-ticker Artifact
        rows still persist for archive/download surfaces.
        """
        from services.artifacts.earnings_prebrief_service import (
            EarningsPrebriefService,
        )
        with app.app_context():
            try:
                summary = EarningsPrebriefService().run_scan_digest()
                logger.info(f"Earnings pre-brief digest scan: {summary}")
            except Exception as e:
                logger.error(f"Earnings pre-brief scan failed: {e}")

    def _scheduled_behavioral_scores():
        """Weekly Sunday 22:00 KST — BehavioralScore for every active user.

        Backs Feature 7 (Weekly Behavioural Score). Scheduled 1h before
        the 23:00 PersonaSnapshot cron so the score's persona-comparison
        block reads against the *previous* snapshot — purely
        observational, no directive language. Per-user failures never
        block the rest; the scorer's UNIQUE(user_id, week_ending)
        constraint keeps a manual re-trigger idempotent.
        """
        from services.behavior import run_weekly_for_all_users
        with app.app_context():
            try:
                summary = run_weekly_for_all_users()
                logger.info(f"Behavioural score weekly run: {summary}")
            except Exception as e:
                logger.error(f"Behavioural score weekly failed: {e}")

    def _scheduled_persona_snapshots():
        """Weekly Sunday 23:00 KST — PersonaSnapshot for every active user.

        Backs Feature 3+4 (Evolution Timeline). Active = at least one
        TradeHistory row in the last 90 days (the User model has no
        ``last_login`` column so trade activity is the engagement proxy).

        Scheduled to fire 21h *after* the Sunday 02:00 KST
        ``compute_group_stats`` job so snapshots are computed against
        the freshly-updated PersonaGroupStats. Per-user failures never
        block the rest — see ``run_weekly_snapshots``. Idempotent: the
        UNIQUE(user_id, computed_at) constraint silently skips a second
        firing within the same second (e.g. cron coalesce + manual
        ``/api/profile/persona-snapshot`` POST).
        """
        from services.profile import run_weekly_snapshots
        with app.app_context():
            try:
                summary = run_weekly_snapshots()
                logger.info(f"Persona snapshot weekly run: {summary}")
            except Exception as e:
                logger.error(f"Persona snapshot weekly failed: {e}")

    # PERF-001 / CONN-001: apply pile-up guards as scheduler-wide job defaults
    # so EVERY job — the artifact crons below AND the Wave H ops jobs
    # registered via register_cron_jobs — inherits them consistently:
    #   • coalesce=True       → collapse a backlog of missed runs into ONE.
    #   • max_instances=1     → never run two copies of the same job at once.
    #   • misfire_grace_time  → 60s window to still fire a delayed run; beyond
    #     that the run is dropped (with coalesce, a whole minute of dropped
    #     per-minute ticks collapses to a single catch-up fire instead of a
    #     30-deep pile-up on the threadpool when the scheduler thread is
    #     briefly blocked by a slow job or GC pause).
    # Per-job kwargs below still pass coalesce/max_instances explicitly for
    # readability; these defaults are the safety net (and supply the missing
    # misfire_grace_time the per-job calls never set).
    sched = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 60,
        },
    )
    # PERF-001: cap concurrent runs and coalesce missed runs so a slow refresh
    # cannot stack up identical jobs on the scheduler thread pool.
    sched.add_job(
        _scheduled_refresh,
        "interval",
        minutes=3,
        id="refresh",
        max_instances=1,
        coalesce=True,
    )
    # Sunday 08:00 KST — 주간 맥킨지 스타일 PDF 메모 (Pro+).
    sched.add_job(
        _scheduled_weekly_memo,
        trigger="cron",
        day_of_week="sun",
        hour=8, minute=0,
        timezone="Asia/Seoul",
        id="weekly_memo_sunday",
        max_instances=1,
        coalesce=True,
    )
    # 매월 1일 09:00 KST — MVP #2 Monthly Brag Card (9:16 PNG, 전 유저).
    sched.add_job(
        _scheduled_brag_card,
        trigger="cron",
        day=1, hour=9, minute=0,
        timezone="Asia/Seoul",
        id="brag_card_monthly",
        max_instances=1,
        coalesce=True,
    )
    # ── RE-ENABLED (2026-05-01): digest mode ──────────────────────────────
    # Was disabled to stop per-ticker email spam (5 holdings → 5 emails).
    # Now switched to `run_scan_digest` — one consolidated email per
    # user with all matched tickers as cards. Daily dedup at user level
    # so the 15-min scan cadence doesn't double-send.
    sched.add_job(
        _scheduled_earnings_prebrief,
        trigger="interval",
        minutes=15,
        id="earnings_prebrief_digest_scan",
        max_instances=1,
        coalesce=True,
    )
    # ── DISABLED (2026-04-19): KPI Dashboard → Morning Brief Plus 통합 ──
    # 5-메트릭 KPI 카드는 이제 06:00 KST Morning Brief 이메일 상단에 포함된다.
    # 스케줄러 job은 제거됐지만 `_scheduled_kpi_dashboard` 함수 + 서비스 +
    # `/api/artifacts/kpi-dashboard/preview` 엔드포인트 + `/kpi-dashboard/trigger`
    # 는 관리자 디버그용으로 그대로 남아있다. 중복 daily 이메일 제거가 목적.
    #
    # sched.add_job(
    #     _scheduled_kpi_dashboard,
    #     trigger="cron",
    #     hour=8, minute=0,
    #     timezone="Asia/Seoul",
    #     id="kpi_dashboard_daily",
    #     max_instances=1,
    #     coalesce=True,
    # )
    # ── DISABLED (2026-04-19): Self Audit → Quarterly Self Report 흡수 ──
    # 기존 Self Audit (4p, 08:00 KST) job 은 Quarterly Self Report (15p,
    # 10:00 KST) Part 2 로 완전히 흡수되었다. SelfAuditService 는 여전히
    # import 가능하며 Quarterly Self Report 내부에서 호출되기 때문에
    # 로직/함수/엔드포인트(/api/artifacts/self-audit/*)는 남겨두되,
    # 분기 cron 은 중복 이메일 방지를 위해 제거한다.
    #
    # sched.add_job(
    #     _scheduled_self_audit,
    #     trigger="cron",
    #     month="1,4,7,10",
    #     day=7,
    #     hour=8, minute=0,
    #     timezone="Asia/Seoul",
    #     id="self_audit_quarterly",
    #     max_instances=1,
    #     coalesce=True,
    # )
    # 분기 +7일 (1/7, 4/7, 7/7, 10/7) 10:00 KST — Quarterly Self Report
    # (Premium, 5-page Premium v3 redesign · Self 10-K + Thesis Reality Check).
    # Self Audit 의 기능을 Part 2 로 흡수. portfolio_segment_quarterly 와 같은
    # 10:00 슬롯이지만 서비스가 독립적으로 User 쿼리/FMP 호출을 분산해 수행하므로 충돌 없음.
    # 2026-04-30: v3 변환 + _to_v3_shape() 데이터 매핑 완료. fake-data leak (sharpe_series,
    # holding_hist, spark hardcoded array) 박멸. persona 분기 보존
    # (test_persona_pdf_branch.py 49/49 통과). 재활성화.
    sched.add_job(
        _scheduled_quarterly_self_report,
        trigger="cron",
        month="1,4,7,10",
        day=7,
        hour=10, minute=0,
        timezone="Asia/Seoul",
        id="quarterly_self_report",
        max_instances=1,
        coalesce=True,
    )
    # 매년 12/31 10:00 KST — Year-End Investor Letter (Premium, 4p v3 PDF).
    # 연간 Buffett 톤 회고 서한. Download-only — share 링크 없음.
    # 2026-04-30: v3 4-page Premium 변환 + _to_v3_shape() 데이터 매핑 완료. 옛
    # template default array leak (sparkline_pts hardcoded) 박멸. 재활성화.
    sched.add_job(
        _scheduled_year_end_letter,
        trigger="cron",
        month=12, day=31,
        hour=10, minute=0,
        timezone="Asia/Seoul",
        id="year_end_letter_annual",
        max_instances=1,
        coalesce=True,
    )
    # 매일 08:05 KST — DD Checklist T+3 self-review 이메일 (Pro+).
    # 2026-04-30: v3 2-page Pro 변환 + semantic 변경 (single-ticker IC pack →
    # multi-position T+3 self-review prompt) 완료. service _to_v3_shape() 데이터
    # 매핑 정상. 옛 fake-data leak surface (quarterly_revenue/fcf_history/
    # peer_bars hardcoded array) 제거됨. 재활성화.
    sched.add_job(
        _scheduled_dd_checklist,
        trigger="cron",
        hour=8, minute=5,
        timezone="Asia/Seoul",
        id="dd_checklist_daily",
        max_instances=1,
        coalesce=True,
    )
    # 매월 1일 09:00 KST — Burn Rate Report PDF (Pro+). 전월 거래 집계.
    # 2026-04-30: v3 변환 + _to_v3_shape() 데이터 매핑 완료. fake-data leak
    # 박멸. 재활성화.
    sched.add_job(
        _scheduled_burn_rate,
        trigger="cron",
        day=1,
        hour=9, minute=0,
        timezone="Asia/Seoul",
        id="burn_rate_monthly",
        max_instances=1,
        coalesce=True,
    )
    # 매월 15일 09:00 KST — Credit Rating Self-Assessment 이메일 (Pro+).
    sched.add_job(
        _scheduled_credit_rating,
        trigger="cron",
        day=15,
        hour=9, minute=0,
        timezone="Asia/Seoul",
        id="credit_rating_monthly",
        max_instances=1,
        coalesce=True,
    )
    # 매월 1일 10:00 KST — Dividend Income Statement PDF (Premium).
    sched.add_job(
        _scheduled_dividend_income,
        trigger="cron",
        day=1,
        hour=10, minute=0,
        timezone="Asia/Seoul",
        id="dividend_income_monthly",
        max_instances=1,
        coalesce=True,
    )
    # 매월 1일 11:00 KST — Monthly Finance Report PDF (Premium).
    # 2026-04-30: v3 변환 + _to_v3_shape() 데이터 매핑 완료. fake-data
    # leak 박멸. 재활성화.
    sched.add_job(
        _scheduled_monthly_finance,
        trigger="cron",
        day=1,
        hour=11, minute=0,
        timezone="Asia/Seoul",
        id="monthly_finance_monthly",
        max_instances=1,
        coalesce=True,
    )
    # 매월 15일 09:30 KST — Risk Board Meeting Deck (Premium) 월간 에디션.
    sched.add_job(
        _scheduled_risk_board_monthly,
        trigger="cron",
        day=15, hour=9, minute=30,
        timezone="Asia/Seoul",
        id="risk_board_monthly",
        max_instances=1,
        coalesce=True,
    )
    # 매시 30분 — VIX 임계값 (>25) 신규 돌파 감지, Premium 전 유저 이벤트
    # 에디션 발송. 이미 임계값 위에 머물러 있는 구간은 no-op.
    sched.add_job(
        _scheduled_vix_spike_monitor,
        trigger="cron",
        minute=30,
        timezone="Asia/Seoul",
        id="vix_spike_monitor",
        max_instances=1,
        coalesce=True,
    )
    # 분기 +7일 (1/7, 4/7, 7/7, 10/7) 10:00 KST — Portfolio Segment Report (Premium).
    sched.add_job(
        _scheduled_portfolio_segment,
        trigger="cron",
        month="1,4,7,10",
        day=7,
        hour=10, minute=0,
        timezone="Asia/Seoul",
        id="portfolio_segment_quarterly",
        max_instances=1,
        coalesce=True,
    )
    # 분기 +14일 (1/14, 4/14, 7/14, 10/14) 09:00 KST — Capital Allocation
    # What-If Calculator 이메일 리마인더 (Premium). 서버 계산은 하지 않는다.
    sched.add_job(
        _scheduled_capital_allocation_reminder,
        trigger="cron",
        month="1,4,7,10",
        day=14,
        hour=9, minute=0,
        timezone="Asia/Seoul",
        id="capital_allocation_quarterly_reminder",
        max_instances=1,
        coalesce=True,
    )
    # 매주 월요일 09:00 KST — Insider Transaction Mirror 주간 PDF (Premium).
    # SEC Form 4 + DART 공시 이벤트 피드. 사실 기록만, 해석 없음.
    sched.add_job(
        _scheduled_insider_mirror_weekly,
        trigger="cron",
        day_of_week="mon",
        hour=9, minute=0,
        timezone="Asia/Seoul",
        id="insider_mirror_weekly",
        max_instances=1,
        coalesce=True,
    )
    # USD/KRW FX rate — refresh every 1 minute via FMP (primary) and
    # exchangerate-api.com (backup). 1440 upstream calls/day is well within
    # FMP Starter plan per-minute limits and free tier of exchangerate-api.
    # Logs a WARNING when stale > 10min.
    sched.add_job(
        func=lambda: fx_service._refresh_fx_rate(app),
        trigger="interval",
        minutes=1,
        id="fx_rate_refresh",
        max_instances=1,
        coalesce=True,
    )
    # Headline-index cache warm — keeps routes.market._indices_cache fresh
    # for the public (no-auth) /api/public/market-snapshot landing ticker,
    # independent of authenticated /market traffic. Mirrors the FX job
    # above: short fixed interval, TTL-gated inside warm_indices_cache so
    # it only hits KIS/Alpaca often during market hours. `next_run_time`
    # fires the first warm ~immediately after scheduler start (boot-time
    # warm), minimising the post-deploy cold window.
    from datetime import datetime as _dt_now, timezone as _tz
    sched.add_job(
        _scheduled_indices_cache_warm,
        trigger="interval",
        minutes=1,
        id="indices_cache_warm",
        next_run_time=_dt_now.now(_tz.utc),
        max_instances=1,
        coalesce=True,
    )
    # 매주 일요일 22:00 KST — BehavioralScore 주간 점수 (Feature 7).
    # PersonaSnapshot 23:00 보다 1시간 먼저 실행해 점수의 persona-comparison
    # 블록이 *직전* 스냅샷을 읽도록 한다. 회고적 관찰 점수만 기록하며
    # 권유 언어는 forbidden_terms 필터로 차단한다.
    sched.add_job(
        _scheduled_behavioral_scores,
        trigger="cron",
        day_of_week="sun", hour=22, minute=0,
        timezone="Asia/Seoul",
        id="behavioral_score_weekly",
        max_instances=1,
        coalesce=True,
    )
    # ── Feature 5 — AI Trader Twin (paper-only) ─────────────────────────
    # 매일 16:30 KST — KOSPI/KOSDAQ 마감 직후 Twin paper 의사결정.
    sched.add_job(
        _scheduled_twin_decisions_kr,
        trigger="cron",
        hour=16, minute=30,
        timezone="Asia/Seoul",
        id="twin_kr_daily",
        max_instances=1,
        coalesce=True,
    )
    # 매일 06:30 KST — NYSE 마감 후 (≈21:30 EST 전일) Twin paper 의사결정.
    sched.add_job(
        _scheduled_twin_decisions_us,
        trigger="cron",
        hour=6, minute=30,
        timezone="Asia/Seoul",
        id="twin_us_daily",
        max_instances=1,
        coalesce=True,
    )
    # 매주 일요일 21:00 KST — Twin 주간 비교 리포트 생성. 22:00 KST의
    # Behavioural Score (Feature 7) cron 보다 1시간 먼저 돌려, score 가 최신
    # 비교 데이터를 참고할 수 있도록 의도적으로 분리한다.
    sched.add_job(
        _scheduled_twin_weekly,
        trigger="cron",
        day_of_week="sun", hour=21, minute=0,
        timezone="Asia/Seoul",
        id="twin_weekly_report",
        max_instances=1,
        coalesce=True,
    )
    # 매주 일요일 23:00 KST — PersonaSnapshot 영속화 (Feature 3+4).
    # 같은 일요일 02:00 KST 의 ``compute_group_stats`` cron 이후에 실행되도록
    # 21시간 뒤로 배치. PersonaGroupStats 가 최신 스냅샷에 반영된 상태에서
    # 각 active 유저의 행동 페르소나를 기록한다.
    sched.add_job(
        _scheduled_persona_snapshots,
        trigger="cron",
        day_of_week="sun", hour=23, minute=0,
        timezone="Asia/Seoul",
        id="persona_snapshot_weekly",
        max_instances=1,
        coalesce=True,
    )

    # ── Wave H (2026-05-19) — macOS crontab → Railway ingestion ────────────
    # 19 ops jobs (api-health / db-backup / signup-funnel / error-rate /
    # checkout-followup / ...) previously lived in ``crontab -l`` on the CEO's
    # MacBook — single point of failure (노트북 꺼지면 멈춤).  Now registered
    # in-process so Railway's always-on web worker keeps them firing.
    # Cost: $0 (no extra Railway process; gunicorn --workers 1 prevents dupe).
    # See services/scheduler/cron_jobs.py for full job table + design notes.
    try:
        from services.scheduler import register_cron_jobs
        ops_ids = register_cron_jobs(sched, app)
        logger.info("Wave H — %d ops cron jobs registered: %s",
                    len(ops_ids), ops_ids)
    except Exception:
        # Wave H registration must never block the artifact-cron scheduler
        # boot.  If ops jobs fail to load (import error, missing script,
        # etc.) we keep the existing weekly_memo / brag_card / fx_rate jobs
        # alive — they're the user-facing scheduled work.
        logger.exception("Wave H ops cron registration failed — continuing")

    # ── Diagnostic — 2026-04-28 ────────────────────────────────────────────
    # Logs worker PID + every registered job's `next_run_time` (already
    # converted to the job's own timezone by APScheduler) at scheduler-start
    # time. Useful for confirming cron registration in Railway logs.
    # NOT a fix — instrumentation only.
    try:
        # APScheduler 4.x: Job 객체에 next_run_time 속성 없음. trigger 정보로 fallback.
        job_summary = [
            (j.id, getattr(j, "next_run_time", None) or
                   getattr(getattr(j, "trigger", None), "__class__", type(None)).__name__)
            for j in sched.get_jobs()
        ]
        logger.info(
            "scheduler.start pid=%s jobs=%s",
            os.getpid(),
            [(jid, str(t)) for jid, t in job_summary],
        )
    except Exception:
        logger.exception("scheduler.start diagnostic logging failed")

    # ── CONN-001 (2026-05-20): deploy-overlap single-scheduler guard ─────────
    # During a Railway deploy the OLD and NEW containers run simultaneously
    # for a few minutes. Both have RUN_SCHEDULER=1, so BOTH spin up this
    # scheduler → every per-minute job (indices_cache_warm, fx_rate_refresh)
    # fires twice, and the symptom in the logs was the same job appearing
    # ~30x within a single minute during a rolling restart. coalesce /
    # max_instances cannot help here — they are per-process. A PG session
    # advisory lock is the right primitive: only the process that wins the
    # lock starts its jobs; the loser registers nothing. The lock is held on
    # a DEDICATED long-lived connection (NOT a pooled one — a pooled
    # connection would return to the pool and release the lock) and is auto-
    # released by PostgreSQL the instant that process disconnects, so when the
    # old container is torn down the new one's NEXT boot wins cleanly.
    #
    # Fail-SAFE: any error (SQLite local dev, lock helper failure) falls back
    # to starting the scheduler unconditionally — losing crons entirely is far
    # worse than a few minutes of deploy-overlap duplication.
    if _try_acquire_scheduler_lock():
        sched.start()
        logger.info("scheduler started (advisory lock held) pid=%s", os.getpid())
    else:
        logger.warning(
            "scheduler NOT started pid=%s — another process holds the "
            "scheduler advisory lock (deploy overlap). Jobs registered but "
            "idle in this process.", os.getpid(),
        )


# ── Create app instance ───────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5050, host="0.0.0.0", use_reloader=False)
