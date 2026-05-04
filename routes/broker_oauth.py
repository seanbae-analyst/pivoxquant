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

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from models.broker_connection import BrokerConnection
from security import trade_rate_limit
from services.broker.user_alpaca_service import (
    UserAlpacaError,
    UserAlpacaService,
    delete_alpaca_connection,
    upsert_alpaca_connection,
)
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
_ACCOUNT_RE = re.compile(r"^\d{6,12}$")  # KIS 계좌는 8자리가 일반적, 여유 허용
_PROD_RE = re.compile(r"^\d{2}$")


def _validate_connect_payload(body: dict) -> tuple[dict | None, dict | None]:
    """Returns (cleaned_dict, error_dict). Only one is non-None."""
    if not isinstance(body, dict):
        return None, {"error": "Request body must be JSON object", "code": "INVALID_BODY"}

    app_key = (body.get("app_key") or "").strip()
    app_secret = (body.get("app_secret") or "").strip()
    account_no = (body.get("account_no") or "").strip()
    account_prod = (body.get("account_prod") or "01").strip()
    display_name = (body.get("display_name") or "").strip() or None

    if not app_key or len(app_key) < 16:
        return None, {"error": "APP KEY가 올바르지 않습니다.", "code": "INVALID_APP_KEY"}
    if not app_secret or len(app_secret) < 16:
        return None, {"error": "APP SECRET이 올바르지 않습니다.", "code": "INVALID_APP_SECRET"}
    if not _ACCOUNT_RE.match(account_no):
        return None, {
            "error": "계좌번호는 숫자 6~12자리여야 합니다.",
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
@trade_rate_limit
@api_auth
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
    sync_result = service.sync_to_db()
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
@trade_rate_limit
@api_auth
def kis_sync():
    """Trigger a manual sync of the user's KIS positions + balance."""
    try:
        service = UserKISService(current_user.id)
    except UserKISError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), exc.http_status

    result = service.sync_to_db()
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
@trade_rate_limit
@api_auth
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

    return jsonify({
        "ok": True,
        "connected": conn.is_active,
        **safe,
        "token_expires_at": conn.token_expires_at.isoformat()
        if conn.token_expires_at
        else None,
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
    """Return KIS + Alpaca (paper) connection summary for the current user.

    Alpaca was re-added 2026-04-22 as a *paper-only* integration. Legacy Alpaca
    rows predating 2026-04-20 may exist with tokens in `access_token` — those
    are ignored here; only rows with encrypted_app_key set via the new upsert
    flow are considered connected.
    """
    kis_conn = BrokerConnection.query.filter_by(
        user_id=current_user.id, broker="kis"
    ).first()

    # Alpaca is kill-switched by default (ALPACA_ENABLED=0). When disabled we
    # still return the key so the frontend sees a stable schema, but force
    # `alpaca_connected=False` and `alpaca_disabled=True` so UI hides the
    # Alpaca card. Legacy rows in `broker_connections` are NOT deleted — the
    # frontend simply can't act on them until Alpaca is re-enabled.
    alpaca_enabled = bool(current_app.config.get("ALPACA_ENABLED"))

    if alpaca_enabled:
        alpaca_conn = BrokerConnection.query.filter_by(
            user_id=current_user.id, broker="alpaca"
        ).first()

        def _alpaca_connected(c: BrokerConnection | None) -> bool:
            return bool(
                c and c.is_active and c.encrypted_app_key and c.encrypted_app_secret
            )

        alpaca_connected = _alpaca_connected(alpaca_conn)
        alpaca_last_sync = (
            alpaca_conn.last_synced_at.isoformat()
            if (alpaca_conn and alpaca_conn.last_synced_at)
            else None
        )
    else:
        alpaca_connected = False
        alpaca_last_sync = None

    return jsonify({
        "kis_connected": bool(kis_conn and kis_conn.is_active),
        "kis_last_sync": kis_conn.last_synced_at.isoformat()
        if (kis_conn and kis_conn.last_synced_at)
        else None,
        "alpaca_connected": alpaca_connected,
        "alpaca_last_sync": alpaca_last_sync,
        "alpaca_mode": "paper",  # live trading intentionally disabled in this release
        "alpaca_disabled": not alpaca_enabled,  # kill switch status for UI
    })


# ── Alpaca (US, paper-only) ───────────────────────────────────────────────
#
# Symmetric with the KIS routes above. Credentials live in the same
# `broker_connections` table under broker='alpaca', reusing the encrypted_app_key
# / encrypted_app_secret columns. We NEVER accept env="live" — paper only.
#
# ⚠️ KILL SWITCH (2026-04-24): All Alpaca endpoints below are gated by
# `ALPACA_ENABLED` (config.py / Dockerfile env). Default OFF — flipping to ON
# without legal sign-off is a compliance violation (Alpaca "My Data" license).
# When disabled, every Alpaca endpoint returns 503 with code="alpaca-disabled".
# Legacy `broker='alpaca'` rows stay readable via `/api/broker/connections`
# (no writes, no credentials exposed) — migration is NOT required.
_ALPACA_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{10,128}$")


def _alpaca_kill_switch_response():
    """Return the standard 503 payload for disabled Alpaca endpoints.

    Returns None when Alpaca is enabled, signalling the caller to proceed.
    Returns a Flask (response, status) tuple when disabled.
    """
    if current_app.config.get("ALPACA_ENABLED"):
        return None
    return (
        jsonify({
            "ok": False,
            "error": "alpaca-disabled",
            "message": (
                "Alpaca integration is currently not available. "
                "KIS (한국투자증권) is the supported broker."
            ),
            "code": "ALPACA_DISABLED",
        }),
        503,
    )


def _validate_alpaca_payload(body: dict) -> tuple[dict | None, dict | None]:
    if not isinstance(body, dict):
        return None, {"error": "Request body must be JSON object", "code": "INVALID_BODY"}

    key_id = (body.get("key_id") or "").strip()
    secret_key = (body.get("secret_key") or "").strip()
    env = (body.get("env") or "paper").strip().lower()

    if env != "paper":
        return None, {
            "error": "Live trading is disabled in this release. Use paper only.",
            "code": "LIVE_DISABLED",
        }
    if not _ALPACA_KEY_RE.match(key_id):
        return None, {
            "error": "Alpaca API Key ID appears malformed.",
            "code": "INVALID_KEY_ID",
        }
    if len(secret_key) < 20:
        return None, {
            "error": "Alpaca API Secret Key appears too short.",
            "code": "INVALID_SECRET",
        }
    return (
        {"key_id": key_id, "secret_key": secret_key, "env": "paper"},
        None,
    )


@broker_oauth_bp.route("/alpaca/connect", methods=["POST"])
@trade_rate_limit
@api_auth
def alpaca_connect():
    """Register the user's Alpaca paper credentials and verify immediately."""
    killed = _alpaca_kill_switch_response()
    if killed is not None:
        return killed
    body = request.get_json(silent=True) or {}
    cleaned, error = _validate_alpaca_payload(body)
    if error:
        return jsonify(error), 400

    try:
        conn = upsert_alpaca_connection(
            user_id=current_user.id,
            key_id=cleaned["key_id"],
            secret_key=cleaned["secret_key"],
        )
    except Exception as exc:  # pragma: no cover
        logger.error("alpaca_connect upsert failed user_id=%s: %s", current_user.id, exc)
        return jsonify({
            "error": "Could not persist Alpaca credentials.",
            "code": "PERSIST_FAILED",
        }), 500

    try:
        service = UserAlpacaService(current_user.id, connection=conn)
    except UserAlpacaError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), exc.http_status

    verify_result = service.verify()
    if not verify_result.get("ok"):
        return jsonify({
            "error": verify_result.get("error", "Alpaca verification failed."),
            "code": verify_result.get("code", "INVALID_CREDENTIALS"),
            "connection_id": conn.id,
        }), 400

    return jsonify({
        "ok": True,
        "connection_id": conn.id,
        "status": "connected",
        "mode": "paper",
        "display_name": conn.display_name,
        "account": verify_result.get("account"),
    }), 200


@broker_oauth_bp.route("/alpaca/sync", methods=["POST"])
@trade_rate_limit
@api_auth
def alpaca_sync():
    """Trigger a light-touch Alpaca account refresh (paper only)."""
    killed = _alpaca_kill_switch_response()
    if killed is not None:
        return killed
    try:
        service = UserAlpacaService(current_user.id)
    except UserAlpacaError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), exc.http_status

    result = service.sync_account()
    if not result.get("ok"):
        return jsonify({
            "error": result.get("error", "Alpaca sync failed."),
            "code": result.get("code", "SYNC_FAILED"),
        }), 502
    return jsonify(result), 200


