"""Single source of truth for compliance scrub of artifact copy.

Why centralise
--------------
Two defense-in-depth lists previously lived inline in
``services/artifacts/pre_trade_checklist_service.py`` (15 terms) and
``services/artifacts/persona_warnings.py`` (16 terms — superset by
``"보유하세요"``). They diverged by accident and the smaller list
opened a real compliance gap. This module is the **only** allowed
home for new directive-language tokens.

Scope
-----
This list catches *directive* phrases (the legal trigger under
자본시장법). It is **not** the place for stylistic prohibitions, brand
names, or PII patterns — those live elsewhere.

Adding a term
-------------
1. Add it to :data:`FORBIDDEN_DIRECTIVE_TERMS` (frozenset; lower-case
   or Hangul; spaces preserved as written by humans).
2. Run the existing per-module legal tests
   (``tests/test_pre_trade_checklist.py::test_no_forbidden_terms_per_persona``
   and ``tests/test_persona_adapter_v2.py::test_rendered_warning_has_no_forbidden_terms``).
   They iterate over a *local* mirror and will flag drift if you
   forget to update both spots — the goal here is to make the
   mirrors thin shims around this canonical set, NOT to keep three
   copies in sync.

Removing a term
---------------
Don't. If you genuinely need to allow a term again — e.g. you can
prove it never appears in a directive context — open a PR with a
legal memo attached. The cost of false-positive failures is much
lower than a compliance incident.
"""
from __future__ import annotations

from typing import Final


# ─────────────────────────────────────────────────────────────────────
# Canonical directive-term blocklist
# ─────────────────────────────────────────────────────────────────────
#
# Notes on intentional gaps:
#   * "추천" alone is still flagged (it appears nowhere in a negation
#     in the current copy; revisit if "비추천" is ever introduced).
#   * "보유" alone is allowed — it is a neutral accounting noun
#     ("보유 기간", "보유 종목 수") that appears in legitimate copy.
#     Only the directive form "보유하세요" is forbidden.

FORBIDDEN_DIRECTIVE_TERMS: Final[frozenset[str]] = frozenset({
    # English single-token tickets to the regulated 자본시장법 trigger.
    "buy",
    "sell",
    "hold",
    "recommend",
    "recommendation",
    "advice",
    "advise",
    "advisor",
    # English compound directives — explicit forms must not slip in
    # through unaudited template additions.
    "buy recommendation",
    "sell recommendation",
    "ai coach",
    "investment coach",
    # Korean directive nouns/verbs (자본시장법 §49 — 투자권유 trigger).
    "추천",
    "조언",
    "투자 코치",
    "매수",
    "매도",
    "매수 추천",
    "매도 추천",
    # Directive form of 보유 — the standalone noun is permitted.
    "보유하세요",
    # ── 2026-05-08 expansion (§101 회피 후속) ──────────────────────────
    # Korean directive verb-phrases that previously slipped through
    # by being assembled from neutral nouns + 검토/유지 hedges.
    "포지션 유지",
    "차익실현",
    "즉시 매도",
    "즉시 청산",
    "추가 매수",
    "청산 검토",
    "매수 검토",
    "매도 검토",
    "포지션 사이징 점검",
    # Performance-suggestion / future-projection vocabulary that drifts
    # toward implicit recommendation framing.
    "적중률",
    "유망",
    "목표가",
    "따라갈 만한",
    "주의가 필요한",
})


def contains_forbidden_term(text: str) -> str | None:
    """Return the first matching forbidden term, or ``None`` if clean.

    Matching is **case-insensitive** for English (Hangul is unaffected
    by ``.lower()``) and **substring-based**. Whitespace inside compound
    forms ("buy recommendation") is preserved verbatim.
    """
    if not text:
        return None
    lowered = text.lower()
    for term in FORBIDDEN_DIRECTIVE_TERMS:
        if term in lowered:
            return term
    return None


def assert_legal_safe(text: str, where: str) -> None:
    """Raise ``ValueError`` when ``text`` contains a forbidden term.

    ``where`` is included in the error so a regression in any caller
    surfaces with the offending location (e.g. ``"value[0].prompt"``).
    """
    hit = contains_forbidden_term(text)
    if hit is not None:
        raise ValueError(
            f"forbidden directive term '{hit}' at {where!r}: {text!r}"
        )


__all__ = [
    "FORBIDDEN_DIRECTIVE_TERMS",
    "contains_forbidden_term",
    "assert_legal_safe",
]
