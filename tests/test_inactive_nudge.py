"""24h inactive-nudge dispatcher — Wave G C-S2 tests.

Covers
------
1. Dispatcher flag off → no sends (``flag_off`` summary line).
2. CS1 consent flag off → no sends (sender gate would block; we
   short-circuit at the dispatcher to save the query budget).
3. Window selection: only users whose ``created_at`` lies in
   ``[now-25h, now-24h)`` are picked up.
4. Active user (has Position / TradeHistory / Artifact) is skipped
   even when in the window.
5. ``inactive_nudge_sent_at`` is set after a successful send → next
   run skips the same user (idempotency).
6. Per-user consent missing → sender returns False → ``skipped_send``
   counter increments and the timestamp is NOT written.
7. ``is_simulated`` users are filtered out at the query level.

All transports mocked — no real provider calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_user_signed_at(app, *, created_hours_ago: float,
                          consent_information: bool = True,
                          consent_marketing: bool = True,
                          is_simulated: bool = False,
                          email: str | None = None):
    """Create a User with ``created_at`` rolled back to a precise offset.

    The dispatcher's window query keys off ``created_at``; we backdate
    by writing the column directly post-commit.
    """
    from extensions import db
    from models import User

    addr = email or f"u{created_hours_ago}-{consent_information}-" \
                    f"{is_simulated}@test.com"

    with app.app_context():
        u = User(email=addr, name="Tester", subscription_tier="free")
        u.set_pw("password123")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        u.created_at = now - timedelta(hours=created_hours_ago)
        u.marketing_consent_at = now - timedelta(days=1)
        if consent_information:
            u.marketing_consent_information_at = now - timedelta(days=1)
        # 2026-09-07: the nudge is 광고성 now, so MARKETING consent is what
        # actually gates it. INFORMATION alone no longer suffices — pinned by
        # test_information_consent_alone_is_not_enough below.
        if consent_marketing:
            u.marketing_consent_marketing_at = now - timedelta(days=1)
        u.is_simulated = is_simulated
        db.session.add(u)
        db.session.commit()
        return u.id


def _patch_transport_succeed():
    return patch.multiple(
        "services.email.sender.EmailSender",
        _send_via_sendgrid=lambda *a, **kw: True,
        _send_via_brevo=lambda *a, **kw: True,
        _send_via_smtp=lambda *a, **kw: True,
    )


def _daytime():
    """Force the §61의2 night gate open.

    2026-09-07: the nudge was reclassified 광고성, which pulls in the
    21:00–08:00 KST send ban. The window-selection tests below assert which
    USERS get picked, not what time it is — without this they pass by day and
    fail by night (they did: the suite went red at 06:49 KST). The gate has
    its own test at the bottom of this file.
    """
    return patch(
        "services.email.retention_sequence.is_night_kst",
        lambda *_a, **_kw: False,
    )


def _flags_on(monkeypatch):
    monkeypatch.setenv("PIVOX_INACTIVE_NUDGE_ENABLED", "true")
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")


# ── 1. dispatcher flag off ──────────────────────────────────────────────────

def test_dispatcher_flag_off_short_circuits(app, monkeypatch):
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    monkeypatch.setenv("PIVOX_INACTIVE_NUDGE_ENABLED", "false")
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    _make_user_signed_at(app, created_hours_ago=24.5)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["flag_off"] == 1
    assert s["sent"] == 0
    assert s["window_users"] == 0  # never even queried


# ── 2. CS1 flag off ─────────────────────────────────────────────────────────

def test_cs1_flag_off_short_circuits(app, monkeypatch):
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    monkeypatch.setenv("PIVOX_INACTIVE_NUDGE_ENABLED", "true")
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "false")
    _make_user_signed_at(app, created_hours_ago=24.5)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["flag_off"] == 1
    assert s["sent"] == 0


# ── 3. window selection ─────────────────────────────────────────────────────

def test_only_24h_to_25h_window_users_picked_up(app, monkeypatch):
    """Three users: too-young (12h ago), in-window (24.5h ago),
    too-old (26h ago). Only the 24.5h one is included.
    """
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    _flags_on(monkeypatch)

    _make_user_signed_at(app, created_hours_ago=12, email="young@test.com")
    in_window_id = _make_user_signed_at(
        app, created_hours_ago=24.5, email="in@test.com",
    )
    _make_user_signed_at(app, created_hours_ago=26, email="old@test.com")

    with app.app_context():
        with _patch_transport_succeed(), _daytime():
            s = run_once()
    assert s["window_users"] == 1
    assert s["sent"] == 1

    # And the timestamp was written on the right row.
    from models import User
    with app.app_context():
        u = User.query.get(in_window_id)
        assert u.inactive_nudge_sent_at is not None


# ── 4. active user is skipped ───────────────────────────────────────────────

def test_user_with_position_is_skipped_as_active(app, monkeypatch):
    from extensions import db
    from models import Position
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    _flags_on(monkeypatch)
    uid = _make_user_signed_at(app, created_hours_ago=24.5)

    with app.app_context():
        db.session.add(Position(
            user_id=uid, ticker="AAPL", shares=10.0,
            avg_cost=150.0, buy_fx_rate=1.0,
        ))
        db.session.commit()

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["window_users"] == 1
    assert s["skipped_active"] == 1
    assert s["sent"] == 0


# ── 5. idempotency (sent_at filter) ─────────────────────────────────────────

def test_user_already_nudged_is_skipped_on_next_run(app, monkeypatch):
    from extensions import db
    from models import User
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    _flags_on(monkeypatch)
    uid = _make_user_signed_at(app, created_hours_ago=24.5)

    # First run sends + writes the timestamp.
    with app.app_context():
        with _patch_transport_succeed(), _daytime():
            s1 = run_once()
    assert s1["sent"] == 1

    # Second run — same window, but the user is no longer NULL.
    with app.app_context():
        with _patch_transport_succeed(), _daytime():
            s2 = run_once()
    assert s2["window_users"] == 0
    assert s2["sent"] == 0


# ── 6. consent missing → sender blocks ──────────────────────────────────────

def test_user_without_information_consent_skipped(app, monkeypatch):
    """User has no ``marketing_consent_information_at`` → sender's
    category gate blocks the send → ``skipped_send`` counter ticks
    and the timestamp stays NULL (so a future consent grant would
    let the next run pick them up).
    """
    from models import User
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    _flags_on(monkeypatch)
    uid = _make_user_signed_at(
        app, created_hours_ago=24.5, consent_information=False,
    )

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["window_users"] == 1
    assert s["sent"] == 0
    assert s["skipped_send"] == 1

    with app.app_context():
        u = User.query.get(uid)
        assert u.inactive_nudge_sent_at is None


# ── 7. is_simulated filter ─────────────────────────────────────────────────

def test_simulated_user_excluded_from_window(app, monkeypatch):
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    _flags_on(monkeypatch)
    _make_user_signed_at(
        app, created_hours_ago=24.5, is_simulated=True,
    )

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
    assert s["window_users"] == 0
    assert s["sent"] == 0


# ── 8. 광고성 재분류 (2026-09-07) ────────────────────────────────────────────
#
# The nudge moved INFORMATION → MARKETING because it is sent to users who have
# recorded nothing: there is no fact of theirs to state, so what remains is a
# request to come back — 광고성 정보 under 정통망법 §50 ①. These pin the régime
# that reclassification pulls in, because every one of them is the kind of
# thing that silently regresses when someone edits a template.

def test_information_consent_alone_is_not_enough(app, monkeypatch):
    """A user who consented to 정보성 but not 광고성 must NOT be mailed."""
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    _flags_on(monkeypatch)
    _make_user_signed_at(
        app, created_hours_ago=24.5,
        consent_information=True, consent_marketing=False,
        email="info_only@test.com",
    )

    with app.app_context():
        with _patch_transport_succeed(), _daytime():
            s = run_once()
    assert s["window_users"] == 1      # picked by the window…
    assert s["sent"] == 0              # …and refused by the category gate
    assert s["skipped_send"] == 1


def test_night_gate_blocks_the_send(app, monkeypatch):
    """시행령 §61의2 — nothing goes out 21:00–08:00 KST."""
    from scripts.nightly.inactive_nudge_dispatcher import run_once

    _flags_on(monkeypatch)
    _make_user_signed_at(app, created_hours_ago=24.5, email="night@test.com")

    night = patch(
        "services.email.retention_sequence.is_night_kst",
        lambda *_a, **_kw: True,
    )
    with app.app_context():
        with _patch_transport_succeed(), night:
            s = run_once()
    assert s["window_users"] == 1
    assert s["sent"] == 0


def test_rendered_body_carries_the_ad_marker_and_sender_block(app):
    """(광고) marker + 시행령 §62 ① identity block survive rendering."""
    from services.customer.inactive_nudge import _render_email

    html, text = _render_email(
        "Tester", unsubscribe_url="https://example.test/unsub?token=abc",
    )
    for body in (html, text):
        assert "(광고)" in body[:400], "marker must sit in the body head"
        assert "459-01-03808" in body          # 사업자등록번호
        assert "support@pivoxquant.com" in body
        assert "example.test/unsub" in body    # 수신거부 링크 치환됨
        assert "{{unsubscribe_url}}" not in body


def test_rendered_body_passes_the_legal_scan(app):
    """The send path asserts on the rendered body — including comments."""
    from services.legal import assert_legal_safe
    from services.customer.inactive_nudge import _render_email

    html, text = _render_email("Tester", unsubscribe_url="https://x.test/u")
    assert_legal_safe(html, "inactive_nudge/html")
    assert_legal_safe(text, "inactive_nudge/txt")
