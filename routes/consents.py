"""User consent records — authenticated proof-of-opt-in (정통망법 §50 ①).

Mounted at ``/api/consents/*``.

Why a separate blueprint
------------------------
Marketing consent is collected at signup and toggled in Settings, but the
existing surfaces store it only in ``localStorage``. §50 ① of the Korean
정통망법 (Information & Communications Network Act) places the *burden of
proof* of prior opt-in on the sender, not the recipient — and a
client-side store evaporates the moment a user clears site data, making
it useless as evidence in a §76 ①4호 dispute. This blueprint persists
the timestamp on the server so the audit trail survives device resets.

Distinct from the public unsubscribe endpoint
---------------------------------------------
``routes/email_preferences.py`` exposes the *unauthenticated*
HMAC-signed unsubscribe link surfaced inside emails (List-Unsubscribe,
RFC 8058). That flow flips ``email_opt_out`` (the runtime kill-switch).

This blueprint exposes the *authenticated* in-app consent record. The
two systems are deliberately separate:

  * ``email_opt_out`` controls future sends (the "do" side).
  * ``marketing_consent_at`` records the legal basis (the "may" side).

A user with ``marketing_consent_at = NULL`` must never receive marketing
mail regardless of ``email_opt_out``, because §50 requires affirmative
prior consent — the absence of an opt-out is not consent.

Endpoints
---------
``POST   /api/consents/marketing`` — record opt-in (timestamp = now UTC).
``DELETE /api/consents/marketing`` — record revocation. Also flips
                                    ``email_opt_out = True`` so the
                                    kill-switch matches the legal state.
``GET    /api/consents/marketing`` — read current state for the UI
                                    Settings toggle.

All three require an authenticated session; CSRF is enforced globally
by ``security._csrf_protect`` for POST/DELETE.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify
from flask_login import current_user

from extensions import db
from routes.decorators import api_auth

logger = logging.getLogger(__name__)

consents_bp = Blueprint("consents", __name__, url_prefix="/api/consents")


def _utcnow_naive() -> datetime:
    """Return a naive UTC datetime, matching ``User.created_at`` convention.

    SQLAlchemy stores naive UTC datetimes throughout the User model
    (see ``models/user.py`` — ``datetime.now(timezone.utc).replace(tzinfo=None)``);
    this helper keeps the consent timestamps on the same tz convention so
    comparisons against ``created_at`` and other DateTime columns are safe.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _consent_state(user) -> dict:
    """Compute the effective marketing consent payload for a user.

    Effective opt-in is true iff a non-null opt-in timestamp exists *and*
    no later revocation has occurred. Returning the raw timestamps too
    lets the frontend display the audit trail ("동의 시각: …") and the
    revocation date for users who once opted in.
    """
    consent_at = getattr(user, "marketing_consent_at", None)
    revoked_at = getattr(user, "marketing_consent_revoked_at", None)
    is_opted_in = consent_at is not None and (
        revoked_at is None or revoked_at < consent_at
    )
    return {
        "marketing_consent_at": consent_at.isoformat() if consent_at else None,
        "marketing_consent_revoked_at": (
            revoked_at.isoformat() if revoked_at else None
        ),
        "opted_in": is_opted_in,
    }


@consents_bp.route("/marketing", methods=["GET"])
@api_auth
def get_marketing_consent():
    """Return the authenticated user's marketing consent record."""
    return jsonify({"ok": True, **_consent_state(current_user)})


@consents_bp.route("/marketing", methods=["POST"])
@api_auth
def record_marketing_consent():
    """Persist an explicit marketing-email opt-in.

    Sets ``marketing_consent_at = now`` and clears any prior revocation
    so the new opt-in supersedes earlier history. Also flips
    ``email_opt_out`` back to False so the kill-switch matches the new
    legal state — otherwise the user could "opt in" but stay muted.

    Idempotent — calling twice within the same second simply re-stamps
    the timestamp (which is what the act actually requires us to retain
    as the most-recent consent record).
    """
    now = _utcnow_naive()
    current_user.marketing_consent_at = now
    current_user.marketing_consent_revoked_at = None
    # Re-enable the kill-switch in lock-step. A user who explicitly opts
    # in cannot simultaneously want the global mute on; if they later
    # change their mind they will issue DELETE /api/consents/marketing.
    if getattr(current_user, "email_opt_out", False):
        current_user.email_opt_out = False

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "consents.record_marketing_consent commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not record consent"}), 500

    return jsonify({"ok": True, **_consent_state(current_user)})


@consents_bp.route("/marketing", methods=["DELETE"])
@api_auth
def revoke_marketing_consent():
    """Record a marketing-consent revocation.

    Sets ``marketing_consent_revoked_at = now`` (preserving the prior
    ``marketing_consent_at`` for the audit trail) *and* flips
    ``email_opt_out = True`` so every email sender service stops
    immediately. Idempotent — re-revoking simply updates the timestamp.
    """
    now = _utcnow_naive()
    current_user.marketing_consent_revoked_at = now
    # Engage the runtime kill-switch so subsequent sends short-circuit.
    # 정통망법 §50 requires the company to honour withdrawals "without
    # delay"; flipping the boolean here closes the gap that would
    # otherwise exist between the user's click and the next nightly job.
    current_user.email_opt_out = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "consents.revoke_marketing_consent commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not revoke consent"}), 500

    return jsonify({"ok": True, **_consent_state(current_user)})
