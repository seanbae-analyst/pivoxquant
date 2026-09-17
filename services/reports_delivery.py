"""월간 거울 리포트 — 발송 / 전달 계층.

이 모듈이 하는 일
=================
PDF 를 *만드는* 쪽은 ``services/reports/mirror_pdf.py`` 다. 이 파일은 그
결과물을 사용자에게 **전달**하는 두 경로만 담당한다.

1. **온디맨드 다운로드** — ``routes/reports.py`` 가 :func:`build_mirror_pdf`
   를 호출해 본인 리포트를 그 자리에서 내려준다.
2. **월 1회 이메일** — :func:`main` 이 APScheduler 크론
   (``services/scheduler/cron_jobs.py::ops_monthly_mirror_report``, 매월 1일
   08:30 KST) 에서 불린다.

렌더러 계약
===========
::

    data      = build_mirror_report(user_id, period_days=30)
    pdf_bytes = render_mirror_pdf(data, locale="ko")

``data["has_content"]`` 가 False 면 그 사용자에게는 되비출 기록이 없다는
뜻이다. 이때는 PDF 를 만들지 않고, 이메일도 보내지 않는다 — 빈 리포트를
보내는 순간 그 메일은 "기록의 회고"가 아니라 복귀를 권하는 메일이 되고,
그건 ``services/email/record_summary.py`` 의 침묵 규칙이 피하려는 바로 그
형태다.

정통망법 §50 분류
=================
정기 서비스 리포트 = **정보성**(:class:`EmailCategory.INFORMATION`).
TRANSACTIONAL 이 아니다 — 계정/보안/영수증이 아니라 주기적으로 발신자가
먼저 보내는 메일이므로 TRANSACTIONAL 로 부르는 것은 §50 동의 게이트를
우회하는 것이 된다. 발송 게이트는 세 겹이다:

* 알림 설정의 ``monthly_mirror`` × email 채널 (기본 **False**, 명시적 옵트인)
* 정보성 수신 동의 (:data:`marketing_consent_information_at` 유효)
* ``EmailSender`` 내부의 opt-out / 카테고리 동의 재검사

앞의 두 개를 PDF 렌더 **전에** 검사하는 이유는 비용이다. 렌더는 비싸고,
sender 가 어차피 막을 사용자를 위해 PDF 를 만들 이유가 없다.

정보성 동의 검사는 ``PIVOX_CS1_CONSENT_ENABLED`` 플래그와 무관하게 항상
적용한다. 플래그가 꺼져 있으면 sender 는 카테고리 동의를 보지 않는데, 이
메일은 그 상태에서도 동의 없이 나가서는 안 된다. 이 게이트는 sender 보다
느슨해지는 일이 없고, 엄격해지기만 한다.

문구 규칙
=========
제목·본문에 점수·등급·판정이 없다. 지시형 어휘도 없다 — 발송 직전
``services.legal.assert_legal_safe`` 로 제목과 본문을 모두 검사하므로,
템플릿이 나중에 그쪽으로 흘러가면 발송 시점에 터진다.

비용
====
월 1회, 수신 동의 + 옵트인한 사용자 수만큼. 클로즈드 베타 규모에서는
SendGrid 무료 100/일 안에 충분히 들어간다.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Iterable

logger = logging.getLogger(__name__)


# ── 렌더러 바인딩 ────────────────────────────────────────────────────────────
#
# 모듈 최상단에서 이름으로 묶어 둔다 (함수 안에서 import 하지 않는다).
# 두 가지를 동시에 얻기 위해서다:
#   * 테스트가 ``monkeypatch.setattr(reports_delivery, "build_mirror_report", …)``
#     하나로 두 경로(라우트/크론)를 모두 가짜 렌더러로 돌릴 수 있다.
#   * 렌더러 모듈이 아직 없어도 이 모듈 import 는 성공한다 — 부팅이
#     다른 에이전트의 작업 순서에 묶이지 않는다.
try:
    from services.reports.mirror_pdf import build_mirror_report, render_mirror_pdf
except Exception as _exc:  # 모듈 부재 / import 시점 오류 모두 포함
    build_mirror_report = None  # type: ignore[assignment]
    render_mirror_pdf = None    # type: ignore[assignment]
    logger.info(
        "services.reports.mirror_pdf unavailable at import (%s) — "
        "mirror report delivery will fail loudly at call time", _exc,
    )


class RendererUnavailable(RuntimeError):
    """렌더러 모듈을 import 할 수 없을 때. 조용히 넘어가지 않는다."""


# ── 상수 ────────────────────────────────────────────────────────────────────

#: ``models.user.NOTIFICATION_EVENT_IDS`` 의 이 리포트용 id.
REPORT_EVENT_ID = "monthly_mirror"

#: 렌더러에 넘기는 관찰 창. 9차원 관찰 페르소나와 같은 30일.
REPORT_PERIOD_DAYS = 30

#: 발신 주소 env 오버라이드 (다른 artefact 메일러와 같은 관례).
FROM_ENV_VAR = "MONTHLY_MIRROR_FROM_EMAIL"
FROM_DEFAULT = "reports@pivoxquant.com"


# ── 파일명 ──────────────────────────────────────────────────────────────────

def mirror_report_filename(ref: datetime | None = None) -> str:
    """``pivoxquant_mirror_<yyyy-mm>.pdf``.

    ``ref`` 는 파일명에 박힐 달을 고르는 기준 시각이다. 온디맨드
    다운로드는 "지금"을 넘기고(= 이번 달), 크론은 발송일 하루 전을
    넘긴다 — 매월 1일 아침에 도는 잡이라 하루를 빼면 리포트가 실제로
    덮는 지난달이 된다. 두 경로가 같은 함수를 쓰므로 규칙은 하나다.
    """
    ref = ref or datetime.now(timezone.utc).replace(tzinfo=None)
    return f"pivoxquant_mirror_{ref:%Y-%m}.pdf"


# ── 렌더 ────────────────────────────────────────────────────────────────────

def build_mirror_pdf(
    user_id: int,
    *,
    locale: str = "ko",
    period_days: int = REPORT_PERIOD_DAYS,
) -> tuple[dict, bytes] | None:
    """``(data, pdf_bytes)`` 를 돌려준다. 되비출 기록이 없으면 ``None``.

    ``None`` 과 예외를 구분하는 것이 이 함수의 계약이다 — "보낼 내용이
    없다"는 정상 상태(404/스킵)고, 렌더 실패는 오류(500/errors)다.
    """
    if build_mirror_report is None or render_mirror_pdf is None:
        raise RendererUnavailable(
            "services.reports.mirror_pdf is not importable — "
            "cannot build the monthly mirror report"
        )

    data = build_mirror_report(user_id, period_days=period_days)
    if not isinstance(data, dict) or not data.get("has_content"):
        return None

    pdf_bytes = render_mirror_pdf(data, locale=locale)
    if not pdf_bytes:
        raise RendererUnavailable(
            f"render_mirror_pdf returned empty bytes for user {user_id}"
        )
    return data, pdf_bytes


# ── 수신 게이트 ─────────────────────────────────────────────────────────────

def _has_information_consent(user: Any) -> bool:
    """정보성 수신 동의가 유효한가.

    술어를 여기서 다시 쓰지 않고 sender 의 것을 그대로 부른다 — 같은 규칙의
    두 번째 구현은 반드시 어긋난다 (CLAUDE.md 함정 §10 과 같은 교훈).
    """
    from services.email.sender import EmailCategory, _has_category_consent

    return bool(_has_category_consent(user, EmailCategory.INFORMATION))


def _email_channel_on(user: Any) -> bool:
    """알림 설정에서 이 리포트의 email 채널이 켜져 있는가."""
    checker = getattr(user, "notification_channel_enabled", None)
    if not callable(checker):
        return False
    return bool(checker(REPORT_EVENT_ID, "email"))


def find_report_recipients() -> list[Any]:
    """발송 후보 사용자. 채널·동의 검사는 호출부가 사용자 단위로 한다.

    쿼리 단계에서는 "애초에 메일이 나가면 안 되는" 행만 걷어낸다:
    시뮬 사용자(CLAUDE.md 함정 §7), 탈퇴 유예 중인 사용자(PIPA §21),
    전역 수신 거부, 주소 없음.
    """
    from models import User

    return (
        User.query
        .filter(
            User.is_simulated.is_(False),
            User.deletion_requested_at.is_(None),
            User.email.isnot(None),
            User.email != "",
            User.email_opt_out.is_(False),
        )
        .order_by(User.id)
        .all()
    )


# ── 문구 ────────────────────────────────────────────────────────────────────

def _display_name(user: Any) -> str:
    name = (getattr(user, "name", "") or "").strip()
    if name:
        return name
    email = getattr(user, "email", "") or ""
    return email.split("@")[0] if email else "PivoxQuant"


def compose_email(user: Any, *, period_label: str) -> tuple[str, str]:
    """``(subject, html_body)``.

    점수도 등급도 판정도 없다. 메일이 하는 말은 "지난 30일의 기록을 한 장에
    정리해 첨부했다" 한 줄이고, 해석은 읽는 사람 몫이라고 명시한다.
    """
    name = escape(_display_name(user))
    locale = (getattr(user, "locale", "") or "ko").lower()

    if locale.startswith("en"):
        subject = f"Your PivoxQuant monthly mirror · {period_label}"
        html_body = (
            "<div style=\"font-family:-apple-system,BlinkMacSystemFont,"
            "'Segoe UI',sans-serif;line-height:1.7;color:#1a1a1a\">"
            f"<p>{name},</p>"
            "<p>The attached PDF looks back over the last 30 days of your "
            "own record — what you wrote down before each trade, and what "
            "the record looks like now that the month is over.</p>"
            "<p>It contains nothing but your own entries, and it passes no "
            "judgement on them; what they mean is yours to read.</p>"
            "<p style=\"color:#6b6b6b;font-size:13px\">"
            "You are receiving this because you turned on the monthly "
            "mirror report in Settings &rsaquo; Notifications. You can turn "
            "it off there at any time.</p>"
            "</div>"
        )
        return subject, html_body

    subject = f"PivoxQuant 월간 거울 · {period_label}"
    html_body = (
        "<div style=\"font-family:-apple-system,BlinkMacSystemFont,"
        "'Segoe UI',sans-serif;line-height:1.7;color:#1a1a1a\">"
        f"<p>{name} 님,</p>"
        "<p>지난 30일의 기록을 한 장으로 정리해 첨부했습니다. 거래 전에 "
        "직접 적어 둔 이유와, 한 달이 지난 지금의 기록을 나란히 놓은 "
        "문서입니다.</p>"
        "<p>회원님이 남긴 기록 외에는 아무것도 들어 있지 않습니다. 이 문서는 "
        "아무것도 판정하지 않습니다 — 무엇을 읽어 낼지는 회원님 몫입니다.</p>"
        "<p style=\"color:#6b6b6b;font-size:13px\">"
        "설정 &rsaquo; 알림에서 월간 거울 리포트를 켜 두셔서 발송된 "
        "메일입니다. 같은 자리에서 언제든 끌 수 있습니다.</p>"
        "</div>"
    )
    return subject, html_body


# ── 사용자 1명 발송 ─────────────────────────────────────────────────────────

# :func:`send_report_to_user` 의 결과 코드. 요약 dict 의 키와 1:1 이다.
RESULT_SENT = "sent"
RESULT_SKIPPED_PREF = "skipped_pref"
RESULT_SKIPPED_CONSENT = "skipped_consent"
RESULT_SKIPPED_EMPTY = "skipped_empty"
RESULT_SKIPPED_SEND = "skipped_send"


def send_report_to_user(user: Any, *, now: datetime | None = None) -> str:
    """한 사용자에게 월간 리포트를 보낸다. 결과 코드를 돌려준다.

    예외는 삼키지 않는다 — 호출부(:func:`dispatch_monthly_reports`)가
    사용자 단위로 잡아 ``errors`` 로 센다. 한 사람의 실패가 나머지
    발송을 멈추게 해서는 안 되지만, 실패를 성공처럼 보이게 해서도 안 된다.
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory
    from services.legal import assert_legal_safe

    now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # 싼 검사부터. PDF 렌더는 이 게이트를 모두 통과한 뒤에만 돈다.
    if not _email_channel_on(user):
        return RESULT_SKIPPED_PREF
    if not _has_information_consent(user):
        return RESULT_SKIPPED_CONSENT

    locale = (getattr(user, "locale", "") or "ko").lower()
    built = build_mirror_pdf(user.id, locale=locale)
    if built is None:
        return RESULT_SKIPPED_EMPTY
    _data, pdf_bytes = built

    # 1일 아침에 도는 잡이므로 하루를 빼면 리포트가 덮는 지난달이 된다.
    label_ref = now - timedelta(days=1)
    filename = mirror_report_filename(label_ref)
    period_label = f"{label_ref:%Y-%m}"

    subject, html_body = compose_email(user, period_label=period_label)
    assert_legal_safe(subject, "reports_delivery/subject")
    assert_legal_safe(html_body, "reports_delivery/html")

    ok = EmailSender().send(
        user,
        subject=subject,
        html_body=html_body,
        from_env_var=FROM_ENV_VAR,
        from_default=FROM_DEFAULT,
        pdf_bytes=pdf_bytes,
        pdf_filename=filename,
        email_category=EmailCategory.INFORMATION,
        event_id=REPORT_EVENT_ID,
    )
    return RESULT_SENT if ok else RESULT_SKIPPED_SEND


