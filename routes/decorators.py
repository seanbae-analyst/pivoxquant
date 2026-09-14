"""Shared route decorators."""
from functools import wraps

from flask import jsonify
from flask_login import current_user

from services.legal_filter import scrub_response


def _deep_scrub(obj, skip_keys=None):
    """Recursively walk a JSON-shaped structure, scrubbing every string leaf.

    Used by :func:`legal_scrub_response` to enforce the legal boundary on
    endpoint responses.

    2026-09-01: this was a second, independent copy of
    ``services.legal_filter.scrub_response``. Two implementations of one
    legal-critical rule is a divergence waiting to happen — and they HAD
    diverged: the copy here handled bare top-level strings and did not
    mutate its input, while the tested one in legal_filter did neither.
    They are now one function; this stays as a thin alias so the ~12
    ``@legal_scrub_response`` call sites keep their own log context.
    """
    return scrub_response(obj, context="legal_scrub_response", skip_keys=skip_keys)


def legal_scrub_response(f=None, *, skip_keys=None):
    """Scrub legally risky phrases out of a JSON response before it ships.

    Wraps any route that may surface generated ``action`` / ``message``
    fields and rewrites them to information-only wording. No-op for non-JSON
    responses. (The generators it was built for — risk_defense.py,
    quant_models.py — were deleted 2026-08-31; the live sources are now
    stored SignalCache payloads and behaviour-mirror text.)

    Layering: place AFTER ``@api_auth`` so auth still short-circuits 401s
    unscrubbed, but the happy-path body is always filtered::

        @risk_quant_bp.route("/risk/defense-status")
        @api_auth
        @legal_scrub_response
        def risk_defense_status():
            ...
    """
    # Usable bare (``@legal_scrub_response``) or parameterised
    # (``@legal_scrub_response(skip_keys=("action",))``).
    skip = frozenset(skip_keys) if skip_keys else None

    def _decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            # Normalize to (response, status) — Flask view returns vary.
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
                return jsonify(_deep_scrub(data, skip)), status
            return result
        return wrapped

    if f is not None and callable(f):
        return _decorate(f)
    return _decorate


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
            # 2026-05-08 (NEW-D): emit `code: "SESSION_EXPIRED"` so the
            # frontend's apiFetch can redirect to /login?expired=1
            # (frontend/src/lib/api.ts:78). Without the code, 401s thrown
            # by api_auth surfaced as silent ApiError and stale views.
            # We use the same SESSION_EXPIRED code that security.py emits
            # for inactivity timeout — both end-states require re-login,
            # so a single frontend handler covers them.
            return jsonify({
                "error":    "Login required",
                "error_kr": "로그인이 필요합니다.",
                "code":     "SESSION_EXPIRED",
            }), 401
        return f(*a, **kw)
    return wrapped


# ── Tier-based access control ──────────────────────────────────────────────────

# Tier hierarchy: free < pro < premium
_TIER_RANK = {
    "free": 0,
    "pro": 1,
    "premium": 2,
    # 2026-05-02: Companion-tier names (routes/agent.py gate). Higher than
    # "premium" so anyone holding premium_plus/founding_lifetime also passes
    # legacy `@require_tier("premium")` decorators.
    "premium_plus": 3,
    "founding_lifetime": 4,
}


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
