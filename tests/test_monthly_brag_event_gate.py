"""Regression — monthly_brag per-event email-channel gate (2026-05-21 fix).

``MonthlyBragService.send_email`` now passes ``event_id="brag_card"`` to
:class:`EmailSender`. Without it, the sender skipped the settings-v2
``notification_prefs`` check and shipped the brag card even when the user
disabled the "Brag card" email channel.

These tests pin that contract using a real DB ``User`` row (no provider
configured / network mocked at the transport boundary) per the project's
"거짓보고 금지" rule — we assert the provider is never invoked when the
channel is off, and IS invoked when it's on.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


def _capturing_smtp(captured: dict):
    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["sent"] = True
    return FakeSMTP


def test_monthly_brag_blocked_when_email_channel_off(app, make_user, monkeypatch):
    """notification_prefs brag_card.email=False → send_email returns False
    and never touches a transport (per-event gate fires)."""
    from extensions import db
    from models import User
    from services.artifacts.monthly_brag_service import MonthlyBragService

    user = make_user(email="brag-off@test.com")
    monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Pass the §50 default-deny gate so the block is purely the per-event gate.
        u.marketing_consent_at = datetime.utcnow()
        u.notification_prefs = {"brag_card": {"email": False}}
        db.session.commit()

        sg = MagicMock(side_effect=AssertionError("brag_card channel-off leaked to SendGrid"))
        smtp = MagicMock(side_effect=AssertionError("brag_card channel-off leaked to SMTP"))
        with patch("sendgrid.SendGridAPIClient", sg), patch("smtplib.SMTP", smtp):
            sent = MonthlyBragService().send_email(
                u, png_bytes=b"\x89PNG\r\n", html_body="<p>brag</p>",
            )
        assert sent is False
        sg.assert_not_called()
        smtp.assert_not_called()


def test_monthly_brag_sends_when_email_channel_on(app, make_user, monkeypatch):
    """brag_card.email=True (explicit) → send proceeds and hits the transport."""
    from extensions import db
    from models import User
    from services.artifacts.monthly_brag_service import MonthlyBragService

    user = make_user(email="brag-on@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict = {}
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.marketing_consent_at = datetime.utcnow()
        u.notification_prefs = {"brag_card": {"email": True}}
        db.session.commit()
        with patch("smtplib.SMTP", _capturing_smtp(captured)):
            sent = MonthlyBragService().send_email(
                u, png_bytes=b"\x89PNG\r\n", html_body="<p>brag</p>",
            )
    assert sent is True
    assert captured.get("sent") is True
