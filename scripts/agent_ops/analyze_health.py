"""Weekly agent health analyzer.

Reads ``.bkit/state/agent_telemetry.jsonl`` (last 7 days), computes
per-agent metrics and structural failure patterns, emits a markdown
report ready to post as a GitHub Issue.

CLI:

    python scripts/agent_ops/analyze_health.py [--days 7] [--out report.md]

Patterns currently detected:
- BG verify gap         — outcome=INCOMPLETE && verify=BLOCKED_BASH
- Domain miss           — same agent fails ≥3× on similar task names
- Token blowup          — single run > 200K tokens
- Hallucination         — false_report_detected=True
- Inactive agent        — 0 calls in window (sunset candidate)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TELEMETRY_FILE = REPO_ROOT / ".bkit" / "state" / "agent_telemetry.jsonl"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

TOKEN_BLOWUP = 200_000


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--out", type=Path, default=None)
    return p.parse_args()


def load_records(days: int) -> list[dict]:
    if not TELEMETRY_FILE.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    with TELEMETRY_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                ts = datetime.fromisoformat(rec["ts"])
                if ts >= cutoff:
                    out.append(rec)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return out


def list_known_agents() -> set[str]:
    if not AGENTS_DIR.exists():
        return set()
    return {p.stem for p in AGENTS_DIR.glob("*.md") if p.stem != "README"}


def per_agent_metrics(records: list[dict]) -> dict[str, dict]:
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_agent[r.get("agent", "?")].append(r)

    metrics = {}
    for agent, rs in by_agent.items():
        n = len(rs)
        complete = sum(1 for r in rs if r.get("outcome") == "COMPLETE")
        verified = sum(1 for r in rs if r.get("verify") == "PASS")
        hallucinated = sum(1 for r in rs if r.get("false_report_detected"))
        avg_tokens = int(mean(r.get("tokens", 0) for r in rs)) if rs else 0
        metrics[agent] = {
            "calls": n,
            "complete": complete,
            "complete_rate": complete / n if n else 0.0,
            "verify_rate": verified / n if n else 0.0,
            "hallucinated": hallucinated,
            "avg_tokens": avg_tokens,
        }
    return metrics


def detect_patterns(records: list[dict]) -> dict[str, list[dict]]:
    patterns: dict[str, list[dict]] = defaultdict(list)

    for r in records:
        if r.get("outcome") == "INCOMPLETE" and r.get("verify") == "BLOCKED_BASH":
            patterns["bg_verify_gap"].append(r)
        if r.get("tokens", 0) > TOKEN_BLOWUP:
            patterns["token_blowup"].append(r)
        if r.get("false_report_detected"):
            patterns["hallucination"].append(r)

    domain_misses: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        if r.get("outcome") in {"INCOMPLETE", "BLOCKED", "ERROR"}:
            key = (r.get("agent", "?"), (r.get("task") or "")[:8])
            domain_misses[key].append(r)
    for key, rs in domain_misses.items():
        if len(rs) >= 3:
            patterns["domain_miss"].extend(rs)

    return dict(patterns)


def render_report(records: list[dict], metrics: dict[str, dict],
                   patterns: dict[str, list[dict]],
                   known_agents: set[str], days: int) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# Agent Health — Week ending {today} (last {days}d)\n"]

    lines.append(f"**Total runs**: {len(records)}")
    inactive = sorted(known_agents - set(metrics.keys()))
    lines.append(f"**Active agents**: {len(metrics)} / {len(known_agents)}")
    lines.append(f"**Inactive (no calls)**: {len(inactive)}")
    lines.append("")

    if metrics:
        lines.append("## Per-Agent Metrics")
        lines.append("| Agent | Calls | Complete% | Verify% | Halluc | Avg tokens |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for agent, m in sorted(metrics.items(), key=lambda x: -x[1]["calls"]):
            lines.append(
                f"| {agent} | {m['calls']} | {m['complete_rate']*100:.0f}% | "
                f"{m['verify_rate']*100:.0f}% | {m['hallucinated']} | "
                f"{m['avg_tokens']:,} |"
            )
        lines.append("")

    if patterns:
        lines.append("## Failure Patterns Detected")
        for name, hits in patterns.items():
            lines.append(f"- **{name}**: {len(hits)} incident(s)")
            for h in hits[:5]:
                lines.append(
                    f"  - {h.get('agent')}/{h.get('task','')} "
                    f"@ {h.get('ts','')[:10]}"
                )
        lines.append("")

    if inactive:
        lines.append("## Sunset Candidates (0 calls)")
        for a in inactive:
            lines.append(f"- {a}")
        lines.append("")
        lines.append("→ Review whether these are still needed or can be removed.")
        lines.append("")

    lines.append("## Recommended Actions")
    if patterns.get("bg_verify_gap"):
        lines.append("- 🔴 Enforce verify-policy on every background launch.")
    if patterns.get("token_blowup"):
        lines.append("- 🟠 Decompose large tasks; investigate single-call >200K.")
    if patterns.get("hallucination"):
        lines.append("- 🔴 Tighten Iron Rules + add post-hoc verification step.")
    if patterns.get("domain_miss"):
        agents_missing = Counter(r.get("agent") for r in patterns["domain_miss"])
        for agent, n in agents_missing.most_common(3):
            lines.append(f"- 🟡 {agent}: {n} domain misses — propose specialist.")
    if not patterns:
        lines.append("- ✅ No structural patterns detected this window.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    records = load_records(args.days)
    known = list_known_agents()
    metrics = per_agent_metrics(records)
    patterns = detect_patterns(records)
    report = render_report(records, metrics, patterns, known, args.days)

    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