# ── 전체 발송 ───────────────────────────────────────────────────────────────

def dispatch_monthly_reports(
    now: datetime | None = None,
    users: Iterable[Any] | None = None,
) -> dict[str, int]:
    """모든 대상에게 월간 리포트를 보낸다. 요약 dict 를 돌려준다.

    사용자 단위 try/except 가 이 함수의 핵심이다 — 한 사람의 렌더 실패나
    provider 오류가 나머지 사용자의 발송을, 나아가 크론 스레드 전체를
    죽이면 안 된다.
    """
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if users is None:
        users = find_report_recipients()

    summary = {
        "candidates":           0,
        RESULT_SENT:            0,
        RESULT_SKIPPED_PREF:    0,
        RESULT_SKIPPED_CONSENT: 0,
        RESULT_SKIPPED_EMPTY:   0,
        RESULT_SKIPPED_SEND:    0,
        "errors":               0,
    }

    for user in users:
        summary["candidates"] += 1
        try:
            result = send_report_to_user(user, now=now)
        except Exception as exc:
            logger.exception(
                "monthly mirror report failed for user %s: %s",
                getattr(user, "id", "?"), exc,
            )
            summary["errors"] += 1
            continue
        summary[result] = summary.get(result, 0) + 1

    logger.info("monthly mirror report dispatch summary: %s", summary)
    return summary


