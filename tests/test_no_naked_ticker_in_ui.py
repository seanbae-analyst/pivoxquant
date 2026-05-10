"""Regression guard: no naked ticker (raw `\\d{6}\\.K[SQ]` / 1-5 upper)
rendered in JSX text nodes without an accompanying name fallback.

Background
----------
2026-05-10 (v29) — sustained CEO feedback: "몇 번을 말하노."
[feedback_ticker_display] memory file mandates that all user-visible
surfaces show the resolved name (삼성전자 / Apple Inc.) first, with the
raw ticker as a small/dim subline OR fully suppressed. Recurring
regressions (PRs #211 / #212) re-introduced bare `005930.KS` rows.

This guard blocks the simplest re-entry path: a JSX text node that
emits the ticker directly (`>{x.ticker}<`) without a wrapping component
that injects the resolved name (e.g. `<PdfTicker>`).

Scope
-----
Scans every `frontend/src/**/*.tsx` file and flags any line that:

1. emits a raw KR market-suffixed ticker literal as a text node
   (`>005930.KS<`), OR
2. emits a `{x.ticker}` JSX expression directly between two tags
   (`>{x.ticker}<`).

Exception list (intentional ticker exposure — see [feedback_ticker_display])
----------------------------------------------------------------------------
| Path                                                       | Reason                                  |
| ---------------------------------------------------------- | --------------------------------------- |
| frontend/src/components/landing/market-ticker.tsx          | Index ticker strip (rendering raw ticker is the feature) |
| frontend/src/components/terminal/top-ticker.tsx            | Real-time ticker tape                   |
| frontend/src/components/watchlist/add-symbol-modal.tsx     | Search dropdown row — needs raw ticker  |
| frontend/src/app/(dashboard)/discover/page.tsx             | Bronze-tinted mono ticker column (separate cleanup) |
| frontend/src/components/signals/v2/signal-card.tsx         | Subline mono dim ticker (name primary, ticker secondary) |
| frontend/src/components/reports/templates/**.tsx           | PdfTicker wrapper component (printable PDF) |

Aligned rule: PivoxQuant memory `feedback_ticker_display.md` —
"종목이름 자리에 005930.KS만 노출 금지". Recurring CEO feedback.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


# Exceptions — files where raw ticker rendering is intentional + audited.
# Stored as repo-relative POSIX paths so the test runs identically on
# macOS (BSD) and Linux (GNU).
EXCEPTION_FILES: frozenset[str] = frozenset(
    {
        "frontend/src/components/landing/market-ticker.tsx",
        "frontend/src/components/terminal/top-ticker.tsx",
        "frontend/src/components/watchlist/add-symbol-modal.tsx",
        # Bronze-tinted mono ticker column — separate D-grade cleanup.
        "frontend/src/app/(dashboard)/discover/page.tsx",
        # signal-card uses ticker as a *subline* (name is primary).
        "frontend/src/components/signals/v2/signal-card.tsx",
    }
)

# Any path under reports/templates/**.tsx wraps the ticker in
# <PdfTicker>…</PdfTicker> — that component injects the name and styles
# the ticker as a small mono caption. Whitelist by directory.
EXCEPTION_DIR_PREFIXES: tuple[str, ...] = (
    "frontend/src/components/reports/templates/",
)


# Naked KR ticker literal in a JSX text node, e.g. `>005930.KS<`.
# `\b` cannot match before a digit on the right side of `>`, so we use
# explicit boundaries.
NAKED_KR_TICKER_RE = re.compile(r">\s*\d{6}\.K[SQ]\s*<")

# Bare `{xxx.ticker}` JSX expression between two tags.  Allows any
# alphanumeric / dot identifier path on the left of `.ticker`.
NAKED_TICKER_EXPR_RE = re.compile(
    r">\s*\{\s*[A-Za-z_][A-Za-z0-9_.]*\.ticker\s*\}\s*<"
)


def _iter_tsx_files() -> list[Path]:
    assert FRONTEND_SRC.is_dir(), f"frontend src missing: {FRONTEND_SRC}"
    return sorted(FRONTEND_SRC.rglob("*.tsx"))


def _is_excepted(rel_posix: str) -> bool:
    if rel_posix in EXCEPTION_FILES:
        return True
    return any(rel_posix.startswith(p) for p in EXCEPTION_DIR_PREFIXES)


class TestNoNakedKoreanTicker:
    """Block raw `>005930.KS<` JSX text nodes — KR ticker codes carry
    no semantic meaning to users and must be paired with a resolved
    name (e.g. 삼성전자)."""

    def test_no_naked_kr_ticker_in_jsx_text(self) -> None:
        offenders: list[str] = []
        for path in _iter_tsx_files():
            rel_posix = path.relative_to(REPO_ROOT).as_posix()
            if _is_excepted(rel_posix):
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if NAKED_KR_TICKER_RE.search(line):
                    offenders.append(f"{rel_posix}:{lineno}: {line.strip()[:120]}")
        assert not offenders, (
            "Naked KR ticker literal in JSX text node — feedback_ticker_display "
            "memory mandates name-first display. Wrap in a Name+Ticker pair "
            "(e.g. `{name}` primary + `<span class='mono dim'>{ticker}</span>` "
            "subline) or render via the resolveName() helper.\n\n"
            + "\n".join(offenders)
        )


class TestNoNakedTickerExpression:
    """Block bare `>{x.ticker}<` JSX — must be wrapped in a presentation
    component (e.g. `<PdfTicker>`) or paired with the resolved name."""

    def test_no_naked_ticker_expression_in_jsx_text(self) -> None:
        offenders: list[str] = []
        for path in _iter_tsx_files():
            rel_posix = path.relative_to(REPO_ROOT).as_posix()
            if _is_excepted(rel_posix):
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if NAKED_TICKER_EXPR_RE.search(line):
                    offenders.append(f"{rel_posix}:{lineno}: {line.strip()[:120]}")
        assert not offenders, (
            "Naked `{x.ticker}` JSX expression — render the resolved name "
            "first (e.g. `{x.name || resolveName(x.ticker)}`) and demote the "
            "ticker to a small mono subline. See feedback_ticker_display memo "
            "and components/signals/v2/signal-card.tsx for the canonical "
            "name-first pattern.\n\n"
            + "\n".join(offenders)
        )


class TestFrontendDirectoryShape:
    """Defensive: ensure the scan actually walked something."""

    def test_frontend_src_populated(self) -> None:
        files = _iter_tsx_files()
        assert len(files) >= 50, (
            f"frontend/src unexpectedly sparse: {len(files)} *.tsx found"
        )
