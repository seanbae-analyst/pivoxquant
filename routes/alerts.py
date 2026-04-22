"""Alert routes."""
import json
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify
from flask_login import current_user

from extensions import db
from models import Position, Alert, SignalCache
from services.serializers import serialize_alert
from services.name_resolver import resolve_stock_name
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@alerts_bp.route("")
@api_auth
@legal_scrub_response
def get_alerts():
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    # TTL cleanup — best-effort. Must never break the GET if the delete fails
    # (e.g. row-lock contention); the read path below is what matters.
    try:
        Alert.query.filter(
            Alert.user_id == current_user.id, Alert.created_at < cutoff
        ).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.get_alerts TTL cleanup failed")
    alerts = (Alert.query.filter_by(user_id=current_user.id)
              .order_by(Alert.created_at.desc()).limit(20).all())
    return jsonify({
        "alerts": [serialize_alert(a) for a in alerts],
        "unread": sum(1 for a in alerts if not a.is_read),
    })


@alerts_bp.route("/read", methods=["POST"])
@api_auth
def mark_read():
    try:
        Alert.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.mark_read commit failed")
        return jsonify({"error": "Failed to update alerts"}), 500
    return jsonify({"ok": True})


@alerts_bp.route("/clear", methods=["POST"])
@api_auth
def clear():
    try:
        Alert.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.clear commit failed")
        return jsonify({"error": "Failed to clear alerts"}), 500
    return jsonify({"ok": True})


@alerts_bp.route("/price-check")
@api_auth
@legal_scrub_response
def price_check():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    alerts = []
    for p in positions:
        c = SignalCache.query.get(p.ticker)
        if not c or not c.data_json:
            continue
        sd = json.loads(c.data_json)
        price = sd.get("price", 0)
        tp = sd.get("take_profit")
        sl = sd.get("stop_loss")
        name = sd.get("name") or resolve_stock_name(p.ticker) or p.ticker
        cur = "₩" if sd.get("is_korean") else "$"
        if tp and price >= tp:
            alerts.append({"ticker": p.ticker, "name": name, "type": "TAKE_PROFIT",
                           "price": price, "target": tp, "shares": p.shares,
                           "proceeds": round(p.shares * price),
                           "message": f"🎯 {name} 사전 설정 TP 레벨 도달 — 정보 고지 ({cur}{round(price):,} ≥ {cur}{round(tp):,}, 보유 {p.shares}주)"})
        elif sl and price <= sl:
            alerts.append({"ticker": p.ticker, "name": name, "type": "STOP_LOSS",
                           "price": price, "target": sl, "shares": p.shares,
                           "proceeds": round(p.shares * price),
                           "message": f"🛑 {name} 사전 설정 SL 레벨 도달 — 정보 고지 ({cur}{round(price):,} ≤ {cur}{round(sl):,}, 보유 {p.shares}주)"})

    try:
        for a in alerts:
            recent = (Alert.query.filter_by(user_id=current_user.id, ticker=a["ticker"])
                      .filter(Alert.message.contains(a["type"]))
                      .filter(Alert.created_at > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4))
                      .first())
            if not recent:
                sig = "NEGATIVE" if a["type"] == "STOP_LOSS" else "POSITIVE"
                db.session.add(Alert(user_id=current_user.id, ticker=a["ticker"],
                                     message=a["message"], signal=sig, score=0))
        if alerts:
            db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.price_check persist failed")
        # Still return the alerts payload — persistence is a side-effect,
        # not the primary purpose of this endpoint.

    return jsonify({"alerts": alerts})
