"""Phase 7 — :class:`services.email.EmailSender` consolidation tests.

The 17 ``services/artifacts/*_service.py`` mailers used to inline an
identical SendGrid → SMTP → skip cascade. Phase 7 collapsed them into
one :class:`EmailSender`. These tests pin the consolidated path so a
future refactor can't quietly break:

  * the global ``email_opt_out`` short-circuit (Phase 2 P0);
  * the per-channel opt-out tuple (e.g. earnings prebrief);
  * SendGrid priority over SMTP when both env vars are set;
  * SMTP-only fallback when ``SENDGRID_API_KEY`` is absent;
  * RFC 8058 ``List-Unsubscribe`` + ``List-Unsubscribe-Post`` headers;
  * Reply-To: support@pivoxquant.com (Phase 7 E7);
  * PDF attachment shape (filename, MIME);
  * "no transport configured" → log + return False, never raise;
  * the shared :func:`currency_prefix` helper (E4).

Following the project's "거짓보고 금지" rule, opt-out tests use real DB
``User`` rows via the ``make_user`` fixture; transport tests mock only
the network boundary (``smtplib.SMTP`` / ``sendgrid.SendGridAPIClient``)
because we cannot — and do not want to — actually deliver email from CI.
"""
from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest


# ── currency_prefix (E4) ─────────────────────────────────────────────────


def test_currency_prefix_usd_for_us_ticker():
    from services.email.format_helpers import currency_prefix

    assert currency_prefix("AAPL") == "$"
    assert currency_prefix("MSFT") == "$"


def test_currency_prefix_krw_for_kospi_kosdaq():
    from services.email.format_helpers import currency_prefix

    assert currency_prefix("005930.KS") == "₩"
    assert currency_prefix("035720.KQ") == "₩"
    # Case-insensitive — DB rows occasionally show lowercase suffixes.
    assert currency_prefix("005930.ks") == "₩"
    assert currency_prefix("035720.kq") == "₩"


def test_currency_prefix_defaults_to_usd():
    from services.email.format_helpers import currency_prefix

    assert currency_prefix(None) == "$"
    assert currency_prefix("") == "$"


# ── opt-out gate ─────────────────────────────────────────────────────────


def test_opt_out_short_circuits(app, make_user, monkeypatch):
    """Global ``email_opt_out=True`` → ``send`` returns False without
    invoking either transport.

    We assert by raising on attempted transport access rather than just
    inspecting the return — a future bug that swaps the gate's order
    could still return False *after* sending, which would be much worse.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="optout-sender@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.email_opt_out = True
        db.session.commit()

        # Configure both transports — the gate must fire before either is
        # attempted. If a regression slips the opt-out check below the
        # transport selection, this test fails loudly.
        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        sg_call = MagicMock(side_effect=AssertionError("opt-out leaked to SendGrid"))
        smtp_call = MagicMock(side_effect=AssertionError("opt-out leaked to SMTP"))
        with patch("sendgrid.SendGridAPIClient", sg_call), \
             patch("smtplib.SMTP", smtp_call):
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
            )
            assert sent is False
            sg_call.assert_not_called()
            smtp_call.assert_not_called()


def test_per_channel_opt_out_blocks_earnings(app, make_user, monkeypatch):
    """``opt_out_attrs=("email_opt_out","email_opt_out_earnings")`` —
    either flag should short-circuit. Mirrors the earnings prebrief
    contract from Phase 2 migration 009.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="optout-earn@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        # Global flag still off — only the channel flag is set.
        u.email_opt_out = False
        u.email_opt_out_earnings = True
        db.session.commit()

        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        with patch("sendgrid.SendGridAPIClient",
                   side_effect=AssertionError("must not send")):
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="EARNINGS_PREBRIEF_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                opt_out_attrs=("email_opt_out", "email_opt_out_earnings"),
            )
            assert sent is False


