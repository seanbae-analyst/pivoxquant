"""
PivoxQuant — Broker connection routes (KIS only, 2026-04-20).

Endpoints (all require login; mutating ones rate-limited):
    POST   /api/broker/kis/connect       submit app_key/app_secret/account_no
    POST   /api/broker/kis/sync          manual position sync
    DELETE /api/broker/kis/disconnect    remove credentials
    GET    /api/broker/kis/status        connection + last-sync status
    GET    /api/broker/connections       broker connection summary for the user

All endpoints respond `{"ok": true, ...}` on success or `{"error": str, "code": str?}`
on failure with an appropriate HTTP status.

Sensitive inputs (app_key / app_secret / account_no) are encrypted via
`services.crypto_service` before being persisted. Raw values never leave this
request handler.

History:
    - 2026-04-20: Simplified to KIS only. Removed /api/broker/kiwoom/csv and
      Alpaca/broker-sync routes. Legacy `broker='alpaca'` / `broker='kiwoom_csv'`
      rows in `broker_connections` are preserved but no longer writable.
"""
from __future__ import annotations

import logging
import re

from flask import Blueprint, jsonify, request
from flask_login import current_user

from models import Position
from models.broker_connection import BrokerConnection
from security import trade_rate_limit
from services.broker.user_kis_service import (
    UserKISError,
    UserKISService,
    delete_kis_connection,
    upsert_kis_connection,
)

from .decorators import api_auth

logger = logging.getLogger(__name__)

broker_oauth_bp = Blueprint("broker_oauth", __name__, url_prefix="/api/broker")

# ── Validation helpers ────────────────────────────────────────────────────
# 2026-05-17: backend regex sync with frontend Wave 6 LOW #4 fix
# (kis-connect-modal.tsx:35 = `/^\d{8}$/`). KIS retail accounts are
# exactly 8 digits — the prior `\d{6,12}` window was a defensive guess
# that let a non-browser caller (curl, mobile dev tools) submit a 6- or
# 12-digit string that we then forwarded to KIS only to hit
# `INVALID_ACCOUNT` four hops later. Closing the gap so frontend and
# backend agree on the canonical shape.
_ACCOUNT_RE = re.compile(r"^\d{8}$")
_PROD_RE = re.compile(r"^\d{2}$")

# 2026-05-25 Bug #3: BrokerConnection.display_name is db.String(100). A payload
# with a >100-char display_name reaches PostgreSQL and raises
# `DataError: value too long for type character varying(100)` → 500. Reject at
# the boundary with an explicit 400 so the caller gets a clear message rather
# than an opaque server error. SQLite (local test) silently truncates instead
# of raising, masking the bug locally — hence the explicit guard.
_DISPLAY_NAME_MAX = 100

# Free-tier position cap (mirror of routes/portfolio.py:2072). Free users (or
# users with no tier set) may hold at most 3 positions total; broker sync must
# not bypass this via brand-new inserts.
FREE_POSITION_CAP = 3


def _free_tier_position_budget(user_id: int) -> int | None:
    """Compute `max_new_positions` for a KIS sync given the user's tier.

    Returns the remaining NEW-insert budget for free-tier users (so a free user
    cannot exceed FREE_POSITION_CAP via broker sync), or None for paid tiers
    (unlimited). Mirrors the reconcile implementation in
    routes/portfolio.py:2070-2076 exactly — `held` counts current shares>0
    positions; budget = max(cap - held, 0). Existing positions are always
    upserted regardless of the cap (handled in sync_to_db).
    """
    if getattr(current_user, "effective_tier", None) not in (None, "free"):
        return None
    held = Position.query.filter_by(user_id=user_id).filter(
        Position.shares > 0
    ).count()
    return max(FREE_POSITION_CAP - held, 0)


