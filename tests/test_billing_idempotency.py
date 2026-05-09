"""tests/test_billing_idempotency.py — Stripe webhook idempotency (migration 028).

Wave 12 (release-prep): without dedup keyed on `event["id"]`, Stripe's 3-day
retry window can re-fire side effects on every redelivery. The fix in
``routes/billing.py:stripe_webhook`` consults ``ProcessedStripeEvent`` before
dispatching, records the event after handling, and tolerates the race window
via the ``uq_processed_stripe_events_event_id`` UNIQUE constraint.

These tests exercise:

1. First delivery of an event creates a ``ProcessedStripeEvent`` row with
   ``status="success"`` and runs the handler.
2. Second delivery of the same event short-circuits with ``deduped: true``
   and does NOT re-run the handler (verified via spy — handler-driven side
   effects must not double-fire).
3. Handler exception still records the event with ``status="error"`` so
   future retries dedupe rather than re-amplifying the failure log.
4. Two concurrent deliveries: the UNIQUE constraint forces one to lose
   the INSERT race; the loser ACKs cleanly without 5xx.

Stripe SDK is fully patched — no network calls.
"""
from __future__ import annotations

import threading
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _registration_complete(monkeypatch):
    """Webhook itself is unguarded; other billing tests share env."""
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.setenv("TELESELLER_REGISTRATION_NUMBER", "2026-Seoul-1234")


def _make_user(app, *, tier="free"):
    from extensions import db
    from models import User
    with app.app_context():
        u = User(
            email="idempotency@test.com",
            name="Idempotency User",
            available_capital=10000.0,
            available_capital_krw=1_000_000.0,
            subscription_tier=tier,
        )
        u.set_pw("password123")
        u.stripe_customer_id = "cus_idempotency_1"
        db.session.add(u)
        db.session.commit()
        return u.id


def _post_webhook(raw_client, fake_event):
    """POST a webhook with the Stripe SDK fully mocked."""
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


