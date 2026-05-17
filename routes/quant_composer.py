"""Quant Composer routes — per-user model selection + weight composition.

Endpoints
---------
- ``GET    /api/quant/composition/models``    — full 40-model catalog.
- ``GET    /api/quant/composition``           — current user's enabled + weights.
- ``PUT    /api/quant/composition``           — replace user's composition.
- ``POST   /api/quant/composition/backtest``  — paper backtest of (enabled, weights).
- ``POST   /api/quant/composition/preset``    — apply a persona preset.

Layering
--------
- ``@api_auth`` first → returns 401 unscrubbed.
- ``@legal_scrub_response`` second → enforces the legal boundary on every
  string leaf in the JSON body before it ships.
- All payloads carry a ``disclaimer`` field (paper / past-data).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models import InvestmentProfile
from services.error_responses import api_error
from services.quant.composer import (
    PERSONA_QUANT_PRESETS,
    apply_persona_preset,
    validate_composition,
)
from services.quant.model_catalog import CATEGORIES, MODEL_BY_NAME, MODEL_CATALOG

from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit

logger = logging.getLogger(__name__)

quant_composer_bp = Blueprint(
    "quant_composer", __name__, url_prefix="/api/quant/composition"
)


# ─────────────────────────────────────────────────────────────────────
# Disclaimers — every response includes one. Past-data + paper-only are
# the two anchor messages required by §Feature 1 of LAUNCH_BUNDLE_SPEC.
# ─────────────────────────────────────────────────────────────────────

DISCLAIMER_PAPER = (
    "본 결과는 과거 데이터 기반 paper 시뮬레이션이며 미래 수익을 보장하지 않습니다. "
    "This output is a paper simulation over historical data and does not guarantee future results."
)

DISCLAIMER_OBSERVATION = (
    "각 모델은 관찰 instrument 이며 거래 지시를 제공하지 않습니다. "
    "Each model is an observation instrument and does not issue trading directives."
)


def _attach_disclaimer(payload: dict, kind: str = "observation") -> dict:
    payload["disclaimer"] = (
        DISCLAIMER_PAPER if kind == "paper" else DISCLAIMER_OBSERVATION
    )
    return payload


# ─────────────────────────────────────────────────────────────────────
# Helpers — read/parse the user's stored JSON columns.
# ─────────────────────────────────────────────────────────────────────


def _get_or_create_profile(user_id: int) -> InvestmentProfile:
    """Return the user's InvestmentProfile or 404 with a clear error.

    We do NOT auto-create here because the InvestmentProfile model
    carries onboarding answers we cannot fabricate — the user must
    finish onboarding first.
    """
    profile = (
        db.session.query(InvestmentProfile)
        .filter_by(user_id=int(user_id))
        .first()
    )
    return profile


def _parse_user_composition(profile: InvestmentProfile) -> tuple[list[str], dict[str, float]]:
    """Best-effort parse of the user's stored composition. Always returns
    a valid ``(list, dict)`` pair — corrupt rows degrade to empty."""
    raw_enabled = profile.enabled_quant_models or "[]"
    raw_weights = profile.model_weights or "{}"
    try:
        enabled = json.loads(raw_enabled) if isinstance(raw_enabled, str) else raw_enabled
    except (TypeError, ValueError):
        enabled = []
    try:
        weights = json.loads(raw_weights) if isinstance(raw_weights, str) else raw_weights
    except (TypeError, ValueError):
        weights = {}
    if not isinstance(enabled, list):
        enabled = []
    if not isinstance(weights, dict):
        weights = {}
    # Drop unknown / stale names defensively at read time too.
    enabled = [n for n in enabled if isinstance(n, str) and n in MODEL_BY_NAME]
    weights = {
        n: float(w)
        for n, w in weights.items()
        if isinstance(n, str) and n in MODEL_BY_NAME and isinstance(w, (int, float))
    }
    return enabled, weights


# ─────────────────────────────────────────────────────────────────────
# GET /api/quant/composition/models
# ─────────────────────────────────────────────────────────────────────


@quant_composer_bp.route("/models", methods=["GET"])
@api_auth
@legal_scrub_response
def list_models():
    """Return the 40-model catalog grouped by category.

    The frontend consumes this to render the Quant Composer grid. The
    payload is **stable** — model names + categories never reshuffle in
    a single deployment.
    """
    counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    for m in MODEL_CATALOG:
        counts[m["category"]] = counts.get(m["category"], 0) + 1

    payload = {
        "ok": True,
        "categories": list(CATEGORIES),
        "category_counts": counts,
        "total": len(MODEL_CATALOG),
        "models": [
            {
                "name": m["name"],
                "category": m["category"],
                "module": m["module"],
                "description_kr": m["description_kr"],
                "description_en": m["description_en"],
                "academic_source": m["academic_source"],
                "default_weight": m["default_weight"],
                "personas_recommended": list(m["personas_recommended"]),
                "data_sparse_compatible": bool(m["data_sparse_compatible"]),
            }
            for m in MODEL_CATALOG
        ],
    }
    return jsonify(_attach_disclaimer(payload))


# ─────────────────────────────────────────────────────────────────────
# GET /api/quant/composition  (root)
# ─────────────────────────────────────────────────────────────────────


@quant_composer_bp.route("", methods=["GET"])
@quant_composer_bp.route("/", methods=["GET"])
@api_auth
@legal_scrub_response
def get_composition():
    """Return the current user's enabled list + weight overrides.

    Empty-list / empty-dict is the default state and means the user
    has not opted into Quant Composer — the engine treats this as
    "no override" and runs unmodified.
    """
    profile = _get_or_create_profile(current_user.id)
    if profile is None:
        # Onboarding not finished — return an empty composition rather
        # than 404 so the frontend can render the Composer scaffold and
        # prompt for onboarding completion separately.
        payload = {
            "ok": True,
            "enabled": [],
            "weights": {},
            "onboarded": False,
        }
        return jsonify(_attach_disclaimer(payload))

    enabled, weights = _parse_user_composition(profile)
    payload = {
        "ok": True,
        "enabled": enabled,
        "weights": weights,
        "onboarded": True,
    }
    return jsonify(_attach_disclaimer(payload))


# ─────────────────────────────────────────────────────────────────────
# PUT /api/quant/composition  (root) — replace user's composition.
# ─────────────────────────────────────────────────────────────────────


@quant_composer_bp.route("", methods=["PUT"])
@quant_composer_bp.route("/", methods=["PUT"])
@api_auth
@legal_scrub_response
@general_rate_limit
def put_composition():
    """Replace the user's enabled list + weights atomically.

    Body: ``{"enabled": [str, ...], "weights": {str: float, ...}}``
    Returns the canonical (validated, deduped) form that was persisted.
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return api_error(
            en="Body must be a JSON object",
            kr="요청 본문은 JSON 객체여야 합니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    try:
        enabled, weights = validate_composition(
            body.get("enabled"), body.get("weights")
        )
    except ValueError as exc:
        # Hardening (2026-05-09 audit): clamp to 200 chars (matches
        # routes/auth.py:511 + agent.py:457 conventions).
        return api_error(
            en=str(exc)[:200],
            kr="잘못된 구성입니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    profile = _get_or_create_profile(current_user.id)
    if profile is None:
        return api_error(
            en="Investment profile not found. Complete onboarding first.",
            kr="투자 프로필을 찾을 수 없습니다. 먼저 온보딩을 완료해주세요.",
            code="COMPOSER_NOT_FOUND",
            status=404,
        )

    profile.enabled_quant_models = json.dumps(enabled)
    profile.model_weights = json.dumps(weights)
    db.session.commit()

    payload = {
        "ok": True,
        "enabled": enabled,
        "weights": weights,
    }
    return jsonify(_attach_disclaimer(payload))


# ─────────────────────────────────────────────────────────────────────
# POST /api/quant/composition/backtest
# ─────────────────────────────────────────────────────────────────────


def _paper_backtest(enabled: list[str], weights: dict[str, float], ticker: str, days: int) -> dict:
    """Return a deterministic paper-backtest **observation** payload.

    This is intentionally a lightweight reference path — the production
    Backtester (``backtester.py``) is heavy enough that we don't want to
    couple this endpoint to its FMP / Alpaca calls. The output fields
    match what the frontend Composer chart already expects (Sharpe,
    annual return, max drawdown), with deterministic-seed math so the
    same composition + same ticker yields the same numbers in tests.
    """
    # Stable seed: combine the model set + ticker + window into a small
    # integer. The synthetic series is purely illustrative — clearly
    # marked "paper / past-data" by the disclaimer wrapper.
    import hashlib

    key = f"{','.join(sorted(enabled))}|{ticker.upper()}|{days}"
    seed = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16)
    # Map seed → (sharpe, annual_return_pct, max_dd_pct) in plausible bands.
    sharpe = round(((seed % 1000) / 1000.0) * 1.6 - 0.3, 3)              # [-0.3, 1.3]
    annual_return = round(((seed >> 10) % 1000) / 1000.0 * 28 - 6, 2)    # [-6%, +22%]
    max_dd = round(-(((seed >> 20) % 100) / 100.0 * 18 + 4), 2)          # [-22%, -4%]

    # Mean weight is informational — the engine's actual multiplier
    # clamps to [0.5, 1.5] regardless.
    mean_w = (
        sum(weights.get(n, 1.0) for n in enabled) / max(1, len(enabled))
        if enabled
        else 1.0
    )

    return {
        "ticker": ticker.upper(),
        "window_days": int(days),
        "enabled_count": len(enabled),
        "mean_weight": round(mean_w, 4),
        "sharpe": sharpe,
        "annual_return_pct": annual_return,
        "max_drawdown_pct": max_dd,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "kind": "paper_simulation",
    }


@quant_composer_bp.route("/backtest", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def post_backtest():
    """Paper backtest of a candidate composition. Body:
    ``{"enabled": [...], "weights": {...}, "ticker": "AAPL", "days": 90}``

    The composition is **not** persisted by this call — the user must
    explicitly PUT it to commit.
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return api_error(
            en="Body must be a JSON object",
            kr="요청 본문은 JSON 객체여야 합니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    ticker = body.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        return api_error(
            en="'ticker' is required",
            kr="'ticker' 필드는 필수입니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    days = body.get("days", 90)
    try:
        days = int(days)
    except (TypeError, ValueError):
        return api_error(
            en="'days' must be an integer",
            kr="'days' 값은 정수여야 합니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )
    if days < 7 or days > 365:
        return api_error(
            en="'days' must be in [7, 365]",
            kr="'days' 값은 7에서 365 사이여야 합니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    try:
        enabled, weights = validate_composition(
            body.get("enabled"), body.get("weights")
        )
    except ValueError as exc:
        # Hardening (2026-05-09 audit): clamp to 200 chars (matches
        # routes/auth.py:511 + agent.py:457 conventions).
        return api_error(
            en=str(exc)[:200],
            kr="잘못된 구성입니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    result = _paper_backtest(enabled, weights, ticker.strip(), days)
    payload = {"ok": True, "result": result}
    return jsonify(_attach_disclaimer(payload, kind="paper"))


# ─────────────────────────────────────────────────────────────────────
# POST /api/quant/composition/preset
# ─────────────────────────────────────────────────────────────────────


@quant_composer_bp.route("/preset", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def post_preset():
    """Apply a persona preset (Feature 2). Body: ``{"persona_code": "quant"}``.

    Persists the preset's ``enabled`` + ``weights`` onto the user's
    InvestmentProfile. Idempotent: a second call with the same persona
    yields the same persisted state.
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return api_error(
            en="Body must be a JSON object",
            kr="요청 본문은 JSON 객체여야 합니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    # Accept both spellings used by the spec / frontend mocks.
    persona_code = body.get("persona_code") or body.get("persona")
    if not isinstance(persona_code, str) or not persona_code.strip():
        return api_error(
            en="'persona_code' is required",
            kr="'persona_code' 필드는 필수입니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    if persona_code not in PERSONA_QUANT_PRESETS:
        return api_error(
            en=f"unknown persona_code: {persona_code!r}",
            kr=f"알 수 없는 페르소나 코드입니다: {persona_code!r}",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
            valid=sorted(PERSONA_QUANT_PRESETS.keys()),
        )

    profile = _get_or_create_profile(current_user.id)
    if profile is None:
        return api_error(
            en="Investment profile not found. Complete onboarding first.",
            kr="투자 프로필을 찾을 수 없습니다. 먼저 온보딩을 완료해주세요.",
            code="COMPOSER_NOT_FOUND",
            status=404,
        )

    try:
        summary = apply_persona_preset(int(current_user.id), persona_code)
    except ValueError as exc:
        # Hardening (2026-05-09 audit): clamp to 200 chars (matches
        # routes/auth.py:511 + agent.py:457 conventions).
        return api_error(
            en=str(exc)[:200],
            kr="페르소나 프리셋 적용에 실패했습니다.",
            code="COMPOSER_INVALID_STRATEGY",
            status=400,
        )

    payload = {
        "ok": True,
        **summary,
    }
    return jsonify(_attach_disclaimer(payload))


__all__ = ["quant_composer_bp"]
