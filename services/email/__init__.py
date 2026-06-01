"""Email subsystem — single send path for every artefact mailer.

Consolidates 17 duplicated ``send_email`` methods (~1,400 lines) under
one :class:`~services.email.sender.EmailSender` that honours opt-out,
generates RFC 8058 unsubscribe headers, attaches PDFs, and falls
through SendGrid → SMTP → skip identically to the Phase 2 baseline.

See ``services/email/sender.py`` for the consolidated implementation
and ``services/email/format_helpers.py`` for shared body-rendering
utilities (currency prefix, etc.).
"""
from __future__ import annotations

from services.email.format_helpers import currency_prefix
from services.email.sender import EmailCategory, EmailSender

__all__ = ["EmailCategory", "EmailSender", "currency_prefix"]
