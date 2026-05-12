"""Watchlist routes."""
from __future__ import annotations

import json
import logging

from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Watchlist, SignalCache
from services import cache_service
from services.container import engine
from services.name_resolver import canonical_display_name
from services.price_overlay import overlay_prices, parse_price_display
from services.ticker_normalizer import normalize_ticker
from .decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

watchlist_bp = Blueprint("watchlist", __name__, url_prefix="/api/watchlist")


def _serialize(w: Watchlist, overlay_entry: dict | None = None) -> dict:
    """Build the response payload for a watchlist row.

    Preferred price source: realtime/non-stale overlay (Alpaca/KIS/SignalCache).
    Falls back to the blob-only cache (even stale) for non-price metadata like
    name / signal / score. Price fields stay 0 when no fresh source exists —
    we never render a days-old number as "current".
    """
    c = db.session.get(SignalCache, w.ticker)
    sd = json.loads(c.data_json) if c and c.data_json else {}
    is_kr = w.ticker.upper().endswith(".KS") or w.ticker.upper().endswith(".KQ")

    o = overlay_entry or {}
    last_price = o.get("price")
    change_1d_pct = o.get("change_pct")
    observed_at = o.get("observed_at")
    price_source = o.get("source") or "stale"

    # Bug-hunter 2026-04-30: when the price overlay is empty/stale, fall
    # back to SignalCache.data_json["change_pct"] (populated by signal
    # cache builders + price_overlay.py:130). Without this fallback every
    # watchlist row showed +0.00% even though detail/signals pages had
    # the real change. Prefer stale-but-real over fake-zero.
    if change_1d_pct is None and "change_pct" in sd:
        try:
            change_1d_pct = float(sd.get("change_pct"))
        except (TypeError, ValueError):
            change_1d_pct = None

    # Bug C (2026-04-24): Watchlist used to render "$0.0000" whenever the
    # overlay came up empty, even though SignalCache stored a valid
    # `price_display` like "$402.91". Derive a last-resort numeric price
    # from the display string so UI never shows $0 when a legible value
    # exists. Mark source "stale" so the UX chip is honest.
    if not last_price:
        parsed = parse_price_display(sd.get("price_display"))
        if parsed:
            last_price = parsed
            if not price_source or price_source == "stale":
                price_source = "stale_display"

    return {
        "id": w.id,
        "ticker": w.ticker,
        "name": canonical_display_name(sd.get("name"), w.ticker),
        "note": w.note or "",
        "added_at": w.added_at.isoformat() if w.added_at else None,
        "price": last_price or 0,
        "last_price": last_price or 0,
        "price_display": sd.get("price_display", "—"),
        "change_pct": change_1d_pct or 0,
        "change_1d_pct": change_1d_pct or 0,
        "observed_at": observed_at,
        "price_source": price_source,
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
    overlay = overlay_prices([w.ticker for w in items])
    out = [_serialize(w, overlay.get(w.ticker)) for w in items]
    return jsonify({"watchlist": out})


@watchlist_bp.route("", methods=["POST"])
@api_auth
@general_rate_limit
def add():
    d = request.get_json() or {}
    raw = (d.get("ticker") or "").strip()
    note = (d.get("note") or "").strip() or None
    if not raw:
        return jsonify({"error": "Ticker required"}), 400
    if note and len(note) > 500:
        return jsonify({"error": "Note too long (max 500 characters)"}), 400
    # Single-source normalization: bare 6-digit code → registry-guided
    # .KS/.KQ. Replaces the ad-hoc default-to-.KS rule that mis-routed
    # KOSDAQ tickers (e.g. 035760 CJ ENM).
    ticker = normalize_ticker(raw)
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
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
    overlay = overlay_prices([ticker])
    return jsonify({"ok": True, "ticker": ticker, "item": _serialize(row, overlay.get(ticker))})


@watchlist_bp.route("/<int:wid>", methods=["DELETE"])
@api_auth
@general_rate_limit
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
@general_rate_limit
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
    overlay = overlay_prices([w.ticker])
    return jsonify({"ok": True, "item": _serialize(w, overlay.get(w.ticker))})
