"""PIPA §22 ⑥ — server-side birthdate parsing + minimum-age guard.

개인정보 보호법 (PIPA) §22 ⑥ requires legal-guardian consent before
collecting personal data from children under 14. PivoxQuant has no such
guardian-consent flow at launch, so we **fail-fast** on registration.

The frontend (``frontend/src/lib/age-verification.ts``) implements the
same rules client-side. This module is the *server-side* defense in
depth — every gate that creates a ``User`` row must call
``parse_birthdate_strict`` + ``is_at_least_min_age`` before commit.

Why this lives in ``services/`` not ``routes/``
------------------------------------------------
Two distinct routes need the same check:

  1. ``routes/auth.py`` ``/api/auth/register`` (email + password)
  2. ``routes/auth.py`` ``/api/auth/oauth-finalize`` (Google / Kakao
     post-callback interstitial)

Putting the rules in a single helper avoids drift between the two —
audit W1.4 explicitly flagged that the OAuth path had **zero**
birthdate validation. A shared helper makes that drift impossible.

Error contract
--------------
The helpers raise ``BirthdateValidationError`` with a stable
machine-readable ``code`` (i18n key). Routes translate the code into a
400 JSON response; the frontend matches on the code, not the message.

Codes:
  * ``birthdate_required``        — payload is missing the field
  * ``birthdate_invalid_format``  — not yyyy-mm-dd or unparseable
  * ``birthdate_unrealistic``     — future date or > 120 years old
  * ``below_min_age``             — under 14 (PIPA §22 ⑥)

These match ``frontend/src/lib/age-verification.ts`` so a single
``i18n`` key set covers both layers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime


# PIPA §22 ⑥ threshold — 만 14세. Mirrors
# ``frontend/src/lib/age-verification.ts`` MIN_AGE_YEARS.
MIN_AGE_YEARS: int = 14

# Upper sanity bound. Anyone claiming > 120 is either typo'd or hostile;
# rejecting cuts garbage early without affecting real users (oldest
# verified human at time of writing: 122).
MAX_AGE_YEARS: int = 120

# Earliest acceptable year. Mirrors the frontend `< 1900` reject so the
# two layers cannot diverge.
MIN_BIRTH_YEAR: int = 1900

_BIRTHDATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BirthdateValidationError(ValueError):
    """Raised when a payload-supplied birthdate fails validation.

    ``code`` is a stable machine-readable key the route turns into a
    400 JSON body (e.g. ``{"error": "birthdate_required"}``); ``message``
    is a developer-facing log string only.
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


@dataclass(frozen=True)
class AgeCheckResult:
    """Outcome of ``check_birthdate_payload``.

    ``birthdate``  — the parsed ``datetime.date`` value (only valid when
                     ``ok`` is True).
    ``years``      — completed-year age at ``today`` (only valid when
                     ``ok`` is True).
    ``ok``         — True when the user passes the §22 ⑥ gate.
    """

    birthdate: date | None
    years: int
    ok: bool


def parse_birthdate_strict(value: object) -> date:
    """Parse a yyyy-mm-dd string into a ``date``.

    Raises ``BirthdateValidationError`` with a stable code on failure.
    Empty / non-string / wrong-format / unparseable / future / >120y all
    raise — the caller never has to validate again.
    """
    if value is None:
        raise BirthdateValidationError("birthdate_required", "missing field")
    if not isinstance(value, str):
        raise BirthdateValidationError(
            "birthdate_invalid_format", f"not a string: {type(value).__name__}"
        )
    s = value.strip()
    if not s:
        raise BirthdateValidationError("birthdate_required", "empty string")
    if not _BIRTHDATE_RE.match(s):
        raise BirthdateValidationError(
            "birthdate_invalid_format", f"not yyyy-mm-dd: {s!r}"
        )
    try:
        bd = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise BirthdateValidationError(
            "birthdate_invalid_format", f"unparseable date {s!r}: {exc}"
        ) from exc
    today = date.today()
    if bd > today:
        raise BirthdateValidationError(
            "birthdate_unrealistic", f"future date {bd.isoformat()}"
        )
    if bd.year < MIN_BIRTH_YEAR:
        raise BirthdateValidationError(
            "birthdate_unrealistic", f"year {bd.year} < {MIN_BIRTH_YEAR}"
        )
    age = compute_age_years(bd, today)
    if age > MAX_AGE_YEARS:
        raise BirthdateValidationError(
            "birthdate_unrealistic", f"age {age} > {MAX_AGE_YEARS}"
        )
    return bd


def compute_age_years(birthdate: date, today: date | None = None) -> int:
    """Return completed-year age. ``today`` is injectable for tests.

    Mirrors ``computeAgeYears`` in ``frontend/src/lib/age-verification.ts``
    so the two layers cannot drift.
    """
    if today is None:
        today = date.today()
    age = today.year - birthdate.year
    before_birthday_this_year = (
        today.month < birthdate.month
        or (today.month == birthdate.month and today.day < birthdate.day)
    )
    if before_birthday_this_year:
        age -= 1
    return age


def is_at_least_min_age(
    birthdate: date,
    min_age: int = MIN_AGE_YEARS,
    today: date | None = None,
) -> bool:
    """True iff the subject is at least ``min_age`` completed years.

    Defaults to ``MIN_AGE_YEARS`` (PIPA §22 ⑥ = 14).
    """
    return compute_age_years(birthdate, today) >= min_age


def check_birthdate_payload(
    value: object, today: date | None = None
) -> AgeCheckResult:
    """Convenience wrapper: parse + age check in one call.

    Raises ``BirthdateValidationError`` for parse failures *and* for the
    under-14 gate (code ``below_min_age``). Returns ``AgeCheckResult``
    only when the user passes — callers never have to re-validate.
    """
    bd = parse_birthdate_strict(value)
    age = compute_age_years(bd, today)
    if age < MIN_AGE_YEARS:
        raise BirthdateValidationError(
            "below_min_age",
            f"age {age} < required {MIN_AGE_YEARS}",
        )
    return AgeCheckResult(birthdate=bd, years=age, ok=True)


__all__ = [
    "MIN_AGE_YEARS",
    "MAX_AGE_YEARS",
    "MIN_BIRTH_YEAR",
    "BirthdateValidationError",
    "AgeCheckResult",
    "parse_birthdate_strict",
    "compute_age_years",
    "is_at_least_min_age",
    "check_birthdate_payload",
]
