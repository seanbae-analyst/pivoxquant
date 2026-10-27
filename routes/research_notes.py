"""Research notes routes — 리서치 양식 + 정한 날 다시 채점.

Endpoints (all under ``/api/research-notes``):

    POST   /                    — write one research note (201)
    GET    /list                — own notes, newest first, id cursor
    GET    /overview            — due notes + judgment × outcome counts
    GET    /by-ticker/<ticker>  — latest note on one ticker (/pre-trade 가 읽는다)
    GET    /<id>                — one note
    DELETE /<id>                — hard delete (양식 자체는 수정 없음)
    POST   /<id>/review         — score: one verdict per thesis (+ a line)

설계 docs/design/research-notes_2026-10-15.md. 검증·소유 필터는 전부
services/research_notes/service.py 에 있고 이 파일은 얇다.

Legal posture
-------------
모든 응답은 ``@legal_scrub_response`` 를 거친다. 다만 유저 본인이 양식에 쓴
서술 칸(``_USER_TEXT``)만 ``skip_keys`` 로 원문 그대로 둔다 — 리포트에서 옮겨
적은 "목표가 상향" 같은 본인 문장을 서버가 고쳐 돌려주면 그건 기록이 아니다.
나머지(종목명·면책 문구·에러 문구·집계 키)는 전부 스크럽된다. 별도 예외
표식(legal-exempt)을 쓰지 않는다 — legal-kr-fintech 에이전트 검토 2026-10-15
(변호사 확인 전 · docs/design/research-notes_2026-10-15.md §7).
우리가 붙이는 것은 집계 숫자(개수)와 면책 문구(SoT services/legal/disclaimers.py)
뿐이며, 점수·등급·지시를 만들지 않는다. 양식은 모든 종목에 같고 종목별 정보·숫자를 우리가 채우지 않는다(자본시장법 §6
투자자문 경계, FMP §2.2.2). 시세를 부르지 않는다. 주문을 넣지 않는다.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.error_responses import api_error
from services.legal.disclaimers import DISCLAIMER_ARTIFACT_KR
from services.research_notes import (
    create_research,
    delete_research,
    get_research,
    list_research,
    research_for_ticker,
    research_overview,
    review_research,
)

from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit

logger = logging.getLogger(__name__)

research_notes_bp = Blueprint("research_notes", __name__, url_prefix="/api/research-notes")

_DISCLAIMER = DISCLAIMER_ARTIFACT_KR
_BAD_INPUT = "RESEARCH_BAD_INPUT"
_NOT_FOUND = "RESEARCH_NOT_FOUND"

# The user's own words — kept verbatim through the scrub (see Legal posture).
_USER_TEXT = ("business", "theses", "invalidation", "risk", "numbers", "review_note")
_scrub = legal_scrub_response(skip_keys=_USER_TEXT)


def _envelope(payload: dict, *, status: int = 200):
    body = {"ok": True, "disclaimer": _DISCLAIMER}
    body.update(payload)
    return jsonify(body), status


def _bad_input(exc: Exception):
    return api_error(en=str(exc)[:200], kr="입력값이 올바르지 않습니다.", code=_BAD_INPUT, status=400)


def _not_found():
    """Someone else's note is a 404, never a 403 — we don't leak existence."""
    return api_error(en="Not found", kr="리서치 노트를 찾을 수 없습니다.", code=_NOT_FOUND, status=404)


@research_notes_bp.route("", methods=["POST"])
@research_notes_bp.route("/", methods=["POST"])
@api_auth
@_scrub
@general_rate_limit
def create():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _bad_input(ValueError("body must be a JSON object"))
    try:
        note = create_research(current_user.id, data)
    except ValueError as exc:
        return _bad_input(exc)
    return _envelope({"note": note}, status=201)


@research_notes_bp.route("/list", methods=["GET"])
@api_auth
@_scrub
@general_rate_limit
def list_own():
    """Own notes, newest first. ``?limit=`` (≤200) ``?before=<id>`` ``?ticker=``
    + 다시 찾기 ``?q=`` ``?source=`` ``?status=`` ``?since=`` ``?until=``
    (services/research_notes/service.py::list_research)."""
    args = request.args
    try:
        return _envelope(
            list_research(
                current_user.id,
                limit=args.get("limit", default=None),
                before=args.get("before", default=None),
                ticker=args.get("ticker", default=None),
                q=args.get("q", default=None),
                source=args.get("source", default=None),
                status=args.get("status", default=None),
                since=args.get("since", default=None),
                until=args.get("until", default=None),
            )
        )
    except ValueError as exc:
        return _bad_input(exc)


@research_notes_bp.route("/overview", methods=["GET"])
@api_auth
@_scrub
@general_rate_limit
def overview():
    return _envelope(research_overview(current_user.id))


@research_notes_bp.route("/by-ticker/<ticker>", methods=["GET"])
@api_auth
@_scrub
@general_rate_limit
def by_ticker(ticker: str):
    """Latest note on one ticker — read-only for /pre-trade, so the 멈춤
    화면 never becomes a way to write around the 7 questions."""
    try:
        return _envelope(research_for_ticker(current_user.id, ticker))
    except ValueError as exc:
        return _bad_input(exc)


@research_notes_bp.route("/<int:note_id>", methods=["GET"])
@api_auth
@_scrub
def get_one(note_id: int):
    try:
        return _envelope({"note": get_research(note_id, current_user.id)})
    except LookupError:
        return _not_found()


@research_notes_bp.route("/<int:note_id>", methods=["DELETE"])
@api_auth
@_scrub
@general_rate_limit
def remove(note_id: int):
    try:
        return _envelope({"deleted": delete_research(note_id, current_user.id)})
    except LookupError:
        return _not_found()


@research_notes_bp.route("/<int:note_id>/review", methods=["POST"])
@api_auth
@_scrub
@general_rate_limit
def review(note_id: int):
    data = request.get_json(silent=True)
    try:
        note = review_research(note_id, current_user.id, data)
    except LookupError:
        return _not_found()
    except ValueError as exc:
        return _bad_input(exc)
    return _envelope({"note": note})
