#!/usr/bin/env python3
"""Aggregate the last 24h of automation status into one Morning Brief body.

Reads from `gh` CLI (already authed by GITHUB_TOKEN env in workflow):
  1. Workflow runs in the last 24h — success vs failure counts + failed list
  2. Currently OPEN issues with automation labels (autopilot, nightly-bug-hunt)
  3. Self-Healing latest run summary (DRY RUN vs AUTO_PR mode)

Output: writes markdown body to $BRIEF_BODY_PATH (default: brief_body.md).
Stdout: nothing important — workflow reads the file path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = os.environ["GITHUB_REPOSITORY"]
OUT_PATH = Path(os.environ.get("BRIEF_BODY_PATH", "brief_body.md"))
RUN_URL_BASE = f"https://github.com/{REPO}/actions/runs"
ISSUE_URL_BASE = f"https://github.com/{REPO}/issues"

NOW = datetime.now(timezone.utc)
SINCE = NOW - timedelta(hours=24)
SINCE_ISO = SINCE.strftime("%Y-%m-%dT%H:%M:%SZ")
TODAY_KST = (NOW + timedelta(hours=9)).strftime("%Y-%m-%d")

AUTOMATION_LABELS = {
    "autopilot",
    "nightly-bug-hunt",
    "legal",
    "legal-monitor",
    "agent-health",
    "frontend-tests",
    "smoke",
    "security",
}


def gh(*args: str) -> str:
    out = subprocess.check_output(["gh", *args], text=True)
    return out.strip()


def load_runs() -> list[dict]:
    raw = gh(
        "run", "list",
        "--repo", REPO,
        "--limit", "150",
        "--json", "name,conclusion,status,createdAt,databaseId,headSha",
    )
    runs = json.loads(raw or "[]")
    return [r for r in runs if r.get("createdAt", "") >= SINCE_ISO]


def load_open_issues() -> list[dict]:
    raw = gh(
        "issue", "list",
        "--repo", REPO,
        "--state", "open",
        "--limit", "100",
        "--json", "number,title,labels,createdAt,url",
    )
    issues = json.loads(raw or "[]")
    out = []
    for i in issues:
        labels = {l["name"] for l in i.get("labels", [])}
        if labels & AUTOMATION_LABELS and "morning-brief" not in labels:
            out.append({**i, "label_set": sorted(labels & AUTOMATION_LABELS)})
    return out


def workflow_summary(runs: list[dict]) -> tuple[str, int, int]:
    by_name: dict[str, dict[str, int]] = {}
    for r in runs:
        n = r.get("name", "?")
        c = r.get("conclusion") or r.get("status") or "unknown"
        by_name.setdefault(n, {}).setdefault(c, 0)
        by_name[n][c] += 1

    success_total = sum(d.get("success", 0) for d in by_name.values())
    failure_total = sum(d.get("failure", 0) for d in by_name.values())

    lines = ["| Workflow | ✅ | ❌ | other |", "|---|---:|---:|---:|"]
    for name in sorted(by_name):
        d = by_name[name]
        s = d.get("success", 0)
        f = d.get("failure", 0)
        other = sum(v for k, v in d.items() if k not in ("success", "failure"))
        lines.append(f"| {name} | {s} | {f} | {other} |")
    return "\n".join(lines), success_total, failure_total


def failed_runs_section(runs: list[dict]) -> str:
    failed = [r for r in runs if r.get("conclusion") == "failure"]
    failed.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    if not failed:
        return "_없음 ✅_"
    lines = []
    for r in failed[:15]:
        url = f"{RUN_URL_BASE}/{r['databaseId']}"
        ts = r["createdAt"].replace("T", " ").replace("Z", " UTC")
        lines.append(f"- [{r['name']}]({url}) — {ts}")
    extra = len(failed) - 15
    if extra > 0:
        lines.append(f"- _… and {extra} more_")
    return "\n".join(lines)


def open_issues_section(issues: list[dict]) -> str:
    if not issues:
        return "_없음 ✅_"
    issues.sort(key=lambda i: i.get("createdAt", ""))
    lines = []
    for i in issues:
        labels = ", ".join(f"`{l}`" for l in i["label_set"])
        lines.append(f"- [#{i['number']}]({i['url']}) {i['title']} — {labels}")
    return "\n".join(lines)


def self_healing_status(runs: list[dict]) -> str:
    sh = [r for r in runs if "Self-Healing" in r.get("name", "")]
    if not sh:
        return "_24h 내 실행 없음_"
    sh.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    last = sh[0]
    url = f"{RUN_URL_BASE}/{last['databaseId']}"
    return f"- 마지막 실행: [{last['conclusion']}]({url}) at {last['createdAt']}\n- 모드: **DRY RUN** (AUTO_PR=0). 자동 PR 생성 비활성."


def render(runs: list[dict], issues: list[dict]) -> str:
    table, ok, fail = workflow_summary(runs)
    failed_md = failed_runs_section(runs)
    issues_md = open_issues_section(issues)
    sh_md = self_healing_status(runs)

    severity = "🟢 정상" if fail == 0 and not issues else (
        "🟡 검토 필요" if fail <= 2 and len(issues) <= 2 else "🔴 주의"
    )

    return f"""## 🌅 PivoxQuant Morning Brief — {TODAY_KST} (KST 09:00)

**상태**: {severity} · 지난 24h: ✅ {ok} / ❌ {fail} 실행

---

### 1. 워크플로우 실행 요약 (24h)

{table}

---

### 2. ❌ 실패한 실행

{failed_md}

---

### 3. 🔓 OPEN 자동화 인시던트

{issues_md}

---

### 4. 🤖 Self-Healing (Layer C) 상태

{sh_md}

> AUTO_PR=1 활성화 시 패치 후보가 Draft PR로 자동 생성됩니다 (Protected paths 제외).
> 활성화 명령:
> ```bash
> gh variable set AUTO_PR --body 1 --repo {REPO}
> ```

---

### 5. 오늘의 액션 후보
- 위 OPEN 인시던트 검토 → 필요한 것만 수동 수정 또는 spawn
- Self-Healing Draft PR 검토 (AUTO_PR=1 켰을 때)
- Frontend / Backend smoke 결과 이상 없으면 routine 작업 진행

---

_이 brief는 매일 09:00 KST에 자동 생성됩니다. 다음 brief 생성 시 이 issue는 자동 close됩니다._
/cc @seanbae-analyst
"""


def main() -> int:
    runs = load_runs()
    issues = load_open_issues()
    body = render(runs, issues)
    OUT_PATH.write_text(body, encoding="utf-8")
    print(f"Wrote brief to {OUT_PATH} ({len(body)} chars, {len(runs)} runs, {len(issues)} open issues)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
