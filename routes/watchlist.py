"""Watchlist routes."""
import json
import logging

from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Watchlist, SignalCache
from services import cache_service
from services.container import engine
from services.name_resolver import resolve_stock_name
from .decorators import api_auth

logger = logging.getLogger(__name__)

watchlist_bp = Blueprint("watchlist", __name__, url_prefix="/api/watchlist")


@watchlist_bp.route("")
@api_auth
def get_watchlist():
    items = Watchlist.query.filter_by(user_id=current_user.id).all()
    out = []
    for w in items:
        c = db.session.get(SignalCache, w.ticker)
        sd = json.loads(c.data_json) if c and c.data_json else {}
        is_kr = w.ticker.upper().endswith(".KS") or w.ticker.upper().endswith(".KQ")
        out.append({
            "id": w.id, "ticker": w.ticker,
            "name": sd.get("name") or resolve_stock_name(w.ticker) or w.ticker,
            "price": sd.get("price", 0),
            "price_display": sd.get("price_display", "—"),
            "change_pct": sd.get("change_pct", 0),
            "signal": sd.get("signal", "—"),
            "score": sd.get("score", 0),
            "currency": sd.get("currency", "KRW" if is_kr else "USD"),
            "is_korean": sd.get("is_korean", is_kr),
        })
    return jsonify({"watchlist": out})


@watchlist_bp.route("", methods=["POST"])
@api_auth
def add():
    d = request.get_json() or {}
    ticker = (d.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    existing = Watchlist.query.filter_by(user_id=current_user.id, ticker=ticker).first()
    if existing:
        return jsonify({"error": "Already in watchlist"}), 409
    try:
        db.session.add(Watchlist(user_id=current_user.id, ticker=ticker))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("watchlist.add commit failed (ticker=%s)", ticker)
        return jsonify({"error": "Failed to add to watchlist"}), 500
    # Best-effort cache warm — never block the response on cache failures.
    try:
        cache_service.cache_ticker(ticker, current_user.available_capital, engine)
    except Exception:
        logger.exception("watchlist.add cache_ticker failed (ticker=%s)", ticker)
    return jsonify({"ok": True, "ticker": ticker})


@watchlist_bp.route("/<int:wid>", methods=["DELETE"])
@api_auth
def remove(wid):
    w = db.session.get(Watchlist, wid)
    if not w or w.user_id != current_user.id:
        return jsonify({"error": "Not found"}), 404
    try:
        db.session.delete(w)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("watchlist.remove commit failed (wid=%s)", wid)
        return jsonify({"error": "Failed to remove from watchlist"}), 500
    return jsonify({"ok": True})
