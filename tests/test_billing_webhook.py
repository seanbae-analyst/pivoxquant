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
