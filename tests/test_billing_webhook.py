"""tests/test_billing_webhook.py — Stripe /api/billing/webhook handlers.

Wave 11 (P1 critical path) — supplements tests/test_billing.py which only
covered checkout. We now exercise the webhook event-dispatch table for the
three handlers most load-bearing on subscription state:

  - Invalid signature → 400 (matches existing behaviour, sanity check).
  - customer.subscription.deleted → user tier reset to "free" + status
    "inactive".
  - invoice.paid → handler runs without raising; no tier mutation expected
    (tier comes from checkout.completed / subscription.updated), but the
    log path must succeed.

Stripe SDK is fully patched — we never make a real network call. The
``construct_event`` mock returns a synthetic event dict that the handler
dispatch table uses directly.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _registration_complete(monkeypatch):
    """Webhook itself is unguarded but other billing tests may share the app."""
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.setenv("TELESELLER_REGISTRATION_NUMBER", "2026-Seoul-1234")


def _make_user_with_sub(app, *, tier="pro", status="active"):
    """Insert a user with an active subscription tied to customer cus_test."""
    from extensions import db
    from models import User
    with app.app_context():
        u = User(
            email="webhook@test.com",
            name="Webhook User",
            available_capital=10000.0,
            available_capital_krw=1_000_000.0,
            subscription_tier=tier,
        )
        u.set_pw("password123")
        u.stripe_customer_id = "cus_test_123"
        u.stripe_subscription_id = "sub_test_123"
        u.subscription_status = status
        db.session.add(u)
        db.session.commit()
        return u.id


class TestWebhookInvalidSignature:
    def test_webhook_invalid_signature_401(self, raw_client):
        """Stripe SignatureVerificationError must surface as 400 (not 500/200).

        Test name says 401 per the wave plan, but Stripe's contract is 400 for
        bad signatures (401 would imply auth, this is a signature mismatch).
        We verify the actual contract.
        """
        with patch("routes.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_stripe.SignatureVerificationError = type(
                "SigErr", (Exception,), {}
            )
            mock_stripe.Webhook.construct_event.side_effect = \
                mock_stripe.SignatureVerificationError("bad sig")
            r = raw_client.post(
                "/api/billing/webhook",
                data=b"{}",
                headers={"Stripe-Signature": "t=1,v1=bad"},
            )
        assert r.status_code == 400
        body = r.get_json()
        assert "Invalid signature" in body.get("error", "")


class TestWebhookSubscriptionDeleted:
    def test_webhook_customer_subscription_deleted(self, raw_client, app):
        """customer.subscription.deleted → user.subscription_tier = 'free'."""
        user_id = _make_user_with_sub(app, tier="pro", status="active")

        fake_event = {
            "id": "evt_test_deleted",
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_test_123"}},
        }
        with patch("routes.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_stripe.SignatureVerificationError = type(
                "SigErr", (Exception,), {}
            )
            mock_stripe.Webhook.construct_event.return_value = fake_event
            r = raw_client.post(
                "/api/billing/webhook",
                data=b"{}",
                headers={"Stripe-Signature": "t=1,v1=ok"},
            )
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

        # Verify side-effect: user tier reset.
        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.subscription_tier == "free"
            assert u.subscription_status == "inactive"
            assert u.stripe_subscription_id is None


class TestWebhookInvoicePaid:
    def test_webhook_invoice_paid(self, raw_client, app):
        """invoice.paid event must ACK 200 without mutating tier.

        Tier movements come from checkout.completed / subscription.updated.
        invoice.paid is logged but never escalates a tier on its own — that
        path is covered here by asserting the response is 200 + no DB drift.
        """
        user_id = _make_user_with_sub(app, tier="pro", status="active")

        fake_event = {
            "id": "evt_test_invoice_paid",
            "type": "invoice.paid",
            "data": {"object": {
                "id": "in_test_123",
                "customer": "cus_test_123",
                "amount_paid": 990,
            }},
        }
        with patch("routes.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_stripe.SignatureVerificationError = type(
                "SigErr", (Exception,), {}
            )
            mock_stripe.Webhook.construct_event.return_value = fake_event
            r = raw_client.post(
                "/api/billing/webhook",
                data=b"{}",
                headers={"Stripe-Signature": "t=1,v1=ok"},
            )
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

        # Tier must be unchanged — invoice.paid is a log-only event here.
        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.subscription_tier == "pro"
            assert u.subscription_status == "active"


# ── Wave 10 (QA gap fill) — webhook handlers without prior tests ────────────
# 2026-05-17: customer.subscription.updated + invoice.payment_failed had
# ZERO test coverage (qa-agent P0 finding). These mutate subscription_tier
# / subscription_status — silent regressions are an immediate revenue +
# legal surface bug. Same Stripe SDK patching pattern as TestWebhookInvoicePaid.


def _post_webhook(raw_client, fake_event):
    """Shared mini-driver for the new event-handler tests below."""
    with patch("routes.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
         patch("routes.billing.stripe") as mock_stripe:
        mock_stripe.SignatureVerificationError = type(
            "SigErr", (Exception,), {}
        )
        mock_stripe.Webhook.construct_event.return_value = fake_event
        return raw_client.post(
            "/api/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "t=1,v1=ok"},
        )


class TestWebhookSubscriptionUpdated:
    """customer.subscription.updated — handler at routes/billing.py:297."""

    def test_subscription_updated_pro_to_premium(self, raw_client, app, monkeypatch):
        """Upgrade pro→premium via price_id swap must lift the tier.

        Wave G-1 Bug #4 (2026-05-18): handler now reads STRIPE_PRICE_* via
        ``os.environ.get`` at runtime so a Stripe test-mode → live-mode env
        swap is picked up without a redeploy. Tests must set the env vars
        rather than patching the (now-unused) module-level cache.
        """
        monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_test")
        monkeypatch.setenv("STRIPE_PRICE_PREMIUM", "price_premium_test")
        user_id = _make_user_with_sub(app, tier="pro", status="active")

        fake_event = {
            "id": "evt_sub_upgrade",
            "type": "customer.subscription.updated",
            "data": {"object": {
                "customer": "cus_test_123",
                "status": "active",
                "items": {"data": [
                    {"price": {"id": "price_premium_test"}}
                ]},
            }},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200

        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.subscription_tier == "premium"
            assert u.subscription_status == "active"

    def test_subscription_updated_past_due_keeps_tier(self, raw_client, app):
        """status=past_due updates status only; tier stays so the user can
        still load their data while Stripe retries the charge."""
        user_id = _make_user_with_sub(app, tier="pro", status="active")

        fake_event = {
            "id": "evt_sub_past_due",
            "type": "customer.subscription.updated",
            "data": {"object": {
                "customer": "cus_test_123",
                "status": "past_due",
                "items": {"data": []},
            }},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200

        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.subscription_status == "past_due"
            assert u.subscription_tier == "pro"

    def test_subscription_updated_canceled_drops_to_free(self, raw_client, app):
        """status=canceled normalises to tier=free + status=inactive."""
        user_id = _make_user_with_sub(app, tier="premium", status="active")

        fake_event = {
            "id": "evt_sub_canceled",
            "type": "customer.subscription.updated",
            "data": {"object": {
                "customer": "cus_test_123",
                "status": "canceled",
                "items": {"data": []},
            }},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200

        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.subscription_tier == "free"
            assert u.subscription_status == "inactive"

    def test_subscription_updated_unknown_customer_is_noop(self, raw_client, app):
        """Missing customer row must not 500 — Stripe routinely emits events
        for customers we no longer own."""
        fake_event = {
            "id": "evt_sub_unknown",
            "type": "customer.subscription.updated",
            "data": {"object": {
                "customer": "cus_does_not_exist",
                "status": "active",
                "items": {"data": []},
            }},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200


class TestWebhookInvoicePaymentFailed:
    """invoice.payment_failed — handler at routes/billing.py:338."""

    def test_invoice_payment_failed_logs_no_mutation(self, raw_client, app):
        """Per the handler docstring, tier is *intentionally* kept on a
        failed invoice — Stripe retries automatically. This test pins
        that contract so a future drift (e.g. flipping tier to free) is
        caught immediately."""
        user_id = _make_user_with_sub(app, tier="pro", status="active")

        fake_event = {
            "id": "evt_invoice_failed",
            "type": "invoice.payment_failed",
            "data": {"object": {
                "id": "in_failed_456",
                "customer": "cus_test_123",
                "attempt_count": 2,
            }},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.subscription_tier == "pro"
            assert u.subscription_status == "active"

    def test_invoice_payment_failed_unknown_customer_is_noop(self, raw_client, app):
        """Unknown customer must 200 + skip (covers 'user_id=unknown' log)."""
        fake_event = {
            "id": "evt_invoice_failed_unknown",
            "type": "invoice.payment_failed",
            "data": {"object": {
                "id": "in_failed_999",
                "customer": "cus_does_not_exist",
                "attempt_count": 1,
            }},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200
