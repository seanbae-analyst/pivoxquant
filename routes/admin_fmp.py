"""Admin-only FMP budget / 402 tracker.

Exposes a single GET endpoint — ``/api/admin/fmp-usage`` — gated by the
``ADMIN_EMAILS`` env var (same gate the ``agent_worker`` admin routes use).
Intended for the founder / ops console to spot-check whether we're about
to hit the 250/day Starter cap or whether a particular endpoint is in
402 cooldown.

Response shape (stable)::

    {
      "daily_calls": 147,
      "daily_limit": 250,
      "remaining": 103,
      "cache_entries": 482,
      "stale_mode": false,
      "hard_stopped": false,
      "blocked_endpoints": {"/institutional-ownership/...": 842},
      "402_counts": {"/institutional-ownership/...": 3},
      "stale_threshold": 220,
      "hard_stop_threshold": 248
    }

The endpoint is read-only — no writes, no external calls, no PII. Safe to
poll.
"""
from __future__ import annotations

import logging
import os

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

import fmp_service

logger = logging.getLogger(__name__)

admin_fmp_bp = Blueprint("admin_fmp", __name__, url_prefix="/api/admin")


def _admin_emails() -> set[str]:
    """Parse the ``ADMIN_EMAILS`` env var into a set of lowercased addresses."""
    raw = os.getenv("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


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
@login_required
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
