"""PIPA §22 ⑥ — server-side minimum-age gate (self-declaration).

개인정보 보호법 (PIPA) §22 ⑥ requires legal-guardian consent before
collecting personal data from children under 14. PivoxQuant has no such
guardian-consent flow, so we **refuse** under-14 signups rather than
build one.

History — why self-declaration, not a birthdate
------------------------------------------------
2026-05 → 2026-09-19 the product collected a date of birth and parsed it
here (``parse_birthdate_strict`` / ``check_birthdate_payload``). On
2026-09-19 that collection ended: a birthdate is more personal data than
the gate needs, and it was the only PII the product asked for that it
never used for anything else. The gate is now the "만 14세 이상입니다"
checkbox in the signup consent stack. The server verifies the payload
carries a literal ``true`` and stamps the submission time into
``users.age_confirmed_at``.

Whether a self-declaration is sufficient evidence under §22 ⑥ is an open
lawyer question — Q9 in ``docs/legal/legal-audit-2026-06-05.md``. Until it
is answered this module is the whole server-side defense; the frontend
checkbox is UX, not evidence.

``users.birthdate`` is kept (column + data) so users from the birthdate
era stay unlocked — see ``User.age_confirmed``. Nothing writes it anymore.

Why this lives in ``services/`` not ``routes/``
------------------------------------------------
Two routes create or complete a ``User`` row and both must apply the
same rule:

  1. ``routes/auth.py`` ``/api/auth/register`` (email + password)
  2. ``routes/auth.py`` ``/api/auth/oauth-finalize`` (Google / Kakao
     post-callback interstitial)

A shared helper keeps them from drifting — audit W1.4 flagged exactly
that drift in the birthdate era (the OAuth path had zero validation).

Error contract
--------------
``check_age_confirmation_payload`` raises ``AgeConfirmationError`` with a
stable machine-readable ``code`` (i18n key). Routes translate it into a
400 JSON body; the frontend matches on the code, not the message.

Codes:
  * ``age_confirmation_required`` — payload value is not literal ``true``
    (missing, ``false``, ``"true"``, ``1``, ``"on"`` … all count as absent;
    only an explicit boolean opt-in is evidence).
"""
from __future__ import annotations


# PIPA §22 ⑥ threshold — 만 14세. The number no longer drives any
# arithmetic (no birthdate to subtract from) but it is the figure the
# checkbox copy and the legal docs cite, so it stays as the single SoT.
MIN_AGE: int = 14


class AgeConfirmationError(ValueError):
    """Raised when a payload does not carry an explicit age self-declaration.

    ``code`` is the stable key routes forward to the client; ``message``
    is a developer-facing detail that never reaches the response.
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def check_age_confirmation_payload(value: object) -> None:
    """Validate the self-declaration flag from a request payload.

    Accepts only the literal boolean ``True``. Anything else — ``None``
    (field missing), ``False``, truthy strings, ``1`` — raises
    ``AgeConfirmationError("age_confirmation_required")``. Returns
    ``None`` on success; the caller stamps ``age_confirmed_at`` itself so
    the timestamp convention stays in one place (``routes/consents.py``
    ``_utcnow_naive``).
    """
    if value is not True:
        raise AgeConfirmationError(
            "age_confirmation_required",
            f"age self-declaration not literal true: {value!r}",
        )


__all__ = [
    "MIN_AGE",
    "AgeConfirmationError",
    "check_age_confirmation_payload",
]
