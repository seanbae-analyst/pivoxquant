"""Billing routes: Stripe subscription checkout, webhooks, portal."""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from functools import wraps

import stripe
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (
    User,
    ProcessedStripeEvent,
    STRIPE_EVENT_STATUS_SUCCESS,
    STRIPE_EVENT_STATUS_ERROR,
)
from flask_login import current_user
from services.error_responses import api_error
from .decorators import _TIER_RANK, api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
# Network resilience: cap default 80s timeout to 10s and limit retries to 2.
# Prevents long-tail latency on Stripe API outages from blocking checkout flow.
stripe.max_network_retries = 2
stripe.api_request_timeout = 10
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_PREMIUM = os.environ.get("STRIPE_PRICE_PREMIUM", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

PLAN_PRICES = {
    "pro": STRIPE_PRICE_PRO,
    "premium": STRIPE_PRICE_PREMIUM,
}
PLAN_TIERS = {
    "pro": "pro",
    "premium": "premium",
}


# ── Business registration gate ──────────────────────────────────────────────
#
# 한국 법: 사업자등록(부가가치세법 §8) + 통신판매업 신고(전자상거래법 §12)가
# 완료되지 않은 상태에서 결제를 활성화하면 위법.
#  - 전자상거래법 §40: 1,000만원 이하 과태료 (신원정보 미표시)
#  - 통신판매법 §43: 3,000만원 이하 과태료 (무신고 영업)
#
# Railway env에 BUSINESS_REGISTRATION_NUMBER + TELESELLER_REGISTRATION_NUMBER
# 두 값이 모두 설정되기 전까지 모든 결제 endpoint를 503으로 차단.
# (frontend도 /api/billing/availability를 호출해 결제 버튼을 disable해야 함.)

def _business_registration_complete() -> bool:
    """사업자등록 + 통신판매업 신고 둘 다 완료됐는지 확인."""
    return bool(
        os.environ.get("BUSINESS_REGISTRATION_NUMBER")
        and os.environ.get("TELESELLER_REGISTRATION_NUMBER")
    )


def _registration_pending_response():
    return jsonify({
        "error": "Subscription not yet available",
        "error_ko": "결제는 사업자등록 및 통신판매업 신고 완료 후 활성화됩니다",
        "code": "BUSINESS_REGISTRATION_PENDING",
    }), 503


def require_business_registration(f):
    """Decorator: 결제 관련 endpoint를 사업자등록 전까지 503으로 차단."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _business_registration_complete():
            return _registration_pending_response()
        return f(*args, **kwargs)
    return wrapper


def _get_or_create_customer(user):
    """Get existing Stripe customer or create a new one.

    Raises stripe.StripeError on API failure — the caller must handle it
    (all call sites already wrap in `except stripe.StripeError`).

    Bug C#3 fix — race-safe customer creation
    -----------------------------------------
    The previous fast-path (``if user.stripe_customer_id: return``) was an
    unlocked check-then-create. Under the multi-worker PG deployment two
    concurrent ``create-checkout`` requests for the *same* user could both
    observe ``stripe_customer_id IS NULL`` and each call
    ``stripe.Customer.create`` — only one row update wins, orphaning the
    other Stripe customer (whose webhooks would then be lost).

    Defense in depth:
      1. Re-read the User row under ``SELECT ... FOR UPDATE`` so a second
         concurrent caller blocks until we commit, then sees the persisted
         id and reuses it (no second Customer.create).
      2. The DB-level ``uq_users_stripe_customer`` partial unique index
         (app._do_migrations) is the backstop: if a race still slips
         through (e.g. SQLite, or lock contention timeout), the commit
         raises IntegrityError, we roll back + delete the orphan + re-read
         the winner's id.

    On SQLite ``with_for_update`` is a no-op (single-threaded test path),
    which is harmless.
    """
    # Lock the user row. ``current_user`` is a proxy that may be attached to
    # the request session; re-query by primary key to obtain a row-locked,
    # session-bound instance and re-check the id while holding the lock.
    locked_user = (
        User.query
        .filter(User.id == user.id)
        .with_for_update()
        .first()
    )
    target = locked_user or user
    if target.stripe_customer_id:
        # Another concurrent request created + persisted it while we waited
        # on the lock (or it already existed). Reuse — never duplicate.
        db.session.commit()  # release the row lock
        return target.stripe_customer_id

    customer = stripe.Customer.create(
        email=target.email,
        name=target.name,
        metadata={"user_id": str(target.id)},
    )
    try:
        target.stripe_customer_id = customer.id
        db.session.commit()
    except IntegrityError as e:
        # The partial unique index rejected the write — a racing request
        # persisted a customer id for this user first. Roll back, delete the
        # orphan we just created, and reuse the winner's id.
        db.session.rollback()
        logger.warning(
            "stripe_customer_id race for user_id=%s — reusing winner: %s",
            target.id, e,
        )
        try:
            stripe.Customer.delete(customer.id)
            logger.info("Deleted duplicate Stripe customer %s after race", customer.id)
        except stripe.StripeError as del_err:
            logger.error(
                "Failed to delete duplicate Stripe customer %s: %s",
                customer.id, del_err,
            )
        winner = db.session.get(User, target.id)
        if winner is not None and winner.stripe_customer_id:
            return winner.stripe_customer_id
        # No persisted winner found (shouldn't happen) — surface failure.
        raise
    except Exception as e:
        # Bug NEW-G fix: previous code logged + swallowed and returned the
        # customer id, leaving an orphan Stripe customer that we'd never
        # persist (next call creates a *second* duplicate). Roll back the
        # DB session and delete the Stripe customer so retries are clean,
        # then re-raise so the caller's `except stripe.StripeError` (or a
        # 500) surfaces the failure to the user.
        db.session.rollback()
        logger.error(
            "Failed to persist stripe_customer_id=%s for user_id=%s: %s",
            customer.id, target.id, e,
        )
        try:
            stripe.Customer.delete(customer.id)
            logger.info("Rolled back orphan Stripe customer %s", customer.id)
        except stripe.StripeError as del_err:
            # Best-effort: log + leave for out-of-band cleanup.
            logger.error(
                "Failed to rollback Stripe customer %s: %s",
                customer.id, del_err,
            )
        raise
    return customer.id


# ── Create Checkout Session ──────────────────────────────────────────────────

@billing_bp.route("/create-checkout", methods=["POST"])
@api_auth
@general_rate_limit
@require_business_registration
def create_checkout():
    """Create a Stripe Checkout session for Pro or Premium plan."""
    d = request.get_json() or {}
    plan = (d.get("plan") or "").lower()
    if plan not in PLAN_PRICES:
        return api_error(
            en="Invalid plan. Choose 'pro' or 'premium'.",
            kr="유효하지 않은 플랜입니다. 'pro' 또는 'premium' 을 선택해 주세요.",
            code="BILLING_INVALID_PLAN", status=400,
        )

    # Read the price ID at request time, not from the module-level
    # PLAN_PRICES snapshot. Wave G-1 Bug #4 fixed the webhook handler
    # (line 499) the same way: if STRIPE_PRICE_* is rotated (test→live)
    # without a redeploy, the cached snapshot would send a stale price ID
    # to Stripe. The dict above is still used for the plan-name allowlist.
    price_id = os.environ.get(f"STRIPE_PRICE_{plan.upper()}", "") or PLAN_PRICES[plan]
    if not price_id:
        return api_error(
            en=f"Price ID not configured for {plan} plan.",
            kr="결제 플랜 설정이 누락되었습니다. 잠시 후 다시 시도해 주세요.",
            code="BILLING_PRICE_ID_MISSING", status=500,
        )

    # Block users who already hold the highest entitlement via a non-Stripe
    # grant (DEV_FOUNDING_EMAILS → founding_lifetime / premium_plus). These
    # cohorts have ``subscription_status == "inactive"``, so the Stripe-status
    # guard below would let them through → checkout.session.completed would
    # overwrite their lifetime tier with pro/premium + active and start
    # billing them monthly for access they already enjoy for free. Gate on the
    # canonical effective_tier rank, mirroring get_subscription's
    # ``eff_rank > _TIER_RANK["premium"]`` entitlement check.
    eff_rank = _TIER_RANK.get(
        getattr(current_user, "effective_tier", None), 0
    )
    if eff_rank > _TIER_RANK["premium"]:
        return api_error(
            en="You already hold the highest tier — no subscription needed.",
            kr="이미 최상위 권한을 보유하고 있어 별도 구독이 필요하지 않습니다.",
            code="BILLING_ALREADY_ENTITLED", status=409,
        )

    # Wave G-1 Bug #3 (2026-05-18): block double-subscribe.
    # 이중 구독 시 Stripe customer 가 두 개의 active subscription 을 보유하게 되어
    # 사용자가 매월 2배 청구를 받게 됨. 변경은 Customer Portal 로 유도.
    # ``past_due`` 도 차단 — Stripe 가 결제 재시도 중인 구독이 살아 있으므로
    # 새 checkout 을 열면 두 번째 구독이 생겨 동일하게 이중청구된다.
    if getattr(current_user, "subscription_status", None) in ("active", "past_due"):
        return api_error(
            en="Already subscribed. Use the customer portal to change plans.",
            kr="이미 구독 중입니다. 결제 포털에서 플랜을 변경하세요.",
            code="BILLING_ALREADY_SUBSCRIBED", status=409,
        )

    # Wave G-1 Bug #1 (2026-05-18): server-side consent audit trail.
    # 금소법 §19 (설명의무) + 전자상거래법 §22의2 (정기결제 청약 확인) +
    # PIPA §28-8 (Stripe 미국 국외이전 동의) — 클라이언트가 보낸 동의 블록을
    # 서버에서 검증하고 evidentiary timestamp 를 갱신.
    consent = d.get("consent") or {}
    required_keys = {"key_info", "recurring", "stripe_overseas"}
    granted = {k for k, v in consent.items() if v}
    if not required_keys.issubset(granted):
        return api_error(
            en="Billing consent required (key info, recurring billing, "
               "Stripe overseas transfer).",
            kr="결제 동의 누락 — 핵심정보·정기결제·해외이전(Stripe) 동의가 모두 필요합니다.",
            code="BILLING_CONSENT_MISSING", status=400,
        )
    # cross_border_consent_at 갱신 — Stripe 는 미국 결제처리자이므로 PIPA §28-8
    # 국외이전 동의가 갱신되어야 함. (별도 billing_consent_at column 추가는
    # migration 036 — 본 PR 범위 외.) Naive UTC 컨벤션 유지.
    try:
        current_user.cross_border_consent_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "Failed to persist consent timestamp for user_id=%s",
            getattr(current_user, "id", "?"),
        )
        # consent timestamp 실패는 checkout 진행을 막을 정도는 아님 — Stripe 측
        # metadata 에도 user_id 가 있어 사후 reconciliation 가능. 로그만 남김.

    try:
        customer_id = _get_or_create_customer(current_user)
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{FRONTEND_URL}/home?billing=success",
            cancel_url=f"{FRONTEND_URL}/home?billing=cancelled",
            metadata={"user_id": str(current_user.id), "plan": plan},
        )
        return jsonify({"url": session.url})
    except stripe.StripeError as e:
        logger.error("Stripe checkout error: %s", e)
        return api_error(
            en="Failed to create checkout session.",
            kr="결제 세션을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.",
            code="BILLING_CHECKOUT_FAILED", status=500,
        )


# ── Webhook ──────────────────────────────────────────────────────────────────

@billing_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events. No auth — verified by signature."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    if not STRIPE_WEBHOOK_SECRET:
        # 503 (not 500): a missing secret is a transient mis-/un-configuration,
        # not a request-level server fault. Returning 500 makes Stripe treat it
        # as a server crash and retry the same delivery for up to 3 days, while
        # 503 (Service Unavailable) signals "temporarily not accepting webhooks"
        # and avoids advertising our internal configuration state.
        # 2026-05-20 bug-hunter (P1).
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return api_error(
            en="Webhook secret not configured",
            kr="Stripe 웹훅 설정이 누락되었습니다.",
            code="STRIPE_WEBHOOK_SECRET_MISSING", status=503,
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return api_error(
            en="Invalid payload",
            kr="잘못된 요청 본문입니다.",
            code="STRIPE_WEBHOOK_INVALID_PAYLOAD", status=400,
        )
    except stripe.SignatureVerificationError:
        return api_error(
            en="Invalid signature",
            kr="잘못된 웹훅 서명입니다.",
            code="STRIPE_WEBHOOK_INVALID_SIGNATURE", status=400,
        )

    event_type = event["type"]
    event_id = event.get("id") or ""
    data = event["data"]["object"]

    # Idempotency fast-path (migration 028). Stripe retries deliveries for up
    # to 3 days; without this check, duplicate `checkout.session.completed`
    # events emit duplicate revenue audit lines and re-fire side-effects that
    # are technically idempotent at the DB level but pollute ops dashboards.
    # Race window between this check and the INSERT below is closed by the
    # `uq_processed_stripe_events_event_id` UNIQUE constraint — the second
    # concurrent delivery hits IntegrityError and we treat it as deduped.
    if event_id and ProcessedStripeEvent.already_processed(event_id):
        logger.info(
            "Stripe webhook deduped (event_id=%s, event_type=%s)",
            event_id, event_type,
        )
        return jsonify({"ok": True, "deduped": True})

    # Webhook handlers must never 500 — Stripe retries failed webhooks for
    # up to 3 days (exponential backoff), which would spam our error logs
    # and potentially duplicate side-effects. Catch + rollback + log, then
    # ACK so Stripe moves on. The event is still recorded upstream so we
    # can replay manually if the handler truly needed to succeed.
    handler_status = STRIPE_EVENT_STATUS_SUCCESS
    handler_error: str | None = None
    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data)
        elif event_type == "checkout.session.expired":
            _handle_checkout_expired(data)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data)
        elif event_type == "invoice.payment_failed":
            _handle_invoice_payment_failed(data)
        elif event_type == "invoice.paid":
            _handle_invoice_paid(data)
        elif event_type == "charge.refunded":
            _handle_charge_refunded(data)
        elif event_type == "charge.dispute.created":
            _handle_charge_dispute(data, phase="created")
        elif event_type == "charge.dispute.funds_withdrawn":
            _handle_charge_dispute(data, phase="funds_withdrawn")
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            logger.debug("silent-fallback: stripe_webhook", exc_info=True)
            pass
        logger.exception(
            "Stripe webhook handler failed (event_type=%s, event_id=%s)",
            event_type, event_id,
        )
        handler_status = STRIPE_EVENT_STATUS_ERROR
        # Short fingerprint only — full traceback is in the log stream above.
        handler_error = f"{type(exc).__name__}: {str(exc)[:160]}"

    # Record the processed event (success or error) so future retries
    # short-circuit. The error case is recorded too — Stripe will keep
    # retrying for 3 days otherwise, and a poison event would amplify
    # the failure log volume each retry.
    if event_id:
        try:
            ProcessedStripeEvent.record(
                event_id=event_id,
                event_type=event_type,
                status=handler_status,
                error_message=handler_error,
            )
            db.session.commit()
        except IntegrityError:
            # Concurrent delivery raced past our `already_processed` check
            # and inserted first. Roll back our duplicate insert and ACK —
            # the other delivery's record is the canonical one.
            db.session.rollback()
            logger.info(
                "Stripe webhook idempotency race (event_id=%s) — peer recorded first",
                event_id,
            )
        except Exception:
            # Idempotency record failure must never block ACK — Stripe will
            # retry, and the next retry will re-execute the handler. Roll
            # back so the ORM session is clean for the next request.
            db.session.rollback()
            logger.exception(
                "Failed to record ProcessedStripeEvent (event_id=%s, event_type=%s)",
                event_id, event_type,
            )

    if handler_status == STRIPE_EVENT_STATUS_ERROR:
        # Still ACK so Stripe doesn't retry forever (handler error is logged
        # above and the idempotency row records the failure for ops triage).
        return jsonify({"ok": True, "warning": "handler_failed"}), 200

    return jsonify({"ok": True})


def _handle_checkout_completed(session_data):
    """Activate subscription after successful checkout."""
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")
    metadata = session_data.get("metadata", {})
    plan = metadata.get("plan", "pro")

    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        # Try finding by user_id in metadata
        user_id = metadata.get("user_id")
        if user_id:
            try:
                user = db.session.get(User, int(user_id))
            except (ValueError, TypeError):
                logger.error("Webhook: Invalid user_id in metadata: %s", user_id)
                user = None
    if not user:
        logger.error("Webhook: No user found for customer %s", customer_id)
        return

    user.stripe_subscription_id = subscription_id
    user.subscription_tier = PLAN_TIERS.get(plan, "pro")
    user.subscription_status = "active"
    db.session.commit()
    logger.info("User %s subscribed to %s", user.id, plan)


def _handle_checkout_expired(session_data):
    """Enqueue a 1h transactional follow-up for an abandoned checkout.

    Wave G C-M1 (2026-05-19).

    Stripe fires ``checkout.session.expired`` when a Checkout Session
    that the user opened was never completed before the session's
    ``expires_at`` window (default 24h). This is the cleanest signal of
    payment-intent abandonment we get from Stripe — strictly better than
    polling because it's idempotent and arrives exactly once per session.

    We enqueue a row in ``checkout_expirations`` with
    ``scheduled_send_at = expired_at + 1h``. A cron-driven dispatcher
    (``scripts/nightly/checkout_followup_dispatcher.py``) drains the
    queue every 15 min and sends a *transactional* email (정통망법 §50
    transactional carve-out — no marketing copy, no discount language).

    Why enqueue regardless of feature flag
    --------------------------------------
    The dispatcher checks ``PIVOX_CHECKOUT_FOLLOWUP_ENABLED`` per tick.
    Enqueueing unconditionally means a single env flip drains the
    historical backlog into emails — no second migration / no replay
    tooling needed. The dispatcher also bumps the ``skipped_reason``
    field with ``"feature_flag_off"`` if the flag is OFF when the row
    comes due, so we get a clean audit of the suppressed sends.

    Resolution of the User row mirrors ``_handle_checkout_completed``:
    customer id first, then metadata ``user_id`` as fallback. If neither
    resolves we log + ACK — the abandoned-session ping is informational
    and not worth blocking the webhook.
    """
    # Local import — avoids a top-level circular (routes → services →
    # models → routes) on first app boot.
    from models import CheckoutExpiration

    customer_id = session_data.get("customer")
    session_id = session_data.get("id")
    if not session_id:
        # Defensive — Stripe should always send id; skip silently.
        logger.warning("checkout.session.expired with no session id")
        return

    metadata = session_data.get("metadata", {}) or {}

    user = None
    if customer_id:
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if user is None:
        user_id_meta = metadata.get("user_id")
        if user_id_meta:
            try:
                user = db.session.get(User, int(user_id_meta))
            except (ValueError, TypeError):
                logger.error(
                    "checkout.session.expired: invalid user_id metadata: %s",
                    user_id_meta,
                )
    if user is None:
        logger.info(
            "checkout.session.expired: no user for customer=%s session=%s "
            "— skip enqueue",
            customer_id, session_id,
        )
        return

    # ``expires_at`` is a Unix timestamp (seconds, int) on the Session
    # object. Fall back to "now" if Stripe omitted it — that still gives
    # us a reasonable +1h target.
    expires_at_unix = session_data.get("expires_at")
    if isinstance(expires_at_unix, (int, float)) and expires_at_unix > 0:
        expired_at = datetime.fromtimestamp(
            float(expires_at_unix), tz=timezone.utc,
        ).replace(tzinfo=None)
    else:
        expired_at = datetime.now(timezone.utc).replace(tzinfo=None)

    row = CheckoutExpiration.enqueue(
        user_id=user.id,
        session_id=session_id,
        expired_at=expired_at,
    )
    if row is None:
        # Idempotent — already enqueued from a prior webhook delivery.
        logger.info(
            "checkout.session.expired: session=%s already enqueued — dedupe",
            session_id,
        )
        return

    # Commit so the row is durable before the surrounding handler ACKs.
    # If this commit fails the outer try/except in stripe_webhook will
    # roll back; the idempotency record then carries status=error and
    # Stripe will retry the delivery (which the next attempt dedupes).
    db.session.commit()
    logger.info(
        "checkout.session.expired enqueued: user=%s session=%s send_at=%s",
        user.id, session_id, row.scheduled_send_at.isoformat(),
    )


def _handle_subscription_updated(subscription):
    """Handle subscription changes (upgrade/downgrade/renewal)."""
    customer_id = subscription.get("customer")
    status = subscription.get("status")  # active, past_due, canceled, etc.

    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.subscription_status = status
    if status == "active":
        # Check which price to determine tier
        items = subscription.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            # Wave G-1 Bug #4 (2026-05-18): module-level STRIPE_PRICE_*
            # 은 import 시점에 한 번만 캡처되어 deploy 후 env 변경이 반영되지
            # 않는다. webhook 핸들러는 env 를 runtime 마다 read 해서 test-mode
            # → live-mode 전환 시 재배포 없이 즉시 반영되어야 한다.
            stripe_price_pro = os.environ.get("STRIPE_PRICE_PRO", "")
            stripe_price_premium = os.environ.get("STRIPE_PRICE_PREMIUM", "")
            if not (stripe_price_pro or stripe_price_premium):
                logger.warning(
                    "STRIPE_PRICE_* env not set — subscription.updated tier "
                    "sync skipped (user_id=%s, price_id=%s)",
                    user.id, price_id,
                )
            elif price_id == stripe_price_premium:
                user.subscription_tier = "premium"
            elif price_id == stripe_price_pro:
                user.subscription_tier = "pro"
            else:
                logger.warning(
                    "Unknown price_id in subscription.updated: %s "
                    "(user_id=%s) — tier kept as %s",
                    price_id, user.id, user.subscription_tier,
                )
    elif status in ("canceled", "unpaid"):
        user.subscription_tier = "free"
        user.subscription_status = "inactive"

    db.session.commit()
    logger.info("User %s subscription updated: %s", user.id, status)


def _handle_subscription_deleted(subscription):
    """Handle subscription cancellation."""
    customer_id = subscription.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.subscription_tier = "free"
    user.subscription_status = "inactive"
    user.stripe_subscription_id = None
    db.session.commit()
    logger.info("User %s subscription deleted", user.id)


def _handle_invoice_payment_failed(invoice):
    """Handle failed invoice payment.

    Pre-2026-05-19: log-only. Tier intentionally kept active — Stripe
    retries automatically on its smart-retry schedule (3-4 attempts over
    ~10 days), so flipping tier on attempt #1 would churn paying users
    over transient card holds.

    2026-05-19 (S2 + C-CS1): two side-effects added —
      (a) CEO Slack DM via ``services.billing_notifications`` so revenue
          loss is visible immediately, not buried in Railway logs.
      (b) Transactional email to the affected user (정통망법 §50 거래
          정보성, marketing consent 면제) with a Customer Portal link to
          update the card.

    Both side-effects are fire-and-forget — failures are logged + Sentry-
    captured but never raise, since the outer webhook handler must ACK
    200 to stop Stripe's 3-day retry loop.
    """
    customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    attempt = invoice.get("attempt_count", 0)
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    user_id = user.id if user else "unknown"
    logger.warning(
        f"Invoice payment failed: invoice={invoice_id} "
        f"customer={customer_id} user={user_id} attempt={attempt}"
    )

    # Side-effects — never raise (webhook handler must ACK 200).
    try:
        from services.billing_notifications import (
            notify_payment_failed_slack,
            notify_payment_failed_email,
        )
        notify_payment_failed_slack(user=user, invoice=invoice)
        notify_payment_failed_email(user=user, invoice=invoice)
    except Exception:
        logger.exception(
            "payment_failed notification dispatch failed "
            "(invoice=%s user=%s) — handler continues",
            invoice_id, user_id,
        )


def _handle_invoice_paid(invoice):
    """Log successful invoice payment."""
    customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    amount = invoice.get("amount_paid", 0)
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    user_id = user.id if user else "unknown"
    logger.info(
        f"Invoice paid: invoice={invoice_id} "
        f"customer={customer_id} user={user_id} amount={amount}"
    )


# ── Refund / Chargeback (Dispute) handlers ───────────────────────────────────
#
# TIER-DOWNGRADE POLICY — IMPLEMENTED (CEO-authorized 2026-05-22).
#
# Stripe sends ``charge.refunded`` / ``charge.dispute.created`` /
# ``charge.dispute.funds_withdrawn``. The tier action per event:
#
#   • charge.refunded — FULL refund (amount_refunded >= amount, or
#     refunded == true) → downgrade user to ``subscription_tier = "free"``
#     + ``subscription_status = "canceled"`` (mirrors the cancel path) +
#     commit. Rationale: 전자상거래법 §17 청약철회 / full withdrawal
#     rescinds the contract → revoke paid access.
#   • charge.refunded — PARTIAL refund (0 < amount_refunded < amount) →
#     KEEP tier (a partial refund of a divisible period shouldn't cut
#     access). Observability only.
#   • charge.dispute.created → KEEP tier (the dispute may be WON; a
#     downgrade now would wrongly punish a customer). Observability only.
#   • charge.dispute.funds_withdrawn (dispute lost / funds pulled) →
#     downgrade user to ``subscription_tier = "free"`` +
#     ``subscription_status = "canceled"`` + commit. Rationale: dispute
#     lost = chargeback final = revoke access.
#
# ⚠️ LEGAL ASSUMPTION (CEO-authorized 2026-05-22, pending lawyer
#     confirmation): full refund treated as §17 청약철회 → access revoked;
#     partial refund preserves access. Confirm with counsel; adjust if
#     가분적 디지털콘텐츠 partial-period rules differ.
#
# SAFER-INTERPRETATION DEFAULT: when FULL-vs-PARTIAL cannot be determined
# from the charge object (e.g. ``amount`` missing/zero), treat as PARTIAL
# (keep access) — a wrongful downgrade of a paying customer is worse than a
# delayed manual one, and ops still receives the Slack alert.
#
# Mechanics (all handlers):
#   • resolve the local User (best-effort, by stripe_customer_id — same
#     lookup the other handlers use; metadata fallback is not available on
#     charge/dispute objects),
#   • emit a WARNING log,
#   • fire the SAME Slack ops alert mechanism billing already uses
#     (SLACK_WEBHOOK_URL — see services/billing_notifications.py) on EVERY
#     event so ops sees both downgrade and keep-access cases,
#   • on downgrade, commit (mirrors _handle_subscription_updated /
#     _handle_subscription_deleted),
#   • NEVER raise (the outer webhook wrapper must ACK 200 so Stripe stops
#     its 3-day retry — any error is logged and re-raised only to the outer
#     try/except, which rolls back + ACKs).


def _notify_refund_dispute_slack(
    *, kind: str, summary: str, action: str | None = None,
) -> bool:
    """Post an ops Slack alert for a refund/dispute event.

    Reuses the SAME ``SLACK_WEBHOOK_URL`` incoming-webhook mechanism that
    ``services.billing_notifications.notify_payment_failed_slack`` already
    uses — no new env var, no new dependency, no new cost. Returns ``True``
    on a successful POST; never raises (Sentry captures any error so the
    webhook ACK is never blocked). Skips silently when the webhook URL is
    unset (dev / CI).

    ``action`` is the policy-action footer line (e.g. what happened to the
    tier). Defaults to the keep-access wording so callers that don't pass it
    still produce accurate text. Always references 전자상거래법 §17.
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.debug("%s Slack skipped: SLACK_WEBHOOK_URL unset", kind)
        return False
    try:
        import requests  # local import — keeps cold-start fast
    except Exception:
        logger.warning("%s Slack skipped: requests not installed", kind)
        return False

    footer = action or (
        "• tier 유지 (access 보존) — MANUAL ACTION REQUIRED 검토 "
        "(전자상거래법 §17)"
    )
    text = (
        f":rotating_light: *Stripe {kind}*\n"
        f"{summary}\n"
        f"{footer}"
    )
    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=10)
        resp.raise_for_status()
        logger.info("%s Slack ops alert sent", kind)
        return True
    except Exception as exc:
        logger.exception("%s Slack post failed: %s", kind, exc)
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        return False


