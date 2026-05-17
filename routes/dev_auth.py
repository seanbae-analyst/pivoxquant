"""
Dev-login bypass for E2E testing.

Security:
  - Only registered when DEV_LOGIN_SECRET env var is set.
  - Production (Railway) must NOT set this variable.
  - The route itself validates the shared secret from the request body.
"""

import hmac
import os
import logging

from flask import Blueprint, request, jsonify
from flask_login import login_user

from extensions import db
from models.user import User
from security import auth_rate_limit
from services.error_responses import api_error

logger = logging.getLogger(__name__)

dev_auth_bp = Blueprint("dev_auth", __name__)

_TEST_EMAIL = "test@pivoxquant.dev"


@dev_auth_bp.route("/api/auth/dev-login", methods=["POST"])
@auth_rate_limit
def dev_login():
    """Create or find a test user and log them in. CSRF-exempt (see security.py)."""
    secret = os.environ.get("DEV_LOGIN_SECRET")
    if not secret:
        return api_error(
            en="Dev login disabled",
            kr="개발용 로그인이 비활성화되어 있습니다.",
            code="DEV_AUTH_LOGIN_DISABLED",
            status=404,
        )

    body = request.get_json(silent=True) or {}
    # SEC-003: timing-safe comparison to prevent secret discovery via response-time side channel.
    if not hmac.compare_digest(str(body.get("secret") or ""), secret):
        logger.warning("dev-login: invalid secret attempt")
        return api_error(
            en="Invalid secret",
            kr="유효하지 않은 시크릿입니다.",
            code="DEV_AUTH_SECRET_INVALID",
            status=401,
        )

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
        return api_error(
            en="Dev endpoints disabled",
            kr="개발용 엔드포인트가 비활성화되어 있습니다.",
            code="DEV_AUTH_ENDPOINTS_DISABLED",
            status=404,
        )

    body = request.get_json(silent=True) or {}
    # SEC-003: timing-safe comparison to prevent secret discovery via response-time side channel.
    if not hmac.compare_digest(str(body.get("secret") or ""), secret):
        logger.warning("dev-upgrade: invalid secret attempt")
        return api_error(
            en="Invalid secret",
            kr="유효하지 않은 시크릿입니다.",
            code="DEV_AUTH_SECRET_INVALID",
            status=401,
        )

    # SEC-003: restrict the upgradeable target to the dev test domain so a leaked
    # DEV_LOGIN_SECRET cannot be turned into a free tier-upgrade for arbitrary
    # real user emails. Test fixtures use *@pivoxquant.dev.
    email = (body.get("email") or "").strip().lower()
    tier = (body.get("tier") or "premium").strip().lower()
    if not email:
        return api_error(
            en="email required",
            kr="이메일이 필요합니다.",
            code="DEV_AUTH_EMAIL_REQUIRED",
            status=400,
        )
    if not email.endswith("@pivoxquant.dev"):
        logger.warning("dev-upgrade: rejected non-dev email %s", email)
        return api_error(
            en="email must be a @pivoxquant.dev test address",
            kr="이메일은 @pivoxquant.dev 테스트 주소여야 합니다.",
            code="DEV_AUTH_EMAIL_NOT_DEV",
            status=400,
        )
    if tier not in ("free", "pro", "premium"):
        return api_error(
            en="tier must be free|pro|premium",
            kr="tier는 free|pro|premium 중 하나여야 합니다.",
            code="DEV_AUTH_TIER_INVALID",
            status=400,
        )

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        return api_error(
            en=f"user not found: {email}",
            kr=f"사용자를 찾을 수 없습니다: {email}",
            code="DEV_AUTH_USER_NOT_FOUND",
            status=404,
        )

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
