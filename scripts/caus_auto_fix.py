#!/usr/bin/env python3
"""CAUS Phase 4 — autonomous fix loop (no-extra-cost variant).

Triggered by ``scripts/caus_daily_sweep.py`` after a Playwright scenario
finds a P0/P1 finding. Spawns a local ``claude -p`` subprocess (Max
plan OAuth session → $0 incremental cost — distinct from the
``self_healing/propose_fix.py`` path which uses the paid Anthropic API
key, gated DRY_RUN by default).

Architecture
------------
1. Caller passes a finding (dict / JSON file / stdin) and we:
   - Run safety gates BEFORE spending any tokens:
     * severity ∈ {P0, P1}                              (skip P2/P3)
     * page NOT in PROTECTED_PATHS                      (skip billing/auth/…)
     * daily fix budget                                 (max 3/day)
     * cooling-off                                      (3 recent fails → halt)
     * not in last-attempted-recently set               (idempotency)
   - On any gate fail → emit ``SKIP <reason>`` to stdout, exit 0.
2. Compose a fix prompt embedding the finding + repo guardrails.
3. ``claude -p`` subprocess, output-format=json, 600s timeout. We give
   the subagent permission to Read/Edit/Write/Bash/git/gh — same shell
   it'd have if a human ran ``claude`` interactively.
4. Parse subprocess output. Expected outcomes:
   - ``PR_URL <url>``    → success, log + return 0
   - ``INSUFFICIENT_EVIDENCE`` → can't reproduce, log + escalate
   - ``ESCALATE <reason>``      → safety-stop, log + escalate
   - anything else        → treat as failure, log + escalate
5. Update state file (.bkit/state/caus_auto_fix_state.json):
   - increment today_fix_count
   - append to recent_outcomes (rolling 10)
   - if last 3 are failures → set cooling_off_until = now + 24h

Cost
----
$0. Max plan tokens via the local ``claude`` OAuth session. No
Anthropic API key needed.

Safety rails (matching scripts/self_healing/propose_fix.py policy +
the bug-hunter / verify-ux false-positive history this session):

- PROTECTED_PATHS — never auto-fix files matching these substrings.
  Same allowlist as propose_fix.py: ``billing/`` ``routes/auth*``
  ``services/legal*`` ``risk_defense.py`` ``security.py``
  ``migrations/``. Plus added: ``routes/portfolio.py`` (CEO-flagged
  Bug #4 dirty row policy — auto-mutation = data fabrication).

- DAILY_BUDGET — max 3 fix attempts per UTC day. CAUS could hit a
  noisy finding loop; the budget caps blast radius.

- COOLING_OFF — if the last 3 attempts in ``recent_outcomes`` are
  failures, the next ``allow_attempt()`` returns False until
  ``cooling_off_until`` (24h from the third fail).

- IDEMPOTENCY — finding signature (severity+page+summary) is hashed;
  the last 10 hashes are remembered. A repeat = SKIP (don't re-fix
  the same thing CAUS keeps noticing). Resets daily.

- NO AUTO-MERGE — this script creates the PR (via ``gh pr create``)
  but never merges. CEO reviews + merges. Auto-merge is a separate
  policy decision and would need a different state machine.

CLI
---
    python scripts/caus_auto_fix.py --finding-json /path/to/finding.json
    python scripts/caus_auto_fix.py --finding-stdin   # reads JSON from stdin
    python scripts/caus_auto_fix.py --dry-run         # skip subprocess
    python scripts/caus_auto_fix.py --state-dump      # print state, exit
    python scripts/caus_auto_fix.py --reset-state     # clear cooling-off

Exit codes:
    0  — success OR safety-gate skip (both expected outcomes)
    1  — finding malformed / state file corrupt / unexpected error
    2  — subprocess timeout or non-zero exit
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".bkit" / "state"
STATE_FILE = STATE_DIR / "caus_auto_fix_state.json"
LOG_DIR = REPO_ROOT / "docs" / "qa" / "auto-fix-log"

# Same protected-path policy as scripts/self_healing/propose_fix.py — plus
# routes/portfolio.py (migration 034 / Bug #4 "auto-mutation = data
# fabrication" rationale).
PROTECTED_PATTERNS: tuple[str, ...] = (
    "billing/",
    "routes/auth",
    "services/legal",
    "risk_defense.py",
    "security.py",
    "migrations/",
    "routes/portfolio.py",
    # The forbidden-word filter itself — bug in the filter could let
    # banned cap-markets words through.
    "services/legal_filter",
    # Cron / scheduler / TCC / launchd plumbing — same rationale as
    # v42 patch "human action only for infra-altering changes".
    "scripts/caus_daily_sweep.py",
    "scripts/caus_auto_fix.py",  # never let it rewrite itself
)

DAILY_BUDGET = int(os.environ.get("CAUS_AUTO_FIX_BUDGET", "3"))
RECENT_OUTCOMES_KEEP = 10
COOLING_OFF_HOURS = 24
SUBPROC_TIMEOUT_S = int(os.environ.get("CAUS_AUTO_FIX_TIMEOUT", "600"))


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _today_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict[str, Any]:
    """Load auto-fix state from disk (or return a fresh state)."""
    if not STATE_FILE.exists():
        return _fresh_state()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _fresh_state()
    # Daily rollover: if today_date is stale, reset today_fix_count +
    # recent_finding_hashes (so the same finding 24h later is allowed).
    if data.get("today_date") != _today_utc():
        data["today_date"] = _today_utc()
        data["today_fix_count"] = 0
        data["recent_finding_hashes"] = []
    return data


def _fresh_state() -> dict[str, Any]:
    return {
        "version": 1,
        "today_date": _today_utc(),
        "today_fix_count": 0,
        "recent_outcomes": [],
        "recent_finding_hashes": [],
        "cooling_off_until": None,
        "last_run": None,
    }


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["last_run"] = _now_iso()
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Safety gates
# ---------------------------------------------------------------------------

def finding_hash(finding: dict[str, Any]) -> str:
    """Hash the finding identity for idempotency tracking."""
    key = (
        f"{finding.get('severity', '')}|"
        f"{finding.get('page', '')}|"
        f"{finding.get('summary', '')[:100]}"
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def is_protected_path(page: str) -> bool:
    """Does the finding's page match a protected-path pattern?"""
    lower = (page or "").lower()
    return any(pat.lower() in lower for pat in PROTECTED_PATTERNS)


