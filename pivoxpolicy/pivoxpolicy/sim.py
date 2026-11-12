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

3. 그 위에 얹는 두 가지 — OWASP Agentic Top 10 커버리지(항목마다 근거 원형의 결과를 모은 것, 자체 계산)와
   개선 조치(아직 AI 까지가 아닌 통제를 하나씩 올렸을 때 사건 막힘 · 원형 결과가 얼마나 바뀌는가).

통제 수준: 0 없음 · 1 사람·계정만(일반 통제 층) · 2 AI 까지(일반 + AI·에이전트 층).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .registry import OUT_DIR, REGISTRY_DIR

SCENARIOS_PATH = REGISTRY_DIR / "sim_scenarios.yaml"
CASES_PATH = REGISTRY_DIR / "sim_cases.yaml"
DISMISSED_PATH = REGISTRY_DIR / "pending_dismissed.yaml"
HISTORY_PATH = Path(__file__).resolve().parents[1] / "snapshots" / "sim_history.jsonl"
TEMPLATES = Path(__file__).resolve().parent / "templates"
EFFECTS = ("prevent", "limit", "detect", "contain")
LAYERS = ("analog", "agent")
REQUIREMENTS = ("untrusted_input", "open_components", "memory", "multi_agent")
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
        if not s.get("basis"):
            problems.append(f"{sid}: basis(근거 — 위협 목록 또는 '실제 사건') 필요")
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
    known_asi = {x.get("id") for x in (data.get("owasp_asi") or {}).get("items") or []}
    for s in data.get("scenarios") or []:
        for a in asi_of(s):
            if a not in known_asi:
                problems.append(f"{s.get('id', '?')}: basis 의 {a} 가 owasp_asi 목록에 없음")
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


# ── 3. OWASP Agentic Top 10 커버리지 · 개선 조치 ───────────────────────

ASI_RE = re.compile(r"\bOWASP (ASI\d{2})\b")
ASI_STATUS = ("full", "partial", "gap", "na", "none")


def asi_of(scn: dict[str, Any]) -> list[str]:
    """원형 basis 에 적힌 OWASP ASI 번호들 (예: 'OWASP ASI04 Agentic Supply Chain' → ASI04)."""
    return sorted({a for b in scn.get("basis") or [] for a in ASI_RE.findall(str(b))})


