"""Alert routes.

Two groups of endpoints:

Legacy (kept for backwards compatibility — price_check et al.):
    GET  /api/alerts                 → {alerts: [...], unread: N}
    POST /api/alerts/read            → mark all read (legacy shape)
    POST /api/alerts/clear           → delete all
    GET  /api/alerts/price-check     → on-demand TP/SL scan

Bell-dropdown (added 2026-04-22, kind/title/body contract):
    GET    /api/alerts/unread-count  → {count: N}
    POST   /api/alerts/read-all      → mark all read (new shape {ok: true})
    POST   /api/alerts/<id>/read     → mark one read
    DELETE /api/alerts/<id>          → delete one

The bare `GET /api/alerts` response is enriched: each element now carries
`kind`, `title`, `body`, `link`, `read_at` alongside legacy fields so the
new NotificationDropdown and legacy /alerts page can share it.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models import Position, Alert, SignalCache
from services.serializers import serialize_alert
from services.name_resolver import resolve_stock_name
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


# ── Legacy list endpoint (enriched with bell fields) ───────────────────────

@alerts_bp.route("")
@api_auth
@legal_scrub_response
def get_alerts():
    """Return up to `limit` alerts (default 20, max 50).

    Response shape preserves the legacy `{alerts, unread}` envelope but
    each alert now carries the new bell-dropdown fields.
    """
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(limit, 50))

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
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
              .order_by(Alert.created_at.desc()).limit(limit).all())
    return jsonify({
        "alerts": [serialize_alert(a) for a in alerts],
        "unread": sum(1 for a in alerts if not a.is_read),
    })


# ── New bell-dropdown endpoints ────────────────────────────────────────────

@alerts_bp.route("/unread-count")
@api_auth
def unread_count():
    try:
        count = Alert.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()
    except Exception:
        logger.exception("alerts.unread_count failed")
        return jsonify({"count": 0}), 500
    return jsonify({"count": int(count)})


@alerts_bp.route("/read-all", methods=["POST"])
@api_auth
def read_all():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        Alert.query.filter_by(user_id=current_user.id, is_read=False).update(
            {"is_read": True, "read_at": now}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.read_all commit failed")
        return jsonify({"error": "Failed to update alerts"}), 500
    return jsonify({"ok": True})


@alerts_bp.route("/<int:alert_id>/read", methods=["POST"])
@api_auth
def mark_one_read(alert_id: int):
    a = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first()
    if a is None:
        return jsonify({"error": "Not found"}), 404
    try:
        a.is_read = True
        a.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.mark_one_read commit failed id=%s", alert_id)
        return jsonify({"error": "Failed to update alert"}), 500
    return jsonify({"ok": True})


@alerts_bp.route("/<int:alert_id>", methods=["DELETE"])
@api_auth
def delete_one(alert_id: int):
    a = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first()
    if a is None:
        return jsonify({"error": "Not found"}), 404
    try:
        db.session.delete(a)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.delete_one commit failed id=%s", alert_id)
        return jsonify({"error": "Failed to delete alert"}), 500
    return jsonify({"ok": True})


# ── Legacy mark-all-read and clear (kept for /alerts page) ─────────────────

@alerts_bp.route("/read", methods=["POST"])
@api_auth
def mark_read():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        Alert.query.filter_by(user_id=current_user.id, is_read=False).update(
            {"is_read": True, "read_at": now}
        )
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
                           "message": f"{name} 사전 설정 TP 레벨 도달 — 정보 고지 ({cur}{round(price):,} ≥ {cur}{round(tp):,}, 보유 {p.shares}주)"})
        elif sl and price <= sl:
            alerts.append({"ticker": p.ticker, "name": name, "type": "STOP_LOSS",
                           "price": price, "target": sl, "shares": p.shares,
                           "proceeds": round(p.shares * price),
                           "message": f"{name} 사전 설정 SL 레벨 도달 — 정보 고지 ({cur}{round(price):,} ≤ {cur}{round(sl):,}, 보유 {p.shares}주)"})

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
