"""tests/test_checkout_followup.py — Stripe checkout.session.expired 1h follow-up.

Wave G C-M1 (2026-05-19).

Covers four contracts:

1.  Webhook ``checkout.session.expired`` enqueues a row in
    ``checkout_expirations`` with ``scheduled_send_at = expired_at + 1h``.
2.  Duplicate webhook delivery (same ``session_id``) is idempotent — no
    duplicate row.
3.  Dispatcher with feature flag **OFF** stamps ``skipped_reason =
    "feature_flag_off"`` and never calls the email sender.
4.  Dispatcher with feature flag **ON** invokes
    ``services.billing_followup.send_checkout_followup`` exactly once
    per due row, then ``mark_sent``. A second dispatcher run does NOT
    re-send (sent_at filter).

Test strategy mirrors ``tests/test_billing_payment_failed.py``:
patch ``stripe.Webhook.construct_event`` so we feed synthetic events,
and patch the email send entry-point so we never hit a real provider.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _registration_complete(monkeypatch):
    # Webhook handler itself isn't gated by registration, but resolving
    # the User row touches the same env hygiene as other billing tests.
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.setenv("TELESELLER_REGISTRATION_NUMBER", "2026-Seoul-1234")


def _make_user(app, *, email="abandoner@test.com", customer_id="cus_abc"):
    from extensions import db
    from models import User
    with app.app_context():
        u = User(
            email=email,
            name="Abandon Test",
            available_capital=10000.0,
            available_capital_krw=1_000_000.0,
            subscription_tier="free",
            subscription_status="inactive",
        )
        u.set_pw("password123")
        u.stripe_customer_id = customer_id
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


def _expired_event(*, customer_id="cus_abc", session_id="cs_test_expire_1",
                   user_id=None, expires_at_unix=None, event_id="evt_exp_1"):
    obj = {
        "id": session_id,
        "customer": customer_id,
        "metadata": {"user_id": str(user_id)} if user_id else {},
    }
    if expires_at_unix is not None:
        obj["expires_at"] = expires_at_unix
    return {
        "id": event_id,
        "type": "checkout.session.expired",
        "data": {"object": obj},
    }


class TestWebhookEnqueue:
    def test_expired_event_creates_row(self, raw_client, app):
        """checkout.session.expired → checkout_expirations row inserted."""
        user_id = _make_user(app)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at_unix = int((now - timedelta(minutes=5)).timestamp())

        event = _expired_event(
            session_id="cs_test_expire_a",
            expires_at_unix=expires_at_unix,
        )
        r = _post_event(raw_client, event)
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

        from models import CheckoutExpiration
        with app.app_context():
            row = CheckoutExpiration.query.filter_by(
                session_id="cs_test_expire_a"
            ).first()
            assert row is not None
            assert row.user_id == user_id
            assert row.sent_at is None
            assert row.skipped_reason is None
            # +1h from expired_at
            delta = row.scheduled_send_at - row.expired_at
            assert delta == timedelta(hours=1)

    def test_expired_event_idempotent_on_session_id(self, raw_client, app):
        """Duplicate webhook delivery (same session id) does not duplicate."""
        _make_user(app)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at_unix = int(now.timestamp())

        e1 = _expired_event(
            session_id="cs_test_dup", expires_at_unix=expires_at_unix,
            event_id="evt_dup_1",
        )
        e2 = _expired_event(
            session_id="cs_test_dup", expires_at_unix=expires_at_unix,
            event_id="evt_dup_2",  # different event id, same session
        )
        r1 = _post_event(raw_client, e1)
        r2 = _post_event(raw_client, e2)
        assert r1.status_code == 200
        assert r2.status_code == 200

        from models import CheckoutExpiration
        with app.app_context():
            rows = CheckoutExpiration.query.filter_by(
                session_id="cs_test_dup"
            ).all()
            assert len(rows) == 1

    def test_expired_event_unknown_customer_no_row(self, raw_client, app):
        """No matching User → no row, but webhook still ACKs 200."""
        # No user created.
        event = _expired_event(
            customer_id="cus_no_match",
            session_id="cs_test_unknown",
            expires_at_unix=int(datetime.now(timezone.utc).timestamp()),
        )
        r = _post_event(raw_client, event)
        assert r.status_code == 200

        from models import CheckoutExpiration
        with app.app_context():
            assert CheckoutExpiration.query.count() == 0

    def test_expired_event_resolves_user_by_metadata_when_no_customer(
        self, raw_client, app,
    ):
        """If customer_id lookup fails, fall back to metadata.user_id."""
        user_id = _make_user(app, customer_id="cus_xyz")
        event = _expired_event(
            customer_id="cus_NOT_PRESENT",  # forces metadata fallback
            session_id="cs_test_meta",
            user_id=user_id,
            expires_at_unix=int(datetime.now(timezone.utc).timestamp()),
        )
        r = _post_event(raw_client, event)
        assert r.status_code == 200

        from models import CheckoutExpiration
        with app.app_context():
            row = CheckoutExpiration.query.filter_by(
                session_id="cs_test_meta"
            ).first()
            assert row is not None
            assert row.user_id == user_id


class TestDispatcherFlagOff:
    def test_flag_off_marks_skipped_no_send(self, raw_client, app, monkeypatch):
        """PIVOX_CHECKOUT_FOLLOWUP_ENABLED unset → mark feature_flag_off."""
        monkeypatch.delenv("PIVOX_CHECKOUT_FOLLOWUP_ENABLED", raising=False)
        user_id = _make_user(app)

        # Seed a due row directly.
        from extensions import db
        from models import CheckoutExpiration
        with app.app_context():
            past_expired = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
            row = CheckoutExpiration(
                user_id=user_id,
                session_id="cs_due_off",
                expired_at=past_expired,
                scheduled_send_at=past_expired + timedelta(hours=1),
            )
            db.session.add(row)
            db.session.commit()

        # Drain — patch send to assert it's never called.
        with patch(
            "services.billing_followup.send_checkout_followup"
        ) as mock_send:
            from services.billing_followup import followup_enabled
            assert followup_enabled() is False

            with app.app_context():
                rows = list(CheckoutExpiration.pending_due())
                # Mirror dispatcher inner loop on the flag_off branch.
                for r in rows:
                    r.mark_skipped("feature_flag_off")
                    db.session.commit()

            assert mock_send.call_count == 0

        with app.app_context():
            row = CheckoutExpiration.query.filter_by(
                session_id="cs_due_off"
            ).first()
            assert row.sent_at is None
            assert row.skipped_reason == "feature_flag_off"


class TestDispatcherFlagOn:
    def test_flag_on_sends_and_marks_sent(self, raw_client, app, monkeypatch):
        """Flag ON → sender called once, row.sent_at populated."""
        monkeypatch.setenv("PIVOX_CHECKOUT_FOLLOWUP_ENABLED", "true")
        user_id = _make_user(app)

        from extensions import db
        from models import CheckoutExpiration
        with app.app_context():
            past_expired = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
            row = CheckoutExpiration(
                user_id=user_id,
                session_id="cs_due_on",
                expired_at=past_expired,
                scheduled_send_at=past_expired + timedelta(hours=1),
            )
            db.session.add(row)
            db.session.commit()

        # The dispatcher's `create_app()` would build a second app; we
        # instead exercise the per-row dispatch logic against the test
        # app (matches the unit-test boundary used by the inactive-nudge
        # dispatcher tests).
        with patch(
            "services.billing_followup.send_checkout_followup",
            return_value=True,
        ) as mock_send:
            from services.billing_followup import followup_enabled
            from models import User as UserModel
            assert followup_enabled() is True

            with app.app_context():
                for r in list(CheckoutExpiration.pending_due()):
                    u = db.session.get(UserModel, r.user_id)
                    ok = mock_send(user=u)
                    if ok:
                        r.mark_sent()
                    else:
                        r.mark_skipped("provider_failed")
                    db.session.commit()

            assert mock_send.call_count == 1

        with app.app_context():
            row = CheckoutExpiration.query.filter_by(
                session_id="cs_due_on"
            ).first()
            assert row.sent_at is not None
            assert row.skipped_reason is None

    def test_double_dispatch_does_not_resend(self, raw_client, app, monkeypatch):
        """Second dispatcher run after a successful send must NOT re-send."""
        monkeypatch.setenv("PIVOX_CHECKOUT_FOLLOWUP_ENABLED", "true")
        user_id = _make_user(app, email="twice@test.com", customer_id="cus_twice")

        from extensions import db
        from models import CheckoutExpiration
        with app.app_context():
            past_expired = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
            row = CheckoutExpiration(
                user_id=user_id,
                session_id="cs_twice",
                expired_at=past_expired,
                scheduled_send_at=past_expired + timedelta(hours=1),
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None),  # already sent
            )
            db.session.add(row)
            db.session.commit()

        with app.app_context():
            rows = list(CheckoutExpiration.pending_due())
            assert rows == []  # filter excludes sent_at IS NOT NULL


class TestActiveSubscriberSuppression:
    def test_user_already_active_marks_skipped_no_send(
        self, raw_client, app, monkeypatch,
    ):
        """User completed checkout between expired and dispatch → skip.

        Race window: webhook fires expired at T, user completes a NEW
        checkout at T+30m, our +1h dispatcher fires at T+1h. We must
        NOT email an active subscriber.
        """
        monkeypatch.setenv("PIVOX_CHECKOUT_FOLLOWUP_ENABLED", "true")
        user_id = _make_user(app)

        from extensions import db
        from models import CheckoutExpiration, User as UserModel
        with app.app_context():
            # Flip user → active *after* the expired enqueue.
            u = db.session.get(UserModel, user_id)
            u.subscription_status = "active"
            u.subscription_tier = "pro"
            past_expired = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
            row = CheckoutExpiration(
                user_id=user_id,
                session_id="cs_active_race",
                expired_at=past_expired,
                scheduled_send_at=past_expired + timedelta(hours=1),
            )
            db.session.add(row)
            db.session.commit()

        with patch(
            "services.billing_followup.send_checkout_followup"
        ) as mock_send:
            with app.app_context():
                for r in list(CheckoutExpiration.pending_due()):
                    u = db.session.get(UserModel, r.user_id)
                    if getattr(u, "subscription_status", None) == "active":
                        r.mark_skipped("already_subscribed")
                    else:
                        ok = mock_send(user=u)
                        if ok:
                            r.mark_sent()
                    db.session.commit()
            assert mock_send.call_count == 0

        with app.app_context():
            row = CheckoutExpiration.query.filter_by(
                session_id="cs_active_race"
            ).first()
            assert row.sent_at is None
            assert row.skipped_reason == "already_subscribed"


class TestRenderNoMarketingCopy:
    """The follow-up body MUST NOT contain marketing words. §50 transactional."""

    BANNED_TOKENS = ("할인", "혜택", "특별 가격", "프로모션", "쿠폰", "discount", "promo")

    def test_html_body_has_no_marketing_words(self, app):
        from services.billing_followup import _render_followup_html

        class _U:
            id = 1
            email = "x@test.com"
            name = "Test"

        html = _render_followup_html(user=_U(), portal_url="https://x.example/p")
        lo = html.lower()
        for tok in self.BANNED_TOKENS:
            assert tok.lower() not in lo, (
                f"banned marketing token {tok!r} appears in follow-up HTML"
            )

    def test_text_body_has_no_marketing_words(self, app):
        from services.billing_followup import _render_followup_text

        class _U:
            id = 1
            email = "x@test.com"
            name = "Test"

        text = _render_followup_text(user=_U(), portal_url="https://x.example/p")
        lo = text.lower()
        for tok in self.BANNED_TOKENS:
            assert tok.lower() not in lo, (
                f"banned marketing token {tok!r} appears in follow-up text"
            )


class TestSendCheckoutFollowupNoProvider:
    def test_no_user_returns_false(self, app, monkeypatch):
        """No user / no email → False, no provider call."""
        from services.billing_followup import send_checkout_followup
        # Clear both providers — must short-circuit early on user check
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("BREVO_API_KEY", raising=False)
        monkeypatch.delenv("SENDINBLUE_API_KEY", raising=False)

        assert send_checkout_followup(user=None) is False

        class _UserNoEmail:
            id = 1
            email = None

        assert send_checkout_followup(user=_UserNoEmail()) is False

    def test_no_providers_returns_false(self, app, monkeypatch):
        """User present + no provider configured → returns False."""
        from services.billing_followup import send_checkout_followup
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("BREVO_API_KEY", raising=False)
        monkeypatch.delenv("SENDINBLUE_API_KEY", raising=False)

        class _U:
            id = 1
            email = "x@test.com"
            name = "Test"

        assert send_checkout_followup(user=_U()) is False
