"""
Tests for services.agents.persona_adapter.

Scope:
  - All 8 persona overlay files exist on disk.
  - compose_system_prompt preserves every HARD RULE phrase from
    companion_system.md (substring assertions — the overlay must never
    re-define, weaken, or shadow the rules).
  - Composed prompt length >= universal + overlay length (proving both
    are concatenated, not truncated).
  - Unknown persona codes fall back to balanced.
  - Persona overlays themselves contain zero forbidden advisory words
    (regulatory defense — overlays ship to users via Claude API).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.agents.persona_adapter import (
    VALID_PERSONAS,
    compose_system_prompt,
    load_persona_overlay,
    load_system_prompt,
)


PERSONA_DIR = (
    Path(__file__).resolve().parent.parent
    / "services" / "agents" / "prompts" / "persona"
)


# ── A. File presence ────────────────────────────────────────────────────────

EXPECTED_PERSONAS = [
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
]


@pytest.mark.parametrize("persona", EXPECTED_PERSONAS)
def test_every_persona_overlay_exists(persona: str) -> None:
    path = PERSONA_DIR / f"{persona}.md"
    assert path.exists(), f"missing overlay: {path}"
    body = path.read_text(encoding="utf-8")
    assert len(body) > 200, f"overlay too short (suspicious): {path}"


def test_adapter_persona_set_matches_companion() -> None:
    """persona_adapter.VALID_PERSONAS must match journal_companion.VALID_PERSONAS."""
    from services.agents.journal_companion import VALID_PERSONAS as JC_SET
    assert VALID_PERSONAS == JC_SET


# ── B. Hard-rule preservation ───────────────────────────────────────────────

# Phrases from companion_system.md HARD RULES that must survive composition.
# If any of these regress, the legal defense is weakened.
HARD_RULE_PHRASES = [
    # Absolute prohibitions header
    "HARD RULES",
    # Advice-refusal canned response
    "I can't advise. I can only help you check against your own past reasoning.",
    # Mandatory footer
    "— Not investment advice. Your record, your decision.",
    # Template markers
    "T1 · Memory Recall",
    "T2 · Behavioral Mirror",
    "T3 · IPS Covenant Check",
    "T4 · Question (open, no leading)",
    "T5 · Refusal",
    "T6 · Month Summary (factual)",
    # Legal-defense guardrail
    "If the situation does not fit T1–T6, respond with T5.",
    # Success metric
    "zero advice events in 365 days",
]


@pytest.mark.parametrize("persona", EXPECTED_PERSONAS)
@pytest.mark.parametrize("phrase", HARD_RULE_PHRASES)
def test_hard_rules_survive_composition(persona: str, phrase: str) -> None:
    composed = compose_system_prompt(persona)
    assert phrase in composed, (
        f"persona={persona}: HARD RULE phrase missing after composition: "
        f"{phrase!r}"
    )


# ── C. Length invariant ─────────────────────────────────────────────────────

def test_composed_prompt_is_at_least_base_plus_overlay_len() -> None:
    """Composed = base + joiner + overlay — length must be >= sum of parts."""
    base = load_system_prompt()
    overlay = load_persona_overlay("growth")
    composed = compose_system_prompt("growth")
    assert len(composed) >= len(base) + len(overlay), (
        f"composed={len(composed)} vs base={len(base)} + overlay={len(overlay)}"
    )
    # And both contents must be substrings
    assert base in composed
    assert overlay in composed


# ── D. Unknown-persona fallback ─────────────────────────────────────────────

def test_unknown_persona_falls_back_to_balanced() -> None:
    balanced_overlay = load_persona_overlay("balanced")
    unknown_overlay = load_persona_overlay("nonexistent-persona-code")
    assert unknown_overlay == balanced_overlay
    # Identity line of balanced persona must appear
    assert "극단이 아닌 일관성" in unknown_overlay


def test_compose_system_prompt_unknown_persona_uses_balanced() -> None:
    composed_unknown = compose_system_prompt("nobody")
    composed_balanced = compose_system_prompt("balanced")
    assert composed_unknown == composed_balanced


def test_empty_string_persona_falls_back() -> None:
    overlay = load_persona_overlay("")
    assert "극단이 아닌 일관성" in overlay  # balanced identity


# ── E. Forbidden-word sweep across ALL overlays ─────────────────────────────
#
# Overlays concatenate directly into the Claude system prompt the user
# never sees, but any advisory word in this layer risks leaking into the
# model's output. The footer string "Not investment advice." is the sole
# legitimate occurrence of "advice" — handled by substring subtraction.

_FORBIDDEN_EN = re.compile(
    r"\b(buy|sell|recommend|advise|suggest|should|must)\b",
    re.IGNORECASE,
)
_FORBIDDEN_KR = re.compile(
    r"(추천|조언|권유|권장|유망|매수하|매도하|손절|익절|해야\s?한다|유리하다)"
)
# "advice" is forbidden EXCEPT inside the mandatory disclaimer footer
_ALLOWED_ADVICE_CONTEXT = "Not investment advice"


def _strip_allowed_footer(text: str) -> str:
    return text.replace(_ALLOWED_ADVICE_CONTEXT, "")


@pytest.mark.parametrize("persona", EXPECTED_PERSONAS)
def test_overlay_has_no_forbidden_advice_english(persona: str) -> None:
    body = _strip_allowed_footer(load_persona_overlay(persona))
    # "hold" is legit when referring to "holding period" — T2/T6 use
    # "avg hold" / "holding period" already, so we don't ban the bare word.
    matches = _FORBIDDEN_EN.findall(body)
    assert matches == [], f"{persona}: forbidden EN words: {matches}"


@pytest.mark.parametrize("persona", EXPECTED_PERSONAS)
def test_overlay_has_no_forbidden_advice_korean(persona: str) -> None:
    body = load_persona_overlay(persona)
    matches = _FORBIDDEN_KR.findall(body)
    assert matches == [], f"{persona}: forbidden KR words: {matches}"


# ── F. Structural sanity per overlay ────────────────────────────────────────

@pytest.mark.parametrize("persona", EXPECTED_PERSONAS)
def test_overlay_has_required_sections(persona: str) -> None:
    body = load_persona_overlay(persona)
    for heading in ["Identity line", "Tone sliders", "T4 question style",
                    "T6 summary style", "Vocabulary preferences"]:
        assert heading in body, f"{persona}: section missing: {heading}"


@pytest.mark.parametrize("persona", EXPECTED_PERSONAS)
def test_overlay_mentions_companion_system(persona: str) -> None:
    """Every overlay must explicitly defer to companion_system.md."""
    body = load_persona_overlay(persona)
    assert "companion_system.md" in body, (
        f"{persona}: overlay does not reference the universal prompt"
    )
