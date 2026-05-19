"""
PivoxQuant — Stripe checkout abandonment 1h follow-up (Wave G C-M1)
====================================================================

When ``checkout.session.expired`` fires, we enqueue a row in
``checkout_expirations`` with ``scheduled_send_at = expired_at + 1h``.
A cron-driven dispatcher (``scripts/nightly/checkout_followup_dispatcher.py``)
runs every 15 minutes, queries this module for the pending rows, and asks
us to render + send the transactional email per row.

This module owns:

* ``send_checkout_followup(user, row)`` — one-shot send via SendGrid
  cascade-to-Brevo. Returns ``True`` on provider accept. Never raises
  (caller is a cron, errors go to logger/Sentry).
* ``followup_enabled()`` — feature-flag read.
* ``_render_followup_html(...)`` — inline HTML body, intentionally
  *transactional* tone — no marketing copy, no discount language.

§50 transactional classification rationale
------------------------------------------
정통망법 §50 ①은 *영리목적 광고성 정보* 에 사전동의 의무. 이 메일은:

  (i)  사용자가 직접 결제 페이지에 진입한 행위에 대한 응답,
  (ii) 결제 절차의 *완수* 를 돕는 거래 보조 통지 (할인/혜택/추천 없음),
  (iii) 본문에 "결제 도와드릴까요?" + Customer Portal 링크만 — 광고 카피
        ("할인", "혜택", "특별 가격" 등) 포함 금지.

따라서 §50 ③ "광고성 아닌 정보의 통지" 에 해당하여 사전동의 면제.
보수적으로 List-Unsubscribe 헤더는 brevo / sendgrid provider 가
자동 부여 (RFC 8058 + Gmail 발신 정책 준수).

Cost
----
- SendGrid 100/day free → 결제 이탈 추정 < 5/일 (BETA + Stripe Live 전).
- Brevo 300/day free fallback.
- Stripe webhook 무료 (별도 비용 없음).
- 추가 비용 0원.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Feature flag — default OFF. dispatcher checks this *per tick*; the
# webhook handler always enqueues so that a flag flip immediately drains
# the backlog into emails. Reading per-tick keeps prod toggle non-redeploy.
_FLAG_ENV = "PIVOX_CHECKOUT_FOLLOWUP_ENABLED"


def followup_enabled() -> bool:
    """Return True iff the dispatcher should actually send emails.

    OFF default mirrors the C-S1 ``PIVOX_CS1_CONSENT_ENABLED`` pattern:
    schema + webhook + dispatcher all deploy, but the user-visible
    side-effect is gated behind a single env flip.
    """
    val = os.environ.get(_FLAG_ENV, "false").strip().lower()
    return val in ("true", "1", "yes", "on")


def _portal_url() -> str:
    """Customer-portal landing URL. Falls back to ``/settings`` so the
    user always has a place to land even if the env is not set.
    """
    explicit = os.environ.get("STRIPE_CUSTOMER_PORTAL_URL")
    if explicit:
        return explicit
    frontend = os.environ.get("FRONTEND_URL", "https://pivoxquant.com").rstrip("/")
    return f"{frontend}/settings"


def _render_followup_html(*, user: Any, portal_url: str) -> str:
    """Transactional HTML body — 광고 카피 0건. 거래 보조 어조만.

    Inline string (no Jinja) — same rationale as
    ``services/billing_notifications.py`` (single template, snapshot-
    testable, provider layer injects unsubscribe footer).

    Korean primary + English subtext — matches bilingual convention.
    """
    name = (
        getattr(user, "name", None)
        or getattr(user, "email", "고객")
        or "고객"
    )
    return f"""
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>결제 도와드릴까요</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #faf8f3; padding: 24px; color: #1a1a1a;">
  <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border: 1px solid #e8e4dc; border-radius: 8px; padding: 32px;">
    <h1 style="font-size: 22px; margin: 0 0 16px; color: #b87f3e;">결제 도와드릴까요?</h1>
    <p style="font-size: 15px; line-height: 1.6; margin: 0 0 12px;">
      {name} 님, 결제 진행 중에 문제가 있으셨나요. 카드 정보를
      다시 확인하시거나 결제 페이지를 새로 여실 수 있어요.
    </p>
    <p style="font-size: 14px; line-height: 1.6; margin: 0 0 24px; color: #555;">
      카드 한도, 만료, 또는 결제 차단(국외 결제 차단 등) 때문일 수
      있어요. 도움이 필요하시면 본 메일에 회신 주세요 — 결제 흐름을
      함께 확인해 드립니다.
    </p>
    <p style="margin: 0 0 24px;">
      <a href="{portal_url}" style="display: inline-block; background: #b87f3e; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">결제 페이지 다시 열기</a>
    </p>
    <p style="font-size: 12px; color: #999; line-height: 1.5; margin: 24px 0 0;">
      본 메일은 회원님이 시작하신 결제 절차의 후속 안내(거래정보성)로,
      정통망법 §50 마케팅 수신 동의와 무관하게 발송됩니다.
      문의: support@pivoxquant.com
    </p>
  </div>
