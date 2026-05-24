"""tests/test_billing_refund_dispute.py — refund / chargeback observability.

Covers the silent-drop gap closed in routes/billing.py: Stripe
``charge.refunded`` / ``charge.dispute.created`` /
``charge.dispute.funds_withdrawn`` events previously hit no dispatch
branch and were recorded as "processed" with zero signal — a refunded /
disputed customer kept paid access and nobody was notified.

Tier-downgrade policy (CEO-authorized 2026-05-22) now IMPLEMENTED:
  • charge.refunded FULL (amount_refunded >= amount, or refunded==true) →
    downgrade tier=free + status=canceled.
  • charge.refunded PARTIAL (or amount unknown → safer default keep) →
    tier unchanged.
  • charge.dispute.created → tier unchanged (may be won).
  • charge.dispute.funds_withdrawn (lost) → downgrade tier=free.
The contract pinned here in all cases:
  (a) handler ACKs 200 (never 500),
  (b) a WARNING is logged (caplog) AND the ops Slack alert is fired.

Test strategy mirrors test_billing_payment_failed.py: mock
``stripe.Webhook.construct_event`` to feed synthetic events, and patch the
in-module Slack notifier to assert wiring without a network call.
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _registration_complete(monkeypatch):
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.setenv("TELESELLER_REGISTRATION_NUMBER", "2026-Seoul-1234")


def _make_user(app, *, tier="premium", status="active"):
    from extensions import db
    from models import User
    with app.app_context():
        u = User(
            email="refund@test.com",
            name="Refund Test",
            available_capital=10000.0,
            available_capital_krw=1_000_000.0,
            subscription_tier=tier,
        )
        u.set_pw("password123")
        u.stripe_customer_id = "cus_rf_test"
        u.stripe_subscription_id = "sub_rf_test"
        u.subscription_status = status
        db.session.add(u)
        db.session.commit()
        return u.id


def _post_event(raw_client, event, *, charge_customer=None):
    with patch("routes.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
         patch("routes.billing.stripe") as mock_stripe:
        mock_stripe.SignatureVerificationError = type(
            "SigErr", (Exception,), {}
        )
        mock_stripe.StripeError = type("StripeErr", (Exception,), {})
        # Real Stripe dispute objects carry no top-level `customer`; the
        # handler recovers it via stripe.Charge.retrieve(charge).customer.
        mock_stripe.Charge.retrieve.return_value = (
            {"customer": charge_customer} if charge_customer else {}
        )
        mock_stripe.Webhook.construct_event.return_value = event
        return raw_client.post(
            "/api/billing/webhook",
            data=b"{}",
            headers={"Stripe-Signature": "t=1,v1=ok"},
        )


def _assert_tier_unchanged(app, user_id, *, tier, status):
    from extensions import db
    from models import User
    with app.app_context():
        u = db.session.get(User, user_id)
        assert u.subscription_tier == tier
        assert u.subscription_status == status


def _assert_downgraded(app, user_id):
    from extensions import db
    from models import User
    with app.app_context():
        u = db.session.get(User, user_id)
        assert u.subscription_tier == "free"
        assert u.subscription_status == "canceled"


class TestChargeRefunded:
    def test_full_refund_downgrades_to_free(self, raw_client, app, caplog):
        """FULL refund (amount_refunded == amount) → tier becomes free."""
        user_id = _make_user(app, tier="premium", status="active")
        event = {
            "id": "evt_rf_1",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_1",
                "payment_intent": "pi_rf_1",
                "customer": "cus_rf_test",
                "amount": 19_900,
                "amount_refunded": 19_900,
                "currency": "krw",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack", return_value=True,
        ) as mock_alert, caplog.at_level(logging.WARNING, logger="routes.billing"):
            r = _post_event(raw_client, event)

        # (a) never 500
        assert r.status_code == 200
        assert r.get_json().get("ok") is True
        # (b) WARNING logged + ops alert fired
        assert any(
            "REFUND received (full=True)" in rec.message
            for rec in caplog.records
        )
        assert mock_alert.call_count == 1
        assert mock_alert.call_args.kwargs["kind"] == "REFUND"
        # (c) FULL refund → downgraded to free
        _assert_downgraded(app, user_id)

    def test_full_refund_via_refunded_flag_downgrades(self, raw_client, app):
        """`refunded: true` is authoritative → FULL → downgrade."""
        user_id = _make_user(app, tier="pro", status="active")
        event = {
            "id": "evt_rf_flag",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_flag", "payment_intent": "pi_flag",
                "customer": "cus_rf_test", "refunded": True,
                "amount": 9_900, "amount_refunded": 9_900, "currency": "krw",
            }},
        }
        with patch("routes.billing._notify_refund_dispute_slack", return_value=True):
            r = _post_event(raw_client, event)
        assert r.status_code == 200
        _assert_downgraded(app, user_id)

    def test_partial_refund_keeps_tier(self, raw_client, app, caplog):
        """PARTIAL refund (amount_refunded < amount) → tier unchanged, alert fired."""
        user_id = _make_user(app, tier="premium", status="active")
        event = {
            "id": "evt_rf_partial",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_p", "payment_intent": "pi_p",
                "customer": "cus_rf_test",
                "amount": 19_900, "amount_refunded": 5_000, "currency": "krw",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack", return_value=True,
        ) as mock_alert, caplog.at_level(logging.WARNING, logger="routes.billing"):
            r = _post_event(raw_client, event)
        assert r.status_code == 200
        assert any(
            "REFUND received (full=False)" in rec.message
            for rec in caplog.records
        )
        assert mock_alert.call_count == 1  # alert still fired
        # tier preserved
        _assert_tier_unchanged(app, user_id, tier="premium", status="active")

    def test_amount_missing_defaults_to_keep_access(self, raw_client, app):
        """No `amount` → can't prove FULL → SAFER default = keep access."""
        user_id = _make_user(app, tier="premium", status="active")
        event = {
            "id": "evt_rf_noamt",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_na", "payment_intent": "pi_na",
                "customer": "cus_rf_test",
                "amount_refunded": 19_900, "currency": "krw",
            }},
        }
        with patch("routes.billing._notify_refund_dispute_slack", return_value=True):
            r = _post_event(raw_client, event)
        assert r.status_code == 200
        _assert_tier_unchanged(app, user_id, tier="premium", status="active")

    def test_refund_unknown_customer_full_still_acks(self, raw_client, app, caplog):
        """FULL refund but no user row → still log + alert, never raise/crash."""
        event = {
            "id": "evt_rf_unknown",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_x", "payment_intent": "pi_x",
                "customer": "cus_no_match",
                "amount": 9_900, "amount_refunded": 9_900,
                "currency": "krw",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack", return_value=False,
        ) as mock_alert, caplog.at_level(logging.WARNING, logger="routes.billing"):
            r = _post_event(raw_client, event)
        assert r.status_code == 200
        assert mock_alert.call_count == 1
        assert any("user=unknown" in rec.message for rec in caplog.records)

    def test_refund_acks_even_when_alert_raises(self, raw_client, app):
        """If the Slack notifier raises, the webhook must still ACK 200."""
        _make_user(app)
        event = {
            "id": "evt_rf_raise",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_r", "payment_intent": "pi_r",
                "customer": "cus_rf_test", "amount_refunded": 9_900,
                "currency": "krw",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack",
            side_effect=RuntimeError("slack down"),
        ):
            r = _post_event(raw_client, event)
        # Handler error is caught by the never-500 wrapper → still 200.
        assert r.status_code == 200
        assert r.get_json().get("ok") is True


