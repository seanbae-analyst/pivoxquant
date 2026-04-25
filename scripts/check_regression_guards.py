#!/usr/bin/env python3
"""
Regression Guards — local + CI shim.

Implements the 5 guards specified in feedback_bug_fix_patterns.md §CI
guards 1-6, minus the ones that are better enforced as pytest tests.

Each guard prints violations to stdout and contributes to an overall
exit code. FAIL guards (1, 3-new-direct-fetch, 5) return non-zero on
the first violation; WARN guards (2, 4) print advisories but never
fail the run.

macOS/BSD friendly — pure Python 3, no grep flags. The companion
GitHub Actions workflow at .github/workflows/regression-guards.yml
invokes this same script so developers can reproduce CI results
locally with:

    python3 scripts/check_regression_guards.py

Env vars:
  GUARD_MODE=warn   -> downgrade all FAIL guards to WARN (for rollout)
  GUARD_BASELINE=1  -> print baseline counts and exit 0 (regen baseline)

The baseline file lives at .github/regression-guards-baseline.json and
tracks pre-existing violations that we don't want to block new PRs for.
New violations beyond the baseline count cause CI failure.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / ".github" / "regression-guards-baseline.json"

# Color codes for terminal output — no-op when not a TTY.
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
RED = "\033[31m" if _USE_COLOR else ""
YELLOW = "\033[33m" if _USE_COLOR else ""
GREEN = "\033[32m" if _USE_COLOR else ""
BOLD = "\033[1m" if _USE_COLOR else ""
RESET = "\033[0m" if _USE_COLOR else ""


@dataclass
class Violation:
    path: str
    line: int
    snippet: str


@dataclass
class GuardResult:
    name: str
    level: str  # "FAIL" or "WARN"
    violations: List[Violation] = field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None

    @property
    def count(self) -> int:
        return len(self.violations)


def _walk(root: Path, suffixes: Tuple[str, ...], skip_dirs: Tuple[str, ...] = ()) -> List[Path]:
    """Yield files under *root* with one of *suffixes*, honoring skip_dirs.

    Uses os.walk to avoid pulling in node_modules / __pycache__ / .git etc.
    """
    default_skip = {
        "node_modules",
        "__pycache__",
        ".git",
        ".next",
        "dist",
        "build",
        "backtest_results",
        ".venv",
        "venv",
    }
    skip = default_skip | set(skip_dirs)
    out: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if fn.endswith(suffixes):
                out.append(Path(dirpath) / fn)
    return out


# --------------------------------------------------------------------------- #
# Guard 1 — Deprecated FMP endpoints                                          #
# --------------------------------------------------------------------------- #
# Pattern: literal `api/v3` / `api/v4` appearing in Python code paths under
# services/, routes/, or top-level modules. Comments (lines starting with #)
# and string mentions inside tests are allowed. FMP v3 stopped working
# 2025-08-31, v4 is /stable-only now. See routes/market.py:80 note.

_FMP_V3V4_RE = re.compile(r"financialmodelingprep\.com/api/v[34]|(?<![a-zA-Z0-9_/])api/v[34](?:/|\b)")
_FMP_CODE_DIRS = ("routes", "services", ".")  # "." = top-level .py modules


def guard_1_fmp_deprecated_endpoints() -> GuardResult:
    result = GuardResult(name="G1: deprecated FMP api/v3 or api/v4 endpoint", level="FAIL")
    # Scan all .py under repo, excluding tests/ and docs/.
    for py in _walk(REPO_ROOT, (".py",)):
        rel = py.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("tests/") or rel.startswith("docs/") or rel.startswith("scripts/check_regression_guards"):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            # Strip inline comments for the detection — # starts a comment in Python
            # (good-enough heuristic; strings containing '#' are rare for URL paths).
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # If the `#` appears mid-line, everything after may be comment prose.
            comment_start = None
            in_string = None  # track triple-quoted strings? overkill — plain # split is fine
            for j, ch in enumerate(line):
                if ch in ("'", '"') and (j == 0 or line[j - 1] != "\\"):
                    if in_string == ch:
                        in_string = None
                    elif in_string is None:
                        in_string = ch
                elif ch == "#" and in_string is None:
                    comment_start = j
                    break
            code_part = line[:comment_start] if comment_start is not None else line
            if _FMP_V3V4_RE.search(code_part):
                result.violations.append(Violation(rel, i, line.strip()))
    return result


# --------------------------------------------------------------------------- #
# Guard 2 — weights.sum() zero-guard missing                                  #
# --------------------------------------------------------------------------- #
# Pattern (warning-level): a `/ weights.sum()` (or similar) division
# without a preceding `weights.sum() <= 0` / `== 0` / `!= 0` / `> 0` guard
# in the surrounding 10 lines. False-positive prone, so advisory only.

_DIV_BY_SUM_RE = re.compile(r"/\s*(?:\w+\.)*\b(weights|w|ws|_weights|sub_w)\.sum\(\)")
_SUM_GUARD_RE = re.compile(r"\b(weights|w|ws|_weights|sub_w)\.sum\(\)\s*(?:==|!=|<=|>=|<|>)\s*0")


def guard_2_weights_sum_zero_guard() -> GuardResult:
    result = GuardResult(name="G2: weights.sum() normalization without zero-guard", level="WARN")
    for py in _walk(REPO_ROOT, (".py",)):
        rel = py.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("tests/") or rel.startswith("scripts/"):
            continue
        try:
            lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            if _DIV_BY_SUM_RE.search(line):
                # Look backward up to 15 lines for a zero-guard.
                start = max(0, i - 15)
                context = "\n".join(lines[start : i + 1])
                if _SUM_GUARD_RE.search(context):
                    continue
                # Also accept np.maximum or np.where patterns in same block.
                if re.search(r"np\.maximum\(\s*\w+\s*,\s*1e-", context):
                    continue
                result.violations.append(Violation(rel, i + 1, line.strip()))
    return result


# --------------------------------------------------------------------------- #
# Guard 3 — Frontend .tsx raw fetch() calls (SWR dedup bypass)                #
# --------------------------------------------------------------------------- #
# Pattern: `fetch(` called directly from a component file under
# frontend/src/**/*.tsx. Allowed locations:
#   - frontend/src/lib/**       (api.ts, realtime.tsx — public wrappers)
#   - files containing an explicit opt-out comment:
#       // regression-guards: allow-raw-fetch (<reason>)
# Uses a baseline file so pre-existing call sites don't block new PRs.
# Baseline regenerated by running with GUARD_BASELINE=1.

_FETCH_CALL_RE = re.compile(r"(?<![a-zA-Z0-9_$.])fetch\s*\(")
_ALLOW_RAW_FETCH_RE = re.compile(r"//\s*regression-guards\s*:\s*allow-raw-fetch")


def guard_3_frontend_raw_fetch() -> GuardResult:
    result = GuardResult(name="G3: raw fetch() in frontend/.tsx (prefer apiFetch/useSWR)", level="FAIL")
    tsx_root = REPO_ROOT / "frontend" / "src"
    if not tsx_root.exists():
        result.skipped = True
        result.skip_reason = "frontend/src not present"
        return result
    for tsx in _walk(tsx_root, (".tsx",)):
        rel = tsx.relative_to(REPO_ROOT).as_posix()
        # Public wrapper modules are allowed to call fetch directly.
        if rel.startswith("frontend/src/lib/"):
            continue
        try:
            text = tsx.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        has_opt_out = bool(_ALLOW_RAW_FETCH_RE.search(text))
        if has_opt_out:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            # skip single-line // comments
            if line.lstrip().startswith("//"):
                continue
            if _FETCH_CALL_RE.search(line):
                result.violations.append(Violation(rel, i, line.strip()))
    return result


# --------------------------------------------------------------------------- #
# Guard 4 — US-indices proxy_ticker rendering (advisory)                      #
# --------------------------------------------------------------------------- #
# Pattern (warning): .tsx files that render `IndexQuote.level` or a
# US-indices card (keyed on SP500/NDX/DJI) but never reference
# `proxy_ticker` in their source. Too structural for grep to enforce
# reliably — advisory so the owner reviews manually.

_INDEX_LEVEL_RE = re.compile(r"\b(SP500|NDX|DJI|IndexQuote|BackendIndex)\b")
_LEVEL_RENDER_RE = re.compile(r"\.level\b")


def guard_4_proxy_ticker_rendering() -> GuardResult:
    result = GuardResult(name="G4: US-indices .level render without proxy_ticker reference", level="WARN")
    tsx_root = REPO_ROOT / "frontend" / "src"
    if not tsx_root.exists():
        result.skipped = True
        result.skip_reason = "frontend/src not present"
        return result
    for tsx in _walk(tsx_root, (".tsx", ".ts")):
        rel = tsx.relative_to(REPO_ROOT).as_posix()
        try:
            text = tsx.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _INDEX_LEVEL_RE.search(text):
            continue
        if not _LEVEL_RENDER_RE.search(text):
            continue
        if "proxy_ticker" in text:
            continue
        # Heuristic: report first .level line so humans have a jump point.
        for i, line in enumerate(text.splitlines(), start=1):
            if _LEVEL_RENDER_RE.search(line):
                result.violations.append(Violation(rel, i, line.strip()))
                break
    return result


# --------------------------------------------------------------------------- #
# Guard 5 — price_display without parse_price_display fallback                #
# --------------------------------------------------------------------------- #
# Pattern: a file under routes/ or services/ reads `price_display`
# (producer or consumer) but never imports/uses `parse_price_display`.
# Producers writing the field are fine; consumers that return
# `price: 0` without a display parse are the regression. Heuristic —
# we flag the file as WARN and let the human inspect.

_PRICE_DISPLAY_RE = re.compile(r"\bprice_display\b")


def guard_5_price_display_fallback() -> GuardResult:
    result = GuardResult(name="G5: price_display read without parse_price_display fallback", level="WARN")
    for py in _walk(REPO_ROOT, (".py",)):
        rel = py.relative_to(REPO_ROOT).as_posix()
        if not (rel.startswith("routes/") or rel.startswith("services/")):
            continue
        if rel == "services/price_overlay.py":
            continue  # the helper itself
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _PRICE_DISPLAY_RE.search(text):
            continue
        if "parse_price_display" in text:
            continue
        # Flag first price_display reference.
        for i, line in enumerate(text.splitlines(), start=1):
            if _PRICE_DISPLAY_RE.search(line):
                result.violations.append(Violation(rel, i, line.strip()))
                break
    return result


# --------------------------------------------------------------------------- #
# Baseline handling                                                            #
# --------------------------------------------------------------------------- #
def load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def write_baseline(results: List[GuardResult]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    baseline = {r.name: r.count for r in results}
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def _print_result(r: GuardResult, baseline_count: int) -> Tuple[int, int]:
    """Return (fail_count_beyond_baseline, warn_count)."""
    if r.skipped:
        print(f"{YELLOW}SKIP{RESET}  {r.name}  — {r.skip_reason}")
        return 0, 0
    new_violations = max(0, r.count - baseline_count)
    color = GREEN if r.count == 0 else (RED if r.level == "FAIL" and new_violations > 0 else YELLOW)
    header = f"{color}{r.level}{RESET} " if r.count > 0 else f"{GREEN}OK{RESET}   "
    suffix = ""
    if baseline_count > 0:
        suffix = f"  (baseline: {baseline_count}; new: {new_violations})"
    print(f"{header} {r.name}  [{r.count} violation(s)]{suffix}")
    if r.count > 0:
        # Show at most 20 lines to keep CI logs sane.
        for v in r.violations[:20]:
            print(f"       {v.path}:{v.line}: {v.snippet[:160]}")
        if r.count > 20:
            print(f"       ... and {r.count - 20} more")
    if r.level == "FAIL":
        return new_violations, 0
    return 0, r.count


def main() -> int:
    mode = os.environ.get("GUARD_MODE", "enforce").lower()
    regen_baseline = os.environ.get("GUARD_BASELINE") == "1"

    print(f"{BOLD}PivoxQuant Regression Guards{RESET}  (mode={mode}, baseline-regen={regen_baseline})")
    print(f"Repo root: {REPO_ROOT}")
    print("")

    guards = [
        guard_1_fmp_deprecated_endpoints,
        guard_2_weights_sum_zero_guard,
        guard_3_frontend_raw_fetch,
        guard_4_proxy_ticker_rendering,
        guard_5_price_display_fallback,
    ]
    results = [g() for g in guards]

    if regen_baseline:
        write_baseline(results)
        print(f"\n{GREEN}Baseline written to {BASELINE_PATH.relative_to(REPO_ROOT)}{RESET}")
        for r in results:
            print(f"  {r.name}: {r.count}")
        return 0

    baseline = load_baseline()
    total_fail = 0
    total_warn = 0
    for r in results:
        bc = int(baseline.get(r.name, 0))
        f, w = _print_result(r, bc)
        total_fail += f
        total_warn += w

    print("")
    if total_warn > 0:
        print(f"{YELLOW}{total_warn} warning(s) — advisory only.{RESET}")
    if total_fail > 0 and mode != "warn":
        print(f"{RED}{BOLD}{total_fail} NEW violation(s) beyond baseline — FAIL{RESET}")
        print("Fix the new violations, or regenerate the baseline if they are intentional:")
        print("   GUARD_BASELINE=1 python3 scripts/check_regression_guards.py")
        return 1
    if total_fail > 0:
        print(f"{YELLOW}{total_fail} new violation(s) — downgraded to warning (GUARD_MODE=warn){RESET}")
    print(f"{GREEN}{BOLD}All regression guards passed.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
