"""tests/test_billing_refund_dispute.py — refund / chargeback observability.

Covers the silent-drop gap closed in routes/billing.py: Stripe
``charge.refunded`` / ``charge.dispute.created`` /
``charge.dispute.funds_withdrawn`` events previously hit no dispatch
branch and were recorded as "processed" with zero signal — a refunded /
disputed customer kept paid access and nobody was notified.

These handlers are **observability-only** (tier change is a DEFERRED CEO +
legal / 전자상거래법 §17 decision). The contract pinned here:
  (a) handler ACKs 200 (never 500),
  (b) a WARNING is logged (caplog) AND the ops Slack alert is fired,
  (c) NO subscription_tier / subscription_status change on the user.

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


def _post_event(raw_client, event):
    with patch("routes.billing.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
         patch("routes.billing.stripe") as mock_stripe:
        mock_stripe.SignatureVerificationError = type(
            "SigErr", (Exception,), {}
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


class TestChargeRefunded:
    def test_refund_acks_200_warns_and_alerts(self, raw_client, app, caplog):
        user_id = _make_user(app, tier="premium", status="active")
        event = {
            "id": "evt_rf_1",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_1",
                "payment_intent": "pi_rf_1",
                "customer": "cus_rf_test",
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
            "REFUND received" in rec.message and "MANUAL ACTION REQUIRED" in rec.message
            for rec in caplog.records
        )
        assert mock_alert.call_count == 1
        assert mock_alert.call_args.kwargs["kind"] == "REFUND"
        # (c) tier untouched
        _assert_tier_unchanged(app, user_id, tier="premium", status="active")

    def test_refund_unknown_customer_still_acks(self, raw_client, app, caplog):
        """No user row → still log + alert, never raise."""
        event = {
            "id": "evt_rf_unknown",
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_rf_x", "payment_intent": "pi_x",
                "customer": "cus_no_match", "amount_refunded": 9_900,
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
                "customer": "cus_rf_test",
                "amount": 9_900,
                "currency": "krw",
                "reason": "fraudulent",
                "status": "needs_response",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack", return_value=True,
        ) as mock_alert, caplog.at_level(logging.WARNING, logger="routes.billing"):
            r = _post_event(raw_client, event)

        assert r.status_code == 200
        assert any(
            "DISPUTE (created)" in rec.message and "MANUAL ACTION REQUIRED" in rec.message
            for rec in caplog.records
        )
        assert mock_alert.call_count == 1
        assert mock_alert.call_args.kwargs["kind"] == "DISPUTE (created)"
        # tier untouched — dispute may later be won
        _assert_tier_unchanged(app, user_id, tier="pro", status="active")

    def test_dispute_funds_withdrawn_routes_to_handler(self, raw_client, app, caplog):
        user_id = _make_user(app, tier="premium", status="active")
        event = {
            "id": "evt_dp_fw",
            "type": "charge.dispute.funds_withdrawn",
            "data": {"object": {
                "id": "dp_fw", "charge": "ch_fw", "payment_intent": "pi_fw",
                "customer": "cus_rf_test", "amount": 19_900, "currency": "krw",
                "reason": "product_not_received", "status": "under_review",
            }},
        }
        with patch(
            "routes.billing._notify_refund_dispute_slack", return_value=True,
        ) as mock_alert, caplog.at_level(logging.WARNING, logger="routes.billing"):
            r = _post_event(raw_client, event)

        assert r.status_code == 200
        assert mock_alert.call_args.kwargs["kind"] == "DISPUTE (funds_withdrawn)"
        assert any(
            "DISPUTE (funds_withdrawn)" in rec.message for rec in caplog.records
        )
        _assert_tier_unchanged(app, user_id, tier="premium", status="active")


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
