"""
StockPilot — Flask Backend v2
New endpoints: /api/morning-brief  /api/market/overview  /api/portfolio/analytics
Supports US + Korean equities. Zero AI API cost.
"""

import os, json, logging, time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

import sentry_sdk

def _sentry_filter(event, hint):
    """Filter out noisy yfinance errors (weekend/holiday data gaps)."""
    msg = str(event.get("logentry", {}).get("message", "")) + str(hint.get("log_record", {}) if hint else "")
    noise = ["possibly delisted", "No price data found", "currentTradingPeriod", "No fundamentals data", "quoteSummary", "Expecting value", "Failed to get ticker", "Snapshot failed", "HTTP Error 404", "yfinance", "No data found"]
    all_text = msg + str(event.get("message", "")) + str(event.get("exception", {}).get("values", [{}])[0].get("value", "") if event.get("exception") else "")
    if any(n in all_text for n in noise):
        return None  # Don't send to Sentry
    exc = hint.get("exc_info")
    if exc:
        exc_msg = str(exc[1]) if exc[1] else ""
        if any(n in exc_msg for n in noise):
            return None
    # Also filter by logger name
    logger_name = str(event.get("logger", ""))
    if logger_name in ("yfinance", "data_fetcher"):
        return None
    return event

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", "https://0a85245ec56788355e861c8b8459576e@o4511165934141440.ingest.us.sentry.io/4511165940826112"),
    traces_sample_rate=0.2,
    send_default_pii=False,
    before_send=_sentry_filter,
)

from datetime import datetime, timedelta
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, request, jsonify, render_template
from flask_login import (LoginManager, UserMixin, login_user,
                         login_required, current_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

from engine import QuantEngine
from data_fetcher import DataFetcher
from ai_service import AIService
from daytrade_service import DayTradeService
from realtime_service import RealtimeService
from autotrader import AutoTrader

# ── Setup ──────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BASE   = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"]                  = os.environ.get("SECRET_KEY", "stockpilot-v2-change-in-prod")
_db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE, 'stockpilot.db')}")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"]     = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db      = SQLAlchemy(app)
lm      = LoginManager(app)
lm.login_view = "index"
engine  = QuantEngine()
fetcher = DataFetcher()
ai      = AIService()
daytrade = DayTradeService()
realtime = RealtimeService()
trader   = None  # Initialized after models are defined

# ── Models ─────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id               = db.Column(db.Integer,     primary_key=True)
    email            = db.Column(db.String(120),  unique=True, nullable=False)
    password_hash    = db.Column(db.String(200),  nullable=False)
    name             = db.Column(db.String(100),  default="")
    available_capital     = db.Column(db.Float, default=0.0)
    available_capital_krw = db.Column(db.Float, default=0.0)
    created_at       = db.Column(db.DateTime,     default=datetime.utcnow)
    positions = db.relationship("Position", backref="user", lazy=True,
                                cascade="all, delete-orphan")
    alerts    = db.relationship("Alert",    backref="user", lazy=True,
                                cascade="all, delete-orphan")

    def set_pw(self, pw):  self.password_hash = generate_password_hash(pw)
    def chk_pw(self, pw):  return check_password_hash(self.password_hash, pw)


class Position(db.Model):
    __tablename__ = "positions"
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker   = db.Column(db.String(20),  nullable=False)
    shares   = db.Column(db.Float,       nullable=False)
    avg_cost = db.Column(db.Float,       nullable=False)
    added_at = db.Column(db.DateTime,    default=datetime.utcnow)