def _resolve_user_by_customer(customer_id):
    """Best-effort local-User lookup by Stripe customer id.

    Mirrors the lookup in ``_handle_subscription_updated`` /
    ``_handle_invoice_payment_failed``. Returns ``None`` (never raises) when
    the customer id is empty or no row matches.
    """
    if not customer_id:
        return None
    try:
        return User.query.filter_by(stripe_customer_id=customer_id).first()
    except Exception:
        logger.debug("user lookup by customer_id failed", exc_info=True)
        return None


def _downgrade_user_to_free(user, *, reason: str) -> None:
    """Revoke paid access: set tier=free + status=canceled + commit.

    Mirrors the cancel paths in ``_handle_subscription_updated`` (status in
    ("canceled","unpaid") → tier "free") and ``_handle_subscription_deleted``
    (tier "free" + status + ``db.session.commit()``). ``subscription_status``
    is set to ``"canceled"`` to mirror the cancel intent. Raises on a db
    error — the outer webhook try/except rolls back + ACKs 200.
    """
    user.subscription_tier = "free"
    user.subscription_status = "canceled"
    # Clear the Stripe subscription id, mirroring _handle_subscription_deleted
    # (line 539). Without this, get_subscription's ``if u.stripe_subscription_id``
    # branch would still retrieve() the cancelled sub and surface a future
    # current_period_end to a now-free user.
    user.stripe_subscription_id = None
    db.session.commit()
    logger.warning(
        "Subscription tier downgraded to free (reason=%s, user_id=%s)",
        reason, user.id,
    )