def test_per_channel_global_flag_still_blocks(app, make_user, monkeypatch):
    """Inverse of the above — global ``email_opt_out`` blocks even when
    the per-channel flag is unset. This is the regression that landed in
    Phase 2 once and we're paranoid about.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="optout-both@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.email_opt_out = True
        u.email_opt_out_earnings = False
        db.session.commit()

        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        with patch("sendgrid.SendGridAPIClient",
                   side_effect=AssertionError("must not send")):
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="EARNINGS_PREBRIEF_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                opt_out_attrs=("email_opt_out", "email_opt_out_earnings"),
            )
            assert sent is False


# ── transport priority ───────────────────────────────────────────────────


def test_sendgrid_called_when_key_set(app, make_user, monkeypatch):
    """Both env vars set → SendGrid wins, SMTP never invoked."""
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="sg-priority@test.com")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.testkey")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        sg_instance = MagicMock()
        sg_instance.send.return_value = MagicMock(status_code=202)
        sg_class = MagicMock(return_value=sg_instance)
        smtp_factory = MagicMock(side_effect=AssertionError("SMTP must not run"))

        with patch("sendgrid.SendGridAPIClient", sg_class), \
             patch("smtplib.SMTP", smtp_factory):
            sent = EmailSender().send(
                u,
                subject="hi",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
            )
            assert sent is True
            sg_class.assert_called_once_with("SG.testkey")
            sg_instance.send.assert_called_once()
            smtp_factory.assert_not_called()


def test_smtp_fallback_when_no_sendgrid(app, make_user, monkeypatch):
    """Only ``SMTP_HOST`` set → SMTP STARTTLS path runs."""
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="smtp-fallback@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        smtp_instance = MagicMock()
        # ``smtplib.SMTP`` is used as a context manager — emulate that.
        smtp_cm = MagicMock()
        smtp_cm.__enter__.return_value = smtp_instance
        smtp_cm.__exit__.return_value = False
        smtp_factory = MagicMock(return_value=smtp_cm)

        with patch("smtplib.SMTP", smtp_factory):
            sent = EmailSender().send(
                u,
                subject="hi",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                pdf_bytes=b"%PDF-1.4 fake",
                pdf_filename="report.pdf",
            )
            assert sent is True
            smtp_factory.assert_called_once()
            smtp_instance.starttls.assert_called_once()
            smtp_instance.login.assert_called_once_with("u", "p")
            smtp_instance.send_message.assert_called_once()


def test_no_transport_returns_false(app, make_user, monkeypatch, caplog):
    """No env vars → log info + return False; never raises."""
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="no-transport@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)

    with app.app_context():
        u = db.session.get(User, user["id"])
        sent = EmailSender().send(
            u,
            subject="x",
            html_body="<p>body</p>",
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
        )
        assert sent is False


# ── headers + attachment shape (SMTP path — easiest to introspect) ──────


def test_list_unsubscribe_header_in_smtp(app, make_user, monkeypatch):
    """RFC 8058 headers must be present on every SMTP send. Without
    these, Gmail won't surface the inbox-level Unsubscribe button.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="hdr-check@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict[str, EmailMessage] = {}

    class FakeSMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["msg"] = msg

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        with patch("smtplib.SMTP", FakeSMTP):
            sent = EmailSender().send(
                u,
                subject="hi",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
            )
            assert sent is True

    msg = captured["msg"]
    assert msg["List-Unsubscribe"], "List-Unsubscribe header missing"
    assert "<http" in msg["List-Unsubscribe"], (
        f"List-Unsubscribe must wrap a URL, got {msg['List-Unsubscribe']!r}"
    )
    assert "type=all" in msg["List-Unsubscribe"]
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_reply_to_header_set_to_support(app, make_user, monkeypatch):
    """Phase 7 audit E7 — every artefact email must include a usable
    Reply-To. Default is ``support@pivoxquant.com``.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="reply-to@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict[str, EmailMessage] = {}

    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["msg"] = msg

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        with patch("smtplib.SMTP", FakeSMTP):
            EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
            )

    assert captured["msg"]["Reply-To"] == "support@pivoxquant.com"


def test_display_name_in_from_header(app, make_user, monkeypatch):
    """Default ``From`` should be ``"PivoxQuant Research" <addr>``.
    Test the SMTP path because the message object is introspectable.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="from-name@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict[str, EmailMessage] = {}

    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["msg"] = msg

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        with patch("smtplib.SMTP", FakeSMTP):
            EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
            )

    from_value = captured["msg"]["From"]
    assert "PivoxQuant Research" in from_value
    assert "<reports@pivoxquant.com>" in from_value


