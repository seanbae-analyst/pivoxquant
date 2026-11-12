"""런타임 레드팀 — 공격 원형의 호출 순서(registry/redteam.yaml)를 등록된 에이전트의 정책 엔진에 흘려보낸다.

실제 저장소 상태는 건드리지 않는다(샌드박스): 에이전트를 복사해 쓰고, 승인은 받을 수 없으며(공격자이므로),
자동 중단 · 호출 빈도도 복사본 안에서만 센다. 결과마다 모의 테스트 모델(sim.run_scenario)의 예측을 같이 낸다 —
'모델이 막힌다고 본 것을 실제 정책도 막는가' 를 비교하는 자리다.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from ..registry import REGISTRY_DIR
from . import policy

PLAYBOOK_PATH = REGISTRY_DIR / "redteam.yaml"
RISK_ORDER = ("pay", "send", "exec", "write")


def load_playbook(path: Path = PLAYBOOK_PATH) -> dict[str, Any]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("scenarios") or {}


def validate_playbook(book: dict[str, Any], scenario_ids: set[str]) -> list[str]:
    probs = []
    for sid, spec in book.items():
        if sid not in scenario_ids:
            probs.append(f"{sid}: sim_scenarios 에 없는 원형")
        for k, st in enumerate(spec.get("steps") or [], 1):
            if st.get("tool") not in (*policy.KINDS, "high", "any_component"):
                probs.append(f"{sid}.{k}: tool 은 {policy.KINDS} · high · any_component")
            if not st.get("note"):
                probs.append(f"{sid}.{k}: note 필요")
        if spec.get("runtime", True) and not spec.get("steps"):
            probs.append(f"{sid}: steps 없음 (런타임 밖이면 runtime: false)")
    for sid in sorted(scenario_ids - set(book)):
        probs.append(f"{sid}: 레드팀 단계가 없다")
    return probs


def pick_tool(agent: dict[str, Any], spec: str) -> dict[str, Any] | None:
    tools = agent.get("tools") or []
    if spec == "high":
        for k in RISK_ORDER:
            t = next((t for t in tools if t["kind"] == k), None)
            if t:
                return t
        return None
    if spec == "any_component":
        return next((t for t in tools if t.get("component")), None)
    return next((t for t in tools if t["kind"] == spec), None)


def walk_steps(agent: dict[str, Any], steps: list[dict[str, Any]] | None, approved: list[dict[str, Any]],
               now=None, note_key: str = "note", approver: str = "refuse") -> dict[str, Any]:
    """단계 목록을 샌드박스 복사본의 정책 엔진으로 흘려보낸다(redteam · cases 공용).
    → {outcome: blocked|passed|no_surface, steps, stopped_at, control, detected}. 단계가 모두 허용되면 passed.
    approver: refuse — 사람 승인 요청에서 멈춘다(공격자는 승인을 받을 수 없다는 가정).
              approve — 승인자가 화면만 보고 승인한다고 치고(요약에 속거나 승인 피로) 그 요청에 묶인 승인으로 다시 묻는다.
              사람 승인을 '실패할 수 있는 통제' 로 다루려는 것이다."""
    a = copy.deepcopy(agent)
    recent, out, detected = 0, [], False
    for k, st in enumerate(steps or [], 1):
        # prefer: 이야기에 맞는 도구 이름(있으면 그것, 없으면 tool 종류로 고른다) — 첫 번째로 걸리는 도구가 이야기와 다른
        # 도구라서 결과가 바뀌는 일을 막는다(예: '결제 모듈 변조' 가 뉴스 피드 도구로 돌던 것)
        tool = next((t for t in a.get("tools") or [] if st.get("prefer") and t["name"] == st["prefer"]), None) or pick_tool(a, st["tool"])
        if tool is None:
            out.append({"step": k, "note": st.get(note_key, ""), "tool": None, "decision": "no_tool", "reason": f"{st['tool']} 도구가 등록돼 있지 않다"})
            return {"outcome": "no_surface", "steps": out, "stopped_at": k, "control": None, "detected": detected}
        for i in range(int(st.get("repeat") or 1)):
            req = {"tool": tool["name"], "action": "call", "args": dict(st.get("args") or {}), "context": dict(st.get("context") or {}),
                   "input_sources": list(st.get("input_sources") or [])}
            if st.get("component_override") and tool.get("component"):
                req["component"] = {**tool["component"], **st["component_override"]}
            if st.get("on_behalf_of"):
                req["on_behalf_of"] = st["on_behalf_of"]
            res = policy.decide(a, req, {"auth": st.get("auth", "token"), "now": now, "recent_high_risk": recent, "approval": None,
                                         "approved_components": approved})
            if res["high"] and res["decision"] != "require_approval":   # service.decide 와 같은 셈법
                recent += 1
            if res["decision"] == "require_approval" and approver == "approve":
                out.append({"step": k, "repeat": i + 1, "note": st.get(note_key, ""), "tool": tool["name"], "kind": res["kind"],
                            "decision": "require_approval", "control": "human_approval", "reason": "승인자가 승인했다(샌드박스 가정)",
                            "checks": res["checks"], "flags": res["flags"], "approved": True})
                ap = {"status": "approved", "request_hash": res["request_hash"], "agent_id": a.get("id")}
                res = policy.decide(a, req, {"auth": st.get("auth", "token"), "now": now, "recent_high_risk": recent, "approval": ap,
                                             "approved_components": approved})
                if res["high"] and res["decision"] != "require_approval":
                    recent += 1
            detected = detected or "burst" in res["flags"]
            out.append({"step": k, "repeat": i + 1, "note": st.get(note_key, ""), "tool": tool["name"], "kind": res["kind"],
                        "decision": res["decision"], "control": res["control"], "reason": res["reason"], "checks": res["checks"], "flags": res["flags"]})
            if res["suspend"]:
                a["status"] = "suspended"
            if res["decision"] != "allow":
                return {"outcome": "blocked", "steps": out, "stopped_at": k, "control": res["control"], "detected": detected}
    return {"outcome": "passed", "steps": out, "stopped_at": None, "control": None, "detected": detected}


def run(agent: dict[str, Any], sid: str, spec: dict[str, Any], approved: list[dict[str, Any]], now=None) -> dict[str, Any]:
    """원형 하나 → {scenario, outcome: blocked|damage|no_surface|runtime_na, stopped_at, control, detected, steps}."""
    if not spec.get("runtime", True):
        return {"scenario": sid, "outcome": "runtime_na", "note": spec.get("note", ""), "steps": [], "stopped_at": None, "control": None, "detected": False}
    r = walk_steps(agent, spec.get("steps"), approved, now)
    return {"scenario": sid, "outcome": "damage" if r["outcome"] == "passed" else r["outcome"],
            "steps": r["steps"], "stopped_at": r["stopped_at"], "control": r["control"], "detected": r["detected"]}


def run_all(agent: dict[str, Any], approved: list[dict[str, Any]], book: dict[str, Any] | None = None, now=None) -> dict[str, Any]:
    """모든 원형 — 런타임 결과와 모의 테스트 모델 예측을 나란히."""
    from .. import sim
    book = book if book is not None else load_playbook()
    scns = {s["id"]: s for s in sim.load_scenarios()["scenarios"]}
    rows = []
    for sid, scn in scns.items():
        spec = book.get(sid) or {"runtime": False, "note": "레드팀 단계가 없다"}
        r = run(agent, sid, spec, approved, now)
        model = sim.run_scenario(scn, agent.get("env") or {}, agent.get("levels") or {})
        r.update(title=scn["title"].split(" →")[0], model=model["outcome"], model_stage=model["stage"],
                 basis=scn.get("basis") or [], incidents=len(scn.get("incidents") or []))
        rows.append(r)
    n = {o: sum(1 for r in rows if r["outcome"] == o) for o in ("blocked", "damage", "no_surface", "runtime_na")}
    return {"agent_id": agent.get("id"), "results": rows, "summary": n}
