"""
Sim user onboarding — autonomous CAUS launcher.

This blueprint mounts ONLY when ``SIM_ONBOARD_SECRET`` env is set. It exists
specifically so the Continuous Autonomous User Simulation cron
(``scripts/caus_daily_sweep.py``) can create + login a Gmail-alias sim user
without operator action — CEO does not have time to OAuth-onboard 10 sim
aliases by hand.

Security model
==============
  * **HMAC ticket** signed with ``SIM_ONBOARD_SECRET``, 5-minute TTL. Replay
    window bounded by TTL; server does not need to track used tickets because
    the email regex (below) restricts the blast radius to sim-only aliases
    that have ``is_simulated=TRUE`` enforced server-side.
  * **Email regex allow-list**: only ``seanbae1521+sim{1-99}@gmail.com`` or
    ``sim{1-99}@pivoxquant-test.local``. A leaked secret cannot escalate to a
    real user account.
  * **``is_simulated=True`` enforced**: new users are flagged simulated.
    Existing sim users are re-logged-in. Existing real users (``is_simulated
    is False``) are **refused** — the endpoint cannot flip a real user's flag
    or hijack a real user's session.
  * **Rate limit**: 3 requests/minute per IP (operator-error / abuse defense);
    1 request/hour per email (replay-window narrowing on top of the 5-minute
    HMAC TTL).
  * **User-Agent gate**: caller must send ``User-Agent: PivoxQuantCAUS/...``.
    Cheap defense against accidental browser POSTs and curl-from-shell typos.
  * **Independent from DEV_LOGIN_SECRET**: the M3 production guard
    (``routes/__init__.py``) refuses to mount ``dev_auth`` when
    ``FLASK_ENV=production`` AND ``DEV_LOGIN_SECRET`` are both set, because
    ``dev_auth`` creates a generic dev user with arbitrary tier. This module
    is **safe to enable in production** because the email regex restricts
    creatable accounts to sim-only aliases and ``is_simulated=True`` is
    forced server-side.

This is NOT a generic auth path: cannot login an existing real user, cannot
upgrade tier, cannot create non-sim users.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import os
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import login_user

from extensions import db
from models.user import User
from security import limiter

logger = logging.getLogger(__name__)

sim_onboard_bp = Blueprint("sim_onboard", __name__)

# Sim aliases:
#   * ``seanbae1521+sim1@gmail.com`` ... ``seanbae1521+sim99@gmail.com``
#     (Gmail plus-addressing — same inbox, distinct sub-addresses)
#   * ``sim1@pivoxquant-test.local`` ... ``sim99@pivoxquant-test.local``
#     (RFC 6761 .local — never resolvable, useful for offline fixtures)
# `sim[1-9]\d?` matches 1..99 without leading-zero / sim0 / negative numbers.
SIM_EMAIL_REGEX = re.compile(
    r"^seanbae1521\+sim[1-9]\d?@gmail\.com$|^sim[1-9]\d?@pivoxquant-test\.local$"
)
TICKET_TTL_SECONDS = 300  # 5 minutes — narrow enough to bound replays.
REQUIRED_UA_PREFIX = "PivoxQuantCAUS/"


def _verify_ticket(ticket_b64: str, secret: str) -> tuple[str, str] | None:
    """Verify HMAC ticket.

    Ticket format (urlsafe base64 of ASCII)::

        "{ISO-8601 UTC timestamp}:{email}:{hex hmac_sha256(ts:email, secret)}"

    Returns ``(timestamp_iso, email)`` if the ticket parses, HMAC verifies,
    and ``|now - ts| <= TICKET_TTL_SECONDS``. Returns ``None`` otherwise.

    The function avoids leaking which check failed (parse / signature / TTL)
    via separate error paths so attackers cannot use response-time / message
    differentials to learn ticket structure.
    """
    if not ticket_b64 or not secret:
        return None

    try:
        raw = base64.urlsafe_b64decode(ticket_b64.encode("ascii"))
        decoded = raw.decode("ascii")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None

    # split(":", 2) -> [ts, email, sig]. Email won't contain ':' (RFC 5321),
    # but rsplit(":", 2) is safer if a ts ever contains it (ISO 8601 does:
    # "2026-05-13T12:30:00+00:00"). Use rsplit so sig is unambiguously the
    # last component.
    parts = decoded.rsplit(":", 2)
    if len(parts) != 3:
        return None
    ts_str, email, sig_hex = parts

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        f"{ts_str}:{email}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig_hex, expected_sig):
        return None

    # Parse the ISO timestamp. "Z" suffix → "+00:00" for fromisoformat compat.
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Force tz-aware UTC for comparison. Naive timestamps are rejected.
    if ts.tzinfo is None:
        return None

    now = datetime.now(timezone.utc)
    if abs((now - ts).total_seconds()) > TICKET_TTL_SECONDS:
        return None

    return ts_str, email


def _email_rate_key() -> str:
    """flask-limiter key_func for per-email throttling.

    Pulls ``email`` from the parsed JSON body when present, falling back to
    the remote address so a malformed request still gets rate-limited
    (rather than bypassing entirely by omitting the field).
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    if email:
        return f"sim-onboard-email:{email}"
    # Anonymous fallback so missing-email cannot bypass the email bucket.
    return f"sim-onboard-ip:{request.remote_addr or 'unknown'}"


