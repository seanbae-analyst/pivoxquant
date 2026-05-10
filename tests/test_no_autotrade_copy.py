"""Regression guard: no `자동매매 / autoTrade / auto-trade / autotrader`
copy re-entry across i18n + frontend components.

Background
----------
2026-04-27 — autotrade UI removed (CEO + legal: 투자일임업 회피).
2026-05-05 — `services/autotrader.py` physically deleted.
2026-05-10 — autotrader-style disclaimer kind retired from
`disclaimer-banner.tsx`.

Anyone re-introducing 자동매매 / autoTrade / auto-trade / autotrader
copy in a user-visible surface re-opens the 자본시장법 §6 (투자일임업
무등록) exposure that the 2026-04-27 removal closed. This guard makes
that re-entry fail CI / pre-push.

Scope
-----
Scans:
* `frontend/src/i18n/*.ts` (locale strings)
* `frontend/src/components/**/*.tsx` and `**/*.ts` (component copy)
* `frontend/src/app/**/*.tsx` (page copy)

Allowed
-------
A line is excused when it explicitly documents the 2026-04-27 removal
(any of the markers in `REMOVED_MARKERS` is present on the same line).
Examples:
* `// REMOVED 2026-04-27 per CEO + legal: ...`
* `// (자동매매 기능 제거 — 투자일임업 등록 회피).`
* `/* ── Steps (v3 + AutoTrader removal post 2026-04-27 legal review) ── */`

Aligned rule: 2026-05-05 autotrader.py 물리 삭제 + 표시광고법 §3 ① 4호
기만광고 회피.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


# Forbidden literal substrings (case-insensitive matched).
FORBIDDEN_LITERALS: tuple[str, ...] = (
    "자동매매",
    "autoTrade",
    "auto-trade",
    "autotrader",
)


# Removal-marker phrases that excuse a line. We intentionally keep this
# list narrow so genuine re-entries cannot smuggle themselves in under a
# vague comment.  The phrase must appear on the *same* line as the
# forbidden literal.
REMOVED_MARKERS: tuple[str, ...] = (
    "REMOVED",
    "retired",
    "기능 제거",
    "투자일임업",
    "물리 삭제",
    "removal",
    "removed",
    # Historical IA docstrings list past pages by name (e.g. terminal-sidebar
    # nav-group docstring) — these describe the old layout, not user copy.
    "Autotrade)",
)


def _iter_target_files() -> list[Path]:
    targets: list[Path] = []
    targets.extend((FRONTEND_SRC / "i18n").glob("*.ts"))
    targets.extend((FRONTEND_SRC / "components").rglob("*.tsx"))
    targets.extend((FRONTEND_SRC / "components").rglob("*.ts"))
    targets.extend((FRONTEND_SRC / "app").rglob("*.tsx"))
    return sorted(set(targets))


def _line_is_documented_removal(line: str) -> bool:
    return any(marker in line for marker in REMOVED_MARKERS)


class TestNoAutotradeCopyInFrontend:
    """Block any 자동매매 / autoTrade / auto-trade / autotrader literal
    landing in a user-visible frontend file (i18n / components / app)."""

    def test_no_autotrade_literal(self) -> None:
        offenders: list[str] = []
        for path in _iter_target_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                lower = line.lower()
                hit = next(
                    (
                        lit
                        for lit in FORBIDDEN_LITERALS
                        if lit.lower() in lower
                    ),
                    None,
                )
                if hit is None:
                    continue
                if _line_is_documented_removal(line):
                    continue
                offenders.append(
                    f"{rel}:{lineno}: hit={hit!r} :: {line.strip()[:120]}"
                )
        assert not offenders, (
            "자동매매 / autoTrade / auto-trade / autotrader literal in a "
            "user-visible frontend file. autotrade UI was retired "
            "2026-04-27 + autotrader.py physically deleted 2026-05-05 to "
            "avoid 투자일임업 무등록 (자본시장법 §6) exposure. Document "
            "any legitimate reference with a `// REMOVED YYYY-MM-DD …` "
            "comment so the guard recognises it as a removal marker.\n\n"
            + "\n".join(offenders)
        )


class TestTargetSetIsPopulated:
    """Defensive: ensure the scan actually walked the expected tree."""

    def test_target_set_nonempty(self) -> None:
        files = _iter_target_files()
        assert len(files) >= 100, (
            f"frontend target set unexpectedly sparse: {len(files)}"
        )
