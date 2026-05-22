"""Admin-only FMP budget / 402 tracker.

Exposes a single GET endpoint — ``/api/admin/fmp-usage`` — gated by the
``ADMIN_EMAILS`` env var (same gate the ``agent_worker`` admin routes use).
Intended for the founder / ops console to spot-check whether we're about
to hit the FMP_DAILY_SOFT_LIMIT (default 10k for Premium $29) or whether a
particular endpoint is in 402 cooldown.

Response shape (stable, values reflect FMP_DAILY_SOFT_LIMIT — example shows Premium default 10000)::

    {
      "daily_calls": 147,
      "daily_limit": 10000,
      "remaining": 9853,
      "cache_entries": 482,
      "stale_mode": false,
      "hard_stopped": false,
      "blocked_endpoints": {"/institutional-ownership/...": 842},
      "402_counts": {"/institutional-ownership/...": 3},
      "stale_threshold": 8800,
      "hard_stop_threshold": 9900
    }

The endpoint is read-only — no writes, no external calls, no PII. Safe to
poll.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from flask_login import current_user

from routes.decorators import api_auth
from services.data import fmp as fmp_service

logger = logging.getLogger(__name__)

admin_fmp_bp = Blueprint("admin_fmp", __name__, url_prefix="/api/admin")


# 2026-05-17 wave 13 P2 (PR #442): parser centralized in
# services/admin_emails.py — keep the local name as a thin alias so
# the route bodies below don't churn.
from services.admin_emails import get_admin_emails as _admin_emails  # noqa: E402


def _deny_non_admin():
    """Return a 403 JSON response when the current user is not an admin.

    Returns ``None`` when the user *is* an admin so the route can proceed.
    Mirrors ``agent_worker.admin_routes._require_admin`` so we fail closed
    when ``ADMIN_EMAILS`` is missing in the environment.
    """
    admins = _admin_emails()
    if not admins:
        logger.warning("ADMIN_EMAILS not configured — denying /api/admin/fmp-usage")
        return jsonify({"error": "Admin access not configured"}), 403
    email = (getattr(current_user, "email", "") or "").lower()
    if email not in admins:
        return jsonify({"error": "Forbidden"}), 403
    return None


@admin_fmp_bp.route("/fmp-usage", methods=["GET"])
@api_auth  # 2026-05-22: JSON 401 {"code":"SESSION_EXPIRED"} for /api/* callers
           # instead of flask-login's 302 HTML redirect. Admin authz still
           # enforced below via _deny_non_admin().
def fmp_usage():
    """Return the current FMP budget / 402 cooldown snapshot.

    Admin-only. Non-admin sessions get 403. The underlying data comes from
    ``fmp_service.get_api_usage()`` which reads the in-process counters —
    note this is per-worker (gunicorn workers don't share state), so the
    numbers shown represent *this* worker's view of the day.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied
    return jsonify(fmp_service.get_api_usage()), 200
