"""One-click email-unsubscribe token (정통망법 §50 compliance).

Used by the artefact email senders in ``services/artifacts/*_service.py``
to embed a stable per-user unsubscribe link in every outgoing message
(`<a href="…/api/email/unsubscribe?token=…">`) AND in the
``List-Unsubscribe`` header that Gmail/Outlook surface as the inbox-level
"Unsubscribe" button.

Why itsdangerous
----------------
``URLSafeTimedSerializer`` already underpins the OAuth state token
(``routes/auth.py``) so this module piggybacks on the same dependency
without adding a new transitive. Tokens are HMAC-signed with
``app.config["SECRET_KEY"]`` — *not* encrypted — which is fine here
because the only payload is the user-id (already public to the user)
and the integrity guarantee is what matters: an attacker who tries to
unsubscribe a different user must forge a signature.

Token lifetime
--------------
1 year (``_MAX_AGE``). Long enough that an old PDF email's link still
works after a holiday hiatus; short enough that a leaked link doesn't
work indefinitely. The salt namespaces these tokens away from any
other ``URLSafeTimedSerializer`` use in the codebase.
"""
from __future__ import annotations

from typing import Optional

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

# Namespacing salt — keeps these tokens distinct from OAuth state
# (``_OAUTH_STATE_SALT`` in routes/auth.py). Bumping the suffix
# (``…-v2``) invalidates every outstanding unsubscribe link in one go,
# which we'd want if SECRET_KEY rotation alone wasn't enough.
_SALT = "pivox-email-unsub-v1"

# 1 year = 365 * 24 * 3600 seconds. Old emails should still let the
# user opt out — the cost of a longer-lived token is low (single
# integer payload) and the UX cost of a shorter one is real.
_MAX_AGE = 365 * 24 * 3600


def _serializer() -> URLSafeTimedSerializer:
    """Build a serializer scoped to the request app context.

    Must be called inside ``flask.current_app`` (i.e. inside a request
    or ``with app.app_context():``) — this is true for every email
    sender already because they run inside Flask CLI / scheduler tasks
    that push an app context.
    """
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt=_SALT,
    )


def make_unsubscribe_token(user_id: int) -> str:
    """Mint a fresh signed token for ``user_id``.

    Returns a URL-safe ASCII string suitable for embedding in a query
    parameter (``?token=…``) or an RFC 8058 ``List-Unsubscribe`` header.
    """
    return _serializer().dumps({"uid": int(user_id)})


def verify_unsubscribe_token(token: str) -> Optional[int]:
    """Return the embedded user-id if the token is valid, else ``None``.

    Catches every itsdangerous error path (bad signature, expired,
    malformed) plus the ``int()`` coercion failure mode so the caller
    can rely on a single ``None`` sentinel for "this token is no good"
    without try/except gymnastics.
    """
    try:
        data = _serializer().loads(token, max_age=_MAX_AGE)
    except BadSignature:
        return None
    except Exception:
        # Defensive — itsdangerous shouldn't raise anything else, but
        # we never want a malformed query-string param to 500 the
        # public unsubscribe endpoint.
        return None

    if not isinstance(data, dict):
        return None
    raw_uid = data.get("uid")
    try:
        return int(raw_uid)
    except (TypeError, ValueError):
        return None


# ── Helpers used by ``services/artifacts/*_service.py`` ──────────────────
# Phase 2 P0 ships these helpers as duplicated calls in each of the 17
# email senders (per task brief — Phase 7 will consolidate into a single
# EmailSender). Keeping the URL + footer assembly here ensures every
# sender produces an identical link shape, so the unsubscribe route can
# rely on a stable contract.

def build_unsubscribe_url(user_id: int, kind: str = "all") -> str:
    """Return the public unsubscribe URL for ``user_id``.

    ``kind`` is mirrored into the ``type`` query param consumed by
    ``GET /api/email/unsubscribe`` — only ``"all"`` and ``"earnings"`` are
    accepted there; anything else is coerced to ``"all"`` server-side.
    """
    import os

    token = make_unsubscribe_token(user_id)
    # Resolve the public-facing origin. Prefer the Flask config (set in
    # ``config.py`` / Railway env), fall back to the canonical brand
    # domain so dev environments still produce a working link shape.
    frontend = ""
    try:
        frontend = current_app.config.get("FRONTEND_URL") or ""
    except Exception:
        # Calling outside an app context — fall back to env directly.
        frontend = ""
    if not frontend:
        frontend = os.environ.get("FRONTEND_URL", "https://pivoxquant.com")
    frontend = frontend.rstrip("/")
    return f"{frontend}/api/email/unsubscribe?token={token}&type={kind}"


# Inline footer HTML stitched into already-rendered email bodies that did
# not receive ``unsubscribe_url`` at render time. Kept short + style-inline
# for Gmail / Outlook compat.
_UNSUB_FOOTER_HTML = (
    '<div style="margin:18px 0 0 0;text-align:center;font-family:'
    "'Geist','Pretendard',sans-serif;\">"
    '<a href="{url}" style="color:#8a8a8a;font-size:9pt;'
    'text-decoration:underline;">'
    "이 메일 더 받지 않기 / Unsubscribe</a></div>"
)


def inject_unsubscribe_footer(html: str, unsubscribe_url: str) -> str:
    """Stitch the unsubscribe footer into ``html`` if it lacks one.

    Idempotent — if the body already contains ``unsubscribe_url`` (because
    the template had ``{{ unsubscribe_url }}`` in scope at render time)
    we skip the injection.

    The footer is inserted immediately before the closing ``</body>``
    tag. If no ``</body>`` is present (rare — fallback HTML), we append
    to the end.
    """
    if not unsubscribe_url:
        return html
    if unsubscribe_url in html:
        return html  # already present from a Jinja-time render
    snippet = _UNSUB_FOOTER_HTML.format(url=unsubscribe_url)
    if "</body>" in html:
        return html.replace("</body>", snippet + "</body>", 1)
    return html + snippet