def _now_dt() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_iso(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return None


def allow_attempt(
    state: dict[str, Any], finding: dict[str, Any]
) -> tuple[bool, str]:
    """Run all safety gates. Returns (allow, reason_when_blocked)."""
    sev = (finding.get("severity") or "").upper()
    if sev not in ("P0", "P1"):
        return False, f"severity={sev or '?'} (only P0/P1)"

    page = finding.get("page") or ""
    if is_protected_path(page):
        return False, f"protected-path: {page}"

    if state.get("today_fix_count", 0) >= DAILY_BUDGET:
        return False, f"daily budget exhausted ({DAILY_BUDGET})"

    cool_until = _parse_iso(state.get("cooling_off_until"))
    if cool_until and cool_until > _now_dt():
        return False, f"cooling-off until {state['cooling_off_until']}"

    h = finding_hash(finding)
    if h in (state.get("recent_finding_hashes") or []):
        return False, f"already attempted this finding today ({h})"

    return True, ""


# ---------------------------------------------------------------------------
# Fix prompt + claude subprocess
# ---------------------------------------------------------------------------

FIX_PROMPT_TEMPLATE = """You are PivoxQuant CAUS Phase 4 auto-fix agent.

A Playwright user-sim scenario found this real production bug:

```json
{finding_json}
```

The screenshot is at `{screenshot}` (if not 'N/A'). The repo is
PivoxQuant (Flask backend + Next.js frontend, see HANDOVER.md for
arch). Current working directory is the repo root.

Your task — fully autonomous, end to end:

1. Investigate. Read the affected page / route / component. Form a
   root-cause hypothesis backed by code evidence. If you cannot
   identify a root cause with high confidence, print
   `INSUFFICIENT_EVIDENCE` and exit — do not guess.

2. Write a minimal fix. Touch the smallest file set that closes the
   root cause. Do NOT add new dependencies. Do NOT silently swallow
   exceptions (any try/except must log + return safe fallback, never
   `pass`).

3. Verify locally:
   - Backend: `venv/bin/python -m pytest <changed-area tests> -q`
   - Frontend: `cd frontend && npm run typecheck && npm test`
   - All must pass with 0 regressions. Tests that fail unrelated to
     your change indicate a pre-existing issue — record it but do not
     attempt to fix.

4. Create a branch `caus-auto-fix/<finding-hash-12>` from main,
   commit, push. The commit message must:
   - First line: `fix(caus-auto): <one-line summary>`
   - Body: which finding triggered this (severity/page/summary), the
     root cause, the change, the verification command outputs.
   - End with `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`

5. Create PR via `gh pr create --base main` with label
   `caus-auto-fix` (idempotent — `gh label create ...` first if
   needed). PR title = commit first line. PR body = the structured
   finding + your investigation summary + verification output.

6. On the LAST line of stdout, print EXACTLY one of:
   - `PR_URL https://github.com/.../pull/NNN` — success.
   - `INSUFFICIENT_EVIDENCE` — could not pinpoint root cause.
   - `ESCALATE <short-reason>` — found a real bug but cannot
     auto-fix safely (e.g., schema migration needed, contested
     interpretation, requires CEO decision).

   Do not print PR_URL unless `gh pr view <pr>` confirms it exists.

Hard constraints (violating any → ESCALATE):
- NO destructive ops: no `rm -rf`, no `git push --force`, no
  `--no-verify`, no `--no-gpg-sign`.
- NO touching billing / auth / migrations / legal_filter / security.py
  / risk_defense.py / routes/portfolio.py (the auto-fix runner
  already pre-filters these, but defense-in-depth).
- NO auto-merge. Create the PR; the human reviews + merges.
- NO speculation. If a bug-hunter agent already flagged a contested
  interpretation (e.g. Bug #2 KOSPI 7,699 — code comment says real,
  bug-hunt says wrong), ESCALATE.

Memory rules (in scope):
- feedback_no_false_reports: only quote grep/test outputs you ran
- feedback_thorough_fixes: when touching a contract, sweep ALL
  consumers (today's session showed 3 sweeps to fully close the
  Position camelCase pattern)
- feedback_no_extra_cost: no new paid services / dependencies
- feedback_official_data_only: KIS / KRX / DART for KR data only
"""


def build_fix_prompt(finding: dict[str, Any]) -> str:
    return FIX_PROMPT_TEMPLATE.format(
        finding_json=json.dumps(finding, ensure_ascii=False, indent=2),
        screenshot=finding.get("screenshot", "N/A"),
    )


def invoke_claude(prompt: str, *, timeout_s: int = SUBPROC_TIMEOUT_S) -> tuple[
    int, str, str
]:
    """Run `claude -p <prompt>` and capture stdout/stderr.

    The Max OAuth session lives in ~/.claude/ — same shell as if a human
    ran the CLI interactively. No API key needed.
    """
    # --output-format text → simpler stdout parsing. We look for one of
    # the contract phrases on a single line. JSON output mode would also
    # work but text is robust to model verbosity.
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format", "text",
        # Allow the agent to use file IO + git + gh CLI. These are the
        # same defaults a human session would have.
        "--allowedTools", "Read,Edit,Write,Bash,Glob,Grep",
        # Hard cap on runtime; the cron job has its own timeout above
        # us, but make this explicit.
        "--max-turns", "30",
    ]
    try:
        proc = subprocess.run(
            cmd,
            timeout=timeout_s,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or ""), (exc.stderr or "") + "\n[caus_auto_fix] subprocess timed out"
    return proc.returncode, proc.stdout, proc.stderr


