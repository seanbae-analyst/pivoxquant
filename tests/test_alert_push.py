"""Tests for the bell-alert → PWA push delivery hook.

Confirms:
1. ``services.alert.create_alert`` triggers ``push_service.notify_bell_alert``
   after a successful DB insert.
2. Bell-alert kinds flow through as transactional (bypass marketing
   opt-out gate).
3. ``services.push_service.send_push_to_user`` honours ``User.email_opt_out`` for
   non-transactional pushes (정통망법 §50).
4. A push delivery failure does NOT prevent the bell alert from being
   persisted.
5. The convenience wrappers (``alert_52w_high``, ``alert_concentration``,
   ``alert_macro_event``) all reach the push fan-out.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ── create_alert → notify_bell_alert ───────────────────────────────────────

class TestCreateAlertPushHook:
    def test_create_alert_invokes_notify_bell_alert(self, app, make_user):
        from services.alert import create_alert

        user = make_user(email="bell1@test.com")
        with app.app_context(), \
             patch("services.push_service.notify_bell_alert") as mock_notify:
            a = create_alert(
                user_id=user["id"],
                kind="price_52w_high",
                title="AAPL reached 52-week high",
                body="Observation",
                ticker="AAPL",
                link="/detail/AAPL",
            )
            assert a is not None, "alert row must be created"
            assert mock_notify.called, "push fan-out must run after insert"
            kwargs = mock_notify.call_args.kwargs
            assert kwargs["user_id"] == user["id"]
            assert kwargs["kind"] == "price_52w_high"
            assert "AAPL" in kwargs["title"]
            assert kwargs["link"] == "/detail/AAPL"

    def test_push_failure_does_not_block_alert_insert(self, app, make_user):
        """If the push fan-out raises, the alert row must still be persisted."""
        from extensions import db
        from models import Alert
        from services.alert import create_alert

        user = make_user(email="bell2@test.com")
        with app.app_context(), \
             patch("services.push_service.notify_bell_alert",
                   side_effect=RuntimeError("push backend down")):
            a = create_alert(
                user_id=user["id"],
                kind="macro_event",
                title="FOMC tomorrow",
                body=None,
            )
            assert a is not None, "alert insert must survive push failure"
            row = Alert.query.filter_by(user_id=user["id"],
                                        kind="macro_event").first()
            assert row is not None
            db.session.rollback()

    def test_invalid_kind_does_not_call_push(self, app, make_user):
        from services.alert import create_alert

        user = make_user(email="bell3@test.com")
        with app.app_context(), \
             patch("services.push_service.notify_bell_alert") as mock_notify:
            a = create_alert(
                user_id=user["id"],
                kind="not_a_real_kind",
                title="should be rejected",
            )
            assert a is None
            mock_notify.assert_not_called()

    def test_dedup_skip_does_not_call_push(self, app, make_user):
        """Second call within the dedup window must be a no-op (DB + push)."""
        from services.alert import create_alert

        user = make_user(email="bell4@test.com")
        with app.app_context():
            with patch("services.push_service.notify_bell_alert") as m1:
                first = create_alert(
                    user_id=user["id"],
                    kind="price_52w_high",
                    title="MSFT 52w high",
                    ticker="MSFT",
                    dedup_window_hours=24,
                )
                assert first is not None
                assert m1.call_count == 1

            with patch("services.push_service.notify_bell_alert") as m2:
                second = create_alert(
                    user_id=user["id"],
                    kind="price_52w_high",
                    title="MSFT 52w high",
                    ticker="MSFT",
                    dedup_window_hours=24,
                )
                assert second is None, "second call should dedup"
                m2.assert_not_called()


# ── notify_bell_alert → send_push_to_user ─────────────────────────────────

class TestNotifyBellAlertRouting:
    def test_known_kinds_marked_transactional(self, app, make_user):
        from services.push_service import notify_bell_alert

        user = make_user(email="route1@test.com")
        with app.app_context(), \
             patch("services.push_service.send_push_to_user") as mock_send:
            notify_bell_alert(
                user_id=user["id"],
                kind="price_52w_high",
                title="AAPL reached 52-week high",
                body="x",
                link="/detail/AAPL",
            )
            assert mock_send.called
            kwargs = mock_send.call_args.kwargs
            assert kwargs["transactional"] is True
            assert "PivoxQuant" in kwargs["title"]
            assert kwargs["url"] == "/detail/AAPL"

    def test_unknown_kind_defaults_to_marketing(self, app, make_user):
        """Unrecognised kinds must NOT be auto-promoted to transactional."""
        from services.push_service import notify_bell_alert

        user = make_user(email="route2@test.com")
        with app.app_context(), \
             patch("services.push_service.send_push_to_user") as mock_send:
            notify_bell_alert(
                user_id=user["id"],
                kind="brand_new_unknown",
                title="hello",
            )
            assert mock_send.called
            assert mock_send.call_args.kwargs["transactional"] is False


# ── send_push_to_user opt-out gate ────────────────────────────────────────

class TestSendPushOptOutGate:
    def test_marketing_push_blocked_when_email_opt_out(self, app, make_user):
        from extensions import db
        from models import User
        from services.push_service import send_push_to_user

        user = make_user(email="optout1@test.com")
        with app.app_context():
            u = User.query.get(user["id"])
            u.email_opt_out = True
            db.session.commit()

            # F3-03 (2026-05-17): patch path was ``routes.push.*`` but
            # send_push_to_user lives in services.push_service since PR
            # #437 — the patch never bound, the assertion was vacuous.
            # Patch the actual module-level import.
            with patch("models.PushSubscription") as mock_sub_q:
                mock_sub_q.query.filter_by.return_value.all.return_value = ["x"]
                send_push_to_user(
                    user_id=user["id"],
                    title="Promo",
                    body="Marketing blast",
                    transactional=False,
                )
                # The opt-out short-circuits BEFORE we reach the
                # PushSubscription query, so filter_by must never run.
                mock_sub_q.query.filter_by.assert_not_called()

    def test_transactional_push_bypasses_opt_out(self, app, make_user):
        """Even with email_opt_out=True, a transactional push must walk
        past the marketing opt-out gate.

        2026-05-13: Continuous User Simulation Phase 1 added an
        ``is_simulated`` lookup that runs BEFORE the opt-out gate for
        every push (sim users must never reach pywebpush regardless of
        the transactional flag — they have no real device). So a
        transactional push consults User exactly once (the sim guard)
        and the opt-out gate is the one that's bypassed. We assert the
        observable contract: transactional=True with a non-sim,
        opt-out=True user still reaches the VAPID stage (i.e. the
        opt-out short-circuit did NOT fire)."""
        from extensions import db
        from models import User
        from services.push_service import send_push_to_user

        user = make_user(email="optout2@test.com")
        with app.app_context():
            u = User.query.get(user["id"])
            u.email_opt_out = True
            u.is_simulated = False  # explicit — default already
            db.session.commit()

            # Real User row, real is_simulated check, real opt-out
            # check. With no VAPID key the send returns at the VAPID
            # stage — but importantly, after walking past the opt-out
            # gate. We confirm by capturing the log line at INFO.
            # F3-03 (2026-05-17): patch services.push_service.logger
            # (where the opt-out log actually emits), not routes.push.
            with patch("services.push_service.logger") as mock_log:
                send_push_to_user(
                    user_id=user["id"],
                    title="52w high",
                    body="AAPL",
                    transactional=True,
                )
                # The opt-out gate emits "push opt-out: user_id=..."
                # at INFO when it fires. Transactional MUST bypass it.
                opt_out_calls = [
                    c for c in mock_log.info.call_args_list
                    if c.args and "push opt-out" in str(c.args[0])
                ]
                assert not opt_out_calls, \
                    "transactional push must bypass the opt-out gate"

    # ── FIX 1: per-event notification_prefs fail-open for bell alerts ──────

    def test_bell_alert_with_no_matching_event_id_is_delivered_regardless_of_prefs(
        self, app, make_user,
    ):
        """A bell kind that maps to NO event_id (52w / concentration / macro)
        must be delivered even when the user has muted everything — there is
        no pref to consult, so FAIL-OPEN governs."""
        from extensions import db
        from models import Alert, User
        from services.alert import create_alert, _BELL_KIND_TO_EVENT_ID

        user = make_user(email="failopen1@test.com")
        with app.app_context():
            # Mute every channel for every known event. None of these touch
            # the unmapped bell kinds, so the alert must still ship.
            from models.user import NOTIFICATION_EVENT_IDS
            u = User.query.get(user["id"])
            u.notification_prefs = {
                ev: {"email": False, "push": False, "inapp": False}
                for ev in NOTIFICATION_EVENT_IDS
            }
            db.session.commit()

            # Sanity: concentration_alert is unmapped (fail-open).
            assert _BELL_KIND_TO_EVENT_ID.get("concentration_alert") is None

            with patch("services.push_service.notify_bell_alert") as mock_notify:
                a = create_alert(
                    user_id=user["id"],
                    kind="concentration_alert",
                    title="Portfolio concentration — Tech 42.0%",
                    body="Observation",
                    link="/risk",
                )
            assert a is not None, "unmapped bell alert must be delivered (fail-open)"
            row = Alert.query.filter_by(user_id=user["id"],
                                        kind="concentration_alert").first()
            assert row is not None
            assert mock_notify.called, "push fan-out must run for unmapped kind"
            db.session.rollback()

    def test_marketing_push_consults_opt_out_when_not_opted_out(self, app, make_user):
        """Non-transactional pushes must read User.email_opt_out before
        proceeding (defence-in-depth: the gate runs every time).

        2026-05-13: send_push_to_user now consults the User row twice —
        once for the ``is_simulated`` guard (added in the CAUS Phase 1
        follow-up), then again for the marketing opt-out gate. Both
        lookups are intentional: failing closed on the sim check
        before the opt-out check matters because sim users must never
        reach pywebpush even if their opt-out flag is False."""
        from services.push_service import send_push_to_user

        user = make_user(email="optout3@test.com")
        with app.app_context():
            with patch("models.User") as mock_user_cls:
                fake = type("U", (), {
                    "email_opt_out": False,
                    "is_simulated": False,
                })()
                mock_user_cls.query.get.return_value = fake
                send_push_to_user(
                    user_id=user["id"],
                    title="Promo",
                    body="ok",
                    transactional=False,
                )
                # Both gates query the same user. The exact count is
                # an implementation detail; the contract is "at least
                # one lookup with the right id, all returning the
                # opted-in user, no short-circuit."
                assert mock_user_cls.query.get.call_count >= 1
                for call in mock_user_cls.query.get.call_args_list:
                    assert call.args == (user["id"],)
