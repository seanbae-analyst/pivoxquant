#!/usr/bin/env python3
"""Layer B — Morning triage (09:00 KST, daily).

Reads open `nightly-bug-hunt` issues from GitHub, collects their body +
optional artifact excerpts, then calls Claude (Sonnet) to produce a
root-cause analysis + 3-line fix proposal for the top N issues by
severity. The result is posted back as a comment on the same issue.

Design constraints
------------------
* Stdlib + `anthropic` SDK + `gh` CLI only.
* Budget: <= 3 issues per run, ~2k input tokens + 400 output tokens each
  at Sonnet pricing (~$0.08/issue → ~$0.24/run → ~$7/month).
* Never modifies files or opens PRs here. This is advisory-only. The
  actual self-healing / PR creation lives in scripts/self_healing/.
* Dry-run mode: `TRIAGE_DRY_RUN=1` skips the Claude call and the GH
  comment, but still prints the prompts that *would* be sent. Used for
  local smoke tests without an API key.

Inputs (env)
------------
* ANTHROPIC_API_KEY — required unless TRIAGE_DRY_RUN=1
* GH_TOKEN           — required for gh CLI (GitHub Actions auto-provides)
* GITHUB_REPOSITORY  — `owner/repo` (GitHub Actions auto-provides)
* TRIAGE_MAX_ISSUES  — default 3
* TRIAGE_DRY_RUN     — "1" to skip live calls
* TRIAGE_MODEL       — default "claude-sonnet-4-5-20251022" (override
  if 4.6/4.7 Sonnet is available)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Caps
MAX_ISSUES = int(os.environ.get("TRIAGE_MAX_ISSUES", "3"))
MAX_BODY_CHARS = 6000
MAX_ARTIFACT_CHARS = 2500
MAX_FILE_PEEK_CHARS = 1500
DRY_RUN = os.environ.get("TRIAGE_DRY_RUN", "") == "1"
MODEL = os.environ.get("TRIAGE_MODEL", "claude-sonnet-4-5-20251022")

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

SYSTEM_PROMPT = """You are a senior PivoxQuant backend/SRE engineer.
PivoxQuant is a Flask 3 + Next.js 16 Korean retail investment platform
(Railway + Vercel, PostgreSQL, Alpaca/KIS/FMP integrations).

Your job: read a nightly bug-hunt issue, identify the MOST LIKELY root
cause using the evidence provided, and propose a minimal 3-line fix.

Strict rules:
- Never invent evidence. If the data is insufficient, say
  "INSUFFICIENT_EVIDENCE" and list exactly what additional data is
  needed.
- Do NOT recommend buying, selling, or holding any security. This is an
  infrastructure context, not advisory.
- Respect the kill switch: `enabled=false` on /api/agent/status is
  intentional and MUST NOT be "fixed" to `true`. (As of 2026-05-09 the
  legal-status field is no longer exposed publicly — see SEC-C.)
- Output format (markdown):

  ## Root Cause (most likely)
  <one paragraph, cite specific file:line or endpoint from evidence>

  ## Confidence
  <low|medium|high> — <one sentence justification>

  ## Fix proposal (max 3 lines)
  1. <concrete change: file + diff sketch>
  2. <concrete change>
  3. <concrete change or "n/a">

  ## Verification
  <one-liner test or curl that will prove the fix>