class Alert(db.Model):
    __tablename__ = "alerts"
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker         = db.Column(db.String(20))
    message        = db.Column(db.Text,    nullable=False)
    signal         = db.Column(db.String(10))
    score          = db.Column(db.Float,   default=0)
    rec_shares     = db.Column(db.Integer, default=0)
    rec_investment = db.Column(db.Float,   default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    is_read        = db.Column(db.Boolean,  default=False)


class SignalCache(db.Model):
    __tablename__ = "signal_cache"
    ticker     = db.Column(db.String(20), primary_key=True)
    data_json  = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class TradeHistory(db.Model):
    __tablename__ = "trade_history"
    id              = db.Column(db.Integer,  primary_key=True)
    user_id         = db.Column(db.Integer,  db.ForeignKey("users.id"), nullable=False)
    ticker          = db.Column(db.String(20))
    name            = db.Column(db.String(100), default="")
    action          = db.Column(db.String(10))   # BUY | SELL
    shares          = db.Column(db.Float)
    price_per_share = db.Column(db.Float)
    total_value     = db.Column(db.Float)
    pnl             = db.Column(db.Float, default=0.0)
    pnl_pct         = db.Column(db.Float, default=0.0)
    currency        = db.Column(db.String(5), default="USD")
    traded_at       = db.Column(db.DateTime, default=datetime.utcnow)


class Watchlist(db.Model):
    __tablename__ = "watchlist"
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker   = db.Column(db.String(20), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize AutoTrader with DB models
trader = AutoTrader(db=db, Position=Position, TradeHistory=TradeHistory)

# Connect KIS to AutoTrader for Korean paper trading
try:
    from kis_service import KISService
    _kis_for_trader = KISService()
    if _kis_for_trader.available:
        trader.set_kis(_kis_for_trader)
except Exception:
    pass

# ── Auth helpers ───────────────────────────────────────────────────────────────

@lm.user_loader
def load_user(uid): return db.session.get(User, int(uid))

@app.after_request
def no_cache(r):
    r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    r.headers["Pragma"] = "no-cache"
    return r

def api_auth(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not current_user.is_authenticated:
            return jsonify({"error": "Login required"}), 401
        return f(*a, **kw)
    return wrapped

# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index(): return render_template("index.html")

# ── Auth API ───────────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    d = request.get_json() or {}
    email = (d.get("email") or "").strip().lower()
    pw    = d.get("password") or ""
    name  = (d.get("name") or "").strip()
    if not email or not pw:           return jsonify({"error": "Email and password required"}), 400
    if len(pw) < 6:                   return jsonify({"error": "Password must be ≥ 6 characters"}), 400
    if User.query.filter_by(email=email).first():
                                       return jsonify({"error": "Email already registered"}), 409
    u = User(email=email, name=name or email.split("@")[0])
    u.set_pw(pw)
    db.session.add(u); db.session.commit()
    login_user(u, remember=True)
    return jsonify({"ok": True, "user": _u(u)})

@app.route("/api/auth/login", methods=["POST"])
def login():
    d = request.get_json() or {}
    u = User.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.chk_pw(d.get("password") or ""):
        return jsonify({"error": "Invalid email or password"}), 401
    login_user(u, remember=True)
    return jsonify({"ok": True, "user": _u(u)})

@app.route("/api/auth/logout", methods=["POST"])
@api_auth
def do_logout(): logout_user(); return jsonify({"ok": True})

@app.route("/api/auth/me")
def me():
    if not current_user.is_authenticated: return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": _u(current_user)})

# ── Portfolio ──────────────────────────────────────────────────────────────────

@app.route("/api/portfolio")
@api_auth
def get_portfolio():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    out = []
    for p in positions:
        cached = SignalCache.query.get(p.ticker)
        sd     = json.loads(cached.data_json) if cached and cached.data_json else {}
        is_kr  = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        cur_px = sd.get("price", p.avg_cost)
        pnl    = (cur_px - p.avg_cost) / p.avg_cost * 100 if p.avg_cost else 0
        cur    = sd.get("currency", "KRW" if is_kr else "USD")
        out.append({
            "id":            p.id,
            "ticker":        p.ticker,
            "shares":        p.shares,
            "avg_cost":      p.avg_cost,
            "price":         cur_px,
            "current_price": cur_px,
            "price_display": sd.get("price_display", f"${cur_px:.2f}"),
            "pnl_pct":       round(pnl, 2),
            "market_value":  round(cur_px * p.shares, 2),
            "signal":        sd.get("signal", "—"),
            "score":         sd.get("score", 0),
            "rec_shares":    sd.get("rec_shares", 0),
            "rec_investment": sd.get("rec_investment", 0),
            "rec_timing":    sd.get("rec_timing", ""),
            "name":           sd.get("name", p.ticker),
            "sector":         sd.get("sector", "Unknown"),
            "currency":       cur,
            "is_korean":      sd.get("is_korean", is_kr),
            "sell_pct":       sd.get("sell_pct", 0),
            "sell_timing":    sd.get("sell_timing", ""),
            "capital_needed": sd.get("capital_needed"),
            "capital_gap":    sd.get("capital_gap"),
            "take_profit":    sd.get("take_profit"),
            "stop_loss":      sd.get("stop_loss"),
            "tp_pct":         sd.get("tp_pct", 0),
            "sl_pct":         sd.get("sl_pct", 0),
            "regime_profile": sd.get("regime_profile", ""),
            "regime_label":   sd.get("regime_label", ""),
            "regime_label_kr":sd.get("regime_label_kr", ""),
            "priority":       sd.get("priority", 0),
        })
    total_usd = sum(p["market_value"] for p in out if p["currency"] == "USD")
    total_krw = sum(p["market_value"] for p in out if p["currency"] == "KRW")
    return jsonify({
        "positions":             out,
        "available_capital":     current_user.available_capital,
        "available_capital_krw": getattr(current_user, "available_capital_krw", 0.0) or 0.0,
        "total_value_usd":       round(total_usd, 2),
        "total_value_krw":       round(total_krw, 0),
    })

@app.route("/api/portfolio/position", methods=["POST"])
@api_auth
def add_position():
    d      = request.get_json() or {}
    ticker = (d.get("ticker") or "").strip().upper()
    shares = float(d.get("shares") or 0)
    cost   = float(d.get("avg_cost") or 0)
    if not ticker or shares <= 0 or cost <= 0:
        return jsonify({"error": "Ticker, shares, and average cost required"}), 400
    ex = Position.query.filter_by(user_id=current_user.id, ticker=ticker).first()
    if ex:
        total = ex.shares * ex.avg_cost + shares * cost
        ex.shares   += shares
        ex.avg_cost  = total / ex.shares
    else:
        db.session.add(Position(user_id=current_user.id,
                                ticker=ticker, shares=shares, avg_cost=cost))
    db.session.commit()
    _cache_ticker(ticker, current_user.available_capital)
    return jsonify({"ok": True})

@app.route("/api/portfolio/position/<int:pid>", methods=["PUT"])
@api_auth
def edit_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p: return jsonify({"error": "Position not found"}), 404
    d      = request.get_json() or {}
    shares = float(d.get("shares") or 0)
    cost   = float(d.get("avg_cost") or 0)
    if shares <= 0 or cost <= 0:
        return jsonify({"error": "Shares and average cost must be positive"}), 400
    p.shares   = shares
    p.avg_cost = cost
    db.session.commit()
    _cache_ticker(p.ticker, current_user.available_capital)
    return jsonify({"ok": True})

@app.route("/api/portfolio/position/<int:pid>", methods=["DELETE"])
@api_auth
def del_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p: return jsonify({"error": "Position not found"}), 404
    db.session.delete(p); db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/portfolio/position/<int:pid>/buy", methods=["POST"])
@api_auth
def buy_more(pid):
    """Add to existing position: deducts from capital, updates shares + weighted avg cost."""
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p: return jsonify({"error": "Position not found"}), 404
    d = request.get_json() or {}
    buy_shares = float(d.get("shares") or 0)
    buy_price  = float(d.get("price")  or 0)
    if buy_shares <= 0 or buy_price <= 0:
        return jsonify({"error": "Shares and price required"}), 400

    cost = buy_shares * buy_price
    cached = SignalCache.query.get(p.ticker)
    sd     = json.loads(cached.data_json) if cached and cached.data_json else {}
    is_kr  = sd.get("is_korean", False)
    name   = sd.get("name", p.ticker)
    currency = sd.get("currency", "USD")

    # Check capital
    if is_kr:
        avail = getattr(current_user, "available_capital_krw", 0) or 0
        if avail < cost:
            return jsonify({"error": f"Insufficient KRW capital (need ₩{cost:,.0f}, have ₩{avail:,.0f})"}), 400
        current_user.available_capital_krw = avail - cost
    else:
        avail = current_user.available_capital or 0
        if avail < cost:
            return jsonify({"error": f"Insufficient capital (need ${cost:,.2f}, have ${avail:,.2f})"}), 400
        current_user.available_capital = avail - cost

    # Weighted average cost
    total_cost   = p.shares * p.avg_cost + buy_shares * buy_price
    p.shares    += buy_shares
    p.avg_cost   = total_cost / p.shares

    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="BUY", shares=buy_shares, price_per_share=round(buy_price, 2),
        total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
    ))
    db.session.commit()
    return jsonify({
        "ok": True,
        "new_shares":   round(p.shares, 4),
        "new_avg_cost": round(p.avg_cost, 2),
        "new_capital_usd": current_user.available_capital,
        "new_capital_krw": getattr(current_user, "available_capital_krw", 0) or 0,
    })

@app.route("/api/portfolio/position/buy-new", methods=["POST"])
@api_auth
def buy_new_position():
    """Create new position + deduct capital atomically (used by Discover)."""
    d       = request.get_json() or {}
    ticker  = (d.get("ticker") or "").strip().upper()
    shares  = float(d.get("shares") or 0)
    price   = float(d.get("price")  or 0)
    if not ticker or shares <= 0 or price <= 0:
        return jsonify({"error": "Ticker, shares, and price required"}), 400

    cost     = shares * price
    currency = fetcher.currency(ticker)
    is_kr    = currency == "KRW"

    cap = (getattr(current_user, "available_capital_krw", 0) or 0) if is_kr else (current_user.available_capital or 0)
    if cap < cost:
        sym = "₩" if is_kr else "$"
        return jsonify({"error": f"Insufficient capital (need {sym}{cost:,.0f}, have {sym}{cap:,.0f})"}), 400

    p = Position.query.filter_by(ticker=ticker, user_id=current_user.id).first()
    if p:
        total = p.shares * p.avg_cost + shares * price
        p.shares   += shares
        p.avg_cost  = total / p.shares
    else:
        p = Position(user_id=current_user.id, ticker=ticker, shares=shares, avg_cost=price)
        db.session.add(p)

    if is_kr:
        current_user.available_capital_krw = cap - cost
    else:
        current_user.available_capital = cap - cost

    cached = SignalCache.query.get(ticker)
    sd     = json.loads(cached.data_json) if cached and cached.data_json else {}
    name   = sd.get("name", ticker)
    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=ticker, name=name,
        action="BUY", shares=shares, price_per_share=round(price, 2),
        total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
    ))
    db.session.commit()
    return jsonify({
        "ok": True,
        "new_shares":    round(p.shares, 4),
        "new_avg_cost":  round(p.avg_cost, 2),
        "new_capital_usd": current_user.available_capital,
        "new_capital_krw": getattr(current_user, "available_capital_krw", 0) or 0,
    })

