"""Regression guard: 표시광고법 §3 ① 1호 (거짓 / 과장 표시광고) — block
"무료 체험" / "원금 보장" / "수익률 보장" / "확실한 수익" / "100% …
수익" / "절대 손실 없음" / "무조건 …" type marketing copy from
landing into the codebase.

Background
----------
2026-04-19 — PivoxQuant beta launch.  Repeated CEO direction:
no advisory verbs, no guarantee verbs, no "free trial" copy when no
actual trial exists (Stripe payment is not yet activated).

표시광고법 §3 ① 1호 prohibits 거짓 / 과장 표시광고.  The KFTC has
specifically called out finance-product marketing using 무조건,
원금 보장, 확실한 수익 patterns as per-se violations regardless of
disclaimers.  This guard makes any such copy fail CI / pre-push.

Scope
-----
Scans:
* `frontend/src/i18n/*.ts` — locale strings
* `frontend/src/app/page.tsx` — landing page
* `frontend/src/components/landing/**/*.tsx` — landing copy
* `frontend/src/app/features/**/*.tsx` — feature pages (marketing)
* `frontend/src/app/pricing/**/*.tsx` — pricing copy

Detection
---------
Quoted string literals + JSX text nodes are scanned for the forbidden
phrase substring.  CSS values (100%, etc.) are not flagged because they
appear inside CSS property values, not string literals carrying
marketing copy.

Allowed
-------
* `tests/`, `services/artifacts/`, backend Python — out of scope.
* Lines containing a documented removal marker (`REMOVED YYYY-MM-DD …`).

Aligned rule: 표시광고법 §3 ① 1호 + 자본시장법 §49 부당권유 회피.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


# Forbidden marketing phrases.  Each entry is a substring match against
# string literals + JSX text nodes (case-insensitive for Latin script).
# We avoid bare "100%", "절대", "확실히" because those have many
# legitimate non-marketing uses (CSS, accessibility copy, technical
# precision claims).  When CEO + legal are ready to extend the list,
# add stricter context-aware patterns then.
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "무료 체험",
    "free trial",
    "원금 보장",
    "수익률 보장",
    "확실한 수익",
    "100% 수익",
    "100% 보장",
    "100% 환불",
    "절대 손실",
    "절대 손해",
    "무조건 수익",
    "무조건 환불",
)


# Removal-marker phrases that excuse a line.  Same convention as
# `test_no_autotrade_copy.py`: the marker must be on the same line as
# the forbidden phrase.
REMOVED_MARKERS: tuple[str, ...] = (
    "REMOVED",
    "retired",
    "기능 제거",
    "removed",
    "removal",
)


# Quoted string literal — single, double, or backtick.  We capture the
# opening quote and require the closing quote of the same kind, but we
# don't try to handle escapes; the phrases above don't contain quotes
# anyway.
_QUOTED_LITERAL_RE = re.compile(
    r"""(['"`])([^'"`]*?)\1"""
)

# JSX text node — content between `>` and `<`.
_JSX_TEXT_RE = re.compile(r">([^<>{}\n]+)<")


def _iter_target_files() -> list[Path]:
    targets: list[Path] = []
    targets.extend((FRONTEND_SRC / "i18n").glob("*.ts"))
    targets.extend((FRONTEND_SRC / "app").rglob("*.tsx"))
    targets.extend((FRONTEND_SRC / "components" / "landing").rglob("*.tsx"))
    return sorted(set(targets))


def _line_is_documented_removal(line: str) -> bool:
    return any(marker in line for marker in REMOVED_MARKERS)


def _phrase_in(haystack: str, needle: str) -> bool:
    """Case-insensitive substring match for Latin script; exact for KR."""
    if all(ord(c) < 128 for c in needle):
        return needle.lower() in haystack.lower()
    return needle in haystack


class TestNoMisleadingMarketingCopy:
    """`무료 체험` / `원금 보장` / `100% 수익` etc. in any user-visible
    surface is a 표시광고법 §3 ① 1호 violation.  This guard blocks
    re-entry; remove the phrase or replace with an accurate claim."""

    def test_no_forbidden_phrase_in_quoted_literal(self) -> None:
        offenders: list[str] = []
        for path in _iter_target_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _line_is_documented_removal(line):
                    continue
                for match in _QUOTED_LITERAL_RE.finditer(line):
                    literal = match.group(2)
                    for phrase in FORBIDDEN_PHRASES:
                        if _phrase_in(literal, phrase):
                            offenders.append(
                                f"{rel}:{lineno}: phrase={phrase!r} :: "
                                f"{literal[:120]!r}"
                            )
                            break
        assert not offenders, (
            "Misleading marketing phrase in a quoted string literal — "
            "표시광고법 §3 ① 1호 (거짓·과장 표시광고) violation. "
            "PivoxQuant has no Stripe-active trial, no principal guarantee, "
            "and no return guarantee. Remove the phrase or replace with an "
            "accurate disclaimer-paired claim.\n\n"
            + "\n".join(offenders)
        )

    def test_no_forbidden_phrase_in_jsx_text_node(self) -> None:
        offenders: list[str] = []
        for path in _iter_target_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _line_is_documented_removal(line):
                    continue
                for match in _JSX_TEXT_RE.finditer(line):
                    segment = match.group(1).strip()
                    if not segment:
                        continue
                    for phrase in FORBIDDEN_PHRASES:
                        if _phrase_in(segment, phrase):
                            offenders.append(
                                f"{rel}:{lineno}: phrase={phrase!r} :: "
                                f"{segment[:120]!r}"
                            )
                            break
        assert not offenders, (
            "Misleading marketing phrase rendered as JSX text — "
            "표시광고법 §3 ① 1호 (거짓·과장 표시광고) violation. "
            "Rewrite to remove the guarantee/trial claim or pair with an "
            "accurate qualifying disclaimer.\n\n"
            + "\n".join(offenders)
        )


class TestTargetSetIsPopulated:
    """Defensive: ensure the scan actually walked the expected tree."""

    def test_target_set_nonempty(self) -> None:
        files = _iter_target_files()
        assert len(files) >= 20, (
            f"marketing target set unexpectedly sparse: {len(files)}"
        )
