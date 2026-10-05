"""월간 거울 리포트 — 온디맨드 다운로드와 앱 안 보기.

* ``GET /api/reports/mirror.pdf`` — 로그인한 사용자가 **자기** 리포트를 그
  자리에서 PDF 로 받는다.
* ``GET /api/reports/mirror`` (2026-10-05) — 같은 리포트를 JSON 으로. 앱의
  ``/journal/report`` 화면이 그린다. 숫자는 PDF 와 같은 ``build_mirror_report``
  에서, 문구는 PDF 템플릿과 같은 ``mirror_labels`` 에서 온다 — 계산도 말도
  두 벌이 아니다. PDF 렌더가 없어 싸므로 일반 레이트리밋을 쓴다. 되비출 기록이
  없어도 404 가 아니라 ``has_content: false`` 로 200 을 준다 — 화면은 빈 상태를
  그 자리에서 말한다.

본인 것만
=========
대상 사용자는 언제나 ``current_user.id`` 다. user id 를 쿼리 파라미터로
받지 않는다 — 받는 순간 열거(enumeration) 표면이 생기고, 그건 PIPA §29 가
막으라는 바로 그 형태다. 다른 사람 리포트를 받을 방법은 이 라우트에 없다.

레이트리밋
==========
PDF 렌더는 이 앱에서 한 요청이 할 수 있는 가장 비싼 일에 속한다. 그래서
``@report_render_rate_limit`` — **유저 단위** 5/min · 20/hour 다. 일반
60/min 은 두 가지로 모자랐다: 키가 IP 라 공유 NAT 을 벌주면서 주소를
바꿀 수 있는 공격자는 그만큼 곱하기였고, Procfile 이 gevent 워커 하나라
순수 파이썬 CPU 인 WeasyPrint 렌더가 도는 동안 **다른 모든 유저의 요청이
멈춘다**. 2026-09-01 에 소비자와 함께 지워졌던 artefact 전용 리미터를
"엔드포인트와 함께 되살리라"던 security.py 의 주석대로 되살린 것이다.

응답 계약
=========
* 200 — ``application/pdf`` + ``Content-Disposition: attachment;
  filename="pivoxquant_mirror_<yyyy-mm>.pdf"``
* 404 ``MIRROR_REPORT_EMPTY`` — 되비출 기록이 없다 (``has_content`` False).
  빈 PDF 를 돌려주지 않는다. 0바이트짜리 문서를 받는 것보다 "아직 없다"는
  말을 듣는 편이 언제나 낫다.
* 500 ``MIRROR_REPORT_FAILED`` — 렌더러 부재 / 렌더 실패.
* 401 — ``@api_auth`` (SESSION_EXPIRED).

``@legal_scrub_response`` 는 JSON 응답에만 작용하고 바이너리 응답에는
no-op 이다 (routes/decorators.py). 위 에러 본문은 스크럽되고 PDF 는 그대로
나간다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, Response, jsonify, make_response, request
from flask_login import current_user

from security import general_rate_limit, report_render_rate_limit
from services.error_responses import api_error
from services.reports import mirror_pdf as _mirror_pdf
from services.reports_delivery import (
    REPORT_PERIOD_DAYS,
    build_mirror_pdf,
    mirror_report_filename,
)

from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)


def _no_store(f):
    """개인 기록 — 공유 캐시·프록시에 남기지 않는다. ``legal_scrub_response`` 가
    JSON 응답을 새로 만들어 뷰 안의 헤더를 버리므로, 그 바깥에서 단다."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        resp = make_response(f(*args, **kwargs))
        resp.headers["Cache-Control"] = "private, no-store"
        return resp
    return wrapped

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.route("/mirror.pdf", methods=["GET"])
@api_auth
@report_render_rate_limit
@legal_scrub_response
def mirror_pdf():
    """본인의 월간 거울 리포트를 PDF 로 내려준다."""
    user_id = current_user.id
    locale = (getattr(current_user, "locale", "") or "ko").lower()

    try:
        built = build_mirror_pdf(user_id, locale=locale)
    except Exception:
        logger.exception("mirror report render failed for user %s", user_id)
        return api_error(
            en="Failed to build the mirror report.",
            kr="거울 리포트를 만들지 못했습니다.",
            code="MIRROR_REPORT_FAILED",
            status=500,
        )

    if built is None:
        return api_error(
            en="There is not enough of your record yet to mirror back.",
            kr="아직 되비출 기록이 충분하지 않습니다.",
            code="MIRROR_REPORT_EMPTY",
            status=404,
        )

    _data, pdf_bytes = built
    filename = mirror_report_filename(
        datetime.now(timezone.utc).replace(tzinfo=None)
    )

    resp = Response(pdf_bytes, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.headers["Content-Length"] = str(len(pdf_bytes))
    # 개인 기록이다 — 공유 캐시나 프록시에 남지 않게 한다.
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@reports_bp.route("/mirror", methods=["GET"])
@api_auth
@general_rate_limit
@_no_store
@legal_scrub_response
def mirror_json():
    """본인의 월간 거울 리포트를 JSON 으로 — 앱 안 보기용.

    Query: ``?locale=ko|en`` (없으면 계정 locale, 그다음 ko). 대상은 언제나
    ``current_user.id`` 다 — user id 를 받지 않는다 (PDF 라우트와 같은 이유).
    """
    user_id = current_user.id
    locale = (
        request.args.get("locale")
        or getattr(current_user, "locale", "")
        or "ko"
    ).lower()
    if locale not in ("ko", "en"):
        locale = "ko"

    try:
        data = _mirror_pdf.build_mirror_report(user_id, period_days=REPORT_PERIOD_DAYS)
    except Exception:
        logger.exception("mirror report build failed for user %s", user_id)
        return api_error(
            en="Failed to build the mirror report.",
            kr="거울 리포트를 만들지 못했습니다.",
            code="MIRROR_REPORT_FAILED",
            status=500,
        )

    # user_id 는 화면에 쓸 데가 없다 — 응답에 싣지 않는다.
    report = {k: v for k, v in data.items() if k != "user_id"}
    return jsonify({
        "ok": True,
        "locale": locale,
        "report": report,
        "labels": _mirror_pdf.mirror_labels(locale),
    })