"""


def run(cmd: list[str], *, check: bool = True) -> str:
    """Run a subprocess, return stdout stripped.

    Graceful fallback: missing binary (e.g. `gh` not installed on a
    macOS dev box) returns "" instead of raising. In GitHub Actions the
    binary is always present, so this only affects local dry-runs.
    """
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=check)
        return res.stdout.strip()
    except FileNotFoundError:
        print(f"[triage] binary not found: {cmd[0]} — returning empty", file=sys.stderr)
        return ""
    except subprocess.CalledProcessError as e:
        print(f"[triage] cmd failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"  stderr: {e.stderr}", file=sys.stderr)
        if check:
            raise
        return ""


def list_open_issues(repo: str) -> list[dict[str, Any]]:
    """Return open issues labeled `nightly-bug-hunt`, newest first."""
    raw = run(
        [
            "gh", "issue", "list",
            "--repo", repo,
            "--state", "open",
            "--label", "nightly-bug-hunt",
            "--json", "number,title,body,labels,updatedAt",
            "--limit", "20",
        ],
        check=False,
    )
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[triage] gh returned non-JSON: {raw[:200]}", file=sys.stderr)
        return []


def issue_severity(issue: dict[str, Any]) -> str:
    """Extract severity from label names; default 'medium'."""
    names = [lbl.get("name", "") for lbl in issue.get("labels", [])]
    for name in names:
        if name in SEVERITY_RANK:
            return name
    title = issue.get("title", "").lower()
    for k in SEVERITY_RANK:
        if k in title:
            return k
    return "medium"


def already_triaged_today(repo: str, issue_number: int) -> bool:
    """Skip if our triage comment already exists *today* (UTC date)."""
    raw = run(
        [
            "gh", "issue", "view", str(issue_number),
            "--repo", repo,
            "--json", "comments",
        ],
        check=False,
    )
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for c in data.get("comments", []):
        body = c.get("body", "")
        created = (c.get("createdAt", "") or "")[:10]
        if created == today and "<!-- morning-triage -->" in body:
            return True
    return False


def extract_file_refs(body: str) -> list[str]:
    """Pull out `path/to/file.py` style references from the issue body.

    Only returns files that actually exist inside the current repo
    checkout, capped at 4 to keep the prompt small.
    """
    import re
    # Conservative: match `services/.../*.py`, `routes/...`, `frontend/src/...`, `scripts/...`
    pat = re.compile(
        r"([a-zA-Z0-9_/\.\-]*?(?:services|routes|frontend/src|scripts|tests|models)"
        r"/[a-zA-Z0-9_/\.\-]+?\.(?:py|ts|tsx|js))"
    )
    seen: list[str] = []
    root = Path(__file__).resolve().parents[2]
    for m in pat.finditer(body):
        path = m.group(1).lstrip("/")
        if path in seen:
            continue
        full = root / path
        if full.exists() and full.is_file():
            seen.append(path)
        if len(seen) >= 4:
            break
    return seen


def peek_file(rel_path: str) -> str:
    """Return the first MAX_FILE_PEEK_CHARS of a repo file."""
    root = Path(__file__).resolve().parents[2]
    p = root / rel_path
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > MAX_FILE_PEEK_CHARS:
        return text[:MAX_FILE_PEEK_CHARS] + f"\n... [truncated at {MAX_FILE_PEEK_CHARS} chars]"
    return text


def git_last_change(rel_path: str) -> str:
    """Last commit that touched the file (for 'recent diff' context)."""
    out = run(
        ["git", "log", "-n", "1", "--pretty=format:%h %ad %s", "--date=short", "--", rel_path],
        check=False,
    )
    return out or "(no git history)"


def build_user_prompt(issue: dict[str, Any], file_refs: list[str]) -> str:
    parts: list[str] = []
    parts.append(f"# Issue #{issue['number']} — {issue['title']}")
    parts.append(f"Severity label: {issue_severity(issue)}")
    parts.append("")
    body = issue.get("body", "") or ""
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + f"\n... [truncated at {MAX_BODY_CHARS} chars]"
    parts.append("## Issue body")
    parts.append(body)
    parts.append("")
    if file_refs:
        parts.append("## Repo context (files referenced in the issue)")
        for rel in file_refs:
            parts.append(f"### `{rel}`")
            parts.append(f"Last change: {git_last_change(rel)}")
            parts.append("```")
            parts.append(peek_file(rel))
            parts.append("```")
            parts.append("")
    parts.append(
        "Given the above, produce your root-cause analysis in the strict "
        "markdown format from the system prompt."
    )
    return "\n".join(parts)


def call_claude(system_prompt: str, user_prompt: str) -> str:
    """Single Anthropic API call. Returns response text or error sentinel."""
    if DRY_RUN:
        return (
            "## Root Cause (most likely)\n"
            "[DRY_RUN] would call Claude here.\n\n"
            "## Confidence\nlow — dry-run skipped live inference\n\n"
            "## Fix proposal (max 3 lines)\n1. n/a\n2. n/a\n3. n/a\n\n"
            "## Verification\nn/a — dry run"
        )
    try:
        import anthropic
    except ImportError:
        print("[triage] anthropic SDK not installed — treating as dry-run", file=sys.stderr)
        return "[ERROR] anthropic SDK missing"
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "[ERROR] ANTHROPIC_API_KEY not set"

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as e:
        print(f"[triage] Anthropic call failed: {e}", file=sys.stderr)
        return f"[ERROR] Anthropic call failed: {e}"
    # Claude Messages API returns a list of content blocks
    out = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    return out.strip() or "[ERROR] empty response"


def post_comment(repo: str, issue_number: int, body: str) -> None:
    if DRY_RUN:
        print(f"[triage][dry-run] would comment on #{issue_number}:\n{body[:400]}")
        return
    # Use stdin to avoid shell-escape issues
    p = subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body-file", "-"],
        input=body, text=True, capture_output=True, check=False,
    )
    if p.returncode != 0:
        print(f"[triage] gh comment failed: {p.stderr}", file=sys.stderr)


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "seanbae-analyst/pivoxquant")
    if DRY_RUN:
        print("[triage] DRY_RUN=1 — no API calls, no comments")

    issues = list_open_issues(repo)
    if not issues:
        print("[triage] no open nightly-bug-hunt issues — nothing to do")
        return 0

    # Sort by severity (critical first), then newest
    issues.sort(key=lambda i: (SEVERITY_RANK.get(issue_severity(i), 9), i.get("updatedAt", "")), reverse=False)
    # reverse=False so critical comes first; updatedAt sort is ascending but
    # severity is primary key. Adequate for tiebreak with small N.

    analyzed = 0
    for issue in issues:
        if analyzed >= MAX_ISSUES:
            break
        num = issue["number"]
        if already_triaged_today(repo, num):
            print(f"[triage] #{num} already triaged today — skip")
            continue
        file_refs = extract_file_refs(issue.get("body", "") or "")
        user_prompt = build_user_prompt(issue, file_refs)
        print(f"[triage] analyzing #{num} ({issue_severity(issue)}) — {len(user_prompt)} chars prompt")
        claude_out = call_claude(SYSTEM_PROMPT, user_prompt)
        comment = (
            "<!-- morning-triage -->\n"
            "## 🤖 Morning Triage — Claude analysis\n\n"
            f"**Model**: `{MODEL}` • **Files inspected**: {', '.join(file_refs) or '(none)'}\n\n"
            f"{claude_out}\n\n"
            "---\n"
            "_This is advisory only. Always verify against the evidence. "
            "Kill switches (`enabled=false` on /api/agent/status) must not be "
            "disabled as a 'fix'._"
        )
        post_comment(repo, num, comment)
        analyzed += 1

    print(f"[triage] done — analyzed {analyzed} issue(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