@app.route("/api/portfolio/position/<int:pid>/sell", methods=["POST"])
@api_auth
def sell_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p: return jsonify({"error": "Position not found"}), 404
    d = request.get_json() or {}
    sell_shares = float(d.get("shares") or p.shares)
    sell_price  = float(d.get("price")  or 0)

    # Fetch cache once for both price fallback and metadata
    cached = SignalCache.query.get(p.ticker)
    sd     = json.loads(cached.data_json) if cached and cached.data_json else {}

    if sell_price <= 0:
        sell_price = sd.get("price", p.avg_cost) if sd else p.avg_cost

    sell_shares = min(sell_shares, p.shares)
    proceeds    = sell_shares * sell_price
    cost_basis  = sell_shares * p.avg_cost
    pnl         = proceeds - cost_basis
    pnl_pct     = pnl / cost_basis * 100 if cost_basis > 0 else 0
    name     = sd.get("name", p.ticker)
    currency = sd.get("currency", "USD")
    is_kr    = sd.get("is_korean", False)

    # Update or delete position (avg_cost unchanged on partial sell — FIFO basis)
    if sell_shares >= p.shares - 0.0001:
        db.session.delete(p)
    else:
        p.shares = round(p.shares - sell_shares, 6)
        # avg_cost stays the same for remaining shares

    # Return proceeds to capital
    if is_kr:
        current_user.available_capital_krw = (getattr(current_user, "available_capital_krw", 0) or 0) + proceeds
    else:
        current_user.available_capital = (current_user.available_capital or 0) + proceeds

    # Record trade
    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="SELL", shares=sell_shares, price_per_share=round(sell_price, 2),
        total_value=round(proceeds, 2), pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
        currency=currency,
    ))
    db.session.commit()
    return jsonify({
        "ok":              True,
        "proceeds":        round(proceeds, 2),
        "pnl":             round(pnl, 2),
        "pnl_pct":         round(pnl_pct, 2),
        "currency":        currency,
        "new_capital_usd": current_user.available_capital,
        "new_capital_krw": getattr(current_user, "available_capital_krw", 0) or 0,
    })

@app.route("/api/portfolio/capital", methods=["PUT"])
@api_auth
def set_capital():
    d       = request.get_json() or {}
    cap_usd = float(d.get("capital_usd") or d.get("capital") or 0)
    cap_krw = float(d.get("capital_krw") or 0)
    if cap_usd < 0 or cap_krw < 0:
        return jsonify({"error": "Capital must be ≥ 0"}), 400
    current_user.available_capital     = cap_usd
    current_user.available_capital_krw = cap_krw
    db.session.commit()
    return jsonify({"ok": True, "capital_usd": cap_usd, "capital_krw": cap_krw})

# ── Portfolio Analytics ────────────────────────────────────────────────────────

@app.route("/api/portfolio/analytics")
@api_auth
def portfolio_analytics():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    pl = []
    for p in positions:
        cached = SignalCache.query.get(p.ticker)
        sd     = json.loads(cached.data_json) if cached and cached.data_json else {}
        pl.append({
            "ticker":       p.ticker,
            "shares":       p.shares,
            "market_value": sd.get("price", p.avg_cost) * p.shares,
            "sector":       sd.get("sector", "Unknown"),
        })
    return jsonify(engine.portfolio_analytics(pl, current_user.available_capital))

# ── Signals ────────────────────────────────────────────────────────────────────

@app.route("/api/signals")
@api_auth
def get_signals():
    tickers = {p.ticker for p in Position.query.filter_by(user_id=current_user.id).all()}
    out = []
    for t in tickers:
        c = SignalCache.query.get(t)
        if c and c.data_json:
            d = json.loads(c.data_json)
            d["cached_at"] = c.updated_at.isoformat()
            out.append(d)
    return jsonify({"signals": out})

@app.route("/api/signals/<ticker>")
@api_auth
def signal_detail(ticker):
    r = engine.analyze(ticker.upper(), current_user.available_capital, getattr(current_user, "available_capital_krw", 0.0) or 0.0)
    if not r:
        # Fallback: return cached data if available
        cached = db.session.get(SignalCache, ticker.upper())
        if cached and cached.data_json:
            return jsonify(json.loads(cached.data_json))
        return jsonify({"error": f"Analysis failed for '{ticker}'. Check the ticker symbol."}), 404
    _save_cache(ticker.upper(), r)
    return jsonify(r)

@app.route("/api/signals/refresh", methods=["POST"])
@api_auth
def refresh():
    tickers = {p.ticker for p in Position.query.filter_by(user_id=current_user.id).all()}
    done = []
    for t in tickers:
        r = engine.analyze(t, current_user.available_capital, getattr(current_user, "available_capital_krw", 0.0) or 0.0)
        if r:
            _save_cache(t, r)
            _maybe_alert(current_user.id, r)
            done.append(t)
    return jsonify({"ok": True, "refreshed": done})

# ── Discover ───────────────────────────────────────────────────────────────────

_discover_cache: dict = {}   # keyed by user_id → {"data": [...], "ts": float}
_DISCOVER_TTL   = 600  # 10 minutes

@app.route("/api/discover")
@api_auth
def discover():
    now = time.time()
    uid = current_user.id
    force = request.args.get("force") == "1"
    uc = _discover_cache.get(uid, {"data": None, "ts": 0})
    if not force and uc["data"] and now - uc["ts"] < _DISCOVER_TTL:
        return jsonify({"results": uc["data"], "cached": True,
                        "cached_at": datetime.fromtimestamp(uc["ts"]).isoformat()})

    cap_usd = current_user.available_capital or 0.0
    cap_krw = getattr(current_user, "available_capital_krw", 0.0) or 0.0
    owned   = {p.ticker for p in Position.query.filter_by(user_id=current_user.id).all()}

    pool = engine.DISCOVER_POOL

    def _analyze_one(ticker):
        try:
            r = engine.analyze(ticker, cap_usd, cap_krw)
            if r:
                r["already_owned"] = ticker in owned
            return r
        except Exception as e:
            logger.warning(f"Discover skip {ticker}: {e}")
            return None

    results = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_analyze_one, t): t for t in pool}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    # Sort: BUY first by priority, then HOLD, then rest
    order = {"BUY": 0, "HOLD": 1, "SELL": 2}
    results.sort(key=lambda x: (order.get(x.get("signal",""), 9), -x.get("priority", 0)))

    _discover_cache[uid] = {"data": results, "ts": now}
    return jsonify({"results": results, "cached": False})

# ── Scan ───────────────────────────────────────────────────────────────────────

@app.route("/api/scan", methods=["POST"])
@api_auth
def scan():
    ticker = ((request.get_json() or {}).get("ticker") or "").strip().upper()
    if not ticker: return jsonify({"error": "Ticker required"}), 400
    r = engine.analyze(ticker, current_user.available_capital, getattr(current_user, "available_capital_krw", 0.0) or 0.0)
    if not r:
        cached = db.session.get(SignalCache, ticker)
        if cached and cached.data_json:
            return jsonify(json.loads(cached.data_json))
        return jsonify({"error": f"Analysis failed for '{ticker}'"}), 404
    return jsonify(r)

# ── Real-time Price Stream ─────────────────────────────────────────────────────

@app.route("/api/realtime/stream")
@api_auth
def realtime_stream():
    """SSE stream: pushes portfolio position prices every 5 seconds via Alpaca+KIS."""
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"error": "No positions"}), 400

    from flask import Response
    def generate():
        while True:
            try:
                prices = realtime.get_prices_batch(tickers)
                yield f"data: {json.dumps(prices, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(5)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/realtime/price/<ticker>")
@api_auth
def realtime_single(ticker):
    """Get real-time price for a single ticker."""
    p = realtime.get_price(ticker.upper())
    if p:
        return jsonify(p)
    return jsonify({"error": f"No price for {ticker}"}), 404

@app.route("/api/realtime/status")
def realtime_status():
    return jsonify({
        "alpaca": realtime.alpaca_available,
        "kis": realtime.kis_available,
        "sources": {
            "us": "alpaca" if realtime.alpaca_available else "yfinance",
            "kr": "kis" if realtime.kis_available else "yfinance",
        }
    })

# ── Earnings Calendar ──────────────────────────────────────────────────────────

