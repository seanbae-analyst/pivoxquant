"""Web Push subscription routes.

2026-05-17 wave 13 structure P1 (PR #437): ``send_push_to_user``
moved from here to ``services/push_service.py`` (its proper layer —
it never was a route handler, it was a service function in the wrong
file). The re-export below preserves any external caller that still
has ``from routes.push import send_push_to_user`` in their import
path.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models import PushSubscription
from services.push_service import send_push_to_user  # noqa: F401 — re-export
from .decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

push_bp = Blueprint("push", __name__, url_prefix="/api/push")


@push_bp.route("/subscribe", methods=["POST"])
@api_auth
@general_rate_limit
def subscribe():
    """Save a push subscription for the current user."""
    data = request.get_json(force=True)
    sub = data.get("subscription")
    if not sub or not sub.get("endpoint"):
        return jsonify({"error": "Invalid subscription"}), 400

    keys = sub.get("keys", {})
    endpoint = sub["endpoint"]

    # Upsert: replace if same endpoint exists.
    # 2026-05-17 wave 14 P2 (PR #450): the previous unconditional
    # ``existing.user_id = current_user.id`` reassignment let any
    # authenticated caller claim a subscription by submitting the
    # endpoint URL with their own auth cookie — silent victim
    # de-registration + attacker receives victim's push payloads on
    # their device. Endpoint URLs contain a long opaque token so
    # guessing is impractical, but URLs leak via shared logs / proxy
    # mirrors / browser history. Refuse to silently reassign — if
    # the endpoint is bound to a different user we 409 so the client
    # knows the URL is taken (matches the watchlist duplicate UX).
    # Same-user resubscribe (browser reset, new install) still
    # rotates the keys + extends lifetime.
    try:
        existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
        if existing:
            if existing.user_id != current_user.id:
                logger.warning(
                    "push subscribe rejected: endpoint already bound to "
                    "user_id=%s, requester user_id=%s",
                    existing.user_id, current_user.id,
                )
                return jsonify({
                    "error": "Subscription endpoint already registered",
                    "error_kr": "이미 다른 계정에 등록된 푸시 endpoint 입니다.",
                    "code": "PUSH_ENDPOINT_OWNED",
                }), 409
            existing.p256dh = keys.get("p256dh", "")
            existing.auth = keys.get("auth", "")
        else:
            db.session.add(PushSubscription(
                user_id=current_user.id,
                endpoint=endpoint,
                p256dh=keys.get("p256dh", ""),
                auth=keys.get("auth", ""),
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("push.subscribe commit failed (user_id=%s)", current_user.id)
        return jsonify({"error": "Failed to save push subscription"}), 500
    return jsonify({"ok": True})


@push_bp.route("/unsubscribe", methods=["POST"])
@api_auth
@general_rate_limit
def unsubscribe():
    """Remove a push subscription."""
    data = request.get_json(force=True)
    endpoint = data.get("endpoint", "")
    try:
        if endpoint:
            PushSubscription.query.filter_by(
                user_id=current_user.id, endpoint=endpoint
            ).delete()
        else:
            # Remove all subscriptions for user
            PushSubscription.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("push.unsubscribe commit failed (user_id=%s)", current_user.id)
        return jsonify({"error": "Failed to unsubscribe"}), 500
    return jsonify({"ok": True})


@push_bp.route("/status")
@api_auth
def status():
    """Check if user has active push subscriptions."""
    count = PushSubscription.query.filter_by(user_id=current_user.id).count()
    return jsonify({"subscribed": count > 0, "count": count})


# send_push_to_user moved to services/push_service.py (PR #437) —
# re-exported at the top of this file so existing callers still work.
