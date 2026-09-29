"""services.email.system_mail — the one owner of the provider order.

2026-09-29: the Brevo/SendGrid cascade was written five times —
``EmailSender`` (respected ``BREVO_PROVIDER_PRIMARY``), ``routes/support``
(respected it), ``services/billing_notifications`` and
``services/billing_followup`` (hard-coded SendGrid first) and
``scripts/nightly/notify_email.sh`` (SendGrid only). With the SendGrid key
dead in prod and Brevo primary (render.yaml), the billing mails burned a
failing SendGrid call on every send. These tests pin the shared rules:

* order = Brevo first iff ``brevo_provider.is_primary()``, else SendGrid first;
* a provider without a key is skipped, never called;
* an exception or a non-accept falls through to the next provider;
* total failure returns False, logs a WARNING and never raises;
* simulated users never reach a provider (CLAUDE.md trap 7);
* system mail is §50-exempt: providers get ``honour_consent=False``.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.email import system_mail


SG = "services.email.sendgrid_provider.send"
BREVO = "services.email.brevo_provider.send"


@pytest.fixture
def no_keys(monkeypatch):
    for k in ("SENDGRID_API_KEY", "BREVO_API_KEY", "SENDINBLUE_API_KEY",
              "BREVO_PROVIDER_PRIMARY"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


@pytest.fixture
def both_keys(no_keys):
    no_keys.setenv("SENDGRID_API_KEY", "SG.fake")
    no_keys.setenv("BREVO_API_KEY", "brevo-fake")
    return no_keys


def _calls(order):
    def _sg(*a, **kw):
        order.append("sendgrid")
        return True

    def _brevo(*a, **kw):
        order.append("brevo")
        return True
    return _sg, _brevo


# ── order ──────────────────────────────────────────────────────────────────

def test_provider_order_default_is_sendgrid_then_brevo(both_keys):
    assert system_mail.provider_order() == ["sendgrid", "brevo"]


def test_provider_order_brevo_first_when_primary(both_keys):
    both_keys.setenv("BREVO_PROVIDER_PRIMARY", "true")
    assert system_mail.provider_order() == ["brevo", "sendgrid"]


def test_provider_order_skips_unconfigured(no_keys):
    assert system_mail.provider_order() == []
    no_keys.setenv("SENDINBLUE_API_KEY", "legacy")  # legacy Brevo name counts
    assert system_mail.provider_order() == ["brevo"]


def test_send_uses_brevo_first_when_primary(both_keys):
    both_keys.setenv("BREVO_PROVIDER_PRIMARY", "true")
    order: list[str] = []
    sg, brevo = _calls(order)
    with patch(SG, side_effect=sg), patch(BREVO, side_effect=brevo):
        assert system_mail.send_system_mail("a@b.com", "s", "<p>x</p>") is True
    assert order == ["brevo"]


def test_send_uses_sendgrid_first_by_default(both_keys):
    order: list[str] = []
    sg, brevo = _calls(order)
    with patch(SG, side_effect=sg), patch(BREVO, side_effect=brevo):
        assert system_mail.send_system_mail("a@b.com", "s", "<p>x</p>") is True
    assert order == ["sendgrid"]


def test_provider_without_key_is_never_called(no_keys):
    no_keys.setenv("BREVO_API_KEY", "brevo-fake")
    with patch(SG) as sg, patch(BREVO, return_value=True) as brevo:
        assert system_mail.send_system_mail("a@b.com", "s", "<p>x</p>") is True
    sg.assert_not_called()
    assert brevo.call_count == 1


# ── fall-through + failure ─────────────────────────────────────────────────

def test_exception_falls_through_to_next_provider(both_keys):
    with patch(SG, side_effect=RuntimeError("SG down")) as sg, \
            patch(BREVO, return_value=True) as brevo:
        assert system_mail.send_system_mail("a@b.com", "s", "<p>x</p>") is True
    assert sg.call_count == 1 and brevo.call_count == 1


def test_non_accept_falls_through_to_next_provider(both_keys):
    with patch(SG, return_value=False), patch(BREVO, return_value=True) as brevo:
        assert system_mail.send_system_mail("a@b.com", "s", "<p>x</p>") is True
    assert brevo.call_count == 1


def test_total_failure_returns_false_and_warns(both_keys, caplog):
    with patch(SG, side_effect=RuntimeError("SG down")), \
            patch(BREVO, side_effect=RuntimeError("Brevo down")), \
            caplog.at_level(logging.WARNING, logger="services.email.system_mail"):
        ok = system_mail.send_system_mail("a@b.com", "s", "<p>x</p>",
                                          log_label="unit-test mail")
    assert ok is False
    warn = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warn, "total failure must be visible at WARNING"
    assert "unit-test mail" in warn[-1].getMessage()
    assert "SG down" in warn[-1].getMessage()


def test_no_provider_configured_returns_false_and_warns(no_keys, caplog):
    with caplog.at_level(logging.WARNING, logger="services.email.system_mail"):
        assert system_mail.send_system_mail("a@b.com", "s", "<p>x</p>") is False
    assert any("no provider configured" in r.getMessage() for r in caplog.records)


# ── guards + pass-through ──────────────────────────────────────────────────

def test_simulated_user_never_reaches_a_provider(both_keys):
    sim = SimpleNamespace(id=7, email="sim@sink.test", is_simulated=True)
    with patch(SG) as sg, patch(BREVO) as brevo:
        assert system_mail.send_system_mail(
            sim.email, "s", "<p>x</p>", user=sim) is False
    sg.assert_not_called()
    brevo.assert_not_called()


def test_arguments_reach_each_provider_in_its_own_dialect(both_keys):
    user = SimpleNamespace(id=5, email="u@b.com", is_simulated=False)
    with patch(SG, return_value=False) as sg, patch(BREVO, return_value=True) as brevo:
        system_mail.send_system_mail(
            "u@b.com", "subj", "<p>h</p>", "plain",
            user=user, category=("billing", "x"),
            from_email="billing@pivoxquant.com", from_name="PivoxQuant Billing",
            reply_to="support@pivoxquant.com",
        )
    for mock in (sg, brevo):
        kw = mock.call_args.kwargs
        rcpt = mock.call_args.args[0]
        assert rcpt.email == "u@b.com" and rcpt.user_id == 5
        assert rcpt.is_simulated is False
        assert kw["subject"] == "subj" and kw["html_body"] == "<p>h</p>"
        assert kw["plain_body"] == "plain"
        assert kw["from_email"] == "billing@pivoxquant.com"
        assert kw["from_name"] == "PivoxQuant Billing"
        assert kw["reply_to"] == "support@pivoxquant.com"
        assert kw["honour_consent"] is False  # system mail — §50 exempt
    assert sg.call_args.kwargs["categories"] == ("billing", "x")
    assert brevo.call_args.kwargs["tags"] == ("billing", "x")


# ── the callers use it ─────────────────────────────────────────────────────

def _billing_user():
    return SimpleNamespace(id=99, email="z@y.com", name="Z", is_simulated=False)


def test_billing_payment_failed_uses_brevo_first_when_primary(both_keys):
    both_keys.setenv("BREVO_PROVIDER_PRIMARY", "true")
    from services.billing_notifications import notify_payment_failed_email

    with patch(SG) as sg, patch(BREVO, return_value=True) as brevo:
        ok = notify_payment_failed_email(
            user=_billing_user(),
            invoice={"id": "in_x", "amount_due": 9_900, "currency": "krw",
                     "attempt_count": 1},
        )
    assert ok is True
    assert brevo.call_count == 1
    sg.assert_not_called()


def test_billing_followup_uses_brevo_first_when_primary(both_keys, app):
    both_keys.setenv("BREVO_PROVIDER_PRIMARY", "true")
    from services.billing_followup import send_checkout_followup

    with app.app_context(), patch(SG) as sg, \
            patch(BREVO, return_value=True) as brevo:
        ok = send_checkout_followup(user=_billing_user())
    assert ok is True
    assert brevo.call_count == 1
    sg.assert_not_called()


def test_billing_mail_skips_simulated_user(both_keys):
    from services.billing_notifications import notify_payment_failed_email

    sim = SimpleNamespace(id=1, email="sim@sink.test", name="S", is_simulated=True)
    with patch(SG) as sg, patch(BREVO) as brevo:
        assert notify_payment_failed_email(user=sim, invoice={}) is False
    sg.assert_not_called()
    brevo.assert_not_called()


# ── EmailSender's SendGrid leg goes through sendgrid_provider ──────────────

def test_email_sender_sendgrid_leg_uses_sendgrid_provider(no_keys, app):
    no_keys.setenv("SENDGRID_API_KEY", "SG.fake")
    from datetime import datetime

    from services.email.sender import EmailSender

    user = SimpleNamespace(
        id=3, email="r@b.com", is_simulated=False, email_opt_out=False,
        marketing_consent_at=datetime(2026, 9, 1), marketing_consent_revoked_at=None,
    )
    sender = EmailSender()
    with app.app_context(), patch(
        "services.email.sendgrid_provider.send_tracked", return_value="msg-123",
    ) as tracked:
        ok = sender.send(
            user, subject="s", html_body="<p>x</p>",
            from_env_var="X_FROM", from_default="reports@pivoxquant.com",
            pdf_bytes=b"%PDF", pdf_filename="r.pdf",
        )
    assert ok is True
    assert sender.last_message_id == "msg-123"
    kw = tracked.call_args.kwargs
    assert kw["headers"]["List-Unsubscribe"].startswith("<")
    assert kw["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert kw["pdf_bytes"] == b"%PDF" and kw["pdf_filename"] == "r.pdf"
    assert kw["honour_consent"] is False  # EmailSender already gated consent