@app.route("/api/earnings")
@api_auth
def earnings_calendar():
    """Get upcoming earnings dates for portfolio positions."""
    import yfinance as yf
    positions = Position.query.filter_by(user_id=current_user.id).all()
    earnings = []
    # Suppress yfinance 404 errors for ETFs
    import logging as _logging
    _yf_logger = _logging.getLogger('yfinance')
    _prev_level = _yf_logger.level
    _yf_logger.setLevel(_logging.CRITICAL)

    for p in positions:
        try:
            # Skip ETFs (no earnings)
            is_etf = p.ticker in ('TSLL','ETHU','SPY','QQQ','TLT','GLD','USO','UUP') or 'ETF' in (p.ticker or '')
            if is_etf:
                continue
            stock = yf.Ticker(p.ticker)
            cal = stock.calendar
            if cal is not None and not cal.empty if hasattr(cal, 'empty') else cal:
                # calendar can be dict or DataFrame
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        dates = ed if isinstance(ed, list) else [ed]
                        for d in dates:
                            ds = str(d)[:10] if d else None
                            if ds:
                                c = db.session.get(SignalCache, p.ticker)
                                sd = json.loads(c.data_json) if c and c.data_json else {}
                                earnings.append({
                                    "ticker": p.ticker,
                                    "name": sd.get("name", p.ticker),
                                    "date": ds,
                                    "signal": sd.get("signal", "—"),
                                    "score": sd.get("score", 0),
                                })
                                break
                else:
                    # DataFrame format
                    if "Earnings Date" in cal.index:
                        ed = cal.loc["Earnings Date"]
                        ds = str(ed.iloc[0])[:10] if len(ed) else None
                        if ds:
                            c = db.session.get(SignalCache, p.ticker)
                            sd = json.loads(c.data_json) if c and c.data_json else {}
                            earnings.append({
                                "ticker": p.ticker,
                                "name": sd.get("name", p.ticker),
                                "date": ds,
                                "signal": sd.get("signal", "—"),
                                "score": sd.get("score", 0),
                            })
        except Exception:
            pass
    _yf_logger.setLevel(_prev_level)  # Restore logger
    earnings.sort(key=lambda x: x.get("date", "9999"))
    return jsonify({"earnings": earnings})

# ── Peer Comparison ────────────────────────────────────────────────────────────

@app.route("/api/peers/<ticker>")
@api_auth
def peer_comparison(ticker):
    """Find peers in the same sector and rank by quant score."""
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    # Get target sector from cache
    c = db.session.get(SignalCache, ticker)
    if not c or not c.data_json:
        return jsonify({"error": "Analyze this stock first"}), 404
    target = json.loads(c.data_json)
    sector = target.get("sector", "Unknown")
    if sector in ("Unknown", "ETF"):
        return jsonify({"peers": [], "sector": sector, "message": "No sector peers available"})

    # Find peers from DISCOVER_POOL + user positions with same sector
    all_cached = SignalCache.query.all()
    peers = []
    for sc in all_cached:
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == sector:
                peers.append({
                    "ticker": sc.ticker,
                    "name": sd.get("name", sc.ticker),
                    "score": sd.get("score", 0),
                    "signal": sd.get("signal", "—"),
                    "price": sd.get("price", 0),
                    "price_display": sd.get("price_display", "—"),
                    "change_pct": sd.get("change_pct", 0),
                    "pe_ratio": sd.get("snapshot", {}).get("pe_ratio"),
                    "is_target": sc.ticker == ticker,
                })
        except Exception:
            pass

    peers.sort(key=lambda x: -x.get("score", 0))
    # Find rank
    rank = next((i+1 for i, p in enumerate(peers) if p["is_target"]), 0)

    return jsonify({"peers": peers[:10], "sector": sector, "rank": rank, "total": len(peers)})

# ── Company Profile ────────────────────────────────────────────────────────────

@app.route("/api/profile/<ticker>")
@api_auth
def company_profile(ticker):
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        try:
            info = stock.info
        except Exception:
            info = {}
        return jsonify({
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "summary": info.get("longBusinessSummary") or "",
            "sector": info.get("sector") or "",
            "industry": info.get("industry") or "",
            "website": info.get("website") or "",
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country") or "",
            "market_cap": info.get("marketCap"),
            "currency": "KRW" if ticker.endswith(".KS") or ticker.endswith(".KQ") else "USD",
        })
    except Exception as e:
        logger.error(f"Profile error {ticker}: {e}")
        return jsonify({"error": "Unable to fetch company profile"}), 500

# ── Dividend Data ──────────────────────────────────────────────────────────────

@app.route("/api/dividend/<ticker>")
@api_auth
def dividend_data(ticker):
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        div_yield = info.get("dividendYield")
        div_rate = info.get("dividendRate")
        ex_date = info.get("exDividendDate")
        payout = info.get("payoutRatio")
        five_yr = info.get("fiveYearAvgDividendYield")

        if not div_yield and not div_rate:
            return jsonify({"has_dividend": False, "ticker": ticker})

        return jsonify({
            "has_dividend": True,
            "ticker": ticker,
            "dividend_yield": round(div_yield * 100, 2) if div_yield else None,
            "dividend_rate": round(div_rate, 2) if div_rate else None,
            "ex_dividend_date": ex_date,
            "payout_ratio": round(payout * 100, 1) if payout else None,
            "five_yr_avg_yield": round(five_yr, 2) if five_yr else None,
        })
    except Exception as e:
        logger.error(f"Dividend error {ticker}: {e}")
        return jsonify({"has_dividend": False, "error": "Unable to fetch dividend data"})

# ── Portfolio History ──────────────────────────────────────────────────────────

@app.route("/api/portfolio/history")
@api_auth
def portfolio_history():
    """Approximate portfolio value over time."""
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"data": []})
    import yfinance as yf
    import pandas as pd

    period = request.args.get("period", "5d")
    if period not in ("5d", "1mo", "3mo"):
        period = "5d"
    all_values = {}
    for p in positions:
        try:
            h = yf.Ticker(p.ticker).history(period=period)
            if h.empty: continue
            for date, row in h.iterrows():
                ds = date.strftime("%Y-%m-%d")
                if ds not in all_values:
                    all_values[ds] = 0
                all_values[ds] += float(row["Close"]) * p.shares
        except Exception:
            pass

    if not all_values:
        return jsonify({"data": []})

    # Add today's real-time value
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        rt_prices = realtime.get_prices_batch([p.ticker for p in positions])
        today_val = 0
        for p in positions:
            if p.ticker in rt_prices:
                today_val += rt_prices[p.ticker]["price"] * p.shares
            elif today in all_values:
                pass  # already have from yfinance
        if today_val > 0:
            all_values[today] = today_val
    except Exception:
        pass

    # Sort by date
    data = [{"date": k, "value": round(v, 2)} for k, v in sorted(all_values.items())]
    return jsonify({"data": data})

# ── Chart Data ─────────────────────────────────────────────────────────────────

@app.route("/api/chart/<ticker>")
@api_auth
def chart_data(ticker):
    """Return price history for charting. Uses Alpaca (US) or yfinance fallback."""
    period = request.args.get("period", "6mo")
    if period not in ("1mo", "3mo", "6mo", "1y", "2y", "1d", "5d"):
        period = "6mo"
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")

    # Try Alpaca for US stocks (intraday periods)
    if not is_kr and realtime.alpaca_available and period in ("1d", "5d"):
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            tf = TimeFrame.Minute if period == "1d" else TimeFrame(5, "Min")
            days = 1 if period == "1d" else 5
            start = datetime.utcnow() - timedelta(days=days)
            req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=tf, start=start, limit=500)
            bars = realtime.alpaca_client.get_stock_bars(req)
            data = []
            for bar in bars[ticker]:
                data.append({
                    "date": bar.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "close": round(float(bar.close), 2),
                    "volume": int(bar.volume),
                })
            if data:
                return jsonify({"ticker": ticker, "period": period, "data": data, "source": "alpaca"})
        except Exception as e:
            logger.warning(f"Alpaca chart failed {ticker}: {e}")

    # Fallback: yfinance (all periods, all markets)
    try:
        import yfinance as yf
        h = yf.Ticker(ticker).history(period=period)
        if h.empty:
            return jsonify({"error": "No data"}), 404
        data = []
        for date, row in h.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return jsonify({"ticker": ticker, "period": period, "data": data, "source": "yfinance"})
    except Exception as e:
        logger.error(f"Chart error {ticker}: {e}")
        return jsonify({"error": "Unable to fetch chart data"}), 500

# ── Market Status ──────────────────────────────────────────────────────────────