def parse_subprocess_outcome(stdout: str) -> tuple[str, str]:
    """Parse the agent's last-line contract.

    Returns (outcome, detail):
      outcome ∈ {"success", "insufficient", "escalate", "unparseable"}
      detail  — PR URL / reason / raw last line
    """
    lines = [ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]
    if not lines:
        return "unparseable", "(empty stdout)"
    last = lines[-1]
    if last.startswith("PR_URL "):
        return "success", last.split(" ", 1)[1].strip()
    if last == "INSUFFICIENT_EVIDENCE":
        return "insufficient", ""
    if last.startswith("ESCALATE"):
        return "escalate", last[len("ESCALATE"):].strip() or "no reason given"
    return "unparseable", last[:200]


# ---------------------------------------------------------------------------
# Outcome recording
# ---------------------------------------------------------------------------

def record_outcome(
    state: dict[str, Any],
    finding: dict[str, Any],
    outcome: str,
    detail: str,
) -> None:
    """Update state + append to docs/qa/auto-fix-log."""
    state["today_fix_count"] = int(state.get("today_fix_count", 0)) + 1
    state["recent_finding_hashes"] = (
        state.get("recent_finding_hashes") or []
    ) + [finding_hash(finding)]
    state["recent_finding_hashes"] = state["recent_finding_hashes"][-RECENT_OUTCOMES_KEEP:]
    state["recent_outcomes"] = (state.get("recent_outcomes") or []) + [outcome]
    state["recent_outcomes"] = state["recent_outcomes"][-RECENT_OUTCOMES_KEEP:]

    # Cooling-off: 3 consecutive non-success (escalate/insufficient/
    # unparseable) → halt for 24h.
    tail = state["recent_outcomes"][-3:]
    if len(tail) == 3 and all(o != "success" for o in tail):
        until = _now_dt() + datetime.timedelta(hours=COOLING_OFF_HOURS)
        state["cooling_off_until"] = until.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Append-only log file for audit trail.
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{_today_utc()}.md"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"## {_now_iso()} · {outcome.upper()} · "
            f"{finding.get('severity', '?')} · "
            f"{finding.get('page', '?')[:60]}\n\n"
            f"- summary: {finding.get('summary', '')[:200]}\n"
            f"- finding hash: `{finding_hash(finding)}`\n"
            f"- detail: {detail[:300]}\n\n"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CAUS Phase 4 auto-fix")
    p.add_argument("--finding-json", type=str, default=None,
                   help="path to a JSON file holding one finding dict")
    p.add_argument("--finding-stdin", action="store_true",
                   help="read JSON finding from stdin")
    p.add_argument("--dry-run", action="store_true",
                   help="skip claude subprocess; print would-do plan")
    p.add_argument("--state-dump", action="store_true",
                   help="print current state and exit")
    p.add_argument("--reset-state", action="store_true",
                   help="reset state (clears cooling-off + budget)")
    return p.parse_args(argv)


