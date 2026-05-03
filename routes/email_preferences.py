"""Public unsubscribe endpoint (정통망법 §50 compliance).

Mounted at ``GET /api/email/unsubscribe?token=…&type=all|earnings``.

Two flows produce hits on this route:

1. The user clicks the inline footer link (`<a href="…">`) inside an
   email — same-tab navigation. They land on a small Korean+English
   confirmation page.
2. Gmail/Outlook surface the inbox-level "Unsubscribe" button driven
   by the ``List-Unsubscribe`` header (RFC 8058). When the user clicks
   it, the mail client either GETs this URL or POSTs to it with
   ``List-Unsubscribe=One-Click`` — both shapes are idempotent here.

Auth model
----------
No session cookie. The HMAC-signed token (``services.email_token``)
authenticates the user-id; the user can be logged out, on a different
device, or never have come back to the site at all and the link still
works. CSRF is not enforced because the POST shape is a single
well-known body Gmail sends — there is no other state-changing action
on this endpoint.

Failure modes
-------------
- Missing/invalid/expired token → 400 with a Korean+English error page.
- Unknown ``type`` → coerced to "all" (the safe default — fewer emails
  rather than more).
- DB commit failure → 500 with a generic page; we intentionally do not
  echo the underlying error.
"""
from __future__ import annotations

import logging

from flask import Blueprint, request

from extensions import db
from models import User
from security import limiter
from services.email_token import verify_unsubscribe_token

logger = logging.getLogger(__name__)

email_pref_bp = Blueprint("email_preferences", __name__, url_prefix="/api/email")


# Brand-aligned inline styles (Vantablack + Bronze + Playfair). Email
# clients render the response after redirect, but this is also rendered
# directly when the user clicks the footer link inside their browser.
_PAGE_TMPL = """\
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background: #050505;
      color: #f5f0e8;
      font-family: 'Geist', 'Pretendard', -apple-system, BlinkMacSystemFont,
                   'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .wrap {{
      max-width: 480px;
      padding: 48px 32px;
      text-align: center;
    }}
    .kicker {{
      font-size: 10px;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: #B8956A;
      margin-bottom: 24px;
    }}
    h1 {{
      font-family: 'Playfair Display', 'Source Serif 4', Georgia, serif;
      font-size: 28px;
      font-weight: 500;
      letter-spacing: -0.01em;
      color: #f5f0e8;
      margin: 0 0 12px 0;
      line-height: 1.2;
    }}
    p {{
      font-size: 14px;
      line-height: 1.6;
      color: rgba(245, 240, 232, 0.7);
      margin: 12px 0;
    }}
    .en {{
      font-size: 12px;
      color: rgba(245, 240, 232, 0.5);
      margin-top: 16px;
    }}
    .brand {{
      margin-top: 40px;
      font-size: 9px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: rgba(245, 240, 232, 0.35);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="kicker">PivoxQuant · Email Preferences</div>
    <h1>{heading}</h1>
    <p>{body_kr}</p>
    <p class="en">{body_en}</p>
    <div class="brand">PivoxQuant Research Desk · pivoxquant.com</div>
  </div>
</body>
</html>"""


def _render(title: str, heading: str, body_kr: str, body_en: str,
            status: int = 200) -> tuple[str, int, dict[str, str]]:
    html = _PAGE_TMPL.format(
        title=title, heading=heading, body_kr=body_kr, body_en=body_en,
    )
    return html, status, {"Content-Type": "text/html; charset=utf-8"}


@email_pref_bp.route("/unsubscribe", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def unsubscribe():
    """Apply the opt-out flag corresponding to ``type`` for the token's user.

    ``type`` query param:
        ``all`` (default)   → set ``email_opt_out = True``.
        ``earnings``        → set ``email_opt_out_earnings = True``.

    Always idempotent — re-clicking simply re-sets the same flag.
    """
    token = (request.values.get("token") or "").strip()
    if not token:
        return _render(
            title="유효하지 않은 링크입니다",
            heading="유효하지 않은 링크입니다",
            body_kr="이 수신거부 링크는 비어 있거나 손상되었습니다.",
            body_en="This unsubscribe link is missing or malformed.",
            status=400,
        )

    user_id = verify_unsubscribe_token(token)
    if user_id is None:
        return _render(
            title="유효하지 않은 링크입니다",
            heading="유효하지 않은 링크입니다",
            body_kr=(
                "이 수신거부 링크가 만료되었거나 변조되었습니다. "
                "설정 페이지에서 직접 변경해주세요."
            ),
            body_en=(
                "This unsubscribe link is invalid or expired. "
                "Please update your preferences from the Settings page."
            ),
            status=400,
        )

    user = db.session.get(User, user_id)
    if user is None:
        return _render(
            title="유효하지 않은 링크입니다",
            heading="유효하지 않은 링크입니다",
            body_kr="해당 계정을 찾을 수 없습니다.",
            body_en="The associated account no longer exists.",
            status=400,
        )

    # Default to global opt-out — safer than narrower scope when the
    # client omits or mistypes ``type``.
    optout_type = (request.values.get("type") or "all").strip().lower()
    if optout_type not in {"all", "earnings"}:
        optout_type = "all"

    if optout_type == "earnings":
        user.email_opt_out_earnings = True
    else:
        user.email_opt_out = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "email_preferences.unsubscribe commit failed (user_id=%s, type=%s)",
            user_id, optout_type,
        )
        return _render(
            title="처리에 실패했습니다",
            heading="처리에 실패했습니다",
            body_kr=(
                "일시적인 오류로 수신거부를 처리하지 못했습니다. "
                "잠시 후 다시 시도해주세요."
            ),
            body_en=(
                "We could not process your unsubscribe right now. "
                "Please try again in a moment."
            ),
            status=500,
        )

    if optout_type == "earnings":
        return _render(
            title="수신거부 완료 — 실적 알림",
            heading="수신거부 완료",
            body_kr=(
                "실적 발표 사전 브리핑 이메일에서 제외되었습니다. "
                "다른 이메일은 계속 받게 됩니다."
            ),
            body_en=(
                "You will no longer receive earnings pre-brief emails. "
                "Other PivoxQuant emails are unaffected."
            ),
        )

    return _render(
        title="수신거부 완료",
        heading="수신거부 완료",
        body_kr=(
            "PivoxQuant의 모든 마케팅 및 알림 이메일에서 제외되었습니다. "
            "결제 관련 안내 등 거래상 필수 메일만 발송됩니다."
        ),
        body_en=(
            "You have been unsubscribed from all PivoxQuant marketing "
            "and digest emails. Transactional notices may still be sent."
        ),
    )