def _enabled() -> bool:
    """Endpoint is mounted only when SIM_ONBOARD_SECRET is set at boot.

    Re-checked at request time so a runtime env-var unset still 404s instead
    of crashing on a None secret in HMAC.
    """
    return bool(os.environ.get("SIM_ONBOARD_SECRET"))


@sim_onboard_bp.route("/api/auth/sim-onboard", methods=["POST"])  # legal-exempt: internal CAUS-only endpoint, no user-facing financial content
@limiter.limit("3 per minute")  # IP-level brute-force defense.
@limiter.limit("1 per hour", key_func=_email_rate_key)  # Per-email throttle.
def sim_onboard():
    """Create-or-login a simulated user via HMAC ticket. CSRF-exempt.

    Request body::

        {"ticket": "<urlsafe_b64(ts:email:sig)>", "email": "<sim alias>"}

    The ``email`` field on the body duplicates the email inside the ticket;
    it exists only so the per-email rate limit key can be computed *before*
    HMAC verification (the limiter runs before the view body). Both must
    match the regex; mismatch returns 400 to avoid an oracle.

    Responses:
      * 200 — sim user logged in. Body: ``{ok, user_id, email, is_simulated}``.
      * 400 — missing/malformed ticket or email field.
      * 401 — ticket signature invalid or expired.
      * 403 — User-Agent missing PivoxQuantCAUS/ prefix, or email not in
              sim allow-list.
      * 404 — endpoint disabled (SIM_ONBOARD_SECRET unset at runtime).
      * 409 — email is reserved by a non-simulated (real) user.
      * 429 — IP rate-limit (3/min) or email rate-limit (1/h) exceeded.
    """
    secret = os.environ.get("SIM_ONBOARD_SECRET")
    if not secret:
        # Belt-and-braces: blueprint only mounts when secret is set at boot,
        # but if it's unset at runtime we still 404 instead of leaking signal.
        return jsonify({"error": "endpoint disabled"}), 404

    ua = request.headers.get("User-Agent", "")
    if not ua.startswith(REQUIRED_UA_PREFIX):
        logger.warning("sim-onboard: rejected UA=%r", ua[:64])
        return jsonify({"error": "invalid client"}), 403

    body = request.get_json(silent=True) or {}
    ticket = body.get("ticket")
    if not ticket or not isinstance(ticket, str):
        return jsonify({"error": "missing ticket"}), 400

    body_email = (body.get("email") or "").strip().lower()
    if not body_email:
        return jsonify({"error": "missing email"}), 400

    verified = _verify_ticket(ticket, secret)
    if not verified:
        logger.warning("sim-onboard: ticket verify failed for email=%s", body_email)
        return jsonify({"error": "invalid ticket"}), 401

    _, ticket_email = verified
    # Defense in depth — body email must match ticket email (case-insensitive,
    # since email local-parts are case-insensitive in practice).
    if ticket_email.lower() != body_email:
        logger.warning(
            "sim-onboard: email mismatch ticket=%s body=%s",
            ticket_email, body_email,
        )
        return jsonify({"error": "email mismatch"}), 400

    email = ticket_email.lower()
    if not SIM_EMAIL_REGEX.match(email):
        logger.warning("sim-onboard: email not in sim allow-list: %s", email)
        return jsonify({"error": "email not allowed for sim"}), 403

    # Find-or-create. CRITICAL: never flip an existing real user's flag.
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user is None:
        user = User(
            email=email,
            name=f"CAUS {email.split('@', 1)[0]}",
            oauth_provider="sim",
            onboarding_completed=True,
            is_simulated=True,
            subscription_tier="free",
        )
        db.session.add(user)
        db.session.commit()
        logger.info("sim-onboard: created sim user id=%s email=%s", user.id, email)
    elif not user.is_simulated:
        # Real user with this email already exists — refuse. This should be
        # impossible in practice (sim regex excludes real Gmail bare addresses
        # and the .local TLD never resolves), but defense-in-depth.
        logger.error(
            "sim-onboard: REFUSED — email %s reserved by real user id=%s",
            email, user.id,
        )
        return jsonify({"error": "email reserved for real user"}), 409
    else:
        # Existing sim user — re-login. Update is_simulated server-side as a
        # belt-and-braces guard against historical rows missing the flag.
        if not user.is_simulated:
            user.is_simulated = True
            db.session.commit()
        logger.info("sim-onboard: re-login sim user id=%s email=%s", user.id, email)

    login_user(user, remember=True)
    return jsonify({
        "ok": True,
        "user_id": user.id,
        "email": user.email,
        "is_simulated": True,
    }), 200
