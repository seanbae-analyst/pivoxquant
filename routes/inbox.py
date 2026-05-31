"""CEO Inbox API — v57 Phase A.

GET /api/inbox
    Returns single-pane payload (5 sources aggregated).
    Admin only (CEO 전용) — ADMIN_EMAILS env 멤버만 허용.

Read-only — no LLM, no external API, no DB writes.
"""
from __future__ import annotations

import os

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from services.inbox import build_inbox_payload

# legal-exempt: admin-only internal CEO ops inbox (autonomous-ops status,
# ship blockers, lawyer queue, cron status). Non-admins get 403 (see
# get_inbox L53); no user-facing financial/advisory/analysis content is
# ever returned, so legal_scrub_response is not applicable.
inbox_bp = Blueprint("inbox", __name__, url_prefix="/api/inbox")


def _is_admin() -> bool:
    """ADMIN_EMAILS env 멤버인지 확인."""
    if not current_user.is_authenticated:
        return False
    admin_emails = {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "").split(",")
        if e.strip()
    }
    email = (getattr(current_user, "email", "") or "").lower()
    return bool(email) and email in admin_emails


@inbox_bp.route("", methods=["GET"])
@login_required
def get_inbox():
    """CEO Inbox payload.

    Returns
    -------
    JSON 200:
        {
          "generated_at_kst": str,
          "autonomous_done": [...],
          "ship_blockers": {...},
          "lawyer_queue": {...},
          "cron_status": {...},
          "next_fires": [...],
          "summary": str
        }
    JSON 403: not admin
    """
    if not _is_admin():
        return jsonify({"error": "admin only", "code": "FORBIDDEN"}), 403
    payload = build_inbox_payload()
    return jsonify(payload)
