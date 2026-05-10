"""
test_ai_content_label.py — Regulatory ③ (2026-01 AI 기본법 / 정보통신망법).

Asserts that the shared `_disclaimer.html` Jinja partial (included by all 17
artifact templates) carries the mandatory "AI 생성 콘텐츠 / AI-generated
content" disclosure label in both Korean and English.

Why a partial-level test:
  All artifact + email templates `{% include '_disclaimer.html' %}` — covering
  the partial transitively covers every PDF/email surface. We additionally
  spot-check a handful of top-level templates to guard against accidental
  inline disclaimer copies that would bypass the partial.

If this test fails, every AI-generated artifact ships without the legally
required "AI 생성" disclosure — block the release.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "services" / "artifacts" / "templates"
DISCLAIMER_PARTIAL = TEMPLATES_DIR / "_disclaimer.html"

# Bilingual label — verbatim text required by regulation.
KO_LABEL = "AI 생성 콘텐츠 (참고용)"
EN_LABEL = "AI-generated content (informational)"

# Templates that include `_disclaimer.html` directly — sampled for the
# include-site spot check.
SPOT_CHECK_TEMPLATES = [
    "weekly_memo.html",
    "earnings_prebrief.html",
    "brag_card.html",
    "year_end_letter.html",
    "kpi_dashboard.html",
]


def test_shared_disclaimer_partial_exists() -> None:
    assert DISCLAIMER_PARTIAL.is_file(), (
        f"Missing shared disclaimer partial: {DISCLAIMER_PARTIAL}"
    )


def test_shared_disclaimer_partial_contains_ai_label_ko() -> None:
    text = DISCLAIMER_PARTIAL.read_text(encoding="utf-8")
    assert KO_LABEL in text, (
        f"Missing KR AI label '{KO_LABEL}' in {DISCLAIMER_PARTIAL}. "
        "Regulatory ③ (2026-01) requires explicit AI-generated content disclosure."
    )


def test_shared_disclaimer_partial_contains_ai_label_en() -> None:
    text = DISCLAIMER_PARTIAL.read_text(encoding="utf-8")
    assert EN_LABEL in text, (
        f"Missing EN AI label '{EN_LABEL}' in {DISCLAIMER_PARTIAL}."
    )


@pytest.mark.parametrize("template_name", SPOT_CHECK_TEMPLATES)
def test_template_includes_shared_disclaimer(template_name: str) -> None:
    """Spot-check that key artifact templates `{% include '_disclaimer.html' %}`
    rather than carrying their own inline disclaimer copy that could drift."""
    path = TEMPLATES_DIR / template_name
    assert path.is_file(), f"Missing template: {path}"
    text = path.read_text(encoding="utf-8")
    assert re.search(
        r"\{%\s*include\s+['\"]_disclaimer\.html['\"]\s*%\}", text
    ), (
        f"{template_name} no longer includes _disclaimer.html — "
        "AI label propagation is broken."
    )
