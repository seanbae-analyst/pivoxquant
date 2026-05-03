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

    # Upsert: replace if same endpoint exists
    try:
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


def send_push_to_user(user_id: int, title: str, body: str,
                      url: str = "/alerts", actions: Optional[list] = None,
                      transactional: bool = False):
    """Send push notification to all subscriptions for a user.

    Call this from services (e.g. alert_service) after creating an alert.

    ``transactional=True`` bypasses the marketing opt-out gate
    (``User.email_opt_out`` — 정통망법 §50). Use it only for service-info
    pushes the user explicitly subscribed to (price alerts, portfolio
    events, account sync, artifact-ready). Marketing pushes must leave
    it ``False`` so opted-out users are silenced.
    """
    try:
        from pywebpush import webpush, WebPushException  # noqa: F401 — runtime exception type
    except ImportError:
        logger.warning("pywebpush not installed — skipping push notification")
        return

    # 정통망법 §50 marketing opt-out gate. Mirrors the email path —
    # ``User.email_opt_out`` is the global kill-switch that disables every
    # marketing channel. Until a dedicated ``push_opt_out`` column exists
    # we honour the email flag for non-transactional pushes.
    if not transactional:
        try:
            from models import User
            user = User.query.get(user_id)
            if user is not None and bool(getattr(user, "email_opt_out", False)):
                logger.info("push opt-out: user_id=%s skipped (email_opt_out=True)",
                            user_id)
                return
        except Exception:
            # Never fail-closed on push delivery for an unrelated DB hiccup.
            logger.debug("opt-out gate lookup failed", exc_info=True)

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_email = os.environ.get("VAPID_EMAIL", "mailto:admin@pivoxquant.com")

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
                try:
                    db.session.delete(sub)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    logger.exception("push send cleanup failed for sub %s", sub.id)
            else:
                logger.error(f"Push send failed for sub {sub.id}: {e}")
