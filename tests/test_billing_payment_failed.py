"""tests/test_billing_payment_failed.py — Stripe payment-failed side-effects.

Covers the 2026-05-19 S2 + C-CS1 wiring: the
``invoice.payment_failed`` handler must (a) fire a Slack alert + (b)
dispatch a transactional email — both fire-and-forget, never raising
through the webhook ACK path.

Test strategy
-------------
- Mock ``stripe.Webhook.construct_event`` so we feed synthetic events
  without a real network call (mirrors test_billing_webhook.py).
- Patch the two notification entry-points
  (``notify_payment_failed_slack`` / ``notify_payment_failed_email``)
  to assert call args + return value. The provider cascade itself is
  exercised separately in unit tests on the helper module — here we
  only verify the wiring.
- Pin the contract that the handler MUST 200 even when both
  notifications throw (idempotency + Stripe retry resilience).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _registration_complete(monkeypatch):
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.setenv("TELESELLER_REGISTRATION_NUMBER", "2026-Seoul-1234")


def _make_user_with_sub(app, *, tier="pro", status="active"):
    from extensions import db
    from models import User
    with app.app_context():
        u = User(
            email="failed@test.com",
            name="Failed Test",
            available_capital=10000.0,
            available_capital_krw=1_000_000.0,
            subscription_tier=tier,
        )
        u.set_pw("password123")
        u.stripe_customer_id = "cus_pf_test"
        u.stripe_subscription_id = "sub_pf_test"
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


class TestPaymentFailedNotifications:
    def test_payment_failed_triggers_slack_and_email(self, raw_client, app):
        """Both notification helpers must be called with user + invoice."""
        user_id = _make_user_with_sub(app)

        invoice = {
            "id": "in_pf_1",
            "customer": "cus_pf_test",
            "attempt_count": 1,
            "amount_due": 9_900,
            "currency": "krw",
            "livemode": False,
        }
        event = {
            "id": "evt_pf_1",
            "type": "invoice.payment_failed",
            "data": {"object": invoice},
        }

        with patch(
            "services.billing_notifications.notify_payment_failed_slack"
        ) as mock_slack, patch(
            "services.billing_notifications.notify_payment_failed_email"
        ) as mock_email:
            mock_slack.return_value = True
            mock_email.return_value = True
            r = _post_event(raw_client, event)

        assert r.status_code == 200
        assert r.get_json().get("ok") is True

        # Both helpers called exactly once
        assert mock_slack.call_count == 1
        assert mock_email.call_count == 1

        # Invoice payload forwarded verbatim
        slack_kw = mock_slack.call_args.kwargs
        assert slack_kw["invoice"]["id"] == "in_pf_1"
        assert slack_kw["user"].id == user_id

        email_kw = mock_email.call_args.kwargs
        assert email_kw["invoice"]["id"] == "in_pf_1"
        assert email_kw["user"].id == user_id

    def test_payment_failed_keeps_tier_active(self, raw_client, app):
        """Per docstring contract — tier intentionally not flipped."""
        user_id = _make_user_with_sub(app, tier="pro", status="active")

        event = {
            "id": "evt_pf_tier",
            "type": "invoice.payment_failed",
            "data": {"object": {
                "id": "in_pf_tier", "customer": "cus_pf_test",
                "attempt_count": 2, "amount_due": 9_900, "currency": "krw",
            }},
        }
        with patch(
            "services.billing_notifications.notify_payment_failed_slack",
            return_value=True,
        ), patch(
            "services.billing_notifications.notify_payment_failed_email",
            return_value=True,
        ):
            r = _post_event(raw_client, event)
        assert r.status_code == 200

        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.subscription_tier == "pro"
            assert u.subscription_status == "active"

    def test_payment_failed_ack_even_when_notifications_raise(
        self, raw_client, app,
    ):
        """If Slack/email helpers raise, handler must still ACK 200 —
        Stripe retries non-2xx for 3 days, which would amplify the bug
        + spam logs. Idempotency record must also be written."""
        _make_user_with_sub(app)

        event = {
            "id": "evt_pf_raises",
            "type": "invoice.payment_failed",
            "data": {"object": {
                "id": "in_pf_raises", "customer": "cus_pf_test",
                "attempt_count": 1, "amount_due": 9_900, "currency": "krw",
            }},
        }
        with patch(
            "services.billing_notifications.notify_payment_failed_slack",
            side_effect=RuntimeError("slack down"),
        ), patch(
            "services.billing_notifications.notify_payment_failed_email",
            side_effect=RuntimeError("provider 500"),
        ):
            r = _post_event(raw_client, event)
        # Webhook MUST ACK regardless of side-effect failure.
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

    def test_payment_failed_unknown_customer_skips_email(
        self, raw_client, app,
    ):
        """No user row → email helper sees user=None and returns False
        without raising. Slack still fires (CEO-side ops alert)."""
        event = {
            "id": "evt_pf_unknown",
            "type": "invoice.payment_failed",
            "data": {"object": {
                "id": "in_pf_unknown", "customer": "cus_no_match",
                "attempt_count": 1, "amount_due": 9_900, "currency": "krw",
            }},
        }
        with patch(
            "services.billing_notifications.notify_payment_failed_slack",
            return_value=True,
        ) as mock_slack, patch(
            "services.billing_notifications.notify_payment_failed_email",
            return_value=False,
        ) as mock_email:
            r = _post_event(raw_client, event)
        assert r.status_code == 200
        # Both still invoked — they handle None user internally
        assert mock_slack.call_count == 1
        assert mock_email.call_count == 1
        # user kwarg is None when customer not found
        assert mock_slack.call_args.kwargs["user"] is None
        assert mock_email.call_args.kwargs["user"] is None


class TestSlackNotifierUnit:
    """services.billing_notifications.notify_payment_failed_slack — unit."""

    def test_slack_skipped_when_webhook_url_unset(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        from services.billing_notifications import notify_payment_failed_slack
        result = notify_payment_failed_slack(
            user=None,
            invoice={"id": "in_x", "customer": "cus_x", "attempt_count": 1},
        )
        assert result is False

    def test_slack_post_called_when_configured(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        with patch("requests.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None

            from services.billing_notifications import (
                notify_payment_failed_slack,
            )
            invoice = {
                "id": "in_y",
                "customer": "cus_y",
                "attempt_count": 1,
                "amount_due": 9_900,
                "currency": "krw",
                "livemode": True,
            }

            class _U:
                id = 42
                email = "x@y.com"

            ok = notify_payment_failed_slack(user=_U(), invoice=invoice)
        assert ok is True
        assert mock_post.call_count == 1
        # Live mode → dashboard URL must not contain /test
        payload_text = mock_post.call_args.kwargs["json"]["text"]
        assert "dashboard.stripe.com/invoices/in_y" in payload_text
        assert "/test/" not in payload_text
        assert "₩9,900" in payload_text

    def test_slack_test_mode_dashboard_url(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        with patch("requests.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None
            from services.billing_notifications import (
                notify_payment_failed_slack,
            )
            invoice = {
                "id": "in_test", "customer": "cus_test", "attempt_count": 1,
                "amount_due": 990, "currency": "usd", "livemode": False,
            }

            class _U:
                id = 7
                email = "a@b.com"
            notify_payment_failed_slack(user=_U(), invoice=invoice)
        payload_text = mock_post.call_args.kwargs["json"]["text"]
        assert "dashboard.stripe.com/test/invoices/in_test" in payload_text
        assert "$9.90" in payload_text

    def test_slack_swallows_exception(self, monkeypatch):
        """Network failures must return False, never raise."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        with patch("requests.post", side_effect=RuntimeError("boom")):
            from services.billing_notifications import (
                notify_payment_failed_slack,
            )
            result = notify_payment_failed_slack(
                user=None,
                invoice={"id": "in_z", "customer": "cus_z",
                         "attempt_count": 1, "amount_due": 0,
                         "currency": "krw"},
            )
        assert result is False


