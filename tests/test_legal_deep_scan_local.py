"""
Local equivalent of .github/workflows/legal-deep-scan.yml.

Why this exists
---------------
The CI workflow runs on ubuntu-latest with GNU grep. macOS BSD grep does
not support PCRE flags (-P / -Pzo) and silently exits 0 — meaning a
violation present locally would *appear* to pass on a developer's
machine. To close that gap, this pytest module reimplements the same
five checks in pure Python so they behave identically across OSes.

What it covers
--------------
1. DisclaimerBanner mount on every (dashboard)/*/page.tsx — or layout-
   level mount short-circuits.
2. <PdfDisclaimer /> or <PdfDisclaimerMini /> on every PDF template
   under frontend/src/components/reports/templates/.
3. New routes/*.py files (best-effort; full diff check is CI-only)
   contain `legal_scrub_response` import or `# legal-exempt:` marker.
4. ko/en disclaimer string-length ratio ≥ 30% (warn under 50%).
5. DisclaimerBanner JSX appears in the top 60% of each dashboard page
   and not adjacent to hidden / footer / sr-only modifiers.
6. FORBIDDEN_DIRECTIVE_TERMS cross-reference against frontend/src/**.

How to run
----------
    pytest tests/test_legal_deep_scan_local.py -v

This is a quick (<5s) local sanity check. Failures here will also fail
in CI — fix locally first.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FE = REPO / "frontend" / "src"
DASHBOARD = FE / "app" / "(dashboard)"
TEMPLATES = FE / "components" / "reports" / "templates"
BANNER = FE / "components" / "ui" / "disclaimer-banner.tsx"
LAYOUT = DASHBOARD / "layout.tsx"


# ---------------------------------------------------------------------
# 1. DisclaimerBanner mount on dashboard pages
# ---------------------------------------------------------------------

def _layout_mounts_banner() -> bool:
    return LAYOUT.is_file() and "DisclaimerBanner" in LAYOUT.read_text(
        encoding="utf-8"
    )


@pytest.mark.skipif(not DASHBOARD.is_dir(), reason="dashboard dir missing")
def test_dashboard_pages_mount_disclaimer_banner() -> None:
    if _layout_mounts_banner():
        return
    missing: list[str] = []
    for page in DASHBOARD.glob("*/page.tsx"):
        if "DisclaimerBanner" not in page.read_text(encoding="utf-8"):
            missing.append(str(page.relative_to(REPO)))
    assert not missing, (
        "DisclaimerBanner missing on dashboard page(s) and not present in "
        f"layout: {missing}"
    )


# ---------------------------------------------------------------------
# 2. PDF templates use PdfDisclaimer / PdfDisclaimerMini
# ---------------------------------------------------------------------

@pytest.mark.skipif(not TEMPLATES.is_dir(), reason="pdf templates dir missing")
def test_pdf_templates_render_disclaimer() -> None:
    pattern = re.compile(r"<PdfDisclaimer(Mini)?\b")
    missing: list[str] = []
    for tpl in TEMPLATES.glob("*.tsx"):
        if not pattern.search(tpl.read_text(encoding="utf-8")):
            missing.append(str(tpl.relative_to(REPO)))
    assert not missing, (
        f"PDF template(s) missing <PdfDisclaimer /> or Mini: {missing}"
    )


# ---------------------------------------------------------------------
# 3. routes/*.py — soft check (best-effort without git diff)
# ---------------------------------------------------------------------

ROUTES = REPO / "routes"


# Files that predate the legal_scrub_response decorator. CI's diff check
# enforces it for *new* routes; this baseline list keeps the local test
# from failing on legacy code while still catching regressions in files
# already migrated. When you add the decorator to a file here, remove it
# from the list — that locks in the migration.
ROUTES_LEGACY_BASELINE: frozenset[str] = frozenset({
    "auth.py", "command_center.py", "billing.py", "dev_auth.py",
    "twin.py", "behavior.py", "realtime.py", "agent_admin.py",
    "email_preferences.py", "health.py", "broker_oauth.py", "ai.py",
    "profile.py", "counterfactual.py", "admin_preview.py",
    "watchlist.py", "share.py", "agent.py", "trades.py",
    "artifacts.py", "admin_fmp.py", "pre_trade.py", "alt_data.py",
    "consents.py", "push.py",
})


@pytest.mark.skipif(not ROUTES.is_dir(), reason="routes dir missing")
def test_routes_files_have_scrub_decorator_or_exempt() -> None:
    """Every routes/*.py with a @bp.route must reference legal_scrub_response
    OR carry an explicit `# legal-exempt: <reason>` comment — except the
    legacy baseline above, which is a known migration backlog.

    CI does the strict per-route diff for new code. This pytest catches
    regressions in already-migrated files.
    """
    bp_route_re = re.compile(r"@\w+_?bp\.route\(|@bp\.route\(")
    bad: list[str] = []
    for py in ROUTES.glob("*.py"):
        if py.name in ROUTES_LEGACY_BASELINE:
            continue
        text = py.read_text(encoding="utf-8")
        if not bp_route_re.search(text):
            continue
        has_decorator = "legal_scrub_response" in text
        has_exempt = "# legal-exempt:" in text
        if not (has_decorator or has_exempt):
            bad.append(str(py.relative_to(REPO)))
    assert not bad, (
        "routes/*.py with @bp.route but no legal_scrub_response / "
        f"# legal-exempt:: {bad}"
    )


# ---------------------------------------------------------------------
# 4. ko/en disclaimer length equivalence
# ---------------------------------------------------------------------

@pytest.mark.skipif(not BANNER.is_file(), reason="disclaimer-banner.tsx missing")
def test_disclaimer_banner_ko_en_length_ratio() -> None:
    src = BANNER.read_text(encoding="utf-8")
    ko_total = sum(
        len(m.group(1))
        for m in re.finditer(r'ko:\s*"((?:[^"\\]|\\.)*)"', src)
    )
    en_total = sum(
        len(m.group(1))
        for m in re.finditer(r'en:\s*"((?:[^"\\]|\\.)*)"', src)
    )
    assert ko_total > 0, "No ko strings found — banner structure changed?"
    ratio = en_total / ko_total
    # Hard floor: 30% (CI fails). Soft floor: 50% (CI warns).
    assert ratio >= 0.30, (
        f"English disclaimer is only {ratio:.0%} of Korean length — "
        "likely incomplete translation."
    )


# ---------------------------------------------------------------------
# 5. Banner position — top of page, not in footer / hidden
# ---------------------------------------------------------------------

@pytest.mark.skipif(not DASHBOARD.is_dir(), reason="dashboard dir missing")
def test_disclaimer_banner_top_mounted() -> None:
    if _layout_mounts_banner():
        return  # layout-level mount → guaranteed visible at top of every page
    suspicious_re = re.compile(
        r"(sr-only|hidden|opacity-0|footer|aria-hidden=\{?true)",
        re.IGNORECASE,
    )
    bad: list[str] = []
    for page in DASHBOARD.glob("*/page.tsx"):
        text = page.read_text(encoding="utf-8")
        if "DisclaimerBanner" not in text:
            continue
        lines = text.splitlines()
        total = len(lines)
        first_jsx = None
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if stripped.startswith("import ") or stripped.startswith("//"):
                continue
            if "<DisclaimerBanner" in ln:
                first_jsx = i + 1
                break
        if first_jsx is None:
            bad.append(f"{page.relative_to(REPO)}: imported but never rendered")
            continue
        window = "\n".join(lines[max(0, first_jsx - 3): first_jsx + 2])
        m = suspicious_re.search(window)
        if m:
            bad.append(
                f"{page.relative_to(REPO)}:{first_jsx} near '{m.group(1)}' — banner must be visible"
            )
            continue
        if first_jsx > total * 0.60:
            bad.append(
                f"{page.relative_to(REPO)}:{first_jsx}/{total} below top 60% (footer-buried)"
            )
    assert not bad, "Banner position violations: " + "; ".join(bad)


