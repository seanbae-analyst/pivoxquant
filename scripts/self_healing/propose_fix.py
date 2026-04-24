#!/usr/bin/env python3
"""Layer C — Propose a fix PR for a recurring Railway error.

Inputs
------
* `self_healing_artifacts/railway_patterns.jsonl` (from `scan_railway_logs.py`)
* `ANTHROPIC_API_KEY` (unless SELF_HEALING_DRY_RUN=1)
* `GH_TOKEN`, `GITHUB_REPOSITORY` (for PR creation — only if AUTO_PR=1)

Safety policy
-------------
1. Protected-path allowlist: error patterns in `autotrader.py`,
   `risk_defense.py`, `services/legal*`, `billing/`, `routes/auth*`,
   `security.py`, `migrations/` are NEVER auto-patched. Only an Issue is
   filed to alert the CEO.
2. Dry-run first: default `SELF_HEALING_DRY_RUN=1`. Draft PR is only
   opened when `AUTO_PR=1` is explicitly set.
3. 24-hour circuit breaker: if the same fingerprint was proposed
   unsuccessfully 3 times in the last 24h (tracked via
   `.self_healing_history.json`), stop and escalate.
4. pytest gate: the generated fix must keep `pytest -q` passing. The
   workflow runs pytest after applying the patch before opening the PR.
   This script prepares the branch + diff; it never decides to merge.

Budget
------
One Claude call per hot pattern, capped at 2 per run (~$0.16/run).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "self_healing_artifacts"
PATTERNS_PATH = ARTIFACT_DIR / "railway_patterns.jsonl"
HISTORY_PATH = ARTIFACT_DIR / "history.json"
PATCH_DIR = ARTIFACT_DIR / "patches"

DRY_RUN = os.environ.get("SELF_HEALING_DRY_RUN", "1") == "1"
AUTO_PR = os.environ.get("AUTO_PR", "0") == "1"
MAX_PATTERNS = int(os.environ.get("SELF_HEALING_MAX_PATTERNS", "2"))
MODEL = os.environ.get("SELF_HEALING_MODEL", "claude-sonnet-4-5-20251022")

SYSTEM_PROMPT = """You are a senior PivoxQuant SRE.
You receive a recurring Python runtime error from Railway logs and a
peek of the offending file. Your job: produce a MINIMAL unified diff
that plausibly fixes the root cause without changing public behavior.

Strict rules:
- Output only a unified diff (patch format starting with `--- a/...` / `+++ b/...`).
- Do NOT touch files outside the one in the error.
- Do NOT add new dependencies.
- Do NOT silently swallow exceptions — if a `try/except` is appropriate,
  it MUST log the exception and return a safe fallback, never `pass`.
- If the root cause is unclear, output EXACTLY the single line
  `INSUFFICIENT_EVIDENCE` and nothing else.
