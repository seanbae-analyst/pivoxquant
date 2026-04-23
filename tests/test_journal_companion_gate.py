"""
tests for services.agents.legal_gate — the last line of defense before an
Agent response reaches a paying user. Every allowed language pattern must
pass; every recognised advice pattern must be refused.

Kill-criteria: if any DENY pattern in this suite regresses to PASS, the
Journal Companion must ship with AGENT_ENABLED=False until fixed.
"""

from __future__ import annotations

import pytest

from services.agents.legal_gate import (
    GateVerdict,
    T5_REFUSAL,
    run_gate,
)


# ─────────────────────────────────────────────────────────────────────────────
# A. Advice patterns must DENY
# ─────────────────────────────────────────────────────────────────────────────

DENY_CASES = [
    ("direct-buy",       "I recommend you buy NVDA now."),
    ("direct-sell",      "Time to sell TSLA."),
    ("kr-buy",           "NVDA 매수하세요."),
    ("kr-sell",          "TSLA 매도하시길 권합니다."),
    ("take-profit",      "You should take profit here."),
    ("stop-loss",        "Set a stop loss at 230."),
    ("should",           "You should trim that position."),
    ("kr-recommend",     "해당 종목을 추천드립니다."),
    ("opinion",          "I think NVDA is attractive."),
    ("evaluation",       "That was a bad trade decision."),
    ("kr-evaluation",    "그 결정은 약한 논리였어요."),
    ("label-leak",       "The overall stance is POSITIVE on semis."),
    ("prediction",       "NVDA will rally next week."),
    ("kr-prediction",    "다음 주 상승할 것입니다."),
    ("price-target",     "The target price is around 500."),
    ("kr-price-target",  "목표가는 10만원 부근입니다."),
    ("outlook",          "The outlook for the sector is strong."),
    ("overweight",       "Consider overweight on tech."),
    ("kr-allocation",    "비중 확대를 고려해보세요."),
    ("cross-user",       "Other users in your group tend to trim here."),
    ("kr-cross-user",    "다른 유저들은 이 시점에 매도합니다."),
]


@pytest.mark.parametrize("label,text", DENY_CASES)
def test_advice_patterns_are_denied(label: str, text: str) -> None:
    result = run_gate(text + "\n— Not investment advice. Your record, your decision.")
    assert result.verdict in {
        GateVerdict.DENY_ADVICE_PATTERN,
        GateVerdict.DENY_LEGAL_REGEX,
    }, f"{label}: expected deny, got {result.verdict.value} / {result.reason}"
    assert result.safe_output == T5_REFUSAL


# ─────────────────────────────────────────────────────────────────────────────
# B. Allowed templates must PASS
# ─────────────────────────────────────────────────────────────────────────────

_FOOTER = "— Not investment advice. Your record, your decision."

PASS_CASES = [
    # T1 Memory Recall
    ("t1-memory",
     "On 2026-02-14, about NVDA, you wrote:\n"
     "\"Data center demand and FCF growth are the anchors.\"\n"
     "That is the record.\n" + _FOOTER),
    # T2 Behavioral Mirror (factual only)
    ("t2-mirror",
     "Across your last 12 trades in technology:\n"
     "- Average holding period: 23 days\n"
     "- Win rate on journaled trades: 58%\n"
     "- Win rate on unjournaled trades: 41%\n"
     "Your current decision falls into the journaled category.\n" + _FOOTER),
    # T3 IPS check
    ("t3-ips",
     "Your Investment Policy Statement (effective 2026-01-02) includes:\n"
     "\"Single-position weight cap is 15%.\"\n"
     "Current state: this trade would put NVDA at 18.2% of portfolio.\n"
     "The policy is yours. The number is objective.\n" + _FOOTER),
    # T4 open question
    ("t4-question",
     "What specifically has changed since 2026-02-14, "
     "when you last journaled about this?\n"
     "(I have no opinion. I can only read your record.)\n" + _FOOTER),
    # T6 month summary
    ("t6-summary",
     "This month: 12 trades, avg hold 18 days, "
     "9 journaled / 3 unjournaled.\n"
     "No interpretation.\n" + _FOOTER),
]


@pytest.mark.parametrize("label,text", PASS_CASES)
def test_allowed_templates_pass(label: str, text: str) -> None:
    result = run_gate(text)
    assert result.verdict == GateVerdict.PASS, (
        f"{label}: expected PASS, got {result.verdict.value} / "
        f"{result.reason} / span={result.offending_span!r}"
    )
    assert result.safe_output == text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# C. Structural guards
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_footer_is_denied() -> None:
    result = run_gate(
        "On 2026-02-14 about NVDA you wrote: 'FCF strong'.\nThat is the record."
    )
    assert result.verdict == GateVerdict.DENY_MISSING_FOOTER


def test_over_length_is_denied() -> None:
    body = "paragraph " * 400  # ~3200 chars, exceeds default cap (2400)
    result = run_gate(body + "\n— Not investment advice. Your record, your decision.")
    assert result.verdict == GateVerdict.DENY_LENGTH


def test_empty_is_denied() -> None:
    result = run_gate("")
    assert result.verdict == GateVerdict.DENY_LENGTH
    assert result.safe_output == T5_REFUSAL


def test_refusal_fallback_always_safe() -> None:
    """The T5 refusal itself must survive the gate (a self-consistent output)."""
    result = run_gate(T5_REFUSAL)
    assert result.verdict == GateVerdict.PASS
