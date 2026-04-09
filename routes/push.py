"""Web Push subscription routes."""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models import PushSubscription
from .decorators import api_auth

logger = logging.getLogger(__name__)

push_bp = Blueprint("push", __name__, url_prefix="/api/push")


@push_bp.route("/subscribe", methods=["POST"])
@api_auth
def subscribe():
    """Save a push subscription for the current user."""
    data = request.get_json(force=True)
    sub = data.get("subscription")
    if not sub or not sub.get("endpoint"):
        return jsonify({"error": "Invalid subscription"}), 400

    keys = sub.get("keys", {})
    endpoint = sub["endpoint"]

    # Upsert: replace if same endpoint exists
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.user_id = current_user.id
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
    return jsonify({"ok": True})


@push_bp.route("/unsubscribe", methods=["POST"])
@api_auth
def unsubscribe():
    """Remove a push subscription."""
    data = request.get_json(force=True)
    endpoint = data.get("endpoint", "")
    if endpoint:
        PushSubscription.query.filter_by(
            user_id=current_user.id, endpoint=endpoint
        ).delete()
    else:
        # Remove all subscriptions for user
        PushSubscription.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True})


@push_bp.route("/status")
@api_auth
def status():
    """Check if user has active push subscriptions."""
    count = PushSubscription.query.filter_by(user_id=current_user.id).count()
    return jsonify({"subscribed": count > 0, "count": count})


def send_push_to_user(user_id: int, title: str, body: str,
                      url: str = "/alerts", actions: Optional[list] = None):
    """Send push notification to all subscriptions for a user.

    Call this from services (e.g. alert_service) after creating an alert.
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed — skipping push notification")
        return

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_email = os.environ.get("VAPID_EMAIL", "mailto:admin@stockpilot.app")

    if not vapid_private:
        logger.warning("VAPID_PRIVATE_KEY not set — skipping push notification")
        return

    subs = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subs:
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "actions": actions or [],
    })

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_email},
            )
        except Exception as e:
            err_msg = str(e)
            # Remove expired/invalid subscriptions
            if "410" in err_msg or "404" in err_msg:
                logger.info(f"Removing expired push subscription {sub.id}")
                db.session.delete(sub)
                db.session.commit()
            else:
                logger.error(f"Push send failed for sub {sub.id}: {e}")