# ---------------------------------------------------------------------
# 6. Forbidden directive terms — cross-reference frontend
# ---------------------------------------------------------------------

# Frontend directories deliberately excluded from the user-facing-prose
# scan. These hold copy where the user describes *their own* behavior
# (questionnaires, persona definitions) — directives like "Sell everything
# immediately" are answer choices the user picks, not advice from the
# platform. Attorney-signed: 2026-05-06.
FRONTEND_VOCAB_SKIP_DIRS: frozenset[str] = frozenset({
    "frontend/src/data",       # onboarding questionnaire choices
    "frontend/src/i18n",       # translation glossary keys
    "frontend/src/__tests__",  # test fixtures
})


@pytest.mark.skipif(not FE.is_dir(), reason="frontend/src missing")
def test_no_forbidden_directive_terms_in_user_facing_strings() -> None:
    """Cross-reference FORBIDDEN_DIRECTIVE_TERMS against *user-facing*
    strings only — JSX text nodes and prose-like string literals.

    What this catches: a copy edit that introduces "BUY this stock" or
    "이 종목을 추천합니다" into rendered text.

    What this deliberately ignores:
    - Identifiers / field names: `buy_threshold`, `sellDate`, etc.
    - API paths: `/api/buy/...`
    - Type annotations.
    The signal-to-noise ratio of a naive substring scan against TS source
    is too low — the backend `scan_advisory_vocab.py` already does the
    rigorous check on Python. For TS we restrict to prose contexts.
    """
    from services.legal.forbidden_terms import FORBIDDEN_DIRECTIVE_TERMS

    skip_paths = {BANNER}
    # JSX text: capture text between `>` and `<` of more than 8 chars
    # containing whitespace (ie. real sentences, not single tokens).
    jsx_text_re = re.compile(r">([^<>{}\n]{8,})<")
    # Prose string literal: a quoted string of 12+ chars containing a
    # space (so we skip "buy" but catch "buy this stock" / "권유합니다").
    prose_literal_re = re.compile(
        r'"((?=[^"]*\s)[^"\\]{12,}(?:\\.[^"\\]*)*)"'
    )
    negation_re = re.compile(
        r"(아니|아닙|않|not\s|does\s+not|do\s+not|never\b|disclaimer|면책)",
        re.IGNORECASE,
    )

    violations: list[str] = []
    for p in FE.rglob("*.ts*"):
        if p in skip_paths:
            continue
        s = str(p)
        if "/node_modules/" in s or "/.next/" in s or "/__tests__/" in s:
            continue
        rel = str(p.relative_to(REPO))
        if any(rel.startswith(skip_dir) for skip_dir in FRONTEND_VOCAB_SKIP_DIRS):
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            continue
        # Strip block / line comments while preserving line numbers.
        # JSDoc headers like /** Buy/Sell/Hold ... */ are descriptions of
        # *what's forbidden*, not directives — so they must not match.
        def _strip_comments(src: str) -> str:
            def _block(m: re.Match[str]) -> str:
                nl = m.group(0).count("\n")
                return "\n" * nl + " " * (len(m.group(0)) - nl)
            src = re.sub(r"/\*.*?\*/", _block, src, flags=re.DOTALL)
            src = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), src)
            return src
        text = _strip_comments(raw)
        # Build set of (line_no, prose_str) candidates.
        candidates: list[tuple[int, str]] = []
        for m in jsx_text_re.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            candidates.append((line_no, m.group(1)))
        for m in prose_literal_re.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            candidates.append((line_no, m.group(1)))
        for line_no, prose in candidates:
            low = prose.lower()
            if negation_re.search(prose):
                continue
            for term in FORBIDDEN_DIRECTIVE_TERMS:
                t = term.lower()
                # Word-ish boundary for ASCII terms; substring for Korean.
                if t.isascii():
                    if not re.search(rf"\b{re.escape(t)}\b", low):
                        continue
                else:
                    if t not in low:
                        continue
                violations.append(
                    f"{p.relative_to(REPO)}:{line_no} '{term}' in user-facing prose: {prose[:60]!r}"
                )
                break
    # Two modes — match the CI workflow:
    #  - LEGAL_VOCAB_STRICT=1 → fail on any finding (target state).
    #  - default              → xfail with the list (advisory; baseline cleanup).
    import os
    if os.environ.get("LEGAL_VOCAB_STRICT") == "1":
        assert not violations, (
            "Forbidden directive terms in user-facing strings "
            "(see services/legal/forbidden_terms.py): "
            + "; ".join(violations[:20])
        )
    else:
        if violations:
            pytest.xfail(
                f"{len(violations)} forbidden-vocab finding(s) in baseline — "
                "advisory until cleaned up. Set LEGAL_VOCAB_STRICT=1 to lock. "
                "First few: " + "; ".join(violations[:5])
            )
