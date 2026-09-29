"""One owner for the email provider order (Brevo / SendGrid).

Why this module exists (2026-09-29)
-----------------------------------
The Brevo/SendGrid cascade had been written five times:

* ``services/email/sender.py`` (``EmailSender``) — respected
  ``BREVO_PROVIDER_PRIMARY``;
* ``routes/support.py::_notify_operator`` — respected it;
* ``services/billing_notifications.py`` and ``services/billing_followup.py``
  — hard-coded SendGrid first;
* ``scripts/nightly/notify_email.sh`` — SendGrid only.

prod runs with the SendGrid key dead and Brevo primary (render.yaml), so the
hard-coded copies spent a failing SendGrid call on every send before falling
back — and each copy logged its failure differently. Now:

* :func:`provider_order` is the single rule for *which providers, in what
  order*: Brevo first iff :func:`brevo_provider.is_primary`, else SendGrid
  first; a provider without an API key is left out. ``EmailSender`` builds
  its cascade from it (it still owns its SMTP last resort and its consent
  gates — nothing about §50 gating moved here).
* :func:`send_system_mail` is the whole cascade for **system / transactional**
  mail (operator alerts, billing notices): it walks that order, falls through
  on an exception or a non-accept, returns ``True`` on the first accept, and
  on total failure logs one WARNING naming every provider's error. It never
  raises.

What it deliberately does not do
--------------------------------
* No marketing-consent gate: callers are §50-exempt system mail, so both
  providers are called with ``honour_consent=False``. Anything that needs the
  consent / opt-out / notification-matrix gates goes through ``EmailSender``.
* No unsubscribe footer / List-Unsubscribe header (wrong for a billing or
  operator notice).
* Simulated users (``users.is_simulated``, CLAUDE.md trap 7) are refused
  here *and* by each provider — pass ``user=`` so the flag travels.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Sequence

logger = logging.getLogger(__name__)

SENDGRID = "sendgrid"
BREVO = "brevo"


def _brevo_configured() -> bool:
    return bool(
        os.environ.get("BREVO_API_KEY") or os.environ.get("SENDINBLUE_API_KEY")
    )


def _sendgrid_configured() -> bool:
    return bool(os.environ.get("SENDGRID_API_KEY"))


def provider_order() -> list[str]:
    """Configured providers, in the order they must be tried.

    Brevo first when ``BREVO_PROVIDER_PRIMARY`` is truthy
    (:func:`services.email.brevo_provider.is_primary`), SendGrid first
    otherwise. Providers whose API key env var is unset are omitted.
    Read live on every call — tests and ops flip env at runtime.
    """
    from services.email import brevo_provider

    order = [BREVO, SENDGRID] if brevo_provider.is_primary() else [SENDGRID, BREVO]
    configured = {BREVO: _brevo_configured(), SENDGRID: _sendgrid_configured()}
    return [p for p in order if configured[p]]


def send_system_mail(
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    *,
    user: Any | None = None,
    category: Sequence[str] = (),
    from_email: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
    log_label: str = "system mail",
) -> bool:
    """Send one system / transactional email through the provider order.

    Parameters
    ----------
    to
        Recipient address.
    subject, html, text
        Already rendered. ``text`` is the optional text/plain part.
    user
        Optional ``User`` row (or duck type) the mail is about. Supplies
        ``id`` for logs and ``is_simulated`` for the sim-user guard.
    category
        Stats buckets — SendGrid ``categories`` / Brevo ``tags``.
    from_email, from_name, reply_to
        Per-call overrides; each provider falls back to its own env/defaults.
    log_label
        Human name for this mail in the success / failure log lines.

    Returns ``True`` when a provider accepted the dispatch. Never raises.
    """
    user_id = getattr(user, "id", None) if user is not None else None
    is_simulated = bool(getattr(user, "is_simulated", False)) if user is not None else False
    if is_simulated:
        logger.info("%s skipped for simulated user id=%s", log_label, user_id)
        return False

    from services.email import brevo_provider, sendgrid_provider

    def _via_sendgrid() -> bool:
        rcpt = sendgrid_provider.SystemMailRecipient(
            email=to, user_id=user_id, is_simulated=is_simulated,
        )
        return sendgrid_provider.send(
            rcpt,
            subject=subject,
            html_body=html,
            plain_body=text,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            categories=tuple(category),
            honour_consent=False,  # system mail — 정통망법 §50 exempt
        )

    def _via_brevo() -> bool:
        rcpt = brevo_provider.SystemMailRecipient(
            email=to, user_id=user_id, is_simulated=is_simulated,
        )
        return brevo_provider.send(
            rcpt,
            subject=subject,
            html_body=html,
            plain_body=text,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            tags=tuple(category),
            honour_consent=False,  # system mail — 정통망법 §50 exempt
        )

    attempts = {SENDGRID: _via_sendgrid, BREVO: _via_brevo}
    errors: list[str] = []
    for name in provider_order():
        try:
            if attempts[name]():
                logger.info("%s sent via %s (user=%s)", log_label, name, user_id)
                return True
            errors.append(f"{name}: not accepted")
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            logger.debug("%s via %s failed", log_label, name, exc_info=True)
            try:
                import sentry_sdk

                sentry_sdk.capture_exception(exc)
            except Exception:
                pass

    logger.warning(
        "%s not delivered (user=%s) — %s",
        log_label, user_id, "; ".join(errors) or "no provider configured",
    )
    return False


__all__ = ["provider_order", "send_system_mail", "SENDGRID", "BREVO"]
