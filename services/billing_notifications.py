"""
PivoxQuant — Billing notification side-effects
==============================================

Stripe ``invoice.payment_failed`` 이벤트가 들어오면 두 가지 외부 알림을
보낸다 — (a) CEO Slack DM (재정 가시성) + (b) 유저 transactional 이메일
(거래정보성, 정통망법 §50 마케팅성 동의 면제).

Why a dedicated module?
-----------------------
``routes/billing.py`` 의 ``_handle_invoice_payment_failed`` 는 webhook
handler 내부에서 호출되므로 **절대 raise 하면 안 된다** — Stripe 는
non-2xx 응답을 3일간 재시도하므로 webhook 가 500 을 던지면 에러 로그
폭주 + idempotency 레코드 race 가 발생한다. 모든 외부 호출은 본 모듈
안에서 try/except 로 흡수하고 실패 시 ``False`` + Sentry capture 로만
표면화한다 (handler 는 ``True``/``False`` 를 무시하고 항상 ACK 한다).

정통망법 §50 transactional 분류 근거
-------------------------------------
정보통신망법 §50 ①은 **영리 목적의 광고성 정보** 에 사전동의를 요구.
결제 실패 안내는 (i) 사용자가 이미 체결한 거래(구독)의 이행 통지 +
(ii) 사용자 행동(카드 갱신)을 요구하는 거래 통지에 해당하므로 동일 조
③ **거래정보성** 으로 분류 — 사전 동의 없이도 발송 가능. 단,
List-Unsubscribe 헤더는 RFC 8058 + Gmail 정책에 따라 모든 발송에
관습적으로 포함 (별도 의무 아님).

근거: 정통망법 §50 ③ "재화 등의 거래관계를 통하여 수신자로부터 직접
연락처를 수집한 자가 거래종료 후 6개월 이내에 송신하는 ... 자신이
취급하는 재화 등에 대한 영리목적의 광고성 정보" 는 면제. 다만 본
케이스는 **광고성 정보 자체가 아님** — 거래 이행 알림 (인보이스 실패)
이므로 §50 ①의 적용 대상 밖.

Cost
----
- Slack incoming webhook: free tier
- SendGrid 100/day free + Brevo 300/day free (cascade in EmailSender)
- 추가 비용 0원
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Stripe dashboard root — switch by livemode flag on the invoice object.
_STRIPE_DASHBOARD_LIVE = "https://dashboard.stripe.com"
_STRIPE_DASHBOARD_TEST = "https://dashboard.stripe.com/test"


def _stripe_dashboard_invoice_url(invoice: dict[str, Any]) -> str:
    """Build a Stripe dashboard deep-link to the invoice.

    Stripe sends ``livemode: bool`` on every Event payload — true for the
    Live key, false for the Test key. We pick the corresponding dashboard
    prefix so CEO clicks land in the right environment immediately.
    """
    livemode = bool(invoice.get("livemode", False))
    base = _STRIPE_DASHBOARD_LIVE if livemode else _STRIPE_DASHBOARD_TEST
    invoice_id = invoice.get("id") or ""
    return f"{base}/invoices/{invoice_id}" if invoice_id else base


def _format_amount(amount_minor: int, currency: str | None) -> str:
    """Render Stripe amount (minor units) as a human KRW/USD string.

    Stripe sends ``amount_due`` / ``amount_paid`` in the smallest currency
    unit — cents for USD, 원 for KRW (no decimal). We avoid pulling
    Babel/locale here because Slack messages tolerate the simple form
    and we don't want a new dep.
    """
    cur = (currency or "").lower()
    try:
        amt = int(amount_minor or 0)
    except (TypeError, ValueError):
        amt = 0
    if cur == "krw":
        return f"₩{amt:,}"
    if cur == "usd":
        return f"${amt / 100:,.2f}"
    return f"{amt} {cur.upper() or '?'}"


def notify_payment_failed_slack(
    *,
    user: Any | None,
    invoice: dict[str, Any],
) -> bool:
    """Post a CEO Slack alert for a failed Stripe invoice.

    Returns ``True`` on successful POST. Never raises — Sentry captures
    any exception so the webhook ACK is never blocked.

    Skips silently (returns ``False``) when ``SLACK_WEBHOOK_URL`` is unset
    — that's the dev / CI case and we don't want to log loud errors.
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.debug("payment_failed Slack skipped: SLACK_WEBHOOK_URL unset")
        return False

    try:
        import requests  # local import — keeps cold-start fast
    except Exception:
        logger.warning("payment_failed Slack skipped: requests not installed")
        return False

    customer_id = invoice.get("customer") or "?"
    invoice_id = invoice.get("id") or "?"
    attempt = invoice.get("attempt_count", "?")
    amount_str = _format_amount(
        invoice.get("amount_due") or invoice.get("amount_paid", 0),
        invoice.get("currency"),
    )
    reason = (
        invoice.get("last_payment_error", {}).get("message")
        if isinstance(invoice.get("last_payment_error"), dict)
        else None
    ) or invoice.get("billing_reason") or "unknown"
    dashboard_url = _stripe_dashboard_invoice_url(invoice)

    user_id = getattr(user, "id", "unknown") if user else "unknown"
    user_email = getattr(user, "email", "unknown") if user else "unknown"

    text = (
        f":warning: *Stripe 결제 실패*\n"
        f"• user: `{user_id}` ({user_email})\n"
        f"• customer: `{customer_id}`\n"
        f"• invoice: `{invoice_id}` (시도 #{attempt})\n"
        f"• 금액: {amount_str}\n"
        f"• 사유: {reason}\n"
        f"• <{dashboard_url}|Stripe 대시보드 열기>"
    )

    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=10)
        resp.raise_for_status()
        logger.info(
            "payment_failed Slack notification sent (invoice=%s user=%s)",
            invoice_id, user_id,
        )
        return True
    except Exception as exc:
        # Capture to Sentry but DO NOT re-raise — webhook handler caller
        # treats False as "alert side-effect failed, ACK anyway".
        logger.exception(
            "payment_failed Slack post failed: invoice=%s err=%s",
            invoice_id, exc,
        )
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        return False


