"""Signed token for the PUBLIC monthly-brag OG image endpoint.

The OG image (``/api/artifacts/monthly-brag/og-image/<id>``) must be
fetchable by social crawlers (Kakao / Twitter / Instagram) with no
session cookie so link unfurls render. The legacy route keyed solely on
the integer ``brag_id`` — anyone could enumerate ``1, 2, 3, …`` and pull
down every user's PNG, which embeds their real name and monthly return
(PIPA §29 personal-data exposure).

This module mints an HMAC-signed token that the owner-authenticated
share-link endpoint embeds in the ``og:image`` URL. The public og-image
endpoint refuses to serve a PNG without a token whose signature matches
the requested ``brag_id``. An attacker cannot forge the signature, so
enumeration is closed while crawlers (which receive the signed URL from
the share landing page) still work. No schema/migration needed — the
payload is just the ``brag_id``.

Piggybacks on ``itsdangerous.URLSafeTimedSerializer`` (already a
dependency via the OAuth state token and ``services/email_token.py``),
HMAC-signed with ``app.config["SECRET_KEY"]``.
"""
from __future__ import annotations

from typing import Optional

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

# Namespacing salt — keeps these tokens distinct from the OAuth state and
# email-unsubscribe serializers. Bump the suffix to invalidate every
# outstanding share link at once.
_SALT = "pivox-brag-og-v1"

# 1 year. A shared card link should keep unfurling long after the share;
# the cost of a long-lived token is low (single integer payload) and a
# leaked link only exposes a PNG the user already chose to make public.
_MAX_AGE = 365 * 24 * 3600


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt=_SALT,
    )


def make_og_token(brag_id: int) -> str:
    """Mint a signed token binding a share link to one ``brag_id``."""
    return _serializer().dumps({"b": int(brag_id)})


def verify_og_token(token: str, brag_id: int) -> bool:
    """Return True iff ``token`` is a valid signature for ``brag_id``."""
    if not token:
        return False
    try:
        payload = _serializer().loads(token, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    except Exception:  # pragma: no cover — defensive
        return False
    return isinstance(payload, dict) and payload.get("b") == int(brag_id)
