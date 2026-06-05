"""Regression (B8, 2026-06-05): core 자본시장법 directive terms must stay blocked
by BOTH compliance layers.

PivoxQuant runs two intentionally-different block lists:
  * ``services.legal.forbidden_terms.FORBIDDEN_DIRECTIVE_TERMS`` — substring SoT
    for artifact/template copy + the support-chatbot intent guard.
  * ``services.legal_filter._COMPLIANCE_FORBIDDEN_RE`` — regex applied to runtime
    AI output (SWOT / weekly memo / self-audit).

They are NOT a subset of each other by design: forbidden_terms also blocks
template-only nouns ("유망", "목표가", "처분효과", "적중률") that legal_filter
deliberately lets through so it does not over-scrub legitimate AI prose
(cf. comments in forbidden_terms.py + feedback_legal_filter_design). So a full
parity assertion would be wrong.

This test locks ONLY the unambiguous *core* buy/sell/recommend/advise directives,
which must never drift out of EITHER layer — the bug class flagged by the
2026-06-05 bug hunt (legal_filter.py does not import forbidden_terms.py, so a new
directive added to one could silently be missing from the other).
"""

from services.legal.forbidden_terms import FORBIDDEN_DIRECTIVE_TERMS
from services.legal_filter import _COMPLIANCE_FORBIDDEN_RE

# Unambiguous directive terms that map directly onto the regulated 자본시장법
# 투자권유 trigger. These must be caught by every compliance layer.
CORE_DIRECTIVES = ["buy", "sell", "recommend", "advice", "advise", "추천", "조언"]


def test_core_directives_present_in_forbidden_terms_sot():
    missing = [t for t in CORE_DIRECTIVES if t.lower() not in FORBIDDEN_DIRECTIVE_TERMS]
    assert not missing, (
        "core directive(s) missing from forbidden_terms.FORBIDDEN_DIRECTIVE_TERMS "
        f"(artifact/template SoT): {missing}"
    )


def test_core_directives_caught_by_legal_filter_regex():
    missing = [t for t in CORE_DIRECTIVES if not _COMPLIANCE_FORBIDDEN_RE.search(t)]
    assert not missing, (
        "core directive(s) not matched by legal_filter._COMPLIANCE_FORBIDDEN_RE "
        f"(runtime AI-output gate): {missing}"
    )
