"""Persona resolver for Artifact rendering.

Resolves an `InvestmentProfile` (or a raw `profile_type` string) into one of
the 8 CFO persona codes used by the PDF partial branches:

    growth / value / balanced / income / quant / speculator / daytrader / beginner

Source of truth: reports/product/PERSONA_SPEC_2026-04-23.md §2.

Mapping strategy
----------------
The current `InvestmentProfile` schema stores `profile_type` as one of
{conservative, balanced, growth, aggressive} (models/investment_profile.py).
Until the V2 questionnaire (§2) lands, we map:

    conservative      → balanced   (risk-averse — Balanced CFO)
    balanced          → balanced
    growth            → growth     (Growth CFO)
    aggressive        → speculator (highest risk tolerance — Speculator CFO)

Additional hints (experience_level, investment_goal) refine the mapping:
    experience_level == 'beginner'  → beginner  (override — novice takes priority)
    investment_goal == 'income'     → income    (dividend-tilt)

All unknown codes fall back to `balanced`. This is defense-in-depth: the
Jinja macro also enforces balanced fallback when rendering.
"""
from __future__ import annotations

from typing import Any, Final, Optional

# The canonical 8-persona set. Must match PERSONA_SPEC §2 and
# services.agents.persona_adapter.VALID_PERSONAS.
VALID_PERSONAS: Final[frozenset[str]] = frozenset({
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
})

DEFAULT_PERSONA: Final[str] = "balanced"

# Lightweight mapping for V1 questionnaire → V2 persona.
_LEGACY_PROFILE_MAP: Final[dict[str, str]] = {
    "conservative": "balanced",
    "balanced":     "balanced",
    "growth":       "growth",
    "aggressive":   "speculator",
}

# V2 questionnaire profile_type → persona. When the V2 onboarding lands
# (PROFILE_PRESETS_V2 in questionnaire.py) the questionnaire result
# string is one of these tokens. This lets `resolve_persona` take the
# direct path without going through the V1 legacy aggregation.
# Source of truth: PERSONA_SPEC_2026-04-23.md §2.
_V2_PROFILE_MAP: Final[dict[str, str]] = {
    "momentum_rider":       "growth",
    "value_hunter":         "value",
    "risk_managed_growth":  "balanced",
    "passive_index_hugger": "balanced",   # promoted to ``income`` when dividend_tilt is set
    "macro_rotator":        "quant",
    "swing_trader":         "speculator",
    "aggressive_scalper":   "daytrader",
    "steady_accumulator":   "balanced",   # promoted to ``beginner`` when experience_level == 'novice'
}


def _is_truthy(val: Any) -> bool:
    """Lenient truthiness for stringly-typed profile attributes."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val > 0
    s = str(val).strip().lower()
    return s in {"true", "1", "yes", "y", "on"}


def resolve_persona(profile: Any) -> str:
    """Return a persona code from an `InvestmentProfile` instance or ``None``.

    Falls back to `DEFAULT_PERSONA` for missing profiles or unknown
    profile_type strings. Experience / goal hints may override the base
    mapping (see module docstring).

    Override precedence (lowest → highest):
        1. ``profile_type`` direct mapping (V1 legacy or V2 token).
        2. ``investment_goal`` of {income, dividend, preservation} → ``income``.
        3. ``dividend_tilt`` truthy attribute → ``income``.
        4. ``experience_level`` of {beginner, novice} → ``beginner``.

    The ``dividend_tilt`` field is forward-compatible — it MAY be added
    to ``InvestmentProfile`` in a later migration. Today the resolver
    reads it via ``getattr(profile, 'dividend_tilt', None)`` so the
    code path lights up the moment the column exists.
    """
    if profile is None:
        return DEFAULT_PERSONA

    raw = getattr(profile, "profile_type", None) or DEFAULT_PERSONA
    raw_low = str(raw).lower()

    # Try V2 mapping first (PROFILE_PRESETS_V2 keys), then V1 legacy,
    # then identity (already a persona code).
    persona = (
        _V2_PROFILE_MAP.get(raw_low)
        or _LEGACY_PROFILE_MAP.get(raw_low)
        or raw_low
    )

    # Income overrides — investment_goal hint OR explicit dividend_tilt
    # boolean. Either path promotes to ``income`` unless the beginner
    # gate (below) overrides it.
    goal = str(getattr(profile, "investment_goal", "") or "").lower()
    dividend_tilt = _is_truthy(getattr(profile, "dividend_tilt", None))
    if dividend_tilt or goal in {"income", "dividend", "preservation"}:
        persona = "income"

    # Beginner override — novices always get the educational track.
    # Highest-priority override per PERSONA_SPEC §2.
    exp = str(getattr(profile, "experience_level", "") or "").lower()
    if exp in {"beginner", "novice"}:
        persona = "beginner"

    if persona not in VALID_PERSONAS:
        return DEFAULT_PERSONA
    return persona


def resolve_persona_from_code(code: Optional[str]) -> str:
    """Direct string-based resolver. Used when the caller already has a code."""
    if not code:
        return DEFAULT_PERSONA
    mapped = _LEGACY_PROFILE_MAP.get(code.lower(), code.lower())
    return mapped if mapped in VALID_PERSONAS else DEFAULT_PERSONA
