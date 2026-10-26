"""Doorway routes — 문 앞의 한 줄 (증권 앱을 여는 순간의 답).

Endpoints (all under ``/api/doorway``):

    POST   /webhook             — 폰 자동화가 보낸다 (Bearer 가져오기 토큰, 세션 없음)
    POST   /checks              — 웹의 /door 화면이 보낸다 (세션 + CSRF)

    두 POST 모두 답(보기·살·팔) 또는 열림 신호(``{"text": "열림"}`` ·
    ``{"intent": "open"}``)를 받는다 — 신호는 질문 전에 먼저 와서 답하지 않은
    열림도 남기고, 이어 온 답이 그 행에 붙는다 (services/doorway, 2026-10-26).
    GET    /checks              — 본인 열림 목록, id 커서
    DELETE /checks/<id>         — 하나 지우기
    GET    /summary?days=30     — 열림 × 체결 개수 (거울 카드)

설계 docs/design/doorway-pause_2026-10-15.md. 검증·소유 필터·맞추는 규칙은
전부 services/doorway/service.py 에 있고 이 파일은 얇다.

토큰
----
체결 자동 기록(routes/imports.py ``/webhook``)과 같은 개인 가져오기 토큰을
쓴다. 단 발급 동의 문구에 문 앞 기록이 들어간 뒤 만든 열쇠만
(``import_tokens.doorway_consent_at``) — 그 전 열쇠는 403
``DOORWAY_TOKEN_RECONSENT``. 인증은 ``import_token_auth`` 를 그대로
재사용한다(두 벌 금지): 삭제 유예 중인 계정은 폐기된 토큰처럼 거절되고, 실패는
한 코드로 묶여 토큰 존재를 흘리지 않는다. 세션이 없으므로 CSRF 는
``security._csrf_protect`` 가 건너뛴다.

Legal posture
-------------
모든 응답은 ``@legal_scrub_response`` 를 거친다. 유저 본인이 적은 한 줄
(``note``)만 ``skip_keys`` 로 원문을 둔다 — research_notes 와 같은 이유. 우리가
붙이는 것은 개수와 면책 문구(SoT services/legal/disclaimers.py)뿐이며 점수·
등급·지시를 만들지 않는다. 시세를 부르지 않는다. 증권 앱·주문에 닿지 않는다.
"""
from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request
from flask_login import current_user

from extensions import db
from models.doorway_check import SOURCE_AUTOMATION, SOURCE_WEB
from services.doorway import (
    DoorwayInputError,
    delete_check,
    doorway_summary,
    list_checks,
    pause_path,
    record_check,
    reply_line,
)
from services.error_responses import api_error
from services.imports import utcnow_naive
from services.legal.disclaimers import DISCLAIMER_ARTIFACT_KR

from .decorators import api_auth, legal_scrub_response
from .imports import import_token_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

doorway_bp = Blueprint("doorway", __name__, url_prefix="/api/doorway")

_DISCLAIMER = DISCLAIMER_ARTIFACT_KR
_NOT_FOUND = "DOORWAY_NOT_FOUND"

# The user's own one line — kept verbatim through the scrub.
_USER_TEXT = ("note",)
_scrub = legal_scrub_response(skip_keys=_USER_TEXT)


def _envelope(payload: dict, *, status: int = 200):
    body = {"ok": True, "disclaimer": _DISCLAIMER}
    body.update(payload)
    return jsonify(body), status


def _input_error(exc: DoorwayInputError):
    return api_error(en=exc.en, kr=exc.kr, code=exc.code, status=exc.status)


def _created(user_id: int, source: str):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        # 단축어·MacroDroid 가 본문을 text/plain 으로 보내도 받는다 — 글 전체를
        # "보기 / 살 … / 팔 …" 한 줄로 읽는다.
        raw = request.get_data(as_text=True) if request.mimetype == "text/plain" else ""
        data = {"text": raw} if raw.strip() else {}
    try:
        result = record_check(user_id, data, source=source)
    except DoorwayInputError as exc:
        return _input_error(exc)
    # 201 = a new row. 200 = no new row: a repeated open signal, or an answer
    # joined to the open signal sent just before it.
    check = result["check"]
    path = pause_path(check)
    pause_url = None
    if path:
        from services.email.urls import _frontend

        pause_url = f"{_frontend()}{path}"
    return _envelope({
        "check": check,
        "today": result["today"],
        # 자동화가 '알림 보기'로 띄울 한 줄 — 개수만.
        "message": reply_line(check, result["today"]),
        "pause_url": pause_url,
    }, status=201 if result.get("created", True) else 200)


@doorway_bp.route("/webhook", methods=["POST"])
@general_rate_limit  # outermost so an invalid-token 401 is rate-limited too
@import_token_auth
@_scrub
def webhook_check():
    # A token issued before the consent text named door answers never agreed
    # to this item (PIPA §15·§22 — legal-kr-fintech review 2026-10-15). It
    # still works for fills; door answers need a newly issued token. Nothing
    # from the refused request is stored.
    if getattr(g.import_token, "doorway_consent_at", None) is None:
        return api_error(
            en="This token was issued before doorway answers were part of its consent. "
               "Create a new token in Settings.",
            kr="이 연결 열쇠는 문 앞의 한 줄 동의 문구가 생기기 전에 만들었어요. "
               "설정 → 체결 자동 기록에서 새 열쇠를 만들어 바꿔 주세요.",
            code="DOORWAY_TOKEN_RECONSENT", status=403,
        )
    result = _created(g.import_user_id, SOURCE_AUTOMATION)
    if result[1] not in (200, 201):
        return result
    # 설정의 "마지막 사용"이 문 앞으로만 쓰는 열쇠에도 맞게 — imports.webhook 과 같다.
    token = g.import_token
    token.last_used_at = utcnow_naive()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning("doorway.webhook last_used_at update failed token_id=%s", token.id)
    return result


@doorway_bp.route("/checks", methods=["POST"])
@api_auth
@general_rate_limit
@_scrub
def create_check():
    return _created(current_user.id, SOURCE_WEB)


@doorway_bp.route("/checks", methods=["GET"])
@api_auth
@general_rate_limit
@_scrub
def get_checks():
    try:
        limit = int(request.args.get("limit", 50))
        before = request.args.get("before")
        before_id = int(before) if before else None
    except (TypeError, ValueError):
        return api_error(en="Bad paging.", kr="요청 형식이 올바르지 않습니다.",
                         code="DOORWAY_BAD_INPUT", status=400)
    return _envelope(list_checks(current_user.id, limit=limit, before_id=before_id))


@doorway_bp.route("/checks/<int:check_id>", methods=["DELETE"])
@api_auth
@general_rate_limit
@_scrub
def remove_check(check_id: int):
    if not delete_check(current_user.id, check_id):
        # Someone else's row is a 404, never a 403 — we don't leak existence.
        return api_error(en="Not found", kr="문 앞 기록을 찾을 수 없습니다.",
                         code=_NOT_FOUND, status=404)
    return _envelope({"deleted": check_id})


@doorway_bp.route("/summary", methods=["GET"])
@api_auth
@general_rate_limit
@_scrub
def summary():
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = -1
    try:
        payload = doorway_summary(current_user.id, days=days)
    except DoorwayInputError as exc:
        return _input_error(exc)
    return _envelope(payload)
