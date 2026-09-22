"""Observation notes routes — 거래 없이 적어 두는 관찰 기록.

Endpoints (all under ``/api/observation-notes``):

    POST   /                    — write one note (201)
    GET    /list                — own notes, newest first, id cursor
    GET    /<id>                — one note
    DELETE /<id>                — hard delete (append-only + 삭제 정책)
    GET    /by-ticker/<ticker>  — recent notes on one ticker (/pre-trade 가 읽는다)

설계 docs/design/observation-notes_2026-09-22.md §3. 검증·소유 필터는 전부
services/observation_notes/service.py 에 있고 이 파일은 얇다 —
routes/pre_trade.py 와 동일한 분업.

Legal posture
-------------
# legal-exempt: 이 파일의 모든 응답은 유저 본인이 쓴 사적 기록을 원문 그대로
# 본인에게만 돌려준다. 서버가 그 문장을 고쳐서 돌려주면 그건 더 이상 "기록"이
# 아니므로 @legal_scrub_response 를 붙이지 않는다 — routes/pre_trade.py 와
# 같은 판단이고, 설계 문서 §3 의 명시된 결정이다. 우리가 붙이는 카피(면책
# 문구)는 SoT(services/legal/disclaimers.py)에서 가져온다.
이 라우트는 주문을 넣지 않는다 — 어떤 라우트도 넣지 않는다. 노트는 유저가
관찰한 바를 적어 둔 사실 기록이고, 우리는 그것으로 어떤 지시도 만들지
않는다 (자본시장법 §49 분리). 시세도 부르지 않는다.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.error_responses import api_error
from services.legal.disclaimers import DISCLAIMER_ARTIFACT_KR
from services.observation_notes import (
    create_note,
    delete_note,
    get_note,
    list_notes,
    notes_for_ticker,
)

from .decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

observation_notes_bp = Blueprint(
    "observation_notes", __name__, url_prefix="/api/observation-notes"
)

# Stamped onto every response so a screen-grab of the payload carries the
# same legal floor as every other surface. Single source of truth — never a
# local copy of the text (tests/test_disclaimer_sot.py).
_DISCLAIMER = DISCLAIMER_ARTIFACT_KR

_BAD_INPUT = "OBS_NOTE_BAD_INPUT"
_NOT_FOUND = "OBS_NOTE_NOT_FOUND"


def _envelope(payload: dict, *, status: int = 200):
    body = {"ok": True, "disclaimer": _DISCLAIMER}
    body.update(payload)
    return jsonify(body), status


def _bad_input(exc: Exception):
    return api_error(
        en=str(exc)[:200],
        kr="입력값이 올바르지 않습니다.",
        code=_BAD_INPUT,
        status=400,
    )


def _not_found():
    """Someone else's note is a 404, never a 403 — we don't leak existence."""
    return api_error(
        en="Not found",
        kr="관찰 노트를 찾을 수 없습니다.",
        code=_NOT_FOUND,
        status=404,
    )


# ── POST / ──────────────────────────────────────────────────────────

@observation_notes_bp.route("", methods=["POST"])
@observation_notes_bp.route("/", methods=["POST"])
@api_auth
@general_rate_limit
def create():
    data = request.get_json(silent=True)
    # A JSON array or scalar body would reach data.get() and 500.
    if not isinstance(data, dict):
        return _bad_input(ValueError("body must be a JSON object"))
    try:
        note = create_note(
            user_id=current_user.id,
            body=data.get("body"),
            tickers=data.get("tickers"),
            tags=data.get("tags"),
            source=data.get("source"),
        )
    except ValueError as exc:
        return _bad_input(exc)
    return _envelope({"note": note}, status=201)


# ── GET /list ───────────────────────────────────────────────────────

@observation_notes_bp.route("/list", methods=["GET"])
@api_auth
@general_rate_limit
def list_own():
    """The caller's own notes, newest first.

    Query: ``?limit=`` (default 50, clamped to 200), ``?before=<id>``
    (cursor), ``?ticker=``, ``?tag=``. User isolation is enforced in the
    service layer — only ``current_user.id`` rows are ever returned.
    """
    result = list_notes(
        current_user.id,
        limit=request.args.get("limit", default=None),
        before=request.args.get("before", default=None),
        ticker=request.args.get("ticker", default=None),
        tag=request.args.get("tag", default=None),
    )
    return _envelope(result)


# ── GET /<id> ───────────────────────────────────────────────────────

@observation_notes_bp.route("/<int:note_id>", methods=["GET"])
@api_auth
def get_one(note_id: int):
    try:
        note = get_note(note_id, current_user.id)
    except LookupError:
        return _not_found()
    return _envelope({"note": note})


# ── DELETE /<id> ────────────────────────────────────────────────────

@observation_notes_bp.route("/<int:note_id>", methods=["DELETE"])
@api_auth
@general_rate_limit
def remove(note_id: int):
    try:
        deleted = delete_note(note_id, current_user.id)
    except LookupError:
        return _not_found()
    return _envelope({"deleted": deleted})


# ── GET /by-ticker/<ticker> ─────────────────────────────────────────

@observation_notes_bp.route("/by-ticker/<ticker>", methods=["GET"])
@api_auth
@general_rate_limit
def by_ticker(ticker: str):
    """Recent notes the caller wrote on one ticker — /pre-trade reads this.

    Query: ``?days=`` (default 30), ``?limit=`` (default 5). Read-only on
    purpose: the 멈춤 화면에서 노트를 *쓰게* 하면 7문항을 피하는 통로가
    된다 (설계 §5 진입점).
    """
    try:
        result = notes_for_ticker(
            current_user.id,
            ticker,
            days=request.args.get("days", default=None),
            limit=request.args.get("limit", default=None),
        )
    except ValueError as exc:
        return _bad_input(exc)
    return _envelope(result)
