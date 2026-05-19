"""OAuth failure detector — Wave I C-1 tests.

Covers
------
1. Sub-threshold (2 fails / 1h) → no alert.
2. At-threshold (3 fails / 1h) → 1 candidate + email + dedup marker.
3. Successful login between fails breaks the count? No — we count
   fails only. Verify success rows do NOT count toward threshold.
4. Marker dedup: a candidate alerted now is NOT re-listed within 24h.
5. Window: fails older than 1h are NOT counted.
6. Daily cap: ``OAUTH_FAILURE_ALERT_DAILY_CAP=0`` halts all alerts.
7. Cross-email isolation: A's failures do NOT trigger an alert on B.

All transports mocked — no real Slack post, no real SendGrid call.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _seed_events(app, *, email: str, count: int, provider: str = "google",
                  event_type: str = "fail",
                  minutes_ago: float = 5,
                  fail_reason: str | None = "google_failed"):
    """Insert ``count`` AuthEvent rows backdated by ``minutes_ago`` minutes."""
    from extensions import db
    from models import AuthEvent

    with app.app_context():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(count):
            ev = AuthEvent(
                email=email,
                provider=provider,
                event_type=event_type,
                fail_reason=fail_reason if event_type == "fail" else None,
                created_at=now - timedelta(minutes=minutes_ago + i * 0.1),
            )
            db.session.add(ev)
        db.session.commit()


def _patch_transport_succeed():
    return patch.multiple(
        "services.email.sender.EmailSender",
        _send_via_sendgrid=lambda *a, **kw: True,
        _send_via_brevo=lambda *a, **kw: True,
        _send_via_smtp=lambda *a, **kw: True,
    )


@pytest.fixture(autouse=True)
def _enable_sendgrid_env(monkeypatch):
    """EmailSender skips the SendGrid tier when SENDGRID_API_KEY is unset.

    Tests mock ``_send_via_sendgrid`` to a truthy lambda but the upstream
    predicate gate also has to be true. Conftest scrubs the env so we
    re-enable it for the test process here.
    """
    monkeypatch.setenv("SENDGRID_API_KEY", "test-sendgrid-key")


def _make_user(app, email: str):
    """Provision a User row for the email so EmailSender resolves it."""
    from extensions import db
    from models import User

    with app.app_context():
        u = User(email=email, name="Tester")
        u.set_pw("password123")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        u.marketing_consent_at = now - timedelta(days=1)
        db.session.add(u)
        db.session.commit()


# ── 1. sub-threshold ────────────────────────────────────────────────────────

def test_sub_threshold_no_alert(app):
    from scripts.nightly.oauth_failure_check import run_once

    _make_user(app, "a@test.com")
    _seed_events(app, email="a@test.com", count=2)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["candidates"] == 0
    assert s["alerted"] == 0


# ── 2. at-threshold ─────────────────────────────────────────────────────────

def test_at_threshold_triggers_alert(app):
    from scripts.nightly.oauth_failure_check import run_once
    from models import AuthEvent

    _make_user(app, "b@test.com")
    _seed_events(app, email="b@test.com", count=3)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
        assert s["candidates"] == 1
        assert s["alerted"] == 1
        # Dedup marker inserted with the sentinel fail_reason
        from scripts.nightly.oauth_failure_check import DEDUP_MARKER_REASON
        n = AuthEvent.query.filter_by(
            email="b@test.com", fail_reason=DEDUP_MARKER_REASON,
        ).count()
        assert n == 1


# ── 3. success events don't count ───────────────────────────────────────────

def test_success_rows_not_counted(app):
    """3 fails + 5 successes = 1 candidate (only fails count)."""
    from scripts.nightly.oauth_failure_check import run_once

    _make_user(app, "c@test.com")
    _seed_events(app, email="c@test.com", count=3, event_type="fail")
    _seed_events(app, email="c@test.com", count=5, event_type="success",
                 fail_reason=None)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["candidates"] == 1


# ── 4. dedup ────────────────────────────────────────────────────────────────

def test_dedup_window_24h(app):
    """Two back-to-back runs alert once, not twice."""
    from scripts.nightly.oauth_failure_check import run_once

    _make_user(app, "d@test.com")
    _seed_events(app, email="d@test.com", count=3)

    with app.app_context():
        with _patch_transport_succeed():
            s1 = run_once()
            s2 = run_once()
    assert s1["alerted"] == 1
    # Second pass: the marker excludes the email from candidates.
    assert s2["candidates"] == 0
    assert s2["alerted"] == 0


# ── 5. window ───────────────────────────────────────────────────────────────

def test_old_fails_excluded_from_window(app):
    """3 fails from 2h ago → not in 1h window → 0 candidates."""
    from scripts.nightly.oauth_failure_check import run_once

    _make_user(app, "e@test.com")
    _seed_events(app, email="e@test.com", count=3, minutes_ago=125)  # > 60min

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["candidates"] == 0


# ── 6. daily cap ────────────────────────────────────────────────────────────

def test_daily_cap_zero_blocks_all(app, monkeypatch):
    from scripts.nightly.oauth_failure_check import run_once

    monkeypatch.setenv("OAUTH_FAILURE_ALERT_DAILY_CAP", "0")

    _make_user(app, "f@test.com")
    _seed_events(app, email="f@test.com", count=3)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    # Daily cap of 0 → never alert (the candidate is found but not actioned).
    assert s["candidates"] == 1
    assert s["alerted"] == 0
    assert s["daily_cap_reached"] >= 1


# ── 7. cross-email isolation ────────────────────────────────────────────────

def test_one_users_fails_do_not_trigger_another(app):
    from scripts.nightly.oauth_failure_check import run_once

    _make_user(app, "g@test.com")
    _make_user(app, "h@test.com")
    _seed_events(app, email="g@test.com", count=3)  # triggers
    _seed_events(app, email="h@test.com", count=1)  # does not

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    # Exactly one candidate (g), not two.
    assert s["candidates"] == 1


# ── 8. logging hook is non-fatal ────────────────────────────────────────────

def test_log_auth_event_helper_never_raises(app):
    """Smoke test: routes.auth._log_auth_event must not propagate on DB error."""
    from routes.auth import _log_auth_event

    with app.app_context():
        # Pass garbage that would otherwise CHECK-constraint reject;
        # helper normalizes provider/event_type to valid values.
        _log_auth_event(None, "garbage-provider", "garbage-event")
        # If we reach here without exception, contract is satisfied.
