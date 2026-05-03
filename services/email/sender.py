"""Single send path for every artefact email.

Background
----------
Phase 2 (PR #39) added per-user opt-out + one-click unsubscribe to
17 ``services/artifacts/*_service.py`` mailers. Each one ended up with
a ~70-line copy of the same SendGrid-then-SMTP cascade — ~1,400 lines
of pure duplication. Phase 7 collapses those into the single
:class:`EmailSender` below; the artefact services keep all of their
template rendering and orchestration logic, but the actual delivery
goes through this class.

Behaviour parity (must remain identical to the Phase 2 baseline)
----------------------------------------------------------------
1. **Opt-out gate.** Honours ``user.email_opt_out`` (global) plus any
   per-channel attributes the caller passes via ``opt_out_attrs``
   (e.g. ``("email_opt_out", "email_opt_out_earnings")`` for the
   earnings pre-brief). First truthy attribute short-circuits and
   returns ``False`` after an info-level log line — exactly like the
   17 inlined copies did.
2. **Unsubscribe URL.** Built via ``services.email_token``'s
   :func:`build_unsubscribe_url` so the same HMAC-signed token shape
   is used for both the inline footer and the ``List-Unsubscribe``
   header.
3. **Transport priority.** SendGrid first (when ``SENDGRID_API_KEY``
   is set); SMTP STARTTLS fallback (when ``SMTP_HOST`` is set);
   otherwise we log + return ``False`` (dev-mode). On a SendGrid
   exception we fall through to SMTP — *that* is a deliberate
   improvement over the Phase 2 inlined paths, which used to give up
   on a SendGrid 5xx. Any SendGrid 2xx or 4xx still short-circuits
   cleanly because we only fall through on raised exceptions.
4. **Headers (RFC 8058).** Every outgoing message — SendGrid or SMTP —
   gets ``List-Unsubscribe: <url>`` plus ``List-Unsubscribe-Post:
   List-Unsubscribe=One-Click``. Gmail / Outlook surface the inbox-
   level "Unsubscribe" button off the former.
5. **Reply-To.** Phase 7 introduces a uniform ``Reply-To:
   support@pivoxquant.com`` (audit item E7) — previously absent. This
   is intentional: support@ is a real shared inbox so users can
   actually reply to any artefact email and reach a human, not bounce
   off the generic ``reports@`` sender address.
6. **Display name.** ``"PivoxQuant Research" <{from_email}>`` is the
   uniform From wrapper — also a Phase 7 introduction so all 17
   mailer types render with the same brand identity in the inbox.
7. **PDF attachment.** When ``pdf_bytes`` is non-empty we attach with
   the supplied ``pdf_filename`` (defaults to ``"report.pdf"``).

Return contract
---------------
:meth:`send` returns ``True`` on a successful dispatch and ``False``
on opt-out / no-transport / failure. It never raises — the caller can
short-circuit persistence on ``False`` if appropriate, but most of
our callers persist regardless because the artefact row itself is
the source of truth.
"""
from __future__ import annotations

import base64
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Sequence

from services.email_token import build_unsubscribe_url, inject_unsubscribe_footer

logger = logging.getLogger(__name__)


# Default reply-to surfaces a real shared inbox so artefact emails can
# round-trip to a human. Overridable per-call for cases where the
# product wants a dedicated reply route (e.g. earnings desk).
_DEFAULT_REPLY_TO = "support@pivoxquant.com"

# Uniform display name. Keep simple — Gmail truncates anything fancy
# in the mobile app. ``{from_email}`` is filled in at send time.
_DEFAULT_DISPLAY_NAME = "PivoxQuant Research"


