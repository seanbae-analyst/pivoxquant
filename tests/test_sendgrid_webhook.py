"""SendGrid Event Webhook handler tests.

Pins the contract that PR #86 establishes for ``POST /webhooks/sendgrid``:

  * ``open`` events set ``Artifact.opened_at`` (first-open wins).
  * ``bounce`` events set ``Artifact.bounced_at``.
  * ``unsubscribe`` and ``group_unsubscribe`` events set
    ``Artifact.unsubscribed_at``.
  * Events whose ``sg_message_id`` doesn't map to an Artifact are
    silently ignored (transactional auth emails, dev sends, etc.).
  * Malformed payloads return 400, not 500.
  * When ``SENDGRID_WEBHOOK_PUBLIC_KEY`` is set, an invalid signature
    returns 403 (signature gate).

Following the project's "거짓보고 금지" rule, these tests use real DB
``Artifact`` rows via the ``make_user`` fixture and the global test
client. The Flask app is built by tests/conftest.py with the same
blueprint registration as production, so a successful POST through
``client`` exercises the full middleware → blueprint → handler stack.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Wave G-3 Bug #2 (2026-05-18): the webhook now hard-fails with 503 when
# SENDGRID_WEBHOOK_PUBLIC_KEY is unset, regardless of FLASK_ENV. Most tests
# in this file exercise *downstream event handling* (artifact column updates),
# not signature verification. To keep those tests black-box (no per-test
# signing), this autouse fixture installs a dummy public key and bypasses
# signature verification by default. The two tests that specifically cover
# signature behaviour (test_invalid_signature_returns_403,
# test_signature_required_when_env_absent, test_valid_signature_accepted)
# override the env / patch directly via their own monkeypatch calls.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _webhook_signature_bypass(request, monkeypatch):
    """Provide a default public key + bypass signature check for most tests.

    Tests that want to exercise the real signature gate opt out by name —
    they reset the env var themselves and (for valid-sig tests) re-patch
    ``_verify_signature`` after this fixture has run.
    """
    opt_out = {
        "test_signature_required_when_env_absent",
        "test_invalid_signature_returns_403",
        "test_valid_signature_accepted",
    }
    if request.node.name in opt_out:
        return
    monkeypatch.setenv("SENDGRID_WEBHOOK_PUBLIC_KEY", "dummy-key-for-tests")
    # Force-accept any signature on unsigned test POSTs.
    from services.email import webhook as _wh
    monkeypatch.setattr(_wh, "_verify_signature",
                        lambda *_args, **_kwargs: True)


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_artifact(app, user_id: int, sg_message_id: str = "abcDEF123"):
    """Insert one Artifact row tied to ``user_id`` with a known sg_message_id."""
    from extensions import db
    from models import Artifact

    with app.app_context():
        art = Artifact(
            user_id=user_id,
            type="weekly_memo",
            title=f"Test Memo {sg_message_id}",
            sg_message_id=sg_message_id,
        )
        db.session.add(art)
        db.session.commit()
        return art.id


def _post_events(raw_client, events):
    """POST a list of SendGrid events to the webhook (no CSRF — exempt)."""
    return raw_client.post(
        "/webhooks/sendgrid",
        json=events,
    )


def _ts():
    """SendGrid sends Unix epoch seconds — keep it concrete."""
    return int(datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc).timestamp())


# ─────────────────────────────────────────────────────────────────────────────
# event handling
# ─────────────────────────────────────────────────────────────────────────────

def test_open_event_sets_opened_at(app, raw_client, make_user):
    user = make_user()
    art_id = _make_artifact(app, user["id"], sg_message_id="abc123")

    resp = _post_events(raw_client, [
        {"sg_message_id": "abc123.filterserver-1",
         "event": "open",
         "timestamp": _ts()},
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 1}

    from models import Artifact
    with app.app_context():
        art = Artifact.query.get(art_id)
        assert art.opened_at is not None
        assert art.bounced_at is None
        assert art.unsubscribed_at is None


def test_open_event_first_open_wins(app, raw_client, make_user):
    """A second open event must NOT overwrite the original timestamp."""
    user = make_user()
    art_id = _make_artifact(app, user["id"], sg_message_id="abc123")

    early_ts = _ts()
    later_ts = early_ts + 3600

    _post_events(raw_client, [
        {"sg_message_id": "abc123.x", "event": "open", "timestamp": early_ts},
    ])
    from models import Artifact
    with app.app_context():
        first_opened = Artifact.query.get(art_id).opened_at
    assert first_opened is not None

    # Second open event — must not touch opened_at.
    resp = _post_events(raw_client, [
        {"sg_message_id": "abc123.x", "event": "open", "timestamp": later_ts},
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 0}

    with app.app_context():
        assert Artifact.query.get(art_id).opened_at == first_opened


def test_bounce_event_sets_bounced_at(app, raw_client, make_user):
    user = make_user()
    art_id = _make_artifact(app, user["id"], sg_message_id="bounceme")

    resp = _post_events(raw_client, [
        {"sg_message_id": "bounceme.fs-1",
         "event": "bounce",
         "timestamp": _ts()},
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 1}

    from models import Artifact
    with app.app_context():
        art = Artifact.query.get(art_id)
        assert art.bounced_at is not None


@pytest.mark.parametrize("evt_type", ["unsubscribe", "group_unsubscribe"])
def test_unsubscribe_events_set_unsubscribed_at(app, raw_client, make_user, evt_type):
    user = make_user(email=f"{evt_type}@test.com")
    art_id = _make_artifact(app, user["id"], sg_message_id=f"unsub-{evt_type}")

    resp = _post_events(raw_client, [
        {"sg_message_id": f"unsub-{evt_type}.fs-1",
         "event": evt_type,
         "timestamp": _ts()},
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 1}

    from models import Artifact
    with app.app_context():
        assert Artifact.query.get(art_id).unsubscribed_at is not None


# ── Wave 13 P1 (PR #439) — auto-opt-out on terminal email events ───────────
# Pre-fix: bounce/unsubscribe set Artifact columns but never flipped
# User.email_opt_out. The daily artifact cron continued to mail bounced
# or hostile addresses → §50 + SendGrid sender-reputation risk. spamreport
# wasn't handled at all. Tests pin the new contract.


@pytest.mark.parametrize("evt_type", ["bounce", "spamreport", "unsubscribe", "group_unsubscribe"])
def test_terminal_event_auto_flips_email_opt_out(
    app, raw_client, make_user, evt_type
):
    user = make_user(email=f"optout-{evt_type}@test.com")
    art_id = _make_artifact(app, user["id"], sg_message_id=f"opt-{evt_type}")

    # Confirm precondition: opt-out starts False.
    from extensions import db
    from models import User
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is False

    resp = _post_events(raw_client, [
        {"sg_message_id": f"opt-{evt_type}.fs-1",
         "event": evt_type,
         "timestamp": _ts()},
    ])
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json() == {"processed": 1}

    # User row now has opt-out flipped.
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is True, (
            f"event '{evt_type}' must auto-flip email_opt_out — "
            "see PR #439 / wave 13 integrations P1"
        )


def test_spamreport_also_records_artifact_bounced_at(
    app, raw_client, make_user
):
    """Pre-fix: spamreport was silently ignored. The handler now treats
    it as a terminal event and also records bounced_at if not already
    set — gives ops a single column to filter on for both classes of
    'this address must not receive more mail'."""
    user = make_user(email="spamreport-art@test.com")
    art_id = _make_artifact(app, user["id"], sg_message_id="spamart")

    resp = _post_events(raw_client, [
        {"sg_message_id": "spamart.fs-1",
         "event": "spamreport",
         "timestamp": _ts()},
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 1}

    from models import Artifact
    with app.app_context():
        art = Artifact.query.get(art_id)
        assert art.bounced_at is not None


def test_bounce_does_not_flip_when_already_opted_out(
    app, raw_client, make_user
):
    """Idempotent — a repeated bounce on an already-opted-out user
    doesn't toggle anything (no DB write churn, no log spam)."""
    user = make_user(email="already-out@test.com")
    art_id = _make_artifact(app, user["id"], sg_message_id="alreadyout")

    from extensions import db
    from models import User
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.email_opt_out = True
        db.session.commit()

    resp = _post_events(raw_client, [
        {"sg_message_id": "alreadyout.fs-1",
         "event": "bounce",
         "timestamp": _ts()},
    ])
    assert resp.status_code == 200
    # Artifact bounce still recorded.
    from models import Artifact
    with app.app_context():
        assert Artifact.query.get(art_id).bounced_at is not None
        # User flag unchanged.
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is True


