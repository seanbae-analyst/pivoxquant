"""Retrospective behaviour-mirror routes.

Endpoints (all under ``/api/behavior``):

    GET /holding-mirror         — retrospective winner/loser holding-period
                                  mirror (?period=30d|all)
    GET /concentration-mirror   — cost-basis concentration of open positions
    GET /profit-loss-mirror     — profit/loss hold-day + return mirror
                                  (?period=30d|all)
    GET /turnover-mirror        — trade-activity mirror: fill counts +
                                  per-currency gross value (?period=30d|all)
    GET /averaging-down-mirror  — follow-on-add mirror: counts of adds to an
                                  already-held position below / above / at the
                                  running average cost (?period=30d|all)

The former AI behavioural-scoring endpoints (``/score``, ``/breakdown``,
``/persona-comparison``) were removed 2026-05-30 per the "AI 점수화 폐기"
decision (DECISIONS.md). See the deprecation note further down.

Legal posture
-------------
Strictly retrospective ("지난 거래"). All language is observational; we
surface only factual statistics — never a score, grade, or directive
("should" / "consider" / "recommend") framing.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from models import TradeHistory
from services.behavior.averaging_down_mirror import (
    compute_averaging_down_mirror,
)
from services.behavior.concentration_mirror import compute_concentration_mirror
from services.behavior.profit_loss_mirror import compute_profit_loss_mirror
from services.behavior.turnover_mirror import compute_turnover_mirror
from services.profile.holding_mirror import compute_holding_mirror

from .decorators import api_auth
from services.legal.disclaimers import DISCLAIMER_MIRROR_RETROSPECTIVE_KR

logger = logging.getLogger(__name__)

behavior_bp = Blueprint("behavior", __name__, url_prefix="/api/behavior")


# ── AI 점수화 폐기 (DECISIONS, 2026-05-30) ──────────────────────────
# 무료 출시 Stage 0 BLOCKER #1: "평가 안 함" 포지션 달성을 위해 점수
# 소비 엔드포인트(GET /score, /breakdown, /persona-comparison)를 제거했다.
# 점수는 이제 (a) 크론 비활성으로 계산되지 않고 (b) API 로 접근 불가하며
# (c) 프론트 소비자가 0건이다. BehavioralScore 모델/스코어러는 거울·export·
# persona benchmark 호환을 위해 dormant 보존한다(물리 컬럼 drop 은 prod
# self-heal 함정 때문에 careful 마이그레이션으로 후속). 아래 거울
# 엔드포인트(holding/concentration/profit-loss)는 사실 관찰 surface 로 유지.


# ── /holding-mirror ─────────────────────────────────────────────────

_HOLDING_MIRROR_DISCLAIMER = DISCLAIMER_MIRROR_RETROSPECTIVE_KR

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
_PROFIT_LOSS_MIRROR_DISCLAIMER = DISCLAIMER_MIRROR_RETROSPECTIVE_KR

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


# ── /turnover-mirror ─────────────────────────────────────────────────

# Wording kept byte-identical to the other retrospective trade-history
# mirror disclaimers so all behaviour mirrors read with one legal voice.
_TURNOVER_MIRROR_DISCLAIMER = DISCLAIMER_MIRROR_RETROSPECTIVE_KR

# Accepted ``?period`` values → window in days. ``all`` (default) = no
# window. Kept tiny and explicit so we never echo an arbitrary
# user-supplied integer back into a window.
_TURNOVER_MIRROR_PERIODS: dict[str, int | None] = {
    "all": None,
    "30d": 30,
}


@behavior_bp.route("/turnover-mirror", methods=["GET"])
@api_auth
def turnover_mirror():
    """Retrospective trade-activity mirror for the user.

    ``?period=30d|all`` (default ``all``). Returns observational fill
    counts (BUY/SELL) and per-currency gross traded value — never a
    turnover ratio, score, grade, or label — over the user's own trade
    history. No live price / FX call.
    """
    period = request.args.get("period", "all")
    if period not in _TURNOVER_MIRROR_PERIODS:
        return jsonify({
            "error": (
                "period must be one of: "
                + ", ".join(sorted(_TURNOVER_MIRROR_PERIODS))
            ),
            "code": "BAD_INPUT",
        }), 400
    period_days = _TURNOVER_MIRROR_PERIODS[period]

    trades = (
        TradeHistory.query
        .filter_by(user_id=current_user.id)
        .all()
    )
    result = compute_turnover_mirror(trades, period_days=period_days)

    body = {
        "ok": True,
        "disclaimer": _TURNOVER_MIRROR_DISCLAIMER,
        "period": period,
    }
    body.update(result)
    return jsonify(body), 200


# ── /averaging-down-mirror ──────────────────────────────────────────

# Wording kept byte-identical to the other retrospective trade-history
# mirror disclaimers so all behaviour mirrors read with one legal voice.
_AVERAGING_DOWN_MIRROR_DISCLAIMER = DISCLAIMER_MIRROR_RETROSPECTIVE_KR

# Accepted ``?period`` values → window in days. ``all`` (default) = no
# window. Kept tiny and explicit so we never echo an arbitrary
# user-supplied integer back into a window.
_AVERAGING_DOWN_MIRROR_PERIODS: dict[str, int | None] = {
    "all": None,
    "30d": 30,
}


@behavior_bp.route("/averaging-down-mirror", methods=["GET"])
@api_auth
def averaging_down_mirror():
    """Retrospective follow-on-add mirror for the user.

    ``?period=30d|all`` (default ``all``). For each BUY that added to an
    already-held position, returns observational counts of whether the add
    landed below / above / at the position's running average cost at that
    instant — never a score, grade, ratio, or "물타기" judgement. Same-ticker
    price comparison only, so no live price / FX call.
    """
    period = request.args.get("period", "all")
    if period not in _AVERAGING_DOWN_MIRROR_PERIODS:
        return jsonify({
            "error": (
                "period must be one of: "
                + ", ".join(sorted(_AVERAGING_DOWN_MIRROR_PERIODS))
            ),
            "code": "BAD_INPUT",
        }), 400
    period_days = _AVERAGING_DOWN_MIRROR_PERIODS[period]

    trades = (
        TradeHistory.query
        .filter_by(user_id=current_user.id)
        .all()
    )
    result = compute_averaging_down_mirror(trades, period_days=period_days)

    body = {
        "ok": True,
        "disclaimer": _AVERAGING_DOWN_MIRROR_DISCLAIMER,
        "period": period,
    }
    body.update(result)
    return jsonify(body), 200
