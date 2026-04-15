"""Shared route decorators."""
from functools import wraps
from flask import jsonify
from flask_login import current_user


def api_auth(f):
    """Require authenticated user for API endpoints."""
    @wraps(f)
    def wrapped(*a, **kw):
        if not current_user.is_authenticated:
            return jsonify({"error": "Login required"}), 401
        return f(*a, **kw)
    return wrapped


# ── Tier-based access control ──────────────────────────────────────────────────

# Tier hierarchy: free < pro < premium
_TIER_RANK = {"free": 0, "pro": 1, "premium": 2}


def require_tier(minimum_tier):
    """Require a minimum subscription tier.

    Usage (uncomment @require_tier when launching paid features):
        @billing_bp.route("/advanced-analytics")
        @api_auth
        # @require_tier("pro")
        def advanced_analytics():
            ...

    Free users receive 403 with UPGRADE_REQUIRED code.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*a, **kw):
            user_tier = getattr(current_user, "subscription_tier", "free") or "free"
            required_rank = _TIER_RANK.get(minimum_tier, 0)
            user_rank = _TIER_RANK.get(user_tier, 0)

            if user_rank < required_rank:
                return jsonify({
                    "error": "Upgrade required",
                    "required_tier": minimum_tier,
                    "code": "UPGRADE_REQUIRED",
                }), 403
            return f(*a, **kw)
        return wrapped
    return decorator
