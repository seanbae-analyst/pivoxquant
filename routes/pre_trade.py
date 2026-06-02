"""Pre-Trade Friction routes — Feature 6.

Endpoints (all under ``/api/pre-trade``):

    POST /start           — open a fresh reflection, returns id + cooldown_ends_at
    GET  /list            — the caller's own reflections, newest first (Journal feed)
    GET  /<id>            — current status + seconds_remaining
    POST /<id>/proceed    — stamp proceeded_at (cooldown must have elapsed)
    POST /<id>/cancel     — abort the reflection

Legal posture
-------------
This route NEVER places an order. ``/proceed`` only marks the reflection
record as "the user finished thinking"; the actual broker call lives in
the existing portfolio / autotrade routes and is invoked by the
frontend separately. Every payload is suffixed with the standard
information-only disclaimer so a screen-grab of the response can't be
misread as a recommendation.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.error_responses import api_error
from services.pre_trade import (
    cancel as cancel_reflection,
    check_status,
    list_reflections,
    proceed as proceed_reflection,
    start_cooldown,
    storage_proof,
)

from .decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

pre_trade_bp = Blueprint("pre_trade", __name__, url_prefix="/api/pre-trade")


# Stamped onto every response — keeps the legal floor explicit.
_DISCLAIMER = (
    "본 도구는 사용자가 자신의 거래 결정에 reflection 시간을 확보하도록 돕는 "
    "정보 제공용 UX 입니다. 거래 권유가 아닙니다."
)


def _envelope(payload: dict, *, status: int = 200):
    body = {"ok": True, "disclaimer": _DISCLAIMER}
    body.update(payload)
    return jsonify(body), status


# ── /start ──────────────────────────────────────────────────────────

@pre_trade_bp.route("/start", methods=["POST"])
@api_auth
@general_rate_limit
def start():
    data = request.get_json(silent=True) or {}
    ticker = data.get("ticker")
    side = data.get("side")
    shares = data.get("shares")
    rationale = data.get("rationale") or ""
    devil = data.get("devil_advocate")
    market_volatility = data.get("market_volatility")

    try:
        result = start_cooldown(
            user_id=current_user.id,
            ticker=ticker,
            side=side,
            shares=shares,
            rationale=rationale,
            devil_advocate=devil,
            market_volatility=market_volatility,
        )
    except ValueError as exc:
        return api_error(
            en=str(exc)[:200],
            kr="입력값이 올바르지 않습니다.",
            code="PRE_TRADE_BAD_INPUT",
            status=400,
        )
    return _envelope({"reflection": result})


# ── /list ───────────────────────────────────────────────────────────

@pre_trade_bp.route("/list", methods=["GET"])
@api_auth
def list_own():
    """Journal feed: the caller's own reflections, newest (created_at) first.

    Query: ``?limit=`` (default 50, clamped to 200). User isolation is
    enforced in the service layer — only ``current_user.id`` rows are
    ever returned.
    """
    raw_limit = request.args.get("limit", default=None)
    rows = list_reflections(current_user.id, limit=raw_limit if raw_limit is not None else 50)
    return _envelope({"reflections": rows})


# ── /<id> ───────────────────────────────────────────────────────────

@pre_trade_bp.route("/<int:reflection_id>", methods=["GET"])
@api_auth
def get_status(reflection_id: int):
    try:
        result = check_status(reflection_id, current_user.id)
    except LookupError:
        return api_error(
            en="Not found",
            kr="reflection을 찾을 수 없습니다.",
            code="PRE_TRADE_NOT_FOUND",
            status=404,
        )
    return _envelope({"reflection": result})


# ── /<id>/storage-proof ─────────────────────────────────────────────

@pre_trade_bp.route("/<int:reflection_id>/storage-proof", methods=["GET"])
@api_auth
def storage_proof_view(reflection_id: int):
    """Trust artifact — show the caller their OWN free-text exactly as it is
    stored (ciphertext), so they witness the at-rest encryption instead of
    reading a claim about it. Ownership enforced in the service layer."""
    try:
        result = storage_proof(reflection_id, current_user.id)
    except LookupError:
        return api_error(
            en="Not found",
            kr="reflection을 찾을 수 없습니다.",
            code="PRE_TRADE_NOT_FOUND",
            status=404,
        )
    return _envelope({"storage_proof": result})


# ── /<id>/proceed ───────────────────────────────────────────────────

@pre_trade_bp.route("/<int:reflection_id>/proceed", methods=["POST"])
@api_auth
@general_rate_limit
def proceed(reflection_id: int):
    try:
        result = proceed_reflection(reflection_id, current_user.id)
    except LookupError:
        return api_error(
            en="Not found",
            kr="reflection을 찾을 수 없습니다.",
            code="PRE_TRADE_NOT_FOUND",
            status=404,
        )
    except ValueError as exc:
        # 409 Conflict — the resource exists but the requested transition
        # is invalid (cooldown not elapsed, or already terminal).
        return api_error(
            en=str(exc)[:200],
            kr="현재 상태에서 처리할 수 없습니다.",
            code="PRE_TRADE_INVALID_STATE",
            status=409,
        )
    return _envelope({"reflection": result})


# ── /<id>/cancel ────────────────────────────────────────────────────

@pre_trade_bp.route("/<int:reflection_id>/cancel", methods=["POST"])
@api_auth
@general_rate_limit
def cancel(reflection_id: int):
    try:
        result = cancel_reflection(reflection_id, current_user.id)
    except LookupError:
        return api_error(
            en="Not found",
            kr="reflection을 찾을 수 없습니다.",
            code="PRE_TRADE_NOT_FOUND",
            status=404,
        )
    except ValueError as exc:
        return api_error(
            en=str(exc)[:200],
            kr="현재 상태에서 처리할 수 없습니다.",
            code="PRE_TRADE_INVALID_STATE",
            status=409,
        )
    return _envelope({"reflection": result})
