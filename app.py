"""
StockPilot — Flask Backend v2
Quant Engine + AI-powered portfolio & trading dashboard.
Supports US + Korean equities.
"""

import os
import logging

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

import sentry_sdk
from flask import Flask, redirect
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from extensions import db, login_manager
from routes import register_blueprints
from services import container as svc
from services import fx_service, cache_service, alert_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Sentry filter ─────────────────────────────────────────────────────────────

def _sentry_filter(event, hint):
    msg = str(event.get("logentry", {}).get("message", "")) + str(hint.get("log_record", {}) if hint else "")
    noise = ["possibly delisted", "No price data found", "currentTradingPeriod",
             "No fundamentals data", "quoteSummary", "Expecting value",
             "Failed to get ticker", "Snapshot failed", "HTTP Error 404",
             "yfinance", "No data found"]
    all_text = msg + str(event.get("message", "")) + str(
        event.get("exception", {}).get("values", [{}])[0].get("value", "")
        if event.get("exception") else "")
    if any(n in all_text for n in noise):
        return None
    exc = hint.get("exc_info")
    if exc:
        if any(n in str(exc[1] or "") for n in noise):
            return None
    if str(event.get("logger", "")) in ("yfinance", "data_fetcher"):
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

    # Extensions
    db.init_app(app)
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
        return redirect("http://localhost:3000")

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
        _populate_cache(app)

    # Background scheduler
    _init_scheduler(app)

    return app


def _run_migrations(app):
    from sqlalchemy import text as _text
    with db.engine.connect() as conn:
        try:
            conn.execute(_text("ALTER TABLE users ADD COLUMN available_capital_krw FLOAT DEFAULT 0.0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(_text("ALTER TABLE users ADD COLUMN google_id VARCHAR(100) UNIQUE"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(_text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(_text("ALTER TABLE positions ADD COLUMN buy_fx_rate FLOAT DEFAULT 0.0"))
            conn.commit()
        except Exception:
            pass
        # Stripe billing columns
        try:
            conn.execute(_text("ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(100)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(_text("ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(100)"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(_text("ALTER TABLE users ADD COLUMN subscription_status VARCHAR(20) DEFAULT 'inactive'"))
            conn.commit()
        except Exception:
            pass

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
    from models import Position, SignalCache
    try:
        positions = Position.query.all()
        tickers = list(set(p.ticker for p in positions))
        cached = set(c.ticker for c in SignalCache.query.all())
        missing = [t for t in tickers if t not in cached]
        if missing:
            logger.info(f"Populating signal cache for {len(missing)} tickers on startup...")
            for ticker in missing:
                try:
                    r = svc.engine.analyze(ticker, 10000)
                    if r:
                        cache_service.save_signal(ticker, r)
                        logger.info(f"  Cached: {ticker}")
                except Exception as e:
                    logger.error(f"  Failed to cache {ticker}: {e}")
            logger.info("Startup cache population complete.")
    except Exception as e:
        logger.error(f"Startup cache error: {e}")


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

    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(_scheduled_refresh, "interval", minutes=3, id="refresh")
    sched.start()


# ── Create app instance ───────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5050, host="0.0.0.0", use_reloader=False)
