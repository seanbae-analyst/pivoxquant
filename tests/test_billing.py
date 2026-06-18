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

    # ── Bug #1: highest-tier (env grant) blocked from checkout ──────────
    def test_founding_lifetime_user_returns_409_already_entitled(
        self, app, client, make_user, monkeypatch
    ):
        """founding_lifetime (DEV_FOUNDING_EMAILS grant, status='inactive')
        must NOT be able to start a paid checkout. The old status-only guard
        let them through → checkout.session.completed would overwrite their
        lifetime tier with pro/premium + active and start monthly billing.
        """
        from extensions import db
        from models import User
        email = "founder@test.com"
        user = make_user(email=email, password="pw12345678")
        # founding_lifetime grant via env (status stays inactive).
        monkeypatch.setenv("DEV_FOUNDING_EMAILS", email)
        with app.app_context():
            db.session.execute(
                User.__table__.update()
                .where(User.id == user["id"])
                .values(subscription_status="inactive", subscription_tier="free")
            )
            db.session.commit()
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
            f"expected 409 BILLING_ALREADY_ENTITLED, got "
            f"{r.status_code} {r.get_json()!r}"
        )
        assert r.get_json()["code"] == "BILLING_ALREADY_ENTITLED"
        # Stripe must never have been touched.
        mock_stripe.checkout.Session.create.assert_not_called()

    def test_plain_free_user_can_still_checkout(self, client, auth_user):
        """Regression guard: the new entitlement gate must NOT block ordinary
        free users — they reach the Stripe checkout flow as before.
        """
        with patch("routes.billing.PLAN_PRICES", {"pro": "price_123"}), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_stripe.Customer.create.return_value = MagicMock(id="cus_free")
            mock_stripe.checkout.Session.create.return_value = MagicMock(
                url="https://checkout.stripe.com/pay/free"
            )
            mock_stripe.StripeError = Exception
            r = client.post(
                "/api/billing/create-checkout",
                json={"plan": "pro", "consent": _CONSENT},
            )
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["url"].startswith("https://checkout.stripe.com/")


class TestDowngradeToFree:
    """Bug #3: full refund downgrade must clear stripe_subscription_id."""

    def test_downgrade_clears_stripe_subscription_id(self, app, make_user):
        from extensions import db
        from models import User
        from routes.billing import _downgrade_user_to_free
        user = make_user(email="refunded@test.com", password="pw12345678")
        with app.app_context():
            db.session.execute(
                User.__table__.update()
                .where(User.id == user["id"])
                .values(
                    subscription_tier="pro",
                    subscription_status="active",
                    stripe_subscription_id="sub_live_123",
                )
            )
            db.session.commit()
            u = db.session.get(User, user["id"])
            _downgrade_user_to_free(u, reason="full_refund")
            refreshed = db.session.get(User, user["id"])
            assert refreshed.subscription_tier == "free"
            assert refreshed.subscription_status == "canceled"
            # The fix: stripe_subscription_id must be cleared so
            # get_subscription does not surface a future period_end.
            assert refreshed.stripe_subscription_id is None

    def test_get_subscription_no_period_end_after_refund(
        self, app, client, make_user
    ):
        """After a full-refund downgrade, get_subscription must NOT call
        Stripe.Subscription.retrieve nor expose current_period_end.
        """
        from extensions import db
        from models import User
        from routes.billing import _downgrade_user_to_free
        user = make_user(email="refunded2@test.com", password="pw12345678")
        with app.app_context():
            db.session.execute(
                User.__table__.update()
                .where(User.id == user["id"])
                .values(
                    subscription_tier="pro",
                    subscription_status="active",
                    stripe_subscription_id="sub_live_456",
                )
            )
            db.session.commit()
            u = db.session.get(User, user["id"])
            _downgrade_user_to_free(u, reason="full_refund")

        resp = client.post("/api/auth/login", json={
            "email": user["email"],
            "password": user["password"],
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)

        with patch("routes.billing.stripe") as mock_stripe:
            mock_stripe.StripeError = Exception
            r = client.get("/api/billing/subscription")
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert "current_period_end" not in body
        mock_stripe.Subscription.retrieve.assert_not_called()


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


# ── _subscription_period_end — Stripe API ≥2025-03-31 items relocation ──────

class TestSubscriptionPeriodEnd:
    """Stripe API 2025-03-31 moved current_period_end onto subscription ITEMS;
    the pinned SDK (15.x) returns no top-level key, so the old direct read
    rendered a blank renews/cancels date for every paying user. The helper
    must read items.data[0] first and keep the top-level key as a fallback
    for older pinned API versions."""

    def test_reads_from_items_first(self):
        from routes.billing import _subscription_period_end
        sub = {
            "items": {"data": [{"current_period_end": 1767225600}]},
            # top-level absent — the post-2025-03-31 shape
        }
        assert _subscription_period_end(sub) == 1767225600

    def test_falls_back_to_top_level_for_old_api_versions(self):
        from routes.billing import _subscription_period_end
        sub = {"items": {"data": []}, "current_period_end": 1735689600}
        assert _subscription_period_end(sub) == 1735689600

    def test_items_wins_over_top_level_when_both_present(self):
        from routes.billing import _subscription_period_end
        sub = {
            "items": {"data": [{"current_period_end": 222}]},
            "current_period_end": 111,
        }
        assert _subscription_period_end(sub) == 222

    def test_returns_none_when_absent_everywhere(self):
        from routes.billing import _subscription_period_end
        assert _subscription_period_end({"items": {"data": [{}]}}) is None
        assert _subscription_period_end({}) is None
