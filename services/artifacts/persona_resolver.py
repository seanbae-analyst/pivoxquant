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


def resolve_persona(profile: Any) -> str:
    """Return a persona code from an `InvestmentProfile` instance or ``None``.

    Falls back to `DEFAULT_PERSONA` for missing profiles or unknown
    profile_type strings. Experience / goal hints may override the base
    mapping (see module docstring).
    """
    if profile is None:
        return DEFAULT_PERSONA

    raw = getattr(profile, "profile_type", None) or DEFAULT_PERSONA
    persona = _LEGACY_PROFILE_MAP.get(str(raw).lower(), raw)

    # Beginner override — novices always get the educational track.
    exp = str(getattr(profile, "experience_level", "") or "").lower()
    if exp in {"beginner", "novice"}:
        persona = "beginner"

    # Income override — dividend-oriented goal.
    goal = str(getattr(profile, "investment_goal", "") or "").lower()
    if goal in {"income", "dividend", "preservation"} and persona != "beginner":
        persona = "income"

    if persona not in VALID_PERSONAS:
        return DEFAULT_PERSONA
    return persona


def resolve_persona_from_code(code: Optional[str]) -> str:
    """Direct string-based resolver. Used when the caller already has a code."""
    if not code:
        return DEFAULT_PERSONA
    mapped = _LEGACY_PROFILE_MAP.get(code.lower(), code.lower())
    return mapped if mapped in VALID_PERSONAS else DEFAULT_PERSONA
