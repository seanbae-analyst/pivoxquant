"""tests/test_retention_sequence.py — D+7/D+30 MARKETING retention.

Wave G C-R1 (2026-05-19).

Covers the 7 hard guardrails enumerated in
``services.email.retention_sequence``:

1.  ``is_night_kst`` — 21:00–08:00 KST window
    (시행령 §61의2). Includes the edges 07:59 / 08:00 / 20:59 / 21:00.
2.  "(광고)" marker is present in every retention subject + body
    (시행령 §62 ②) — both HTML and text templates.
3.  Every retention subject + body passes ``assert_legal_safe`` —
    no buy / sell / hold / 추천 / 매수 / 매도 / 조언 / coach vocabulary
    (자본시장법 §49 trigger).
4.  ``schedule_retention`` enqueues nothing when the feature flag is off.
5.  ``schedule_retention`` enqueues nothing when MARKETING consent is
    missing or has been revoked.
6.  Consent revoked between enqueue and dispatch blocks the send
    (dispatch-time re-check).
7.  Render footer carries all 4 elements required by 시행령 §62 ① —
    사업자명 + 사업자등록번호 + 연락처 + 수신거부 + 수신동의 일시.

Plus dispatcher integration:
* MARKETING category is the value passed to ``EmailSender.send``
  (INFORMATION-only consent is therefore insufficient).
* Night-window rows are LEFT pending (not stamped) so the next
  ≥ 08:00 KST tick picks them up.
* Onboarding's ``dispatch_due`` no longer consumes retention rows
  (regression guard for the type-filter we added).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest


KST = ZoneInfo("Asia/Seoul")


# ── helpers ──────────────────────────────────────────────────────────────────


def _enable(monkeypatch):
    monkeypatch.setenv("PIVOX_RETENTION_ENABLED", "true")


def _disable(monkeypatch):
    monkeypatch.setenv("PIVOX_RETENTION_ENABLED", "false")


def _grant_marketing_consent(app, user_id: int, *, at: datetime | None = None):
    """Grant MARKETING consent on the User row (mirrors routes/consents.py)."""
    from extensions import db
    from models import User
    at = at or datetime(2026, 5, 19, 12, 0, 0)  # UTC naive — project convention
    with app.app_context():
        user = db.session.get(User, user_id)
        user.marketing_consent_marketing_at = at
        user.marketing_consent_marketing_revoked_at = None
        # Also flip the global marketing_consent_at — EmailSender's
        # marketing_consent_at default-deny gate (sender.py L242) requires
        # the flag-1 column to be set, otherwise every send is blocked
        # regardless of the per-category split.
        user.marketing_consent_at = at
        user.marketing_consent_revoked_at = None
        db.session.commit()


def _row_count(app, user_id: int) -> int:
    from models import ScheduledEmail
    with app.app_context():
        return ScheduledEmail.query.filter_by(user_id=user_id).count()


def _retention_rows(app, user_id: int):
    from models import ScheduledEmail
    with app.app_context():
        return (
            ScheduledEmail.query
            .filter_by(user_id=user_id)
            .order_by(ScheduledEmail.scheduled_send_at.asc())
            .all()
        )


# ── 1. KST night-time block (§61의2) ─────────────────────────────────────────


class TestRetentionKstNightBlock21To08:
    """Guardrail #1 — is_night_kst edges."""

    def test_blocks_at_21_00(self):
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 21, 0, 0, tzinfo=KST)) is True

    def test_blocks_at_22_00(self):
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 22, 0, 0, tzinfo=KST)) is True

    def test_blocks_at_07_59(self):
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 7, 59, 0, tzinfo=KST)) is True

    def test_blocks_at_00_00(self):
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 0, 0, 0, tzinfo=KST)) is True

    def test_allows_at_08_00(self):
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 8, 0, 0, tzinfo=KST)) is False

    def test_allows_at_20_59(self):
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 20, 59, 0, tzinfo=KST)) is False

    def test_allows_at_12_00(self):
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 12, 0, 0, tzinfo=KST)) is False

    def test_utc_naive_treated_as_utc(self):
        """A naive datetime is assumed UTC. 22:00 UTC = 07:00 KST → night."""
        from services.email.retention_sequence import is_night_kst
        assert is_night_kst(datetime(2026, 5, 19, 22, 0, 0)) is True
        # 04:00 UTC = 13:00 KST → daytime.
        assert is_night_kst(datetime(2026, 5, 19, 4, 0, 0)) is False


