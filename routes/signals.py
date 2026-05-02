"""Signal analysis routes."""
import json
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Position, SignalCache, InvestmentProfile
from services import fx_service, cache_service, alert_service
from services.container import engine
from services.name_resolver import resolve_stock_name
from services.access_guard import is_user_allowed_ticker, access_denied_response
from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit


def _get_profile_params():
    """Get current user's investment profile engine params, or None."""
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    return profile.to_engine_params() if profile else None

signals_bp = Blueprint("signals", __name__, url_prefix="/api")


@signals_bp.route("/signals")
@api_auth
@legal_scrub_response
def get_signals():
    tickers = {p.ticker for p in Position.query.filter_by(user_id=current_user.id).all()}
    out = []
    for t in tickers:
        c = SignalCache.query.get(t)
        if c and c.data_json:
            try:
                d = json.loads(c.data_json)
            except json.JSONDecodeError:
                d = {}
            stale = c.is_stale()
            d["cached_at"] = c.updated_at.isoformat()
            d["observed_at"] = c.updated_at.isoformat()
            d["is_stale"] = stale
            # Backfill name: SignalCache blobs are populated by engine.analyze()
            # which may emit bare ticker when the broker snapshot lacks a name.
            # resolve_stock_name guarantees 회사명 for every KRX/US listing.
            if not d.get("name") or d.get("name") == t:
                d["name"] = resolve_stock_name(t) or t
            d.setdefault("ticker", t)
            out.append(d)

            # Best-effort background refresh when stale so subsequent reads
            # see fresh data. Never blocks the current response.
            if stale:
                try:
                    from threading import Thread
                    from flask import current_app
                    app_obj = current_app._get_current_object()
                    capital = current_user.available_capital

                    def _refresh(ticker=t, cap=capital, app=app_obj):
                        with app.app_context():
                            try:
                                cache_service.cache_ticker(ticker, cap, engine)
                            except Exception:
                                pass

                    Thread(target=_refresh, daemon=True).start()
                except Exception:
                    pass
        else:
            # No row at all — surface as stale so the client can show "—" / skeleton.
            out.append({
                "ticker": t,
                "name": resolve_stock_name(t) or t,
                "observed_at": None,
                "is_stale": True,
            })
    return jsonify({"signals": out})


@signals_bp.route("/signals/<ticker>")
@api_auth
@legal_scrub_response
def signal_detail(ticker):
    t_up = ticker.upper()
    # §101 회피 — 보유/watchlist 종목만 분석 허용.
    if not is_user_allowed_ticker(current_user.id, t_up):
        body, status = access_denied_response()
        return jsonify(body), status
    r = engine.analyze(t_up, current_user.available_capital,
                       getattr(current_user, "available_capital_krw", 0.0) or 0.0,
                       fx_rate=fx_service.get_rate(),
                       profile_params=_get_profile_params())
    if not r:
        cached = db.session.get(SignalCache, t_up)
        if cached and cached.data_json:
            d = json.loads(cached.data_json)
            if not d.get("name") or d.get("name") == t_up:
                d["name"] = resolve_stock_name(t_up) or t_up
            return jsonify(d)
        return jsonify({"error": f"Analysis failed for '{ticker}'. Check the ticker symbol."}), 404
    cache_service.save_signal(t_up, r)
    if not r.get("name") or r.get("name") == t_up:
        r["name"] = resolve_stock_name(t_up) or t_up
    return jsonify(r)


@signals_bp.route("/signals/refresh", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def refresh():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    pos_map = {p.ticker: p for p in positions}
    done = []
    for t, p in pos_map.items():
        cached = SignalCache.query.get(t)
        cur_price = json.loads(cached.data_json).get("price", p.avg_cost) if cached and cached.data_json else p.avg_cost
        pnl_pct = (cur_price - p.avg_cost) / p.avg_cost * 100 if p.avg_cost > 0 else 0
        r = engine.analyze(t, current_user.available_capital,
                           getattr(current_user, "available_capital_krw", 0.0) or 0.0,
                           fx_rate=fx_service.get_rate(), current_pnl_pct=pnl_pct,
                           profile_params=_get_profile_params())
        if r:
            cache_service.save_signal(t, r)
            alert_service.maybe_generate(current_user.id, r)
            done.append(t)
    return jsonify({"ok": True, "refreshed": done})


@signals_bp.route("/scan", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def scan():
    ticker = ((request.get_json() or {}).get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
    # §101 회피 — 보유/watchlist 종목만 스캔 허용.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status
    r = engine.analyze(ticker, current_user.available_capital,
                       getattr(current_user, "available_capital_krw", 0.0) or 0.0,
                       fx_rate=fx_service.get_rate(),
                       profile_params=_get_profile_params())
    if not r:
        cached = db.session.get(SignalCache, ticker)
        if cached and cached.data_json:
            d = json.loads(cached.data_json)
            if not d.get("name") or d.get("name") == ticker:
                d["name"] = resolve_stock_name(ticker) or ticker
            return jsonify(d)
        return jsonify({"error": f"Analysis failed for '{ticker}'"}), 404
    if not r.get("name") or r.get("name") == ticker:
        r["name"] = resolve_stock_name(ticker) or ticker
    return jsonify(r)
