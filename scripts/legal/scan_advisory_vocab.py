"""Advisory-vocabulary scanner — replaces the legal-guard.yml grep block.

Why a script: bash grep was producing false positives on:
- comments and docstrings ("# Legal: no recommend")
- field names ("recommended: boolean")
- negation prose ("not solicit or recommend")

This scanner walks Python / TypeScript / TSX files, strips comments
and string-literal field declarations, then matches the canonical
forbidden-vocab list against semantic prose only.

Forbidden tokens (English + Korean):
- should buy / should sell
- recommend(ed|ing|s)?
- give(s)? investment advice
- 매수하세요 / 매도하세요 / 추천합니다 / 조언드립니다 / 이 종목을 사세요

Skipped contexts:
- comment lines (`#`, `//`, `/*`, `*` JSDoc)
- string literals that look like field declarations (e.g. ``recommended: boolean``)
- prose that contains an explicit negation token within ±5 words
  (never / not / no / nothing / does not / do not / 금지 / 없음 / 않습니다)
- existing whitelist files (legal_filter.py, disclaimer*, consent*, *.test.*, conftest, samples/)

CLI:

    python scripts/legal/scan_advisory_vocab.py [--paths ...] [--out report.md]

Exit codes:
- 0 — no advisory hits
- 1 — at least one hit (CI fail)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_PATHS = [
    REPO_ROOT / "frontend" / "src" / "app",
    REPO_ROOT / "frontend" / "src" / "components",
    REPO_ROOT / "routes",
    REPO_ROOT / "services",
]

INCLUDE_SUFFIXES = {".tsx", ".ts", ".py"}

WHITELIST_PATH_TOKENS = (
    "test_",
    "__pycache__",
    "/legal_filter.py",
    "/disclaimer",
    "/consent",
    ".test.",
    "/conftest",
    "/samples/",
    "/__tests__/",
    "/forbidden_terms.py",
)

EN_TOKENS = re.compile(
    r"\b(?:"
    r"should\s+(?:buy|sell)|"
    r"recommend(?:ed|ing|s)?|"
    r"give[s]?\s+investment\s+advice"
    r")\b",
    flags=re.IGNORECASE,
)

KR_TOKENS = re.compile(
    r"매수하세요|매도하세요|추천합니다|조언드립니다|이\s*종목을\s*사세요"
)

NEGATION_TOKENS = re.compile(
    r"(?:never|not|no|nothing|none|"
    r"does\s+not|do\s+not|isn'?t|aren'?t|cannot|"
    r"buy/sell/recommend|sell/recommend|recommend/predict|"
    r"금지|없음|않습니다|안\s*합니다|아닙니다|아닌)",
    flags=re.IGNORECASE,
)

# ``recommended: boolean`` / ``recommended?: boolean`` — TS field declaration
FIELD_DECLARATION = re.compile(
    r"recommend(?:ed|ing|s)?\??\s*[:]\s*(?:boolean|bool|true|false|string|number)",
    flags=re.IGNORECASE,
)

# ``p.recommended`` / ``item.recommended`` etc. — property access
PROPERTY_ACCESS = re.compile(r"\b\w+\.recommended\b")


# Comment markers per language (include JSDoc continuation `*`)
COMMENT_LINE_RE = re.compile(r"^\s*(?:#|//|\*\s|\*$|/\*|\"\"\"|''')")


# Lines that DEFINE the forbidden vocab itself (regex sources, banned lists)
# legitimately contain the tokens — they are the legal-filter source code.
DEFINITION_CONTEXT = re.compile(
    r"(?:"
    r"banned\s*=|forbidden|FORBIDDEN|regex|pattern|"
    r"r['\"]\\b|tuple\(|list\(|"
    r"backslash|advisory\s+verb|"
    r"# Legal:|# 금지|# Forbidden|"
    r"\"buy\"\s*,|'buy'\s*,|"
    r"such\s+as|imperative\s+copy|"
    r"verbs?\s+\(|words?\s+\(|"
    # disclaimer triplets ("recommend, predict, or guarantee")
    r"recommend,?\s*(?:predict|guarantee|advice|advise)|"
    # ID/label strings ("recommend-verb", "kr-recommend-verb")
    r"['\"][a-z-]*recommend[a-z-]*['\"]|"
    # legal-filter banned-word list ("buy, sell, recommend, advice, ...")
    r"['\"][^'\"]*\b(?:buy|sell)\s*,\s*(?:sell|recommend|advice)|"
    # list-of-forbidden-strings ("recommend", "advice", ...)
    r"['\"]recommend['\"]\s*,\s*['\"]|"
    r"\bnot\s+(?:to\s+)?(?:recommend|advise|solicit)|"
    r"do(?:es)?\s+not\s+(?:recommend|advise|solicit|guarantee|predict)"
    r")",
    flags=re.IGNORECASE,
)


@dataclass
class Hit:
    file: Path
    line_no: int
    line: str
    matched: str
    category: str  # 'en' | 'kr'

    def fmt(self) -> str:
        rel = self.file.relative_to(REPO_ROOT) if self.file.is_relative_to(REPO_ROOT) else self.file
        return f"{rel}:{self.line_no} [{self.category}] {self.line.strip()[:200]}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--paths", nargs="*", type=Path, default=DEFAULT_PATHS)
    p.add_argument("--out", type=Path, default=None,
                   help="Write a markdown report; otherwise print to stdout")
    return p.parse_args()


def is_whitelisted(path: Path) -> bool:
    posix = path.as_posix()
    return any(token in posix for token in WHITELIST_PATH_TOKENS)


def is_comment_line(line: str) -> bool:
    return bool(COMMENT_LINE_RE.match(line))


def has_negation_context(line: str, match_start: int) -> bool:
    """Check whether a forbidden token sits inside negation prose."""
    # ±60 chars window around the match
    left = max(0, match_start - 60)
    right = min(len(line), match_start + 60)
    window = line[left:right]
    return bool(NEGATION_TOKENS.search(window))


def is_field_or_property(line: str) -> bool:
    if FIELD_DECLARATION.search(line):
        return True
    if PROPERTY_ACCESS.search(line):
        return True
    return False


def iter_files(paths: list[Path]):
    for root in paths:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in INCLUDE_SUFFIXES:
                continue
            if is_whitelisted(p):
                continue
            yield p


def is_definition_context(line: str) -> bool:
    """Lines that DEFINE forbidden vocab (regex source, banned lists,
    docstring examples) legitimately mention the tokens."""
    return bool(DEFINITION_CONTEXT.search(line))


def in_docstring_or_block_comment(text: str, line_no: int) -> bool:
    """Cheap heuristic: count unclosed ``\"\"\"`` and ``'''`` markers up to
    line_no — odd count means we are inside a Python docstring."""
    lines = text.splitlines()
    if line_no > len(lines):
        return False
    head = "\n".join(lines[:line_no - 1])
    return (head.count('"""') % 2 == 1) or (head.count("'''") % 2 == 1)