def test_pdf_attachment_smtp_path(app, make_user, monkeypatch):
    """PDF bytes must be attached as ``application/pdf`` with the
    caller-supplied filename.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="pdf-attach@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict[str, EmailMessage] = {}

    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["msg"] = msg

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        with patch("smtplib.SMTP", FakeSMTP):
            EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                pdf_bytes=b"%PDF-1.4 dummy",
                pdf_filename="weekly_memo_42.pdf",
            )

    msg = captured["msg"]
    # Walk the message to find the attachment part.
    parts = list(msg.walk())
    pdf_parts = [
        p for p in parts
        if p.get_content_type() == "application/pdf"
    ]
    assert len(pdf_parts) == 1, (
        f"expected one PDF attachment, got {len(pdf_parts)}"
    )
    fname = pdf_parts[0].get_filename()
    assert fname == "weekly_memo_42.pdf"


def test_png_attachment_via_attachment_mime(app, make_user, monkeypatch):
    """The brag card sends a PNG, not a PDF. ``attachment_mime`` must
    flow through to the message's MIME type.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="png-attach@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict[str, EmailMessage] = {}

    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["msg"] = msg

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        with patch("smtplib.SMTP", FakeSMTP):
            EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="BRAG_CARD_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                pdf_bytes=b"\x89PNG\r\n",
                pdf_filename="brag.png",
                attachment_mime="image/png",
            )

    msg = captured["msg"]
    png_parts = [
        p for p in msg.walk() if p.get_content_type() == "image/png"
    ]
    assert len(png_parts) == 1
    assert png_parts[0].get_filename() == "brag.png"


# ── unsubscribe footer injection ─────────────────────────────────────────


