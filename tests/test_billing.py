"""
tests/test_billing.py — Stripe billing routes
===============================================
All Stripe SDK calls are mocked. Verifies:
  - Invalid plan names rejected
  - Checkout session creation flow
  - Webhook signature verification
"""
from unittest.mock import patch, MagicMock



class TestCreateCheckout:
    def test_unauthenticated_is_blocked(self, client):
        r = client.post("/api/billing/create-checkout", json={"plan": "pro"})
        assert r.status_code == 401

    def test_invalid_plan_returns_400(self, client, auth_user):
        r = client.post("/api/billing/create-checkout", json={"plan": "turbo"})
        assert r.status_code == 400

    def test_missing_price_id_returns_500(self, client, auth_user):
        """STRIPE_PRICE_PRO is empty in tests → route must fail cleanly."""
        r = client.post("/api/billing/create-checkout", json={"plan": "pro"})
        # Either 500 (price not configured) or 400 — but never 200.
        assert r.status_code in (500, 400)

    def test_checkout_success_flow_with_mocked_stripe(self, client, auth_user):
        """With a valid price_id env + mocked Stripe, checkout returns a URL."""
        with patch("routes.billing.PLAN_PRICES", {"pro": "price_123"}), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_customer = MagicMock(id="cus_abc123")
            mock_stripe.Customer.create.return_value = mock_customer
            mock_session = MagicMock(url="https://checkout.stripe.com/pay/test")
            mock_stripe.checkout.Session.create.return_value = mock_session
            # StripeError fallback import
            mock_stripe.StripeError = Exception

            r = client.post("/api/billing/create-checkout", json={"plan": "pro"})

        assert r.status_code == 200
        assert r.get_json()["url"].startswith("https://checkout.stripe.com/")


class TestWebhook:
    def test_webhook_without_secret_configured_returns_500(self, raw_client):
        """Webhook endpoint is CSRF-exempt but still requires STRIPE_WEBHOOK_SECRET."""
        with patch("routes.billing.STRIPE_WEBHOOK_SECRET", ""):
            r = raw_client.post("/api/billing/webhook", data=b"{}",
                                 headers={"Stripe-Signature": "t=1,v1=xxx"})
        assert r.status_code == 500

    def test_webhook_invalid_signature_returns_400(self, raw_client):
        with patch("routes.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("routes.billing.stripe") as mock_stripe:
            # Stripe SDK exposes both attributes on the module.
            mock_stripe.SignatureVerificationError = type(
                "SigErr", (Exception,), {}
            )
            mock_stripe.Webhook.construct_event.side_effect = \
                mock_stripe.SignatureVerificationError("bad sig")
            r = raw_client.post("/api/billing/webhook", data=b"{}",
                                 headers={"Stripe-Signature": "t=1,v1=bad"})
        assert r.status_code == 400