def _handle_charge_refunded(charge):
    """Handle a ``charge.refunded`` event — downgrade on FULL refund only.

    FULL refund (amount_refunded >= amount, or refunded == true) →
    downgrade to free (전자상거래법 §17 청약철회 rescinds the contract).
    PARTIAL refund (0 < amount_refunded < amount) → keep access. When
    FULL-vs-PARTIAL can't be determined (amount missing/zero) the SAFER
    default is PARTIAL/keep-access. Always logs + alerts ops.
    """
    charge_id = charge.get("id")
    payment_intent = charge.get("payment_intent")
    customer_id = charge.get("customer")
    amount = charge.get("amount") or 0
    amount_refunded = charge.get("amount_refunded") or 0
    refunded_flag = bool(charge.get("refunded"))
    currency = charge.get("currency")
    user = _resolve_user_by_customer(customer_id)
    user_id = getattr(user, "id", "unknown") if user else "unknown"
    user_email = getattr(user, "email", "unknown") if user else "unknown"

    # FULL vs PARTIAL. The ``refunded`` boolean (Stripe sets it when the
    # whole charge is refunded) is authoritative; otherwise compare amounts.
    # Safer default: only call it FULL when we can prove it — a known
    # positive ``amount`` with ``amount_refunded >= amount``, or the flag.
    if refunded_flag:
        is_full = True
    elif amount > 0 and amount_refunded >= amount:
        is_full = True
    else:
        # PARTIAL, or amount unknown/zero (can't prove full) → keep access.
        is_full = False

    if is_full and user is not None:
        try:
            _downgrade_user_to_free(user, reason="charge.refunded (full)")
            action = "• tier → free (전부환불/청약철회 §17 → access 회수)"
        except Exception:
            logger.exception(
                "REFUND downgrade commit failed (charge=%s user=%s)",
                charge_id, user_id,
            )
            raise
    elif is_full:
        # Full refund but no local user → can't downgrade an unknown user.
        action = "• tier 변경 불가 (전부환불이나 user 미해결) — MANUAL"
    else:
        action = "• tier 유지 (부분환불/가분 콘텐츠 → access 보존, §17)"

    logger.warning(
        "REFUND received (full=%s): charge=%s payment_intent=%s customer=%s "
        "amount=%s amount_refunded=%s %s user=%s (%s)",
        is_full, charge_id, payment_intent, customer_id, amount,
        amount_refunded, (currency or "?").upper(), user_id, user_email,
    )
    _notify_refund_dispute_slack(
        kind="REFUND",
        summary=(
            f"• charge: `{charge_id}`\n"
            f"• payment_intent: `{payment_intent}`\n"
            f"• customer: `{customer_id}`\n"
            f"• 환불액: {amount_refunded} / {amount} {(currency or '?').upper()}\n"
            f"• user: `{user_id}` ({user_email})"
        ),
        action=action,
    )


