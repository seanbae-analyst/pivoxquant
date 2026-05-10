"""Regression guard (PLACEHOLDER): every Artifact PDF/email template
must carry an "AI 생성물" / "AI generated" badge once the format is
finalised.

Status: TODO — skipped pending lawyer sign-off on the exact label form.

Background
----------
2026-04-22 신규 규제 — AI 생성물 표시제 (방통위) 시행.  Every
GenAI-rendered Artifact (Weekly Memo / Brag Card / Earnings Pre-Brief /
Self-Audit / etc.) must display an AI-origin badge, but the legally
sufficient form (badge text, placement, font weight, colour contrast)
is currently in the variable-cost blocked queue Q14:
"~/.claude/projects/.../memory/legal_question_queue.md".

This test file is the regression hook for the day Q14 lands.  When the
lawyer answers, replace the `pytest.skip()` body below with the actual
assertion:

    assert "AI 생성물" in template_text
    # OR (if English locale ships):
    assert re.search(r"AI[  ]?generated", template_text, re.I)

Until then this file holds the test scaffolding (imports, file
enumeration helper, expected-template list) so the day-of edit is a
3-line change rather than a from-scratch write.

Aligned rule: 방통위 AI 생성물 표시제 (2026-04 시행) +
~/.claude/projects/.../memory/legal_question_queue.md Q14.
"""
from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "services" / "artifacts" / "templates"


# Canonical 14 artifact templates that must carry the AI badge.
# Sourced from `services/artifacts/templates/` — populated lazily so
# the file list stays in sync with the templates directory.
def _iter_artifact_templates() -> list[Path]:
    if not TEMPLATES_DIR.is_dir():
        return []
    return sorted(TEMPLATES_DIR.rglob("*.html"))


# Placeholder — flip to False the day Q14 returns from the lawyer.
_Q14_PENDING = True


@pytest.mark.skipif(
    _Q14_PENDING,
    reason=(
        "TODO Q14 — pending lawyer sign-off on AI 생성물 표시제 badge form. "
        "Replace the skip with a real assertion once the legally-sufficient "
        "label string is decided."
    ),
)
class TestArtifactTemplatesCarryAiBadge:
    """When Q14 returns, replace the body of the test below with the
    actual badge assertion. Keep the file enumeration intact — every
    .html template under services/artifacts/templates/ must carry the
    badge."""

    def test_every_template_carries_ai_badge(self) -> None:  # pragma: no cover
        # FIXME 2026-Q3 — replace with real assertion once Q14 lands:
        #
        #     for path in _iter_artifact_templates():
        #         text = path.read_text(encoding="utf-8")
        #         assert "AI 생성물" in text or re.search(
        #             r"AI[  ]?generated", text, re.I
        #         ), f"AI badge missing: {path.relative_to(REPO_ROOT)}"
        raise NotImplementedError("placeholder — Q14 pending")


class TestPlaceholderSelfShape:
    """The skip-marker is intentional — a future maintainer must not
    silently delete this file thinking it is dead code. The presence
    of `services/artifacts/templates/` and at least 10 templates
    proves the regression target still exists."""

    def test_templates_directory_populated(self) -> None:
        files = _iter_artifact_templates()
        assert len(files) >= 10, (
            "services/artifacts/templates/ unexpectedly sparse: "
            f"{len(files)} files. Either templates were removed or the "
            "skill of this regression guard moved — update the path "
            "before deleting the file."
        )
