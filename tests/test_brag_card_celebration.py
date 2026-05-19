"""First-brag-card celebration — Wave G C-AC1 tests.

Covers
------
1. ``is_first_brag_card`` returns True on N=1, False on N=0 / N≥2.
2. ``maybe_send_first_brag_celebration`` sends on first card, skips on
   subsequent ones.
3. Idempotency marker prevents re-fire when ``_persist`` UPSERTs the
   same row twice (same month).
4. Category is TRANSACTIONAL — bypasses the C-S1 consent gate even
   when ``PIVOX_CS1_CONSENT_ENABLED=true`` and the user has no
   marketing-information consent timestamp.
5. Wrong artefact type (e.g. ``weekly_memo``) → no send.
6. Transport mocked throughout — no real provider calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_user(app, *, email="brag-celebrate@test.com", name="Tester",
               consent: bool = True):
    """Create a User with consent timestamps set so the v1 gate passes.

    The celebration uses ``EmailCategory.TRANSACTIONAL`` so even a user
    with no consent should receive the celebration — but the v1
    ``marketing_consent_at NULL → block`` gate sits *before* the
    category gate, so we keep a consent timestamp to isolate the
    category behaviour under test.
    """
    from extensions import db
    from models import User

    with app.app_context():
        u = User(email=email, name=name, subscription_tier="free")
        u.set_pw("password123")
        if consent:
            u.marketing_consent_at = (
                datetime.now(timezone.utc).replace(tzinfo=None)
                - timedelta(days=1)
            )
        db.session.add(u)
        db.session.commit()
        return u.id


def _make_brag_artifact(app, user_id, *, title="2026-04 Brag Card",
                        share_token="abc123", data_json=None):
    from extensions import db
    from models import Artifact

    payload = dict(data_json or {})
    payload.setdefault("referral_code", "REF42")

    with app.app_context():
        a = Artifact(
            user_id=user_id,
            type="brag_card",
            title=title,
            data_json=payload,
        )
        try:
            setattr(a, "share_token", share_token)
        except Exception:
            pass
        db.session.add(a)
        db.session.commit()
        return a.id


def _patch_transport_succeed():
    return patch.multiple(
        "services.email.sender.EmailSender",
        _send_via_sendgrid=lambda *a, **kw: True,
        _send_via_brevo=lambda *a, **kw: True,
        _send_via_smtp=lambda *a, **kw: True,
    )


# ── 1. is_first_brag_card ───────────────────────────────────────────────────

def test_is_first_brag_card_zero_returns_false(app):
    from services.customer.brag_card_celebration import is_first_brag_card

    uid = _make_user(app)
    with app.app_context():
        assert is_first_brag_card(uid) is False


def test_is_first_brag_card_one_returns_true(app):
    from services.customer.brag_card_celebration import is_first_brag_card

    uid = _make_user(app)
    _make_brag_artifact(app, uid)
    with app.app_context():
        assert is_first_brag_card(uid) is True


def test_is_first_brag_card_two_returns_false(app):
    from services.customer.brag_card_celebration import is_first_brag_card

    uid = _make_user(app)
    _make_brag_artifact(app, uid, title="2026-04 Brag Card")
    _make_brag_artifact(app, uid, title="2026-05 Brag Card",
                        share_token="abc456")
    with app.app_context():
        assert is_first_brag_card(uid) is False


# ── 2. maybe_send_first_brag_celebration ────────────────────────────────────

def test_celebration_sent_on_first_card(app, monkeypatch):
    """N=1 + SENDGRID_API_KEY → dispatch returns True, transport called."""
    from services.customer.brag_card_celebration import (
        maybe_send_first_brag_celebration,
    )
    from models import Artifact, User

    monkeypatch.setenv("SENDGRID_API_KEY", "test")

    uid = _make_user(app)
    aid = _make_brag_artifact(app, uid)

    with app.app_context():
        user = User.query.get(uid)
        artefact = Artifact.query.get(aid)
        with _patch_transport_succeed():
            ok = maybe_send_first_brag_celebration(user, artefact)
        assert ok is True


def test_celebration_skipped_when_not_first(app, monkeypatch):
    """N=2 — second brag card → no send, regardless of consent."""
    from services.customer.brag_card_celebration import (
        maybe_send_first_brag_celebration,
    )
    from models import Artifact, User

    monkeypatch.setenv("SENDGRID_API_KEY", "test")

    uid = _make_user(app)
    _make_brag_artifact(app, uid, title="2026-04 Brag Card")
    aid2 = _make_brag_artifact(app, uid, title="2026-05 Brag Card",
                               share_token="abc456")

    with app.app_context():
        user = User.query.get(uid)
        a2 = Artifact.query.get(aid2)
        with _patch_transport_succeed():
            ok = maybe_send_first_brag_celebration(user, a2)
        assert ok is False


def test_celebration_wrong_type_skipped(app, monkeypatch):
    """A non-brag artefact (e.g. weekly_memo) is never celebrated."""
    from extensions import db
    from models import Artifact, User
    from services.customer.brag_card_celebration import (
        maybe_send_first_brag_celebration,
    )

    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    uid = _make_user(app)

    with app.app_context():
        memo = Artifact(
            user_id=uid, type="weekly_memo",
            title="2026-04 Weekly Memo",
            data_json={"foo": "bar"},
        )
        db.session.add(memo)
        db.session.commit()
        memo_id = memo.id

        user = User.query.get(uid)
        a = Artifact.query.get(memo_id)
        with _patch_transport_succeed():
            ok = maybe_send_first_brag_celebration(user, a)
        assert ok is False


# ── 3. idempotency (upsert same month) ──────────────────────────────────────

def test_celebration_idempotent_on_same_month_upsert(app, monkeypatch):
    """Second call on the SAME first-card row must not re-fire.

    Simulates ``BragCardService.run_for_user`` being invoked twice for
    the same month: ``_persist`` UPSERTs the existing row so
    ``COUNT(*) == 1`` still, but the celebration marker has been
    written → second call returns False.
    """
    from services.customer.brag_card_celebration import (
        maybe_send_first_brag_celebration,
    )
    from models import Artifact, User

    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    uid = _make_user(app)
    aid = _make_brag_artifact(app, uid)

    with app.app_context():
        user = User.query.get(uid)
        a = Artifact.query.get(aid)
        with _patch_transport_succeed():
            first = maybe_send_first_brag_celebration(user, a)
        assert first is True

        # Re-fetch (mimics a second run_for_user call inside a new
        # session) and try again — marker should block.
        a2 = Artifact.query.get(aid)
        with _patch_transport_succeed():
            second = maybe_send_first_brag_celebration(user, a2)
        assert second is False


# ── 4. category is TRANSACTIONAL — bypasses C-S1 gate ──────────────────────

def test_celebration_bypasses_cs1_gate_when_flag_on(app, monkeypatch):
    """Even with ``PIVOX_CS1_CONSENT_ENABLED=true`` and no information
    consent timestamp, the TRANSACTIONAL category short-circuits the
    sender's per-category gate → the celebration still ships.
    """
    from services.customer.brag_card_celebration import (
        maybe_send_first_brag_celebration,
    )
    from models import Artifact, User

    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")

    uid = _make_user(app)  # marketing_consent_information_at = None
    aid = _make_brag_artifact(app, uid)

    with app.app_context():
        user = User.query.get(uid)
        a = Artifact.query.get(aid)
        with _patch_transport_succeed():
            ok = maybe_send_first_brag_celebration(user, a)
        assert ok is True


# ── 5. share URL composition ────────────────────────────────────────────────

def test_share_url_carries_token_referral_and_utm(app, monkeypatch):
    """Share URL must include the artefact's share_token, the user's
    referral code (from data_json), and the utm_source tag.
    """
    from services.customer.brag_card_celebration import _build_share_url
    from models import Artifact, User

    monkeypatch.setenv(
        "BRAG_CARD_SHARE_BASE_URL", "https://pivoxquant.com",
    )
    uid = _make_user(app)
    aid = _make_brag_artifact(
        app, uid, share_token="TOKENXYZ",
        data_json={"referral_code": "REFCODE"},
    )

    with app.app_context():
        user = User.query.get(uid)
        a = Artifact.query.get(aid)
        url = _build_share_url(user, a)
        assert "/share/brag/TOKENXYZ" in url
        assert "r=REFCODE" in url
        assert "utm_source=email_brag_celebration" in url