class EmailSender:
    """Stateless dispatcher; every send is a method call.

    Stateless because the only thing it would cache (env vars) is
    cheap to read each time, and any future test that wants to mutate
    the env mid-run needs the lookup to be live.
    """

    # ── public ─────────────────────────────────────────────────────────

    def send(
        self,
        user: Any,
        *,
        subject: str,
        html_body: str,
        from_env_var: str,
        from_default: str,
        pdf_bytes: bytes | None = None,
        pdf_filename: str | None = None,
        attachment_mime: str = "application/pdf",
        opt_out_attrs: Sequence[str] = ("email_opt_out",),
        unsubscribe_kind: str = "all",
        reply_to: str = _DEFAULT_REPLY_TO,
        display_name: str = _DEFAULT_DISPLAY_NAME,
    ) -> bool:
        """Dispatch a single email. Returns ``True`` on success.

        Parameters
        ----------
        user
            A SQLAlchemy ``User`` row (or anything duck-typing
            ``id`` / ``email`` / opt-out flags). Kept untyped here so
            this module never has to import the ORM.
        subject, html_body
            Already rendered — caller owns Jinja. ``html_body`` will
            have the unsubscribe footer injected idempotently if it
            doesn't already contain the unsubscribe URL.
        from_env_var, from_default
            ``os.environ.get(from_env_var, from_default)`` — every
            artefact service has its own env override knob (e.g.
            ``WEEKLY_MEMO_FROM_EMAIL``); the default is the
            global shared sender (``reports@pivoxquant.com``).
        pdf_bytes, pdf_filename, attachment_mime
            Optional binary attachment. ``pdf_bytes`` is the legacy
            name (kept because nearly every caller really is sending
            a PDF) but the brag card sends a PNG; pass
            ``attachment_mime="image/png"`` to override. Filename
            falls back to ``"report.pdf"`` for safety — most callers
            always pass an explicit one.
        opt_out_attrs
            Tuple of attribute names checked on ``user`` (in order).
            First truthy one short-circuits with ``False`` and an
            info log. Defaults to the global ``email_opt_out`` only;
            channel-specific senders pass tuples like
            ``("email_opt_out", "email_opt_out_earnings")``.
        unsubscribe_kind
            Mirrored into the unsubscribe URL's ``?type=`` query —
            today only ``"all"`` and ``"earnings"`` are honoured by
            the public unsubscribe route.
        reply_to, display_name
            Header overrides; sensible defaults for every artefact
            type.
        """
        # ── 1. opt-out gate ────────────────────────────────────────────
        for attr in opt_out_attrs:
            if getattr(user, attr, False):
                logger.info(
                    "user %s opted out (%s); skipping send",
                    getattr(user, "id", "?"), attr,
                )
                return False

        # ── 2. resolve from + unsubscribe URL ──────────────────────────
        from_email = os.environ.get(from_env_var, from_default)
        unsubscribe_url = build_unsubscribe_url(user.id, kind=unsubscribe_kind)
        # Idempotent — if the template already rendered ``{{ unsubscribe_url }}``
        # this is a no-op. Otherwise we splice a small footer in so every
        # outgoing email has the inline link (regulatory belt-and-braces
        # alongside the List-Unsubscribe header).
        html_body = inject_unsubscribe_footer(html_body, unsubscribe_url)

        # ── 3. SendGrid first ──────────────────────────────────────────
        sg_key = os.environ.get("SENDGRID_API_KEY")
        if sg_key:
            try:
                ok = self._send_via_sendgrid(
                    sg_key=sg_key,
                    from_email=from_email,
                    display_name=display_name,
                    to_email=user.email,
                    subject=subject,
                    html_body=html_body,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=pdf_filename,
                    attachment_mime=attachment_mime,
                    unsubscribe_url=unsubscribe_url,
                    reply_to=reply_to,
                )
                if ok:
                    return True
            except Exception:
                # Log + fall through to SMTP. The Phase 2 baseline used
                # to short-circuit to ``return False`` here, but that
                # made a transient SendGrid 5xx silently kill the email
                # even when an SMTP fallback was configured. Retrying
                # via SMTP is strictly safer.
                logger.exception(
                    "SendGrid send failed for user %s; trying SMTP",
                    getattr(user, "id", "?"),
                )

        # ── 4. SMTP fallback ───────────────────────────────────────────
        smtp_host = os.environ.get("SMTP_HOST")
        if smtp_host:
            try:
                return self._send_via_smtp(
                    smtp_host=smtp_host,
                    from_email=from_email,
                    display_name=display_name,
                    to_email=user.email,
                    subject=subject,
                    html_body=html_body,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=pdf_filename,
                    attachment_mime=attachment_mime,
                    unsubscribe_url=unsubscribe_url,
                    reply_to=reply_to,
                )
            except Exception:
                logger.exception(
                    "SMTP send failed for user %s",
                    getattr(user, "id", "?"),
                )
                return False

        # ── 5. no transport configured ─────────────────────────────────
        logger.info(
            "no email transport configured; skipping send for user %s",
            getattr(user, "id", "?"),
        )
        return False

    # ── private transport helpers ──────────────────────────────────────

    def _format_from(self, display_name: str, from_email: str) -> str:
        """Compose the RFC 5322 From header value.

        Both transports accept ``Name <addr>`` so we render a single
        string here. Quoting the display name keeps Gmail happy when
        it eventually contains commas / periods.
        """
        if not display_name:
            return from_email
        # Strip stray quotes from caller-supplied display names so we
        # don't end up with double-quoted header values that some
        # MTAs reject.
        clean = display_name.replace('"', "").strip()
        return f'"{clean}" <{from_email}>'

    def _send_via_sendgrid(
        self,
        *,
        sg_key: str,
        from_email: str,
        display_name: str,
        to_email: str,
        subject: str,
        html_body: str,
        pdf_bytes: bytes | None,
        pdf_filename: str | None,
        attachment_mime: str,
        unsubscribe_url: str,
        reply_to: str,
    ) -> bool:
        """SendGrid path. Returns ``True`` on accepted dispatch.

        Imports SendGrid lazily — keeps the dependency optional in
        local dev (where ``pip install sendgrid`` may be skipped) and
        in tests that mock the transport.
        """
        from sendgrid import SendGridAPIClient  # type: ignore[import-not-found]
        from sendgrid.helpers.mail import (  # type: ignore[import-not-found]
            Attachment,
            Disposition,
            FileContent,
            FileName,
            FileType,
            Mail,
        )

        from_value = self._format_from(display_name, from_email)
        mail = Mail(
            from_email=from_value,
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )

        if pdf_bytes:
            enc = base64.b64encode(pdf_bytes).decode()
            mail.attachment = Attachment(
                FileContent(enc),
                FileName(pdf_filename or "report.pdf"),
                FileType(attachment_mime),
                Disposition("attachment"),
            )

        # Headers (Reply-To + List-Unsubscribe). SendGrid's Header
        # helper occasionally raises during init on broken deps — keep
        # the import inside the try and log+continue rather than
        # blowing up the whole send for a header issue.
        try:
            from sendgrid.helpers.mail import Header  # type: ignore[import-not-found]

            mail.add_header(Header("List-Unsubscribe", f"<{unsubscribe_url}>"))
            mail.add_header(
                Header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click")
            )
            if reply_to:
                mail.add_header(Header("Reply-To", reply_to))
        except Exception:
            logger.debug(
                "SendGrid header injection failed", exc_info=True,
            )

        SendGridAPIClient(sg_key).send(mail)
        return True

    def _send_via_smtp(
        self,
        *,
        smtp_host: str,
        from_email: str,
        display_name: str,
        to_email: str,
        subject: str,
        html_body: str,
        pdf_bytes: bytes | None,
        pdf_filename: str | None,
        attachment_mime: str,
        unsubscribe_url: str,
        reply_to: str,
    ) -> bool:
        """SMTP STARTTLS path. Returns ``True`` on accepted dispatch.

        Stays inside ``smtplib.SMTP`` (the plaintext-then-STARTTLS
        flavour) because all of our outbound providers — Gmail SMTP
        relay, Mailgun, etc. — take 587 + STARTTLS. If we ever need
        SMTPS (465) we add a branch here keyed on ``SMTP_PORT``.
        """
        msg = EmailMessage()
        msg["From"] = self._format_from(display_name, from_email)
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        if reply_to:
            msg["Reply-To"] = reply_to
        # Plain-text alternative is mandatory for STARTTLS clients —
        # we don't render a real text variant because every artefact
        # is design-heavy HTML, but Gmail flags messages with no
        # text/plain part as spam.
        msg.set_content("HTML-only; view in an HTML-capable client.")
        msg.add_alternative(html_body, subtype="html")

        if pdf_bytes:
            # ``attachment_mime`` is "type/subtype". email.message
            # wants them split — fall back to ``application/pdf`` if
            # the caller passed something malformed (defensive).
            if "/" in attachment_mime:
                maintype, subtype = attachment_mime.split("/", 1)
            else:
                maintype, subtype = "application", "pdf"
            msg.add_attachment(
                pdf_bytes,
                maintype=maintype,
                subtype=subtype,
                filename=pdf_filename or "report.pdf",
            )

        port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pw = os.environ.get("SMTP_PASSWORD")
        with smtplib.SMTP(smtp_host, port, timeout=10) as s:
            s.starttls()
            if smtp_user and smtp_pw:
                s.login(smtp_user, smtp_pw)
            s.send_message(msg)
        return True


__all__ = ["EmailSender"]
