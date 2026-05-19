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
   is set); **Brevo second** (when ``BREVO_API_KEY`` /
   ``SENDINBLUE_API_KEY`` is set — adds a free 300/day tier for a
   combined 400/day budget); SMTP STARTTLS fallback (when
   ``SMTP_HOST`` is set); otherwise we log + return ``False``
   (dev-mode). On a SendGrid exception (5xx) or
   :class:`~services.email.sendgrid_provider.SendGridRateLimitExceeded`
   (429 — daily quota) we fall through to Brevo, then SMTP — *that* is
   a deliberate improvement over the Phase 2 inlined paths, which used
   to give up on a SendGrid 5xx. Any SendGrid 2xx still short-circuits
   cleanly because we return immediately on ``ok=True``.

   **Operational override.** Setting ``BREVO_PROVIDER_PRIMARY=true``
   flips the order so Brevo is tried first and SendGrid is the
   fallback — useful when SendGrid's domain reputation degrades or
   its 100/day cap is exhausted early in the day.
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
from enum import Enum
from typing import Any, Sequence

from services.email_token import build_unsubscribe_url, inject_unsubscribe_footer

logger = logging.getLogger(__name__)


class EmailCategory(str, Enum):
    """정통망법 §50 ① 카테고리 (Wave D Sub-wave 1, C-S1).

    분리 동의 카테고리. ``EmailSender.send(email_category=...)`` 에 전달되어
    ``PIVOX_CS1_CONSENT_ENABLED=true`` 일 때 카테고리별 동의 컬럼을 검사한다.

    * ``TRANSACTIONAL`` — 계정 / 보안 / 결제 영수증 / 비밀번호 재설정 등
      서비스 제공의 핵심에 직결되는 발송. §50 ① 적용 제외 (광고성 아님).
      동의 검사 skip.
    * ``INFORMATION``   — 서비스 업데이트 / 기능 공지 / 정책 변경 안내 등
      비광고성 정보 메일. 사용자가 정보성 동의를 분리 거부한 경우 차단.
    * ``MARKETING``     — 할인 / 프로모션 / 추천 / 교차판매. §50 ① 명시적
      사전 동의 필수. 광고성 동의 미수령 시 차단.

    값을 문자열로도 사용 가능 (``str`` 상속) — 기존 호출부가 점진적으로
    이전할 수 있도록 한다.
    """
    TRANSACTIONAL = "transactional"
    INFORMATION   = "information"
    MARKETING     = "marketing"


def _cs1_consent_enabled() -> bool:
    """Runtime feature flag for the split-consent enforcement path.

    Default false — variable-flag guard so prod can deploy the schema +
    routes without changing send behaviour until the lawyer's Q-S1
    answer arrives. Read on every send so an env flip during a single
    run is honoured (matches the EmailSender's stateless dispatch
    contract).
    """
    val = os.environ.get("PIVOX_CS1_CONSENT_ENABLED", "false").strip().lower()
    return val in ("true", "1", "yes", "on")


