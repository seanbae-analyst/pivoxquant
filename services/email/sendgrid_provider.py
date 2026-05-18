"""Direct SendGrid v3 transport for **system / transactional** emails.

Scope vs ``sender.py`` (intentional split)
------------------------------------------
``sender.py`` (:class:`~services.email.sender.EmailSender`) owns the
**17 artefact mailers** — opinionated cascade (SendGrid → SMTP → skip),
unsubscribe footer injection, ``marketing_consent_at`` default-deny
(정통망법 §50), display-name + Reply-To, PDF attachment. Do **not**
duplicate that logic here. New artefact callers MUST continue to use
``EmailSender``.

This module is for the narrow class of non-artefact emails that
``EmailSender`` is overkill for:

* OAuth provisioning confirmations (no PDF, no opt-out gate — legally
  required system mail)
* Password reset / 2FA codes (transactional, time-sensitive)
* Admin alerts (``ALERT_EMAIL_TO`` recipients, not real users)
* Internal bounce / DMARC report ingestion replies

Why a thin wrapper at all?
~~~~~~~~~~~~~~~~~~~~~~~~~~
1. **One place to enforce 0-cost free-tier discipline** —
   ``feedback_no_extra_cost``. A single ``MailSendRateLimitExceeded``
   exception type lets callers fail loudly when the 100/day SendGrid
   free quota is hit, rather than silently 429-bouncing.
2. **One place to read SendGrid env consistently** — the new env keys
   ``SENDGRID_API_KEY``, ``SENDGRID_FROM_EMAIL``, ``SENDGRID_FROM_NAME``
   from ``docs/ops/email-setup-2026-05-18.md`` resolve here.
3. **Lazy SDK import** — keeps local dev / unit tests free of the
   ``sendgrid`` dependency cost path. ``requirements.txt`` already pins
   ``sendgrid>=6.12.5`` so the dependency is there, but lazy import
   means a test that monkey-patches transport never has to install.
4. **Single retry policy** — exponential backoff on 5xx only (4xx is
   bad-request, retry would just re-burn quota). Bounded to 3 tries.

Behaviour contract (must NOT silently expand)
---------------------------------------------
* Honours ``user.marketing_consent_at`` only when ``honour_consent=True``
  (default ``False`` because transactional mail is exempt from §50).
  Callers that send marketing-adjacent system mail MUST pass
  ``honour_consent=True`` to get the same gate as ``EmailSender``.
* Returns ``True`` on 2xx, raises typed exceptions otherwise.
  No silent swallow — system mail failure is operationally meaningful.
* No HTML body mutation (no unsubscribe footer injection). Use
  ``EmailSender`` if you need that — this module is for emails where
  injecting an unsubscribe link is wrong (e.g. a 2FA code).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Sequence

logger = logging.getLogger(__name__)


# ── env keys (single source — mirrored in docs/ops/email-setup-2026-05-18.md §4) ─
_ENV_API_KEY = "SENDGRID_API_KEY"
_ENV_FROM_EMAIL = "SENDGRID_FROM_EMAIL"
_ENV_FROM_NAME = "SENDGRID_FROM_NAME"
_ENV_SUPPORT_EMAIL = "SUPPORT_EMAIL"

# ── fallback defaults (used only when env unset; matches noreply@ convention) ─
_DEFAULT_FROM_EMAIL = "noreply@pivoxquant.com"
_DEFAULT_FROM_NAME = "PivoxQuant"
_DEFAULT_SUPPORT_EMAIL = "support@pivoxquant.com"

# ── retry policy ─────────────────────────────────────────────────────
# 3 tries with 1s / 2s backoff. Anything 5xx is retryable; 4xx is not
# (retry would just re-burn the 100/day free-tier quota).
_MAX_RETRIES = 3
_BACKOFF_BASE_SEC = 1.0

# ── timeout ──────────────────────────────────────────────────────────
# Mirrors sender.py:339 (10s). SendGrid SDK default is unbounded which
# would block the request thread forever on a network partition.
_HTTP_TIMEOUT_SEC = 10


# ── typed errors — callers can distinguish quota vs config vs network ─

class SendGridProviderError(RuntimeError):
    """Base for all sendgrid_provider failures."""


class SendGridNotConfigured(SendGridProviderError):
    """``SENDGRID_API_KEY`` env var is unset — caller must decide fallback."""


class SendGridRateLimitExceeded(SendGridProviderError):
    """SendGrid returned 429 — free-tier 100/day quota reached.

    cost-monitor agent should alert when this fires; system mail
    delivery is materially degraded until next day or quota upgrade.
    """


class SendGridBadRequest(SendGridProviderError):
    """SendGrid returned 4xx (other than 429) — usually unverified
    sender / malformed payload. Not retryable."""


class SendGridUpstreamError(SendGridProviderError):
    """SendGrid returned 5xx after all retries — provider outage."""


# ── consent-gated user-shaped duck type ──────────────────────────────

@dataclass(frozen=True)
class SystemMailRecipient:
    """Minimal recipient shape for system mail.

    Frozen so a caller can't mutate during retry. ``marketing_consent_at``
    only matters when ``honour_consent=True`` is passed to ``send``.
    """
    email: str
    user_id: int | str | None = None
    marketing_consent_at: object | None = None
    is_simulated: bool = False


def send(
    recipient: SystemMailRecipient | str,
    *,
    subject: str,
    html_body: str,
    plain_body: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
    categories: Sequence[str] = (),
    honour_consent: bool = False,
) -> bool:
    """Send a single system / transactional email via SendGrid v3 API.

    Parameters
    ----------
    recipient
        Either a ``SystemMailRecipient`` (preferred — gives us
        ``is_simulated`` + consent fields) or a bare email string for
        admin alerts where there's no associated User row.
    subject, html_body
        Already-rendered. No template engine here.
    plain_body
        Optional ``text/plain`` alternative. Strongly recommended for
        deliverability — Gmail flags HTML-only mail as spam. When
        ``None``, a minimal fallback is added (mirrors ``sender.py:379``).
    from_email, from_name
        Per-call overrides. Falls back to ``SENDGRID_FROM_EMAIL`` /
        ``SENDGRID_FROM_NAME`` env, then to ``noreply@pivoxquant.com`` /
        ``PivoxQuant``.
    reply_to
        Override Reply-To. Defaults to ``SUPPORT_EMAIL`` env or
        ``support@pivoxquant.com``.
    categories
        SendGrid stats categories (e.g. ``("oauth", "provisioning")``).
        Useful for the Activity Feed filter that cost-monitor reads.
    honour_consent
        ``False`` (default) — transactional exempt from 정통망법 §50.
        ``True`` — apply the same ``marketing_consent_at`` default-deny
        gate as ``EmailSender``. Use for borderline system mail that
        also carries marketing content (rare; usually wrong path —
        use ``EmailSender`` instead).

    Returns
    -------
    bool
        ``True`` on 2xx accepted dispatch.

    Raises
    ------
    SendGridNotConfigured
        ``SENDGRID_API_KEY`` env unset. Caller chooses fallback.
    SendGridRateLimitExceeded
        SendGrid 429 — free-tier quota hit.
    SendGridBadRequest
        SendGrid 4xx (config / payload error).
    SendGridUpstreamError
        SendGrid 5xx after ``_MAX_RETRIES`` retries.
    """
    api_key = os.environ.get(_ENV_API_KEY)
    if not api_key:
        raise SendGridNotConfigured(
            f"{_ENV_API_KEY} not set — see docs/ops/email-setup-2026-05-18.md §4"
        )

    # Normalise recipient to dataclass for uniform downstream handling.
    rcpt = (
        recipient
        if isinstance(recipient, SystemMailRecipient)
        else SystemMailRecipient(email=recipient)
    )

    # ── simulated-user guard (Continuous User Simulation Phase 1) ──
    # Mirrors sender.py:151. Sim users must never hit the provider —
    # both for §50 safety (no marketing consent) and SendGrid quota.
    if rcpt.is_simulated:
        logger.info(
            "skipping system mail for simulated recipient user_id=%s",
            rcpt.user_id,
        )
        return False

    # ── opt-in gate (only when caller asks) ──
    if honour_consent and not rcpt.marketing_consent_at:
        logger.info(
            "skipping system mail for user_id=%s — marketing_consent_at "
            "NULL and honour_consent=True (정통망법 §50 default-deny)",
            rcpt.user_id,
        )
        return False

    # ── resolve sender identity ──
    eff_from_email = from_email or os.environ.get(_ENV_FROM_EMAIL, _DEFAULT_FROM_EMAIL)
    eff_from_name = from_name or os.environ.get(_ENV_FROM_NAME, _DEFAULT_FROM_NAME)
    eff_reply_to = reply_to or os.environ.get(_ENV_SUPPORT_EMAIL, _DEFAULT_SUPPORT_EMAIL)

    # ── lazy SDK import (mirrors sender.py:289 rationale) ──
    from sendgrid import SendGridAPIClient  # type: ignore[import-not-found]
    from sendgrid.helpers.mail import (  # type: ignore[import-not-found]
        Category,
        Mail,
        ReplyTo,
    )

    mail = Mail(
        from_email=(eff_from_email, eff_from_name),
        to_emails=rcpt.email,
        subject=subject,
        html_content=html_body,
        plain_text_content=plain_body or "HTML-only; view in an HTML-capable client.",
    )
    mail.reply_to = ReplyTo(eff_reply_to)
    for cat in categories:
        mail.add_category(Category(cat))

    client = SendGridAPIClient(api_key)
    try:
        # python_http_client timeout knob — same as sender.py:339.
        client.client.timeout = _HTTP_TIMEOUT_SEC
    except Exception:
        logger.debug("SendGrid timeout set failed", exc_info=True)

    # ── send with bounded retry ──
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = client.send(mail)
            status = getattr(resp, "status_code", None)
            if status is not None and 200 <= status < 300:
                logger.info(
                    "sendgrid_provider sent to user_id=%s status=%s attempt=%d",
                    rcpt.user_id, status, attempt,
                )
                return True
            # SDK normally raises on non-2xx, but defensively handle a
            # raw-return path (some test doubles return resp instead of raise).
            if status == 429:
                raise SendGridRateLimitExceeded(
                    f"SendGrid 429 (free-tier 100/day quota) attempt={attempt}"
                )
            if status is not None and 400 <= status < 500:
                raise SendGridBadRequest(f"SendGrid {status}")
            raise SendGridUpstreamError(f"SendGrid status={status}")
        except SendGridRateLimitExceeded:
            # Not retryable — quota is per-day.
            raise
        except SendGridBadRequest:
            # Not retryable — would re-burn quota on same bad payload.
            raise
        except Exception as exc:
            # python_http_client raises HTTPError with .status_code on
            # any non-2xx. Detect 4xx (incl. 429) vs 5xx vs network.
            status = _extract_status(exc)
            if status == 429:
                # Don't even bother retrying — daily quota.
                raise SendGridRateLimitExceeded(
                    f"SendGrid 429 (free-tier 100/day quota); "
                    f"upstream={exc!r}"
                ) from exc
            if status is not None and 400 <= status < 500:
                raise SendGridBadRequest(
                    f"SendGrid {status}: {exc!r}"
                ) from exc
            # 5xx or network — retry with backoff.
            last_exc = exc
            if attempt < _MAX_RETRIES:
                sleep_for = _BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                logger.warning(
                    "sendgrid_provider attempt=%d/%d failed status=%s; "
                    "sleeping %.1fs before retry",
                    attempt, _MAX_RETRIES, status, sleep_for,
                )
                time.sleep(sleep_for)
                continue
            # exhausted
            raise SendGridUpstreamError(
                f"SendGrid 5xx after {_MAX_RETRIES} attempts: {exc!r}"
            ) from exc

    # Unreachable (loop either returns True, raises, or continues).
    raise SendGridUpstreamError(  # pragma: no cover
        f"SendGrid send exhausted retries: {last_exc!r}"
    )


def _extract_status(exc: Exception) -> int | None:
    """Best-effort HTTP status extraction from a SendGrid SDK exception.

    ``python_http_client.exceptions.HTTPError`` exposes ``.status_code``
    in newer versions and ``.code`` in older ones. We try both.
    """
    for attr in ("status_code", "code"):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            return v
    return None


__all__ = [
    "SystemMailRecipient",
    "SendGridProviderError",
    "SendGridNotConfigured",
    "SendGridRateLimitExceeded",
    "SendGridBadRequest",
    "SendGridUpstreamError",
    "send",
]