def _handle_charge_dispute(dispute, *, phase: str):
    """Handle a chargeback/dispute event — downgrade only on funds_withdrawn.

    ``charge.dispute.created`` → KEEP tier (the dispute may be WON; a
    downgrade now would wrongly punish a customer). Observability only.
    ``charge.dispute.funds_withdrawn`` (dispute lost / funds pulled) →
    downgrade to free (전자상거래법 §17 — chargeback final = revoke access).
    Always logs + alerts ops; never raises beyond the outer webhook wrapper.
    """
    dispute_id = dispute.get("id")
    charge_id = dispute.get("charge")
    payment_intent = dispute.get("payment_intent")
    amount = dispute.get("amount") or 0
    currency = dispute.get("currency")
    reason = dispute.get("reason") or "unknown"
    status = dispute.get("status") or "unknown"
    # Stripe dispute objects do NOT carry ``customer`` at the top level — it
    # lives on the underlying Charge. Without resolving it the funds_withdrawn
    # branch falls through to MANUAL on every real event and never revokes
    # paid access. Retrieve the charge to recover the customer id.
    customer_id = dispute.get("customer")
    if not customer_id and charge_id:
        try:
            charge = stripe.Charge.retrieve(charge_id)
            customer_id = charge.get("customer")
        except stripe.StripeError:
            logger.warning(
                "DISPUTE charge retrieve failed (dispute=%s charge=%s)",
                dispute_id, charge_id, exc_info=True,
            )
    user = _resolve_user_by_customer(customer_id)
    user_id = getattr(user, "id", "unknown") if user else "unknown"
    user_email = getattr(user, "email", "unknown") if user else "unknown"

    if phase == "funds_withdrawn" and user is not None:
        try:
            _downgrade_user_to_free(
                user, reason="charge.dispute.funds_withdrawn (lost)",
            )
            action = "• tier → free (분쟁 패소/chargeback 확정 → access 회수, §17)"
        except Exception:
            logger.exception(
                "DISPUTE downgrade commit failed (dispute=%s user=%s)",
                dispute_id, user_id,
            )
            raise
    elif phase == "funds_withdrawn":
        action = "• tier 변경 불가 (분쟁 패소이나 user 미해결) — MANUAL"
    else:
        # created → keep access (dispute may be won).
        action = "• tier 유지 (분쟁 진행중, 승소 가능 → access 보존, §17)"

    logger.warning(
        "DISPUTE (%s) received: dispute=%s charge=%s payment_intent=%s "
        "customer=%s amount=%s %s reason=%s status=%s user=%s (%s)",
        phase, dispute_id, charge_id, payment_intent, customer_id, amount,
        (currency or "?").upper(), reason, status, user_id, user_email,
    )
    _notify_refund_dispute_slack(
        kind=f"DISPUTE ({phase})",
        summary=(
            f"• dispute: `{dispute_id}` (status={status}, reason={reason})\n"
            f"• charge: `{charge_id}`\n"
            f"• payment_intent: `{payment_intent}`\n"
            f"• 금액: {amount} {(currency or '?').upper()}\n"
            f"• customer: `{customer_id}`\n"
            f"• user: `{user_id}` ({user_email})"
        ),
        action=action,
    )


