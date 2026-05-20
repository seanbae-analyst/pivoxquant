"""
tests/test_billing.py — Stripe billing routes
===============================================
All Stripe SDK calls are mocked. Verifies:
  - Invalid plan names rejected
  - Checkout session creation flow
  - Webhook signature verification
  - Wave G-1 Bug #1: consent block required (server-side audit trail)
  - Wave G-1 Bug #3: active subscription returns 409 (double-subscribe block)

Note: 사업자등록 가드 (BUSINESS_REGISTRATION_NUMBER +
TELESELLER_REGISTRATION_NUMBER) 가 결제 endpoint 앞단에 있으므로,
기존 검증 테스트들은 가드를 통과시킨 뒤 plan/price 검증을 확인한다.
가드 자체의 동작은 tests/test_billing_gate.py 에서 검증한다.
"""
from unittest.mock import patch, MagicMock

import pytest


# Wave G-1 Bug #1 helper: consent block 이 routes/billing.py 에서 필수가 됐다.
# 모든 success-path 테스트는 이 블록을 함께 보내야 한다.
_CONSENT = {
    "key_info": True,
    "recurring": True,
    "stripe_overseas": True,
    "consented_at": "2026-05-18T00:00:00Z",
}


@pytest.fixture(autouse=True)
def _registration_complete(monkeypatch):
    """이 모듈의 모든 테스트는 사업자등록 가드를 통과한 뒤의 동작을 검증한다."""
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.setenv("TELESELLER_REGISTRATION_NUMBER", "2026-Seoul-1234")


class TestCreateCheckout:
    def test_unauthenticated_is_blocked(self, client):
        r = client.post("/api/billing/create-checkout", json={"plan": "pro"})
        assert r.status_code == 401

    def test_invalid_plan_returns_400(self, client, auth_user):
        r = client.post(
            "/api/billing/create-checkout",
            json={"plan": "turbo", "consent": _CONSENT},
        )
        assert r.status_code == 400

    def test_missing_price_id_returns_500(self, client, auth_user):
        """STRIPE_PRICE_PRO is empty in tests → route must fail cleanly."""
        r = client.post(
            "/api/billing/create-checkout",
            json={"plan": "pro", "consent": _CONSENT},
        )
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

            r = client.post(
                "/api/billing/create-checkout",
                json={"plan": "pro", "consent": _CONSENT},
            )

        assert r.status_code == 200
        assert r.get_json()["url"].startswith("https://checkout.stripe.com/")

    # ── Wave G-1 Bug #1: consent block required ────────────────────────
    def test_missing_consent_returns_400(self, client, auth_user):
        """Consent 누락 시 400 BILLING_CONSENT_MISSING."""
        with patch("routes.billing.PLAN_PRICES", {"pro": "price_123"}):
            r = client.post(
                "/api/billing/create-checkout",
                json={"plan": "pro"},  # no consent
            )
        assert r.status_code == 400
        assert r.get_json()["code"] == "BILLING_CONSENT_MISSING"

    def test_partial_consent_returns_400(self, client, auth_user):
        """필수 3개 중 하나라도 빠지면 400."""
        partial = {"key_info": True, "recurring": True}  # stripe_overseas 누락
        with patch("routes.billing.PLAN_PRICES", {"pro": "price_123"}):
            r = client.post(
                "/api/billing/create-checkout",
                json={"plan": "pro", "consent": partial},
            )
        assert r.status_code == 400
        assert r.get_json()["code"] == "BILLING_CONSENT_MISSING"

    def test_consent_persists_cross_border_timestamp(self, app, client, auth_user):
        """Bug #1: cross_border_consent_at 이 갱신되어야 PIPA §28-8 audit pass."""
        from extensions import db
        from models import User
        with patch("routes.billing.PLAN_PRICES", {"pro": "price_123"}), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_stripe.Customer.create.return_value = MagicMock(id="cus_x")
            mock_stripe.checkout.Session.create.return_value = MagicMock(
                url="https://checkout.stripe.com/pay/x"
            )
            mock_stripe.StripeError = Exception
            r = client.post(
                "/api/billing/create-checkout",
                json={"plan": "pro", "consent": _CONSENT},
            )
        assert r.status_code == 200
        with app.app_context():
            u = db.session.get(User, auth_user["id"])
            assert u.cross_border_consent_at is not None

    # ── Wave G-1 Bug #3: double-subscribe blocked ──────────────────────
    def test_active_subscription_returns_409(self, app, client, make_user):
        """Active subscription blocks new checkout (409 BILLING_ALREADY_SUBSCRIBED).

        Setup: create user with subscription_status='active' BEFORE login so
        the flask_login session-attached `current_user` reflects active state
        from the first request (no stale-cache games).
        """
        from extensions import db
        from models import User
        user = make_user(email="already-sub@test.com", password="pw12345678")
        with app.app_context():
            db.session.execute(
                User.__table__.update()
                .where(User.id == user["id"])
                .values(subscription_status="active")
            )
            db.session.commit()
        # Now log in — user_loader will SELECT fresh and see 'active'.
        resp = client.post("/api/auth/login", json={
            "email": user["email"],
            "password": user["password"],
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)

        with patch("routes.billing.PLAN_PRICES", {"pro": "price_123"}), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_stripe.Customer.create.return_value = MagicMock(id="cus_x")
            mock_stripe.checkout.Session.create.return_value = MagicMock(
                url="https://checkout.stripe.com/pay/x"
            )
            mock_stripe.StripeError = Exception
            r = client.post(
                "/api/billing/create-checkout",
                json={"plan": "pro", "consent": _CONSENT},
            )
        assert r.status_code == 409, (
            f"expected 409 BILLING_ALREADY_SUBSCRIBED, got "
            f"{r.status_code} {r.get_json()!r}"
        )
        assert r.get_json()["code"] == "BILLING_ALREADY_SUBSCRIBED"


class TestWebhook:
    def test_webhook_without_secret_configured_returns_503(self, raw_client):
        """Webhook endpoint is CSRF-exempt but still requires STRIPE_WEBHOOK_SECRET.

        A missing secret returns 503 (not 500): a transient mis-/un-configuration
        rather than a request-level server crash. 500 would make Stripe retry the
        same delivery for up to 3 days; 503 signals "temporarily unavailable".
        2026-05-20 bug-hunter (P1).
        """
        with patch("routes.billing.STRIPE_WEBHOOK_SECRET", ""):
            r = raw_client.post("/api/billing/webhook", data=b"{}",
                                 headers={"Stripe-Signature": "t=1,v1=xxx"})
        assert r.status_code == 503
        assert r.get_json()["code"] == "STRIPE_WEBHOOK_SECRET_MISSING"

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