class TestChargeDispute:
    def test_dispute_created_acks_warns_and_alerts(self, raw_client, app, caplog):
        user_id = _make_user(app, tier="pro", status="active")
        event = {
            "id": "evt_dp_1",
            "type": "charge.dispute.created",
            "data": {"object": {
                "id": "dp_1",
                "charge": "ch_dp_1",
                "payment_intent": "pi_dp_1",
                "amount": 9_900,
                "currency": "krw",
                "reason": "fraudulent",
                "status": "needs_response",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack", return_value=True,
        ) as mock_alert, caplog.at_level(logging.WARNING, logger="routes.billing"):
            r = _post_event(raw_client, event, charge_customer="cus_rf_test")

        assert r.status_code == 200
        assert any(
            "DISPUTE (created)" in rec.message for rec in caplog.records
        )
        assert mock_alert.call_count == 1
        assert mock_alert.call_args.kwargs["kind"] == "DISPUTE (created)"
        # tier untouched — dispute may later be won
        _assert_tier_unchanged(app, user_id, tier="pro", status="active")

    def test_dispute_funds_withdrawn_downgrades_to_free(self, raw_client, app, caplog):
        """Dispute lost / funds pulled → downgrade tier to free."""
        user_id = _make_user(app, tier="premium", status="active")
        event = {
            "id": "evt_dp_fw",
            "type": "charge.dispute.funds_withdrawn",
            "data": {"object": {
                "id": "dp_fw", "charge": "ch_fw", "payment_intent": "pi_fw",
                "amount": 19_900, "currency": "krw",
                "reason": "product_not_received", "status": "lost",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack", return_value=True,
        ) as mock_alert, caplog.at_level(logging.WARNING, logger="routes.billing"):
            r = _post_event(raw_client, event, charge_customer="cus_rf_test")

        assert r.status_code == 200
        assert mock_alert.call_args.kwargs["kind"] == "DISPUTE (funds_withdrawn)"
        assert any(
            "DISPUTE (funds_withdrawn)" in rec.message for rec in caplog.records
        )
        _assert_downgraded(app, user_id)


class TestRefundDisputeSlackNotifierUnit:
    """routes.billing._notify_refund_dispute_slack — unit."""

    def test_skipped_when_webhook_url_unset(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        from routes.billing import _notify_refund_dispute_slack
        assert _notify_refund_dispute_slack(kind="REFUND", summary="x") is False

    def test_posts_when_configured(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        with patch("requests.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None
            from routes.billing import _notify_refund_dispute_slack
            ok = _notify_refund_dispute_slack(kind="REFUND", summary="• y")
        assert ok is True
        assert mock_post.call_count == 1
        text = mock_post.call_args.kwargs["json"]["text"]
        assert "MANUAL ACTION REQUIRED" in text
        assert "전자상거래법 §17" in text

    def test_swallows_exception(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        with patch("requests.post", side_effect=RuntimeError("boom")):
            from routes.billing import _notify_refund_dispute_slack
            assert _notify_refund_dispute_slack(kind="REFUND", summary="z") is False