# ── 2. (광고) marker (§62 ②) ─────────────────────────────────────────────────


class TestRetentionTemplateHasAdMarker:
    """Guardrail #2 — subject + body first line must contain '(광고)'."""

    def test_sequence_subjects_carry_ad_marker(self):
        from services.email.retention_sequence import SEQUENCE
        for step in SEQUENCE:
            assert "(광고)" in step.subject, (
                f"SEQUENCE step {step.slug!r} subject missing '(광고)' marker"
            )

    def test_template_bodies_carry_ad_marker_in_head(self):
        template_dir = (
            Path(__file__).resolve().parent.parent
            / "services" / "email" / "templates" / "retention"
        )
        for path in sorted(template_dir.iterdir()):
            if path.suffix not in (".html", ".txt"):
                continue
            head = path.read_text(encoding="utf-8")[:400]
            assert "(광고)" in head, (
                f"{path.name} missing '(광고)' marker in first 400 chars "
                f"— violates 시행령 §62 ②"
            )

    def test_all_four_templates_present(self):
        template_dir = (
            Path(__file__).resolve().parent.parent
            / "services" / "email" / "templates" / "retention"
        )
        expected = {
            "d7_summary.html", "d7_summary.txt",
            "d30_summary.html", "d30_summary.txt",
        }
        actual = {p.name for p in template_dir.iterdir() if p.is_file()}
        assert expected.issubset(actual), (
            f"missing retention templates: {expected - actual}"
        )


# ── 3. legal-safe vocabulary (자본시장법 §49) ────────────────────────────────


class TestRetentionForbiddenTermsBlocked:
    """Guardrail #5 — assert_legal_safe over subjects + bodies."""

    def test_sequence_subjects_pass_legal_safe(self):
        from services.email.retention_sequence import SEQUENCE
        from services.legal import assert_legal_safe
        for step in SEQUENCE:
            # Will raise ValueError on a forbidden term.
            assert_legal_safe(step.subject, f"SEQUENCE.{step.slug}.subject")

    def test_template_bodies_pass_legal_safe(self):
        from services.legal import assert_legal_safe
        template_dir = (
            Path(__file__).resolve().parent.parent
            / "services" / "email" / "templates" / "retention"
        )
        for path in sorted(template_dir.iterdir()):
            if path.suffix not in (".html", ".txt"):
                continue
            text = path.read_text(encoding="utf-8")
            assert_legal_safe(text, f"template/{path.name}")


# ── 4. consent default OFF ───────────────────────────────────────────────────


class TestConsentDefaultOff:
    """Guardrail #7 — no enqueue when MARKETING consent is missing."""

    def test_user_without_consent_enqueues_nothing(
        self, app, make_user, monkeypatch,
    ):
        _enable(monkeypatch)
        u = make_user(email="ret_noconsent@test.com")
        # Intentionally do NOT call _grant_marketing_consent.

        from extensions import db
        from models import User
        from services.email.retention_sequence import schedule_retention

        with app.app_context():
            user = db.session.get(User, u["id"])
            stats = schedule_retention(user, now=datetime(2026, 5, 19, 12, 0, 0))
            db.session.commit()

        assert stats == {
            "enqueued": 0, "existed": 0, "flag_off": 0, "no_consent": 1,
        }
        assert _row_count(app, u["id"]) == 0

    def test_user_with_consent_enqueues_two_rows(
        self, app, make_user, monkeypatch,
    ):
        _enable(monkeypatch)
        u = make_user(email="ret_consent@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.retention_sequence import (
            schedule_retention, SEQUENCE,
        )

        with app.app_context():
            user = db.session.get(User, u["id"])
            now = datetime(2026, 5, 19, 12, 0, 0)
            stats = schedule_retention(user, now=now)
            db.session.commit()

        assert stats == {
            "enqueued": 2, "existed": 0, "flag_off": 0, "no_consent": 0,
        }

        rows = _retention_rows(app, u["id"])
        assert [r.email_type for r in rows] == [s.slug for s in SEQUENCE]
        assert [r.email_category for r in rows] == ["marketing", "marketing"]
        assert rows[0].scheduled_send_at == now + timedelta(days=7)
        assert rows[1].scheduled_send_at == now + timedelta(days=30)
        for r in rows:
            assert r.sent_at is None
            assert r.skipped_reason is None
            assert r.idempotency_key == f"u{u['id']}:{r.email_type}"


