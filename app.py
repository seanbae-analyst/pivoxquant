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

from services import fx_service, cache_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Sentry filter ─────────────────────────────────────────────────────────────

# Sensitive header names (lowercased) — must NEVER reach Sentry/logs.
# Broker headers (appkey/appsecret) were added after the Wave 1 KIS OAuth work
# introduced the (since removed, 2026-08-30) user KIS auth headers, which embedded
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


# ── PIPA §22 ⑥ — age-verification gate (defense-in-depth) ───────────────────
#
# An OAuth signup is only *provisioned* (``login_user``) so the frontend can
# POST the birthdate via ``/api/auth/oauth-finalize``. Until that column is
# set we must NOT let the authenticated session reach any data / feature
# endpoint — otherwise a direct API caller (curl) bypasses the browser
# interstitial and uses the product (and can flip ``onboarding_completed``)
# without ever confirming they are 14+.
#
# We gate only ``/api/*`` (rendered HTML / OAuth redirect HTML is not a data
# surface). A tight whitelist keeps the very routes that LET a user reach a
# set birthdate (or escape the half-provisioned state) open — dropping any
# of these would lock every fresh OAuth user out entirely:
#   - oauth-finalize: the ONLY route that writes birthdate.
#   - me: how the frontend learns ``birthdate_required=True`` → redirect to
#         the ``/signup/oauth-finalize`` interstitial.
#   - logout / logout alias: must be able to abandon the session.
#   - google|kakao callbacks: complete the OAuth handshake itself.
#   - delete-account / delete-request: PIPA §36 (삭제권) cannot be blocked by
#         a missing birthdate.
#   - health: liveness probe, no user data.
# CSRF tokens ride on every response cookie (security._set_security_headers)
# so no separate csrf-token endpoint exists to whitelist.
BIRTHDATE_GATE_WHITELIST = frozenset({
    "/api/auth/oauth-finalize",
    "/api/auth/me",
    "/api/auth/logout",
    "/api/logout",
    "/api/auth/google/callback",
    "/api/auth/kakao/callback",
    "/api/auth/delete-account",
    "/api/auth/delete-request",
    "/api/health",
})


def birthdate_gate_blocks(path, is_authenticated, birthdate):
    """Return True iff this request must be 403'd for a missing birthdate.

    Pure predicate (no Flask globals) so it is directly unit-testable. The
    ``before_request`` hook in :func:`create_app` is a thin wrapper around it.
    """
    normalized = (path or "").rstrip("/") or "/"
    if not normalized.startswith("/api/"):
        return False
    if normalized in BIRTHDATE_GATE_WHITELIST:
        return False
    if not is_authenticated:
        # api_auth / public endpoints handle the unauthenticated case.
        return False
    return birthdate is None