@broker_oauth_bp.route("/alpaca/disconnect", methods=["DELETE"])
@trade_rate_limit
@api_auth
def alpaca_disconnect():
    killed = _alpaca_kill_switch_response()
    if killed is not None:
        return killed
    removed = delete_alpaca_connection(current_user.id)
    if not removed:
        return jsonify({
            "ok": False,
            "error": "No Alpaca account connected.",
            "code": "NO_CONNECTION",
        }), 404
    return jsonify({"ok": True, "status": "disconnected"}), 200


@broker_oauth_bp.route("/alpaca/status", methods=["GET"])
@api_auth
def alpaca_status():
    killed = _alpaca_kill_switch_response()
    if killed is not None:
        return killed
    conn = BrokerConnection.query.filter_by(
        user_id=current_user.id, broker="alpaca"
    ).first()
    if conn is None:
        return jsonify({"ok": True, "connected": False, "mode": "paper"})

    _SAFE = {
        "id", "broker", "is_active", "is_paper", "has_credentials",
        "display_name", "last_synced_at", "last_sync_status",
        "consecutive_failures",
    }
    full = conn.to_dict()
    safe = {k: v for k, v in full.items() if k in _SAFE}
    return jsonify({
        "ok": True,
        "connected": bool(conn.is_active and conn.encrypted_app_key),
        "mode": "paper",  # live disabled by policy
        **safe,
    })