# ── 5. dispatch-time consent re-check ────────────────────────────────────────


class TestConsentRevokeBlocksDispatch:
    """Guardrail #6 — revoke after enqueue must short-circuit send."""

    def test_revoke_between_enqueue_and_dispatch_skips(
        self, app, make_user, monkeypatch,
    ):
        _enable(monkeypatch)
        u = make_user(email="ret_revoke@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.retention_sequence import (
            schedule_retention, dispatch_retention,
        )

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            user = db.session.get(User, u["id"])
            schedule_retention(user, now=base)
            db.session.commit()
        assert _row_count(app, u["id"]) == 2

        # Revoke MARKETING consent.
        with app.app_context():
            user = db.session.get(User, u["id"])
            user.marketing_consent_marketing_revoked_at = (
                base + timedelta(hours=1)
            )
            db.session.commit()

        # Day-40 dispatch — both rows are due. Use a daytime-KST instant
        # (03:00 UTC = 12:00 KST) so the night gate doesn't fire ahead
        # of the consent gate we want to exercise. Patch EmailSender at
        # its canonical module so the test can't accidentally hit a
        # provider; assert it is NEVER called because the consent re-check
        # inside _send_one fires first.
        day_utc = datetime(2026, 6, 30, 3, 0, 0)  # 12:00 KST
        with app.app_context(), \
             patch("services.email.EmailSender") as Sender:
            instance = Sender.return_value
            stats = dispatch_retention(now=day_utc)
            instance.send.assert_not_called()

        assert stats["due"] == 2
        assert stats["sent"] == 0
        assert stats["skipped_no_consent"] == 2

        rows = _retention_rows(app, u["id"])
        assert all(r.sent_at is None for r in rows)
        assert all(r.skipped_reason == "no_consent_or_provider" for r in rows)


# ── 6. feature flag off (no schedule, no dispatch) ───────────────────────────


