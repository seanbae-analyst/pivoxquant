"""Quant Composer service — apply per-user model selection + weights to the
engine's quant pillar, validate composition payloads, and surface persona
presets for one-click application (Feature 1 + Feature 2).

Boundaries
----------
- The engine is the only legitimate caller of
  :func:`apply_user_composition`. The route layer never calls it directly;
  it simply persists the user's preferences and lets the next engine pass
  pick them up.
- All input is **adversarial-treated** at the boundary
  (:func:`validate_composition`). Unknown model names, NaN/inf weights,
  negative weights, weights outside ``[0.0, 5.0]``, and non-list / non-dict
  shapes are all rejected — the storage layer should never carry bad data.
- Persona presets (:data:`PERSONA_QUANT_PRESETS`) are **observation-only**:
  rationales describe what the bucket of models *measures*, never what
  the user *should* do. Tests pin this property
  (:mod:`tests.test_quant_composer`).

Backward compatibility
----------------------
:func:`apply_user_composition` short-circuits to ``base_quant_score`` when
the user has never opted in (``enabled_quant_models`` is empty / null).
Existing engine paths that don't pass ``user_id`` are unaffected.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Iterable

from extensions import db
from .model_catalog import MODEL_BY_NAME

logger = logging.getLogger(__name__)


# Hard cap on per-model weight to keep composer arithmetic stable. Beyond
# 5× the engine's quant pillar would dominate the composite to the point
# where Technical / Fundamental / News become decorative — not a posture
# we want to ship behind a single bad slider drag.
WEIGHT_MIN = 0.0
WEIGHT_MAX = 5.0

# Cap on the number of enabled models. The catalog has 40; we hard-stop
# at 40 so a malicious payload can't bloat the JSON column past a sane
# size on Postgres.
MAX_ENABLED_COUNT = 40


# ─────────────────────────────────────────────────────────────────────
# Persona → Quant preset (Feature 2)
# ─────────────────────────────────────────────────────────────────────
#
# Each entry mirrors what a user with that behavioural persona is most
# likely to find informative. Composition counts intentionally match the
# spec table (LAUNCH_BUNDLE_SPEC.md §Feature 2):
#
#   beginner   : 4   models  — defensive volatility + anchoring observation
#   income     : 6   models  — defensive vol + downside-only risk emphasis
#   value      : 8   models  — mean-reversion + behavioural CGO + risk
#   balanced   : 10  models  — diversified across all six categories
#   growth     : 14  models  — momentum-leaning, AI synthesis on top
#   quant      : 22  models  — full quant + behavioural + risk shelf
#   speculator : 12  models  — high-vol / breakout / OFI emphasis
#   daytrader  : 8   models  — intraday + breakout + indicator overlay
#
# All entries reference names present in MODEL_BY_NAME — validated below.

PERSONA_QUANT_PRESETS: dict[str, dict] = {
    "beginner": {
        "enabled": [
            "MeanReversion",
            "VolatilityRegime",
            "MinVariance",
            "AnchoringBias",
        ],
        "weights": {
            "MeanReversion": 1.0,
            "VolatilityRegime": 1.2,
            "MinVariance": 1.5,
            "AnchoringBias": 1.0,
        },
        "rationale": "변동성 안정 관찰을 우선하는 보수적 instrument 구성. 신규 가입자를 위한 관찰 패키지.",
    },
    "income": {
        "enabled": [
            "VolatilityRegime",
            "MinVariance",
            "EqualRiskContribution",
            "SortinoByPosition",
            "ConditionalDrawdown",
            "GKYZVolatility",
        ],
        "weights": {
            "VolatilityRegime": 1.2,
            "MinVariance": 1.5,
            "EqualRiskContribution": 1.3,
            "SortinoByPosition": 1.2,
            "ConditionalDrawdown": 1.1,
            "GKYZVolatility": 1.0,
        },
        "rationale": "하방 변동성 + 분산 균형 관찰을 우선하는 income-style instrument 구성.",
    },
    "value": {
        "enabled": [
            "MeanReversion",
            "DispositionEffect",
            "AnchoringBias",
            "VarianceRatioFilter",
            "ComponentES",
            "TailRiskParity",
            "LedoitWolfShrinkage",
            "AdditionalFundamentals",
        ],
        "weights": {
            "MeanReversion": 1.3,
            "DispositionEffect": 1.2,
            "AnchoringBias": 1.0,
            "VarianceRatioFilter": 1.1,
            "ComponentES": 1.2,
            "TailRiskParity": 1.0,
            "LedoitWolfShrinkage": 1.0,
            "AdditionalFundamentals": 1.4,
        },
        "rationale": "평균회귀 + 펀더멘털 비율 + 좌측 tail 관찰의 value-style instrument 구성.",
    },
    "balanced": {
        "enabled": [
            "MeanReversion",
            "VolatilityRegime",
            "RegimeSwitching",
            "CrossAssetMomentum",
            "VIXStrategy",
            "AdaptiveParams",
            "GKYZVolatility",
            "LedoitWolfShrinkage",
            "HRP",
            "MinVariance",
        ],
        "weights": {
            "MeanReversion": 1.0,
            "VolatilityRegime": 1.2,
            "RegimeSwitching": 1.0,
            "CrossAssetMomentum": 1.0,
            "VIXStrategy": 1.0,
            "AdaptiveParams": 1.0,
            "GKYZVolatility": 1.0,
            "LedoitWolfShrinkage": 1.0,
            "HRP": 1.2,
            "MinVariance": 1.0,
        },
        "rationale": "6개 카테고리 전반에 걸친 분산 관찰 instrument. balanced 페르소나의 default shelf.",
    },
    "growth": {
        "enabled": [
            "MomentumBreakout",
            "TSMOM",
            "FiftyTwoWeekHigh",
            "DualMomentum",
            "VolatilityRegime",
            "RegimeSwitching",
            "CrossAssetMomentum",
            "MLSignal",
            "AdaptiveParams",
            "VIXStrategy",
            "EarningsCallToneAnalyzer",
            "AISectorRotation",
            "AIRiskSummary",
            "CANSLIMScreener",
        ],
        "weights": {
            "MomentumBreakout": 1.3,
            "TSMOM": 1.2,
            "FiftyTwoWeekHigh": 1.0,
            "DualMomentum": 1.2,
            "VolatilityRegime": 1.0,
            "RegimeSwitching": 1.0,
            "CrossAssetMomentum": 1.0,
            "MLSignal": 1.2,
            "AdaptiveParams": 1.0,
            "VIXStrategy": 1.0,
            "EarningsCallToneAnalyzer": 1.0,
            "AISectorRotation": 1.0,
            "AIRiskSummary": 1.0,
            "CANSLIMScreener": 1.1,
        },
        "rationale": "모멘텀 + AI 합성 + CAN SLIM 스크리너 중심의 growth-style instrument 구성.",
    },
    "quant": {
        "enabled": [
            "StatArb",
            "MeanReversion",
            "MomentumBreakout",
            "VolatilityRegime",
            "RegimeSwitching",
            "CrossAssetMomentum",
            "VIXStrategy",
            "MLSignal",
            "AdaptiveParams",
            "VarianceRatioFilter",
            "TSMOM",
            "FiftyTwoWeekHigh",
            "DonchianBreakout",
            "DualMomentum",
            "CorrelationRegime",
            "InterestRateRegime",
            "DispositionEffect",
            "HerdingIntensity",
            "SentimentPriceDivergence",
            "OrderFlowImbalance",
            "AnchoringBias",
            "GKYZVolatility",
        ],
        "weights": {n: 1.0 for n in [
            "StatArb", "MeanReversion", "MomentumBreakout", "VolatilityRegime",
            "RegimeSwitching", "CrossAssetMomentum", "VIXStrategy", "MLSignal",
            "AdaptiveParams", "VarianceRatioFilter", "TSMOM", "FiftyTwoWeekHigh",
            "DonchianBreakout", "DualMomentum", "CorrelationRegime",
            "InterestRateRegime", "DispositionEffect", "HerdingIntensity",
            "SentimentPriceDivergence", "OrderFlowImbalance", "AnchoringBias",
            "GKYZVolatility",
        ]},
        "rationale": "전체 quant + behavioural + 핵심 risk instrument 셸프. quant 페르소나의 full-stack 관찰 구성.",
    },
    "speculator": {
        "enabled": [
            "MomentumBreakout",
            "DonchianBreakout",
            "TSMOM",
            "FiftyTwoWeekHigh",
            "VolatilityRegime",
            "VIXStrategy",
            "MLSignal",
            "OrderFlowImbalance",
            "TailRatio",
            "AdaptiveParams",
            "AdditionalIndicators",
            "RiskDefenseSystem",
        ],
        "weights": {
            "MomentumBreakout": 1.4,
            "DonchianBreakout": 1.3,
            "TSMOM": 1.2,
            "FiftyTwoWeekHigh": 1.1,
            "VolatilityRegime": 1.0,
            "VIXStrategy": 1.0,
            "MLSignal": 1.2,
            "OrderFlowImbalance": 1.2,
            "TailRatio": 1.0,
            "AdaptiveParams": 1.0,
            "AdditionalIndicators": 1.0,
            "RiskDefenseSystem": 1.5,
        },
        "rationale": "Range-break + 고변동성 instrument. RiskDefenseSystem 가중치를 높여 회로차단기 관찰 우선.",
    },
    "daytrader": {
        "enabled": [
            "MomentumBreakout",
            "DonchianBreakout",
            "OrderFlowImbalance",
            "VolatilityRegime",
            "AdaptiveParams",
            "AdditionalIndicators",
            "VIXStrategy",
            "RiskDefenseSystem",
        ],
        "weights": {
            "MomentumBreakout": 1.3,
            "DonchianBreakout": 1.2,
            "OrderFlowImbalance": 1.4,
            "VolatilityRegime": 1.0,
            "AdaptiveParams": 1.1,
            "AdditionalIndicators": 1.2,
            "VIXStrategy": 1.0,
            "RiskDefenseSystem": 1.5,
        },
        "rationale": "Intraday range-break + order-flow 관찰 중심의 daytrader-style instrument.",
    },
}


# Internal sanity check — every persona references only catalogued names.
# Fails loudly at import time if the catalog drifts away from the presets.
for _persona, _spec in PERSONA_QUANT_PRESETS.items():
    for _name in _spec["enabled"]:
        if _name not in MODEL_BY_NAME:
            raise AssertionError(
                f"PERSONA_QUANT_PRESETS[{_persona!r}] references unknown model {_name!r}"
            )
    for _name in _spec["weights"]:
        if _name not in MODEL_BY_NAME:
            raise AssertionError(
                f"PERSONA_QUANT_PRESETS[{_persona!r}].weights references unknown model {_name!r}"
            )


# ─────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────


def validate_composition(
    enabled: Iterable | None,
    weights: dict | None,
) -> tuple[list[str], dict[str, float]]:
    """Validate a composition payload and return canonical types.

    Rejects anything that isn't a list of catalogued model names + a
    dict mapping a (subset of) those names to floats in
    ``[WEIGHT_MIN, WEIGHT_MAX]``. NaN / inf are rejected; missing names
    in ``weights`` default to 1.0 at apply time.

    Returns
    -------
    ``(enabled_canonical, weights_canonical)`` — both safe to persist.

    Raises
    ------
    ``ValueError`` with a human-readable message on any violation.
    """
    if enabled is None:
        enabled = []
    if weights is None:
        weights = {}

    # Shape checks first — bail fast with a clear message.
    if not isinstance(enabled, (list, tuple)):
        raise ValueError("'enabled' must be a list of model names")
    if not isinstance(weights, dict):
        raise ValueError("'weights' must be an object mapping name → float")
    if len(enabled) > MAX_ENABLED_COUNT:
        raise ValueError(
            f"'enabled' length {len(enabled)} exceeds cap of {MAX_ENABLED_COUNT}"
        )

    enabled_canonical: list[str] = []
    seen: set[str] = set()
    for name in enabled:
        if not isinstance(name, str):
            raise ValueError(f"'enabled' entries must be strings, got {type(name).__name__}")
        if name not in MODEL_BY_NAME:
            raise ValueError(f"unknown model name in 'enabled': {name!r}")
        if name in seen:
            # Duplicates are silent-no-ops semantically, but persisting
            # them inflates the column for nothing — collapse here.
            continue
        seen.add(name)
        enabled_canonical.append(name)

    weights_canonical: dict[str, float] = {}
    for name, w in weights.items():
        if not isinstance(name, str):
            raise ValueError(f"'weights' keys must be strings, got {type(name).__name__}")
        if name not in MODEL_BY_NAME:
            raise ValueError(f"unknown model name in 'weights': {name!r}")
        # Accept ints transparently; reject bool (which is_instance(bool, int)) explicitly.
        if isinstance(w, bool) or not isinstance(w, (int, float)):
            raise ValueError(f"'weights[{name!r}]' must be a number, got {type(w).__name__}")
        wf = float(w)
        if math.isnan(wf) or math.isinf(wf):
            raise ValueError(f"'weights[{name!r}]' must be finite")
        if wf < WEIGHT_MIN or wf > WEIGHT_MAX:
            raise ValueError(
                f"'weights[{name!r}]'={wf} out of range [{WEIGHT_MIN}, {WEIGHT_MAX}]"
            )
        weights_canonical[name] = wf

    return enabled_canonical, weights_canonical


# ─────────────────────────────────────────────────────────────────────
# Engine integration
# ─────────────────────────────────────────────────────────────────────


def _load_user_composition(user_id: int | None) -> tuple[list[str], dict[str, float]]:
    """Fetch the persisted ``(enabled, weights)`` for ``user_id``.

    Returns ``([], {})`` whenever:
    - ``user_id`` is None (anonymous engine call),
    - the user has no ``InvestmentProfile`` row,
    - either column is null / unparseable.

    Never raises — the engine's quant_score path is hot and a row that's
    been hand-edited to garbage must NOT take down the analysis.
    """
    if user_id is None:
        return [], {}
    try:
        from models import InvestmentProfile
        profile = db.session.query(InvestmentProfile).filter_by(user_id=int(user_id)).first()
        if profile is None:
            return [], {}
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
        return enabled, weights
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("composer._load_user_composition failed for user=%s: %s", user_id, exc)
        return [], {}


def apply_user_composition(
    user_id: int | None,
    base_quant_score: float,
) -> float:
    """Adjust ``base_quant_score`` in place for the user's composition.

    Behavior contract
    -----------------
    - When the user has NOT opted into Quant Composer (``enabled`` empty),
      this returns ``base_quant_score`` unchanged. Backward compatibility
      with the 1118 existing tests relies on this short-circuit.
    - When the user has opted in, the score is multiplied by the
      *normalised* mean weight across enabled models — so a user with
      ``weights = {"X": 1.0, "Y": 1.0}`` lands at the same score as the
      default, while a user with ``weights = {"X": 1.5, "Y": 1.5}`` lands
      at a 1.5× *intent multiplier* clamped to ``[0.5, 1.5]`` to bound the
      composer's authority over the engine.
    - Output is always clamped to ``[0.0, 100.0]`` — the engine's
      composite math depends on a 0–100 input.

    Why a *bounded* multiplier?
    ---------------------------
    The composer is allowed to *tilt* the user's quant pillar up or down,
    not to *replace* it. A 0.5× / 1.5× envelope keeps the engine's other
    pillars (Technical, Fundamental, News) non-decorative and prevents a
    runaway composition from wiping out the composite cap.
    """
    enabled, weights = _load_user_composition(user_id)
    if not enabled:
        return float(base_quant_score)

    # Validate at the boundary — a row written before validation tightened
    # could still surface stale entries here. Drop unknowns silently in
    # the hot path (validation refuses them at write time).
    enabled = [n for n in enabled if n in MODEL_BY_NAME]
    if not enabled:
        return float(base_quant_score)

    # Mean weight across the enabled set, defaulting unspecified models
    # to 1.0 (neutral). NaN / inf can't reach here because the writer
    # path validates; defend anyway.
    total = 0.0
    for name in enabled:
        w = weights.get(name, 1.0)
        try:
            wf = float(w)
        except (TypeError, ValueError):
            wf = 1.0
        if math.isnan(wf) or math.isinf(wf):
            wf = 1.0
        # Final clamp — the persistence layer enforces this too.
        wf = max(WEIGHT_MIN, min(WEIGHT_MAX, wf))
        total += wf
    mean_weight = total / len(enabled) if enabled else 1.0

    # Bound the composer's authority to ±50% of the base.
    multiplier = max(0.5, min(1.5, mean_weight))
    adjusted = float(base_quant_score) * multiplier

    # Clamp to the engine's expected 0..100 quant_score domain.
    if adjusted < 0.0:
        adjusted = 0.0
    elif adjusted > 100.0:
        adjusted = 100.0
    return adjusted


# ─────────────────────────────────────────────────────────────────────
# Persona preset (Feature 2)
# ─────────────────────────────────────────────────────────────────────


def get_persona_preset(persona_code: str) -> dict | None:
    """Return the immutable preset for ``persona_code``.

    Returns ``None`` when the code is unknown — the caller is expected
    to map that to HTTP 400 / "Unknown persona". The dict is a *copy*
    so accidental mutation by the caller cannot corrupt the global.
    """
    if not isinstance(persona_code, str):
        return None
    spec = PERSONA_QUANT_PRESETS.get(persona_code)
    if spec is None:
        return None
    return {
        "enabled": list(spec["enabled"]),
        "weights": dict(spec["weights"]),
        "rationale": spec["rationale"],
    }


def apply_persona_preset(user_id: int, persona_code: str) -> dict:
    """Persist the persona preset onto the user's InvestmentProfile.

    Returns a serialisable summary used by the route to confirm
    application. Raises ``ValueError`` for unknown personas; the route
    layer turns that into HTTP 400.

    Idempotency
    -----------
    Calling twice with the same ``persona_code`` yields the same
    persisted state. The frontend's "Apply Persona Preset" UX relies on
    this — a double-click never produces drift.
    """
    preset = get_persona_preset(persona_code)
    if preset is None:
        raise ValueError(f"unknown persona_code: {persona_code!r}")

    # Re-validate through the same gate the route uses so a code-path
    # bypassing the route still can't write garbage.
    enabled, weights = validate_composition(preset["enabled"], preset["weights"])

    from models import InvestmentProfile

    profile = db.session.query(InvestmentProfile).filter_by(user_id=int(user_id)).first()
    if profile is None:
        # Caller should have gone through onboarding first. Don't auto-create
        # — the InvestmentProfile model carries onboarding answers we
        # cannot fabricate here.
        raise ValueError(f"no InvestmentProfile for user_id={user_id}")

    profile.enabled_quant_models = json.dumps(enabled)
    profile.model_weights = json.dumps(weights)
    db.session.commit()

    return {
        "applied": True,
        "persona_code": persona_code,
        "enabled_count": len(enabled),
        "rationale": preset["rationale"],
    }


__all__ = [
    "PERSONA_QUANT_PRESETS",
    "WEIGHT_MIN",
    "WEIGHT_MAX",
    "MAX_ENABLED_COUNT",
    "validate_composition",
    "apply_user_composition",
    "get_persona_preset",
    "apply_persona_preset",
]