# ── Get Subscription Status ─────────────────────────────────────────────────

@billing_bp.route("/subscription")
@api_auth
def get_subscription():
    """Return current user's subscription info."""
    u = current_user
    # Resolve entitlement off the canonical tier rank (routes/decorators._TIER_RANK)
    # via effective_tier so dev/owner overrides (DEV_FOUNDING_EMAILS etc.) and the
    # Companion-tier rollout (premium_plus rank 3, founding_lifetime rank 4) are all
    # honored — the old `subscription_tier in ("pro","premium")` literal silently
    # excluded the highest-paying cohorts.
    #
    # founding_lifetime / premium_plus are lifetime / Companion grants with NO active
    # Stripe subscription, so their stored subscription_status is typically "inactive".
    # Gating has_active_subscription on `status == "active"` would wrongly report them
    # as lapsed (→ frontend shows upgrade CTAs, hides manage-subscription). Treat any
    # tier above "premium" (rank > 2) as entitled regardless of Stripe status, and the
    # billed tiers (pro/premium) as active only when Stripe says so.
    eff_tier = (
        getattr(u, "effective_tier", None)
        or getattr(u, "subscription_tier", "free")
        or "free"
    )
    eff_rank = _TIER_RANK.get(eff_tier, 0)
    sub_status = getattr(u, "subscription_status", "inactive") or "inactive"
    has_active = (
        eff_rank > _TIER_RANK["premium"]              # premium_plus / founding_lifetime — always entitled
        # pro / premium — active OR past_due. past_due = Stripe is retrying
        # a failed charge; @require_tier still grants access during the
        # retry window, so has_active must agree or the frontend shows a
        # bogus upgrade CTA while the backend still serves paid content.
        or (eff_rank > _TIER_RANK["free"] and sub_status in ("active", "past_due"))
    )
    result = {
        "subscription_tier": u.subscription_tier,
        "subscription_status": sub_status,
        "has_active_subscription": has_active,
    }

    # Fetch latest info from Stripe if they have a subscription
    if u.stripe_subscription_id:
        try:
            sub = stripe.Subscription.retrieve(u.stripe_subscription_id)
            result["current_period_end"] = sub.get("current_period_end")
            result["cancel_at_period_end"] = sub.get("cancel_at_period_end", False)
        except stripe.StripeError:
            logger.debug("silent-fallback: get_subscription", exc_info=True)
            pass

    return jsonify(result)