@app.route("/api/market/status")
def market_status():
    """Returns current open/closed/pre-market status for US and KR markets."""
    from zoneinfo import ZoneInfo
    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))

    # US Market holidays 2026 (NYSE closed)
    US_HOLIDAYS = {
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",  # New Year, MLK, Presidents, Good Friday
        "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",  # Memorial, July 4th, Labor, Thanksgiving, Christmas
    }
    # KR Market holidays 2026 (KRX closed)
    KR_HOLIDAYS = {
        "2026-01-01", "2026-01-28", "2026-01-29", "2026-01-30",  # New Year, Seollal
        "2026-03-01", "2026-05-05", "2026-05-24", "2026-06-06",  # Independence, Children, Buddha, Memorial
        "2026-08-15", "2026-09-24", "2026-09-25", "2026-09-26",  # Liberation, Chuseok
        "2026-10-03", "2026-10-09", "2026-12-25",  # National Foundation, Hangul, Christmas
    }

    # US Market (NYSE/NASDAQ) — ET timezone
    # 9:30 AM ET = 570 min, 4:00 PM ET = 960 min
    et = now_utc.astimezone(ZoneInfo("America/New_York"))
    us_min = et.hour * 60 + et.minute
    us_date = et.strftime("%Y-%m-%d")

    if et.weekday() >= 5 or us_date in US_HOLIDAYS:
        us_status = "CLOSED"
        us_label = "Holiday" if us_date in US_HOLIDAYS else "Weekend"
    elif 570 <= us_min < 960:
        us_status, us_label = "OPEN", "Market Open"
    elif 240 <= us_min < 570:
        us_status, us_label = "PRE_MARKET", "Pre-Market"
    elif 960 <= us_min < 1200:
        us_status, us_label = "AFTER_HOURS", "After Hours"
    else:
        us_status, us_label = "CLOSED", "Closed"

    # KR Market (KRX) — KST timezone
    # 9:00 AM KST = 540 min, 3:30 PM KST = 930 min
    kst = now_utc.astimezone(ZoneInfo("Asia/Seoul"))
    kr_min = kst.hour * 60 + kst.minute
    kr_date = kst.strftime("%Y-%m-%d")

    if kst.weekday() >= 5 or kr_date in KR_HOLIDAYS:
        kr_status = "CLOSED"
        kr_label = "Holiday" if kr_date in KR_HOLIDAYS else "Weekend"
    elif 540 <= kr_min < 930:
        kr_status, kr_label = "OPEN", "Market Open"
    else:
        kr_status, kr_label = "CLOSED", "Closed"

    return jsonify({
        "us": {"status": us_status, "label": us_label, "time": et.strftime("%H:%M ET")},
        "kr": {"status": kr_status, "label": kr_label, "time": kst.strftime("%H:%M KST")},
    })

# ── Market Data ────────────────────────────────────────────────────────────────

@app.route("/api/lookup/<ticker>")
def lookup_ticker(ticker):
    """Fast ticker lookup — used by the Add Position modal for real-time name/price display."""
    result = fetcher.quick_lookup(ticker.strip().upper())
    if result:
        return jsonify(result)
    return jsonify({"ok": False, "error": f"Ticker '{ticker}' not found"}), 404

# Simple 5-minute cache for macro data (expensive to fetch)
_macro_cache: dict = {"data": None, "ts": 0.0}

@app.route("/api/prices")
@api_auth
def get_prices_fast():
    """Real-time batch price update — Alpaca (US) + KIS (KR) + yfinance fallback."""
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers   = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"prices": {}})

    # Use real-time service (Alpaca + KIS) with yfinance fallback
    prices = realtime.get_prices_batch(tickers)

    # Update cached signal data with fresh prices
    for ticker, pdata in prices.items():
        c = db.session.get(SignalCache, ticker)
        if c and c.data_json:
            try:
                sd = json.loads(c.data_json)
                sd["price"]         = pdata["price"]
                sd["price_display"] = pdata.get("price_display", sd.get("price_display"))
                if pdata.get("change_pct") is not None:
                    sd["change_pct"] = pdata["change_pct"]
                c.data_json  = json.dumps(sd, ensure_ascii=False)
                c.updated_at = datetime.utcnow()
            except Exception:
                pass
    db.session.commit()
    return jsonify({"prices": prices, "updated_at": datetime.utcnow().isoformat(), "sources": {t: p.get("source","?") for t,p in prices.items()}})

@app.route("/api/morning-brief")
def morning_brief():
    brief    = fetcher.get_wall_street_brief()
    macro    = fetcher.get_macro_data()
    gs_view  = fetcher.generate_gs_view(macro)
    return jsonify({**brief, "gs_view": gs_view})

@app.route("/api/market/overview")
def market_overview():
    import time as _time
    now = _time.time()
    if _macro_cache["data"] and now - _macro_cache["ts"] < 300:   # 5-min cache
        return jsonify(_macro_cache["data"])
    macro   = fetcher.get_enhanced_macro()
    gs_view = fetcher.generate_gs_view(macro)
    result  = {"macro": macro, "gs_view": gs_view, "cached_at": datetime.utcnow().isoformat()}
    _macro_cache["data"] = result
    _macro_cache["ts"]   = now
    return jsonify(result)

@app.route("/api/macro")
def get_macro(): return jsonify(fetcher.get_macro_data())

@app.route("/api/sectors")
def get_sectors(): return jsonify(fetcher.get_sector_performance())

@app.route("/api/news/<ticker>")
@api_auth
def get_news(ticker): return jsonify({"news": fetcher.get_news(ticker.upper())})


@app.route("/api/alerts/price-check")
@api_auth
def price_alert_check():
    """Returns positions that have breached take-profit or stop-loss."""
    positions = Position.query.filter_by(user_id=current_user.id).all()
    alerts = []
    for p in positions:
        c = SignalCache.query.get(p.ticker)
        if not c or not c.data_json: continue
        sd = json.loads(c.data_json)
        price = sd.get("price", 0)
        tp    = sd.get("take_profit")
        sl    = sd.get("stop_loss")
        name  = sd.get("name", p.ticker)
        cur   = "₩" if sd.get("is_korean") else "$"
        dp    = 0 if sd.get("is_korean") else 0   # integer display
        if tp and price >= tp:
            alerts.append({"ticker": p.ticker, "name": name, "type": "TAKE_PROFIT",
                           "price": price, "target": tp, "shares": p.shares,
                           "proceeds": round(p.shares * price),
                           "message": f"🎯 {name} 목표가 도달! {cur}{round(price):,} ≥ {cur}{round(tp):,} — {p.shares}주 매도 권고"})
        elif sl and price <= sl:
            alerts.append({"ticker": p.ticker, "name": name, "type": "STOP_LOSS",
                           "price": price, "target": sl, "shares": p.shares,
                           "proceeds": round(p.shares * price),
                           "message": f"🛑 {name} 손절가 도달! {cur}{round(price):,} ≤ {cur}{round(sl):,} — {p.shares}주 손절 권고"})

    # Save TP/SL alerts to DB so they appear in Alert Center
    for a in alerts:
        # Check for duplicate (same ticker + type within 4 hours)
        recent = (Alert.query.filter_by(user_id=current_user.id, ticker=a["ticker"])
                  .filter(Alert.message.contains(a["type"]))
                  .filter(Alert.created_at > datetime.utcnow() - timedelta(hours=4))
                  .first())
        if not recent:
            sig = "SELL" if a["type"] == "STOP_LOSS" else "BUY"
            db.session.add(Alert(
                user_id=current_user.id, ticker=a["ticker"],
                message=a["message"], signal=sig, score=0
            ))
    if alerts:
        db.session.commit()

    return jsonify({"alerts": alerts})

@app.route("/api/trades")
@api_auth
def get_trades():
    trades = (TradeHistory.query
              .filter_by(user_id=current_user.id)
              .order_by(TradeHistory.traded_at.desc())
              .limit(60).all())
    return jsonify({"trades": [_trade(t) for t in trades]})

# ── Alerts ─────────────────────────────────────────────────────────────────────

