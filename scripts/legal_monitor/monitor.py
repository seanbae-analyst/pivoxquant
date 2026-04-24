#!/usr/bin/env python3
"""Daily legal-risk monitor (10:00 KST).

Complements (does NOT duplicate) `.github/workflows/daily-legal-scan.yml`:
- daily-legal-scan: grep forbidden tokens in production sources + pytest
- THIS monitor: deeper inspection:
    a) Canonical blocklist drift — diff the live code vs
       `services/legal/forbidden_terms.py::FORBIDDEN_DIRECTIVE_TERMS`.
    b) Artifact sample verification — samples/artifacts/*.html +
       samples/pdf/*.pdf scanned for forbidden phrases.
    c) AI output path coverage — confirm every artifact service calls
       `safe_scrub` or `scrub_text` before returning user-visible text.
    d) Optional: runtime DB content scan via admin endpoint (skipped
       unless DB_SCAN_URL + DB_SCAN_TOKEN set).

Outputs
-------
* `legal_monitor_artifacts/report.md` — human-readable summary
* `legal_monitor_artifacts/summary.json` — `{severity, total, findings}`

Severity map (consumed by the GH workflow):
* critical: forbidden phrase found in a PUBLIC artifact/PDF
* high:     AI output service missing a scrub call
* medium:   new code term drift
* none:     clean

Regulatory RSS (KOFIA / FSC) is OUT OF SCOPE for this script — tracked in
`docs/AUTONOMOUS_OPS.md` as a deferred item.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(os.environ.get(
    "LEGAL_MONITOR_OUT", ROOT / "legal_monitor_artifacts"
))
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Load canonical forbidden terms ------------------------------------
sys.path.insert(0, str(ROOT))
try:
    from services.legal.forbidden_terms import FORBIDDEN_DIRECTIVE_TERMS  # type: ignore
except Exception as e:  # pragma: no cover — defensive
    print(f"[legal_monitor] failed to import forbidden_terms: {e}", file=sys.stderr)
    FORBIDDEN_DIRECTIVE_TERMS = frozenset()

# Artifact services that assemble user-visible AI/output text. Each MUST
# call scrub_text / safe_scrub before returning. Missing calls = high.
EXPECTED_SCRUB_CALLERS = (
    "services/artifacts/weekly_memo_service.py",
    "services/artifacts/brag_card_service.py",
    "services/artifacts/earnings_prebrief_service.py",
    "services/artifacts/risk_board_service.py",
    "services/artifacts/monthly_finance_service.py",
    "services/artifacts/year_end_letter_service.py",
    "services/artifacts/quarterly_self_report_service.py",
    "services/artifacts/dividend_income_service.py",
    "services/ai_service.py",
    "ai_service.py",
    "services/morning_brief_service.py",
    "services/alert_service.py",
)


def _scan_text_for_terms(text: str, terms: set[str]) -> list[str]:
    """Return list of terms found in text.

    - Hangul terms: substring match (matches the canonical behaviour in
      ``services/legal/forbidden_terms.py::contains_forbidden_term``).
    - ASCII terms: **word-boundary** match (case-insensitive). This is
      intentionally stricter than the canonical substring check because
      sample HTML copy contains legitimate connective text like
      ``"holder"``, ``"buying guide"``, ``"advice is not provided"`` —
      subword substring matches create alert fatigue. A directive
      violation requires the bare token as a word.
    """
    hits: list[str] = []
    for term in terms:
        if any(ord(c) > 127 for c in term):
            if term in text:
                hits.append(term)
        else:
            # Word boundary, case-insensitive
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                hits.append(term)
    return hits


# Sample-scan policy: the canonical blocklist is substring-matched and
# tuned for narrow assertion call-sites inside services. Running it on
# full HTML narrative creates too many false positives (e.g. "8-day
# hold", "holder", "buyback", "advisor-like signals"). For artifact
# sample scanning we narrow to the DIRECTIVE-UNAMBIGUOUS subset:
# - All Hangul terms (directive triggers under 자본시장법)
# - English COMPOUND directives (multi-word, unambiguous)
# - Bare English words are NOT scanned at the sample level — those are
#   caught upstream by ``tests/test_no_hardcoded_samples.py`` and
#   ``services/legal_filter.py``.
def _directive_only(terms: set[str]) -> set[str]:
    keep: set[str] = set()
    for t in terms:
        if any(ord(c) > 127 for c in t):
            keep.add(t)
        elif " " in t:
            keep.add(t)
    return keep


# Negation markers — when a forbidden term appears in a sentence that
# ALSO contains one of these, it is almost certainly a legal-safe
# disclaimer ("does not recommend buying or selling"). Used by the
# sample scanners to suppress false positives on the standard
# disclaimer block that every sample embeds.
NEGATION_MARKERS = (
    # Korean disclaimer patterns
    "권유하지 않",
    "권유가 아",
    "추천하지 않",
    "추천이 아",
    "제공하지 않",
    "아닙니다",
    "않습니다",
    "인가를 받지 않",
    "투자자문업",
    # English disclaimer patterns
    "not investment advice",
    "not a recommendation",
    "does not recommend",
    "is not a solicitation",
    "informational only",
    "informational purpose",
    "disclaimer",
    # Generic markers
    "금지",
    "면책",
    "no recommend",
)


def _sentence_window(text: str, idx: int, span: int = 280) -> str:
    lo = max(0, idx - span)
    hi = min(len(text), idx + span)
    return text[lo:hi]


def _hit_with_negation_filter(text: str, terms: set[str]) -> list[str]:
    """Like ``_scan_text_for_terms`` but drops a hit when the surrounding
    ±120-char window contains a negation marker."""
    hits: list[str] = []
    lowered_full = text.lower()
    for term in terms:
        if any(ord(c) > 127 for c in term):
            # Hangul substring
            pos = text.find(term)
            while pos != -1:
                window = _sentence_window(text, pos).lower()
                if not any(m.lower() in window for m in NEGATION_MARKERS):
                    hits.append(term)
                    break   # one match per term is enough for reporting
                pos = text.find(term, pos + 1)
        else:
            # ASCII word-boundary + negation window
            for m in re.finditer(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE):
                window = _sentence_window(text, m.start()).lower()
                if not any(mk.lower() in window for mk in NEGATION_MARKERS):
                    hits.append(term)
                    break
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# --- (a) Sample artifact HTML scan -------------------------------------
def scan_artifact_samples() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    sample_dir = ROOT / "samples" / "artifacts"
    if not sample_dir.exists():
        return findings
    terms = _directive_only(set(FORBIDDEN_DIRECTIVE_TERMS))
    for html in sorted(sample_dir.glob("*.html")):
        try:
            text = html.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Strip HTML tags coarsely — terms are substrings either way but
        # this keeps reported context human-readable.
        plain = re.sub(r"<[^>]+>", " ", text)
        plain = re.sub(r"\s+", " ", plain)
        hits = _hit_with_negation_filter(plain, terms)
        if hits:
            findings.append({
                "severity": "critical",
                "kind": "artifact_sample",
                "path": str(html.relative_to(ROOT)),
                "terms": sorted(set(hits)),
            })
    return findings


# --- (b) Sample PDF scan (needs pdftotext) -----------------------------
def scan_pdf_samples() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    sample_dir = ROOT / "samples" / "pdf"
    if not sample_dir.exists():
        return findings
    if not shutil.which("pdftotext"):
        findings.append({
            "severity": "medium",
            "kind": "tooling_missing",
            "path": "samples/pdf/",
            "terms": ["pdftotext not installed — PDF scan skipped"],
        })
        return findings
    terms = _directive_only(set(FORBIDDEN_DIRECTIVE_TERMS))
    for pdf in sorted(sample_dir.glob("*.pdf")):
        try:
            res = subprocess.run(
                ["pdftotext", "-layout", str(pdf), "-"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            text = res.stdout
        except Exception as e:
            findings.append({
                "severity": "medium",
                "kind": "pdf_extract_failed",
                "path": str(pdf.relative_to(ROOT)),
                "terms": [str(e)],
            })
            continue
        hits = _hit_with_negation_filter(text, terms)
        if hits:
            findings.append({
                "severity": "critical",
                "kind": "pdf_sample",
                "path": str(pdf.relative_to(ROOT)),
                "terms": sorted(set(hits)),
            })
    return findings


# --- (c) Scrub-coverage audit ------------------------------------------
def audit_scrub_coverage() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for rel in EXPECTED_SCRUB_CALLERS:
        p = ROOT / rel
        if not p.exists():
            # Not every service file exists in every checkout — skip
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if ("scrub_text" not in src) and ("safe_scrub" not in src) and ("scrub_signal" not in src):
            findings.append({
                "severity": "high",
                "kind": "missing_scrub",
                "path": rel,
                "terms": [
                    "No call to scrub_text / safe_scrub / scrub_signal found. "
                    "AI-generated output from this service may bypass the legal scrubber."
                ],
            })
    return findings


# --- (d) New forbidden-token drift in production sources ---------------
def scan_drift_in_sources() -> list[dict[str, Any]]:
    """Scan production paths for any canonical term that is NOT already
    guarded by a negation. This is a drift detector: the daily-legal-scan
    workflow uses a small hardcoded set, but this checks the FULL canonical
    list."""
    findings: list[dict[str, Any]] = []
    # Same narrowing rationale as the sample scan: bare English verbs
    # appear legitimately in source (e.g. `buy_button`, `sell_modal`).
    # The daily-legal-scan workflow already handles bare-word regression
    # with its curated EN set; the monitor focuses on directive forms.
    terms = _directive_only(set(FORBIDDEN_DIRECTIVE_TERMS))
    scan_paths = ("routes", "services", "frontend/src")
    for term in sorted(terms):
        # Skip very short / ambiguous tokens (e.g., single Hangul chars)
        if len(term) < 2:
            continue
        pattern = re.escape(term)
        hits: list[str] = []
        for top in scan_paths:
            base = ROOT / top
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if p.suffix not in (".py", ".ts", ".tsx", ".md"):
                    continue
                if "__pycache__" in p.parts:
                    continue
                # Skip the canonical file itself + known scrubber/test files
                rel = str(p.relative_to(ROOT))
                if rel in (
                    "services/legal/forbidden_terms.py",
                    "services/legal_filter.py",
                ):
                    continue
                if "/tests/" in rel or rel.startswith("tests/"):
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for idx, line in enumerate(text.splitlines(), start=1):
                    if re.search(pattern, line, re.IGNORECASE):
                        # Reject if the line also contains a negation marker
                        if re.search(
                            r"(금지|없음|않습|안\s*합|하지\s*않|not\s+|no\s+|never\s+|disclaimer)",
                            line, re.IGNORECASE,
                        ):
                            continue
                        hits.append(f"{rel}:{idx}: {line.strip()[:120]}")
                        if len(hits) >= 5:
                            break
                if len(hits) >= 5:
                    break
        if hits:
            findings.append({
                "severity": "medium",
                "kind": "source_drift",
                "path": "routes/|services/|frontend/src/",
                "term": term,
                "terms": hits,
            })
    return findings


# --- (e) Optional runtime DB scan --------------------------------------
def scan_runtime_db() -> list[dict[str, Any]]:
    url = os.environ.get("DB_SCAN_URL")
    token = os.environ.get("DB_SCAN_TOKEN")
    if not url or not token:
        return []
    import urllib.request
    import urllib.error
    findings: list[dict[str, Any]] = []
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        findings.append({
            "severity": "medium",
            "kind": "runtime_scan_failed",
            "path": url,
            "terms": [str(e)],
        })
        return findings
    hits = data.get("hits", [])
    if hits:
        findings.append({
            "severity": "critical",
            "kind": "runtime_db",
            "path": url,
            "terms": hits[:10],
        })
    return findings


SEV_RANK = {"critical": 3, "high": 2, "medium": 1, "none": 0}


def rollup(findings: list[dict[str, Any]]) -> str:
    best = "none"
    for f in findings:
        s = f.get("severity", "none")
        if SEV_RANK.get(s, 0) > SEV_RANK.get(best, 0):
            best = s
    return best


def render_report(findings: list[dict[str, Any]], severity: str) -> str:
    lines = [
        f"# Legal Risk Monitor — {severity.upper()}",
        "",
        f"Total findings: **{len(findings)}**",
        "",
    ]
    if not findings:
        lines.append("All checks passed.")
        return "\n".join(lines)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for f in findings:
        by_kind.setdefault(f["kind"], []).append(f)
    for kind, items in by_kind.items():
        lines.append(f"## {kind} ({len(items)})")
        for it in items:
            lines.append(f"- **{it['severity']}** — `{it.get('path', '?')}`")
            for t in it.get("terms", [])[:5]:
                lines.append(f"  - {t}")
        lines.append("")
    lines.append("---")
    lines.append("_Generated by `scripts/legal_monitor/monitor.py`._")
    return "\n".join(lines)


def main() -> int:
    findings: list[dict[str, Any]] = []
    findings.extend(scan_artifact_samples())
    findings.extend(scan_pdf_samples())
    findings.extend(audit_scrub_coverage())
    findings.extend(scan_drift_in_sources())
    findings.extend(scan_runtime_db())

    severity = rollup(findings)
    report = render_report(findings, severity)
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps({
        "severity": severity,
        "total": len(findings),
        "findings": findings,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[legal_monitor] severity={severity} total={len(findings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
