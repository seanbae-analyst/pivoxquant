"""
Persona PDF Branch — 8-persona × 3-report rendering tests.

Scope
-----
  - 24 partial HTML files exist on disk (8 personas × 3 section types).
  - `_persona_macros.html` loads and dispatches correctly.
  - 8 personas × 2 reports (weekly_memo / quarterly_self_report) render
    without error = 16 successful renders.
  - Each persona opener contains a distinguishing phrase unique to that
    persona (so a template swap couldn't silently collapse branches).
  - Forbidden advisory vocabulary (BUY/SELL/HOLD/recommend/advice/should/
    must/추천/조언/권유) appears 0 times across all partials.
  - Unknown persona codes fall back to `balanced`.
  - Persona resolver maps legacy profile_types correctly.

Design notes
------------
The 3 templates require many data fields. We build minimal stub contexts
that satisfy Jinja (missing fields default to `None` or empty lists via
the `| default(...)` filters already in the templates). Rendering is
validated by a non-empty HTML string plus persona-phrase assertion — we
do not try to render PDFs (WeasyPrint needs system libs).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARTIAL_DIR = PROJECT_ROOT / "services" / "artifacts" / "templates" / "partials"
TEMPLATE_DIR = PROJECT_ROOT / "services" / "artifacts" / "templates"

PERSONAS = [
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
]
SECTIONS = ["opener", "data_focus", "risk_block"]
# 2026-04-29: weekly_memo.html was redesigned to a 1-page Free template
# (CEO design v3) that does not branch on persona. Persona-specific openers /
# data-focus / risk-block sections still apply to quarterly_self_report.html
# (the Pro+ flagship). The 24 persona partials remain on disk for the legacy
# 6-page Goldman IC v2 archive and other tier templates.
REPORTS = [
    "quarterly_self_report.html",
]

# Phrase uniquely associated with each persona's opener — lets us prove
# the branch actually fired. Pulled from the partial copy (authoritative
# source: PERSONA_SPEC §3 §G).
PERSONA_OPENER_PHRASES = {
    "growth":     "이번 주 움직임의 리더십",
    "value":      "시장이 매긴 가격",
    "balanced":   "포트폴리오 전체가 말하는",
    "income":     "들어올 현금의 지도",
    "quant":      "Factor tilt snapshot",
    "speculator": "꼬리에 집중된",
    "daytrader":  "어제 세션의 숫자",
    "beginner":   "내 포트폴리오에 무슨 일",
}

# Regex for forbidden advisory language. Run across every persona partial.
_FORBIDDEN_EN = re.compile(
    r"\b(buy|sell|hold|recommend|advice|should|must)\b",
    re.IGNORECASE,
)
_FORBIDDEN_KO = re.compile(r"(추천|조언|권유|유망|AI Coach|투자 코치)")


# ── A. File presence ────────────────────────────────────────────────────────

@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("section", SECTIONS)
def test_persona_partial_exists(persona: str, section: str) -> None:
    """Every (persona, section) partial must exist on disk and be non-trivial."""
    path = PARTIAL_DIR / persona / f"{section}.html"
    assert path.exists(), f"missing partial: {path}"
    body = path.read_text(encoding="utf-8")
    # Must contain at least ~200 chars of actual content (not just a stub).
    assert len(body) > 200, f"partial suspiciously short: {path}"
    # Must include a <section class=...> (HTML fragment contract).
    assert "<section" in body, f"partial not a section fragment: {path}"


def test_macros_file_exists() -> None:
    macros = PARTIAL_DIR / "_persona_macros.html"
    assert macros.exists()
    body = macros.read_text(encoding="utf-8")
    for macro_name in (
        "persona_opener", "persona_data_focus", "persona_risk_block",
        "persona_action_points", "persona_benchmark_line",
    ):
        assert f"macro {macro_name}" in body, f"missing macro: {macro_name}"


# ── B. Legal guard — forbidden vocab 0 occurrences ──────────────────────────

def _collect_html_fragments() -> list[Path]:
    return sorted(PARTIAL_DIR.rglob("*.html"))


def test_no_forbidden_english_terms_anywhere() -> None:
    offenders: list[str] = []
    for path in _collect_html_fragments():
        text = path.read_text(encoding="utf-8")
        # Strip Jinja comments ({# ... #}) before scanning — the comment
        # block itself may legally discuss forbidden terms as metadata.
        stripped = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)
        for m in _FORBIDDEN_EN.finditer(stripped):
            offenders.append(f"{path.name}: '{m.group(0)}' at offset {m.start()}")
    assert not offenders, (
        "forbidden English advisory term(s) found in persona partials:\n"
        + "\n".join(offenders)
    )


def test_no_forbidden_korean_terms_anywhere() -> None:
    offenders: list[str] = []
    for path in _collect_html_fragments():
        text = path.read_text(encoding="utf-8")
        stripped = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)
        for m in _FORBIDDEN_KO.finditer(stripped):
            offenders.append(f"{path.name}: '{m.group(0)}' at offset {m.start()}")
    assert not offenders, (
        "forbidden Korean advisory term(s) found in persona partials:\n"
        + "\n".join(offenders)
    )


# ── C. Persona resolver ─────────────────────────────────────────────────────

def test_resolver_unknown_code_falls_back_to_balanced() -> None:
    from services.artifacts.persona_resolver import (
        VALID_PERSONAS, resolve_persona, resolve_persona_from_code,
    )
    assert resolve_persona_from_code(None) == "balanced"
    assert resolve_persona_from_code("") == "balanced"
    assert resolve_persona_from_code("not_a_real_persona") == "balanced"
    # None profile object
    assert resolve_persona(None) == "balanced"
    # All expected codes present
    for p in PERSONAS:
        assert p in VALID_PERSONAS


def test_resolver_maps_legacy_profile_types() -> None:
    from services.artifacts.persona_resolver import resolve_persona_from_code
    assert resolve_persona_from_code("conservative") == "balanced"
    assert resolve_persona_from_code("balanced") == "balanced"
    assert resolve_persona_from_code("growth") == "growth"
    assert resolve_persona_from_code("aggressive") == "speculator"


def test_resolver_beginner_override_by_experience() -> None:
    """A novice user always gets the beginner persona, regardless of type."""
    from services.artifacts.persona_resolver import resolve_persona

    class Profile:
        profile_type = "growth"
        experience_level = "beginner"
        investment_goal = ""

    assert resolve_persona(Profile()) == "beginner"


def test_resolver_income_override_by_goal() -> None:
    from services.artifacts.persona_resolver import resolve_persona

    class Profile:
        profile_type = "balanced"
        experience_level = "intermediate"
        investment_goal = "income"

    assert resolve_persona(Profile()) == "income"


# ── D. Jinja rendering — 8 personas × 3 reports = 24 renders ───────────────

@pytest.fixture(scope="module")
def jinja_env():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _weekly_memo_context(persona: str) -> dict:
    """Minimal context for weekly_memo.html — undefined fields degrade."""
    return {
        "persona":           persona,
        "user_name":         "Test User",
        "week_number":       17,
        "year":              2026,
        "period_start":      "2026-04-16",
        "period_end":        "2026-04-23",
        "generated_at":      "2026-04-23T00:00:00Z",
        "weekly_return_pct": 0.82,
        "benchmark_pct":     0.34,
        "alpha_pct":         0.48,
        "sector_alloc":      {"Technology": 40.0, "Healthcare": 30.0},
        "sector_changes":    [],
        "top_movers_up":     [],
        "top_movers_down":   [],
        "earnings_calendar": [],
        "macro_checklist":   [],
        "risk_notes":        [],
        "risk_kpi":          {},
        "disclaimer":        "정보 제공 목적이며 투자 권유가 아닙니다.",
    }


def _quarterly_context(persona: str) -> dict:
    return {
        "persona":              persona,
        "user_name":            "Test User",
        "quarter_label":        "2026 Q1",
        "period_start":         "2026-01-01",
        "period_end":           "2026-03-31",
        "generated_at":         "2026-04-01T00:00:00Z",
        "opening_value":        100000.0,
        "closing_value":        104200.0,
        "net_cash_flow":        0.0,
        "quarterly_return_pct": 4.2,
        "mdna":                 "분기 서술.",
        "segments":             [],
        "risk_factors":         [],
        "internal_controls":    [],
        "legal_matters":        [],
        "principal_positions":  [],
        "thesis_entries":       [],
        "thesis_checks":        [],
        "decision_quality":     {
            "trades_total":    0, "wins": 0, "losses": 0,
            "win_rate_pct":    None, "avg_return_pct": None,
            "best_decisions":  [], "worst_decisions": [],
            "pattern_summary": "",
        },
        "thesis_checklist":     [],
        "watch_items":          [],
        "disclaimer":           "정보 제공 목적.",
    }


_CTX_BUILDERS = {
    "weekly_memo.html":            _weekly_memo_context,
    "quarterly_self_report.html":  _quarterly_context,
}


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("report", REPORTS)
def test_persona_report_renders(jinja_env, persona: str, report: str) -> None:
    """Every (persona, report) pair renders to a non-empty HTML string."""
    tpl = jinja_env.get_template(report)
    ctx = _CTX_BUILDERS[report](persona)
    html = tpl.render(**ctx)
    assert isinstance(html, str)
    # PDF HTMLs are large (opening page alone is kilobytes)
    assert len(html) > 2000, (
        f"rendered HTML unexpectedly short for {report} [{persona}]: "
        f"{len(html)} chars"
    )


# ── E. Branch discrimination — persona phrase must appear ───────────────────

@pytest.mark.parametrize("persona", PERSONAS)
def test_persona_opener_phrase_unique(jinja_env, persona: str) -> None:
    """Confirm the rendered quarterly self-report contains that persona's
    opener phrase and none of the other 7 persona phrases (cross-leak guard).

    2026-04-29: switched from weekly_memo.html (now a 1-page Free template
    that does not branch on persona) to quarterly_self_report.html where
    persona-specific openers still apply.
    """
    tpl = jinja_env.get_template("quarterly_self_report.html")
    html = tpl.render(**_quarterly_context(persona))

    expected = PERSONA_OPENER_PHRASES[persona]
    assert expected in html, (
        f"persona='{persona}' rendered without its opener phrase '{expected}'"
    )

    other_phrases = [
        phrase for code, phrase in PERSONA_OPENER_PHRASES.items()
        if code != persona
    ]
    # At most 0 of the other 7 should appear in the rendered body.
    leaks = [p for p in other_phrases if p in html]
    assert not leaks, (
        f"cross-persona leak in persona='{persona}' render: {leaks}"
    )


# ── F. Unknown persona → balanced fallback in Jinja ────────────────────────

def test_unknown_persona_macro_fallback(jinja_env) -> None:
    """When an unknown persona code is injected the macro falls back to
    the balanced partial — verified by the balanced opener phrase.
    """
    tpl = jinja_env.get_template("quarterly_self_report.html")
    ctx = _quarterly_context("totally_unknown_persona_xyz")
    html = tpl.render(**ctx)
    # Balanced opener phrase is the fallback target.
    assert PERSONA_OPENER_PHRASES["balanced"] in html


def test_missing_persona_macro_fallback(jinja_env) -> None:
    """When `persona` is omitted entirely the template default fires."""
    tpl = jinja_env.get_template("quarterly_self_report.html")
    ctx = _quarterly_context("balanced")
    ctx.pop("persona", None)
    html = tpl.render(**ctx)
    # `{% set persona = persona | default('balanced') %}` → balanced branch.
    assert PERSONA_OPENER_PHRASES["balanced"] in html


# ── G. §101 surface-label guard — banned short-horizon labels NEVER print ───
#
# DECISIONS.md ✅확정: the user-facing surface may only ever name the 3
# disclosed buckets (성장형 / 균형형 / 수익형 CFO). The 8-code engine personas
# (speculator / daytrader / scalper / swing) drive opener *tone* internally but
# their NAME must never reach a rendered PDF surface. This guard renders every
# persona (incl. the high-risk ones) and asserts the banned label phrases
# appear 0 times. It is the inverse of the old behaviour: previously a
# speculator render printed "Speculator CFO · 투기 CFO" — that is now a FAILURE.

# Exact banned LABEL phrases only (not bare "투기"/"단타" prose tokens — the
# opener prose legitimately discusses short-horizon *concepts*; only the
# persona LABEL strings are forbidden on surface).
_BANNED_SURFACE_LABELS = [
    "투기 CFO", "투기CFO",
    "단타 CFO", "단타CFO",
    "가치 CFO", "밸런스 CFO", "인컴 CFO", "퀀트 CFO", "초보 CFO",
    "스캘퍼 CFO", "스윙 트레이더 CFO",
]
_BANNED_SURFACE_LABELS_EN = re.compile(
    r"\b(Speculator|Daytrader|Day\s*Trader|Scalper|Swing\s*Trader|"
    r"Value|Quant|Beginner)\s+CFO\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("persona", PERSONAS)
def test_no_banned_persona_label_on_surface(jinja_env, persona: str) -> None:
    """Every persona render must show only a 3-bucket disclosed CFO label.

    Previously this assertion was inverted (speculator/daytrader openers were
    expected to print '투기 CFO' / '단타 CFO'). The §101 fix collapses every
    surfaced label to 성장형 / 균형형 / 수익형 CFO via the persona_label macro
    chokepoint — so any banned label is now a hard failure.
    """
    tpl = jinja_env.get_template("quarterly_self_report.html")
    html = tpl.render(**_quarterly_context(persona))

    for banned in _BANNED_SURFACE_LABELS:
        assert banned not in html, (
            f"persona='{persona}' rendered banned surface label '{banned}'"
        )
    en_hit = _BANNED_SURFACE_LABELS_EN.search(html)
    assert en_hit is None, (
        f"persona='{persona}' rendered banned English label "
        f"'{en_hit.group(0) if en_hit else ''}'"
    )

    # And the correct disclosed bucket label IS present.
    from services.profile.persona_analytics import surface_label
    assert surface_label(persona) in html, (
        f"persona='{persona}' missing expected surface label "
        f"'{surface_label(persona)}'"
    )


def test_persona_label_macro_matches_python_ssot() -> None:
    """Drift guard: the Jinja persona_label macro must collapse the 8 codes to
    the same 3 buckets as the canonical Python SSOT
    (services.profile.persona_analytics.PERSONA_TO_SURFACE / surface_label).
    Renders the macro in isolation for each code and checks the printed bucket.
    """
    from jinja2 import Environment, FileSystemLoader
    from services.profile.persona_analytics import surface_label

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.from_string(
        "{% import 'partials/_persona_macros.html' as pm %}"
        "{{ pm.persona_label(persona) | trim }}"
    )
    for code in PERSONAS + ["totally_unknown_xyz"]:
        rendered = tpl.render(persona=code)
        expected_bucket = (
            surface_label(code) if code in PERSONAS else "균형형"
        )
        assert expected_bucket in rendered, (
            f"macro persona_label('{code}') = '{rendered}' does not contain "
            f"expected bucket label '{expected_bucket}'"
        )
