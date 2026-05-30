"""Weekly Behavioural Score routes — Feature 7.

Endpoints (all under ``/api/behavior``):

    GET /score                — most recent week's score
    GET /score?weeks=N        — last N weeks (capped 1..52)
    GET /breakdown            — sub-score detail for the most recent week
    GET /persona-comparison   — same week vs. anonymised persona-group avg
    GET /holding-mirror       — retrospective winner/loser holding-period
                                mirror (?period=30d|all)

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

from models import BehavioralScore, TradeHistory
from services.behavior.concentration_mirror import compute_concentration_mirror
from services.behavior.profit_loss_mirror import compute_profit_loss_mirror
from services.profile.holding_mirror import compute_holding_mirror

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


# ── /holding-mirror ─────────────────────────────────────────────────

_HOLDING_MIRROR_DISCLAIMER = (
    "본 정보는 지난 거래의 회고적 사실 관찰이며 미래 예측이나 거래 권유가 "
    "아닙니다."
)

# Accepted ``?period`` values → window in days. ``all`` (default) = no
# window. Keep the set tiny and explicit so we never echo an arbitrary
# user-supplied integer back into a window.
_HOLDING_MIRROR_PERIODS: dict[str, int | None] = {
    "all": None,
    "30d": 30,
}


@behavior_bp.route("/holding-mirror", methods=["GET"])
@api_auth
def holding_mirror():
    """Retrospective winner/loser holding-period mirror for the user.

    ``?period=30d|all`` (default ``all``). Returns observational
    holding-day statistics — never a score/grade/ratio — over the
    user's own closed FIFO round trips.
    """
    period = request.args.get("period", "all")
    if period not in _HOLDING_MIRROR_PERIODS:
        return jsonify({
            "error": (
                "period must be one of: "
                + ", ".join(sorted(_HOLDING_MIRROR_PERIODS))
            ),
            "code": "BAD_INPUT",
        }), 400
    period_days = _HOLDING_MIRROR_PERIODS[period]

    trades = (
        TradeHistory.query
        .filter_by(user_id=current_user.id)
        .all()
    )
    result = compute_holding_mirror(trades, period_days=period_days)

    body = {"ok": True, "disclaimer": _HOLDING_MIRROR_DISCLAIMER, "period": period}
    body.update(result)
    return jsonify(body), 200


# ── /concentration-mirror ───────────────────────────────────────────

_CONCENTRATION_MIRROR_DISCLAIMER = (
    "본 정보는 현재 보유 종목의 사실 관찰이며 미래 예측이나 거래 권유가 "
    "아닙니다."
)


@behavior_bp.route("/concentration-mirror", methods=["GET"])
@api_auth
def concentration_mirror():
    """Cost-basis concentration mirror for the user's open positions.

    Returns the single largest holding's share of the portfolio at cost
    basis (평균매입가 기준), the position count, and the largest holding's
    display name — never a score/grade/ratio. No external price call.
    """
    result = compute_concentration_mirror(current_user.id)
    body = {"ok": True, "disclaimer": _CONCENTRATION_MIRROR_DISCLAIMER}
    body.update(result)
    return jsonify(body), 200


# ── /profit-loss-mirror ─────────────────────────────────────────────

# Wording kept byte-identical to the holding-mirror disclaimer so the two
# retrospective trade-history mirrors read with one legal voice.
_PROFIT_LOSS_MIRROR_DISCLAIMER = (
    "본 정보는 지난 거래의 회고적 사실 관찰이며 미래 예측이나 거래 권유가 "
    "아닙니다."
)

# Accepted ``?period`` values → window in days. ``all`` (default) = no
# window. Kept tiny and explicit so we never echo an arbitrary
# user-supplied integer back into a window.
_PROFIT_LOSS_MIRROR_PERIODS: dict[str, int | None] = {
    "all": None,
    "30d": 30,
}


@behavior_bp.route("/profit-loss-mirror", methods=["GET"])
@api_auth
def profit_loss_mirror():
    """Retrospective profit/loss holding + return mirror for the user.

    ``?period=30d|all`` (default ``all``). Returns observational hold-day
    and return-percent statistics — never a score/grade/label — split by
    whether the user's own closed FIFO round trips realised a profit or a
    loss.
    """
    period = request.args.get("period", "all")
    if period not in _PROFIT_LOSS_MIRROR_PERIODS:
        return jsonify({
            "error": (
                "period must be one of: "
                + ", ".join(sorted(_PROFIT_LOSS_MIRROR_PERIODS))
            ),
            "code": "BAD_INPUT",
        }), 400
    period_days = _PROFIT_LOSS_MIRROR_PERIODS[period]

    trades = (
        TradeHistory.query
        .filter_by(user_id=current_user.id)
        .all()
    )
    result = compute_profit_loss_mirror(trades, period_days=period_days)

    body = {
        "ok": True,
        "disclaimer": _PROFIT_LOSS_MIRROR_DISCLAIMER,
        "period": period,
    }
    body.update(result)
    return jsonify(body), 200
