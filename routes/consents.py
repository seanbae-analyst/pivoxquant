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


# ── Cross-border data-transfer consent (PIPA §28-8) ─────────────────────
#
# 개인정보보호법 §28-8 (2024-09 시행) — 개인정보 국외 이전 시 정보주체에게
# 별도로 알리고 명시적 동의를 받아야 함. PivoxQuant 의 모든 위탁처
# (Anthropic / Stripe / Vercel / Railway / Google) 가 미국 소재이므로
# 전 사용자에게 적용된다. 본 엔드포인트는 동의 기록 계층만 다루고,
# 향후 국외이전 코드 경로를 막는 runtime 가드는 별도 PR 에서 추가한다.

def _cross_border_state(user) -> dict:
    """Compute the effective cross-border consent payload (PIPA §28-8)."""
    consent_at = getattr(user, "cross_border_consent_at", None)
    revoked_at = getattr(user, "cross_border_consent_revoked_at", None)
    is_opted_in = consent_at is not None and (
        revoked_at is None or revoked_at < consent_at
    )
    return {
        "cross_border_consent_at": consent_at.isoformat() if consent_at else None,
        "cross_border_consent_revoked_at": (
            revoked_at.isoformat() if revoked_at else None
        ),
        "opted_in": is_opted_in,
    }


@consents_bp.route("/cross-border", methods=["GET"])
@api_auth
def get_cross_border_consent():
    """Return the authenticated user's cross-border consent record."""
    return jsonify({"ok": True, **_cross_border_state(current_user)})


@consents_bp.route("/cross-border", methods=["POST"])
@api_auth
def record_cross_border_consent():
    """Persist explicit cross-border data transfer opt-in (PIPA §28-8)."""
    now = _utcnow_naive()
    current_user.cross_border_consent_at = now
    current_user.cross_border_consent_revoked_at = None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "consents.record_cross_border_consent commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not record consent"}), 500
    return jsonify({"ok": True, **_cross_border_state(current_user)})


@consents_bp.route("/cross-border", methods=["DELETE"])
@api_auth
def revoke_cross_border_consent():
    """Record a cross-border consent revocation. Future cross-border data
    flows for this user must short-circuit when the runtime kill-switch is
    added (separate PR)."""
    now = _utcnow_naive()
    current_user.cross_border_consent_revoked_at = now
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "consents.revoke_cross_border_consent commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not revoke consent"}), 500
    return jsonify({"ok": True, **_cross_border_state(current_user)})


# ── Split categories (Wave D Sub-wave 1, C-S1 §50) ─────────────────────
#
# 정통망법 §50 ① 시행령 및 KISA 가이드라인 — 정보성 / 광고성 메일 카테고리별
# 분리 동의. 위의 ``/marketing`` 엔드포인트는 통합 게이트로 유지하고, 본
# ``/categories`` 엔드포인트는 카테고리별 audit-trail 을 별도 컬럼에 기록한다.
#
# Feature flag (``PIVOX_CS1_CONSENT_ENABLED``) 는 *발송 측* 게이트이지 동의
# *수집* 측 게이트가 아니므로, 본 GET/POST 는 flag 값과 무관하게 항상 동작한다.
# 변호사 Q-S1 답변 전이라도 frontend 가 새 UI 를 prefetch 한 사용자의 동의
# 기록을 손실 없이 보존할 수 있다. flag=true 로 전환되는 순간부터 비로소
# ``services/email/sender.py`` 가 컬럼 값을 검사해 발송을 결정한다.


def _categories_state(user) -> dict:
    """Compute per-category (information / marketing) effective consent."""
    def _eff(consent_at, revoked_at) -> bool:
        return consent_at is not None and (
            revoked_at is None or revoked_at < consent_at
        )

    info_at = getattr(user, "marketing_consent_information_at", None)
    info_rev = getattr(user, "marketing_consent_information_revoked_at", None)
    mkt_at = getattr(user, "marketing_consent_marketing_at", None)
    mkt_rev = getattr(user, "marketing_consent_marketing_revoked_at", None)

    return {
        "information": {
            "consent_at": info_at.isoformat() if info_at else None,
            "revoked_at": info_rev.isoformat() if info_rev else None,
            "opted_in": _eff(info_at, info_rev),
        },
        "marketing": {
            "consent_at": mkt_at.isoformat() if mkt_at else None,
            "revoked_at": mkt_rev.isoformat() if mkt_rev else None,
            "opted_in": _eff(mkt_at, mkt_rev),
        },
    }


@consents_bp.route("/categories", methods=["GET"])
@api_auth
def get_consent_categories():
    """Return per-category (information / marketing) consent record.

    Safe to call regardless of ``PIVOX_CS1_CONSENT_ENABLED`` — the response
    shape is stable and frontend can render the toggles based on the
    ``opted_in`` flags without depending on the runtime enforcement gate.
    """
    return jsonify({"ok": True, "categories": _categories_state(current_user)})


@consents_bp.route("/categories", methods=["POST"])
@api_auth
def record_consent_categories():
    """Persist per-category opt-in / opt-out decisions in a single call.

    Request body
    ------------
    ``{"information": bool, "marketing": bool}``

    Either key may be omitted to leave that category untouched. Passing
    ``True`` records a fresh opt-in timestamp and clears the matching
    revoked_at (re-opt-in supersedes prior revocation). Passing ``False``
    stamps revoked_at (preserving consent_at for the audit trail).

    Returns the post-write category state so the client can update its
    UI without a follow-up GET.
    """
    from flask import request

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    info = payload.get("information")
    mkt = payload.get("marketing")

    # Validate types up-front — silently ignore missing keys, reject
    # wrong types (avoids "truthy string == opt-in" surprises).
    for key, val in (("information", info), ("marketing", mkt)):
        if val is not None and not isinstance(val, bool):
            return jsonify({
                "error": f"'{key}' must be a boolean (got {type(val).__name__})",
            }), 400

    now = _utcnow_naive()

    if info is True:
        current_user.marketing_consent_information_at = now
        current_user.marketing_consent_information_revoked_at = None
    elif info is False:
        current_user.marketing_consent_information_revoked_at = now

    if mkt is True:
        current_user.marketing_consent_marketing_at = now
        current_user.marketing_consent_marketing_revoked_at = None
    elif mkt is False:
        current_user.marketing_consent_marketing_revoked_at = now

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "consents.record_consent_categories commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not record consent"}), 500

    return jsonify({"ok": True, "categories": _categories_state(current_user)})


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
