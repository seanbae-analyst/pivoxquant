"""Methodology & data-provenance transparency surface (public, read-only).

==============================================================================
Why this exists
==============================================================================
Data-trust strategy Stage 1 (``docs/strategy/DATA_TRUST_STRATEGY.md``): the
strongest proof of trustworthiness is *reproducibility* — "every number we
show can be re-derived from public, licensed data." This endpoint exposes,
in one place and with no user context:

  - the 40-entry (39 active) quant / signal / risk / portfolio / AI / system
    model catalog, each carrying its published ``academic_source`` anchor —
    the reproducibility hook (anyone can re-derive the formula);
  - the system data lineage (FMP v4 / SEC EDGAR / FRED) every computation
    rests on, sourced from ``services.artifacts.data_source_resolver`` so the
    provenance is *never hardcoded in the frontend* — the very anti-pattern
    that resolver was built to prevent (Wave 4 audit, 표시광고법 §3);
  - a plain-language reproducibility statement + the observation-only
    disclaimer.

Legal posture
-------------
Observation-only. No 추천 / 조언 / 매수 / 매도 / buy / sell / hold. The model
descriptions mirror ``model_catalog`` (already verified observation-only by
``tests.test_quant_composer``) and the response passes through
``@legal_scrub_response``.

FLAG-GATED (legal-kr-fintech audit 2026-06-01; Q-DT4 open). The trust surface
is *meant* to be public — a prospect should read *how the engine works* before
trusting us with their (incl. behavioural) data. But until a 핀테크 변호사 signs
off that exposing the per-model ``academic_source`` catalogue is clear of
자본시장법 §101 / 영업비밀 (queued as Q-DT4), it stays behind login by default —
the conservative, reversible posture. Set ``METHODOLOGY_PUBLIC=1`` once Q-DT4 is
answered to restore the public surface. During closed beta this costs nothing
(the whole app already sits behind the Vercel beta gate).

Contract (locked — frontend depends on these field names)
---------------------------------------------------------
``GET /api/methodology``

    200 OK {
        "ok":              true,
        "categories":      ["Quant Edge", "Signal", "Risk", ...],
        "category_counts": {"Quant Edge": 16, ...},
        "total":           40,
        "active":          39,
        "models": [
            {name, category, module, description_kr, description_en,
             academic_source}, ...
        ],
        "data_lineage":    [{source, description, coverage}, ...],
        "reproducibility": {"statement_kr": str, "statement_en": str},
        "disclaimer":      str,
    }

Graceful-fallback contract
--------------------------
Never raises. The catalog is a static in-process constant, so the only
failure surface is the data-lineage import; on any exception that falls back
to an empty ``data_lineage`` list (the page renders "데이터 출처 미표기"
rather than a fabricated source — same truthfulness rule as
``data_source_resolver``: you can't misstate what you refuse to claim).
"""
from __future__ import annotations

import logging
import os

from flask import Blueprint, jsonify
from flask_login import current_user

from services.quant.model_catalog import (
    ACTIVE_MODEL_COUNT,
    CATEGORIES,
    MODEL_CATALOG,
)

from .decorators import legal_scrub_response

logger = logging.getLogger(__name__)

methodology_bp = Blueprint(
    "methodology", __name__, url_prefix="/api/methodology"
)


# Observation-only disclaimer — identical wording to the Quant Composer
# surface so the legal boundary reads consistently across the product.
DISCLAIMER_OBSERVATION = (
    "각 모델은 관찰 instrument 이며 거래 지시를 제공하지 않습니다. "
    "Each model is an observation instrument and does not issue trading directives."
)

_REPRODUCIBILITY_KR = (
    "모든 수치는 공개·라이선스 데이터(FMP·SEC EDGAR·FRED)와 아래 학술 출처에 "
    "공개된 산출식으로 재계산할 수 있습니다. 가중치 등 일부 파라미터를 제외한 "
    "방법론은 블랙박스가 아닙니다."
)
_REPRODUCIBILITY_EN = (
    "Every figure can be re-derived from public, licensed data (FMP, SEC "
    "EDGAR, FRED) and the published formulas in the academic sources below. "
    "Apart from a few parameters such as weights, the methodology is not a "
    "black box."
)


def _methodology_is_public() -> bool:
    """Whether the surface is exposed without a login session.

    Default OFF (login required) — the conservative posture while Q-DT4 (the
    §101 / 영업비밀 review of public ``academic_source`` disclosure) is open.
    Flip ``METHODOLOGY_PUBLIC=1`` after the lawyer signs off.
    """
    return os.environ.get("METHODOLOGY_PUBLIC", "0").strip().lower() in {
        "1", "true", "yes", "on",
    }


@methodology_bp.route("", methods=["GET"])
@methodology_bp.route("/", methods=["GET"])
@legal_scrub_response
def methodology():
    """Methodology + provenance disclosure. Flag-gated (login by default), never raises."""
    if not _methodology_is_public() and not current_user.is_authenticated:
        # Q-DT4 conservative gate (see module docstring). SESSION_EXPIRED so the
        # frontend apiFetch treats it like any other auth wall (lib/api.ts).
        return jsonify({
            "ok": False,
            "error": "Login required",
            "error_kr": "로그인이 필요합니다.",
            "code": "SESSION_EXPIRED",
        }), 401

    counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    for m in MODEL_CATALOG:
        counts[m["category"]] = counts.get(m["category"], 0) + 1

    try:
        from services.artifacts.data_source_resolver import system_data_lineage
        data_lineage = system_data_lineage()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("methodology data lineage unavailable: %s", exc)
        data_lineage = []

    payload = {
        "ok": True,
        "categories": list(CATEGORIES),
        "category_counts": counts,
        "total": len(MODEL_CATALOG),
        "active": ACTIVE_MODEL_COUNT,
        "models": [
            {
                "name": m["name"],
                "category": m["category"],
                "module": m["module"],
                "description_kr": m["description_kr"],
                "description_en": m["description_en"],
                "academic_source": m["academic_source"],
            }
            for m in MODEL_CATALOG
        ],
        "data_lineage": data_lineage,
        "reproducibility": {
            "statement_kr": _REPRODUCIBILITY_KR,
            "statement_en": _REPRODUCIBILITY_EN,
        },
        "disclaimer": DISCLAIMER_OBSERVATION,
    }
    return jsonify(payload)