def _validate_connect_payload(body: dict) -> tuple[dict | None, dict | None]:
    """Returns (cleaned_dict, error_dict). Only one is non-None."""
    if not isinstance(body, dict):
        return None, {"error": "Request body must be JSON object", "code": "INVALID_BODY"}

    app_key = (body.get("app_key") or "").strip()
    app_secret = (body.get("app_secret") or "").strip()
    account_no = (body.get("account_no") or "").strip()
    account_prod = (body.get("account_prod") or "01").strip()
    display_name = (body.get("display_name") or "").strip() or None

    if display_name is not None and len(display_name) > _DISPLAY_NAME_MAX:
        return None, {
            "error": f"표시 이름은 {_DISPLAY_NAME_MAX}자 이하여야 합니다.",
            "code": "INVALID_DISPLAY_NAME",
        }
    if not app_key or len(app_key) < 16:
        return None, {"error": "APP KEY가 올바르지 않습니다.", "code": "INVALID_APP_KEY"}
    if not app_secret or len(app_secret) < 16:
        return None, {"error": "APP SECRET이 올바르지 않습니다.", "code": "INVALID_APP_SECRET"}
    if not _ACCOUNT_RE.match(account_no):
        # 2026-05-18 Wave G-2 P1 Bug #3: regex is `\d{8}$` since PR #416
        # (frontend Wave 6 LOW #4 sync). Error text was stale '6~12자리'
        # which conflicted with the actual validation rule and confused
        # API consumers debugging 400s.
        return None, {
            "error": "계좌번호는 정확히 8자리 숫자여야 합니다.",
            "code": "INVALID_ACCOUNT",
        }
    if not _PROD_RE.match(account_prod):
        return None, {
            "error": "상품코드는 두 자리 숫자여야 합니다 (예: 01).",
            "code": "INVALID_ACCOUNT_PROD",
        }

    return (
        {
            "app_key": app_key,
            "app_secret": app_secret,
            "account_no": account_no,
            "account_prod": account_prod,
            "display_name": display_name,
        },
        None,
    )


# ── POST /api/broker/kis/connect ─────────────────────────────────────────
@broker_oauth_bp.route("/kis/connect", methods=["POST"])
@api_auth
@trade_rate_limit
def kis_connect():
    """Register/update the user's KIS credentials and verify immediately."""
    body = request.get_json(silent=True) or {}
    cleaned, error = _validate_connect_payload(body)
    if error:
        return jsonify(error), 400

    try:
        conn = upsert_kis_connection(
            user_id=current_user.id,
            **cleaned,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("kis_connect upsert failed user_id=%s: %s", current_user.id, exc)
        return jsonify({
            "error": "자격 증명 저장에 실패했습니다.",
            "code": "PERSIST_FAILED",
        }), 500

    # Verify credentials by minting a token immediately.
    try:
        service = UserKISService(current_user.id, connection=conn)
    except UserKISError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), exc.http_status

    auth_result = service.authenticate(force=True)
    if not auth_result.get("ok"):
        # Keep the encrypted credentials but mark inactive so the user can retry.
        return jsonify({
            "error": auth_result.get("error", "KIS 인증에 실패했습니다."),
            "code": auth_result.get("code", "INVALID_CREDENTIALS"),
            "connection_id": conn.id,
        }), 400

    # Kick off an initial sync (best-effort; sync errors surface as warnings).
    # 2026-05-25 Bug #1: apply the free-tier 3-position cap here too — the
    # initial sync was inserting positions with no cap, letting a free user
    # bypass the limit (revenue leak). Mirror reconcile (portfolio.py:2070-2078).
    sync_result = service.sync_to_db(
        max_new_positions=_free_tier_position_budget(current_user.id)
    )
    initial_sync = {
        "ok": bool(sync_result.get("ok")),
        "added": sync_result.get("added", []),
        "updated": sync_result.get("updated", []),
        "error": sync_result.get("error") if not sync_result.get("ok") else None,
    }

    return jsonify({
        "ok": True,
        "connection_id": conn.id,
        "status": "connected",
        "display_name": conn.display_name,
        "is_paper": conn.is_paper,
        "initial_sync": initial_sync,
    }), 200


