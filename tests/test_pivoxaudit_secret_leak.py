"""Regression guard: no `pivoxaudit\\d*` beta-password literal in repo
files (md / ts / tsx / py / yml / yaml).

Background
----------
2026-04-19 — original `pivoxaudit` beta password leaked to a public
GitHub commit; CEO rotated to `pivoxaudit2`.
2026-05-10 — HANDOVER.md leaked the rotated value `pivoxaudit2` in
plaintext.  CEO direction (memory MEMORY.md): the literal value lives
only in Vercel env (prod) + `.env.local` (dev).  Anywhere it appears
in the tracked repo is an immediate rotate-and-leak event.

CI defence already exists in `.github/workflows/legal-guard.yml` (the
"Block beta password leak in repo" step).  This pytest mirrors that
defence so:

* Local devs catch the regression pre-push (CI-only is too late once
  the leaked branch is on the remote).
* The defence runs cross-platform — the CI step uses GNU `grep -rEn`
  which works on ubuntu but produces silent failures on macOS BSD
  grep when shell-quoted differently.

Detection
---------
Walks the repo (rooted at this file's parent's parent) and flags any
file matching:

* extension in {md, ts, tsx, py, yml, yaml}, AND
* file content contains the regex `pivoxaudit\\d*`,
* EXCEPT the self-referencing CI workflow (which contains the regex
  literal by design) and tests/ (this file plus any future tests).

Exclusions (mirror the CI step)
-------------------------------
* `.git/`
* `.claude/` (private session memory)
* `node_modules/`
* `venv/` (local Python env)
* `.next/` (Next.js build)
* `__pycache__/`
* `.github/workflows/legal-guard.yml` — owns the self-referencing
  regex literal.
* `tests/test_pivoxaudit_secret_leak.py` — this file (the regex literal
  must appear here as the test body).

Aligned rule: 정통망법 §28 (개인정보 안전조치) + memory/feedback rotate
discipline.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

SCANNED_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".ts", ".tsx", ".py", ".yml", ".yaml"}
)

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".claude",
        "node_modules",
        "venv",
        ".next",
        "__pycache__",
        ".pytest_cache",
        "test-results",
        "self_healing_artifacts",
        "legal_monitor_artifacts",
        "agent_worker",  # archived agent runs
    }
)

# Files allowed to contain the regex literal as part of their guard
# implementation. Stored as repo-relative POSIX paths.
ALLOWED_SELF_REFERENCES: frozenset[str] = frozenset(
    {
        ".github/workflows/legal-guard.yml",
        "tests/test_pivoxaudit_secret_leak.py",
    }
)

# Forbidden literal — `pivoxaudit` followed by zero or more digits, bounded
# by word breaks at both ends.  The `\b...\b` boundaries are the W7.3
# narrowing (2026-05-11): the unbounded version self-matched this file's
# name and every HANDOVER/PR bullet describing the guard, forcing six
# rounds of cosmetic sanitization.  With word boundaries the regex catches
# `pivoxaudit` / `pivoxaudit2` / `pivoxaudit42` as bare tokens but leaves
# `test_pivoxaudit_secret_leak`, `TestNoPivoxauditSecretLeak`, and
# `pivoxaudit_legacy` alone (Python regex treats `_` as a word char, so no
# boundary fires between `t` and `_`).  Case-sensitive — real beta password
# was lowercase.
LEAK_RE = re.compile(r"\bpivoxaudit\d*\b")


def _iter_scanned_files() -> list[Path]:
    """Walk the repo and yield every file whose extension is in
    SCANNED_EXTENSIONS, pruning excluded directories at the OS level
    (Wave G fix, 2026-05-13). The previous ``Path.rglob('*')`` walked
    every file in the tree before filtering — with frontend/.next at
    ~4 GB and frontend/node_modules at ~800 MB on a real dev machine
    that took long enough to hang pytest collection (observed during
    the v40 cycle's full pytest run, 64% completion before stall).

    ``os.walk`` accepts in-place mutation of ``dirnames`` to prune the
    descent, so excluded directories aren't entered at all. Identical
    final file list, ~50–100× faster on a real checkout.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        # In-place prune: avoids descending into node_modules / .next
        # / .git / .claude entirely. Must be a slice assignment.
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames:
            if Path(name).suffix.lower() not in SCANNED_EXTENSIONS:
                continue
            found.append(Path(dirpath) / name)
    return found


def _is_allowed(rel_posix: str) -> bool:
    return rel_posix in ALLOWED_SELF_REFERENCES


class TestNoPivoxauditSecretLeak:
    """Block any `pivoxaudit\\d*` literal landing in tracked repo files
    other than the two audited self-reference points."""

    def test_no_beta_password_literal_in_repo(self) -> None:
        offenders: list[str] = []
        for path in _iter_scanned_files():
            rel_posix = path.relative_to(REPO_ROOT).as_posix()
            if _is_allowed(rel_posix):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if LEAK_RE.search(line):
                    offenders.append(
                        f"{rel_posix}:{lineno}: {line.strip()[:120]}"
                    )
        assert not offenders, (
            "Beta password literal `pivoxaudit\\d*` leaked in repo file. "
            "The literal value must live only in Vercel env (prod) and "
            ".env.local (dev). Rotate the value in Vercel + Railway, "
            "purge the file, and force-push the cleaned history.\n\n"
            + "\n".join(offenders)
        )


class TestScanCoverage:
    """Defensive: ensure the scan walked something."""

    def test_scan_covers_expected_files(self) -> None:
        files = _iter_scanned_files()
        # Repo has hundreds of .md / .py / .ts files; <50 means the
        # walk broke (e.g. `EXCLUDED_DIRS` swallowed too much).
        assert len(files) >= 50, (
            f"file scan unexpectedly sparse: {len(files)} files. "
            "Check EXCLUDED_DIRS and SCANNED_EXTENSIONS."
        )


class TestRegexThreatModel:
    """W7.3 — verify narrowed regex against catch + skip threat model.

    Build the bare-token prefix at runtime so this test file itself does
    not embed greppable literals.
    """

    _PREFIX = "pivox" + "audit"

    def test_catch_bare_token(self) -> None:
        assert LEAK_RE.search(self._PREFIX) is not None

    def test_catch_bare_token_with_suffix_digit(self) -> None:
        assert LEAK_RE.search(self._PREFIX + "2") is not None

    def test_catch_in_password_context(self) -> None:
        line = f"BETA_PASSWORD={self._PREFIX}2"
        assert LEAK_RE.search(line) is not None

    def test_catch_in_markdown_quote(self) -> None:
        line = f"v34 BETA_PASSWORD was `{self._PREFIX}2`"
        assert LEAK_RE.search(line) is not None

    def test_skip_underscored_identifier(self) -> None:
        line = f"tests/test_{self._PREFIX}_secret_leak.py"
        assert LEAK_RE.search(line) is None

    def test_skip_camelcase_class_name(self) -> None:
        line = "class TestNoPivoxauditSecretLeak:"
        assert LEAK_RE.search(line) is None

    def test_skip_legacy_underscore_suffix(self) -> None:
        line = f"{self._PREFIX}_legacy"
        assert LEAK_RE.search(line) is None

    def test_skip_redacted_marker(self) -> None:
        line = "history reference: [REDACTED:ex-beta-pw-v1]"
        assert LEAK_RE.search(line) is None

    def test_skip_capitalized(self) -> None:
        line = "Pivoxaudit"
        assert LEAK_RE.search(line) is None

    def test_skip_substring_in_word(self) -> None:
        line = self._PREFIX + "foo"
        assert LEAK_RE.search(line) is None