def _render_payment_failed_html(
    *,
    user: Any,
    invoice: dict[str, Any],
    portal_url: str,
) -> str:
    """Render the transactional email body.

    Inline HTML kept here (not Jinja) because:
      - Single use-case → templating overhead unjustified
      - EmailSender / brevo_provider already inject the unsubscribe
        footer + List-Unsubscribe header
      - Inline string is easier to lock with a snapshot test

    Korean primary copy, English subtext — matches the bilingual
    convention in services/error_responses.py and existing artifact
    emails.
    """
    name = (getattr(user, "name", None) or getattr(user, "email", "고객")
            or "고객")
    amount_str = _format_amount(
        invoice.get("amount_due") or invoice.get("amount_paid", 0),
        invoice.get("currency"),
    )
    attempt = invoice.get("attempt_count", 1)

    return f"""
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>결제 실패 안내</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #faf8f3; padding: 24px; color: #1a1a1a;">
  <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border: 1px solid #e8e4dc; border-radius: 8px; padding: 32px;">
    <h1 style="font-size: 22px; margin: 0 0 16px; color: #b87f3e;">결제가 실패했어요</h1>
    <p style="font-size: 15px; line-height: 1.6; margin: 0 0 12px;">
      {name} 님, PivoxQuant 구독 결제(₩{amount_str if not amount_str.startswith('₩') else amount_str[1:]})가 처리되지 않았습니다.
      카드 정보를 확인해 주세요. (시도 #{attempt})
    </p>
    <p style="font-size: 14px; line-height: 1.6; margin: 0 0 24px; color: #555;">
      Stripe 가 자동으로 재시도하지만, 카드가 만료되었거나 한도가 초과된
      경우 아래 버튼에서 결제 수단을 갱신해 주세요.
    </p>
    <p style="margin: 0 0 24px;">
      <a href="{portal_url}" style="display: inline-block; background: #b87f3e; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">결제 정보 업데이트</a>
    </p>
    <p style="font-size: 12px; color: #999; line-height: 1.5; margin: 24px 0 0;">
      본 메일은 회원님과의 결제 거래 관련 이행 안내(거래정보성)로,
      정통망법 §50 마케팅 수신 동의와 무관하게 발송됩니다.
      문의: support@pivoxquant.com
    </p>
  </div>
</body>
</html>
""".strip()


def notify_payment_failed_email(
    *,
    user: Any | None,
    invoice: dict[str, Any],
) -> bool:
    """Send transactional payment-failed email to the user.

    Returns ``True`` when the provider accepted the dispatch. Never
    raises — Sentry captures any provider error.

    정통망법 §50 transactional carve-out: bypasses ``EmailSender`` (which
    enforces ``marketing_consent_at`` default-deny) and calls the lower-
    level ``brevo_provider.send`` / ``sendgrid_provider.send`` directly
    with ``honour_consent=False``. Cascade order: SendGrid → Brevo.
    """
    if user is None or not getattr(user, "email", None):
        logger.debug("payment_failed email skipped: no user/email")
        return False

    portal_url = os.environ.get(
        "STRIPE_CUSTOMER_PORTAL_URL",
        f"{os.environ.get('FRONTEND_URL', 'https://pivoxquant.com').rstrip('/')}/settings",
    )
    subject = "[PivoxQuant] 결제가 실패했어요 — 카드 확인 부탁드립니다"
    html_body = _render_payment_failed_html(
        user=user, invoice=invoice, portal_url=portal_url,
    )

    from_email = os.environ.get(
        "BILLING_FROM_EMAIL", "billing@pivoxquant.com",
    )

    # ── Cascade: SendGrid first, then Brevo. Match the cascade order
    # ── used by EmailSender (which defaults to SendGrid primary).
    sg_key = os.environ.get("SENDGRID_API_KEY")
    brevo_key = os.environ.get("BREVO_API_KEY") or os.environ.get(
        "SENDINBLUE_API_KEY"
    )

    # SendGrid path
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
                from_email=from_email,
                from_name="PivoxQuant Billing",
                reply_to="support@pivoxquant.com",
                # SendGrid v3: stats bucket = ``categories`` (Brevo: ``tags``).
                categories=("billing", "payment_failed"),
                honour_consent=False,  # transactional — §50 exempt
            )
            if ok:
                logger.info(
                    "payment_failed email sent via SendGrid (user=%s)",
                    user.id,
                )
                return True
        except Exception as exc:
            logger.exception(
                "payment_failed email SendGrid path failed (user=%s): %s",
                user.id, exc,
            )
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except Exception:
                pass

    # Brevo fallback
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
                from_email=from_email,
                from_name="PivoxQuant Billing",
                reply_to="support@pivoxquant.com",
                tags=("billing", "payment_failed"),
                honour_consent=False,  # transactional — §50 exempt
            )
            if ok:
                logger.info(
                    "payment_failed email sent via Brevo (user=%s)",
                    user.id,
                )
                return True
        except Exception as exc:
            logger.exception(
                "payment_failed email Brevo path failed (user=%s): %s",
                user.id, exc,
            )
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except Exception:
                pass

    logger.info(
        "payment_failed email: no provider succeeded (user=%s) — skipped",
        getattr(user, "id", "?"),
    )
    return False


__all__ = [
    "notify_payment_failed_slack",
    "notify_payment_failed_email",
]
