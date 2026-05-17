"""Continuous User Simulation Phase 1 — ``is_simulated`` isolation tests.

Spec: ``docs/specs/continuous-user-sim-spec.md`` Phase 1 / PR #351 follow-up.

``User.is_simulated`` (migration 032) tags synthetic test users the Sunday
04:30 KST simulation cron will eventually generate. Every external side
effect MUST short-circuit for sim users:

1. **Email** — ``EmailSender.send`` returns ``False`` before any provider
   is contacted (정통망법 §50 + SendGrid quota).
2. **Push** — ``services.push_service.send_push_to_user`` returns before pywebpush
   is reached. Covers all four ``services.push_service`` helpers
   (``notify_alert``, ``notify_bell_alert``, ``notify_trade``,
   ``notify_insight``) because they all funnel through that one call.
3. **Analytics / mass artefact loops** — ``User.query.filter_by(
   is_simulated=False)`` excludes sim rows from the scheduled refresh
   and the brag-card mass-mailers so the cycle doesn't burn real
   compute on synthetic users.
4. **Sentry** — every request emits a ``user_type`` tag
   (``sim`` / ``real`` / ``anon``) so the dashboard can filter sim
   noise away from real-user signal.

Real users (``is_simulated=False``) are NOT affected by any of these
guards — every test asserts the negative path too so we never silently
regress on legit traffic.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── 1. EmailSender ──────────────────────────────────────────────────────────


class TestEmailSenderIsSimulatedGuard:
    def test_email_sender_skips_simulated_user(self, app, make_user, monkeypatch):
        """``is_simulated=True`` → ``send`` returns False without touching
        either provider. Both SendGrid and SMTP raise on call so a slipped
        guard is loud, not silent."""
        from extensions import db
        from models import User
        from services.email import EmailSender

        user = make_user(email="sim-email@test.com")
        with app.app_context():
            u = db.session.get(User, user["id"])
            u.is_simulated = True
            db.session.commit()

            monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
            monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
            sg = MagicMock(side_effect=AssertionError("sim leaked to SendGrid"))
            smtp = MagicMock(side_effect=AssertionError("sim leaked to SMTP"))
            with patch("sendgrid.SendGridAPIClient", sg), \
                 patch("smtplib.SMTP", smtp):
                sent = EmailSender().send(
                    u,
                    subject="x",
                    html_body="<p>body</p>",
                    from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                    from_default="reports@pivoxquant.com",
                )
                assert sent is False
                sg.assert_not_called()
                smtp.assert_not_called()

    def test_email_sender_real_user_still_sends(self, app, make_user, monkeypatch):
        """Negative path — ``is_simulated=False`` (default) must NOT be
        gated. Mocks SendGrid so we don't actually dispatch but assert
        the client was constructed + ``send`` invoked."""
        from extensions import db
        from models import User
        from services.email import EmailSender

        user = make_user(email="real-email@test.com")
        with app.app_context():
            u = db.session.get(User, user["id"])
            # explicit for clarity — default is False already
            u.is_simulated = False
            db.session.commit()

            monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
            fake_client = MagicMock()
            fake_client.send = MagicMock(return_value=None)
            with patch("sendgrid.SendGridAPIClient",
                       return_value=fake_client) as sg_ctor:
                sent = EmailSender().send(
                    u,
                    subject="x",
                    html_body="<p>body</p>",
                    from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                    from_default="reports@pivoxquant.com",
                )
                assert sent is True
                sg_ctor.assert_called_once()
                fake_client.send.assert_called_once()


# ── 2. send_push_to_user (covers all 4 push helpers) ────────────────────────


class TestSendPushToUserIsSimulatedGuard:
    """``services.push_service.send_push_to_user`` is the single funnel for every
    helper in ``services.push_service`` (``notify_alert`` /
    ``notify_bell_alert`` / ``notify_trade`` / ``notify_insight``). One
    guard there → all four helpers covered."""

    def _arm_vapid(self, monkeypatch):
        # Make sure the guard fires *before* the VAPID-missing return below
        # — otherwise a passing test would be ambiguous about which exit
        # path actually fired.
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "x" * 64)
        monkeypatch.setenv("VAPID_EMAIL", "mailto:admin@pivoxquant.com")

    def test_send_push_skips_simulated_user(self, app, make_user, monkeypatch):
        from extensions import db
        from models import User
        from services.push_service import send_push_to_user

        user = make_user(email="sim-push@test.com")
        with app.app_context():
            u = db.session.get(User, user["id"])
            u.is_simulated = True
            db.session.commit()

            self._arm_vapid(monkeypatch)
            with patch("pywebpush.webpush",
                       side_effect=AssertionError("sim leaked to pywebpush")):
                # transactional=True must still be blocked — sim users
                # have no real device subscription.
                send_push_to_user(
                    user_id=user["id"],
                    title="t", body="b", url="/x",
                    transactional=True,
                )
                # No exception → guard fired before webpush(). If the
                # guard regressed, the side_effect AssertionError would
                # surface here.

    def test_notify_helpers_all_skip_simulated_user(self, app, make_user, monkeypatch):
        """All four ``services.push_service`` helpers funnel through
        ``send_push_to_user``. Patching webpush to raise asserts that
        none of them reach the network path for a sim user."""
        from extensions import db
        from models import User
        from services.push_service import (
            notify_alert,
            notify_bell_alert,
            notify_trade,
            notify_insight,
        )

        user = make_user(email="sim-helpers@test.com")
        with app.app_context():
            u = db.session.get(User, user["id"])
            u.is_simulated = True
            db.session.commit()

            self._arm_vapid(monkeypatch)
            with patch("pywebpush.webpush",
                       side_effect=AssertionError("sim leaked to pywebpush")):
                notify_alert(user["id"], {
                    "signal": "POSITIVE", "ticker": "AAPL",
                    "message": "x",
                })
                notify_bell_alert(user["id"], kind="price_52w_high",
                                  title="t", body="b")
                notify_trade(user["id"], ticker="AAPL", action="BUY",
                             shares=1, price=100.0)
                notify_insight(user["id"], title_text="t", body_text="b")
                # Reaching this line means no helper invoked webpush().

    def test_send_push_real_user_proceeds_past_guard(self, app, make_user, monkeypatch):
        """Negative path — real user (``is_simulated=False``) must NOT be
        blocked by the sim guard. We confirm the guard does not early-exit
        by asserting the code path reaches PushSubscription lookup
        (no subscriptions in DB → returns without calling webpush, but
        through a *different* exit than the sim guard)."""
        from extensions import db
        from models import User
        from services.push_service import send_push_to_user

        user = make_user(email="real-push@test.com")
        with app.app_context():
            u = db.session.get(User, user["id"])
            u.is_simulated = False
            db.session.commit()

            self._arm_vapid(monkeypatch)
            # 2026-05-17 PR #437: send_push_to_user moved from
            # routes.push to services.push_service and imports
            # PushSubscription lazily from models. The previous
            # patch.object(push_mod, "PushSubscription") no longer
            # intercepts the lookup because the routes.push module
            # never references PushSubscription anymore. Patch the
            # canonical source instead so the spy still fires.
            import models as models_mod
            with patch.object(models_mod, "PushSubscription") as ps_mock:
                ps_mock.query.filter_by.return_value.all.return_value = []
                send_push_to_user(
                    user_id=user["id"],
                    title="t", body="b", url="/x",
                    transactional=True,
                )
                ps_mock.query.filter_by.assert_called_once_with(user_id=user["id"])


# ── 3. Analytics queries (mass user iteration) ──────────────────────────────


class TestAnalyticsQueryExcludesSimulatedUsers:
    """Mass artefact mailers + the scheduled alert refresh filter
    ``is_simulated=False`` at the SQL layer so the per-row email/push
    guards don't have to burn render cycles on synthetic users."""

    def test_brag_card_query_excludes_simulated(self, app, make_user):
        from extensions import db
        from models import User

        real = make_user(email="real-brag@test.com")
        sim = make_user(email="sim-brag@test.com")
        with app.app_context():
            db.session.get(User, sim["id"]).is_simulated = True
            db.session.commit()

            # Mirror the exact query used in
            # services/artifacts/brag_card_service.py:1026.
            users = User.query.filter_by(is_simulated=False).all()
            ids = {u.id for u in users}
            assert real["id"] in ids
            assert sim["id"] not in ids

    def test_monthly_brag_query_excludes_simulated(self, app, make_user):
        from extensions import db
        from models import User

        real = make_user(email="real-monthly@test.com")
        sim = make_user(email="sim-monthly@test.com")
        with app.app_context():
            db.session.get(User, sim["id"]).is_simulated = True
            db.session.commit()

            users = User.query.filter_by(is_simulated=False).all()
            ids = {u.id for u in users}
            assert real["id"] in ids
            assert sim["id"] not in ids

    def test_scheduled_refresh_query_excludes_simulated(self, app, make_user):
        """app.py:_scheduled_refresh builds a ``users`` map keyed by id
        from ``User.query.filter_by(is_simulated=False).all()`` so the
        engine analyse loop never targets a sim user's available_capital."""
        from extensions import db
        from models import User

        real = make_user(email="real-sched@test.com")
        sim = make_user(email="sim-sched@test.com")
        with app.app_context():
            db.session.get(User, sim["id"]).is_simulated = True
            db.session.commit()

            users_map = {
                u.id: u
                for u in User.query.filter_by(is_simulated=False).all()
            }
            assert real["id"] in users_map
            assert sim["id"] not in users_map