def test_unknown_message_id_silently_ignored(app, raw_client, make_user):
    """Events for messages we never sent (e.g. auth emails) must not 500."""
    make_user()  # ensure DB is initialised
    resp = _post_events(raw_client, [
        {"sg_message_id": "no-such-message.x",
         "event": "open",
         "timestamp": _ts()},
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 0}


def test_unhandled_event_types_ignored(app, raw_client, make_user):
    """delivered/processed/dropped/click must be silently skipped."""
    user = make_user()
    _make_artifact(app, user["id"], sg_message_id="click-me")

    resp = _post_events(raw_client, [
        {"sg_message_id": "click-me.x", "event": "delivered", "timestamp": _ts()},
        {"sg_message_id": "click-me.x", "event": "click",     "timestamp": _ts()},
        {"sg_message_id": "click-me.x", "event": "processed", "timestamp": _ts()},
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 0}


def test_empty_event_list(app, raw_client):
    """Empty list is a valid, no-op payload."""
    resp = _post_events(raw_client, [])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 0}


def test_malformed_payload_returns_400(app, raw_client):
    """Non-list bodies are rejected as 400 (not 500)."""
    resp = raw_client.post(
        "/webhooks/sendgrid",
        json={"not": "a list"},
    )
    assert resp.status_code == 400


def test_garbage_event_entries_skipped(app, raw_client, make_user):
    """Non-dict elements in the events list don't crash the handler."""
    user = make_user()
    art_id = _make_artifact(app, user["id"], sg_message_id="mixed")

    resp = _post_events(raw_client, [
        "not a dict",
        None,
        {"sg_message_id": "mixed.x", "event": "open", "timestamp": _ts()},
        42,
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 1}

    from models import Artifact
    with app.app_context():
        assert Artifact.query.get(art_id).opened_at is not None


def test_missing_timestamp_skipped(app, raw_client, make_user):
    """Events without a parseable timestamp must be skipped, not crash."""
    user = make_user()
    art_id = _make_artifact(app, user["id"], sg_message_id="bad-ts")

    resp = _post_events(raw_client, [
        {"sg_message_id": "bad-ts.x", "event": "open", "timestamp": "not-a-number"},
        {"sg_message_id": "bad-ts.x", "event": "open"},  # missing entirely
    ])
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 0}

    from models import Artifact
    with app.app_context():
        assert Artifact.query.get(art_id).opened_at is None


# ─────────────────────────────────────────────────────────────────────────────
# signature verification
# ─────────────────────────────────────────────────────────────────────────────

def test_invalid_signature_returns_403(app, raw_client, monkeypatch):
    """When SENDGRID_WEBHOOK_PUBLIC_KEY is set, a bogus signature must 403."""
    # A syntactically valid but unrelated P-256 public key. The actual
    # ECDSA verify call will fail because the signature won't match.
    fake_pub = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE2DfZ8QPhRf6yPP3Y2L1H7tE7tpRb\n"
        "PqL2oXrR3xRQy8z7hYz0H4nXoX+5y6aE2KoRy6n1n0bXkW9tvKpY5gK6JQ==\n"
        "-----END PUBLIC KEY-----"
    )
    monkeypatch.setenv("SENDGRID_WEBHOOK_PUBLIC_KEY", fake_pub)

    resp = raw_client.post(
        "/webhooks/sendgrid",
        json=[{"sg_message_id": "x.y", "event": "open", "timestamp": _ts()}],
        headers={
            "X-Twilio-Email-Event-Webhook-Signature": "AAAA",  # garbage
            "X-Twilio-Email-Event-Webhook-Timestamp": "1714000000",
        },
    )
    assert resp.status_code == 403


