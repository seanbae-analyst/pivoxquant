"""Direct Brevo (formerly Sendinblue) v3 transport for **system / transactional** emails.

Scope vs ``sendgrid_provider.py`` (sibling — read that first)
-------------------------------------------------------------
``sendgrid_provider.py`` is the **primary** transactional path
(SendGrid free 100/day). This module is the **fallback** path:

* When ``SENDGRID_API_KEY`` is unset (dev / partial config), OR
* When SendGrid raises :class:`SendGridRateLimitExceeded` (429 — daily
  quota exhausted), OR
* When ``BREVO_PROVIDER_PRIMARY=true`` env flag flips the priority
  (operationally useful if SendGrid's domain reputation degrades).

Combined budget: SendGrid 100/day + **Brevo 300/day** = **400/day**
~= 12,000/mo. Enough headroom from beta (5–10 users) through ~1k users
before any paid tier is required. Honours
:doc:`memory/feedback_no_extra_cost`.

Scope vs ``sender.py`` (intentional split — same as sendgrid_provider)
----------------------------------------------------------------------
``sender.py`` (:class:`~services.email.sender.EmailSender`) owns the
**17 artefact mailers** — opinionated cascade, unsubscribe footer
injection, ``marketing_consent_at`` default-deny (정통망법 §50),
display-name + Reply-To, PDF attachment. ``sender.py`` calls *into*
this module as a transport tier; it does **not** wrap us with another
opt-out gate. Do **not** duplicate that logic here.

This module — like ``sendgrid_provider.py`` — is also directly callable
for the narrow class of non-artefact system mail (OAuth provisioning
confirmations, password reset / 2FA codes, admin alerts) where
``EmailSender`` is overkill. Honours its own typed exceptions so
callers can fall through cleanly.

Why a thin wrapper at all?
~~~~~~~~~~~~~~~~~~~~~~~~~~
1. **One place to enforce 0-cost free-tier discipline** —
   ``feedback_no_extra_cost``. A single
   :class:`BrevoRateLimitExceeded` lets callers fail loudly when the
   300/day Brevo free quota is hit.
2. **One place to read Brevo env consistently** — the new env keys
   ``BREVO_API_KEY``, ``BREVO_FROM_EMAIL``, ``BREVO_FROM_NAME`` from
   ``docs/ops/email-setup-2026-05-18.md`` §4 resolve here. We also
   accept the legacy ``SENDINBLUE_API_KEY`` (Brevo rebrand 2023) so a
   CEO who already has a Sendinblue account doesn't need to recreate.
3. **Lazy ``requests`` import** — keeps cold-start unaffected for
   deploys that never hit the fallback path. ``requests`` is already
   a transitive dep so no new ``requirements.txt`` line is needed.
4. **Single retry policy** — exponential backoff on 5xx only (4xx is
   bad-request, retry would just re-burn quota). Bounded to 3 tries.
5. **Provider-distinguishable telemetry** — every send emits a log
   line tagged ``brevo_provider`` so cost-monitor can attribute usage
   per provider (vs lumped "email sent" counters).

Behaviour contract (must NOT silently expand)
---------------------------------------------
* Honours ``user.marketing_consent_at`` only when ``honour_consent=True``
  (default ``False`` because transactional mail is exempt from §50).
* Returns ``True`` on 2xx, raises typed exceptions otherwise.
  No silent swallow — system mail failure is operationally meaningful.
* No HTML body mutation (no unsubscribe footer injection). Use
  ``EmailSender`` if you need that — this module is for emails where
  injecting an unsubscribe link is wrong (e.g. a 2FA code).
* PDF attachment via base64 ``content`` field (Brevo v3 spec).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Sequence

logger = logging.getLogger(__name__)


# ── env keys (single source — mirrored in docs/ops/email-setup-2026-05-18.md §4) ─
# Accept both ``BREVO_*`` (current) and ``SENDINBLUE_*`` (legacy 2023
# rebrand). Operationally a CEO with a pre-rebrand Sendinblue account
# does not need to mint new keys — Brevo treats the keys interchangeably.
_ENV_API_KEY_PRIMARY = "BREVO_API_KEY"
_ENV_API_KEY_LEGACY = "SENDINBLUE_API_KEY"
_ENV_FROM_EMAIL = "BREVO_FROM_EMAIL"
_ENV_FROM_NAME = "BREVO_FROM_NAME"
_ENV_SUPPORT_EMAIL = "SUPPORT_EMAIL"

# Operational override: when set to "true"/"1"/"yes" the cascade in
# ``sender.py`` prefers Brevo over SendGrid. Useful if SendGrid's
# domain reputation degrades or its 100/day cap is hit early in the
# day and we want fresh sends routed to Brevo immediately.
_ENV_BREVO_PRIMARY = "BREVO_PROVIDER_PRIMARY"

# ── fallback defaults (used only when env unset; matches noreply@ convention) ─
_DEFAULT_FROM_EMAIL = "noreply@pivoxquant.com"
_DEFAULT_FROM_NAME = "PivoxQuant"
_DEFAULT_SUPPORT_EMAIL = "support@pivoxquant.com"

# ── Brevo v3 endpoint ────────────────────────────────────────────────
# https://developers.brevo.com/reference/sendtransacemail
_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"

# ── retry policy ─────────────────────────────────────────────────────
# 3 tries with 1s / 2s backoff. Anything 5xx is retryable; 4xx is not
# (retry would just re-burn the 300/day free-tier quota).
_MAX_RETRIES = 3
_BACKOFF_BASE_SEC = 1.0

# ── timeout ──────────────────────────────────────────────────────────
# Mirrors sender.py:339 (10s). Brevo API is normally <1s but a network
# partition would otherwise hang the request thread.
_HTTP_TIMEOUT_SEC = 10


# ── typed errors — callers can distinguish quota vs config vs network ─

class BrevoProviderError(RuntimeError):
    """Base for all brevo_provider failures."""


class BrevoNotConfigured(BrevoProviderError):
    """Neither ``BREVO_API_KEY`` nor ``SENDINBLUE_API_KEY`` env var set."""


class BrevoRateLimitExceeded(BrevoProviderError):
    """Brevo returned 429 — free-tier 300/day quota reached.

    cost-monitor agent should alert when this fires; combined with a
    concurrent ``SendGridRateLimitExceeded`` it means the 400/day
    aggregate budget is exhausted and SMTP fallback (if configured)
    is the only remaining transport.
    """


class BrevoBadRequest(BrevoProviderError):
    """Brevo returned 4xx (other than 429) — usually unverified sender
    / unverified domain / malformed payload. Not retryable."""


class BrevoUpstreamError(BrevoProviderError):
    """Brevo returned 5xx after all retries — provider outage."""


# ── consent-gated user-shaped duck type ──────────────────────────────
# Re-declared (not imported from sendgrid_provider) to keep this
# module standalone — a future refactor that wants to swap providers
# entirely shouldn't need to keep sendgrid_provider around just for
# its dataclass.

@dataclass(frozen=True)
class SystemMailRecipient:
    """Minimal recipient shape for system mail. Mirrors
    :class:`services.email.sendgrid_provider.SystemMailRecipient` so
    callers can pass the same instance to either provider.

    Frozen so a caller can't mutate during retry. ``marketing_consent_at``
    only matters when ``honour_consent=True`` is passed to ``send``.
    """
    email: str
    user_id: int | str | None = None
    marketing_consent_at: object | None = None
    is_simulated: bool = False


def is_primary() -> bool:
    """Return ``True`` when ``BREVO_PROVIDER_PRIMARY`` env asks the
    cascade in ``sender.py`` to prefer Brevo over SendGrid.

    Accepts ``"true"``, ``"1"``, ``"yes"`` (case-insensitive). Anything
    else — including unset — returns ``False`` (default = SendGrid
    primary, Brevo fallback).
    """
    raw = os.environ.get(_ENV_BREVO_PRIMARY, "").strip().lower()
    return raw in ("true", "1", "yes")


def _resolve_api_key() -> str | None:
    """Look up the API key, preferring the current ``BREVO_*`` name
    over the legacy ``SENDINBLUE_*`` name. Returns ``None`` when
    neither is set so the caller can raise the right exception.
    """
    for env_key in (_ENV_API_KEY_PRIMARY, _ENV_API_KEY_LEGACY):
        value = os.environ.get(env_key)
        if value:
            return value
    return None


def send(
    recipient: SystemMailRecipient | str,
    *,
    subject: str,
    html_body: str,
    plain_body: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
    tags: Sequence[str] = (),
    pdf_bytes: bytes | None = None,
    pdf_filename: str | None = None,
    attachment_mime: str = "application/pdf",
    honour_consent: bool = False,
) -> bool:
    """Send a single system / transactional email via Brevo v3 API.

    Parameters
    ----------
    recipient
        Either a :class:`SystemMailRecipient` (preferred — gives us
        ``is_simulated`` + consent fields) or a bare email string for
        admin alerts where there's no associated User row.
    subject, html_body
        Already-rendered. No template engine here.
    plain_body
        Optional ``text/plain`` alternative. Strongly recommended for
        deliverability — Gmail flags HTML-only mail as spam. When
        ``None``, a minimal fallback is added (mirrors ``sender.py:379``).
    from_email, from_name
        Per-call overrides. Falls back to ``BREVO_FROM_EMAIL`` /
        ``BREVO_FROM_NAME`` env, then to ``noreply@pivoxquant.com`` /
        ``PivoxQuant``.
    reply_to
        Override Reply-To. Defaults to ``SUPPORT_EMAIL`` env or
        ``support@pivoxquant.com``.
    tags
        Brevo "tags" (~SendGrid categories — Activity Feed filter).
        cost-monitor reads these to bucket usage per artifact type.
    pdf_bytes, pdf_filename, attachment_mime
        Optional binary attachment. Encoded base64 into the Brevo
        ``attachment`` array element ``content`` field per v3 spec.
    honour_consent
        ``False`` (default) — transactional exempt from 정통망법 §50.
        ``True`` — apply the same ``marketing_consent_at`` default-deny
        gate as ``EmailSender``.

    Returns
    -------
    bool
        ``True`` on 2xx accepted dispatch.

    Raises
    ------
    BrevoNotConfigured
        Neither ``BREVO_API_KEY`` nor ``SENDINBLUE_API_KEY`` env set.
    BrevoRateLimitExceeded
        Brevo 429 — free-tier 300/day quota hit.
    BrevoBadRequest
        Brevo 4xx (config / payload error).
    BrevoUpstreamError
        Brevo 5xx after ``_MAX_RETRIES`` retries.
    """
    api_key = _resolve_api_key()
    if not api_key:
        raise BrevoNotConfigured(
            f"Neither {_ENV_API_KEY_PRIMARY} nor {_ENV_API_KEY_LEGACY} "
            f"is set — see docs/ops/email-setup-2026-05-18.md §4"
        )

    # Normalise recipient to dataclass for uniform downstream handling.
    rcpt = (
        recipient
        if isinstance(recipient, SystemMailRecipient)
        else SystemMailRecipient(email=recipient)
    )

    # ── simulated-user guard (Continuous User Simulation Phase 1) ──
    # Mirrors sender.py:151 and sendgrid_provider.py:200. Sim users
    # must never hit the provider — both for §50 safety (no marketing
    # consent) and Brevo quota.
    if rcpt.is_simulated:
        logger.info(
            "brevo_provider: skipping system mail for simulated "
            "recipient user_id=%s",
            rcpt.user_id,
        )
        return False

    # ── opt-in gate (only when caller asks) ──
    if honour_consent and not rcpt.marketing_consent_at:
        logger.info(
            "brevo_provider: skipping system mail for user_id=%s — "
            "marketing_consent_at NULL and honour_consent=True "
            "(정통망법 §50 default-deny)",
            rcpt.user_id,
        )
        return False

    # ── resolve sender identity ──
    eff_from_email = from_email or os.environ.get(_ENV_FROM_EMAIL, _DEFAULT_FROM_EMAIL)
    eff_from_name = from_name or os.environ.get(_ENV_FROM_NAME, _DEFAULT_FROM_NAME)
    eff_reply_to = reply_to or os.environ.get(_ENV_SUPPORT_EMAIL, _DEFAULT_SUPPORT_EMAIL)

    # ── build Brevo v3 payload ──
    # https://developers.brevo.com/reference/sendtransacemail
    payload: dict[str, object] = {
        "sender": {"email": eff_from_email, "name": eff_from_name},
        "to": [{"email": rcpt.email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": plain_body or "HTML-only; view in an HTML-capable client.",
    }
    if eff_reply_to:
        payload["replyTo"] = {"email": eff_reply_to}
    if tags:
        # Brevo accepts up to 10 tags per send; cap defensively.
        payload["tags"] = list(tags)[:10]
    if pdf_bytes:
        payload["attachment"] = [
            {
                "name": pdf_filename or "report.pdf",
                # Brevo wants base64 string in the ``content`` field.
                # ``attachment_mime`` is metadata only — Brevo infers
                # MIME from filename extension. Logged for ops parity.
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        ]
        logger.debug(
            "brevo_provider attaching file name=%s mime=%s bytes=%d",
            pdf_filename or "report.pdf", attachment_mime, len(pdf_bytes),
        )

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # ── lazy requests import (mirrors sender.py:289 rationale) ──
    # ``requests`` is a transitive dep via sendgrid / flask plugins so
    # no new requirements.txt pin is needed; the lazy import keeps
    # test paths that monkey-patch this module unaffected.
    import requests  # type: ignore[import-not-found]

    # ── send with bounded retry ──
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(
                _BREVO_SEND_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=_HTTP_TIMEOUT_SEC,
            )
            status = resp.status_code

            # ── 2xx: accepted ──
            # Brevo returns 201 Created with body ``{"messageId": "..."}``.
            if 200 <= status < 300:
                message_id = None
                try:
                    message_id = (resp.json() or {}).get("messageId")
                except Exception:
                    # Body parse failure is non-fatal; we already have 2xx.
                    pass
                logger.info(
                    "brevo_provider sent to user_id=%s status=%s "
                    "messageId=%s attempt=%d",
                    rcpt.user_id, status, message_id, attempt,
                )
                return True

            # ── 429: per-day quota exhausted, not retryable ──
            if status == 429:
                raise BrevoRateLimitExceeded(
                    f"Brevo 429 (free-tier 300/day quota); "
                    f"body={resp.text[:200]!r}"
                )

            # ── other 4xx: bad request, not retryable ──
            if 400 <= status < 500:
                # Common causes: unverified sender (DKIM not yet set
                # up — see docs/ops/email-setup-2026-05-18.md §1-4),
                # invalid recipient, malformed payload.
                raise BrevoBadRequest(
                    f"Brevo {status}: {resp.text[:200]!r}"
                )

            # ── 5xx: provider outage, retryable ──
            last_exc = BrevoUpstreamError(
                f"Brevo {status}: {resp.text[:200]!r}"
            )
            if attempt < _MAX_RETRIES:
                sleep_for = _BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                logger.warning(
                    "brevo_provider attempt=%d/%d failed status=%s; "
                    "sleeping %.1fs before retry",
                    attempt, _MAX_RETRIES, status, sleep_for,
                )
                time.sleep(sleep_for)
                continue
            raise last_exc

        except BrevoRateLimitExceeded:
            raise
        except BrevoBadRequest:
            raise
        except BrevoUpstreamError:
            raise
        except Exception as exc:
            # Network error (DNS, connection reset, read timeout) —
            # treat as retryable. requests.Timeout / ConnectionError
            # both flow here.
            last_exc = exc
            if attempt < _MAX_RETRIES:
                sleep_for = _BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                logger.warning(
                    "brevo_provider attempt=%d/%d network failure %r; "
                    "sleeping %.1fs before retry",
                    attempt, _MAX_RETRIES, exc, sleep_for,
                )
                time.sleep(sleep_for)
                continue
            raise BrevoUpstreamError(
                f"Brevo network failure after {_MAX_RETRIES} "
                f"attempts: {exc!r}"
            ) from exc

    # Unreachable (loop either returns True, raises, or continues).
    raise BrevoUpstreamError(  # pragma: no cover
        f"Brevo send exhausted retries: {last_exc!r}"
    )


__all__ = [
    "SystemMailRecipient",
    "BrevoProviderError",
    "BrevoNotConfigured",
    "BrevoRateLimitExceeded",
    "BrevoBadRequest",
    "BrevoUpstreamError",
    "is_primary",
    "send",
]