def run_once(now: datetime | None = None) -> dict[str, int]:
    """크론 1회분. 앱 컨텍스트 안에서 불린다."""
    return dispatch_monthly_reports(now=now)


# ── 크론 엔트리포인트 ───────────────────────────────────────────────────────

def main() -> int:
    """``services/scheduler/cron_jobs.py`` 의 ``_wrap_python_main`` 진입점.

    ``scripts/nightly/*_dispatcher.py`` 들과 같은 형태다: 요청 밖에서
    ``models.*.query`` 가 돌도록 임시 앱 컨텍스트를 세우고, 끝나면
    커넥션 풀을 즉시 반납한다. 0 = 성공, 1 = 처리되지 않은 오류.
    """
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        from app import create_app
        from extensions import db
    except Exception as exc:
        logger.error("create_app import failed: %s", exc)
        return 1

    # 이미 떠 있는 web 프로세스가 캐시를 데웠다 — 임시 앱이 FMP 를 다시
    # 때리지 않게 하고, 스케줄러도 두 번 만들지 않는다.
    os.environ["POPULATE_CACHE_ON_BOOT"] = "0"
    os.environ.setdefault("RUN_SCHEDULER", "0")

    try:
        app = create_app()
    except Exception as exc:
        logger.error("create_app() failed: %s", exc)
        return 1

    summary: dict[str, int] = {}
    try:
        with app.app_context():
            try:
                summary = run_once()
            except Exception as exc:
                logger.exception("monthly mirror dispatcher crashed: %s", exc)
                return 1
    finally:
        try:
            db.engine.dispose()
        except Exception:
            logger.debug("engine dispose failed (non-fatal)", exc_info=True)

    print(f"monthly_mirror summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
