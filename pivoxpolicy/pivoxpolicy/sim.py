"""모의 테스트 — 통제를 켜고 끄며 AI 에이전트 공격을 다시 돌려 본다 (out/sim.html).

두 가지를 계산한다. 이 파일이 기준 구현이고, 페이지의 templates/sim-engine.js 는 같은 규칙을 옮긴 것이다
(tests/test_sim.py 가 node 로 둘의 결과를 대조한다).

1. 시나리오 모의 테스트 — registry/sim_scenarios.yaml 의 공격 원형 하나를 단계별로 걷는다.
   단계마다 그 단계에서 끼어들 수 있는 통제(check)가 켜져 있는지 보고, 막힘 · 피해 축소 · 피해 발생을 낸다.
   원형과 단계는 저자 설계다(블라인드 코딩 아님).

2. 실제 사건 다시 돌리기 — 사건 조정본(registry/incident_codings/consensus_*)이 '실패했다' 고 본 통제를 쓴다.
   반사실 가정: 그 사건에서 실패한 통제가 (그 층에서) 켜져 있었다면 사건이 막히거나 줄었을 것이다.
   막힘은 하한~상한으로 낸다 — 하한 = 실패한 통제가 모두 켜졌을 때, 상한 = 사전·사용 중 단계 통제가 하나라도 켜졌을 때.
   실패한 통제가 하나도 판정되지 않은 사건은 '판단 근거 없음' 으로 따로 센다(막힌 것도 안 막힌 것도 아니다).

통제 수준: 0 없음 · 1 사람·계정만(일반 통제 층) · 2 AI 까지(일반 + AI·에이전트 층).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .registry import OUT_DIR, REGISTRY_DIR

SCENARIOS_PATH = REGISTRY_DIR / "sim_scenarios.yaml"
TEMPLATES = Path(__file__).resolve().parent / "templates"
EFFECTS = ("prevent", "limit", "detect", "contain")
LAYERS = ("analog", "agent")
REQUIREMENTS = ("untrusted_input", "open_components")
TOOLS = ("read", "write", "pay")
LEVEL_KO = {0: "없음", 1: "사람·계정만", 2: "AI 까지"}


class SimError(ValueError):
    pass


# ── 공통 ──────────────────────────────────────────────────────────────

def covers(level: int, layer: str) -> bool:
    """통제 수준이 그 층을 덮는가 — 일반 층은 1 이상, AI 층은 2."""
    return level >= (2 if layer == "agent" else 1)


def load_scenarios(path: Path = SCENARIOS_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def validate_scenarios(data: dict[str, Any], control_ids: set[str], incident_ids: set[str]) -> list[str]:
    """시나리오 파일의 문제 목록 — 통제·층·효과 이름, 사건 id, 사건이 정확히 한 원형에 속하는지."""
    problems: list[str] = []
    seen: dict[str, str] = {}
    for s in data.get("scenarios") or []:
        sid = s.get("id", "?")
        for r in s.get("requires") or []:
            if r not in REQUIREMENTS:
                problems.append(f"{sid}: 모르는 requires {r}")
        imp = s.get("impact") or {}
        if not imp.get("fixed") and set((imp.get("by_tools") or {})) != set(TOOLS):
            problems.append(f"{sid}: impact 는 fixed 또는 by_tools(read·write·pay 모두)")
        if not s.get("stages"):
            problems.append(f"{sid}: stages 없음")
        for k, st in enumerate(s.get("stages") or [], 1):
            for c in st.get("checks") or []:
                where = f"{sid}.{k}.{c.get('control')}"
                if c.get("control") not in control_ids:
                    problems.append(f"{where}: 모르는 통제")
                if c.get("layer") not in LAYERS:
                    problems.append(f"{where}: layer 는 analog/agent")
                if c.get("effect") not in EFFECTS:
                    problems.append(f"{where}: effect 는 {EFFECTS}")
                if not c.get("why"):
                    problems.append(f"{where}: why 필요")
        for i in s.get("incidents") or []:
            if i not in incident_ids:
                problems.append(f"{sid}: 모르는 사건 {i}")
            elif i in seen:
                problems.append(f"{i}: {seen[i]} 와 {sid} 두 원형에 있음")
            seen[i] = sid
    missing = sorted(incident_ids - set(seen))
    if missing:
        problems.append(f"원형이 없는 사건 {len(missing)}건: {', '.join(missing)}")
    return problems


# ── 1. 시나리오 모의 테스트 ────────────────────────────────────────────

def run_scenario(scn: dict[str, Any], env: dict[str, Any], levels: dict[str, int]) -> dict[str, Any]:
    """공격 원형 하나를 단계별로 걷는다.
    env = {tools: read|write|pay, untrusted_input: bool, open_components: bool}, levels = 통제 id → 0|1|2.
    결과 outcome: no_surface(공격면 없음) · blocked(막힘) · reduced(피해 축소) · damage(피해 발생)."""
    missing = [r for r in scn.get("requires") or [] if not env.get(r)]
    imp = scn.get("impact") or {}
    impact = imp.get("fixed") or (imp.get("by_tools") or {}).get(env.get("tools", "read"), "")
    steps: list[dict[str, Any]] = []
    if missing:
        return {"outcome": "no_surface", "stage": 0, "missing": missing, "steps": steps, "impact": impact,
                "limited_by": [], "detected_at": None, "contained": None}
    limited_by: list[str] = []
    detected_at: int | None = None
    contained: str | None = None            # 'early' | 'late' | None
    for k, st in enumerate(scn.get("stages") or [], 1):
        checks = []
        blocked_by = None
        for c in st.get("checks") or []:
            on = covers(int(levels.get(c["control"], 0)), c["layer"])
            checks.append({"control": c["control"], "layer": c["layer"], "effect": c["effect"], "on": on})
            if not on:
                continue
            if c["effect"] == "prevent" and blocked_by is None:
                blocked_by = c["control"]
            elif c["effect"] == "limit":
                limited_by.append(c["control"])
            elif c["effect"] == "detect" and detected_at is None:
                detected_at = k
            elif c["effect"] == "contain":
                contained = "early" if detected_at is not None else "late"
        steps.append({"stage": k, "checks": checks, "blocked_by": blocked_by})
        if blocked_by:
            return {"outcome": "blocked", "stage": k, "missing": [], "steps": steps, "impact": impact,
                    "limited_by": limited_by, "detected_at": detected_at, "contained": contained}
    reduced = bool(limited_by) or contained == "early"
    return {"outcome": "reduced" if reduced else "damage", "stage": len(steps), "missing": [], "steps": steps,
            "impact": impact, "limited_by": limited_by, "detected_at": detected_at, "contained": contained}


# ── 2. 실제 사건 다시 돌리기 ───────────────────────────────────────────

def incident_failures(consensus: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """조정본 → 사건 id → [{control, layer, level}] (실패로 판정된 칸만)."""
    out: dict[str, list[dict[str, str]]] = {}
    for iid, rec in (consensus.get("incidents") or {}).items():
        out[iid] = [{"control": c, "layer": cell.get("layer"), "level": cell.get("level")}
                    for c, cell in ((rec or {}).get("controls") or {}).items() if (cell or {}).get("failed") is True]
    return out


def replay_one(fails: list[dict[str, str]], levels: dict[str, int], stage_of: dict[str, str], stated_only: bool) -> str:
    """사건 하나 → blocked(하한에도 듦) · blocked_maybe(상한에만) · reduced · unchanged · unknown."""
    fs = [f for f in fails if f.get("level") == "stated"] if stated_only else list(fails)
    if not fs:
        return "unknown"
    cov = [f for f in fs if covers(int(levels.get(f["control"], 0)), f["layer"])]
    early = [f for f in cov if stage_of.get(f["control"]) != "after"]
    if early and len(cov) == len(fs):
        return "blocked"
    if early:
        return "blocked_maybe"
    if cov:
        return "reduced"
    return "unchanged"


def replay(failures: dict[str, list[dict[str, str]]], levels: dict[str, int], stage_of: dict[str, str],
           stated_only: bool = False) -> dict[str, Any]:
    per = {iid: replay_one(f, levels, stage_of, stated_only) for iid, f in sorted(failures.items())}
    n = {k: sum(1 for v in per.values() if v == k) for k in ("blocked", "blocked_maybe", "reduced", "unchanged", "unknown")}
    return {"per": per, "blocked_lo": n["blocked"], "blocked_hi": n["blocked"] + n["blocked_maybe"],
            "reduced": n["reduced"], "unchanged": n["unchanged"], "unknown": n["unknown"], "total": len(per)}


def best_next(failures, levels, stage_of, stated_only=False) -> list[tuple[str, int]]:
    """아직 AI 까지 켜지지 않은 통제를 하나씩 2 로 올렸을 때 막힘 상한이 얼마나 느는가 — 큰 순."""
    base = replay(failures, levels, stage_of, stated_only)["blocked_hi"]
    out = []
    for c in sorted(levels):
        if levels[c] >= 2:
            continue
        up = dict(levels, **{c: 2})
        out.append((c, replay(failures, up, stage_of, stated_only)["blocked_hi"] - base))
    return sorted(out, key=lambda x: (-x[1], x[0]))


# ── 규제 프리셋 ───────────────────────────────────────────────────────

JUR_KO = {"KR": "한국", "US": "미국", "EU": "EU", "INTL": "국제 권고"}


def presets(docs, controls, coding) -> list[dict[str, Any]]:
    """관할마다 '규제가 강제하는 것만 지키는 회사'(구속력 2) · '자율 가이드라인까지 지키는 회사'(1 이상).
    통제 수준 = AI 층 점수가 문턱 이상이면 2, 아니고 일반 층이 문턱 이상이면 1, 둘 다 아니면 0."""
    from . import matrix as matrix_mod
    ms = matrix_mod.layer_matrices(docs, controls, coding)
    out = [{"id": "none", "label": "통제 없음", "levels": {c.id: 0 for c in controls}},
           {"id": "all", "label": "모든 통제를 AI 까지", "levels": {c.id: 2 for c in controls}}]
    for j in ("KR", "US", "EU", "INTL"):
        for thr, suffix in ((2, "강제 규제만"), (1, "가이드라인까지")):
            if j == "INTL" and thr == 2:
                continue           # 국제 권고에는 구속력 문서가 없다
            lv = {}
            for c in controls:
                a = ms["analog"][j][c.id].score or 0
                g = ms["agent"][j][c.id].score or 0
                lv[c.id] = 2 if g >= thr else (1 if a >= thr else 0)
            out.append({"id": f"{j}-{thr}", "label": f"{JUR_KO[j]} — {suffix}", "levels": lv})
    return out


# ── 페이지 데이터 · 빌드 ──────────────────────────────────────────────

def payload() -> dict[str, Any]:
    from . import agreement as agreement_mod
    from . import incidents as incidents_mod
    from .registry import load_codings, load_controls, load_documents
    from .schema import primary_coder
    controls = load_controls()
    docs = load_documents()
    codings = load_codings()
    incs = incidents_mod.load_incidents(control_ids={c.id for c in controls})
    raws = agreement_mod.load_incident_codings()
    adj = next((n for n in sorted(raws) if agreement_mod.is_incident_adjudicated(raws[n])), None)
    if adj is None:
        raise SimError("사건 조정본(registry/incident_codings/consensus_*)이 없다")
    data = load_scenarios()
    probs = validate_scenarios(data, {c.id for c in controls}, {i.id for i in incs})
    if probs:
        raise SimError("; ".join(probs[:5]))
    scen_of = {i: s["id"] for s in data["scenarios"] for i in s["incidents"]}
    fails = incident_failures(raws[adj])
    return {
        "controls": [{"id": c.id, "num": c.num, "name": c.name_ko, "stage": c.stage} for c in controls],
        "scenarios": data["scenarios"],
        "agent_profiles": data.get("agent_profiles") or [],
        "presets": presets(docs, controls, codings[primary_coder(codings)]),
        "incidents": [{"id": i.id, "title": i.title, "date": i.date, "url": i.source_url, "role": i.ai_role,
                       "evidence": i.evidence_level, "scenario": scen_of.get(i.id), "fails": fails.get(i.id, [])}
                      for i in sorted(incs, key=lambda x: x.date, reverse=True)],
        "sources": {"incident_coding": adj, "doc_coding": primary_coder(codings)},
    }


def render_report(p: dict[str, Any]) -> str:
    """논문·발표용 표 — 규제 프리셋마다 실제 사건 다시 돌리기 결과, 원형마다 시나리오 결과."""
    stage_of = {c["id"]: c["stage"] for c in p["controls"]}
    fails = {i["id"]: i["fails"] for i in p["incidents"]}
    names = {c["id"]: c["name"] for c in p["controls"]}
    lines = ["# 모의 테스트 — 규제 프리셋별 결과", "",
             f"사건 {len(fails)}건 · 사건 판정 `{p['sources']['incident_coding']}` · 규제 매트릭스 `{p['sources']['doc_coding']}`.",
             "반사실 가정: 사건에서 실패한 통제가 그 층에서 켜져 있었다면 막혔거나 줄었을 것이다. 막힘 = 하한~상한.",
             "", "## 실제 사건 다시 돌리기", "",
             "| 프리셋 | 막힘 (적었거나 추론) | 피해 축소 | 그대로 | 판단 근거 없음 | 막힘 (원문이 적은 것만) | 다음에 켤 통제 |",
             "|---|---|---|---|---|---|---|"]
    for pr in p["presets"]:
        r = replay(fails, pr["levels"], stage_of)
        rs = replay(fails, pr["levels"], stage_of, stated_only=True)
        nxt = [f"{names[c]} +{d}" for c, d in best_next(fails, pr["levels"], stage_of)[:2] if d > 0]
        lines.append(f"| {pr['label']} | **{r['blocked_lo']}~{r['blocked_hi']}** | {r['reduced']} | {r['unchanged']} | {r['unknown']} | "
                     f"{rs['blocked_lo']}~{rs['blocked_hi']} | {' · '.join(nxt) or '—'} |")
    out_ko = {"no_surface": "공격면 없음", "blocked": "막힘", "reduced": "피해 축소", "damage": "피해 발생"}
    env = {"tools": "pay", "untrusted_input": True, "open_components": True}
    lines += ["", "## 시나리오 원형 — 가장 노출된 환경(송금 도구 · 외부 입력 읽음 · 외부 구성요소 들임)", "",
              "| 프리셋 | " + " | ".join(s["title"].split(" →")[0] for s in p["scenarios"]) + " |",
              "|---|" + "---|" * len(p["scenarios"])]
    for pr in p["presets"]:
        cells = []
        for s in p["scenarios"]:
            r = run_scenario(s, env, pr["levels"])
            cells.append(out_ko[r["outcome"]] + (f" ({r['stage']}단계)" if r["outcome"] == "blocked" else ""))
        lines.append(f"| {pr['label']} | " + " | ".join(cells) + " |")
    lines += ["", "원형과 단계는 저자 설계다(`registry/sim_scenarios.yaml`) — 사건 판정과 달리 블라인드 코딩을 거치지 않았다.", ""]
    return "\n".join(lines)


def build(out_dir: Path = OUT_DIR) -> list[Path]:
    """out/sim.html · sim-engine.js · sim-ui.js · sim-data.js · simulation.md"""
    p = payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    data_js = "window.PIVOX_SIM = " + json.dumps(p, ensure_ascii=False, separators=(",", ":")) + ";\n"
    for name, text in (("sim-data.js", data_js),
                       ("sim-engine.js", (TEMPLATES / "sim-engine.js").read_text(encoding="utf-8")),
                       ("sim-ui.js", (TEMPLATES / "sim-ui.js").read_text(encoding="utf-8")),
                       ("simulation.md", render_report(p))):
        (out_dir / name).write_text(text, encoding="utf-8")
        written.append(out_dir / name)
    html = (TEMPLATES / "sim.html").read_text(encoding="utf-8")
    for k, v in {"TOKENS_CSS": (TEMPLATES / "tokens.css").read_text(encoding="utf-8"),
                 "BASE_CSS": (TEMPLATES / "base.css").read_text(encoding="utf-8"),
                 "SIM_CSS": (TEMPLATES / "sim.css").read_text(encoding="utf-8"),
                 "N_INCIDENTS": str(len(p["incidents"])), "N_SCENARIOS": str(len(p["scenarios"]))}.items():
        html = html.replace("{{" + k + "}}", v)
    (out_dir / "sim.html").write_text(html, encoding="utf-8")
    written.append(out_dir / "sim.html")
    return written