def run_one(finding: dict[str, Any], *, dry_run: bool = False) -> int:
    """Process one finding. Returns exit code (0 = OK or skip)."""
    state = load_state()
    allow, reason = allow_attempt(state, finding)
    if not allow:
        print(f"SKIP {reason}")
        save_state(state)
        return 0

    prompt = build_fix_prompt(finding)
    if dry_run:
        h = finding_hash(finding)
        print(f"DRY-RUN would invoke claude -p for finding {h}")
        print(f"  severity: {finding.get('severity')}")
        print(f"  page: {finding.get('page')}")
        print(f"  summary: {finding.get('summary')}")
        return 0

    rc, stdout, stderr = invoke_claude(prompt)
    outcome, detail = parse_subprocess_outcome(stdout)
    if rc not in (0, 1):
        # 124 timeout / abnormal exit
        outcome = "escalate" if outcome == "unparseable" else outcome
        detail = (detail or "") + f" [subproc rc={rc}]"
    record_outcome(state, finding, outcome, detail)
    save_state(state)

    if outcome == "success":
        print(f"PR_URL {detail}")
        return 0
    print(f"{outcome.upper()} {detail}")
    # ESCALATE / INSUFFICIENT are expected outcomes for some findings;
    # return 0 so cron doesn't mark the whole sweep failed.
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.state_dump:
        print(json.dumps(load_state(), ensure_ascii=False, indent=2))
        return 0
    if args.reset_state:
        save_state(_fresh_state())
        print("state reset")
        return 0

    # Load finding.
    if args.finding_json:
        path = Path(args.finding_json)
        if not path.exists():
            print(f"ERROR: --finding-json path does not exist: {path}", file=sys.stderr)
            return 1
        try:
            finding = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"ERROR: --finding-json invalid: {exc}", file=sys.stderr)
            return 1
    elif args.finding_stdin:
        try:
            finding = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            print(f"ERROR: stdin invalid JSON: {exc}", file=sys.stderr)
            return 1
    else:
        print(
            "ERROR: must pass --finding-json <path> or --finding-stdin",
            file=sys.stderr,
        )
        return 1

    return run_one(finding, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
