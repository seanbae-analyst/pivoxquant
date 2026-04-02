"""
StockPilot — Flask Backend v2
New endpoints: /api/morning-brief  /api/market/overview  /api/portfolio/analytics
Supports US + Korean equities. Zero AI API cost.
"""

import os, json, logging, time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

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
            "tp_pct":         sd.get("tp_pct", 20),
            "sl_pct":         sd.get("sl_pct", -8),
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
    """Fast batch price update — uses fast_info, much quicker than full analysis."""
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers   = [p.ticker for p in positions]
    if not tickers:
        return jsonify({"prices": {}})
    prices = fetcher.get_prices_batch(tickers)
    # Update cached signal data with fresh prices only
    for ticker, pdata in prices.items():
        c = db.session.get(SignalCache, ticker)
        if c and c.data_json:
            try:
                sd = json.loads(c.data_json)
                sd["price"]         = pdata["price"]
                sd["price_display"] = pdata["price_display"]
                c.data_json  = json.dumps(sd, ensure_ascii=False)
                c.updated_at = datetime.utcnow()
            except Exception:
                pass
    db.session.commit()
    return jsonify({"prices": prices, "updated_at": datetime.utcnow().isoformat()})

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
sched.add_job(_scheduled_refresh, "interval", minutes=15, id="refresh")
sched.start()

if __name__ == "__main__":
    app.run(debug=False, port=5050, host="0.0.0.0", use_reloader=False)
