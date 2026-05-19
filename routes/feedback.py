"""User feedback collection — NPS 1-click (Wave G C-AC2).

Mounted at ``/api/feedback/*``.

§50 classification: TRANSACTIONAL (서비스 개선, not marketing). No
prior-opt-in required — collecting feedback to improve the product is
a normal service-provider action under 정통망법, distinct from the
광고성 emails that ``services/email/sender.py`` gates via
``marketing_consent_*`` columns.

Endpoints
---------
``POST /api/feedback/nps`` — record a 1-10 score, optionally tied to a
                              Weekly Memo artifact.

Both authenticated. CSRF is enforced globally by ``security._csrf_protect``
for POSTs; the email-link entry path (frontend ``/feedback/nps?...``)
must therefore submit through the authenticated browser session — the
URL itself carries no auth, only a score pre-fill.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from routes.decorators import api_auth

logger = logging.getLogger(__name__)

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


_SCORE_MIN = 1
_SCORE_MAX = 10
_MEMO_ID_MAX_LEN = 64


@feedback_bp.route("/nps", methods=["POST"])
@api_auth
def submit_nps():
    """Record a 1-click NPS score.

    Request body
    ------------
    ``{"score": int (1-10), "weekly_memo_id": str | null}``

    ``score``
        Required. Integer in [1, 10] inclusive. Floats, strings, and
        out-of-range values are rejected with 400 — a buggy client must
        never poison the aggregates.

    ``weekly_memo_id``
        Optional opaque slug (max 64 chars) identifying the Weekly Memo
        that triggered the prompt. Deliberately NOT FK-checked against
        ``artifacts`` so history survives artifact deletion (mirrors
        ``ArtifactFeedback``).

    Duplicates allowed
    ------------------
    Repeat submissions on the same ``(user_id, weekly_memo_id)`` are
    intentionally not rejected here — the frontend localStorage gate
    handles "don't show twice", and the read path picks the latest
    ``created_at``. This lets a user change their mind without a DELETE
    flow.
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    raw_score = payload.get("score")
    # `bool` is a subclass of `int` in Python; reject it explicitly so a
    # buggy client cannot submit ``true`` as a score and have it coerce
    # to 1 silently.
    if isinstance(raw_score, bool) or not isinstance(raw_score, int):
        return jsonify({
            "error": (
                f"'score' must be an integer in [{_SCORE_MIN}, {_SCORE_MAX}]"
            ),
        }), 400
    if raw_score < _SCORE_MIN or raw_score > _SCORE_MAX:
        return jsonify({
            "error": (
                f"'score' must be in [{_SCORE_MIN}, {_SCORE_MAX}] "
                f"(got {raw_score})"
            ),
        }), 400

    raw_memo = payload.get("weekly_memo_id")
    weekly_memo_id: str | None
    if raw_memo is None:
        weekly_memo_id = None
    elif isinstance(raw_memo, str):
        memo = raw_memo.strip()
        if len(memo) == 0:
            weekly_memo_id = None
        elif len(memo) > _MEMO_ID_MAX_LEN:
            return jsonify({
                "error": (
                    f"'weekly_memo_id' must be ≤ {_MEMO_ID_MAX_LEN} chars"
                ),
            }), 400
        else:
            weekly_memo_id = memo
    else:
        return jsonify({
            "error": "'weekly_memo_id' must be a string or null",
        }), 400

    # Import lazily so a missing migration doesn't blow up app import; the
    # endpoint itself surfaces a clean 500 in that case instead.
    from models.nps_feedback import NpsFeedback

    row = NpsFeedback(
        user_id=current_user.id,
        score=raw_score,
        weekly_memo_id=weekly_memo_id,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception(
            "feedback.submit_nps commit failed (user_id=%s)",
            getattr(current_user, "id", None),
        )
        return jsonify({"error": "Could not record feedback"}), 500

    return jsonify({"ok": True, "feedback": row.to_dict()}), 200