@app.route("/api/alerts")
@api_auth
def get_alerts():
    # Auto-delete alerts older than 7 days
    cutoff = datetime.utcnow() - timedelta(days=7)
    Alert.query.filter(Alert.user_id == current_user.id, Alert.created_at < cutoff).delete()
    db.session.commit()
    alerts = (Alert.query.filter_by(user_id=current_user.id)
              .order_by(Alert.created_at.desc()).limit(20).all())
    return jsonify({
        "alerts": [_al(a) for a in alerts],
        "unread": sum(1 for a in alerts if not a.is_read),
    })

@app.route("/api/alerts/read", methods=["POST"])
@api_auth
def mark_read():
    Alert.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/api/alerts/clear", methods=["POST"])
@api_auth
def clear_alerts():
    Alert.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True})

# ── Day Trade ──────────────────────────────────────────────────────────────────

@app.route("/api/daytrade/status")
def daytrade_status():
    return jsonify({"available": daytrade.available})

@app.route("/api/daytrade/scan")
@api_auth
def daytrade_scan():
    results = []

    # US stocks (Alpaca) — works when US market is open
    if daytrade.available:
        try:
            us_results = daytrade.scan_momentum() or []
            results.extend(us_results)
        except Exception as e:
            logger.warning(f"US scan error: {e}")

    # Korean stocks (KIS) — works when KR market is open
    try:
        from kis_service import KISService
        kis = KISService()
        if kis.available:
            # Get held Korean tickers from portfolio
            held_kr = set()
            try:
                positions = Position.query.filter_by(user_id=current_user.id).all()
                for p in positions:
                    t = p.ticker.replace(".KS", "").replace(".KQ", "")
                    if t.isdigit() and len(t) == 6:
                        held_kr.add(t)
            except Exception:
                pass
            kr_results = kis.scan_momentum(held_tickers=held_kr) or []
            results.extend(kr_results)
    except Exception as e:
        logger.warning(f"KR scan error: {e}")

    if not results and not daytrade.available:
        return jsonify({"error": "Day trade not configured (Alpaca API key missing)"}), 503

    # Sort by score descending
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return jsonify({"results": results, "count": len(results)})

@app.route("/api/daytrade/analyze/<ticker>")
@api_auth
def daytrade_analyze(ticker):
    # Korean stock: KIS intraday analysis (day trade only)
    if ticker.isdigit() and len(ticker) == 6:
        try:
            from kis_service import KISService
            import numpy as np
            kis = KISService()
            if not kis.available:
                return jsonify({"error": "KIS not configured"}), 503

            price_data = kis.get_current_price(ticker)
            if not price_data or price_data["price"] == 0:
                return jsonify({"error": f"No price data for {ticker}"}), 404

            bars = kis.get_intraday_bars(ticker)

            score = 50.0
            signals = []
            rsi_val = None
            vol_ratio = None
            price = price_data["price"]
            chg = price_data["change_pct"]
            high = price_data.get("high", 0)
            low = price_data.get("low", 0)
            opn = price_data.get("open", 0)

            # Price momentum
            if chg > 5: score += 20; signals.append({"type":"bullish","msg":f"Surging +{chg:.1f}%","msg_kr":f"급등 +{chg:.1f}%"})
            elif chg > 3: score += 15; signals.append({"type":"bullish","msg":f"Strong rally +{chg:.1f}%","msg_kr":f"강한 상승 +{chg:.1f}%"})
            elif chg > 1: score += 8; signals.append({"type":"bullish","msg":f"Up +{chg:.1f}%","msg_kr":f"상승 +{chg:.1f}%"})
            elif chg < -5: score -= 20; signals.append({"type":"bearish","msg":f"Crashing {chg:.1f}%","msg_kr":f"급락 {chg:.1f}%"})
            elif chg < -3: score -= 15; signals.append({"type":"bearish","msg":f"Sharp drop {chg:.1f}%","msg_kr":f"강한 하락 {chg:.1f}%"})
            elif chg < -1: score -= 8; signals.append({"type":"bearish","msg":f"Down {chg:.1f}%","msg_kr":f"하락 {chg:.1f}%"})

            # Intraday position
            if high > low > 0:
                pos_r = (price - low) / (high - low)
                if pos_r > 0.85: score -= 5; signals.append({"type":"bearish","msg":f"Near intraday high ({pos_r*100:.0f}%)","msg_kr":f"장중 고점 근접 ({pos_r*100:.0f}%)"})
                elif pos_r < 0.15: score += 5; signals.append({"type":"bullish","msg":f"Near intraday low ({pos_r*100:.0f}%)","msg_kr":f"장중 저점 근접 ({pos_r*100:.0f}%)"})

            # Bars analysis
            if bars and len(bars) > 5:
                closes = [b["close"] for b in bars if b["close"] > 0]
                volumes = [b["volume"] for b in bars if b["volume"] > 0]

                if len(closes) >= 14:
                    rsi_val = KISService._calc_rsi(np.array(closes), 14)
                    if rsi_val is not None:
                        if rsi_val < 25: score += 18; signals.append({"type":"bullish","msg":f"RSI extreme oversold ({rsi_val:.0f})","msg_kr":f"RSI 극과매도 ({rsi_val:.0f})"})
                        elif rsi_val < 35: score += 12; signals.append({"type":"bullish","msg":f"RSI oversold ({rsi_val:.0f})","msg_kr":f"RSI 과매도 ({rsi_val:.0f})"})
                        elif rsi_val > 80: score -= 18; signals.append({"type":"bearish","msg":f"RSI extreme overbought ({rsi_val:.0f})","msg_kr":f"RSI 극과매수 ({rsi_val:.0f})"})
                        elif rsi_val > 70: score -= 12; signals.append({"type":"bearish","msg":f"RSI overbought ({rsi_val:.0f})","msg_kr":f"RSI 과매수 ({rsi_val:.0f})"})

                if len(volumes) > 3:
                    avg_v = np.mean(volumes[:-1])
                    if avg_v > 0:
                        vol_ratio = round(volumes[-1] / avg_v, 1)
                        if vol_ratio >= 5: score += 15; signals.append({"type":"bullish","msg":f"Volume explosion {vol_ratio}x","msg_kr":f"거래량 폭발 {vol_ratio}배"})
                        elif vol_ratio >= 3: score += 10; signals.append({"type":"bullish","msg":f"Volume surge {vol_ratio}x","msg_kr":f"거래량 급증 {vol_ratio}배"})

                if len(closes) >= 20:
                    ma5 = np.mean(closes[-5:]); ma20 = np.mean(closes[-20:])
                    if ma5 > ma20 and closes[-1] > ma5: score += 8; signals.append({"type":"bullish","msg":"Short MA > Long MA — uptrend","msg_kr":"단기MA > 중기MA — 상승"})
                    elif ma5 < ma20 and closes[-1] < ma5: score -= 8; signals.append({"type":"bearish","msg":"Short MA < Long MA — downtrend","msg_kr":"단기MA < 중기MA — 하락"})

                if len(closes) >= 6:
                    rc = (closes[-1] - closes[-5]) / closes[-5] * 100
                    if rc > 1.5: signals.append({"type":"bullish","msg":f"Last 5 bars rising +{rc:.1f}%","msg_kr":f"직전 5봉 상승 +{rc:.1f}%"})
                    elif rc < -1.5: signals.append({"type":"bearish","msg":f"Last 5 bars falling {rc:.1f}%","msg_kr":f"직전 5봉 하락 {rc:.1f}%"})

            # Gap
            if opn > 0:
                gap = (price - opn) / opn * 100
                if gap > 3: signals.append({"type":"bullish","msg":f"Gap up +{gap:.1f}%","msg_kr":f"갭 상승 +{gap:.1f}%"})
                elif gap < -3: signals.append({"type":"bearish","msg":f"Gap down {gap:.1f}%","msg_kr":f"갭 하락 {gap:.1f}%"})

            score = max(0, min(100, score))
            signal = "BUY" if score >= 65 else "SELL" if score < 30 else "HOLD"

            # TP/SL based on intraday range
            atr = (high - low) if high > low else price * 0.02
            tp_price = round(price + atr * 0.7)   # Day trade: tight TP
            sl_price = round(price - atr * 0.5)   # Day trade: tight SL
            tp_pct = round((tp_price - price) / price * 100, 2)
            sl_pct = round((sl_price - price) / price * 100, 2)
            trail_pct = round(atr / price * 100, 2)

            return jsonify({
                "ticker": ticker,
                "name": price_data["name"],
                "price": price,
                "change_pct": chg,
                "score": round(score, 1),
                "signal": signal,
                "signals": signals,
                "rsi": round(rsi_val, 1) if rsi_val else None,
                "vwap": None,
                "vol_ratio": vol_ratio,
                "take_profit": tp_price,
                "stop_loss": sl_price,
                "tp_pct": tp_pct,
                "sl_pct": sl_pct,
                "trailing_stop_pct": trail_pct,
                "atr": round(atr),
                "currency": "KRW",
                "is_korean": True,
                "regime_profile": "",
            })
        except Exception as e:
            logger.warning(f"KR daytrade error {ticker}: {e}")
        return jsonify({"error": f"No data for {ticker}"}), 404

    # US stock: use Alpaca
    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503
    r = daytrade.analyze_short_term(ticker)
    if not r:
        return jsonify({"error": f"No intraday data for {ticker}"}), 404
    return jsonify(r)

