"""
Persona overlay adapter for the Journal Companion.

The universal system prompt lives in
`services/agents/prompts/companion_system.md`. Per-persona *tone* overlays
live in `services/agents/prompts/persona/{code}.md`.

This module composes the final system prompt for a given request:

    [companion_system.md]
    ---
    [persona/{code}.md]

Overlays DO NOT unlock new operations — they only steer tone, favored
vocabulary, and T4 question phrasing. The hard rules in
companion_system.md take absolute precedence at inference time.

Design notes:
  - Files are read from disk on every call (no module-level cache) so ops
    can hot-patch without a service restart, mirroring the rationale in
    `JournalCompanion._load_system_prompt`.
  - An unknown / missing persona code falls back to `balanced`, which is
    also the default in
    `reports/product/PERSONA_SPEC_2026-04-23.md §2`.
  - If even the fallback overlay is missing on disk we return the
    universal prompt alone — the system must never crash due to a
    missing overlay; the fallback behavior is the universal contract,
    which is always safe.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)


# ── Paths ───────────────────────────────────────────────────────────────────

_PROMPTS_DIR: Final[Path] = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT_PATH: Final[Path] = _PROMPTS_DIR / "companion_system.md"
_PERSONA_DIR: Final[Path] = _PROMPTS_DIR / "persona"

# Must match services.agents.journal_companion.VALID_PERSONAS
VALID_PERSONAS: Final[frozenset[str]] = frozenset({
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
})

_DEFAULT_PERSONA: Final[str] = "balanced"

_JOINER: Final[str] = "\n\n---\n\n"


# ── Public API ──────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """Read the canonical universal system prompt.

    Raises RuntimeError if missing — a missing universal prompt is a
    hard failure (legal defense relies on it being present).
    """
    try:
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("agent.system_prompt.missing path=%s", _SYSTEM_PROMPT_PATH)
        raise RuntimeError(
            "Journal Companion system prompt missing — refuse all requests."
        )


def load_persona_overlay(persona_code: str) -> str:
    """Read the overlay for `persona_code`, or the balanced fallback.

    Unknown codes fall back to balanced. If the balanced overlay is
    itself missing (should never happen in a healthy deploy), returns an
    empty string — the caller will compose just the universal prompt,
    which remains safe.
    """
    code = persona_code if persona_code in VALID_PERSONAS else _DEFAULT_PERSONA

    if code != persona_code:
        logger.info(
            "agent.persona.fallback requested=%s -> %s",
            persona_code, _DEFAULT_PERSONA,
        )

    overlay_path = _PERSONA_DIR / f"{code}.md"
    try:
        return overlay_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("agent.persona.overlay_missing path=%s", overlay_path)

    if code != _DEFAULT_PERSONA:
        # Try the balanced fallback once more before giving up.
        fallback_path = _PERSONA_DIR / f"{_DEFAULT_PERSONA}.md"
        try:
            return fallback_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(
                "agent.persona.fallback_missing path=%s", fallback_path,
            )

    return ""


def compose_system_prompt(persona_code: str) -> str:
    """Concatenate universal prompt + persona overlay.

    Format:
        <companion_system.md contents>
        \\n\\n---\\n\\n
        <persona/{code}.md contents>

    If the overlay is empty (missing file), only the universal prompt is
    returned — no trailing separator.
    """
    base = load_system_prompt()
    overlay = load_persona_overlay(persona_code)
    if not overlay:
        return base
    return base + _JOINER + overlay
