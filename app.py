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


# ── App factory ───────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Security middleware (CORS, Rate Limiting, CSRF, Session, Headers)
    init_security(app)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "index"

    # User loader
    from models import User, Position, SignalCache, TradeHistory

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

    @app.after_request
    def no_cache(r):
        r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        r.headers["Pragma"] = "no-cache"
        return r

    @app.route("/")
    def index():
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        return redirect(frontend_url)

    # Initialize services
    svc.init_trader(db, Position, TradeHistory, app)

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
    # scheduler, causing morning_brief / refresh jobs to fire N times).
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

    def _add_column_if_missing(table, column, col_type, default=None, unique=False):
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

    # Artifacts table — full coverage of Artifact model columns.
    # `share_token` was added post-initial-creation (MVP#2 Brag Card public
    # share); other cols are base but safe to declare idempotently.
    _add_column_if_missing("artifacts", "data_json", "JSON")
    _add_column_if_missing("artifacts", "pdf_path", "VARCHAR(500)")
    _add_column_if_missing("artifacts", "sent_at", "TIMESTAMP")
    _add_column_if_missing("artifacts", "opened_at", "TIMESTAMP")
    _add_column_if_missing("artifacts", "share_token", "VARCHAR(32)")

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

    # User referrals — `invited_count` is the one post-create candidate.
    _add_column_if_missing("user_referrals", "invited_count", "INTEGER", default="0")

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

    # Morning briefs / portfolio shares / push subscriptions / signal_cache /
    # watchlist — all their current columns are in the initial create_all
    # snapshot. No post-creation additions observed. Declared here as a
    # no-op safety net so future model additions auto-get a migration hook.

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


def _init_scheduler(app):
    def _scheduled_refresh():
        from models import Position, User
        with app.app_context():
            positions = Position.query.all()
            users = {u.id: u for u in User.query.all()}
            tku: dict[str, list[int]] = {}
            for p in positions:
                tku.setdefault(p.ticker, []).append(p.user_id)
            for ticker, uids in tku.items():
                cap = users[uids[0]].available_capital if uids[0] in users else 10_000
                try:
                    r = svc.engine.analyze(ticker, cap)
                    if r:
                        cache_service.save_signal(ticker, r)
                        for uid in uids:
                            alert_service.maybe_generate(uid, r)
                except Exception as e:
                    logger.error(f"Scheduler failed {ticker}: {e}")
            logger.info(f"Scheduled refresh done — {len(tku)} tickers")

    def _scheduled_morning_briefs():
        """Generate personalised morning briefings for all onboarded users.

        Fires at 06:00 Asia/Seoul daily. Each cycle is wrapped in an app
        context because APScheduler jobs execute on their own thread.
        """
        from services.morning_brief_service import run_daily_briefs
        with app.app_context():
            try:
                summary = run_daily_briefs()
                logger.info(f"Morning brief scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Morning brief scheduler failed: {e}")

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
        """Quarterly (1/7, 4/7, 7/7, 10/7) 08:00 KST — Self Audit PDF (Premium).

        The `_quarter_bounds` helper inside the service resolves "today" to
        the preceding quarter when we're in the first week of the new
        quarter, so calling this job with day=7 of those months always
        audits the quarter that just closed.
        """
        from services.artifacts.self_audit_service import SelfAuditService
        with app.app_context():
            try:
                summary = SelfAuditService().run_quarterly()
                logger.info(f"Self audit scheduler run: {summary}")
            except Exception as e:
                logger.error(f"Self audit scheduler failed: {e}")

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

    def _scheduled_earnings_prebrief():
        """Scan every 15 min for positions whose earnings fire in ~30 min
        (MVP #3). The service enforces dedup per (user, ticker,
        earnings_dt) so a scan that fires at T-35 and another at T-25
        won't double-send — the brief only emits inside the tight
        `LEAD_MINUTES ± tolerance` window.

        Runs at 15-min cadence to comfortably contain the ±6-min match
        window — a 30-min cadence would miss narrowly-scheduled
        announcements. Per-user failures never block the next one.
        """
        from services.artifacts.earnings_prebrief_service import (
            EarningsPrebriefService,
        )
        with app.app_context():
            try:
                summary = EarningsPrebriefService().run_scan()
                logger.info(f"Earnings pre-brief scan: {summary}")
            except Exception as e:
                logger.error(f"Earnings pre-brief scan failed: {e}")

    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(_scheduled_refresh, "interval", minutes=3, id="refresh")
    sched.add_job(
        _scheduled_morning_briefs,
        trigger="cron",
        hour=6, minute=0,
        timezone="Asia/Seoul",
        id="morning_brief_daily",
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
    # 15분 간격 — MVP #3 Earnings Pre-Brief scan. The service's internal
    # window matcher ensures only positions ~30 min away from their
    # earnings actually trigger a send, so this cadence is safe.
    sched.add_job(
        _scheduled_earnings_prebrief,
        trigger="interval",
        minutes=15,
        id="earnings_prebrief_scan",
        max_instances=1,
        coalesce=True,
    )
    # 매일 08:00 KST — KPI Dashboard 일일 5-메트릭 이메일 (Pro+).
    sched.add_job(
        _scheduled_kpi_dashboard,
        trigger="cron",
        hour=8, minute=0,
        timezone="Asia/Seoul",
        id="kpi_dashboard_daily",
        max_instances=1,
        coalesce=True,
    )
    # 분기 +7일 (1/7, 4/7, 7/7, 10/7) 08:00 KST — Self Audit PDF (Premium).
    sched.add_job(
        _scheduled_self_audit,
        trigger="cron",
        month="1,4,7,10",
        day=7,
        hour=8, minute=0,
        timezone="Asia/Seoul",
        id="self_audit_quarterly",
        max_instances=1,
        coalesce=True,
    )
    # 매일 08:00 KST — DD 체크리스트 T+3 프롬프트 이메일 (Pro+).
    # 5분 차이를 두어 KPI job과 겹치지 않게 한다.
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
    # 1시간 뒤로 분리해 Dividend Statement와 FMP 예산이 겹치지 않게 한다.
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
    sched.start()


# ── Create app instance ───────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5050, host="0.0.0.0", use_reloader=False)