class TestFlagOffNoScheduleNoDispatch:
    """Guardrail #4 — PIVOX_RETENTION_ENABLED=false short-circuits."""

    def test_flag_off_schedule_writes_no_rows(self, app, make_user, monkeypatch):
        _disable(monkeypatch)
        u = make_user(email="ret_flagoff_sched@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User
        from services.email.retention_sequence import schedule_retention

        with app.app_context():
            user = db.session.get(User, u["id"])
            stats = schedule_retention(user)
            db.session.commit()

        assert stats["flag_off"] == 1
        assert stats["enqueued"] == 0
        assert _row_count(app, u["id"]) == 0

    def test_flag_off_dispatch_marks_rows_as_feature_flag_off(
        self, app, make_user, monkeypatch,
    ):
        # Enqueue while ON, dispatch while OFF.
        _enable(monkeypatch)
        u = make_user(email="ret_flagoff_dispatch@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.retention_sequence import (
            schedule_retention, dispatch_retention,
        )

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            user = db.session.get(User, u["id"])
            schedule_retention(user, now=base)
            db.session.commit()

        _disable(monkeypatch)

        # Dispatch at noon UTC = 21:00 KST (night). The flag-off branch
        # must run FIRST, before the night gate; otherwise we'd never
        # close rows once the flag stays off + a tick fires at night.
        with app.app_context(), \
             patch("services.email.retention_sequence._send_one") as send:
            stats = dispatch_retention(now=base + timedelta(days=40))
            send.assert_not_called()

        assert stats["due"] == 2
        assert stats["skipped_flag_off"] == 2
        assert stats["sent"] == 0
        rows = _retention_rows(app, u["id"])
        assert all(r.skipped_reason == "feature_flag_off" for r in rows)


# ── 7. sender footer carries 4 mandated elements (§62 ①) ─────────────────────


class TestFooterHas4Elements:
    """Guardrail #7 — 사업자명 + 등록번호 + 연락처 + 수신거부 + 수신동의."""

    def test_rendered_html_carries_4_elements(self, app, make_user, monkeypatch):
        _enable(monkeypatch)
        u = make_user(email="ret_footer@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User
        from services.email.retention_sequence import _render
        from services.email_token import build_unsubscribe_url

        with app.app_context():
            user = db.session.get(User, u["id"])
            unsub = build_unsubscribe_url(user.id, kind="all")
            # `record` is required: the body is the reader's counts, so a
            # render without them would be a mail with a blank content
            # section. This test is about the §62 footer, so any non-empty
            # record will do.
            html, txt = _render(
                "d7_summary", user=user, unsubscribe_url=unsub,
                record={"lines": ["지난 7일 동안 체결 기록은 2건입니다."]},
            )

        # 1 — 사업자명
        assert "PivoxQuant" in html and "PivoxQuant" in txt
        # 2 — 사업자등록번호 (459-01-03808 issued 2026-05-08 per memory)
        assert "459-01-03808" in html and "459-01-03808" in txt
        # 3 — 연락처
        assert "support@pivoxquant.com" in html
        assert "support@pivoxquant.com" in txt
        # 4 — 수신거부 link (HMAC-signed unsubscribe URL)
        assert unsub in html and unsub in txt
        # Bonus — 수신동의 timestamp (rendered in KST locale)
        assert "KST" in html and "KST" in txt
        # And we expect the source label "회원가입 시 동의".
        assert "회원가입 시 동의" in html
        assert "회원가입 시 동의" in txt


# ── 8. MARKETING category not satisfied by INFORMATION consent only ──────────


class TestMarketingCategoryConsentCheck:
    """Guardrail #6/#7 — INFORMATION consent does NOT unlock MARKETING."""

    def test_information_only_does_not_unlock_marketing(
        self, app, make_user, monkeypatch,
    ):
        _enable(monkeypatch)
        u = make_user(email="ret_info_only@test.com")

        from extensions import db
        from models import User
        from services.email.retention_sequence import schedule_retention

        # Grant INFORMATION but NOT MARKETING.
        at = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            user = db.session.get(User, u["id"])
            user.marketing_consent_at = at
            user.marketing_consent_information_at = at
            db.session.commit()

        with app.app_context():
            user = db.session.get(User, u["id"])
            stats = schedule_retention(user, now=at)
            db.session.commit()

        assert stats["no_consent"] == 1
        assert stats["enqueued"] == 0
        assert _row_count(app, u["id"]) == 0


# ── 9. night window leaves rows pending (does NOT close them) ────────────────


class TestNightWindowLeavesRowsPending:
    """Dispatch during 21:00-08:00 KST must NOT stamp rows."""

    def test_night_dispatch_does_not_stamp_rows(
        self, app, make_user, monkeypatch,
    ):
        _enable(monkeypatch)
        u = make_user(email="ret_night@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.retention_sequence import (
            schedule_retention, dispatch_retention,
        )

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            user = db.session.get(User, u["id"])
            schedule_retention(user, now=base)
            db.session.commit()

        # 14:00 UTC = 23:00 KST → night.
        night_utc = datetime(2026, 6, 30, 14, 0, 0)

        with app.app_context(), \
             patch("services.email.retention_sequence._send_one") as send:
            stats = dispatch_retention(now=night_utc)
            send.assert_not_called()

        assert stats["due"] == 2
        assert stats["skipped_night"] == 2
        assert stats["sent"] == 0
        rows = _retention_rows(app, u["id"])
        # Critical: rows MUST stay pending (sent_at NULL, skipped_reason NULL).
        for r in rows:
            assert r.sent_at is None
            assert r.skipped_reason is None

        # Re-run at 23:00 UTC = 08:00 KST next day (allowed). _send_one
        # still patched but now returns True so we stamp sent_at.
        morning_utc = datetime(2026, 6, 30, 23, 0, 0)
        with app.app_context(), \
             patch(
                 "services.email.retention_sequence._send_one",
                 return_value=True,
             ) as send:
            stats2 = dispatch_retention(now=morning_utc)
            assert send.call_count == 2

        assert stats2["sent"] == 2
        rows2 = _retention_rows(app, u["id"])
        assert all(r.sent_at is not None for r in rows2)


# ── 10. dispatcher renders MARKETING category to EmailSender ─────────────────


def _seed_record(app, user_id: int, *, at: datetime) -> None:
    """Give the user something to reflect, so the send is not silenced.

    2026-09-07: retention mail bodies are the reader's OWN counts, and
    `_send_one` refuses to send when `build_record_summary` finds nothing
    (services/email/record_summary.py — the silence rule). A fixture with an
    empty record therefore produces zero sends, which is correct behaviour
    and not what these tests are exercising.
    """
    from extensions import db
    from models import TradeHistory

    with app.app_context():
        for i in range(3):
            db.session.add(TradeHistory(
                user_id=user_id,
                ticker="AAPL",
                action="BUY",
                shares=1.0,
                price_per_share=100.0,
                total_value=100.0,
                pnl=0.0,
                traded_at=at - timedelta(days=i + 1),
            ))
        db.session.commit()


class TestEmailSenderInvokedWithMarketing:
    """Send path must pass EmailCategory.MARKETING (not INFORMATION)."""

    def test_send_uses_marketing_category(self, app, make_user, monkeypatch):
        _enable(monkeypatch)
        u = make_user(email="ret_mk_category@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User
        from services.email.retention_sequence import (
            schedule_retention, dispatch_retention,
        )
        from services.email.sender import EmailCategory

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            user = db.session.get(User, u["id"])
            schedule_retention(user, now=base)
            db.session.commit()

        # The mail states the reader's own counts; without a record the send
        # is silenced by design. Seed fills inside both windows.
        day_utc = datetime(2026, 6, 30, 3, 0, 0)
        _seed_record(app, u["id"], at=day_utc)

        # 03:00 UTC = 12:00 KST (daytime). Patch EmailSender at its
        # canonical module and assert the kwargs the send path uses.
        with app.app_context(), \
             patch("services.email.EmailSender") as Sender:
            Sender.return_value.send.return_value = True
            dispatch_retention(now=day_utc)
            assert Sender.return_value.send.call_count == 2
            for call in Sender.return_value.send.call_args_list:
                kw = call.kwargs
                assert kw["email_category"] is EmailCategory.MARKETING
                assert "(광고)" in kw["subject"]


class TestSilenceRuleIsReportedHonestly:
    """The skip must be recorded as what it was, not as a consent failure.

    The first cut set `row.skipped_reason` directly and the dispatcher's
    else-branch overwrote it with "no_consent_or_provider", also ticking
    stats["skipped_no_consent"]. An operator reading that summary would
    conclude §50 consent plumbing was broken and go looking for a bug that
    does not exist.
    """

    def test_no_record_keeps_its_own_reason_and_counter(
        self, app, make_user, monkeypatch
    ):
        _enable(monkeypatch)
        u = make_user(email="ret_reason@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User, ScheduledEmail
        from services.email.retention_sequence import (
            schedule_retention, dispatch_retention,
        )

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            schedule_retention(db.session.get(User, u["id"]), now=base)
            db.session.commit()

        # No record seeded on purpose.
        day_utc = datetime(2026, 6, 30, 3, 0, 0)
        with app.app_context(), patch("services.email.EmailSender") as Sender:
            Sender.return_value.send.return_value = True
            stats = dispatch_retention(now=day_utc)

            assert Sender.return_value.send.call_count == 0
            assert stats["skipped_no_record"] >= 1
            # The consent bucket must stay clean — that is the whole point.
            assert stats["skipped_no_consent"] == 0

            rows = (
                ScheduledEmail.query
                .filter_by(user_id=u["id"])
                .filter(ScheduledEmail.skipped_reason.isnot(None))
                .all()
            )
            assert rows, "the row should be closed, not left pending"
            assert all(r.skipped_reason == "no_record" for r in rows), (
                [r.skipped_reason for r in rows]
            )


class TestSilenceRule:
    """No record → no mail. This is the contract, not an optimisation.

    These mails carry the reader's own counts (2026-09-07). When the window
    holds nothing, there is no fact to state, and filling the gap with
    encouragement is exactly the re-engagement nudge 정통망법 §50 treats as
    광고성 — the shape this redesign exists to leave behind. So the send is
    refused rather than padded.
    """

    def test_user_with_no_record_is_not_mailed(self, app, make_user, monkeypatch):
        _enable(monkeypatch)
        u = make_user(email="ret_silent@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User
        from services.email.retention_sequence import (
            schedule_retention, dispatch_retention,
        )

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            schedule_retention(db.session.get(User, u["id"]), now=base)
            db.session.commit()

        # Deliberately seed NOTHING. Daytime KST so the night gate is open —
        # the only thing that can stop this send is the silence rule.
        day_utc = datetime(2026, 6, 30, 3, 0, 0)
        with app.app_context(), patch("services.email.EmailSender") as Sender:
            Sender.return_value.send.return_value = True
            dispatch_retention(now=day_utc)
            assert Sender.return_value.send.call_count == 0

    def test_seeded_record_is_mailed_and_carries_the_counts(
        self, app, make_user, monkeypatch
    ):
        _enable(monkeypatch)
        u = make_user(email="ret_speaks@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User
        from services.email.retention_sequence import (
            schedule_retention, dispatch_retention,
        )

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            schedule_retention(db.session.get(User, u["id"]), now=base)
            db.session.commit()

        day_utc = datetime(2026, 6, 30, 3, 0, 0)
        _seed_record(app, u["id"], at=day_utc)

        with app.app_context(), patch("services.email.EmailSender") as Sender:
            Sender.return_value.send.return_value = True
            dispatch_retention(now=day_utc)
            assert Sender.return_value.send.call_count >= 1
            body = Sender.return_value.send.call_args_list[0].kwargs
            joined = f"{body.get('html_body','')}{body.get('txt_body','')}"
            # The reader's own number reached the rendered body — the whole
            # point. Three fills were seeded inside both windows.
            assert "체결 기록은 3건" in joined
            # And the slot was substituted, not shipped raw.
            assert "{{ record_txt }}" not in joined
            assert "{{ record_html }}" not in joined


# ── 11. onboarding dispatch does NOT consume retention rows ──────────────────


class TestOnboardingDoesNotConsumeRetentionRows:
    """Regression: onboarding's dispatch_due filters by SEQUENCE slugs."""

    def test_onboarding_dispatch_ignores_retention_rows(
        self, app, make_user, monkeypatch,
    ):
        monkeypatch.setenv("PIVOX_ONBOARDING_SEQUENCE_ENABLED", "true")
        _enable(monkeypatch)
        u = make_user(email="ret_isolation@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User
        from services.email.onboarding_sequence import dispatch_due
        from services.email.retention_sequence import schedule_retention

        base = datetime(2026, 5, 19, 12, 0, 0)
        with app.app_context():
            user = db.session.get(User, u["id"])
            schedule_retention(user, now=base)
            db.session.commit()

        # All retention rows due far in the future. Onboarding's dispatch
        # MUST pull zero rows (none are onboarding slugs).
        with app.app_context(), \
             patch("services.email.onboarding_sequence._send_one") as send:
            stats = dispatch_due(now=base + timedelta(days=60))
            send.assert_not_called()

        assert stats["due"] == 0

        # Retention rows are still pending.
        rows = _retention_rows(app, u["id"])
        assert len(rows) == 2
        for r in rows:
            assert r.sent_at is None
            assert r.skipped_reason is None


# ── 12. idempotent enqueue ───────────────────────────────────────────────────


class TestIdempotentEnqueue:
    def test_double_call_does_not_duplicate(self, app, make_user, monkeypatch):
        _enable(monkeypatch)
        u = make_user(email="ret_dup@test.com")
        _grant_marketing_consent(app, u["id"])

        from extensions import db
        from models import User
        from services.email.retention_sequence import schedule_retention

        with app.app_context():
            user = db.session.get(User, u["id"])
            stats1 = schedule_retention(user)
            db.session.commit()
            stats2 = schedule_retention(user)
            db.session.commit()

        assert stats1["enqueued"] == 2
        assert stats2["enqueued"] == 0
        assert stats2["existed"] == 2
        assert _row_count(app, u["id"]) == 2


# ── 13. Bug C#4 — retention drain SKIP LOCKED ────────────────────────────────


class TestPendingRetentionRowsSkipLocked:
    """_pending_retention_rows bypasses pending_due() with its own inline
    query, so it must carry its own ``FOR UPDATE SKIP LOCKED`` — otherwise
    two overlapping retention cron ticks claim the same row and double-send.
    """

    def _compiled_pg(self, query):
        from sqlalchemy.dialects import postgresql
        return str(
            query.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": False},
            )
        )

    def test_retention_query_has_for_update_skip_locked(self, app):
        from models import ScheduledEmail
        from services.email.retention_sequence import RETENTION_SLUGS
        with app.app_context():
            q = (
                ScheduledEmail.query
                .filter(ScheduledEmail.email_type.in_(RETENTION_SLUGS))
                .filter(ScheduledEmail.sent_at.is_(None))
                .filter(ScheduledEmail.skipped_reason.is_(None))
                .with_for_update(skip_locked=True)
            )
            sql = self._compiled_pg(q).upper()
            assert "FOR UPDATE" in sql
            assert "SKIP LOCKED" in sql

    def test_source_uses_skip_locked(self):
        import inspect
        from services.email.retention_sequence import _pending_retention_rows
        src = inspect.getsource(_pending_retention_rows)
        assert "with_for_update(skip_locked=True)" in src

    def test_returns_only_due_retention_rows_on_sqlite(self, app, make_user):
        """SKIP LOCKED is a no-op on SQLite — the drain must still return
        exactly the due ``retention_*`` rows and exclude future/non-retention.
        """
        from extensions import db
        from models import ScheduledEmail
        from services.email.retention_sequence import _pending_retention_rows
        uid = make_user(email="ret_skiplocked@test.com")["id"]
        now = datetime(2026, 1, 1, 12, 0, 0)
        with app.app_context():
            ScheduledEmail.enqueue(
                user_id=uid, email_type="retention_d7",
                email_category="marketing",
                scheduled_send_at=now - timedelta(minutes=5),  # due
            )
            ScheduledEmail.enqueue(
                user_id=uid, email_type="retention_d30",
                email_category="marketing",
                scheduled_send_at=now + timedelta(days=1),  # not yet due
            )
            ScheduledEmail.enqueue(
                user_id=uid, email_type="welcome",
                email_category="transactional",
                scheduled_send_at=now - timedelta(minutes=5),  # due but not retention
            )
            db.session.commit()
            rows = _pending_retention_rows(now=now)
            assert {r.email_type for r in rows} == {"retention_d7"}