# ── App factory ───────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # JSON safety net: coerce non-finite floats (NaN/Inf/-Inf) → null at the
    # serialisation boundary. Python's json emits the bare tokens `NaN`/
    # `Infinity`, which are invalid JSON and make the browser's response.json()
    # throw — losing the *entire* payload (silent blank/error card despite a
    # 200). Routes guard ad-hoc with `_finite_floats`, but that is opt-in and
    # most modules skip it; this makes a missed guard unable to ship a
    # non-parseable body. See services/json_provider.py.
    from services.json_provider import SafeJSONProvider

    app.json = SafeJSONProvider(app)

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
        # Wave I C-2 — PIPA §21 soft-delete session invalidation.
        # routes/auth.py login() + google/kakao callbacks reject users with
        # deletion_requested_at != NULL at authentication time, but a
        # remember_token cookie issued *before* the delete-request would
        # otherwise silently re-authenticate the same user on every request
        # (load_user runs per request) — bypassing the login-time block and
        # granting full 200 access to /api/auth/me and every data API.
        # Returning None here invalidates the session so the soft-delete is
        # enforced consistently across all entry points. Cancellation is a
        # manual "contact support" flow (no self-service /delete-cancel), so
        # logging the user out everywhere is the correct, consistent behaviour.
        try:
            user = db.session.get(User, int(uid))
        except (TypeError, ValueError):
            return None
        if user is not None and user.deletion_requested_at is not None:
            return None
        return user

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
            # API clients expect JSON, not Flask's default HTML error page.
            # Without this, a 404 (wrong URL) or 405 (wrong method) under /api/
            # returns text/html → frontend fetch().json() throws SyntaxError and
            # the real status is lost. 5xx already gets JSON below; mirror it for
            # 4xx HTTPExceptions on API routes. (429 has its own handler and
            # never reaches here.)
            if request.path.startswith("/api/"):
                return (
                    jsonify({
                        "error": exc.description or exc.name,
                        "code": f"HTTP_{exc.code}",
                    }),
                    exc.code or 500,
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

    @app.before_request
    def _require_birthdate():
        from flask_login import current_user
        if birthdate_gate_blocks(
            request.path,
            bool(getattr(current_user, "is_authenticated", False)),
            getattr(current_user, "birthdate", None),
        ):
            return jsonify({
                "error":    "Birthdate confirmation required.",
                "error_kr": "생년월일 확인이 필요합니다.",
                "code":     "BIRTHDATE_REQUIRED",
            }), 403

    # Public OG / social-share images intentionally set a long, cacheable
    # Every response gets no-store. There was a narrow allowlist here that
    # preserved `public, max-age=...` on the artefact share-image paths so
    # crawlers could cache unfurl previews. Those routes were removed with
    # services/artifacts on 2026-08-30, so the allowlist matched nothing —
    # and an exemption that matches nothing is a hole waiting for a future
    # path to fall into it.
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

    def _widen_column_to_text(table, column):
        """Idempotently widen an existing VARCHAR column to TEXT (PG only).

        Needed where a column that used to be ``String(500)`` now stores
        ``EncryptedText`` ciphertext — base64(AES-GCM) of multi-byte Korean
        text easily exceeds 500 chars and would overflow VARCHAR(500) on
        PostgreSQL. SQLite has no VARCHAR length enforcement, so this is a
        no-op there. Already-TEXT columns are skipped. Mirrors Alembic 048.
        """
        if not is_postgres:
            return
        try:
            col = {c["name"]: c for c in inspector.get_columns(table)}.get(column)
        except Exception:
            return
        if col is None:
            return  # absent → a fresh box adds/creates it as TEXT already
        if "TEXT" in str(col.get("type", "")).upper():
            return  # already wide
        try:
            with db.engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TEXT"
                ))
            logger.info("Migration: widened %s.%s to TEXT", table, column)
        except Exception as exc:
            logger.warning("Migration: widen %s.%s skipped: %s", table, column, exc)

    # Users table — full coverage of User model columns so any DB
    # (new PG instance, restored snapshot, legacy SQLite dev box) can
    # boot without ProgrammingError / OperationalError on SELECT.
    _add_column_if_missing("users", "available_capital", "FLOAT", default="0.0")
    _add_column_if_missing("users", "available_capital_krw", "FLOAT", default="0.0")
    # Wave F (2026-05-28) — i18n locale preference. Alembic 046_user_locale.
    # ⚠️ BLOCKER FIX: prod self-heal 미적용 시 OAuth callback에서 ORM은 새
    # 컬럼을 보지만 DB는 없어 UndefinedColumn → provisioning_failed 100%.
    # 메모리 [project_prod_schema_selfheal] 패턴 — alembic 런타임 미실행
    # prod에서 self-heal 가드 필수.
    # Bug #3 (bug-hunter 2026-05-28 + audit 2026-05-28): NOT NULL 의도는
    # line ~648에 있었지만 이 호출이 먼저 실행되어 NOT NULL 없이 컬럼이
    # 생성되고, 두 번째 호출은 _add_column_if_missing 의 "exists short-circuit"
    # 으로 스킵됨 (app.py:503-508 if column in existing: return). 결과 prod
    # locale 컬럼이 NOT NULL 없이 생성. 첫 호출부터 not_null=True 박아서
    # 의도 일치. 두 번째 호출은 idempotent (이미 존재 시 skip).
    _add_column_if_missing(
        "users", "locale", "VARCHAR(2)", default="'ko'", not_null=True,
    )
    _add_column_if_missing("users", "risk_profile", "VARCHAR(20)", default="'balanced'")
    _add_column_if_missing("users", "profile_changes_left", "INTEGER", default="3")
    _add_column_if_missing("users", "subscription_tier", "VARCHAR(32)", default="'free'")
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
    # Viral-loop attribution — inviter's code captured at signup. Nullable.
    # Migration 045_funnel_events; runtime guard covers boxes that boot
    # without Alembic (prod self-heal pattern).
    _add_column_if_missing("users", "referred_by", "VARCHAR(16)")
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
    # Wave F (2026-05-28) — i18n locale preference column (ko default).
    # Alembic migration 046_user_locale. ORM 매핑에 존재하므로 누락 시 모든
    # User SELECT 가 ProgrammingError → OAuth provisioning_failed.
    # NOT NULL DEFAULT 'ko' — 기존 모든 row 한국어로 backfill.
    _add_column_if_missing(
        "users", "locale", "VARCHAR(2)", default="'ko'", not_null=True,
    )

    # Positions table — full coverage of Position model columns.
    # thesis_* columns were added in commit c6644c2 (Thesis Tracker) but
    # _do_migrations() was never updated, causing ProgrammingError on
    # INSERT when Railway PostgreSQL does not have these columns.
    _add_column_if_missing("positions", "buy_fx_rate", "FLOAT", default="0.0")
    # thesis / thesis_reason are EncryptedText (ciphertext) → create as TEXT,
    # not VARCHAR(500); a long encrypted 매수 이유 overflows VARCHAR on PG.
    # Existing VARCHAR(500) boxes are widened by the pass at the end of this
    # function (Alembic 048 is the canonical equivalent).
    _add_column_if_missing("positions", "thesis", "TEXT")
    _add_column_if_missing("positions", "thesis_created_at", "TIMESTAMP")
    _add_column_if_missing("positions", "thesis_last_checked", "TIMESTAMP")
    _add_column_if_missing("positions", "thesis_status", "VARCHAR(20)", default="'pending'")
    _add_column_if_missing("positions", "thesis_reason", "TEXT")

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
    # Viral loop (migration 045) — public-visibility toggle for shared cards.
    # Default false so cards stay private until the owner opts in.
    _add_column_if_missing("artifacts", "is_public", "BOOLEAN", default="0")

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
    # Questionnaire V3 (2026-09-06, alembic 050) — the user's own onboarding
    # words + their projection onto the observed feature scale.
    _add_column_if_missing("investment_profiles", "questionnaire_version", "INTEGER")
    _add_column_if_missing("investment_profiles", "onboarding_answers_json", "TEXT")
    _add_column_if_missing("investment_profiles", "declared_vector_json", "TEXT")

    # User referrals — `invited_count` is the one post-create candidate.
    _add_column_if_missing("user_referrals", "invited_count", "INTEGER", default="0")

    # Watchlist — `note` is a free-text memo (2026-04-22), now EncryptedText.
    # Create as TEXT (ciphertext); existing VARCHAR(500) boxes widened below.
    _add_column_if_missing("watchlist", "note", "TEXT")

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
        _add_column_if_missing("position_dd_checks", "note",               "TEXT")  # EncryptedText

    # pre_trade_reflections.observed_context_json — record-as-spine Phase 2
    # (2026-06-10). Alembic twin: 049_reflection_observed_context. Snapshot of
    # the observation surfaces (signal label/score, VIX, 1h move) at the
    # moment the reflection was opened. Nullable TEXT — purely additive.
    _add_column_if_missing("pre_trade_reflections", "observed_context_json", "TEXT")

    # anthropic_usage_log (Wave I G-3) — Anthropic API 비용 추적 테이블.
    # 이 테이블은 ORM 모델이 아니라 services/ai/service.py 가 raw SQL INSERT
    # 로 직접 기록하므로 db.create_all() 범위 밖이다. 생성은 alembic
    # migration 042_anthropic_usage_log 에만 존재한다. prod 는 alembic 미실행
    # (db.create_all() + _do_migrations() self-heal 패턴) 으로 운영되므로
    # 이 가드가 없으면 테이블 부재 → _log_usage() 의 INSERT 가 silent 실패
    # (except: pass) → nightly anthropic_cost_estimate 집계가 무력화된다.
    # 스키마는 migration 042 와 정확히 일치 (컬럼명/타입). Postgres/SQLite 양쪽
    # 호환을 위해 created_at 은 TIMESTAMP, PK 는 단순 INTEGER PRIMARY KEY 로
    # 둔다 (SQLite 는 INTEGER PRIMARY KEY 가 자동 rowid autoincrement, PG 는
    # 본 fallback 경로에서 명시 INSERT 만 들어오므로 SERIAL 불필요).
    if "anthropic_usage_log" not in existing_tables:
        try:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS anthropic_usage_log ("
                    "id INTEGER PRIMARY KEY, "
                    "user_id INTEGER, "
                    "model VARCHAR(64) NOT NULL, "
                    "endpoint VARCHAR(64) NOT NULL, "
                    "input_tokens INTEGER NOT NULL DEFAULT 0, "
                    "output_tokens INTEGER NOT NULL DEFAULT 0, "
                    "created_at TIMESTAMP NOT NULL"
                    ")"
                ))
                # Indexes mirror migration 042 (user_id/model/endpoint/created_at
                # are all index=True). IF NOT EXISTS keeps it idempotent on both
                # engines.
                for col in ("user_id", "model", "endpoint", "created_at"):
                    conn.execute(text(
                        f"CREATE INDEX IF NOT EXISTS "
                        f"ix_anthropic_usage_log_{col} "
                        f"ON anthropic_usage_log ({col})"
                    ))
            logger.info("Migration: created table anthropic_usage_log")
        except Exception as exc:
            # Never block boot — nightly cost aggregation degrades gracefully.
            logger.warning(
                "Migration: could not create anthropic_usage_log: %s", exc
            )

    # funnel_events (viral loop, migration 045) — 0원 자체 퍼널 추적. ORM 모델
    # (models/funnel_event.py) 이라 db.create_all() 범위 안이지만, prod 는
    # alembic 미적용 self-heal 패턴이라 boot-time 가드를 둔다. ``POST /api/track``
    # 의 INSERT 가 테이블 부재로 silent 실패하면 K-factor/WAMR 집계가 무력화된다.
    if "funnel_events" not in existing_tables:
        try:
            from models.funnel_event import FunnelEvent  # noqa: F401
            db.metadata.tables["funnel_events"].create(bind=db.engine)
            logger.info("Migration: created table funnel_events")
        except Exception as exc:
            logger.warning("Migration: could not create funnel_events: %s", exc)

    # inquiries (고객문의센터, migration 044) — support tickets (contact form +
    # chatbot auto-escalation). ORM 모델(models/inquiry.py)이라 db.create_all()
    # 범위 안이지만, prod 는 alembic 미적용 self-heal 패턴이라 boot-time 가드를
    # 둔다. 테이블 부재 시 POST /api/support/inquiries / /chat 의 INSERT 가
    # ProgrammingError 로 500 → 문의 접수 전면 불가. 멱등 (테이블 존재 시 skip).
    if "inquiries" not in existing_tables:
        try:
            from models.inquiry import Inquiry  # noqa: F401
            db.metadata.tables["inquiries"].create(bind=db.engine)
            logger.info("Migration: created table inquiries")
        except Exception as exc:
            logger.warning("Migration: could not create inquiries: %s", exc)

    # ── Growth OS + agent_worker tables — REMOVED 2026-09-01 ────────────────
    # This block used to CREATE 7 model-less tables on every boot:
    #   growth_daily_logs · growth_reflections · growth_scores ·
    #   growth_weekly_reports · agent_tasks · agent_decisions · agent_budget
    #
    # Both consumers named in the original comments are gone from the tree:
    # `agent_worker/` (worker.py / budget.py / escalation.py / admin_routes.py)
    # and `growth_routes.py`. Measured 2026-09-01: zero references to any of
    # the seven table names anywhere outside app.py and the alembic history,
    # and zero /api/growth or /api/agent URL rules. The DDL was boot-time work
    # producing tables nothing ever read or wrote.
    #
    # Existing databases are UNAFFECTED — dropping the creation code does not
    # drop tables, so Supabase keeps the rows it already has. Only a fresh DB
    # stops being seeded with the seven.
    #
    # The alembic revisions that also create them (004_add_agent_tables and the
    # growth revisions) are deliberately untouched — revision history is never
    # deleted (see CLAUDE.md). If either surface returns, restore the DDL from
    # `git show 5c0187dc:app.py`.


    # Portfolio shares / push subscriptions / signal_cache / watchlist —
    # all their current columns are in the initial create_all snapshot.
    # No post-creation additions observed. Declared here as a no-op safety
    # net so future model additions auto-get a migration hook.

    # Widen subscription_tier (legacy VARCHAR(10) boxes) + backfill env-override
    # tiers (2026-05-26). Cron artifact fan-out queries `subscription_tier` at
    # the DB layer; `effective_tier` (DEV_FOUNDING_EMAILS / DEV_PREMIUM_EMAILS)
    # is a runtime property never materialised to the column, so owner/tester
    # override accounts (DB tier 'free') were silently excluded from every
    # scheduled artifact. Widen so 'founding_lifetime' (17 chars) fits, then
    # upgrade matching emails in the DB (upgrade-only — never downgrades a real
    # Stripe-paid tier; mirrors effective_tier's "highest wins" rule).
    try:
        if is_postgres:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE users ALTER COLUMN subscription_tier TYPE VARCHAR(32)"
                ))
        from models import User as _User

        def _env_emails(var):
            raw = os.environ.get(var, "") or ""
            return {e.strip().lower() for e in raw.split(",") if e.strip()}

        _TIER_RANK = {
            "free": 0, "pro": 1, "premium": 2, "premium_plus": 3, "founding_lifetime": 4,
        }
        _grants = [
            (_env_emails("DEV_FOUNDING_EMAILS"), "founding_lifetime"),
            (_env_emails("DEV_PREMIUM_EMAILS"), "premium"),
        ]
        _changed = 0
        for _emails, _tier in _grants:
            if not _emails:
                continue
            rows = _User.query.filter(
                db.func.lower(_User.email).in_(_emails)
            ).all()
            for _u in rows:
                if _TIER_RANK.get(_u.subscription_tier or "free", 0) < _TIER_RANK[_tier]:
                    _u.subscription_tier = _tier
                    _changed += 1
        if _changed:
            db.session.commit()
            logger.info("Backfilled subscription_tier for %d env-override users", _changed)
    except Exception:
        logger.debug("silent-fallback: env-tier backfill", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass

    # 2026-06-02 — EncryptedText rollout: widen columns that used to be
    # String(500) and now hold AES-GCM ciphertext. Existing PG boxes created
    # them as VARCHAR(500); _add_column_if_missing short-circuits on existing
    # columns, so widen them explicitly here. Fresh boxes already get TEXT.
    # Alembic 048 is the canonical migration; this is the alembic-less Railway
    # self-heal twin (prevents the v44.7 "migration not applied to prod" class).
    for _wt, _wc in (
        ("positions", "thesis"),
        ("positions", "thesis_reason"),
        ("watchlist", "note"),
        ("position_dd_checks", "note"),
        ("weekly_pulse", "worry"),
        ("weekly_pulse", "learn"),
    ):
        _widen_column_to_text(_wt, _wc)

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
                        # Was svc.engine.analyze() + save_signal; the engine is
                        # gone and cache_ticker fetches the same fields.
                        cache_service.cache_ticker(ticker)
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
    def _alert_sched(job_id: str, exc: BaseException) -> None:
        """T8 mechanical wrapper — emit_failure for ``_scheduled_*`` jobs.

        Defence-in-depth: the alerts module already swallows everything
        internally, but we wrap one more time so a missing module import
        (e.g. observability not yet deployed in a hotfix branch) still
        cannot kill the scheduler thread.
        """
        try:
            from services.observability.alerts import emit_failure
            emit_failure(job_id, exc)
        except Exception:
            logger.exception("[sched] emit_failure swallowed for %s", job_id)

    def _record_sched_success(job_id: str) -> None:
        """T8 — reset 3-strike counter on successful run."""
        try:
            from services.observability.alerts import record_success
            record_success(job_id)
        except Exception:
            pass

    def _scheduled_refresh():
        """Refresh the SignalCache metadata for every held ticker.

        2026-09-01: this used to run ``svc.engine.analyze()`` per ticker and
        hand the result to ``alert_service.maybe_generate``. The quant engine
        was deleted with the scoring surfaces, so every iteration raised into
        the per-ticker except and logged a failure — every three minutes,
        forever, with nothing refreshed.

        What the surviving Portfolio surface reads out of SignalCache is
        identity and price: name, price, price_display, currency, is_korean,
        sector. ``cache_service.cache_ticker`` fetches exactly that in one
        quote call, so the job now does that and nothing else.

        CONN-001 (2026-05-20) still applies: read the ticker list, release the
        pooled connection, then let each cache_ticker call take a short one of
        its own. Nothing holds a connection across an upstream request.
        """
        from models import Position
        with app.app_context():
            try:
                tickers = sorted({p.ticker for p in Position.query.all()})
                # Release the connection before any external API work.
                db.session.remove()

                for ticker in tickers:
                    try:
                        cache_service.cache_ticker(ticker)
                    except Exception as e:
                        logger.error(f"Scheduler refresh failed {ticker}: {e}")
                    finally:
                        db.session.remove()

                logger.info(f"Scheduled refresh done — {len(tickers)} tickers")
                _record_sched_success("sched_refresh")
            except Exception as e:
                logger.error(f"Scheduler refresh failed: {e}")
                _alert_sched("sched_refresh", e)

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
                from services.data.indices import warm_indices_cache
                us_n = warm_indices_cache("us")
                kr_n = warm_indices_cache("kr")
                logger.info(
                    "Indices cache-warm done — us=%s kr=%s rows", us_n, kr_n
                )
                _record_sched_success("sched_indices_cache_warm")
            except Exception as e:
                logger.error(f"Indices cache-warm scheduler failed: {e}")
                _alert_sched("sched_indices_cache_warm", e)

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

        Wrapped in try/except + emit_failure for parity with the other
        25 Group A jobs — even no-ops can raise on a future logger config
        change, and we want zero silent scheduler-thread kills.
        """
        try:
            logger.info(
                "self_audit standalone job is deprecated — "
                "see quarterly_self_report"
            )
        except Exception as exc:  # noqa: BLE001
            try:
                from services.observability.alerts import emit_failure
                emit_failure("sched_scheduled_self_audit", exc)
            except Exception:
                logger.exception("self_audit alert emit failed")

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
                _record_sched_success("sched_persona_snapshots")
            except Exception as e:
                logger.error(f"Persona snapshot weekly failed: {e}")
                _alert_sched("sched_persona_snapshots", e)

    def _scheduled_price_alerts():
        """Weekday post-US-close sweep — 52-week high/low + sector concentration.

        Both ``check_52w_highs_lows`` and ``check_concentration_alerts`` exist
        in ``services.alert`` but were never wired to a cron, so the in-app
        BELL alerts a user configured (52w touches, concentration) only ever
        fired via the admin ``POST /api/alerts/admin/check`` — i.e. never in
        practice. This wrapper drives both once per US trading day.

        Cadence is deliberately conservative: 06:35 KST (= 21:35 EST, just
        after the NYSE 16:00 ET close, at 06:30 KST).
        A single daily fire keeps FMP/KIS budget + PG pressure low — these
        checks fan out across every holder's tickers. US tickers price via FMP;
        KR (.KS/.KQ) tickers route through KIS (``w52_hgpr``/``w52_lwpr`` in
        kis_market_adapter.get_52w_range) since commit 3ba9564d — they are no
        longer skipped. ``create_alert`` already dedups via a 24h/7d window so a
        daily cadence cannot spam. Bell prefs routing is unchanged from every
        other bell alert (fail-open) — not wired here.

        Per-check failures are isolated; a bad 52w sweep must not block the
        concentration sweep, and neither must raise out of the scheduler.
        """
        from services.alert import (
            check_52w_highs_lows,
            check_concentration_alerts,
        )
        with app.app_context():
            # Two independent jobs — track success per-job. A shared ``ok`` flag
            # would let a concentration failure suppress the 52w success record
            # (and vice-versa), leaving a clean sweep's 3-strike counter un-reset.
            ok_52w = True
            try:
                m = check_52w_highs_lows()
                logger.info(f"52w high/low sweep: {m}")
            except Exception as e:
                ok_52w = False
                logger.error(f"52w high/low sweep failed: {e}")
                _alert_sched("sched_price_alerts_52w", e)
            ok_conc = True
            try:
                m = check_concentration_alerts()
                logger.info(f"Concentration sweep: {m}")
            except Exception as e:
                ok_conc = False
                logger.error(f"Concentration sweep failed: {e}")
                _alert_sched("sched_price_alerts_concentration", e)
            if ok_52w:
                _record_sched_success("sched_price_alerts_52w")
            if ok_conc:
                _record_sched_success("sched_price_alerts_concentration")

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
    # USD/KRW FX rate — refresh every 1 minute via FMP (primary) and
    # exchangerate-api.com (backup). 1440 upstream calls/day is well within
    # FMP Starter plan per-minute limits and free tier of exchangerate-api.
    # Logs a WARNING when stale > 10min.
    def _scheduled_fx_rate_refresh():
        try:
            fx_service._refresh_fx_rate(app)
            _record_sched_success("sched_fx_rate_refresh")
        except Exception as e:  # noqa: BLE001
            logger.error(f"FX rate refresh scheduler failed: {e}")
            _alert_sched("sched_fx_rate_refresh", e)

    sched.add_job(
        func=_scheduled_fx_rate_refresh,
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
    # behavioral_score_weekly 잡은 2026-05-30 "AI 점수화 폐기" 결정
    # (DECISIONS.md)에 따라 제거했다. 점수는 더 이상 계산되지 않으며
    # BehavioralScore 모델/스코어러는 dormant 보존한다.
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

    # 평일 06:35 KST (= 21:35 EST, NYSE 마감 직후) — 52주 고/저 + 섹터 집중도
    # 벨 알림 스윕. 두 check 함수는 services.alert 에 존재했으나 cron 미등록이라
    # 사용자가 설정한 52w 알림이 자동 발화되지 않았다(어드민 수동 POST 외 0회).
    # 하루 1회 보수적 cadence — FMP/KIS budget + PG 압박 회피. KR 티커는 KIS
    # (get_52w_range) 로 라우팅(커밋 3ba9564d, 더 이상 skip 아님), create_alert
    # 24h/7d dedup 로 스팸 방지.
    sched.add_job(
        _scheduled_price_alerts,
        trigger="cron",
        day_of_week="mon-fri",
        hour=6, minute=35,
        timezone="Asia/Seoul",
        id="price_alerts_daily",
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