def asi_coverage(scenarios: list[dict[str, Any]], env: dict[str, Any], levels: dict[str, int],
                 catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OWASP ASI 항목마다 그 항목을 basis 로 둔 원형들의 결과를 모은다 — 자체 계산이고 OWASP 의 평가가 아니다.
    full = 공격면이 있는 원형이 모두 막힘 · gap = 모두 피해 발생 · partial = 그 사이(축소 포함) ·
    na = 이 환경에서 모두 공격면 없음 · none = 그 항목을 근거로 둔 원형이 없다(이 테스트가 재지 않는다)."""
    out = []
    for item in catalog:
        rows = [(s["id"], run_scenario(s, env, levels)["outcome"]) for s in scenarios if item["id"] in asi_of(s)]
        live = [o for _, o in rows if o != "no_surface"]
        if not rows:
            status = "none"
        elif not live:
            status = "na"
        elif all(o == "blocked" for o in live):
            status = "full"
        elif all(o == "damage" for o in live):
            status = "gap"
        else:
            status = "partial"
        out.append({"id": item["id"], "status": status, "scenarios": [{"id": i, "outcome": o} for i, o in rows]})
    return out


def improvement_actions(scenarios: list[dict[str, Any]], env: dict[str, Any], failures: dict[str, list[dict[str, str]]],
                        levels: dict[str, int], stage_of: dict[str, str], stated_only: bool = False) -> list[dict[str, Any]]:
    """아직 AI 까지가 아닌 통제마다 '그 통제 하나만 AI 까지 올리면' 의 효과.
    inc_lo · inc_hi = 사건 막힘 하한 · 상한 증가(하한이 상한보다 더 늘 수 있다 — '막혔을 수도' 가 '막힘' 으로 굳는 경우),
    scenarios = 결과가 바뀌는 원형(이 에이전트 환경에서).
    큰 순: 하한 증가(확실한 쪽) → 상한 증가 → 바뀌는 원형 수 → 통제 id. 점수·가중치는 매기지 않는다."""
    base_r = replay(failures, levels, stage_of, stated_only)
    base_s = {s["id"]: run_scenario(s, env, levels)["outcome"] for s in scenarios}
    out = []
    for c in sorted(levels):
        if levels[c] >= 2:
            continue
        up = dict(levels, **{c: 2})
        r = replay(failures, up, stage_of, stated_only)
        changed = []
        for s in scenarios:
            o = run_scenario(s, env, up)["outcome"]
            if o != base_s[s["id"]]:
                changed.append({"id": s["id"], "from": base_s[s["id"]], "to": o})
        out.append({"control": c, "from": int(levels[c]), "inc_lo": r["blocked_lo"] - base_r["blocked_lo"],
                    "inc_hi": r["blocked_hi"] - base_r["blocked_hi"], "scenarios": changed})
    return sorted(out, key=lambda x: (-x["inc_lo"], -x["inc_hi"], -len(x["scenarios"]), x["control"]))


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


def regulation_basis(docs, controls, coding) -> dict[str, dict[str, Any]]:
    """통제 id → 관할 → {analog|agent: {score, doc, title, url, quote}} — 그 관할에서 가장 센 문서 하나와 근거 인용.
    점수 0 이면 문서를 싣지 않는다(다루지 않음). AI 층은 자율 문서 중 에이전트를 명시한 것이 따로 있으면 agent_named 로."""
    from . import matrix as matrix_mod
    ms = matrix_mod.layer_matrices(docs, controls, coding)
    items = coding.get("items") or {}

    def short(t: str) -> str:
        return (t or "").split(" — ")[0].strip()

    def clip(t: str, n: int = 200) -> str:
        """코딩 근거(위치 + 인용) — 길면 단어 경계에서 자르고 '…'."""
        t = " ".join(t.split())
        if len(t) <= n:
            return t
        cut = t[:n].rsplit(" ", 1)[0]
        return cut.rstrip(" ,;:/") + " …"

    out: dict[str, dict[str, Any]] = {}
    for c in controls:
        row: dict[str, Any] = {}
        for j in JUR_KO:
            cell: dict[str, Any] = {}
            for layer in LAYERS:
                m = ms[layer][j][c.id]
                rec: dict[str, Any] = {"score": m.score or 0}
                if (m.score or 0) > 0 and m.top_docs:
                    d = docs[m.top_docs[0]]
                    ev = (((items.get(d.id) or {}).get(c.id) or {}).get(layer) or {}).get("evidence", "")
                    rec.update(doc=d.id, title=short(d.title), url=d.url or "", quote=clip(str(ev)))
                if layer == "agent" and m.agent_specific_voluntary:
                    v = docs[m.agent_specific_voluntary[0]]
                    rec["agent_named"] = {"doc": v.id, "title": short(v.title), "url": v.url or ""}
                cell[layer] = rec
            row[j] = cell
        out[c.id] = row
    return out


# ── 데모 케이스 ───────────────────────────────────────────────────────

OUTCOMES = ("no_surface", "blocked", "reduced", "damage")
ENV_KEYS = ("tools",) + REQUIREMENTS


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("cases") or []


def case_setup(case: dict[str, Any], presets_by_id: dict[str, Any], profiles_by_id: dict[str, Any]) -> tuple[dict[str, int], dict[str, Any]]:
    """케이스 → (통제 수준, 에이전트 환경). 프리셋 위에 levels 를, 에이전트 종류 위에 env 를 덮는다."""
    levels = dict(presets_by_id[case["preset"]]["levels"])
    levels.update({k: int(v) for k, v in (case.get("levels") or {}).items()})
    prof = profiles_by_id[case["profile"]]
    env = {k: prof.get(k) for k in ENV_KEYS}
    env.update(case.get("env") or {})
    return levels, env


def validate_cases(cases, scenarios_by_id, presets_by_id, profiles_by_id, control_ids) -> list[str]:
    problems, seen = [], set()
    for c in cases:
        cid = c.get("id", "?")
        if cid in seen:
            problems.append(f"{cid}: id 중복")
        seen.add(cid)
        for k in ("title", "org", "story", "lesson"):
            if not c.get(k):
                problems.append(f"{cid}: {k} 필요")
        if c.get("preset") not in presets_by_id:
            problems.append(f"{cid}: 모르는 preset {c.get('preset')}")
        if c.get("profile") not in profiles_by_id:
            problems.append(f"{cid}: 모르는 profile {c.get('profile')}")
        if c.get("scenario") not in scenarios_by_id:
            problems.append(f"{cid}: 모르는 scenario {c.get('scenario')}")
        if c.get("expect") not in OUTCOMES:
            problems.append(f"{cid}: expect 는 {OUTCOMES}")
        for k, v in (c.get("levels") or {}).items():
            if k not in control_ids or v not in (0, 1, 2):
                problems.append(f"{cid}: levels {k}={v}")
        for k in (c.get("env") or {}):
            if k not in ENV_KEYS:
                problems.append(f"{cid}: env {k}")
    return problems


def case_results(p: dict[str, Any]) -> list[dict[str, Any]]:
    """케이스마다 지금 데이터로 돌린 결과와 기대(expect) — 규제 데이터가 바뀌어 달라지면 ok=False."""
    pres = {x["id"]: x for x in p["presets"]}
    profs = {x["id"]: x for x in p["agent_profiles"]}
    scns = {x["id"]: x for x in p["scenarios"]}
    out = []
    for c in p.get("cases") or []:
        levels, env = case_setup(c, pres, profs)
        r = run_scenario(scns[c["scenario"]], env, levels)
        out.append({"id": c["id"], "outcome": r["outcome"], "stage": r["stage"], "expect": c["expect"], "ok": r["outcome"] == c["expect"]})
    return out


# ── 규제 업데이트 이력 ────────────────────────────────────────────────

WORST_ENV = {"tools": "pay", "untrusted_input": True, "open_components": True, "memory": True, "multi_agent": True}


def history_entry(p: dict[str, Any], doc_ids: list[str]) -> dict[str, Any]:
    """지금 레지스트리로 낸 결과의 지문 — 문서 목록 · 프리셋별 다시 돌리기 · 프리셋 × 원형 결과(가장 노출된 환경)."""
    stage_of = {c["id"]: c["stage"] for c in p["controls"]}
    fails = {i["id"]: i["fails"] for i in p["incidents"]}
    presets_out, scen_out = {}, {}
    for pr in p["presets"]:
        r = replay(fails, pr["levels"], stage_of)
        presets_out[pr["id"]] = [r["blocked_lo"], r["blocked_hi"], r["unknown"]]
        scen_out[pr["id"]] = {s["id"]: run_scenario(s, WORST_ENV, pr["levels"])["outcome"] for s in p["scenarios"]}
    return {"docs": sorted(doc_ids), "presets": presets_out, "scenarios": scen_out}


def load_history(path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_history(entry: dict[str, Any], path: Path = HISTORY_PATH, at: str | None = None, label: str | None = None) -> bool:
    """마지막 기록과 지문이 다르면 한 줄 덧붙인다(규제 문서가 들어오거나 코딩이 바뀌었을 때). 덧붙였으면 True.
    원형·케이스 정의만 바뀐 경우는 이력이 아니다 — 비교는 문서 목록과 프리셋 결과로만 한다(원형 결과는 같은 원형끼리만)."""
    from datetime import datetime, timezone
    hist = load_history(path)
    if hist:
        last = hist[-1]
        same_scn = all(last.get("scenarios", {}).get(pid, {}).get(sid, o) == o
                       for pid, row in entry["scenarios"].items() for sid, o in row.items())
        if last.get("docs") == entry["docs"] and last.get("presets") == entry["presets"] and same_scn:
            return False
        added = sorted(set(entry["docs"]) - set(last.get("docs") or []))
        removed = sorted(set(last.get("docs") or []) - set(entry["docs"]))
        auto = " · ".join([f"문서 추가 {', '.join(added)}"] * bool(added) + [f"문서 제외 {', '.join(removed)}"] * bool(removed)) or "코딩·판정 변경"
    else:
        auto = "첫 기록"
    rec = {"at": at or datetime.now(timezone.utc).strftime("%Y-%m-%d"), "label": label or auto, **entry}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    return True


# ── 반영 대기 새 규제 (자동 수집 피드에서) ─────────────────────────────

_AGENT = ("agent", "agentic", "에이전트")
_AI = ("ai act", "인공지능", "artificial intelligence", "생성형", "genai", "llm", " ai ")
_FIN = ("금융", "financial", "finance", "bank", "은행", "증권", "보험", "핀테크", "fintech", "payment", "결제")
_CTRL = ("보안", "security", "identity", "인증", "권한", "통제", "risk", "위험", "cyber", "사이버", "governance", "거버넌스", "안전", "safety")
_LAW = ("ai act", "인공지능 기본법", "ai 기본법", "가이드라인", "guideline", "guidance", "안내서", "기준", "standard", "framework", "규정", "regulation")


def _norm_url(u: str) -> str:
    """비교용 URL — 스킴·www·끝 / · 쿼리(utm_ 추적값 등)·# 을 버린다."""
    u = (u or "").strip().lower().split("#", 1)[0].split("?", 1)[0]
    return u.rstrip("/").replace("http://", "https://").replace("://www.", "://")


def pending_regulations(items, docs, dismissed: set[str] | None = None, min_score: int = 5) -> list[dict[str, Any]]:
    """피드 항목 중 '규제·가이드라인·표준' 이고 AI 에이전트·금융·통제와 닿는데 아직 레지스트리에 없는 것 — 점수순.
    점수: 에이전트 +3 · 금융 +2 · 보안·통제 +2 · 규범 말(가이드라인·기준·AI Act) +1 · 발행 주체(1차) +1."""
    known = {_norm_url(d.url) for d in docs.values() if getattr(d, "url", None)}
    dismissed = {_norm_url(u) for u in (dismissed or set())}
    out, seen = [], set()
    for it in items:
        if it.topic not in ("regulation", "guideline", "standard"):
            continue
        link = _norm_url(it.link)
        if not link or link in known or link in dismissed or link in seen:
            continue
        hay = (" ".join(it.matched or []) + " " + it.title + " " + (it.summary or "")).lower()
        if not any(w in hay for w in _AGENT + _AI):     # AI·에이전트와 닿지 않으면 후보가 아니다(양자 내성 암호 안내 같은 것)
            continue
        why, score = [], 0
        for words, pts, lab in ((_AGENT, 3, "에이전트"), (_FIN, 2, "금융"), (_CTRL, 2, "보안·통제"), (_LAW, 1, "규범")):
            if any(w in hay for w in words):
                score += pts
                why.append(lab)
        if it.kind == "primary":
            score += 1
            why.append("1차 출처")
        if score >= min_score:
            seen.add(link)
            out.append({"title": it.title, "link": it.link, "issuer": it.issuer, "jurisdiction": it.jurisdiction,
                        "published": (it.published or it.first_seen or "")[:10], "score": score, "why": why})
    out.sort(key=lambda x: x["published"], reverse=True)       # 같은 점수 안에서는 최신 먼저 (sort 는 안정적)
    return sorted(out, key=lambda x: -x["score"])


def load_dismissed(path: Path = DISMISSED_PATH) -> set[str]:
    if not path.exists():
        return set()
    return {d.get("link", "") for d in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("dismissed") or []}


def render_pending(rows: list[dict[str, Any]]) -> str:
    lines = ["# 반영 대기 — 자동 수집 피드에서 찾은 새 규제·가이드라인 후보", "",
             f"후보 **{len(rows)}**건 (점수 5 이상). 레지스트리 문서로 올릴지 사람이 정한다 — 올리면 두 팀 블라인드 코딩 → 조정 → `site` 로",
             "매트릭스 · 모의 테스트 프리셋 · 규제 근거가 다시 계산되고, 결과가 바뀌면 `snapshots/sim_history.jsonl` 에 남는다.",
             "올리지 않기로 한 것은 `registry/pending_dismissed.yaml` 에 링크를 적으면 다시 안 보인다.", "",
             "| 점수 | 날짜 | 관할 | 발행 | 제목 | 왜 |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['score']} | {r['published']} | {r['jurisdiction']} | {r['issuer']} | [{r['title']}]({r['link']}) | {' · '.join(r['why'])} |")
    return "\n".join(lines) + "\n"


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
    doc_coding = codings[primary_coder(codings)]
    helps = data.get("control_help") or {}
    pres = presets(docs, controls, doc_coding)
    cases = load_cases()
    cprobs = validate_cases(cases, {s["id"]: s for s in data["scenarios"]}, {x["id"]: x for x in pres},
                            {x["id"]: x for x in data.get("agent_profiles") or []}, {c.id for c in controls})
    if cprobs:
        raise SimError("; ".join(cprobs[:5]))
    from .intel import load_items
    try:
        pend = pending_regulations(load_items(), docs, load_dismissed())
    except FileNotFoundError:
        pend = []
    binding_docs = [d for d in docs.values() if d.binding >= 1 and d.status != "superseded"]
    return {
        "cases": cases,
        "pending": {"count": len(pend), "top": pend[:8]},
        "registry": {"docs": len(binding_docs), "latest": max((str(d.date) for d in binding_docs if d.date), default=""),
                     "doc_ids": sorted(d.id for d in binding_docs)},
        "controls": [{"id": c.id, "num": c.num, "name": c.name_ko, "stage": c.stage, "help": helps.get(c.id, {})} for c in controls],
        "regulation": regulation_basis(docs, controls, doc_coding),
        "jurisdictions": JUR_KO,
        "scenarios": data["scenarios"],
        "owasp_asi": data.get("owasp_asi") or {"source": "", "items": []},
        "agent_profiles": data.get("agent_profiles") or [],
        "presets": pres,
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
    env = {"tools": "pay", "untrusted_input": True, "open_components": True, "memory": True, "multi_agent": True}
    lines += ["", "## 시나리오 원형 — 가장 노출된 환경(송금 도구 · 외부 입력 · 외부 구성요소 · 장기 메모리 · 멀티 에이전트 모두 켬)", "",
              "| 프리셋 | " + " | ".join(s["title"].split(" →")[0] for s in p["scenarios"]) + " |",
              "|---|" + "---|" * len(p["scenarios"])]
    for pr in p["presets"]:
        cells = []
        for s in p["scenarios"]:
            r = run_scenario(s, env, pr["levels"])
            cells.append(out_ko[r["outcome"]] + (f" ({r['stage']}단계)" if r["outcome"] == "blocked" else ""))
        lines.append(f"| {pr['label']} | " + " | ".join(cells) + " |")
    asi = (p.get("owasp_asi") or {}).get("items") or []
    if asi:
        st_ko = {"full": "막음", "partial": "부분", "gap": "공백", "na": "해당 없음", "none": "원형 없음"}
        lines += ["", "## OWASP Agentic Top 10 커버리지 — 같은 환경, 자체 계산(OWASP 의 평가 아님)", "",
                  "막음 = 그 항목을 근거로 둔 원형이 모두 막힘 · 공백 = 모두 피해 발생 · 부분 = 그 사이 · 원형 없음 = 이 테스트가 재지 않는다.", "",
                  "| 프리셋 | " + " | ".join(f"{a['id']} {a['ko']}" for a in asi) + " |", "|---|" + "---|" * len(asi)]
        for pr in p["presets"]:
            cov = asi_coverage(p["scenarios"], env, pr["levels"], asi)
            lines.append(f"| {pr['label']} | " + " | ".join(st_ko[c["status"]] for c in cov) + " |")
    kr = next((x for x in p["presets"] if x["id"] == "KR-2"), None)
    if kr:
        scn_ko = {s["id"]: s["title"].split(" →")[0] for s in p["scenarios"]}
        lines += ["", "## 개선 조치 — 한국 강제 규제만 지키는 회사, 같은 환경", "",
                  "통제 하나를 AI 까지 올렸을 때의 효과(하나씩 따로 잰 값 — 더하면 안 된다). 점수·가중치는 매기지 않는다.", "",
                  "| 순위 | 통제 | 지금 | 막힘 하한 증가 | 막힘 상한 증가 | 결과가 바뀌는 원형 |", "|---|---|---|---|---|---|"]
        for k, a in enumerate(improvement_actions(p["scenarios"], env, fails, kr["levels"], stage_of), 1):
            ch = " · ".join(f"{scn_ko[x['id']]} {out_ko[x['from']]}→{out_ko[x['to']]}" for x in a["scenarios"]) or "—"
            lines.append(f"| {k} | {names[a['control']]} | {LEVEL_KO[a['from']]} | +{a['inc_lo']} | +{a['inc_hi']} | {ch} |")
    lines += ["", "원형과 단계는 저자 설계다(`registry/sim_scenarios.yaml`) — 사건 판정과 달리 블라인드 코딩을 거치지 않았다.", ""]
    return "\n".join(lines)


def _all_pending() -> list[dict[str, Any]]:
    from .intel import load_items
    from .registry import load_documents
    try:
        return pending_regulations(load_items(), load_documents(), load_dismissed())
    except FileNotFoundError:
        return []


def build(out_dir: Path = OUT_DIR, history_path: Path | None = HISTORY_PATH) -> list[Path]:
    """out/sim.html · sim-engine.js · sim-ui.js · sim-data.js · simulation.md · pending-regulations.md.
    history_path 가 있으면 결과 지문이 바뀌었을 때 이력에 한 줄 덧붙이고, 이력 전체를 페이지에 싣는다."""
    p = payload()
    if history_path is not None:
        update_history(history_entry(p, p["registry"]["doc_ids"]), history_path)
        p["history"] = load_history(history_path)
    else:
        p["history"] = []
    p["case_results"] = case_results(p)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    data_js = "window.PIVOX_SIM = " + json.dumps(p, ensure_ascii=False, separators=(",", ":")) + ";\n"
    for name, text in (("sim-data.js", data_js),
                       ("sim-engine.js", (TEMPLATES / "sim-engine.js").read_text(encoding="utf-8")),
                       ("sim-ui.js", (TEMPLATES / "sim-ui.js").read_text(encoding="utf-8")),
                       ("simulation.md", render_report(p)),
                       ("pending-regulations.md", render_pending(_all_pending()))):
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
