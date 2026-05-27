"""Regression guard: take-profit / stop-loss directives must be caught by the
substring SoT (``contains_forbidden_term``) the same way the regex
``legal_filter`` catches them — WITHOUT over-scrubbing observational copy.

Background (2026-05-27, bug-hunt B#1): the substring SoT in
``services.legal.forbidden_terms`` had drifted from
``services.legal_filter`` — it was missing take-profit/stop-loss directives,
so callers that only use ``contains_forbidden_term`` (support chatbot intent
guard, behaviour-note belt-and-suspenders, artifact mirrors) let those
directives through. The fix added ONLY the unambiguous directive forms; bare
nouns "익절"/"손절" are deliberately excluded to avoid over-scrubbing the
observational behaviour-metric label "손절 속도" and the negation "익절하지 않".
"""
from services.legal.forbidden_terms import contains_forbidden_term


# Directive phrasings that MUST trip the substring SoT.
CAUGHT = [
    "take profit now",
    "you should stop loss here",
    "stoploss soon",
    "익절하세요",
    "손절하세요",
]

# Legitimate observational / negation / neutral copy that MUST NOT trip it.
# Each previously was (or would be, with a naive bare-noun fix) a false
# positive that drops valid copy.
NOT_CAUGHT = [
    "손절 속도 65/100 — 관찰됨",   # behaviour-metric label (scorer.py loss_cut)
    "익절하지 않습니다",            # negation
    "손실 회피 성향이 관찰됨",      # 손실/회피 — neutral behavioural vocab
    "net profit margin grew",      # 'profit' must not match 'take profit'
    "보유 기간 3개월",              # bare 보유 is an allowed accounting noun
]


def test_take_profit_stop_loss_directives_are_caught():
    for text in CAUGHT:
        assert contains_forbidden_term(text) is not None, (
            f"directive slipped through SoT: {text!r}"
        )


def test_observational_and_negation_copy_not_over_scrubbed():
    for text in NOT_CAUGHT:
        assert contains_forbidden_term(text) is None, (
            f"over-scrub false positive on legitimate copy: {text!r}"
        )
