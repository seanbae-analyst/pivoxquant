"""Application JSON provider — last-line defense against non-finite floats.

Python's stdlib ``json`` (which Flask's ``DefaultJSONProvider`` uses) emits the
bare tokens ``NaN``, ``Infinity`` and ``-Infinity`` for non-finite floats.
Those tokens are **invalid JSON**: a browser ``response.json()`` /
``JSON.parse`` raises ``SyntaxError`` on them, so a *single* non-finite value
anywhere in a payload makes the **entire** response unparseable on the
frontend — the user silently sees a blank/error card instead of the data
(and the request looks "successful" with HTTP 200 server-side).

Quant / numpy math readily produces non-finite floats: zero-variance
``corrcoef``, ``0/0`` ratios, ``log(0)``, empty-window stats, a missing last
close. Individual routes guard with ad-hoc ``_finite_floats`` helpers, but
that is opt-in — only a minority of the 40+ route modules do it, and any new
endpoint starts unprotected. This provider sanitises **every** response at the
serialisation boundary, so a missed guard can never ship a non-parseable body.

Non-finite floats are coerced to ``null`` (not ``0.0``): for a value that
leaked past every upstream guard, ``null`` is the honest "no data" sentinel
and avoids fabricating a financial zero (a false-display / 표시광고법 risk),
and the frontend already null-guards optional fields. Routes that want a
specific numeric fallback still coerce upstream before the payload reaches
here, so in practice this only ever touches genuinely-leaked values.
"""

from __future__ import annotations

import math
from typing import Any

from flask.json.provider import DefaultJSONProvider


def sanitize_non_finite(obj: Any) -> Any:
    """Recursively replace non-finite floats (NaN/Inf/-Inf) with ``None``.

    Non-destructive: returns the **same** object when no descendant changed,
    so clean payloads (the common case) incur only a read-only walk with no
    re-allocation, and cached payload objects are never mutated in place.

    ``bool`` is not a ``float`` subclass so booleans pass through untouched;
    ``numpy.float64`` *is* a ``float`` subclass so numpy non-finite values are
    covered as well.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        replacement: dict | None = None
        for key, value in obj.items():
            cleaned = sanitize_non_finite(value)
            if cleaned is not value:
                if replacement is None:
                    replacement = dict(obj)
                replacement[key] = cleaned
        return replacement if replacement is not None else obj
    if isinstance(obj, (list, tuple)):
        replacement = None
        for idx, value in enumerate(obj):
            cleaned = sanitize_non_finite(value)
            if cleaned is not value:
                if replacement is None:
                    replacement = list(obj)
                replacement[idx] = cleaned
        return replacement if replacement is not None else obj
    return obj


class SafeJSONProvider(DefaultJSONProvider):
    """Flask JSON provider that strips non-finite floats before dumping.

    Wired in :func:`app.create_app` via ``app.json = SafeJSONProvider(app)``.
    Inherits all other behaviour (datetime/Decimal/UUID/dataclass handling,
    ``sort_keys``, ``compact``) from :class:`DefaultJSONProvider`.
    """

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        return super().dumps(sanitize_non_finite(obj), **kwargs)