def test_signature_required_when_env_absent(app, raw_client, monkeypatch, make_user):
    """Wave G-3 Bug #2 (2026-05-18) P0: without SENDGRID_WEBHOOK_PUBLIC_KEY,
    the handler must HARD-FAIL with 503 regardless of FLASK_ENV.

    Previously this test asserted 200 (dev-mode bypass), but that allowed
    unsigned forged webhooks in any env where ``FLASK_ENV`` was not
    explicitly ``production`` — including railway.json which (until
    Wave G-3) did not set the var. An attacker could POST a synthetic
    bounce/spamreport event to flip arbitrary users to email_opt_out=True.
    """
    monkeypatch.delenv("SENDGRID_WEBHOOK_PUBLIC_KEY", raising=False)
    user = make_user()
    art_id = _make_artifact(app, user["id"], sg_message_id="dev-ok")

    resp = _post_events(raw_client, [
        {"sg_message_id": "dev-ok.x", "event": "open", "timestamp": _ts()},
    ])
    assert resp.status_code == 503
    body = resp.get_json() or {}
    assert "not configured" in (body.get("error") or "").lower()

    # No state mutation should have happened.
    from models import Artifact
    with app.app_context():
        assert Artifact.query.get(art_id).opened_at is None


def test_valid_signature_accepted(app, raw_client, monkeypatch, make_user):
    """Sign with a known private key + verify with its matching public key."""
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    import base64
    import json as _json

    priv = ec.generate_private_key(ec.SECP256R1())
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setenv("SENDGRID_WEBHOOK_PUBLIC_KEY", pub_pem)

    user = make_user()
    art_id = _make_artifact(app, user["id"], sg_message_id="signed-ok")

    body_obj = [{"sg_message_id": "signed-ok.x", "event": "open", "timestamp": _ts()}]
    raw_body = _json.dumps(body_obj).encode("utf-8")
    timestamp = "1714000000"
    signature = priv.sign(
        timestamp.encode("utf-8") + raw_body,
        ec.ECDSA(hashes.SHA256()),
    )
    sig_b64 = base64.b64encode(signature).decode()

    resp = raw_client.post(
        "/webhooks/sendgrid",
        data=raw_body,
        content_type="application/json",
        headers={
            "X-Twilio-Email-Event-Webhook-Signature": sig_b64,
            "X-Twilio-Email-Event-Webhook-Timestamp": timestamp,
        },
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"processed": 1}

    from models import Artifact
    with app.app_context():
        assert Artifact.query.get(art_id).opened_at is not None
