"""Alert routes."""
import json
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify
from flask_login import current_user

from extensions import db
from models import Position, Alert, SignalCache
from services.serializers import serialize_alert
from .decorators import api_auth

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@alerts_bp.route("")
@api_auth
def get_alerts():
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    Alert.query.filter(Alert.user_id == current_user.id, Alert.created_at < cutoff).delete()
    db.session.commit()
    alerts = (Alert.query.filter_by(user_id=current_user.id)
              .order_by(Alert.created_at.desc()).limit(20).all())
    return jsonify({
        "alerts": [serialize_alert(a) for a in alerts],
        "unread": sum(1 for a in alerts if not a.is_read),
    })


@alerts_bp.route("/read", methods=["POST"])
@api_auth
def mark_read():
    Alert.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})


@alerts_bp.route("/clear", methods=["POST"])
@api_auth
def clear():
    Alert.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True})


@alerts_bp.route("/price-check")
@api_auth
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
        name = sd.get("name", p.ticker)
        cur = "₩" if sd.get("is_korean") else "$"
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

    return jsonify({"alerts": alerts})