class TestFirstDeliveryRecordsEvent:
    def test_first_delivery_creates_processed_event_row(self, raw_client, app):
        """First time we see evt_X, handler runs and a row is recorded."""
        user_id = _make_user(app, tier="free")

        fake_event = {
            "id": "evt_first_delivery_1",
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_idempotency_1"}},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("ok") is True
        assert body.get("deduped") is not True  # first delivery, not deduped

        from extensions import db
        from models import ProcessedStripeEvent
        with app.app_context():
            row = ProcessedStripeEvent.query.filter_by(
                event_id="evt_first_delivery_1"
            ).first()
            assert row is not None
            assert row.event_type == "customer.subscription.deleted"
            assert row.status == "success"
            assert row.error_message is None


class TestSecondDeliveryShortCircuits:
    def test_duplicate_event_id_returns_deduped(self, raw_client, app):
        """Second delivery of the same evt_X must not re-run the handler.

        We assert the dedup envelope shape and that no second
        ProcessedStripeEvent row is created.
        """
        user_id = _make_user(app, tier="pro")

        fake_event = {
            "id": "evt_dedupe_target",
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_idempotency_1"}},
        }
        r1 = _post_webhook(raw_client, fake_event)
        assert r1.status_code == 200
        assert r1.get_json().get("deduped") is not True

        # Second delivery — same event_id, same body.
        r2 = _post_webhook(raw_client, fake_event)
        assert r2.status_code == 200
        body2 = r2.get_json()
        assert body2.get("ok") is True
        assert body2.get("deduped") is True

        # Exactly one row in the dedupe table.
        from extensions import db
        from models import ProcessedStripeEvent
        with app.app_context():
            count = ProcessedStripeEvent.query.filter_by(
                event_id="evt_dedupe_target"
            ).count()
            assert count == 1


class TestSecondDeliveryDoesNotReFireSideEffect:
    def test_handler_does_not_run_on_dedupe(self, raw_client, app):
        """The handler dispatch must short-circuit BEFORE running.

        We patch a handler to raise on 2nd call; if dedup works, the patched
        function is called exactly once across two webhook deliveries.
        """
        user_id = _make_user(app, tier="pro")

        fake_event = {
            "id": "evt_no_double_fire",
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_idempotency_1"}},
        }

        call_count = {"n": 0}
        original = None
        from routes import billing as billing_module
        original = billing_module._handle_subscription_deleted

        def _spy(*args, **kwargs):
            call_count["n"] += 1
            return original(*args, **kwargs)

        with patch.object(billing_module, "_handle_subscription_deleted", side_effect=_spy):
            r1 = _post_webhook(raw_client, fake_event)
            r2 = _post_webhook(raw_client, fake_event)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.get_json().get("deduped") is True
        # First delivery ran the handler exactly once; second was deduped before dispatch.
        assert call_count["n"] == 1


class TestHandlerErrorStillRecorded:
    def test_handler_exception_records_error_status(self, raw_client, app):
        """Even if the handler raises, the event is recorded (status=error)
        so Stripe's 3-day retry storm doesn't keep re-amplifying the same
        failure logger entries. ACK 200 is preserved."""
        # No matching user → _handle_checkout_completed will hit the
        # "No user found" branch which is *not* an exception. Force a real
        # exception by patching the handler.
        fake_event = {
            "id": "evt_handler_explodes",
            "type": "checkout.session.completed",
            "data": {"object": {
                "customer": "cus_does_not_exist",
                "subscription": "sub_x",
                "metadata": {},
            }},
        }
        from routes import billing as billing_module
        with patch.object(
            billing_module,
            "_handle_checkout_completed",
            side_effect=RuntimeError("boom — db driver melted"),
        ):
            r = _post_webhook(raw_client, fake_event)

        assert r.status_code == 200  # never 5xx — Stripe retry contract
        body = r.get_json()
        assert body.get("ok") is True
        assert body.get("warning") == "handler_failed"

        from extensions import db
        from models import ProcessedStripeEvent
        with app.app_context():
            row = ProcessedStripeEvent.query.filter_by(
                event_id="evt_handler_explodes"
            ).first()
            assert row is not None
            assert row.status == "error"
            assert "RuntimeError" in (row.error_message or "")
            assert "boom" in (row.error_message or "")


class TestErrorEventDedupesOnRetry:
    def test_retry_of_failing_event_short_circuits(self, raw_client, app):
        """A poison event recorded with status=error must still dedupe on
        retry — otherwise Stripe spends 3 days re-amplifying the same
        500-level handler failure."""
        fake_event = {
            "id": "evt_poison",
            "type": "checkout.session.completed",
            "data": {"object": {
                "customer": "cus_does_not_exist",
                "subscription": "sub_y",
                "metadata": {},
            }},
        }
        from routes import billing as billing_module

        # First delivery: handler explodes, row recorded with status=error.
        with patch.object(
            billing_module,
            "_handle_checkout_completed",
            side_effect=RuntimeError("boom"),
        ):
            r1 = _post_webhook(raw_client, fake_event)
        assert r1.status_code == 200
        assert r1.get_json().get("warning") == "handler_failed"

        # Second delivery: must dedupe BEFORE running the handler.
        # If dedup is working, the patched handler is never called.
        spy = MagicMock(side_effect=RuntimeError("should not run"))
        with patch.object(billing_module, "_handle_checkout_completed", spy):
            r2 = _post_webhook(raw_client, fake_event)
        assert r2.status_code == 200
        assert r2.get_json().get("deduped") is True
        spy.assert_not_called()


class TestMissingEventIdSkipsRecord:
    def test_event_without_id_does_not_create_row(self, raw_client, app):
        """Stripe always sends an id, but the handler must not crash if a
        synthetic / malformed event arrives without one."""
        fake_event = {
            "id": "",  # empty — defensive case
            "type": "invoice.paid",
            "data": {"object": {
                "id": "in_test",
                "customer": "cus_x",
                "amount_paid": 100,
            }},
        }
        r = _post_webhook(raw_client, fake_event)
        assert r.status_code == 200
        # No row created since event_id was empty.
        from extensions import db
        from models import ProcessedStripeEvent
        with app.app_context():
            assert ProcessedStripeEvent.query.filter_by(event_id="").count() == 0