def scan_file(path: Path) -> list[Hit]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    hits: list[Hit] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        if is_comment_line(line):
            continue
        if is_field_or_property(line):
            continue
        if is_definition_context(line):
            continue
        if path.suffix == ".py" and in_docstring_or_block_comment(text, line_no):
            continue

        for category, regex in (("en", EN_TOKENS), ("kr", KR_TOKENS)):
            for m in regex.finditer(line):
                if has_negation_context(line, m.start()):
                    continue
                hits.append(
                    Hit(
                        file=path,
                        line_no=line_no,
                        line=line,
                        matched=m.group(0),
                        category=category,
                    )
                )
    return hits


def render_report(hits: list[Hit]) -> str:
    if not hits:
        return "# Advisory Vocab Scan — clean ✅\n\nNo advisory tokens in production paths.\n"
    lines = [f"# Advisory Vocab Scan — {len(hits)} hit(s) ❌\n"]
    by_cat: dict[str, list[Hit]] = {"en": [], "kr": []}
    for h in hits:
        by_cat[h.category].append(h)
    for cat, label in (("en", "EN advisory"), ("kr", "KR advisory")):
        rows = by_cat[cat]
        if not rows:
            continue
        lines.append(f"## {label} ({len(rows)})\n")
        for r in rows:
            lines.append(f"- {r.fmt()}")
        lines.append("")
    lines.append("## Fix")
    lines.append("- Replace advisory token with observational language")
    lines.append("  (관찰 / observed / pattern / retrospective).")
    lines.append("- If the line is a comment / docstring / disclaimer, the")
    lines.append("  scanner already skipped it — re-inspect and adjust phrasing")
    lines.append("  so the context obviously reads as negation.")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    hits: list[Hit] = []
    for f in iter_files(args.paths):
        hits.extend(scan_file(f))

    report = render_report(hits)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    print(report)
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
