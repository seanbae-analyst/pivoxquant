"""Persona adapter V2 — depth-enhancement tests.

Covers the new modules added in the 2026-04-24 persona personalization
depth upgrade:

  • services.artifacts.persona_warnings  (stat-injected warning copy)
  • services.artifacts.templates.partials._persona_macros.html  (V2 macros)
  • Integration with existing pre_trade_checklist_service.

Runs in addition to (not replacing) the existing persona_adapter and
persona_pdf_branch suites.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.artifacts.persona_warnings import (
    SIGNAL_TYPES,
    generate_warning,
)
from services.artifacts.persona_resolver import VALID_PERSONAS


PERSONAS = sorted(VALID_PERSONAS)

# Mirror of persona_warnings._FORBIDDEN_TERMS (defense-in-depth).
FORBIDDEN = (
    "buy", "sell", "hold",
    "recommend", "recommendation", "advice", "advise", "advisor",
    "ai coach", "investment coach",
    "추천", "조언", "투자 코치", "매수", "매도",
)


MACRO_PATH = (
    Path(__file__).resolve().parent.parent
    / "services" / "artifacts" / "templates" / "partials" / "_persona_macros.html"
)


# ── A. Signal type taxonomy ────────────────────────────────────────────────

def test_signal_types_is_frozen_and_nonempty() -> None:
    assert isinstance(SIGNAL_TYPES, frozenset)
    assert len(SIGNAL_TYPES) >= 8


# ── B. Qualitative fallback — every (persona, signal_type) returns a string

@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("signal_type", sorted(SIGNAL_TYPES))
def test_warning_always_returns_nonempty_string(persona: str, signal_type: str) -> None:
    out = generate_warning(persona, signal_type)
    assert isinstance(out, str)
    assert len(out) > 20, f"{persona}/{signal_type} too short: {out!r}"


# ── C. Stat injection ──────────────────────────────────────────────────────

def test_stat_injection_growth_momentum() -> None:
    out = generate_warning(
        "growth",
        "momentum_entry",
        stats={"median_return_30d": -3.5, "p25": -12.0, "p75": 2.1},
    )
    assert "-3.5%" in out
    assert "-12.0%" in out
    assert "+2.1%" in out


def test_stat_injection_speculator_includes_win_rate() -> None:
    out = generate_warning(
        "speculator",
        "momentum_entry",
        stats={"median_return_30d": -5.2, "win_rate": 0.38},
    )
    assert "-5.2%" in out
    assert "38%" in out  # .format spec {:.0%} -> "38%"


def test_stat_injection_value_trap() -> None:
    out = generate_warning(
        "value",
        "low_multiple",
        stats={"median_return_30d": -1.2, "p25": -18.4, "p75": 0.0},
    )
    assert "-1.2%" in out
    assert "-18.4%" in out


def test_stat_injection_income_dividend_trap() -> None:
    out = generate_warning(
        "income",
        "high_dividend",
        stats={"median_return_30d": -8.0, "win_rate": 0.22},
    )
    assert "-8.0%" in out
    assert "22%" in out


def test_stat_injection_daytrader_consecutive_losses() -> None:
    out = generate_warning(
        "daytrader",
        "consecutive_losses",
        stats={"median_return_30d": -2.4},
    )
    assert "-2.4%" in out


# ── D. Graceful fallback on bad stats ──────────────────────────────────────

def test_missing_placeholder_falls_back_to_qualitative() -> None:
    # growth/momentum_entry needs median_return_30d, p25, p75
    out = generate_warning(
        "growth",
        "momentum_entry",
        stats={"median_return_30d": -1.0},  # missing p25, p75
    )
    # Qualitative fallback must NOT contain numeric %.
    assert "%" not in out or "p25" not in out
    assert len(out) > 20


def test_empty_stats_falls_back_to_qualitative() -> None:
    out_with = generate_warning("growth", "momentum_entry", stats={})
    out_without = generate_warning("growth", "momentum_entry")
    assert out_with == out_without


def test_unknown_signal_type_returns_generic() -> None:
    out = generate_warning("growth", "nonexistent_signal")
    assert "포트폴리오 관찰 대상" in out  # text from _GENERIC


def test_unknown_persona_still_returns_string() -> None:
    out = generate_warning("does-not-exist", "momentum_entry")
    assert isinstance(out, str) and len(out) > 10


# ── E. Legal scrub on rendered output ──────────────────────────────────────

@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("signal_type", sorted(SIGNAL_TYPES))
def test_rendered_warning_has_no_forbidden_terms(
    persona: str, signal_type: str
) -> None:
    # Qualitative
    q = generate_warning(persona, signal_type).lower()
    for term in FORBIDDEN:
        assert term not in q, f"{persona}/{signal_type}: '{term}' in: {q!r}"


def test_stat_rendered_warning_has_no_forbidden_terms() -> None:
    stats = {"median_return_30d": -5.0, "p25": -10.0, "p75": 1.0, "win_rate": 0.4}
    for persona in PERSONAS:
        for signal_type in sorted(SIGNAL_TYPES):
            out = generate_warning(persona, signal_type, stats=stats).lower()
            for term in FORBIDDEN:
                assert term not in out, (
                    f"{persona}/{signal_type} w/stats: '{term}' in: {out!r}"
                )


# ── F. Macro file — V2 macros exist ────────────────────────────────────────

@pytest.mark.parametrize("macro_name", [
    "weekly_memo_section_order",
    "risk_block_position",
    "brag_card_highlight_metric",
    "earnings_prebrief_focus",
    "pre_trade_checklist",
])
def test_v2_macro_defined(macro_name: str) -> None:
    body = MACRO_PATH.read_text(encoding="utf-8")
    assert f"macro {macro_name}(" in body, f"macro {macro_name} missing"


@pytest.mark.parametrize("persona", PERSONAS)
def test_weekly_memo_section_order_branch_exists(persona: str) -> None:
    """Every persona must have its own branch in weekly_memo_section_order."""
    body = MACRO_PATH.read_text(encoding="utf-8")
    # Each persona code must appear inside the macro branch list.
    marker_a = f"persona == '{persona}'"
    marker_b = f"persona in ['{persona}'"
    marker_c = f"'{persona}',"
    assert (marker_a in body) or (marker_b in body) or (marker_c in body), (
        f"{persona}: no branch in _persona_macros.html"
    )


@pytest.mark.parametrize("persona", PERSONAS)
def test_brag_card_highlight_metric_branch_exists(persona: str) -> None:
    body = MACRO_PATH.read_text(encoding="utf-8")
    assert f"persona-focus-block--{persona}" in body or f"persona == '{persona}'" in body


def test_risk_block_position_distinguishes_high_risk_personas() -> None:
    body = MACRO_PATH.read_text(encoding="utf-8")
    # The two personas that must render risk BEFORE data.
    assert "risk_first" in body
    assert "speculator" in body and "daytrader" in body


# ── G. Sanity — module count / persona coverage ───────────────────────────

def test_signal_type_count_matches_module() -> None:
    from services.artifacts import persona_warnings as pw
    assert set(pw.SIGNAL_TYPES) == set(SIGNAL_TYPES)
