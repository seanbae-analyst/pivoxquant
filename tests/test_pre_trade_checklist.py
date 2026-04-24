"""Tests for services.artifacts.pre_trade_checklist_service.

Scope
-----
A. Structure   — every persona returns exactly 7 questions (3 universal + 4 specific).
B. Coverage    — all 8 canonical personas are implemented.
C. Legal       — no forbidden terms anywhere in the rendered copy.
D. Determinism — order is stable across calls; universal block is byte-identical.
E. Context     — passing a context dict does not mutate output (reserved field).
F. Unknown     — unknown persona falls back to ``balanced``.
G. Serializer  — build_checklist_as_dicts is round-trippable.

These run in addition to the existing 130 persona_adapter tests and do
not replace them.
"""
from __future__ import annotations

import pytest

from services.artifacts.pre_trade_checklist_service import (
    ChecklistQuestion,
    all_personas,
    build_checklist,
    build_checklist_as_dicts,
)
from services.artifacts.persona_resolver import VALID_PERSONAS


PERSONAS = sorted(VALID_PERSONAS)

# Must mirror ``pre_trade_checklist_service._FORBIDDEN_TERMS``.
FORBIDDEN = (
    "buy", "sell", "hold",
    "recommend", "recommendation", "advice", "advise", "advisor",
    "ai coach", "investment coach",
    "추천", "조언", "투자 코치", "매수", "매도",
)


# ── A. Structure ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("persona", PERSONAS)
def test_every_persona_returns_seven_questions(persona: str) -> None:
    qs = build_checklist(persona)
    assert len(qs) == 7, f"{persona} expected 7 got {len(qs)}"


@pytest.mark.parametrize("persona", PERSONAS)
def test_first_three_are_universal(persona: str) -> None:
    """Universal block must be byte-identical across all personas."""
    qs = build_checklist(persona)
    cats = [q.category for q in qs[:3]]
    assert cats == ["thesis", "exit", "size"], f"{persona} universal order drift"


def test_universal_block_is_identical_across_personas() -> None:
    first = build_checklist("growth")[:3]
    for persona in PERSONAS:
        other = build_checklist(persona)[:3]
        assert other == first, f"{persona} universal diverges from growth"


@pytest.mark.parametrize("persona", PERSONAS)
def test_specific_four_distinct_categories(persona: str) -> None:
    qs = build_checklist(persona)
    specific = qs[3:]
    assert len(specific) == 4
    cats = {q.category for q in specific}
    # All 4 must come from the persona-specific category set. Categories
    # MAY repeat within a persona (e.g. two 'rule' questions are fine) —
    # but none may leak into the universal category set.
    universal = {"thesis", "exit", "size"}
    assert not (cats & universal), (
        f"{persona} persona-specific uses universal category: {cats & universal}"
    )
    valid_cats = {"bias", "regime", "evidence", "rule"}
    assert cats <= valid_cats, f"{persona} uses unknown categories: {cats - valid_cats}"


# ── B. Coverage ────────────────────────────────────────────────────────────

def test_all_personas_exposed() -> None:
    assert set(all_personas()) == set(PERSONAS)


@pytest.mark.parametrize("persona", PERSONAS)
def test_total_assertion_count(persona: str) -> None:
    """8 persona × 7 questions = 56 assertions across the suite."""
    qs = build_checklist(persona)
    assert sum(1 for q in qs if q.prompt) == 7
    assert sum(1 for q in qs if q.why) == 7


# ── C. Legal ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("persona", PERSONAS)
def test_no_forbidden_terms_per_persona(persona: str) -> None:
    for q in build_checklist(persona):
        lowered_prompt = q.prompt.lower()
        lowered_why = q.why.lower()
        for term in FORBIDDEN:
            assert term not in lowered_prompt, f"{persona}: '{term}' in prompt: {q.prompt!r}"
            assert term not in lowered_why, f"{persona}: '{term}' in why: {q.why!r}"


@pytest.mark.parametrize("persona", PERSONAS)
def test_every_prompt_ends_with_question_mark(persona: str) -> None:
    for q in build_checklist(persona):
        assert q.prompt.endswith("?"), f"{persona} non-question prompt: {q.prompt!r}"


# ── D. Determinism ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("persona", PERSONAS)
def test_two_calls_return_same_objects(persona: str) -> None:
    a = build_checklist(persona)
    b = build_checklist(persona)
    assert a == b
    # ChecklistQuestion is frozen dataclass → hashable → can use set equality.
    assert set(a) == set(b)


# ── E. Context (reserved) ──────────────────────────────────────────────────

@pytest.mark.parametrize("persona", PERSONAS)
def test_context_does_not_mutate_output(persona: str) -> None:
    bare = build_checklist(persona)
    with_ctx = build_checklist(persona, context={"ticker": "AAPL", "pe": 32})
    assert bare == with_ctx


# ── F. Unknown persona → balanced ──────────────────────────────────────────

def test_unknown_persona_falls_back_to_balanced() -> None:
    unknown = build_checklist("does-not-exist")
    balanced = build_checklist("balanced")
    assert unknown == balanced


def test_empty_persona_falls_back_to_balanced() -> None:
    assert build_checklist("") == build_checklist("balanced")


# ── G. Serializer ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("persona", PERSONAS)
def test_dict_form_matches_dataclass(persona: str) -> None:
    objs = build_checklist(persona)
    dicts = build_checklist_as_dicts(persona)
    assert len(dicts) == len(objs)
    for obj, d in zip(objs, dicts):
        assert d == {"category": obj.category, "prompt": obj.prompt, "why": obj.why}


def test_checklist_question_is_frozen() -> None:
    q = ChecklistQuestion(category="thesis", prompt="a?", why="b")
    with pytest.raises(Exception):
        q.category = "mutated"  # type: ignore[misc]
