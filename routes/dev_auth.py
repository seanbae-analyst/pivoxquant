"""
Dev-login bypass for E2E testing.

Security:
  - Only registered when DEV_LOGIN_SECRET env var is set.
  - Production (Railway) must NOT set this variable.
  - The route itself validates the shared secret from the request body.
"""

import os
import logging

from flask import Blueprint, request, jsonify
from flask_login import login_user

from extensions import db
from models.user import User
from security import auth_rate_limit

logger = logging.getLogger(__name__)

dev_auth_bp = Blueprint("dev_auth", __name__)

_TEST_EMAIL = "test@pivoxquant.dev"


@dev_auth_bp.route("/api/auth/dev-login", methods=["POST"])
@auth_rate_limit
def dev_login():
    """Create or find a test user and log them in. CSRF-exempt (see security.py)."""
    secret = os.environ.get("DEV_LOGIN_SECRET")
    if not secret:
        return jsonify({"error": "Dev login disabled"}), 404

    body = request.get_json(silent=True) or {}
    if body.get("secret") != secret:
        logger.warning("dev-login: invalid secret attempt")
        return jsonify({"error": "Invalid secret"}), 401

    user = User.query.filter_by(email=_TEST_EMAIL).first()
    if not user:
        user = User(
            email=_TEST_EMAIL,
            name="QA Tester",
            oauth_provider="dev",
            onboarding_completed=True,
            subscription_tier="premium",
        )
        db.session.add(user)
        db.session.commit()
        logger.info("dev-login: created test user id=%s", user.id)

    login_user(user, remember=True)
    return jsonify({
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
        },
    })


@dev_auth_bp.route("/api/auth/dev-upgrade", methods=["POST"])
@auth_rate_limit
def dev_upgrade():
    """Upgrade a user's subscription tier. Requires DEV_LOGIN_SECRET."""
    secret = os.environ.get("DEV_LOGIN_SECRET")
    if not secret:
        return jsonify({"error": "Dev endpoints disabled"}), 404

    body = request.get_json(silent=True) or {}
    if body.get("secret") != secret:
        logger.warning("dev-upgrade: invalid secret attempt")
        return jsonify({"error": "Invalid secret"}), 401

    email = (body.get("email") or "").strip().lower()
    tier = (body.get("tier") or "premium").strip().lower()
    if not email:
        return jsonify({"error": "email required"}), 400
    if tier not in ("free", "pro", "premium"):
        return jsonify({"error": "tier must be free|pro|premium"}), 400

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        return jsonify({"error": f"user not found: {email}"}), 404

    user.subscription_tier = tier
    user.subscription_status = "active" if tier != "free" else "inactive"
    db.session.commit()
    logger.info("dev-upgrade: %s -> tier=%s", email, tier)
    return jsonify({
        "ok": True,
        "email": user.email,
        "subscription_tier": user.subscription_tier,
        "subscription_status": user.subscription_status,
    })
