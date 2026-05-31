"""tests/test_onboarding_sequence.py — D+0/D+3/D+7 onboarding sequence.

Wave G S5 (2026-05-19).

Covers seven contracts:

1.  ``schedule_onboarding`` with the feature flag ON enqueues exactly
    three rows (welcome / d3_guide / d7_pro_nudge) with correct offsets
    and categories.
2.  ``schedule_onboarding`` is idempotent — calling it twice for the
    same user produces no duplicate rows.
3.  ``schedule_onboarding`` with the feature flag OFF enqueues nothing
    and reports ``flag_off=1``.
4.  ``ScheduledEmail.pending_due`` returns only rows whose
    ``scheduled_send_at <= now`` AND ``sent_at IS NULL`` AND
    ``skipped_reason IS NULL``, ordered oldest-first.
5.  ``dispatch_due`` with the flag ON sends each due row exactly once
    and stamps ``sent_at``; a second pass does not re-send.
6.  ``dispatch_due`` with the flag OFF stamps ``skipped_reason =
    "feature_flag_off"`` on each due row and never invokes the
    EmailSender.
7.  INFORMATION steps respect the EmailSender's consent / opt-out gate
    (sender returns False → row stamped ``no_consent_or_provider``).

Also asserts the marketing-copy ban list (``BANNED_MARKETING_PHRASES``)
is absent from every onboarding template — HTML + text bodies. This
keeps the d7 Pro step on the right side of 정통망법 §50 ①
(information vs marketing reclassification).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────


def _enable_flag(monkeypatch):
    monkeypatch.setenv("PIVOX_ONBOARDING_SEQUENCE_ENABLED", "true")


def _disable_flag(monkeypatch):
    monkeypatch.setenv("PIVOX_ONBOARDING_SEQUENCE_ENABLED", "false")


def _enable_paid_plans(monkeypatch):
    # Stage-1 revival: brings d7_pro_nudge back into the active sequence.
    monkeypatch.setenv("PIVOX_PAID_PLANS_ENABLED", "true")


def _disable_paid_plans(monkeypatch):
    # Stage-0 free launch (default): d7_pro_nudge excluded.
    monkeypatch.setenv("PIVOX_PAID_PLANS_ENABLED", "false")


def _row_count(app, user_id: int) -> int:
    from models import ScheduledEmail
    with app.app_context():
        return ScheduledEmail.query.filter_by(user_id=user_id).count()


# ── 1. happy-path enqueue ──────────────────────────────────────────────────


class TestScheduleOnboarding:
    def test_stage0_enqueues_two_rows(self, app, make_user, monkeypatch):
        # Free launch (Stage 0, default): welcome + d3_guide only — the
        # d7_pro_nudge paid-plan step is excluded (PIVOX_PAID_PLANS_ENABLED
        # off). This is the LIVE free-launch contract.
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)
        u = make_user(email="seq1@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import (
            schedule_onboarding, active_sequence,
        )

        with app.app_context():
            user = db.session.get(User, u["id"])
            now = datetime(2026, 5, 19, 12, 0, 0)
            stats = schedule_onboarding(user, now=now)
            db.session.commit()

        assert stats == {"enqueued": 2, "existed": 0, "flag_off": 0}

        with app.app_context():
            rows = (
                ScheduledEmail.query
                .filter_by(user_id=u["id"])
                .order_by(ScheduledEmail.scheduled_send_at.asc())
                .all()
            )
            assert [r.email_type for r in rows] == ["welcome", "d3_guide"]
            assert [r.email_type for r in rows] == [
                s.slug for s in active_sequence()
            ]
            # d7_pro_nudge (paid-plan nudge) must NOT be queued at Stage 0.
            assert "d7_pro_nudge" not in [r.email_type for r in rows]
            assert [r.email_category for r in rows] == [
                "transactional", "information",
            ]
            expected_offsets = [
                timedelta(days=0),
                timedelta(days=3),
            ]
            for row, off in zip(rows, expected_offsets):
                assert row.scheduled_send_at == datetime(2026, 5, 19, 12, 0, 0) + off
                assert row.sent_at is None
                assert row.skipped_reason is None
                assert row.idempotency_key == f"u{u['id']}:{row.email_type}"

    def test_stage1_enqueues_three_rows(self, app, make_user, monkeypatch):
        # Stage-1 revival (PIVOX_PAID_PLANS_ENABLED on): d7_pro_nudge comes
        # back at +7d. Guards the code-preservation/revival path.
        _enable_flag(monkeypatch)
        _enable_paid_plans(monkeypatch)
        u = make_user(email="seq1_stage1@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import schedule_onboarding

        with app.app_context():
            user = db.session.get(User, u["id"])
            now = datetime(2026, 5, 19, 12, 0, 0)
            stats = schedule_onboarding(user, now=now)
            db.session.commit()

        assert stats == {"enqueued": 3, "existed": 0, "flag_off": 0}

        with app.app_context():
            rows = (
                ScheduledEmail.query
                .filter_by(user_id=u["id"])
                .order_by(ScheduledEmail.scheduled_send_at.asc())
                .all()
            )
            assert [r.email_type for r in rows] == [
                "welcome", "d3_guide", "d7_pro_nudge",
            ]
            assert [r.email_category for r in rows] == [
                "transactional", "information", "information",
            ]
            d7 = rows[-1]
            assert d7.scheduled_send_at == datetime(2026, 5, 19, 12, 0, 0) + timedelta(days=7)

    def test_flag_off_enqueues_nothing(self, app, make_user, monkeypatch):
        _disable_flag(monkeypatch)
        u = make_user(email="seq_off@test.com")

        from extensions import db
        from models import User
        from services.email.onboarding_sequence import schedule_onboarding

        with app.app_context():
            user = db.session.get(User, u["id"])
            stats = schedule_onboarding(user)
            db.session.commit()

        assert stats["flag_off"] == 1
        assert stats["enqueued"] == 0
        assert _row_count(app, u["id"]) == 0

    def test_double_call_is_idempotent(self, app, make_user, monkeypatch):
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)  # Stage-0: 2-step sequence.
        u = make_user(email="seq_dup@test.com")

        from extensions import db
        from models import User
        from services.email.onboarding_sequence import schedule_onboarding

        with app.app_context():
            user = db.session.get(User, u["id"])
            stats1 = schedule_onboarding(user)
            db.session.commit()
            stats2 = schedule_onboarding(user)
            db.session.commit()

        assert stats1["enqueued"] == 2
        assert stats2["enqueued"] == 0
        assert stats2["existed"] == 2
        assert _row_count(app, u["id"]) == 2


# ── 2. pending_due query correctness ───────────────────────────────────────


class TestPendingDue:
    def test_only_due_rows_returned(self, app, make_user, monkeypatch):
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)  # Stage-0: welcome + d3_guide only.
        u = make_user(email="due@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import schedule_onboarding

        with app.app_context():
            user = db.session.get(User, u["id"])
            base = datetime(2026, 5, 19, 12, 0, 0)
            schedule_onboarding(user, now=base)
            db.session.commit()

            # 1h after base: only D+0 is due.
            due = list(ScheduledEmail.pending_due(now=base + timedelta(hours=1)))
            assert [r.email_type for r in due] == ["welcome"]

            # 4d after base: D+0 + D+3 due (oldest-first ordering).
            due4 = list(ScheduledEmail.pending_due(now=base + timedelta(days=4)))
            assert [r.email_type for r in due4] == ["welcome", "d3_guide"]

            # 10d after base: both Stage-0 rows due, no d7_pro_nudge.
            due10 = list(ScheduledEmail.pending_due(now=base + timedelta(days=10)))
            assert [r.email_type for r in due10] == ["welcome", "d3_guide"]

    def test_sent_rows_filtered_out(self, app, make_user, monkeypatch):
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)  # Stage-0: welcome + d3_guide only.
        u = make_user(email="sentfilter@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import schedule_onboarding

        with app.app_context():
            user = db.session.get(User, u["id"])
            base = datetime(2026, 5, 19, 12, 0, 0)
            schedule_onboarding(user, now=base)
            db.session.commit()

            welcome = ScheduledEmail.query.filter_by(
                user_id=u["id"], email_type="welcome",
            ).one()
            welcome.mark_sent()
            db.session.commit()

            due = list(ScheduledEmail.pending_due(now=base + timedelta(days=10)))
            slugs = [r.email_type for r in due]
            assert "welcome" not in slugs
            assert set(slugs) == {"d3_guide"}

    def test_skipped_rows_filtered_out(self, app, make_user, monkeypatch):
        _enable_flag(monkeypatch)
        u = make_user(email="skipfilter@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import schedule_onboarding

        with app.app_context():
            user = db.session.get(User, u["id"])
            base = datetime(2026, 5, 19, 12, 0, 0)
            schedule_onboarding(user, now=base)
            db.session.commit()

            d3 = ScheduledEmail.query.filter_by(
                user_id=u["id"], email_type="d3_guide",
            ).one()
            d3.mark_skipped("test_reason")
            db.session.commit()

            due = list(ScheduledEmail.pending_due(now=base + timedelta(days=10)))
            slugs = [r.email_type for r in due]
            assert "d3_guide" not in slugs


# ── 3. dispatch_due send + idempotency ─────────────────────────────────────


class TestDispatchDue:
    def test_flag_off_marks_skipped_no_send(self, app, make_user, monkeypatch):
        # Enqueue while flag is ON, then dispatch while flag is OFF.
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)  # Stage-0: 2-step sequence.
        u = make_user(email="dispatch_off@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import (
            schedule_onboarding, dispatch_due,
        )

        with app.app_context():
            user = db.session.get(User, u["id"])
            base = datetime(2026, 5, 19, 12, 0, 0)
            schedule_onboarding(user, now=base)
            db.session.commit()

        _disable_flag(monkeypatch)

        with app.app_context(), \
             patch("services.email.onboarding_sequence._send_one") as send:
            stats = dispatch_due(now=base + timedelta(days=10))
            send.assert_not_called()

        assert stats["due"] == 2
        assert stats["skipped_flag_off"] == 2
        assert stats["sent"] == 0

        with app.app_context():
            rows = ScheduledEmail.query.filter_by(user_id=u["id"]).all()
            assert all(r.skipped_reason == "feature_flag_off" for r in rows)
            assert all(r.sent_at is None for r in rows)

    def test_flag_on_sends_due_rows(self, app, make_user, monkeypatch):
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)  # Stage-0: 2-step sequence.
        u = make_user(email="dispatch_on@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import (
            schedule_onboarding, dispatch_due,
        )

        with app.app_context():
            user = db.session.get(User, u["id"])
            base = datetime(2026, 5, 19, 12, 0, 0)
            schedule_onboarding(user, now=base)
            db.session.commit()

        with app.app_context(), \
             patch(
                 "services.email.onboarding_sequence._send_one",
                 return_value=True,
             ) as send:
            stats = dispatch_due(now=base + timedelta(days=10))
            assert send.call_count == 2

        assert stats["due"] == 2
        assert stats["sent"] == 2
        assert stats["skipped_flag_off"] == 0

        with app.app_context():
            rows = ScheduledEmail.query.filter_by(user_id=u["id"]).all()
            assert all(r.sent_at is not None for r in rows)
            assert all(r.skipped_reason is None for r in rows)

    def test_double_dispatch_does_not_resend(self, app, make_user, monkeypatch):
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)  # Stage-0: 2-step sequence.
        u = make_user(email="dispatch_twice@test.com")

        from extensions import db
        from models import User
        from services.email.onboarding_sequence import (
            schedule_onboarding, dispatch_due,
        )

        with app.app_context():
            user = db.session.get(User, u["id"])
            base = datetime(2026, 5, 19, 12, 0, 0)
            schedule_onboarding(user, now=base)
            db.session.commit()

        with app.app_context(), \
             patch(
                 "services.email.onboarding_sequence._send_one",
                 return_value=True,
             ) as send:
            dispatch_due(now=base + timedelta(days=10))
            # Second pass — every row's sent_at is now set, so
            # pending_due returns zero rows.
            stats2 = dispatch_due(now=base + timedelta(days=10))
            assert stats2["due"] == 0
            assert stats2["sent"] == 0
            # send was called 2x for the first pass, 0x for the second.
            assert send.call_count == 2

    def test_information_blocked_by_consent_marks_skipped(
        self, app, make_user, monkeypatch,
    ):
        """When EmailSender refuses (no consent), row is closed."""
        _enable_flag(monkeypatch)
        _disable_paid_plans(monkeypatch)  # Stage-0: 2-step sequence.
        u = make_user(email="noconsent@test.com")

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import (
            schedule_onboarding, dispatch_due,
        )

        with app.app_context():
            user = db.session.get(User, u["id"])
            base = datetime(2026, 5, 19, 12, 0, 0)
            schedule_onboarding(user, now=base)
            db.session.commit()

        # _send_one returns False → dispatcher closes the row with
        # "no_consent_or_provider".
        with app.app_context(), \
             patch(
                 "services.email.onboarding_sequence._send_one",
                 return_value=False,
             ):
            stats = dispatch_due(now=base + timedelta(days=10))

        assert stats["due"] == 2
        assert stats["sent"] == 0
        assert stats["skipped_no_consent"] == 2

        with app.app_context():
            rows = ScheduledEmail.query.filter_by(user_id=u["id"]).all()
            assert all(
                r.skipped_reason == "no_consent_or_provider" for r in rows
            )
            assert all(r.sent_at is None for r in rows)


# ── 4. template marketing-copy ban ─────────────────────────────────────────


class TestTemplateContent:
    def test_no_marketing_copy_in_templates(self):
        from services.email.onboarding_sequence import BANNED_MARKETING_PHRASES

        template_dir = (
            Path(__file__).resolve().parent.parent
            / "services" / "email" / "templates" / "onboarding"
        )
        for path in sorted(template_dir.iterdir()):
            if path.suffix not in (".html", ".txt"):
                continue
            text = path.read_text(encoding="utf-8").lower()
            for banned in BANNED_MARKETING_PHRASES:
                assert banned.lower() not in text, (
                    f"{path.name} contains banned marketing phrase {banned!r} "
                    f"— would re-classify as 광고성 정보 under 정통망법 §50 ①"
                )

    def test_all_six_templates_present(self):
        template_dir = (
            Path(__file__).resolve().parent.parent
            / "services" / "email" / "templates" / "onboarding"
        )
        expected = {
            "welcome.html", "welcome.txt",
            "d3_guide.html", "d3_guide.txt",
            "d7_pro_nudge.html", "d7_pro_nudge.txt",
        }
        actual = {p.name for p in template_dir.iterdir() if p.is_file()}
        assert expected.issubset(actual), (
            f"missing onboarding templates: {expected - actual}"
        )
