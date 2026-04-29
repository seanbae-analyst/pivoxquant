"""Shared route decorators."""
from functools import wraps

from flask import jsonify
from flask_login import current_user

from services.legal_filter import safe_scrub


def _deep_scrub(obj):
    """Recursively walk a JSON-shaped structure, scrubbing every string leaf.

    Used by :func:`legal_scrub_response` to enforce the legal boundary on
    risk/quant endpoint responses without touching engine code.
    """
    if isinstance(obj, dict):
        return {k: _deep_scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_scrub(x) for x in obj]
    if isinstance(obj, str):
        return safe_scrub(obj, context="legal_scrub_response")
    return obj


def legal_scrub_response(f):
    """Scrub legally risky phrases out of a JSON response before it ships.

    Wraps any route that may surface engine-generated ``action`` / ``message``
    / ``recommendation`` fields (risk_defense.py, quant_models.py, etc.) and
    rewrites them to information-only wording. No-op for non-JSON responses.

    Layering: place AFTER ``@api_auth`` so auth still short-circuits 401s
    unscrubbed, but the happy-path body is always filtered::

        @quant_bp.route("/risk/defense-status")
        @api_auth
        @legal_scrub_response
        def risk_defense_status():
            ...
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        result = f(*args, **kwargs)
        # Normalize to (response, status) — Flask view returns vary.
        # Default status: prefer Response.status_code (preserves 4xx/5xx from
        # _data_unavailable / abort-style returns); fall back to 200 only when
        # there is no Response object at all.
        if isinstance(result, tuple):
            resp = result[0]
            status = result[1] if len(result) > 1 else getattr(resp, "status_code", 200)
        else:
            resp = result
            status = getattr(resp, "status_code", 200)
        if hasattr(resp, "get_json") and getattr(resp, "is_json", False):
            try:
                data = resp.get_json()
            except Exception:
                return result
            return jsonify(_deep_scrub(data)), status
        return result
    return wrapped


def api_auth(f):
    """Require an authenticated user.

    Cron / scheduled triggers must NOT use this decorator — apply
    `_check_cron_admin_secret()` (defined in routes/artifacts.py) inside the
    endpoint body instead. Earlier versions of this decorator allowed an
    X-Admin-Secret bypass, but that caused user-data endpoints (e.g.
    `/api/artifacts/list`, which dereferences `current_user.id`) to 500
    when called with a valid admin secret but no user session.
    """
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
            # effective_tier applies DEV_PREMIUM_EMAILS override, then falls back.
            user_tier = (
                getattr(current_user, "effective_tier", None)
                or getattr(current_user, "subscription_tier", "free")
                or "free"
            )
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