# ── Customer Portal ──────────────────────────────────────────────────────────

@billing_bp.route("/portal", methods=["POST"])
@api_auth
@general_rate_limit
@require_business_registration
def create_portal():
    """Create a Stripe Customer Portal session for managing subscription."""
    if not current_user.stripe_customer_id:
        return api_error(
            en="No billing account found.",
            kr="연결된 결제 계정이 없습니다. 먼저 구독을 등록해 주세요.",
            code="BILLING_NO_ACCOUNT", status=400,
        )

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/home",
        )
        return jsonify({"url": session.url})
    except stripe.StripeError as e:
        logger.error("Stripe portal error: %s", e)
        return api_error(
            en="Failed to create portal session.",
            kr="결제 관리 페이지를 열지 못했습니다. 잠시 후 다시 시도해 주세요.",
            code="BILLING_PORTAL_FAILED", status=500,
        )


# ── Billing Availability ─────────────────────────────────────────────────────

@billing_bp.route("/availability", methods=["GET"])
def billing_availability():
    """Whether checkout is enabled (frontend uses this to disable pricing CTAs).

    No auth required — the pricing page is publicly visible and needs to know
    whether to show the "Coming soon" state before the user logs in.
    """
    available = _business_registration_complete()
    payload = {
        "available": available,
        "code": None if available else "BUSINESS_REGISTRATION_PENDING",
        "message_ko": (
            "결제 가능"
            if available
            else "결제는 사업자등록 및 통신판매업 신고 완료 후 활성화됩니다"
        ),
    }
    return jsonify(payload)
