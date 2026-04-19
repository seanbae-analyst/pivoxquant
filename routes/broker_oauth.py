"""
PivoxQuant — Broker OAuth / personal-credential routes (Week 1: KIS, Week 2: Kiwoom CSV).

Endpoints (all require login; mutating ones rate-limited):
    POST   /api/broker/kis/connect       submit app_key/app_secret/account_no
    POST   /api/broker/kis/sync          manual position sync
    DELETE /api/broker/kis/disconnect    remove credentials
    GET    /api/broker/kis/status        connection + last-sync status
    POST   /api/broker/kiwoom/csv        upload 영웅문 잔고 엑셀/CSV → positions merge

All endpoints respond `{"ok": true, ...}` on success or `{"error": str, "code": str?}`
on failure with an appropriate HTTP status.

Sensitive inputs (app_key / app_secret / account_no) are encrypted via
`services.crypto_service` before being persisted. Raw values never leave this
request handler.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models.broker_connection import BrokerConnection
from models.position import Position
from security import trade_rate_limit
from services.broker.user_kis_service import (
    UserKISError,
    UserKISService,
    delete_kis_connection,
    upsert_kis_connection,
)
from services.broker.user_kiwoom_csv_service import (
    UserKiwoomCSVError,
    parse_kiwoom_balance_file,
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
        logger.error(f"kis_connect upsert failed user_id={current_user.id}: {exc}")
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


# ── POST /api/broker/kiwoom/csv ───────────────────────────────────────────
#
# Upload the 영웅문 HTS 잔고 export (.xls / .xlsx / .csv) and merge it into
# the user's `positions` table. We do NOT store the raw credentials — Kiwoom
# OAuth (api.kiwoom.com) requires a separate review; this CSV path is the
# interim zero-approval option.
#
# Request:  multipart/form-data with field name `file` (<= 5 MB).
# Success:  200 {"ok": true, "imported": N, "updated": M, "tickers": [...]}
# Errors:   400 parse / 403 tier limit / 404 etc., all with {error, code}.
_KIWOOM_CSV_BROKER = "kiwoom_csv"
_KIWOOM_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_KIWOOM_ALLOWED_EXTS = (".xls", ".xlsx", ".csv")


def _upsert_kiwoom_csv_connection(user_id: int) -> BrokerConnection:
    """Record `kiwoom_csv` broker row so /status shows 'last import' time.

    We reuse BrokerConnection to keep one table. broker='kiwoom_csv' holds
    only last_synced_at + display_name — no encrypted credentials, since
    this path has none to store.
    """
    conn = BrokerConnection.query.filter_by(
        user_id=user_id, broker=_KIWOOM_CSV_BROKER
    ).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if conn is None:
        conn = BrokerConnection(
            user_id=user_id,
            broker=_KIWOOM_CSV_BROKER,
            is_paper=False,
            is_active=True,
            display_name="키움 영웅문 (CSV)",
            last_synced_at=now,
            last_sync_status="ok",
            consecutive_failures=0,
        )
        db.session.add(conn)
    else:
        conn.is_active = True
        conn.last_synced_at = now
        conn.last_sync_status = "ok"
        conn.last_sync_error = None
        conn.consecutive_failures = 0
    return conn


@broker_oauth_bp.route("/kiwoom/csv", methods=["POST"])
@trade_rate_limit
@api_auth
def kiwoom_upload_csv():
    """Parse a 영웅문 balance export and merge into positions."""
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({
            "error": "No file uploaded",
            "error_kr": "업로드된 파일이 없습니다.",
            "code": "CSV_NO_FILE",
        }), 400

    filename = uploaded.filename
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in _KIWOOM_ALLOWED_EXTS:
        return jsonify({
            "error": f"Unsupported file extension: {ext or 'none'}",
            "error_kr": "지원하지 않는 파일 형식입니다. .xls / .xlsx / .csv 만 업로드 가능합니다.",
            "code": "CSV_BAD_EXTENSION",
        }), 400

    data = uploaded.read()
    if not data:
        return jsonify({
            "error": "Empty file",
            "error_kr": "업로드된 파일이 비어 있습니다.",
            "code": "CSV_EMPTY",
        }), 400
    if len(data) > _KIWOOM_MAX_BYTES:
        return jsonify({
            "error": f"File too large ({len(data)} bytes > 5MB)",
            "error_kr": "파일 크기가 5MB를 초과합니다.",
            "code": "CSV_TOO_LARGE",
        }), 400

    try:
        parsed_rows = parse_kiwoom_balance_file(data, filename)
    except UserKiwoomCSVError as exc:
        return jsonify({
            "error": exc.message,
            "error_kr": exc.message,
            "code": exc.code,
        }), 400
    except Exception as exc:  # pragma: no cover
        logger.exception(f"kiwoom_csv parse failed user_id={current_user.id}")
        return jsonify({
            "error": "Failed to parse file",
            "error_kr": "파일 파싱 중 알 수 없는 오류가 발생했습니다.",
            "code": "CSV_PARSE_FAILED",
        }), 400

    # ── Tier check: Free plan limited to 3 TOTAL positions ────────────────
    # We compute post-merge count BEFORE writing, so free users don't get
    # a partial import. Existing tickers in the upload don't count against
    # the 3-position cap since they only mutate an existing row.
    tier = getattr(current_user, "effective_tier", None) or getattr(current_user, "subscription_tier", None) or "free"
    if tier == "free":
        existing_tickers = {
            p.ticker
            for p in Position.query.filter_by(user_id=current_user.id).all()
        }
        new_tickers = {row["ticker"] for row in parsed_rows} - existing_tickers
        projected = len(existing_tickers) + len(new_tickers)
        if projected > 3:
            return jsonify({
                "error": "Free plan limited to 3 positions",
                "error_kr": (
                    f"무료 플랜은 포지션 3개까지만 가능합니다. "
                    f"(현재 {len(existing_tickers)}개 + 신규 {len(new_tickers)}개 = {projected}개) "
                    "Pro 요금제로 업그레이드하시면 무제한입니다."
                ),
                "code": "TIER_LIMIT",
                "current_count": len(existing_tickers),
                "projected_count": projected,
                "limit": 3,
            }), 403

    # ── Merge into positions table (weighted-average avg_cost on conflict) ─
    imported = 0
    updated = 0
    imported_tickers: list[str] = []
    try:
        for row in parsed_rows:
            ticker = row["ticker"]
            shares = float(row["shares"])
            avg_cost = float(row["avg_cost"])

            existing = Position.query.filter_by(
                user_id=current_user.id, ticker=ticker
            ).first()
            if existing is None:
                db.session.add(Position(
                    user_id=current_user.id,
                    ticker=ticker,
                    shares=shares,
                    avg_cost=avg_cost,
                    buy_fx_rate=0.0,  # KR stocks: no FX
                    thesis_status="pending",
                ))
                imported += 1
            else:
                total_shares = (existing.shares or 0) + shares
                if total_shares > 0 and existing.avg_cost and existing.shares:
                    # Weighted average of the two buy bases.
                    existing.avg_cost = (
                        existing.avg_cost * existing.shares + avg_cost * shares
                    ) / total_shares
                else:
                    existing.avg_cost = avg_cost
                existing.shares = total_shares
                updated += 1
            imported_tickers.append(ticker)

        _upsert_kiwoom_csv_connection(current_user.id)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception(f"kiwoom_csv DB merge failed user_id={current_user.id}")
        return jsonify({
            "error": f"Failed to save positions: {exc}",
            "error_kr": "포지션 저장에 실패했습니다. 잠시 후 다시 시도해주세요.",
            "code": "CSV_PERSIST_FAILED",
        }), 500

    return jsonify({
        "ok": True,
        "imported": imported,
        "updated": updated,
        "tickers": imported_tickers,
    }), 200