def _has_category_consent(user: Any, category: EmailCategory) -> bool:
    """Return True iff the user has effective opt-in for *category*.

    Mirrors the ``consent_at IS NOT NULL AND (revoked_at IS NULL OR
    revoked_at < consent_at)`` predicate used by ``routes/consents.py``
    so the send-side gate and the consent-record source agree exactly.
    """
    if category is EmailCategory.TRANSACTIONAL:
        return True  # §50 ① 적용 제외 — 동의 무관 발송

    if category is EmailCategory.INFORMATION:
        at_attr, rev_attr = (
            "marketing_consent_information_at",
            "marketing_consent_information_revoked_at",
        )
    elif category is EmailCategory.MARKETING:
        at_attr, rev_attr = (
            "marketing_consent_marketing_at",
            "marketing_consent_marketing_revoked_at",
        )
    else:  # defensive — unknown enum member
        return False

    consent_at = getattr(user, at_attr, None)
    if consent_at is None:
        return False
    revoked_at = getattr(user, rev_attr, None)
    return revoked_at is None or revoked_at < consent_at


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
        email_category: EmailCategory | None = None,
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
        # ── 1a. simulated-user guard (Continuous User Simulation Phase 1) ──
        # ``User.is_simulated`` (migration 032) tags synthetic test users the
        # Sunday 04:30 KST simulation cron generates. Their email column is
        # a real-looking address routed to a sink, but we still must NEVER
        # actually dispatch to a provider — both for 정통망법 §50 safety
        # (sim users never give marketing consent) and SendGrid quota.
        # Short-circuits BEFORE the opt-out tuple so we don't burn the
        # opt-out log line on every sim send.
        if getattr(user, "is_simulated", False):
            logger.info(
                "skipping email for simulated user id=%s",
                getattr(user, "id", "?"),
            )
            return False

        # ── 1b. opt-out gate ───────────────────────────────────────────
        # Wave G-1 Bug #8 (2026-05-18): consents.py spec —
        #   effective consent = marketing_consent_at IS NOT NULL
        #                       AND (revoked_at IS NULL OR revoked_at < consent_at)
        # email_opt_out flag 만 보고 보냈더니, marketing_consent_at 이 한 번도
        # set 된 적 없는 (회원가입 직후 settings 미방문) 유저에게도 마케팅성
        # 이메일이 발송될 수 있었다. 정통망법 §50 ① default-deny 원칙으로
        # marketing_consent_at NULL = 발송 차단.
        if not getattr(user, "marketing_consent_at", None):
            logger.debug(
                "skipping email for user %s — marketing_consent_at NULL "
                "(정통망법 §50 default-deny)",
                getattr(user, "id", "?"),
            )
            return False

        # ── 1c. category-split consent gate (Wave D Sub-wave 1, C-S1) ──
        # Feature-flagged behind ``PIVOX_CS1_CONSENT_ENABLED`` (default false)
        # so the schema + routes can deploy ahead of the lawyer's Q-S1 answer.
        # When the flag is off OR the caller omits ``email_category``, behaviour
        # is identical to the pre-CS1 baseline (no extra gating). When the flag
        # is on AND a category is supplied, INFORMATION / MARKETING sends are
        # blocked unless the corresponding per-category consent timestamp is
        # set and not revoked. TRANSACTIONAL always passes through.
        if email_category is not None and _cs1_consent_enabled():
            if not _has_category_consent(user, email_category):
                logger.info(
                    "skipping %s email for user %s — category consent missing "
                    "(정통망법 §50 ① 분리 동의 미수령)",
                    email_category.value, getattr(user, "id", "?"),
                )
                return False

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

        # ── 3. provider cascade: SendGrid → Brevo → SMTP ───────────────
        # Operational override: ``BREVO_PROVIDER_PRIMARY=true`` flips
        # the first two tiers (Brevo first, SendGrid fallback). SMTP
        # remains the last-resort transport in both orderings. The
        # lazy import below avoids loading the provider modules when
        # only SMTP / dev-mode is configured.
        from services.email import brevo_provider as _brevo_provider  # local import

        sg_key = os.environ.get("SENDGRID_API_KEY")
        brevo_first = _brevo_provider.is_primary()

        # Build the ordered tier list once so we don't repeat the
        # ``brevo_first`` branch logic. Each entry is
        # ``(label, predicate, callable)``; the predicate gates whether
        # the tier is even attempted (e.g. SendGrid skipped when
        # ``SENDGRID_API_KEY`` is unset). Each callable raises on
        # non-2xx; ``True`` short-circuits the cascade.
        def _try_sendgrid() -> bool:
            return self._send_via_sendgrid(
                sg_key=sg_key or "",
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

        def _try_brevo() -> bool:
            return self._send_via_brevo(
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

        # Brevo predicate: any of the two accepted env keys present.
        brevo_configured = bool(
            os.environ.get("BREVO_API_KEY")
            or os.environ.get("SENDINBLUE_API_KEY")
        )

        tiers: list[tuple[str, bool, Any]] = (
            [
                ("Brevo", brevo_configured, _try_brevo),
                ("SendGrid", bool(sg_key), _try_sendgrid),
            ]
            if brevo_first
            else [
                ("SendGrid", bool(sg_key), _try_sendgrid),
                ("Brevo", brevo_configured, _try_brevo),
            ]
        )

        for label, configured, attempt in tiers:
            if not configured:
                continue
            try:
                if attempt():
                    # Tag the provider used so cost-monitor can
                    # attribute usage per provider when scraping logs.
                    logger.info(
                        "email dispatched via %s for user %s",
                        label, getattr(user, "id", "?"),
                    )
                    return True
            except Exception:
                # Log + fall through to the next tier. The Phase 2
                # baseline used to short-circuit to ``return False``
                # on the first SendGrid exception, but that made a
                # transient 5xx silently kill the email even when a
                # fallback was configured. Cascading is strictly safer.
                logger.exception(
                    "%s send failed for user %s; trying next transport",
                    label, getattr(user, "id", "?"),
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

        # SendGrid SDK는 python_http_client 기반. 기본 timeout이 무한이라
        # send()가 hang될 수 있음 → 명시적 10s timeout 주입.
        sg_client = SendGridAPIClient(sg_key)
        try:
            # python_http_client.Client.timeout 속성 (urllib2 timeout)
            sg_client.client.timeout = 10
        except Exception:
            logger.debug("SendGrid timeout set failed", exc_info=True)
        sg_client.send(mail)
        return True

    def _send_via_brevo(
        self,
        *,
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
        """Brevo (Sendinblue v3) path. Returns ``True`` on 2xx.

        Bridges the artifact cascade into
        :mod:`services.email.brevo_provider`. We re-use the same
        ``SystemMailRecipient`` shape for parity with the system-mail
        path, but pass the unsubscribe URL via the ``html_body``
        (already injected upstream by
        :func:`services.email_token.inject_unsubscribe_footer`) — the
        Brevo SDK does not have an ``add_header`` equivalent for arbitrary
        SMTP headers on the v3 transactional API, so RFC 8058
        ``List-Unsubscribe`` ends up in the body footer only. Gmail /
        Outlook's inline "Unsubscribe" button is therefore SendGrid-
        only when this fallback fires; the inline footer link still
        functions, which is the regulatory minimum (정통망법 §50).

        Imports the provider module lazily so unit tests that don't
        exercise the fallback don't have to pre-import it.
        """
        from services.email import brevo_provider as _brevo_provider

        recipient = _brevo_provider.SystemMailRecipient(
            email=to_email,
            # No user_id here — sender.py:_send_via_* are post-opt-out;
            # the upstream gate already vetted the user.
        )

        return _brevo_provider.send(
            recipient,
            subject=subject,
            html_body=html_body,
            from_email=from_email,
            from_name=display_name,
            reply_to=reply_to,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
            attachment_mime=attachment_mime,
            # Artifact mailers already enforce marketing_consent_at at
            # the EmailSender.send level (sender.py:166) — passing
            # ``honour_consent=False`` here avoids a double-gate. The
            # transactional callers of brevo_provider directly still get
            # the gate when they pass ``honour_consent=True``.
            honour_consent=False,
        )

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
