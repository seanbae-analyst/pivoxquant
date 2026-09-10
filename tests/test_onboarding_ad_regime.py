"""d3_guide is 광고성, and the régime that follows must actually render.

Reclassified 2026-09-10 (CEO) from 정보성. The reasoning is the one this
codebase already applied to the inactive nudge in f70bc8b4, and leaving the
two classified differently was the inconsistency:

    the mail goes out on day 3 whether or not the reader has recorded
    anything, and states no fact about them — it explains the three screens
    and then says "아직 안 해보셨다면 1. 2. 3." with a dashboard CTA. That is
    a message asking someone to come back, 광고성 정보 under 정통망법 §50 ①.
    Containing instructions does not make it 정보성.

Four requirements follow, and all four were missing while it was 정보성:
"(광고)" in subject and body (시행령 §62 ②), the sender-identity block
(시행령 §62 ①), the 21:00–08:00 KST night ban (시행령 §61의2), and MARKETING
consent rather than INFORMATION.

welcome stays TRANSACTIONAL — a signup confirmation is §50 ③ exempt — and is
asserted here too, because the cheapest way to get this wrong later is to
sweep the whole sequence into one category.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from services.email import onboarding_sequence as ob

UNSUB = "https://www.pivoxquant.com/api/email/unsubscribe?token=TEST"


def _user():
    return SimpleNamespace(
        id=1, name="배상현", email="seanbae1521@gmail.com", is_simulated=False,
        marketing_consent_marketing_at=datetime(2026, 9, 1, 10, 30),
    )


def _step(slug):
    for s in ob.active_sequence():
        if s.slug == slug:
            return s
    raise AssertionError(f"{slug} not in active_sequence()")


def _bodies(slug):
    return ob._render(_step(slug).template_basename, user=_user(),
                      unsubscribe_url=UNSUB)


class TestClassification:
    def test_d3_guide_is_marketing(self):
        assert _step("d3_guide").category == "marketing"

    def test_welcome_stays_transactional(self):
        """§50 ③ exempt. A signup confirmation is not an advertisement, and
        forcing MARKETING consent on it would block the one mail a new user
        has a right to receive."""
        assert _step("welcome").category == "transactional"

    def test_the_subject_carries_the_marker(self):
        assert _step("d3_guide").subject.startswith("(광고)")


class TestRegimeRenders:
    """Asserted on the RENDERED bodies, not the template files. The template
    can hold the markup and still ship without it if a placeholder is left
    unfilled — which is exactly what happened when the consent slots were
    first added and _render did not know them."""

    @pytest.mark.parametrize("kind", ["html", "txt"])
    def test_ad_marker_present(self, kind):
        html, txt = _bodies("d3_guide")
        assert "(광고)" in (html if kind == "html" else txt)

    @pytest.mark.parametrize("kind", ["html", "txt"])
    def test_sender_identity_block(self, kind):
        # 시행령 §62 ① — 사업자명 · 연락처 · 수신거부 수단 · 동의 일시/출처.
        body = _bodies("d3_guide")[0 if kind == "html" else 1]
        for needle in ("459-01-03808", "support@pivoxquant.com", UNSUB, "동의"):
            assert needle in body, f"{kind} missing {needle}"

    @pytest.mark.parametrize("kind", ["html", "txt"])
    def test_night_ban_is_disclosed(self, kind):
        body = _bodies("d3_guide")[0 if kind == "html" else 1]
        assert "21:00" in body and "08:00" in body

    def test_marker_is_early_enough_to_be_seen(self):
        """The retention templates learned this the hard way: a "(광고)" that
        sits past the first screenful is not a marker anyone reads. Both the
        <title> and the first body line carry it."""
        html, txt = _bodies("d3_guide")
        assert "(광고)" in html[:400]
        assert txt.lstrip().startswith("(광고)")


class TestNoPlaceholderLeaks:
    @pytest.mark.parametrize("slug", ["welcome", "d3_guide"])
    def test_every_slot_is_filled(self, slug):
        html, txt = _bodies(slug)
        assert "{{" not in html and "}}" not in html, slug
        assert "{{" not in txt and "}}" not in txt, slug

    def test_render_needs_no_app_context(self):
        """_render must stay a pure function. It briefly built the unsubscribe
        token itself, which signs an HMAC with SECRET_KEY and therefore needs
        a Flask app — that broke every test calling it directly. The caller
        passes the token in instead."""
        html, _ = ob._render("d3_guide", user=_user())   # no url, no app
        assert "{{" not in html


class TestNightBan:
    """시행령 §61의2 — 광고성 정보는 21:00~08:00 KST 에 발송 금지.

    Implemented by leaving the row PENDING rather than skipping it, the way
    retention_sequence does: this queue is re-scanned every 15 minutes, so a
    row that comes due at 23:00 is simply picked up after 08:00. (The nudge
    had to widen its selection window instead — it has no queue to wait in,
    and roughly 46% of signups would otherwise never have been reached.)

    Without these, the suite would still be green while the gate did nothing:
    the existing dispatch tests only prove a send happens at a legal hour.
    """

    @pytest.mark.parametrize("utc_hour,kst,expect_night", [
        (2, "11:00", False),   # 낮
        (9, "18:00", False),   # 낮
        (12, "21:00", True),   # 야간 시작 — 기존 테스트가 여기 걸려 있었다
        (18, "03:00", True),   # 심야
        (22, "07:00", True),   # 야간 끝 직전
        (23, "08:00", False),  # 해제
    ])
    def test_boundary(self, utc_hour, kst, expect_night):
        from datetime import datetime as _dt
        from services.email.retention_sequence import is_night_kst
        got = is_night_kst(_dt(2026, 5, 19, utc_hour, 0, 0))
        assert got is expect_night, f"{utc_hour:02d}:00 UTC = {kst} KST"

    def test_marketing_row_is_deferred_not_skipped(self, app, make_user, monkeypatch):
        """Deferred means still sendable. A mark_skipped here would lose the
        mail permanently for anyone whose day-3 mark lands after 21:00."""
        from datetime import datetime as _dt, timedelta
        from unittest.mock import patch as _patch
        from extensions import db
        from models import User, ScheduledEmail
        from services.email.onboarding_sequence import (
            schedule_onboarding, dispatch_due,
        )
        monkeypatch.setenv("PIVOX_ONBOARDING_SEQUENCE_ENABLED", "true")
        monkeypatch.setenv("PIVOX_PAID_PLANS_ENABLED", "false")
        u = make_user(email="night_defer@test.com")
        base = _dt(2026, 5, 19, 2, 0, 0)          # 11:00 KST

        with app.app_context():
            schedule_onboarding(db.session.get(User, u["id"]), now=base)
            db.session.commit()

        night = base + timedelta(days=10)
        night = night.replace(hour=12)             # 21:00 KST
        with app.app_context(), _patch(
            "services.email.onboarding_sequence._send_one", return_value=True,
        ) as send:
            stats = dispatch_due(now=night)
            assert stats["deferred_night"] >= 1
            # welcome is transactional — the ban does not touch it.
            assert send.call_count == 1

        with app.app_context():
            row = (ScheduledEmail.query
                   .filter_by(user_id=u["id"], email_type="d3_guide").first())
            assert row is not None
            assert row.sent_at is None, "night ban must not consume the row"
            assert not getattr(row, "skipped_reason", None), (
                "row was skipped, not deferred — it can never be sent now"
            )

    def test_it_sends_once_morning_comes(self, app, make_user, monkeypatch):
        from datetime import datetime as _dt, timedelta
        from unittest.mock import patch as _patch
        from extensions import db
        from models import User
        from services.email.onboarding_sequence import (
            schedule_onboarding, dispatch_due,
        )
        monkeypatch.setenv("PIVOX_ONBOARDING_SEQUENCE_ENABLED", "true")
        monkeypatch.setenv("PIVOX_PAID_PLANS_ENABLED", "false")
        u = make_user(email="night_then_day@test.com")
        base = _dt(2026, 5, 19, 2, 0, 0)

        with app.app_context():
            schedule_onboarding(db.session.get(User, u["id"]), now=base)
            db.session.commit()

        due = base + timedelta(days=10)
        with app.app_context(), _patch(
            "services.email.onboarding_sequence._send_one", return_value=True,
        ) as send:
            dispatch_due(now=due.replace(hour=12))   # 21:00 KST — deferred
            dispatch_due(now=due.replace(hour=2))    # 11:00 KST — goes
            assert send.call_count == 2