@app.route("/api/daytrade/chart/<ticker>")
@api_auth
def daytrade_chart(ticker):
    # Korean stock codes → no Alpaca chart data
    if ticker.isdigit() and len(ticker) == 6:
        return jsonify({"ticker": ticker, "timeframe": "1Min", "bars": [], "note": "Korean stocks use KIS"})
    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503
    tf = request.args.get("tf", "5Min")
    limit = int(request.args.get("limit", "100"))
    bars = daytrade.get_intraday_bars(ticker, tf, limit)
    return jsonify({"ticker": ticker.upper(), "timeframe": tf, "bars": bars})

@app.route("/api/daytrade/prices")
@api_auth
def daytrade_prices():
    """Get latest prices for all day trade symbols."""
    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503
    prices = daytrade.get_latest_prices()
    return jsonify({"prices": prices})

@app.route("/api/daytrade/stream")
@api_auth
def daytrade_stream():
    """SSE stream that pushes price updates every 5 seconds."""
    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503

    from flask import Response
    def generate():
        while True:
            try:
                prices = {}
                # US prices (Alpaca)
                if daytrade.available:
                    try:
                        prices.update(daytrade.get_latest_prices() or {})
                    except Exception:
                        pass
                # KR prices (KIS)
                try:
                    from kis_service import KISService
                    kis = KISService()
                    if kis.available:
                        for code in ['005930','000660','035420','005380','006400','051910']:
                            p = kis.get_current_price(code)
                            if p:
                                prices[code] = {"price": p["price"], "change_pct": p["change_pct"]}
                            time.sleep(0.55)
                except Exception:
                    pass
                yield f"data: {json.dumps(prices, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(10)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── Backtest ──────────────────────────────────────────────────────────────────

@app.route("/api/backtest/<ticker>")
@api_auth
def run_backtest(ticker):
    from backtester import Backtester
    period = request.args.get("period", "1y")
    capital = float(request.args.get("capital", "10000"))
    result = Backtester.run(ticker.upper(), period=period, initial_capital=capital)
    if result:
        return jsonify(result)
    return jsonify({"error": f"Backtest failed for {ticker}"}), 500

# ── VIX Strategy ──────────────────────────────────────────────────────────────

@app.route("/api/vix-strategy")
@api_auth
def vix_strategy():
    from quant_models import VIXStrategy
    result = VIXStrategy.analyze()
    if result:
        return jsonify(result)
    return jsonify({"error": "VIX data unavailable"}), 500

# ── Cross-Asset Momentum ──────────────────────────────────────────────────────

_ca_cache = {"data": None, "ts": 0}

@app.route("/api/cross-asset")
@api_auth
def cross_asset():
    import time as _time
    now = _time.time()
    if _ca_cache["data"] and now - _ca_cache["ts"] < 300:  # 5-min cache
        return jsonify(_ca_cache["data"])
    from quant_models import CrossAssetMomentum
    result = CrossAssetMomentum.analyze()
    if result:
        _ca_cache["data"] = result
        _ca_cache["ts"] = now
        return jsonify(result)
    return jsonify({"error": "Insufficient data"}), 500

# ── Auto Trading ──────────────────────────────────────────────────────────────

@app.route("/api/autotrade/status")
@api_auth
def autotrade_status():
    return jsonify(trader.get_status())

@app.route("/api/autotrade/start", methods=["POST"])
@api_auth
def autotrade_start():
    trader._user_id = current_user.id
    return jsonify(trader.start())

@app.route("/api/autotrade/stop", methods=["POST"])
@api_auth
def autotrade_stop():
    return jsonify(trader.stop())

@app.route("/api/autotrade/sell-all", methods=["POST"])
@api_auth
def autotrade_sell_all():
    us_results = trader.force_sell_all()
    kr_results = trader.force_sell_all_kr()
    all_results = us_results.get("results", []) + kr_results
    return jsonify({"results": all_results})

# ── AI Analysis (SWOT, Competitor, Sector Trend) ──────────────────────────────

@app.route("/api/ai/swot", methods=["POST"])
@api_auth
def ai_swot():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_swot(d)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate SWOT"}), 500

@app.route("/api/ai/competitor", methods=["POST"])
@api_auth
def ai_competitor():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    ticker = d.get("ticker", "")
    # Get peers
    peers = []
    all_cached = SignalCache.query.all()
    target_sector = d.get("sector", d.get("snapshot", {}).get("sector", ""))
    for sc in all_cached:
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == target_sector and sc.ticker != ticker:
                peers.append(sd)
        except Exception:
            pass
    result = ai.generate_competitor_analysis(d, peers[:8])
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate competitor analysis"}), 500

@app.route("/api/ai/sector-trend", methods=["POST"])
@api_auth
def ai_sector_trend():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    sector = d.get("sector", "")
    stocks = []
    all_cached = SignalCache.query.all()
    for sc in all_cached:
        try:
            sd = json.loads(sc.data_json) if sc.data_json else {}
            if sd.get("sector") == sector:
                stocks.append(sd)
        except Exception:
            pass
    result = ai.generate_sector_trend(sector, stocks[:10])
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate sector trend"}), 500

# ── Watchlist ──────────────────────────────────────────────────────────────────

@app.route("/api/watchlist")
@api_auth
def get_watchlist():
    items = Watchlist.query.filter_by(user_id=current_user.id).all()
    tickers = [w.ticker for w in items]
    # Get current prices + signals from cache
    out = []
    for w in items:
        c = db.session.get(SignalCache, w.ticker)
        sd = json.loads(c.data_json) if c and c.data_json else {}
        is_kr = w.ticker.upper().endswith(".KS") or w.ticker.upper().endswith(".KQ")
        out.append({
            "id": w.id, "ticker": w.ticker,
            "name": sd.get("name", w.ticker),
            "price": sd.get("price", 0),
            "price_display": sd.get("price_display", "—"),
            "change_pct": sd.get("change_pct", 0),
            "signal": sd.get("signal", "—"),
            "score": sd.get("score", 0),
            "currency": sd.get("currency", "KRW" if is_kr else "USD"),
            "is_korean": sd.get("is_korean", is_kr),
        })
    return jsonify({"watchlist": out})

