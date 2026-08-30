"""UTC-aware observation timestamps for client-facing payloads.

Single source of truth for the ``timestamp`` / ``observed_at`` fields that
market-data payloads hand to the frontend.

Why this module exists
----------------------
Price providers used to stamp payloads with a bare ``datetime.now().isoformat()``.
That string is *naive* (no timezone marker) **and** local wall-clock. On Railway
the server clock is UTC, so a price observed at 07:00Z was serialized as
``"2026-08-30T07:00:00"``. Per ECMA-262 the browser parses a naive ISO string as
**local** time — for a KST user that reads as 07:00 KST (= 22:00Z the previous
day), putting the observation 9 hours in the past.

The visible symptom was backwards: the *freshest* prices (live provider path)
rendered "9h ago" behind an amber stale dot, while genuinely stale cached prices
rendered correctly, because the cache paths already appended ``Z``.

Rule: every timestamp that leaves the backend for a client carries an explicit
UTC marker. Naive datetimes are treated as UTC, matching the DB convention in
``services/profile/common_util.utc_now`` (columns are stored naive-UTC).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

__all__ = ["observed_at_iso", "normalize_observed_at"]

_OFFSET_RE = re.compile(r"[+-]\d{2}:?\d{2}$")


def observed_at_iso(dt: datetime | None = None) -> str:
    """Return ``dt`` as an ISO-8601 UTC string with an explicit ``Z`` suffix.

    ``None`` (the default) stamps the current time. Naive datetimes are
    interpreted as UTC; aware datetimes are converted to UTC. The ``Z`` form is
    used rather than ``+00:00`` to match the timestamps already emitted by
    ``services/price_overlay`` and ``services/serializers``.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def normalize_observed_at(value: str | datetime | None) -> str | None:
    """Coerce a provider-supplied observation stamp into UTC-marked ISO.

    Boundary guard for payloads that pass a provider's ``timestamp`` straight
    through to the client (``services/price_overlay``). Accepts a datetime, an
    ISO string, or ``None``:

      - ``None``                        -> ``None`` (caller decides the fallback)
      - naive ISO / naive datetime      -> treated as UTC, gains ``Z``
      - already-marked ISO (``Z``/offset) -> returned unchanged
      - unparseable string              -> returned unchanged (never raises)

    Returning the input untouched on a parse failure keeps a malformed upstream
    value visible rather than silently replacing it with "now", which would
    fabricate freshness.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return observed_at_iso(value)
    if not isinstance(value, str) or not value:
        return value
    if value.endswith("Z") or _OFFSET_RE.search(value):
        return value
    try:
        return observed_at_iso(datetime.fromisoformat(value))
    except ValueError:
        return value
