"""Agent telemetry logger — append agent run results to jsonl.

Called by the main orchestrator (Opus) immediately after a sub-agent
returns. Records outcome, verify status, tokens, tool uses, and any
self-flagged concerns so agent-ops can analyze patterns weekly.

Storage: ``.bkit/state/agent_telemetry.jsonl`` (gitignored).

CLI usage (one row per call):

    python scripts/agent_ops/log_run.py \
        --agent backend-dev \
        --task F5_ai_twin \
        --outcome INCOMPLETE \
        --verify BLOCKED_BASH \
        --tokens 164028 \
        --tools 99 \
        --duration-ms 816568 \
        --concerns "rationale leak" "no rate limit"

JSON usage (stdin):

    echo '{"agent":"...","outcome":"COMPLETE",...}' | \
        python scripts/agent_ops/log_run.py --stdin
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TELEMETRY_DIR = REPO_ROOT / ".bkit" / "state"
TELEMETRY_FILE = TELEMETRY_DIR / "agent_telemetry.jsonl"


VALID_OUTCOMES = {"COMPLETE", "INCOMPLETE", "BLOCKED", "ERROR"}
VALID_VERIFY = {"PASS", "FAIL", "BLOCKED_BASH", "SKIPPED", "PARTIAL"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--stdin", action="store_true",
                        help="Read JSON record from stdin instead of CLI flags")
    parser.add_argument("--agent", help="Agent name (e.g. backend-dev)")
    parser.add_argument("--task", help="Task identifier (free-form)")
    parser.add_argument("--outcome", choices=VALID_OUTCOMES,
                        help="High-level outcome classification")
    parser.add_argument("--verify", choices=VALID_VERIFY,
                        help="Did the agent actually verify (run pytest etc.)?")
    parser.add_argument("--tokens", type=int, default=0,
                        help="Total tokens consumed")
    parser.add_argument("--tools", type=int, default=0,
                        help="Tool use count")
    parser.add_argument("--duration-ms", type=int, default=0,
                        help="Wall-clock duration in milliseconds")
    parser.add_argument("--tests-added", type=int, default=0)
    parser.add_argument("--tests-passing", type=int, default=None,
                        help="Pass count if verifiable, else omit")
    parser.add_argument("--concerns", nargs="*", default=[],
                        help="Self-flagged concerns (legal/perf/etc.)")
    parser.add_argument("--false-report", action="store_true",
                        help="Detected post-hoc as false reporting")
    parser.add_argument("--note", help="Free-form context note")
    return parser.parse_args()


def build_record(args: argparse.Namespace) -> dict:
    if args.stdin:
        return json.loads(sys.stdin.read())
    if not args.agent or not args.outcome or not args.verify:
        raise SystemExit(
            "--agent, --outcome, --verify are required (or use --stdin)"
        )
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent,
        "task": args.task or "",
        "outcome": args.outcome,
        "verify": args.verify,
        "tokens": args.tokens,
        "tools": args.tools,
        "duration_ms": args.duration_ms,
        "tests_added": args.tests_added,
        "tests_passing": args.tests_passing,
        "self_flagged_concerns": args.concerns,
        "false_report_detected": args.false_report,
        "note": args.note or "",
    }


def append_record(record: dict) -> Path:
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    with TELEMETRY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return TELEMETRY_FILE


def main() -> int:
    args = parse_args()
    record = build_record(args)
    # Validate even when reading from stdin
    if record.get("outcome") not in VALID_OUTCOMES:
        raise SystemExit(f"Invalid outcome: {record.get('outcome')}")
    if record.get("verify") not in VALID_VERIFY:
        raise SystemExit(f"Invalid verify: {record.get('verify')}")
    path = append_record(record)
    print(f"logged → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
