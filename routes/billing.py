"""Billing routes: Stripe subscription checkout, webhooks, portal."""
import os
import logging
from functools import wraps

import stripe
from flask import Blueprint, request, jsonify

from extensions import db
from models import User
from flask_login import current_user
from .decorators import api_auth
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
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email,
        name=user.name,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "Failed to persist stripe_customer_id=%s for user_id=%s",
            customer.id, user.id,
        )
        # Stripe customer was created successfully — surface the id even
        # though we couldn't persist it. Next checkout attempt will create
        # a duplicate customer; orphan cleanup is handled out-of-band.
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
        return jsonify({"error": "Invalid plan. Choose 'pro' or 'premium'."}), 400

    price_id = PLAN_PRICES[plan]
    if not price_id:
        return jsonify({"error": f"Price ID not configured for {plan} plan."}), 500

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
        logger.error(f"Stripe checkout error: {e}")
        return jsonify({"error": "Failed to create checkout session."}), 500


# ── Webhook ──────────────────────────────────────────────────────────────────

@billing_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events. No auth — verified by signature."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return jsonify({"error": "Webhook secret not configured"}), 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event["type"]
    data = event["data"]["object"]

    # Webhook handlers must never 500 — Stripe retries failed webhooks for
    # up to 3 days (exponential backoff), which would spam our error logs
    # and potentially duplicate side-effects. Catch + rollback + log, then
    # ACK so Stripe moves on. The event is still recorded upstream so we
    # can replay manually if the handler truly needed to succeed.
    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data)
        elif event_type == "invoice.payment_failed":
            _handle_invoice_payment_failed(data)
        elif event_type == "invoice.paid":
            _handle_invoice_paid(data)
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            logger.debug("silent-fallback: stripe_webhook", exc_info=True)
            pass
        logger.exception(
            "Stripe webhook handler failed (event_type=%s, event_id=%s)",
            event_type, event.get("id"),
        )
        # Still ACK so Stripe doesn't retry forever.
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
                logger.error(f"Webhook: Invalid user_id in metadata: {user_id}")
                user = None
    if not user:
        logger.error(f"Webhook: No user found for customer {customer_id}")
        return

    user.stripe_subscription_id = subscription_id
    user.subscription_tier = PLAN_TIERS.get(plan, "pro")
    user.subscription_status = "active"
    db.session.commit()
    logger.info(f"User {user.id} subscribed to {plan}")


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
            if price_id == STRIPE_PRICE_PREMIUM:
                user.subscription_tier = "premium"
            elif price_id == STRIPE_PRICE_PRO:
                user.subscription_tier = "pro"
    elif status in ("canceled", "unpaid"):
        user.subscription_tier = "free"
        user.subscription_status = "inactive"

    db.session.commit()
    logger.info(f"User {user.id} subscription updated: {status}")


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
    logger.info(f"User {user.id} subscription deleted")


def _handle_invoice_payment_failed(invoice):
    """Log failed invoice payment. Tier is kept — Stripe retries automatically."""
    customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    attempt = invoice.get("attempt_count", 0)
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    user_id = user.id if user else "unknown"
    logger.warning(
        f"Invoice payment failed: invoice={invoice_id} "
        f"customer={customer_id} user={user_id} attempt={attempt}"
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


# ── Get Subscription Status ─────────────────────────────────────────────────

@billing_bp.route("/subscription")
@api_auth
def get_subscription():
    """Return current user's subscription info."""
    u = current_user
    result = {
        "subscription_tier": u.subscription_tier,
        "subscription_status": getattr(u, "subscription_status", "inactive") or "inactive",
        "has_active_subscription": (
            getattr(u, "subscription_status", "inactive") == "active"
            and u.subscription_tier in ("pro", "premium")
        ),
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
        return jsonify({"error": "No billing account found."}), 400

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/home",
        )
        return jsonify({"url": session.url})
    except stripe.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        return jsonify({"error": "Failed to create portal session."}), 500


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
