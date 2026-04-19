"""
PivoxQuant — Flask Backend v2
Quant Engine + AI-powered portfolio & trading dashboard.
Supports US + Korean equities.
"""

import os
import logging
import threading

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

import sentry_sdk
from flask import Flask, redirect
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
        # hashtext() returns int4 — perfect for pg_advisory_lock(bigint).
        # Lock is held on the pooled connection for the duration of migrations.
        db.session.execute(text(
            "SELECT pg_advisory_lock(hashtext('pivoxquant_migrate'))"
        ))
        try:
            _do_migrations()
        finally:
            db.session.execute(text(
                "SELECT pg_advisory_unlock(hashtext('pivoxquant_migrate'))"
            ))
            db.session.commit()
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
            sql += f" DEFAULT {default}"
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

    # Users table
    _add_column_if_missing("users", "available_capital_krw", "FLOAT", default="0.0")
    _add_column_if_missing("users", "google_id", "VARCHAR(100)", unique=True)
    _add_column_if_missing("users", "avatar_url", "VARCHAR(500)")
    _add_column_if_missing("users", "oauth_provider", "VARCHAR(20)")
    _add_column_if_missing("users", "kakao_id", "VARCHAR(100)", unique=True)
    _add_column_if_missing("users", "stripe_customer_id", "VARCHAR(100)")
    _add_column_if_missing("users", "stripe_subscription_id", "VARCHAR(100)")
    _add_column_if_missing("users", "subscription_status", "VARCHAR(20)", default="'inactive'")
    # MVP #3 Earnings Pre-Brief — per-channel email opt-out. Added via
    # migration 009_earnings_prebrief; this runtime hook covers existing
    # local dev DBs that boot without running Alembic.
    _add_column_if_missing("users", "email_opt_out_earnings", "BOOLEAN", default="0")

    # Positions table
    _add_column_if_missing("positions", "buy_fx_rate", "FLOAT", default="0.0")

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
