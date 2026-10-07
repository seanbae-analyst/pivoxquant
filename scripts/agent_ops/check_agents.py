"""Agent 체계 점검 — `.claude/agents/` 가 지금 코드와 맞는지 잰다.

옛 ``propose_upgrades.py`` 를 대신한다. 그 스크립트는 HANDOVER v9(2026-04) 문자열과
아카이브된 agent(verify-policy · autopilot-monitor · frontend-test-runner) 참조를
요구해서, 2026-10-07 기준 25개 중 64건을 "고쳐라" 로 냈다 — 전부 소음이었다.
여기서는 **git 이 추적하는 입력만** 읽고, 틀릴 수 없는 것은 ERROR, 사람이 판단할 것은
WARN/INFO 로 낸다.

ERROR (``--strict`` 면 exit 1 — CI 가 쓴다)
  E1 nested       ``.claude/agents/`` 하위 폴더에 frontmatter 있는 .md. Claude Code 는
                  하위 폴더까지 agent 로 읽는다 — 보관은 ``.claude/agents-archive/``.
  E2 frontmatter  ``name`` 이 파일명과 다르거나 ``description`` 이 비었다.
  E3 workflow     ``.claude/workflows/*.md`` 의 ``agent: X`` 가 활성 agent 에 없다.

WARN
  W1 budget       description 이 agent 당 400B 또는 합계 6,000B 를 넘는다 (매 턴 로드).
  W2 archived     본문이 아카이브 agent 를 협업자로 부른다 (같은 줄에 archive 표기 없이).
  W3 dead path    본문이 가리키는 레포 경로가 없다 (같은 줄에 "삭제/없다/deleted" 면 의도).
  W4 abs path     레포를 절대경로로 가리킨다 (``cd /Users/…/pivoxquant``). 트리가 움직이면 썩는다 —
                  레포 상대경로로 (README "경로는 레포 상대경로로"). 메모리 디렉터리처럼 레포 밖은 제외.

INFO (``--no-history`` 면 건너뜀 — git 이력이 필요하다)
  I1 gap          최근 N일 커밋이 바꾼 모듈 중 어느 agent 본문에도 이름이 없는 것.
  I2 drift        agent 파일보다 나중에 바뀐, 그 agent 가 가리키는 경로 수.

    python3 scripts/agent_ops/check_agents.py                 # 리포트 stdout
    python3 scripts/agent_ops/check_agents.py --out report.md --days 30
    python3 scripts/agent_ops/check_agents.py --strict --no-history   # CI
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
AGENTS = REPO / ".claude" / "agents"
ARCHIVE = REPO / ".claude" / "agents-archive"
WORKFLOWS = REPO / ".claude" / "workflows"

DESC_MAX_BYTES = 400
DESC_TOTAL_MAX_BYTES = 6000

# 같은 줄에 있으면 "없는 것을 일부러 적었다" 로 본다.
INTENT_MARKERS = re.compile(r"grep|삭제|없다|없음|없는|사라진|지웠|폐기|deleted|removed|gone|archive|아카이브|DEPRECATED", re.I)
PATH_RE = re.compile(
    r"(?<![\w/.-])((?:services|routes|models|migrations|scripts|tests|docs|frontend/src|\.github|\.claude)"
    r"/[\w./\-\[\]()*{},]+)"
)
# 모듈 이름으로는 아무것도 말하지 않는 파일들 — 상위 폴더 이름을 쓴다.
ABS_REPO_RE = re.compile(r"/(?:Users|home)/[^\s`'\"]*/pivoxquant(?![\w-])")
GENERIC_STEMS = {"__init__", "index", "page", "layout", "route", "utils", "types", "constants", "client", "api"}
GAP_ROOTS = ("services/", "routes/", "models/", "frontend/src/lib/")


def frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def body_of(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            return text[end + 4:]
    return text


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=False).stdout


def clean_path(raw: str) -> str:
    p = raw.rstrip(".,()`'\"").split("::")[0]
    return re.sub(r":\d+(-\d+)?$", "", p).rstrip("/")


def resolve(raw: str) -> str | None:
    """레포에 있는 경로로 풀리면 그 경로, 아니면 None. ``a/b.func`` 는 ``a/b.py`` 로 본다."""
    p = clean_path(raw)
    if not p:
        return ""
    if any(c in p for c in "*{"):
        # 글롭·중괄호는 앞부분 폴더만 확인한다.
        head = re.split(r"[*{]", p)[0].rsplit("/", 1)[0]
        return head if (REPO / head).exists() else None
    if (REPO / p).exists():
        return p
    stem, _, attr = p.rpartition(".")
    if stem and attr.isidentifier() and (REPO / f"{stem}.py").exists():
        return f"{stem}.py"
    return None


def ignored(path: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO, check=False).returncode == 0


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.info: list[str] = []


def check(days: int, history: bool) -> tuple[Report, dict]:
    r = Report()
    active = {p.stem: p for p in sorted(AGENTS.glob("*.md")) if p.stem != "README"}
    archived = {p.stem for p in ARCHIVE.glob("*.md")} if ARCHIVE.exists() else set()
    texts = {n: p.read_text(encoding="utf-8") for n, p in active.items()}

    # E1 — 하위 폴더의 agent 파일
    for p in sorted(AGENTS.rglob("*.md")):
        if p.parent == AGENTS:
            continue
        fm = frontmatter(p.read_text(encoding="utf-8"))
        if fm and fm.get("name"):
            r.errors.append(f"E1 nested — `{p.relative_to(REPO)}` (name: {fm['name']}) 가 매 턴 agent 로 로드된다. `.claude/agents-archive/` 로 옮겨라")

    # E2 — frontmatter
    desc_bytes: dict[str, int] = {}
    for n, t in texts.items():
        fm = frontmatter(t)
        if fm is None:
            r.errors.append(f"E2 frontmatter — `{n}.md` 에 frontmatter 가 없다")
            continue
        if fm.get("name") != n:
            r.errors.append(f"E2 frontmatter — `{n}.md` 의 name 이 `{fm.get('name')}` (파일명과 달라야 할 이유가 없다)")
        if not fm.get("description"):
            r.errors.append(f"E2 frontmatter — `{n}.md` 의 description 이 비었다")
        desc_bytes[n] = len(fm.get("description", "").encode())

    # E3 — 워크플로 계약
    contracts: list[tuple[str, str]] = []
    for wf in sorted(WORKFLOWS.glob("*.md")) if WORKFLOWS.exists() else []:
        for m in re.finditer(r"^\s*agent:\s*([\w-]+)", wf.read_text(encoding="utf-8"), re.M):
            contracts.append((wf.name, m.group(1)))
            if m.group(1) not in active:
                where = "아카이브에 있다" if m.group(1) in archived else "어디에도 없다"
                r.errors.append(f"E3 workflow — `{wf.name}` 이 `agent: {m.group(1)}` 를 부르는데 {where}")

    # W1 — description 예산
    total = sum(desc_bytes.values())
    for n, b in sorted(desc_bytes.items(), key=lambda x: -x[1]):
        if b > DESC_MAX_BYTES:
            r.warns.append(f"W1 budget — `{n}` description {b}B > {DESC_MAX_BYTES}B. 트리거만 남기고 나머지는 본문으로")
    if total > DESC_TOTAL_MAX_BYTES:
        r.warns.append(f"W1 budget — description 합계 {total}B > {DESC_TOTAL_MAX_BYTES}B")

    # W2 / W3 — 본문 참조
    refs: dict[str, set[str]] = defaultdict(set)
    for n, t in texts.items():
        for i, line in enumerate(body_of(t).splitlines(), 1):
            intent = bool(INTENT_MARKERS.search(line))
            if ABS_REPO_RE.search(line):
                r.warns.append(f"W4 abs path — `{n}` 본문 {i}행이 레포를 절대경로로 가리킨다: {line.strip()[:100]}")
            for a in archived:
                if re.search(rf"`{re.escape(a)}`", line) and not intent:
                    r.warns.append(f"W2 archived — `{n}` 본문이 아카이브 agent `{a}` 를 부른다: {line.strip()[:110]}")
            for m in PATH_RE.finditer(line):
                raw = m.group(1)
                hit = resolve(raw)
                if hit:
                    if (REPO / hit).is_file():
                        refs[n].add(hit)  # 폴더는 늘 바뀐다 — drift 는 파일만
                elif hit is None and not intent and not ignored(clean_path(raw)):
                    r.warns.append(f"W3 dead path — `{n}`: `{clean_path(raw)}` 가 없다 — {line.strip()[:100]}")

    stats = {"active": len(active), "archived": len(archived), "desc_total": total,
             "contracts": contracts, "desc_bytes": desc_bytes}
    if not history:
        return r, stats

    # 경로 → 마지막 커밋 시각 (한 번의 git log 로)
    last_touch: dict[str, int] = {}
    ts = 0
    for line in git("log", "--name-only", "--format=@%ct", "--no-renames").splitlines():
        if line.startswith("@"):
            ts = int(line[1:])
        elif line:
            last_touch[line] = max(ts, last_touch.get(line, 0))

    # I1 — 최근 바뀐 모듈 중 아무 agent 도 이름을 모르는 것
    corpus = "\n".join(body_of(t) for t in texts.values()) + "\n".join(
        (frontmatter(t) or {}).get("description", "") for t in texts.values())
    changed = Counter()
    for line in git("log", f"--since={days} days ago", "--name-only", "--format=", "--no-merges").splitlines():
        if line.startswith(GAP_ROOTS) and (REPO / line).exists() and "/__tests__/" not in line:
            p = Path(line)
            stem = p.stem.split(".")[0]
            # 프론트 lib 의 하위 폴더(fill-ocr/ …)는 폴더가 한 모듈이다.
            nested_lib = line.startswith("frontend/src/lib/") and p.parent.name != "lib"
            key = p.parent.name if (stem in GENERIC_STEMS or nested_lib) else stem
            parent = str(p.parent.parent if nested_lib else p.parent)
            changed[(key, parent)] += 1
    gaps = []
    for (key, parent), cnt in changed.most_common():
        variants = {key, key.replace("-", "_"), key.replace("_", "-")}
        if not any(re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", corpus) for v in variants):
            gaps.append(f"I1 gap — `{parent}/{key}` 최근 {days}일 {cnt}회 변경, 어느 agent 본문에도 이름이 없다")
    r.info.extend(gaps[:20])
    if len(gaps) > 20:
        r.info.append(f"I1 gap — 외 {len(gaps) - 20}건")

    # I2 — agent 가 가리키는 경로가 agent 보다 나중에 바뀌었다
    for n in sorted(texts):
        mine = last_touch.get(str(active[n].relative_to(REPO)), 0)
        newer = []
        for p in refs[n]:
            t = max((v for k, v in last_touch.items() if k == p or k.startswith(p + "/")), default=0)
            if t > mine:
                newer.append(p)
        if newer:
            when = datetime.fromtimestamp(mine, tz=timezone.utc).strftime("%Y-%m-%d") if mine else "?"
            r.info.append(f"I2 drift — `{n}` (마지막 수정 {when}) 이후 가리키는 경로 {len(newer)}개가 바뀌었다: "
                          + ", ".join(f"`{x}`" for x in sorted(newer)[:5]) + (" …" if len(newer) > 5 else ""))
    return r, stats


def render(r: Report, stats: dict, days: int, history: bool) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = [f"# Agent 체계 점검 — {today}", "",
           f"- 활성 **{stats['active']}** · 아카이브 {stats['archived']} (`.claude/agents-archive/`, 로드 안 됨)",
           f"- description 합계 **{stats['desc_total']}B** (매 턴 로드, 예산 {DESC_TOTAL_MAX_BYTES}B)",
           f"- 워크플로 계약 {len(stats['contracts'])}건: "
           + ", ".join(sorted({f'{w}→{a}' for w, a in stats['contracts']})),
           f"- ERROR {len(r.errors)} · WARN {len(r.warns)} · INFO {len(r.info)}"
           + ("" if history else " (이력 점검 생략: --no-history)"), ""]
    for title, items in (("ERROR — 지금 고친다", r.errors), ("WARN — 판단해서 고친다", r.warns),
                         (f"INFO — 최근 {days}일 기준, agent-ops 가 본문 갱신 여부를 판단", r.info)):
        out.append(f"## {title}")
        out.extend(f"- {x}" for x in items) if items else out.append("- 없음")
        out.append("")
    out += ["## 처리", "", "- ERROR·WARN 은 이 리포트만 보고 고칠 수 있다. INFO 는 해당 코드를 읽고 agent 본문에",
            "  한 섹션을 더할지 판단한다 — **새 agent 는 기존 25개로 안 되는 이유를 README 에 적은 뒤에만.**",
            "- 규칙 SoT: `.claude/agents/README.md` · 점검기: `scripts/agent_ops/check_agents.py`"]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--strict", action="store_true", help="ERROR 가 있으면 exit 1")
    ap.add_argument("--no-history", action="store_true", help="git 이력 점검(I1·I2) 생략 — 얕은 체크아웃용")
    a = ap.parse_args()
    r, stats = check(a.days, not a.no_history)
    text = render(r, stats, a.days, not a.no_history)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    print(text)
    return 1 if (a.strict and r.errors) else 0


if __name__ == "__main__":
    sys.exit(main())
