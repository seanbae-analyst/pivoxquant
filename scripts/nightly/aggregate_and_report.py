#!/usr/bin/env python3
"""
Aggregate nightly bug hunt artifacts into a single markdown report + JSON.

Inputs (jsonl files under ARTIFACTS_DIR):
  - ticker_health.jsonl
  - indices_consistency.jsonl
  - critical_endpoints.jsonl
  - pytest_main.txt        (plain text from pytest -q output, optional)

Outputs:
  - report.md              (human-readable, used for GitHub Issue body)
  - summary.json           (machine-readable counts + severity)

Severity rules:
  - critical: /api/health failure at any point
  - high:    >=5 ticker issues OR any indices_consistency issue OR pytest failed
  - medium:  1-4 ticker issues
  - none:    everything clean
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ARTIFACTS = Path(os.environ.get("ARTIFACTS_DIR", "nightly_artifacts"))
REPORT_MD = ARTIFACTS / "report.md"
SUMMARY_JSON = ARTIFACTS / "summary.json"


def _load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    tickers = _load_jsonl(ARTIFACTS / "ticker_health.jsonl")
    indices = _load_jsonl(ARTIFACTS / "indices_consistency.jsonl")
    critical = _load_jsonl(ARTIFACTS / "critical_endpoints.jsonl")

    ticker_issues = [t for t in tickers if t.get("issue")]
    indices_issues = [i for i in indices if i.get("issue")]
    critical_issues = [c for c in critical if c.get("issue")]

    health_failed = any(
        c.get("issue") and c.get("path") == "/api/health" for c in critical
    )

    pytest_log = ARTIFACTS / "pytest_main.txt"
    pytest_text = pytest_log.read_text() if pytest_log.exists() else ""
    pytest_failed = False
    if pytest_text:
        # Look only at pytest's canonical summary line, which is the last
        # non-empty line and looks like:
        #   "= 1283 passed, 1 skipped, 190 warnings in 173s ="          (clean)
        #   "= 1 failed, 1282 passed, 1 skipped in 173s ="             (real fail)
        # Earlier behaviour grepped "FAILED" anywhere which tripped on
        # things like "ERROR ... FAILED to fetch X" inside test stdout
        # for tests that ultimately passed.
        non_empty = [ln for ln in pytest_text.strip().splitlines() if ln.strip()]
        last_line = non_empty[-1] if non_empty else ""
        m = re.search(r"(\d+)\s+failed", last_line)
        pytest_failed = bool(m and int(m.group(1)) > 0)

    # Severity
    if health_failed:
        severity = "critical"
    elif indices_issues or pytest_failed or len(ticker_issues) >= 5:
        severity = "high"
    elif ticker_issues or critical_issues:
        severity = "medium"
    else:
        severity = "none"

    total_issues = (
        len(ticker_issues) + len(indices_issues) + len(critical_issues) + (1 if pytest_failed else 0)
    )

    summary = {
        "severity": severity,
        "total_issues": total_issues,
        "ticker_issues": len(ticker_issues),
        "indices_issues": len(indices_issues),
        "critical_endpoint_issues": len(critical_issues),
        "health_failed": health_failed,
        "pytest_failed": pytest_failed,
        "ticker_scanned": len(tickers),
        "critical_probes": len(critical),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2))

    # Build markdown
    lines = []
    lines.append(f"## Nightly Bug Hunt — severity: **{severity}** ({total_issues} issues)")
    lines.append("")
    lines.append("| layer | scanned | issues |")
    lines.append("|---|---:|---:|")
    lines.append(f"| ticker-health | {len(tickers)} | {len(ticker_issues)} |")
    lines.append(f"| indices-consistency | {len(indices)} | {len(indices_issues)} |")
    lines.append(f"| critical-endpoints (9 iters) | {len(critical)} | {len(critical_issues)} |")
    lines.append(f"| pytest-main | {'ran' if pytest_text else 'skipped'} | {'FAIL' if pytest_failed else 'OK'} |")
    lines.append("")

    if health_failed:
        lines.append("### Critical — /api/health failed")
        for c in critical:
            if c.get("issue") and c.get("path") == "/api/health":
                lines.append(f"- iter {c['iter']} @ {c['ts']}: {c['reason']}  \n  body: `{c['body_preview']}`")
        lines.append("")

    if ticker_issues:
        lines.append(f"### Ticker issues ({len(ticker_issues)})")
        for t in ticker_issues[:30]:
            lines.append(f"- `{t['ticker']}` (HTTP {t['status']}, mode={t.get('mode','?')}): {t['reason']}")
        if len(ticker_issues) > 30:
            lines.append(f"- _... {len(ticker_issues)-30} more (see artifact)_")
        lines.append("")

    if indices_issues:
        lines.append(f"### Indices issues ({len(indices_issues)})")
        for i in indices_issues:
            lines.append(
                f"- [{i['region']}] `{i['index']}` level={i.get('level')} "
                f"range_52w={i.get('range_52w')} stale={i.get('is_stale')}  \n  → {i['reason']}"
            )
        lines.append("")

    if critical_issues:
        lines.append(f"### Critical endpoint issues ({len(critical_issues)})")
        # Group by path
        by_path: dict[str, list[dict]] = {}
        for c in critical_issues:
            by_path.setdefault(c["path"], []).append(c)
        for path, rs in by_path.items():
            lines.append(f"- `{path}` — {len(rs)}/9 iters failed")
            for r in rs[:3]:
                lines.append(f"  - iter {r['iter']}: {r['reason']}  body: `{r['body_preview']}`")
        lines.append("")

    if pytest_failed:
        lines.append("### pytest on main — FAILED")
        lines.append("```")
        # last 50 lines of pytest output
        tail = pytest_text.strip().splitlines()[-50:]
        lines.extend(tail)
        lines.append("```")
        lines.append("")

    if total_issues == 0:
        lines.append("### All green")
        lines.append("- No issues detected.")
        lines.append("")

    lines.append("---")
    lines.append("_Generated by `.github/workflows/nightly-bug-hunt.yml`_  ")
    lines.append("_Full raw artifacts attached to this workflow run (30-day retention)._")

    REPORT_MD.write_text("\n".join(lines))

    print(f"[aggregate] severity={severity} total_issues={total_issues}")
    print(f"[aggregate] report: {REPORT_MD}")
    print(f"[aggregate] summary: {SUMMARY_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