@app.route("/api/watchlist", methods=["POST"])
@api_auth
def add_watchlist():
    d = request.get_json() or {}
    ticker = (d.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    # Check duplicate
    existing = Watchlist.query.filter_by(user_id=current_user.id, ticker=ticker).first()
    if existing:
        return jsonify({"error": "Already in watchlist"}), 409
    db.session.add(Watchlist(user_id=current_user.id, ticker=ticker))
    db.session.commit()
    # Cache signal if not already cached
    _cache_ticker(ticker, current_user.available_capital)
    return jsonify({"ok": True, "ticker": ticker})

@app.route("/api/watchlist/<int:wid>", methods=["DELETE"])
@api_auth
def remove_watchlist(wid):
    w = db.session.get(Watchlist, wid)
    if not w or w.user_id != current_user.id:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(w)
    db.session.commit()
    return jsonify({"ok": True})

# ── AI Endpoints ──────────────────────────────────────────────────────────────

@app.route("/api/ai/status")
def ai_status():
    return jsonify({"available": ai.available})

@app.route("/api/ai/chat", methods=["POST"])
@api_auth
def ai_chat():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    message = (d.get("message") or "").strip()
    history = d.get("history") or []
    if not message:
        return jsonify({"error": "Message required"}), 400

    positions = Position.query.filter_by(user_id=current_user.id).all()
    sig_cache = {}
    for p in positions:
        c = db.session.get(SignalCache, p.ticker)
        if c and c.data_json:
            sig_cache[p.ticker] = json.loads(c.data_json)

    try:
        macro = fetcher.get_macro_data()
    except Exception:
        macro = {}

    context = ai.build_portfolio_context(current_user, positions, sig_cache, macro)

    from flask import Response
    def generate():
        try:
            for chunk in ai.chat_stream(message, history, context):
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/ai/commentary", methods=["POST"])
@api_auth
def ai_commentary():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_commentary(d)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate commentary"}), 500

@app.route("/api/ai/morning-summary", methods=["POST"])
@api_auth
def ai_morning_summary():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    d = request.get_json() or {}
    result = ai.generate_morning_summary(d)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate summary"}), 500

@app.route("/api/ai/coaching", methods=["POST"])
@api_auth
def ai_coaching():
    if not ai.available:
        return jsonify({"error": "AI not configured"}), 503
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"insight": "Add some positions first to get AI coaching!", "insight_kr": "AI 코칭을 받으려면 먼저 포지션을 추가하세요!"})
    sig_cache = {}
    for p in positions:
        c = db.session.get(SignalCache, p.ticker)
        if c and c.data_json:
            sig_cache[p.ticker] = json.loads(c.data_json)
    context = ai.build_portfolio_context(current_user, positions, sig_cache)
    result = ai.generate_coaching(context)
    if result:
        return jsonify(result)
    return jsonify({"error": "Failed to generate coaching"}), 500

# ── Helpers ────────────────────────────────────────────────────────────────────

def _u(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name,
            "available_capital":     u.available_capital,
            "available_capital_krw": getattr(u, "available_capital_krw", 0.0) or 0.0}

def _trade(t: TradeHistory) -> dict:
    return {
        "id": t.id, "ticker": t.ticker, "name": t.name,
        "action": t.action, "shares": t.shares,
        "price_per_share": t.price_per_share, "total_value": t.total_value,
        "pnl": t.pnl, "pnl_pct": t.pnl_pct, "currency": t.currency,
        "traded_at": t.traded_at.isoformat(),
    }

def _al(a: Alert) -> dict:
    return {"id": a.id, "ticker": a.ticker, "message": a.message,
            "signal": a.signal, "score": a.score,
            "rec_shares": a.rec_shares, "rec_investment": a.rec_investment,
            "created_at": a.created_at.isoformat(), "is_read": a.is_read}

def _save_cache(ticker: str, data: dict):
    c = db.session.get(SignalCache, ticker)
    if c:
        c.data_json = json.dumps(data, ensure_ascii=False)
        c.updated_at = datetime.utcnow()
    else:
        db.session.add(SignalCache(ticker=ticker,
                                   data_json=json.dumps(data, ensure_ascii=False)))
    db.session.commit()

def _cache_ticker(ticker: str, capital: float):
    try:
        r = engine.analyze(ticker, capital)
        if r: _save_cache(ticker, r)
    except Exception as e:
        logger.error(f"Cache update failed {ticker}: {e}")

def _maybe_alert(user_id: int, r: dict):
    sig = r.get("signal")
    if sig not in ("BUY", "SELL"): return

    # Only alert during market hours
    from zoneinfo import ZoneInfo
    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    is_kr = r.get("is_korean", False)
    if is_kr:
        kst = now_utc.astimezone(ZoneInfo("Asia/Seoul"))
        kr_min = kst.hour * 60 + kst.minute
        if kst.weekday() >= 5 or not (540 <= kr_min < 930):
            return  # KR market closed
    else:
        et = now_utc.astimezone(ZoneInfo("America/New_York"))
        us_min = et.hour * 60 + et.minute
        if et.weekday() >= 5 or not (570 <= us_min < 960):
            return  # US market closed

    ticker = r["ticker"]
    name   = r.get("name", ticker)
    score  = r.get("score", 0)
    recent = (Alert.query.filter_by(user_id=user_id, ticker=ticker)
              .filter(Alert.created_at > datetime.utcnow() - timedelta(hours=4))
              .first())
    if recent: return
    cur = "₩" if r.get("is_korean") else "$"
    if sig == "BUY":
        sh, inv, tim = r.get("rec_shares", 0), r.get("rec_investment", 0), r.get("rec_timing", "")
        inv_str = f"{cur}{inv:,.0f}" if inv > 0 else "set capital for sizing"
        msg = (f"[BUY] {name} ({ticker}) — Score {score:.0f}/100. "
               f"Rec: {sh} shares · {inv_str}. {tim}.")
    else:
        sell_pct = r.get("sell_pct", 50)
        msg = (f"[SELL] {name} ({ticker}) — Score {score:.0f}/100. "
               f"Quant flags weakness. Consider selling {sell_pct}% of position.")
    db.session.add(Alert(user_id=user_id, ticker=ticker, message=msg,
                         signal=sig, score=score))
    db.session.commit()

# ── Scheduler ──────────────────────────────────────────────────────────────────

def _scheduled_refresh():
    with app.app_context():
        positions = Position.query.all()
        users     = {u.id: u for u in User.query.all()}
        tku: dict[str, list[int]] = {}
        for p in positions:
            tku.setdefault(p.ticker, []).append(p.user_id)
        for ticker, uids in tku.items():
            cap = users[uids[0]].available_capital if uids[0] in users else 10_000
            try:
                r = engine.analyze(ticker, cap)
                if r:
                    _save_cache(ticker, r)
                    for uid in uids:
                        _maybe_alert(uid, r)
            except Exception as e:
                logger.error(f"Scheduler failed {ticker}: {e}")
        logger.info(f"Scheduled refresh done — {len(tku)} tickers")

# ── Init ───────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    # Migrate: add KRW capital column for existing DBs
    from sqlalchemy import text as _text
    with db.engine.connect() as _conn:
        try:
            _conn.execute(_text(
                "ALTER TABLE users ADD COLUMN available_capital_krw FLOAT DEFAULT 0.0"
            ))
            _conn.commit()
        except Exception:
            pass  # Column already exists

    # Auto-populate signal cache on startup if empty
    try:
        positions = Position.query.all()
        tickers = list(set(p.ticker for p in positions))
        cached = set(c.ticker for c in SignalCache.query.all())
        missing = [t for t in tickers if t not in cached]
        if missing:
            logger.info(f"Populating signal cache for {len(missing)} tickers on startup...")
            for ticker in missing:
                try:
                    r = engine.analyze(ticker, 10000)
                    if r:
                        _save_cache(ticker, r)
                        logger.info(f"  Cached: {ticker}")
                except Exception as e:
                    logger.error(f"  Failed to cache {ticker}: {e}")
            logger.info("Startup cache population complete.")
    except Exception as e:
        logger.error(f"Startup cache error: {e}")

sched = BackgroundScheduler(timezone="UTC")
sched.add_job(_scheduled_refresh, "interval", minutes=3, id="refresh")
sched.start()

if __name__ == "__main__":
    app.run(debug=False, port=5050, host="0.0.0.0", use_reloader=False)
