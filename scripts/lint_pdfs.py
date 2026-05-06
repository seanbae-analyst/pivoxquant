#!/usr/bin/env python3
"""
PivoxQuant PDF Placeholder Lint
================================

Scans generated PDFs for template-variable leaks and common output-quality issues.
Run as a pre-publication check; exits non-zero if any P0 issues are found.

Usage:
    python lint_pdfs.py <directory>
    python lint_pdfs.py <directory> --markdown report.md
    python lint_pdfs.py <directory> --json report.json

Detects:
  P0  hard-broken template placeholders that must be fixed before shipping
  P1  suspicious patterns (doubled years, wrong default text, typos)
  P2  stylistic patterns (LLM short/long Korean duplication)

Dependencies:
    pip install pypdf
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except ImportError:
        sys.stderr.write("Missing dependency: pip install pypdf\n")
        sys.exit(2)


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
# Each rule: (severity, regex, human_name, hint)
# P0 = ship-blocker  (clearly a placeholder that wasn't filled)
# P1 = likely wrong  (date/identifier issues, wrong-template defaults, typos)
# P2 = stylistic     (LLM output artifacts you may want to clean up)

RULES = [
    # ---- P0 — broken template placeholders ----
    # 5th element: use_collapsed (True = match against CJK-space-collapsed text)
    ("P0", r"\bLesson\s+\d+\s+(Title|Body)\b",
     "Lesson N Title/Body placeholder",
     "변수 미치환. Year-End Letter의 LESSON 슬롯을 실제 내용으로 채우세요.",
     False),

    # PDF extraction often concatenates "Promise 2" with the right-aligned
    # "RULE 02" label into "Promise 2RULE 02". Detect both shapes.
    ("P0", r"(?m)^\s*Promise\s*[2-9](?:\s*RULE\s*\d+|\s*$)",
     "Empty Promise N placeholder",
     "Promise 슬롯이 비어있습니다.",
     False),

    ("P0", r"\bCfo\s+Memo\b",
     "Cfo Memo placeholder",
     "CFO Memo 본문 자리에 라벨이 그대로 출력됨.",
     False),

    # "Letter Body" sometimes concatenates with the next label
    # ("Letter BodyRETURN TARGET"), so \b after "Body" can fail.
    ("P0", r"\bLetter\s+Body(?![a-z])",
     "Letter Body placeholder",
     "Year-End Letter 본문 자리에 라벨이 그대로 출력됨.",
     False),

    ("P0", r"\bMistake\s+Text\b",
     "Mistake Text placeholder",
     "변수 미치환.",
     False),

    ("P0", r"\bReinvest\s+Text\b",
     "Reinvest Text placeholder",
     "변수 미치환.",
     False),

    ("P0", r"\bBias\s+Text\b",
     "Bias Text placeholder",
     "변수 미치환 (Morning Brief).",
     False),

    ("P0", r"\bPost\s+Earnings\s+Notes\b",
     "Post Earnings Notes label leak",
     "입력 필드 라벨이 본문에 노출됨.",
     False),

    ("P0", r"\b(Rivn|Lcid|Rblx)\s+Note\s*—",
     "<Ticker> Note placeholder",
     "Burn Rate 본문 자리에 라벨이 그대로 출력됨.",
     False),

    ("P0", r"\bFY\s*Next\s*Fy\b",
     "FYNext Fy variable name",
     "Year-End Letter 헤더의 변수가 치환되지 않음.",
     False),

    ("P0", r"\bCompany\s*Name\b(?!\s+is)",
     "CompanyName variable",
     "Earnings Pre-brief의 종목명 변수 미치환.",
     False),

    ("P0", r"\bQQ\d+\s+\d{4}\s+FY\d{4}\b",
     "Quarter / FY variable leak",
     "QQ1 FY2026 같은 템플릿 토큰 미치환.",
     False),

    ("P0", r"\bREPORT\s+DATE\b",
     "REPORT DATE label leak",
     "헤더 라벨이 그대로 출력 (Earnings Pre-brief).",
     False),

    ("P0", r"(?m)^Headline\s+[4-9]\b\s+—",
     "Headline N — placeholder",
     "Morning Brief의 빈 헤드라인 슬롯.",
     False),

    ("P0", r"(?m)^Keyword\s+[1-9]\b\s+—",
     "Keyword N — placeholder",
     "Earnings Pre-brief의 키워드 슬롯.",
     False),

    # ---- P1 — likely-wrong but not necessarily broken ----
    ("P1", r"\b(20\d{2})\s+\1\b",
     "Doubled year",
     "헤더에 연도가 두 번 나옴 (예: 'APRIL 2026 2026').",
     False),

    # Wrong default CFO note. Match against collapsed text so Korean glyph
    # spacing inserted by the PDF extractor doesn't break the match.
    ("P1", r"시그널은\s*시그널일\s*뿐\.\s*사이즈\s*룰\s*지키",
     "Wrong default CFO note (insider-mirror text leaking into other reports)",
     "이 문구는 Insider Mirror 전용. 다른 리포트의 CFO NOTE 기본값으로 잘못 박혀있음.",
     True),

    ("P1", r"\b술명\b",
     "Possible typo: '술명'",
     "'수명' 또는 '선언/술회'의 오탈자로 추정.",
     True),

    ("P1", r"(?m)^Plan\s+[1-9]\s*$",
     "Empty Plan N placeholder",
     "Plan 슬롯이 비어있음.",
     False),

    # Memo-to-Self / similar grey placeholder paragraphs that leak into output
    ("P1", r"이번\s*주\s*떠오른\s*생각,\s*다음\s*주\s*점검\s*사항",
     "Memo-to-Self placeholder (gray hint text) leaked into output",
     "Weekly Memo의 placeholder hint가 그대로 인쇄됨.",
     True),

    # Mismatched issue numbers between header and footer
    # (heuristic: same prefix appears with two different trailing numbers)
    # Skipped — too noisy to detect cleanly across templates.

    # ---- P2 — stylistic ----
    # LLM short/long Korean duplication: "<short Korean.> — <long Korean.>"
    # Conservative pattern (run on collapsed text so the period anchor works
    # even when the extractor injected glyph-spacing).
    ("P2",
     r"([가-힣][^.\n]{8,80}\.)\s*—\s*([가-힣][^.\n]{12,200}\.)",
     "Possible short/long Korean duplication",
     "LLM이 짧은 버전과 긴 버전을 둘 다 출력했을 가능성. 'A. — A...' 패턴.",
     True),
]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as e:  # pragma: no cover
            pages.append(f"[extract error: {e}]")
    return "\n".join(pages)


# Some PDF extractors insert single spaces between every CJK glyph. We collapse
# those when matching certain rules, but keep an offset map so we can still
# point back to the original source location for context.
def collapse_cjk_spaces(text: str):
    """Return (collapsed_text, mapping) where mapping[i] is the index in the
    original text that produced the character at index i in collapsed_text."""
    out_chars = []
    out_map = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        out_chars.append(ch)
        out_map.append(i)
        # If current char is CJK and next is a single space and char after is
        # also CJK or punctuation, drop the space.
        if (
            i + 2 < n
            and _is_cjk(ch)
            and text[i + 1] == " "
            and (_is_cjk(text[i + 2]) or text[i + 2] in ".,·—-()[]?!:;%")
        ):
            i += 2
            continue
        i += 1
    return "".join(out_chars), out_map


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    return (
        0xAC00 <= cp <= 0xD7A3      # Hangul syllables
        or 0x3130 <= cp <= 0x318F   # Hangul compat jamo
        or 0x4E00 <= cp <= 0x9FFF   # CJK unified
    )


def lint_text(text: str):
    findings = []
    collapsed, mapping = collapse_cjk_spaces(text)

    for severity, pattern, name, hint, use_collapsed in RULES:
        haystack = collapsed if use_collapsed else text
        for m in re.finditer(pattern, haystack):
            start, end = m.span()
            if use_collapsed:
                # Translate back to original text indices for context display
                orig_start = mapping[start] if start < len(mapping) else 0
                orig_end = mapping[end - 1] + 1 if 0 < end <= len(mapping) else len(text)
                src = text
            else:
                orig_start, orig_end, src = start, end, text
            ctx_start = max(0, orig_start - 40)
            ctx_end = min(len(src), orig_end + 40)
            context = src[ctx_start:ctx_end].replace("\n", " ")
            context = re.sub(r"\s+", " ", context).strip()
            findings.append({
                "severity": severity,
                "rule": name,
                "match": m.group(0)[:120],
                "context": context[:200],
                "hint": hint,
            })
    return findings


def lint_file(pdf_path: Path):
    text = extract_text(pdf_path)
    return lint_text(text)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def render_text(results, target_dir: Path) -> str:
    out = []
    out.append(f"PivoxQuant PDF Lint  -  {target_dir}")
    out.append("=" * 78)
    total = sum(len(f) for f in results.values())
    by_sev = defaultdict(int)
    for findings in results.values():
        for f in findings:
            by_sev[f["severity"]] += 1

    out.append(f"{len(results)} files scanned  -  {total} findings  "
               f"(P0={by_sev['P0']}  P1={by_sev['P1']}  P2={by_sev['P2']})")
    out.append("")

    for fname in sorted(results.keys()):
        findings = results[fname]
        if not findings:
            continue
        findings = sorted(findings, key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"]))
        out.append(f"-- {fname}  ({len(findings)} issues)")
        for f in findings:
            out.append(f"   [{f['severity']}] {f['rule']}")
            out.append(f"        match:   {f['match']!r}")
            out.append(f"        context: ...{f['context']}...")
        out.append("")

    out.append("SUMMARY")
    out.append("-" * 78)
    out.append(f"  {'File':<40}  {'P0':>3}  {'P1':>3}  {'P2':>3}")
    out.append(f"  {'-'*40}  {'-'*3}  {'-'*3}  {'-'*3}")
    for fname in sorted(results.keys()):
        c = defaultdict(int)
        for f in results[fname]:
            c[f["severity"]] += 1
        if any(c.values()):
            out.append(f"  {fname:<40}  {c['P0']:>3}  {c['P1']:>3}  {c['P2']:>3}")
    out.append("")
    return "\n".join(out)


def render_markdown(results, target_dir: Path) -> str:
    out = []
    out.append("# PivoxQuant PDF Lint Report")
    out.append("")
    out.append(f"Target: `{target_dir}`")
    out.append("")
    total = sum(len(f) for f in results.values())
    by_sev = defaultdict(int)
    for findings in results.values():
        for f in findings:
            by_sev[f["severity"]] += 1
    out.append(f"**{len(results)} files scanned - {total} findings** "
               f"(P0={by_sev['P0']}, P1={by_sev['P1']}, P2={by_sev['P2']})")
    out.append("")

    out.append("## Summary")
    out.append("")
    out.append("| File | P0 | P1 | P2 |")
    out.append("|---|---:|---:|---:|")
    for fname in sorted(results.keys()):
        c = defaultdict(int)
        for f in results[fname]:
            c[f["severity"]] += 1
        if any(c.values()):
            out.append(f"| `{fname}` | {c['P0']} | {c['P1']} | {c['P2']} |")
    out.append("")

    out.append("## Findings")
    out.append("")
    for fname in sorted(results.keys()):
        findings = results[fname]
        if not findings:
            continue
        findings = sorted(findings, key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"]))
        out.append(f"### `{fname}` — {len(findings)} issues")
        out.append("")
        for f in findings:
            out.append(f"- **[{f['severity']}] {f['rule']}**")
            out.append(f"  - match: `{f['match']}`")
            out.append(f"  - context: `…{f['context']}…`")
            out.append(f"  - hint: {f['hint']}")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Lint PivoxQuant PDFs for placeholder leaks")
    ap.add_argument("path", help="Directory containing PDFs (or a single PDF file)")
    ap.add_argument("--markdown", help="Write a markdown report to this path")
    ap.add_argument("--json", help="Write a JSON report to this path")
    ap.add_argument("--quiet", action="store_true", help="Suppress stdout output")
    args = ap.parse_args()

    target = Path(args.path)
    if target.is_dir():
        pdfs = sorted(target.glob("*.pdf"))
    elif target.is_file() and target.suffix.lower() == ".pdf":
        pdfs = [target]
        target = target.parent
    else:
        sys.stderr.write(f"Not a directory or PDF: {target}\n")
        sys.exit(2)

    if not pdfs:
        sys.stderr.write(f"No PDFs found in {target}\n")
        sys.exit(2)

    results = {pdf.name: lint_file(pdf) for pdf in pdfs}

    if not args.quiet:
        sys.stdout.write(render_text(results, target) + "\n")

    if args.markdown:
        Path(args.markdown).write_text(render_markdown(results, target), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Exit 1 if any P0 was found
    found_p0 = any(f["severity"] == "P0" for findings in results.values() for f in findings)
    sys.exit(1 if found_p0 else 0)


if __name__ == "__main__":
    main()