# ── POST /api/broker/kis/sync ────────────────────────────────────────────
@broker_oauth_bp.route("/kis/sync", methods=["POST"])
@api_auth
@trade_rate_limit
def kis_sync():
    """Trigger a manual sync of the user's KIS positions + balance."""
    try:
        service = UserKISService(current_user.id)
    except UserKISError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), exc.http_status

    # 2026-05-25 Bug #1: manual sync must enforce the free-tier 3-position cap
    # too. Was calling sync_to_db() with no cap → free user could exceed the
    # limit by syncing a KIS account holding >3 symbols (revenue leak).
    result = service.sync_to_db(
        max_new_positions=_free_tier_position_budget(current_user.id)
    )
    if not result.get("ok"):
        return jsonify({
            "error": result.get("error", "KIS 동기화에 실패했습니다."),
            "code": result.get("code", "SYNC_FAILED"),
        }), 502

    return jsonify({
        "ok": True,
        "added": result["added"],
        "updated": result["updated"],
        "synced": result["synced"],
        "available_cash": result["available_cash"],
        "total_value": result["total_value"],
    }), 200


# ── DELETE /api/broker/kis/disconnect ────────────────────────────────────
@broker_oauth_bp.route("/kis/disconnect", methods=["DELETE"])
@api_auth
@trade_rate_limit
def kis_disconnect():
    """Remove the user's KIS connection and encrypted credentials."""
    removed = delete_kis_connection(current_user.id)
    if not removed:
        return jsonify({
            "ok": False,
            "error": "연결된 KIS 계좌가 없습니다.",
            "code": "NO_CONNECTION",
        }), 404
    return jsonify({"ok": True, "status": "disconnected"}), 200


# ── GET /api/broker/kis/status ───────────────────────────────────────────
@broker_oauth_bp.route("/kis/status", methods=["GET"])
@api_auth
def kis_status():
    """Return the user's KIS connection status (without exposing any secret)."""
    conn = BrokerConnection.query.filter_by(
        user_id=current_user.id, broker="kis"
    ).first()
    if conn is None:
        return jsonify({"ok": True, "connected": False})

    # Whitelist-only serialization — never spread `**conn.to_dict()` blindly,
    # because future model additions (tokens, refresh secrets, encrypted blobs)
    # would otherwise leak into this public endpoint on first schema change.
    _SAFE_FIELDS = {
        "id",
        "broker",
        "is_active",
        "is_paper",
        "has_credentials",
        "display_name",
        "last_synced_at",
        "last_sync_status",
        "consecutive_failures",
    }
    full = conn.to_dict()
    safe = {k: v for k, v in full.items() if k in _SAFE_FIELDS}

    # 2026-05-18 Wave G-2 P1 Bug #4: token_expires_at REMOVED from response.
    # Was bypassing the _SAFE_FIELDS whitelist (spread outside the filter),
    # exposing the exact KIS bearer token expiry timestamp. Knowing the precise
    # expiry window enables token re-issue race timing attacks (request a new
    # token at expiry-N seconds and race the legitimate user's session).
    # Frontend does not consume this field — verified via repo grep.
    return jsonify({
        "ok": True,
        "connected": conn.is_active,
        **safe,
    })


# ── GET /api/broker/connections ──────────────────────────────────────────
#
# Frontend summary endpoint. Returns only the fields the UI actually reads
# (`kis_connected`, `kis_last_sync`). Legacy `broker='alpaca'` and
# `broker='kiwoom_csv'` rows are intentionally ignored — we preserve them
# in the DB for historical positions but stopped surfacing them in the UI
# on 2026-04-20.
@broker_oauth_bp.route("/connections", methods=["GET"])
@api_auth
def broker_connections():
    """Return the KIS (read-only) connection summary for the current user.

    Alpaca was fully removed 2026-05-27 (it had been kill-switched and unused).
    KIS is the only supported broker integration.
    """
    kis_conn = BrokerConnection.query.filter_by(
        user_id=current_user.id, broker="kis"
    ).first()

    return jsonify({
        "kis_connected": bool(kis_conn and kis_conn.is_active),
        "kis_last_sync": kis_conn.last_synced_at.isoformat()
        if (kis_conn and kis_conn.last_synced_at)
        else None,
    })
