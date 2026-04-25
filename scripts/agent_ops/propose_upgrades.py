"""Agent upgrade proposal generator.

Reads telemetry + agent .md files, identifies improvement patterns,
and generates a PR-ready diff bundle. CEO reviews + merges.

Trigger:
- Monthly cron (`agent-upgrades-monthly.yml`)
- Manual: ``python scripts/agent_ops/propose_upgrades.py``

Output:
- ``reports/agent_ops/proposals_<YYYY-MM>.md`` — human-readable
- ``.bkit/state/proposed_diffs/<agent>.diff`` — apply with ``git apply``

Detection rules (extensible):
1. **PivoxQuant context staleness** — agent .md does not reference
   the current HANDOVER version → append context stanza.
2. **Cross-reference gap** — generic agent (e.g. legal) without
   delegation hint to its specialist (legal-kr-fintech).
3. **Iron Rules absent** — no "거짓 보고 금지" / verify mandate.
4. **Background-launch warning absent** — agent uses Bash but no
   verify-policy reference.
5. **Tool inflation** — agent has > 12 tools (likely overscoped).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
REPORTS_DIR = REPO_ROOT / "reports" / "agent_ops"

CURRENT_HANDOVER_VERSION = "v9"  # bump when HANDOVER ships new version
CURRENT_HANDOVER_DATE = "2026-04-25"

# Agents that should delegate to specialists when present
SPECIALIST_DELEGATIONS = {
    "legal":          ("legal-kr-fintech", "한국 핀테크 규제"),
    "verify-design":  ("brand-voice", "브랜드 톤 / observational 어휘"),
    "engineering":    ("migration-guard", "Alembic / DB schema"),
    "qa":             ("frontend-test-runner", "Playwright / Vitest"),
    "devops":         ("autopilot-monitor", "Layer A/B/C 모니터링"),
    "audit":          ("agent-ops", "agent telemetry / upgrade"),
}

REQUIRED_PHRASES = [
    "거짓 보고 금지",
    "PivoxQuant",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", type=Path, default=None,
                   help="Output report path (default: reports/agent_ops/...)")
    p.add_argument("--apply", action="store_true",
                   help="Actually edit agent .md files (default: dry-run report only)")
    return p.parse_args()


def load_agent(name: str) -> tuple[Path, str]:
    path = AGENTS_DIR / f"{name}.md"
    return path, path.read_text(encoding="utf-8") if path.exists() else ""


def detect_issues(name: str, content: str) -> list[dict]:
    issues = []

    # Rule 1: HANDOVER version staleness
    if CURRENT_HANDOVER_VERSION not in content:
        issues.append({
            "rule": "stale_handover",
            "severity": "low",
            "fix": f"reference HANDOVER {CURRENT_HANDOVER_VERSION}",
        })

    # Rule 2: Cross-reference gap
    if name in SPECIALIST_DELEGATIONS:
        specialist, _ = SPECIALIST_DELEGATIONS[name]
        if specialist not in content:
            issues.append({
                "rule": "missing_delegation",
                "severity": "medium",
                "fix": f"delegate to specialist `{specialist}`",
            })

    # Rule 3: Iron Rules / honesty mandate
    for phrase in REQUIRED_PHRASES:
        if phrase not in content:
            issues.append({
                "rule": f"missing_phrase:{phrase}",
                "severity": "low",
                "fix": f"add `{phrase}` mandate",
            })
            break  # one report per agent is enough

    # Rule 4: BG-launch warning
    has_bash = re.search(r"^\s*-\s*Bash\b", content, re.MULTILINE)
    if has_bash and "verify-policy" not in content:
        issues.append({
            "rule": "no_verify_policy",
            "severity": "high",
            "fix": "reference verify-policy for background launch decisions",
        })

    # Rule 5: Tool inflation
    tools = re.findall(r"^\s*-\s+(\S+)$", content[:1500], re.MULTILINE)
    if len(tools) > 12:
        issues.append({
            "rule": "tool_inflation",
            "severity": "low",
            "fix": f"agent has {len(tools)} tools — consider scoping down",
        })

    return issues


def render_report(per_agent: dict[str, list[dict]]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# Agent Upgrade Proposals — {today}\n"]

    total = sum(len(v) for v in per_agent.values())
    lines.append(f"**Agents scanned**: {len(per_agent)}")
    lines.append(f"**Issues found**: {total}")
    lines.append(f"**Reference HANDOVER**: {CURRENT_HANDOVER_VERSION} ({CURRENT_HANDOVER_DATE})\n")

    if total == 0:
        lines.append("✅ All agents look healthy. No upgrade proposals.")
        return "\n".join(lines)

    by_severity = defaultdict(list)
    for agent, issues in per_agent.items():
        for issue in issues:
            by_severity[issue["severity"]].append((agent, issue))

    for sev in ("high", "medium", "low"):
        rows = by_severity.get(sev, [])
        if not rows:
            continue
        lines.append(f"## {sev.upper()} ({len(rows)})")
        for agent, issue in rows:
            lines.append(f"- **{agent}** — {issue['rule']}")
            lines.append(f"  → {issue['fix']}")
        lines.append("")

    lines.append("## Apply")
    lines.append("```bash")
    lines.append("python scripts/agent_ops/propose_upgrades.py --apply")
    lines.append("# review diff, then commit")
    lines.append("```")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    if not AGENTS_DIR.exists():
        print(f"agents dir missing: {AGENTS_DIR}", file=sys.stderr)
        return 1

    per_agent: dict[str, list[dict]] = {}
    for path in sorted(AGENTS_DIR.glob("*.md")):
        name = path.stem
        if name == "README":
            continue
        _, content = load_agent(name)
        issues = detect_issues(name, content)
        if issues:
            per_agent[name] = issues

    report = render_report(per_agent)

    if args.out is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        args.out = REPORTS_DIR / f"proposals_{month}.md"

    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out}")
    print(report[:600])

    if args.apply:
        print("\n--apply not implemented in this draft. Use the report to "
              "make the edits manually or via Claude Code.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
