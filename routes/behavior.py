"""Weekly Behavioural Score routes — Feature 7.

Endpoints (all under ``/api/behavior``):

    GET /score                — most recent week's score
    GET /score?weeks=N        — last N weeks (capped 1..52)
    GET /breakdown            — sub-score detail for the most recent week
    GET /persona-comparison   — same week vs. anonymised persona-group avg

Legal posture
-------------
Strictly retrospective ("지난주"). All language is observational; we
never emit "should" / "consider" / "recommend" framing. Persona
comparison surfaces only when the underlying group aggregate clears
``MIN_GROUP_SIZE = 20`` — otherwise the comparison block is null.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from models import BehavioralScore

from .decorators import api_auth

logger = logging.getLogger(__name__)

behavior_bp = Blueprint("behavior", __name__, url_prefix="/api/behavior")


_DISCLAIMER = (
    "본 점수는 지난 주의 회고적 관찰 지표이며 미래 예측이나 거래 권유가 "
    "아닙니다."
)


def _envelope(payload: dict, *, status: int = 200):
    body = {"ok": True, "disclaimer": _DISCLAIMER}
    body.update(payload)
    return jsonify(body), status


# ── /score ──────────────────────────────────────────────────────────

@behavior_bp.route("/score", methods=["GET"])
@api_auth
def score():
    """Most recent score, or a series when ``?weeks=N`` is supplied."""
    weeks_raw = request.args.get("weeks")
    if weeks_raw is None:
        latest = (
            BehavioralScore.query
            .filter_by(user_id=current_user.id)
            .order_by(BehavioralScore.week_ending.desc())
            .first()
        )
        if latest is None:
            return _envelope({"score": None})
        return _envelope({"score": latest.to_dict()})

    try:
        weeks = int(weeks_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "weeks must be an integer", "code": "BAD_INPUT"}), 400
    weeks = max(1, min(52, weeks))

    rows = (
        BehavioralScore.query
        .filter_by(user_id=current_user.id)
        .order_by(BehavioralScore.week_ending.desc())
        .limit(weeks)
        .all()
    )
    # Oldest first so the chart draws left-to-right.
    series = [r.to_dict() for r in reversed(rows)]
    return _envelope({"series": series, "weeks": weeks})


# ── /breakdown ──────────────────────────────────────────────────────

@behavior_bp.route("/breakdown", methods=["GET"])
@api_auth
def breakdown():
    latest = (
        BehavioralScore.query
        .filter_by(user_id=current_user.id)
        .order_by(BehavioralScore.week_ending.desc())
        .first()
    )
    if latest is None:
        return _envelope({"breakdown": None})
    payload = latest.to_dict()
    return _envelope({
        "week_ending": payload.get("week_ending"),
        "overall_score": payload.get("overall_score"),
        "sub_scores": payload.get("sub_scores", {}),
        "trade_count": payload.get("trade_count", 0),
    })


# ── /persona-comparison ────────────────────────────────────────────

@behavior_bp.route("/persona-comparison", methods=["GET"])
@api_auth
def persona_comparison():
    latest = (
        BehavioralScore.query
        .filter_by(user_id=current_user.id)
        .order_by(BehavioralScore.week_ending.desc())
        .first()
    )
    if latest is None:
        return _envelope({"comparison": None})
    payload = latest.to_dict()
    return _envelope({
        "week_ending": payload.get("week_ending"),
        "user": payload.get("sub_scores", {}),
        "persona_avg": payload.get("persona_avg"),
    })