</body>
</html>
""".strip()


def _render_followup_text(*, user: Any, portal_url: str) -> str:
    """Plain-text fallback for clients that don't render HTML."""
    name = (
        getattr(user, "name", None)
        or getattr(user, "email", "고객")
        or "고객"
    )
    return (
        f"{name} 님, 결제 진행 중에 문제가 있으셨나요.\n\n"
        "카드 정보를 다시 확인하시거나 아래 링크에서 결제 페이지를\n"
        "다시 여실 수 있어요. 도움이 필요하시면 본 메일에 회신 주세요.\n\n"
        f"{portal_url}\n\n"
        "— PivoxQuant Billing\n"
        "(거래정보성 안내 — 정통망법 §50 마케팅 수신 동의 무관)\n"
        "문의: support@pivoxquant.com\n"
    ).strip()


def send_checkout_followup(*, user: Any) -> bool:
    """Send the 1h follow-up email to *user*.

    Returns ``True`` on provider accept, ``False`` on any path that
    skipped the send (no email / both providers absent / both failed).
    Never raises — caller (cron dispatcher) treats False as a permanent
    skip and stamps ``skipped_reason``.

    Provider cascade order: SendGrid → Brevo. Mirrors the cascade in
    ``services/billing_notifications.py``. Both use
    ``honour_consent=False`` because the call is transactional and the
    user-row consent state is irrelevant.
    """
    if user is None or not getattr(user, "email", None):
        logger.debug("checkout_followup skipped: no user/email")
        return False

    portal_url = _portal_url()
    subject = "[PivoxQuant] 결제 도와드릴까요? — 카드 확인 부탁드립니다"
    html_body = _render_followup_html(user=user, portal_url=portal_url)
    text_body = _render_followup_text(user=user, portal_url=portal_url)
    from_email = os.environ.get(
        "BILLING_FROM_EMAIL", "billing@pivoxquant.com",
    )

    sg_key = os.environ.get("SENDGRID_API_KEY")
    brevo_key = (
        os.environ.get("BREVO_API_KEY")
        or os.environ.get("SENDINBLUE_API_KEY")
    )

    # ── SendGrid primary ───────────────────────────────────────────────
    if sg_key:
        try:
            from services.email import sendgrid_provider as _sg
            rcpt = _sg.SystemMailRecipient(
                email=user.email,
                user_id=getattr(user, "id", None),
            )
            ok = _sg.send(
                rcpt,
                subject=subject,
                html_body=html_body,
                plain_body=text_body,
                from_email=from_email,
                from_name="PivoxQuant Billing",
                reply_to="support@pivoxquant.com",
                categories=("billing", "checkout_followup"),
                honour_consent=False,  # transactional — §50 exempt
            )
            if ok:
                logger.info(
                    "checkout_followup sent via SendGrid (user=%s)",
                    getattr(user, "id", "?"),
                )
                return True
        except Exception as exc:
            logger.exception(
                "checkout_followup SendGrid path failed (user=%s): %s",
                getattr(user, "id", "?"), exc,
            )
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except Exception:
                pass

    # ── Brevo fallback ─────────────────────────────────────────────────
    if brevo_key:
        try:
            from services.email import brevo_provider as _brevo
            rcpt = _brevo.SystemMailRecipient(
                email=user.email,
                user_id=getattr(user, "id", None),
            )
            ok = _brevo.send(
                rcpt,
                subject=subject,
                html_body=html_body,
                plain_body=text_body,
                from_email=from_email,
                from_name="PivoxQuant Billing",
                reply_to="support@pivoxquant.com",
                tags=("billing", "checkout_followup"),
                honour_consent=False,  # transactional — §50 exempt
            )
            if ok:
                logger.info(
                    "checkout_followup sent via Brevo (user=%s)",
                    getattr(user, "id", "?"),
                )
                return True
        except Exception as exc:
            logger.exception(
                "checkout_followup Brevo path failed (user=%s): %s",
                getattr(user, "id", "?"), exc,
            )
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except Exception:
                pass

    logger.info(
        "checkout_followup: no provider succeeded (user=%s) — skipped",
        getattr(user, "id", "?"),
    )
    return False


__all__ = [
    "followup_enabled",
    "send_checkout_followup",
]