class TestEmailNotifierUnit:
    """services.billing_notifications.notify_payment_failed_email — unit."""

    def test_email_skipped_when_user_is_none(self):
        from services.billing_notifications import notify_payment_failed_email
        assert notify_payment_failed_email(user=None, invoice={}) is False

    def test_email_skipped_when_no_provider_configured(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("BREVO_API_KEY", raising=False)
        monkeypatch.delenv("SENDINBLUE_API_KEY", raising=False)

        class _U:
            id = 1
            email = "x@y.com"
            name = "X"

        from services.billing_notifications import notify_payment_failed_email
        ok = notify_payment_failed_email(
            user=_U(),
            invoice={"id": "in_a", "amount_due": 9_900, "currency": "krw",
                     "attempt_count": 1},
        )
        assert ok is False

    def test_email_uses_sendgrid_first_with_consent_bypass(self, monkeypatch):
        """SendGrid path must be called with honour_consent=False
        (transactional carve-out)."""
        monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake")

        with patch(
            "services.email.sendgrid_provider.send", return_value=True,
        ) as mock_sg:
            from services.billing_notifications import (
                notify_payment_failed_email,
            )

            class _U:
                id = 99
                email = "z@y.com"
                name = "Z"
            ok = notify_payment_failed_email(
                user=_U(),
                invoice={"id": "in_e", "amount_due": 19_900,
                         "currency": "krw", "attempt_count": 1},
            )

        assert ok is True
        assert mock_sg.call_count == 1
        # transactional: honour_consent must be False
        assert mock_sg.call_args.kwargs["honour_consent"] is False
        # Brand tag for cost-monitor bucketing (SendGrid uses ``categories``)
        assert "payment_failed" in mock_sg.call_args.kwargs["categories"]

    def test_email_falls_back_to_brevo_when_sendgrid_fails(
        self, monkeypatch,
    ):
        monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake")
        monkeypatch.setenv("BREVO_API_KEY", "brevo-fake")

        with patch(
            "services.email.sendgrid_provider.send",
            side_effect=RuntimeError("SG down"),
        ), patch(
            "services.email.brevo_provider.send", return_value=True,
        ) as mock_brevo:
            from services.billing_notifications import (
                notify_payment_failed_email,
            )

            class _U:
                id = 100
                email = "fallback@y.com"
                name = "FB"
            ok = notify_payment_failed_email(
                user=_U(),
                invoice={"id": "in_f", "amount_due": 9_900,
                         "currency": "krw", "attempt_count": 1},
            )

        assert ok is True
        assert mock_brevo.call_count == 1
        assert mock_brevo.call_args.kwargs["honour_consent"] is False