- Never modify kill-switch values or compliance-sensitive constants.
"""


def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def load_patterns() -> list[dict[str, Any]]:
    if not PATTERNS_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in PATTERNS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def load_history() -> dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_history(h: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(h, indent=2), encoding="utf-8")


def under_circuit_breaker(fp: str, history: dict[str, Any]) -> bool:
    """True if this fingerprint has been attempted 3+ times in 24h."""
    entries = history.get(fp, [])
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent = [e for e in entries if e.get("ts", "") > cutoff]
    return len(recent) >= 3


def record_attempt(fp: str, history: dict[str, Any], status: str) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "status": status}
    history.setdefault(fp, []).append(entry)
    save_history(history)


def peek_source(file_rel: str, line: int, window: int = 40) -> str:
    p = ROOT / file_rel
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    lo = max(0, line - window)
    hi = min(len(lines), line + window)
    numbered = [f"{i+1:>5}: {lines[i]}" for i in range(lo, hi)]
    return "\n".join(numbered)


def build_prompt(pattern: dict[str, Any]) -> str:
    src = peek_source(pattern["file"], pattern["line"])
    return (
        f"# Recurring error\n"
        f"- File: `{pattern['file']}`\n"
        f"- Line: {pattern['line']}\n"
        f"- Exception: `{pattern['exception']}: {pattern['message']}`\n"
        f"- Occurrences in last hour: {pattern['count']}\n"
        f"- Samples: {json.dumps(pattern.get('sample_lines', []), ensure_ascii=False)}\n\n"
        f"# Source context (lines {max(1, pattern['line']-40)}..{pattern['line']+40})\n"
        f"```python\n{src}\n```\n\n"
        f"Produce a minimal unified diff that fixes the root cause. "
        f"Start immediately with `--- a/...` — no prose, no code fences."
    )


def call_claude(prompt: str) -> str:
    if DRY_RUN:
        return "INSUFFICIENT_EVIDENCE"
    try:
        import anthropic
    except ImportError:
        print("[propose_fix] anthropic SDK missing — treating as dry-run", file=sys.stderr)
        return "INSUFFICIENT_EVIDENCE"
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "INSUFFICIENT_EVIDENCE"
    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"[propose_fix] API call failed: {e}", file=sys.stderr)
        return "INSUFFICIENT_EVIDENCE"
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def write_patch(fp: str, diff: str) -> Path:
    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = PATCH_DIR / f"{fp}.patch"
    out.write_text(diff, encoding="utf-8")
    return out


def open_escalation_issue(pattern: dict[str, Any], reason: str) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo or DRY_RUN or not os.environ.get("GH_TOKEN"):
        print(f"[propose_fix] would escalate: {reason}")
        return
    title = f"[Self-healing] Cannot auto-fix {pattern['fingerprint']} — {reason}"
    body = (
        f"## Escalation from self-healing\n\n"
        f"**Reason**: {reason}\n\n"
        f"- File: `{pattern['file']}`\n"
        f"- Line: {pattern['line']}\n"
        f"- Exception: `{pattern['exception']}: {pattern['message']}`\n"
        f"- Count last hour: {pattern['count']}\n"
        f"- Fingerprint: `{pattern['fingerprint']}`\n\n"
        f"Manual intervention required."
    )
    subprocess.run(
        ["gh", "issue", "create", "--repo", repo,
         "--title", title, "--body", body,
         "--label", "self-healing,escalation"],
        check=False,
    )


def main() -> int:
    patterns = load_patterns()
    if not patterns:
        print("[propose_fix] no hot patterns — nothing to do")
        return 0
    history = load_history()

    done = 0
    for p in patterns:
        if done >= MAX_PATTERNS:
            break
        fp = p["fingerprint"]
        if p.get("protected"):
            print(f"[propose_fix] {fp} is in a PROTECTED path ({p['file']}) — escalating only")
            open_escalation_issue(p, "file is on protected-path allowlist")
            record_attempt(fp, history, "escalated:protected")
            continue
        if under_circuit_breaker(fp, history):
            print(f"[propose_fix] {fp} under 24h circuit breaker — escalating")
            open_escalation_issue(p, "24h circuit breaker tripped (3+ failed auto-fix attempts)")
            record_attempt(fp, history, "escalated:circuit-breaker")
            continue

        prompt = build_prompt(p)
        diff = call_claude(prompt)
        if diff.strip() == "INSUFFICIENT_EVIDENCE":
            print(f"[propose_fix] {fp} — insufficient evidence (or dry-run)")
            record_attempt(fp, history, "insufficient-evidence")
            continue
        patch = write_patch(fp, diff)
        print(f"[propose_fix] {fp} — wrote candidate patch to {patch}")
        record_attempt(fp, history, "patch-written")
        # The workflow itself is responsible for: apply patch → pytest →
        # if green and AUTO_PR=1, create Draft PR. We do not do that
        # here to keep this script reproducible locally.
        done += 1

    print(f"[propose_fix] done — {done} patch(es) prepared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