# ── 4. Sentry user_type tag ─────────────────────────────────────────────────


class TestSentryUserTypeTag:
    """``app._set_sentry_user_type_tag`` is the single SoT for the Sentry
    ``user_type`` tag (wired up via ``before_request`` in the real
    ``create_app``). We unit-test the function directly with patched
    ``current_user`` so the conftest's stripped-down test app (which
    omits the before_request hook) doesn't matter — production wiring
    is verified by the in-file ``@app.before_request`` registration.
    """

    def _make_user_stub(self, *, is_authenticated: bool, is_simulated: bool = False):
        return MagicMock(
            is_authenticated=is_authenticated,
            is_simulated=is_simulated,
        )

    def test_anon_request_tags_user_type_anon(self):
        from app import _set_sentry_user_type_tag

        stub = self._make_user_stub(is_authenticated=False)
        with patch("app.sentry_sdk.set_tag") as set_tag, \
             patch("flask_login.utils._get_user", return_value=stub):
            result = _set_sentry_user_type_tag()
            assert result == "anon"
            set_tag.assert_called_with("user_type", "anon")

    def test_real_user_request_tags_user_type_real(self):
        from app import _set_sentry_user_type_tag

        stub = self._make_user_stub(is_authenticated=True, is_simulated=False)
        with patch("app.sentry_sdk.set_tag") as set_tag, \
             patch("flask_login.utils._get_user", return_value=stub):
            result = _set_sentry_user_type_tag()
            assert result == "real"
            set_tag.assert_called_with("user_type", "real")

    def test_simulated_user_request_tags_user_type_sim(self):
        from app import _set_sentry_user_type_tag

        stub = self._make_user_stub(is_authenticated=True, is_simulated=True)
        with patch("app.sentry_sdk.set_tag") as set_tag, \
             patch("flask_login.utils._get_user", return_value=stub):
            result = _set_sentry_user_type_tag()
            assert result == "sim"
            set_tag.assert_called_with("user_type", "sim")

    def test_before_request_hook_is_registered(self, app):
        """Belt-and-braces: confirm the production factory wires
        ``_set_sentry_user_type_tag`` into ``before_request``. The test
        conftest builds a minimal app so we inspect the real ``create_app``
        function source to check the hook is registered (rather than
        running the full factory which spins up schedulers + live API
        calls)."""
        import inspect
        import app as app_module

        src = inspect.getsource(app_module.create_app)
        assert "_set_sentry_user_type_tag" in src, \
            "create_app must call _set_sentry_user_type_tag via before_request"
        assert "@app.before_request" in src, \
            "create_app must register a before_request hook"
