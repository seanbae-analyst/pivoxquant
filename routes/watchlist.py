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


def _serialize(w: Watchlist) -> dict:
    """Build the response payload for a watchlist row.

    Pulls last-price + 1D% from the SignalCache row (warmed on add) so we
    don't burn an FMP quote call on every list render. Falls back to a
    live `get_quote` only when the cache is empty.
    """
    c = db.session.get(SignalCache, w.ticker)
    sd = json.loads(c.data_json) if c and c.data_json else {}
    is_kr = w.ticker.upper().endswith(".KS") or w.ticker.upper().endswith(".KQ")

    last_price = sd.get("price")
    change_1d_pct = sd.get("change_pct")
    # Best-effort fill from FMP quote if the cache row is missing price data.
    # Never raise — watchlist must render even when FMP is budget-capped.
    if last_price is None:
        try:
            import fmp_service
            q = fmp_service.get_quote(w.ticker) or {}
            last_price = q.get("price")
            change_1d_pct = q.get("changesPercentage")
        except Exception:
            logger.exception("watchlist serialize quote fallback failed (ticker=%s)", w.ticker)

    return {
        "id": w.id,
        "ticker": w.ticker,
        "name": sd.get("name") or resolve_stock_name(w.ticker) or w.ticker,
        "note": w.note or "",
        "added_at": w.added_at.isoformat() if w.added_at else None,
        "price": last_price or 0,
        "last_price": last_price or 0,
        "price_display": sd.get("price_display", "—"),
        "change_pct": change_1d_pct or 0,
        "change_1d_pct": change_1d_pct or 0,
        "signal": sd.get("signal", "—"),
        "score": sd.get("score", 0),
        "currency": sd.get("currency", "KRW" if is_kr else "USD"),
        "is_korean": sd.get("is_korean", is_kr),
    }


@watchlist_bp.route("")
@api_auth
def get_watchlist():
    items = (Watchlist.query
             .filter_by(user_id=current_user.id)
             .order_by(Watchlist.added_at.desc())
             .all())
    out = [_serialize(w) for w in items]
    return jsonify({"watchlist": out})


@watchlist_bp.route("", methods=["POST"])
@api_auth
def add():
    d = request.get_json() or {}
    ticker = (d.get("ticker") or "").strip().upper()
    note = (d.get("note") or "").strip() or None
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
    if note and len(note) > 500:
        return jsonify({"error": "Note too long (max 500 characters)"}), 400
    if ticker.isdigit() and len(ticker) == 6:
        ticker += ".KS"
    existing = Watchlist.query.filter_by(user_id=current_user.id, ticker=ticker).first()
    if existing:
        return jsonify({"error": "Already in watchlist"}), 409
    try:
        row = Watchlist(user_id=current_user.id, ticker=ticker, note=note)
        db.session.add(row)
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
    return jsonify({"ok": True, "ticker": ticker, "item": _serialize(row)})


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


@watchlist_bp.route("/<int:wid>", methods=["PATCH"])
@api_auth
def update(wid):
    """Patch the note on an existing watchlist row.

    Payload: {"note": "..."}   — empty string clears the note.
    Body is intentionally narrow: ticker changes are disallowed (delete +
    re-add instead), and we don't let the client rewrite added_at.
    """
    w = db.session.get(Watchlist, wid)
    if not w or w.user_id != current_user.id:
        return jsonify({"error": "Not found"}), 404
    d = request.get_json() or {}
    if "note" in d:
        raw = d.get("note")
        if raw is None:
            w.note = None
        else:
            s = str(raw).strip()
            if len(s) > 500:
                return jsonify({"error": "Note too long (max 500 characters)"}), 400
            w.note = s or None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("watchlist.update commit failed (wid=%s)", wid)
        return jsonify({"error": "Failed to update watchlist"}), 500
    return jsonify({"ok": True, "item": _serialize(w)})
