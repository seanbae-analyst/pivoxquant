"""월간 거울 리포트 — 온디맨드 다운로드.

``GET /api/reports/mirror.pdf`` 하나뿐이다. 로그인한 사용자가 **자기**
리포트를 그 자리에서 PDF 로 받는다.

본인 것만
=========
대상 사용자는 언제나 ``current_user.id`` 다. user id 를 쿼리 파라미터로
받지 않는다 — 받는 순간 열거(enumeration) 표면이 생기고, 그건 PIPA §29 가
막으라는 바로 그 형태다. 다른 사람 리포트를 받을 방법은 이 라우트에 없다.

레이트리밋
==========
PDF 렌더는 이 앱에서 한 요청이 할 수 있는 가장 비싼 일에 속한다. 다른
라우트와 같은 ``@general_rate_limit`` 을 건다 (60/min). 더 좁은
artefact 전용 리미터는 2026-09-01 에 소비자와 함께 security.py 에서
지워졌고, 되살리려면 그 파일을 건드려야 하므로 여기서는 기존 데코레이터를
그대로 쓴다.

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

from flask import Blueprint, Response
from flask_login import current_user

from security import general_rate_limit
from services.error_responses import api_error
from services.reports_delivery import build_mirror_pdf, mirror_report_filename

from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.route("/mirror.pdf", methods=["GET"])
@api_auth
@general_rate_limit
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