def test_unsubscribe_footer_injected_into_html(app, make_user, monkeypatch):
    """The sender must idempotently inject the unsubscribe URL into the
    body when the template didn't render it itself. Mirrors the Phase 2
    inline behaviour.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="footer@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict[str, EmailMessage] = {}

    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["msg"] = msg

    with app.app_context():
        u = db.session.get(User, user["id"])
        # Wave G-1 Bug #8 (2026-05-18): EmailSender now requires
        # marketing_consent_at to be set (정통망법 §50 default-deny).
        from datetime import datetime
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        with patch("smtplib.SMTP", FakeSMTP):
            EmailSender().send(
                u,
                subject="x",
                html_body="<html><body><p>hello</p></body></html>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
            )

    # The HTML alternative is one of the message parts — find it.
    html_payload = None
    for part in captured["msg"].walk():
        if part.get_content_type() == "text/html":
            html_payload = part.get_content()
            break
    assert html_payload is not None
    assert "unsubscribe" in html_payload.lower(), (
        "unsubscribe footer must be auto-injected"
    )


# ── TRANSACTIONAL bypass (정통망법 §50 ① 적용 제외 / PIPA §21) ────────────
#
# Regression for the 2026-05-21 fix: transactional email (탈퇴 확인, 영수증,
# 보안 알림) must bypass the marketing-consent NULL gate + opt-out + the
# category gate so it always reaches the user — but the simulated-user guard
# stays in force (sink address). These tests use real DB ``User`` rows so a
# future reorder of the gates fails loudly.


def _fake_smtp_capture(captured: dict):
    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            captured["msg"] = msg
            captured["sent"] = True
    return FakeSMTP


def test_transactional_bypasses_marketing_consent_null(app, make_user, monkeypatch):
    """marketing_consent_at NULL + TRANSACTIONAL → provider IS invoked.

    Pre-fix the default-deny §50 gate would block this and the user would
    never receive their account-deletion / receipt email (PIPA §21 위반).
    """
    from extensions import db
    from models import User
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    user = make_user(email="txn-null-consent@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict = {}
    with app.app_context():
        u = db.session.get(User, user["id"])
        # Brand-new user — never visited settings, so consent is NULL.
        assert getattr(u, "marketing_consent_at", None) is None
        with patch("smtplib.SMTP", _fake_smtp_capture(captured)):
            sent = EmailSender().send(
                u,
                subject="회원탈퇴가 완료되었습니다",
                html_body="<p>bye</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                email_category=EmailCategory.TRANSACTIONAL,
            )
    assert sent is True, "transactional send must NOT be blocked by NULL consent"
    assert captured.get("sent") is True, "transport must have been invoked"


def test_transactional_bypasses_opt_out_flag(app, make_user, monkeypatch):
    """email_opt_out=True + TRANSACTIONAL → still sends (opt-out is for ads)."""
    from extensions import db
    from models import User
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    user = make_user(email="txn-optout@test.com")
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    captured: dict = {}
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.email_opt_out = True
        db.session.commit()
        with patch("smtplib.SMTP", _fake_smtp_capture(captured)):
            sent = EmailSender().send(
                u,
                subject="결제 영수증",
                html_body="<p>receipt</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                email_category=EmailCategory.TRANSACTIONAL,
            )
    assert sent is True
    assert captured.get("sent") is True


def test_non_transactional_still_blocked_by_null_consent(app, make_user, monkeypatch):
    """email_category=None (legacy) + NULL consent → blocked (no transport).

    Pins that the bypass is *narrow* — only TRANSACTIONAL slips the gate.
    A marketing/None send to a no-consent user must still be dropped.
    """
    from extensions import db
    from models import User
    from services.email import EmailSender

    user = make_user(email="none-cat-null-consent@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert getattr(u, "marketing_consent_at", None) is None
        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        sg = MagicMock(side_effect=AssertionError("must not send (category=None)"))
        smtp = MagicMock(side_effect=AssertionError("must not send (category=None)"))
        with patch("sendgrid.SendGridAPIClient", sg), patch("smtplib.SMTP", smtp):
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                email_category=None,
            )
        assert sent is False
        sg.assert_not_called()
        smtp.assert_not_called()


def test_marketing_category_blocked_by_null_consent(app, make_user, monkeypatch):
    """email_category=MARKETING + NULL consent → blocked (not bypassed)."""
    from extensions import db
    from models import User
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    user = make_user(email="marketing-null-consent@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert getattr(u, "marketing_consent_at", None) is None
        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        sg = MagicMock(side_effect=AssertionError("marketing must not bypass"))
        with patch("sendgrid.SendGridAPIClient", sg):
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                email_category=EmailCategory.MARKETING,
            )
        assert sent is False
        sg.assert_not_called()


def test_simulated_user_blocked_even_for_transactional(app, make_user, monkeypatch):
    """is_simulated=True + TRANSACTIONAL → still blocked (sink-address guard).

    The simulated-user guard sits ABOVE the transactional bypass and must
    never be relaxed — synthetic users have non-deliverable sink addresses.
    """
    from datetime import datetime
    from extensions import db
    from models import User
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    user = make_user(email="sim-txn@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        # Give full consent too, to prove the block is purely the sim guard.
        u.is_simulated = True
        u.marketing_consent_at = datetime.utcnow()
        db.session.commit()
        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        sg = MagicMock(side_effect=AssertionError("simulated user leaked"))
        smtp = MagicMock(side_effect=AssertionError("simulated user leaked"))
        with patch("sendgrid.SendGridAPIClient", sg), patch("smtplib.SMTP", smtp):
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                email_category=EmailCategory.TRANSACTIONAL,
            )
        assert sent is False
        sg.assert_not_called()
        smtp.assert_not_called()
