"""런타임 데모 케이스 — '공격하는 팀'(공격 케이스 모음)과 정상 업무를 등록된 에이전트에 흘려보낸다.

두 가지 방식:
  run_cases(agent, …)   — 지금 통제 그대로 각 케이스를 돌린다.
  run_matrix(agent, …)  — 케이스 × 규제 프리셋. 같은 에이전트를 관할 프리셋 수준으로 바꿔(샌드박스 복사본)
                          돌려, 규제마다 어디서 막히고 어디가 뚫리는지 한 표로 낸다.

실제 저장소는 건드리지 않는다(redteam.py 와 같은 샌드박스). 공격자는 사람 승인을 받을 수 없으므로 승인 요청에서
멈추면 '막힘' 으로 센다. 판정(verdict): 공격이 통과하면 결함(defect), 정상 업무가 막히면 업무 마찰(friction).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from ..registry import REGISTRY_DIR
from . import policy, redteam

CASES_PATH = REGISTRY_DIR / "runtime_cases.yaml"
STEP_TOOLS = (*policy.KINDS, "high", "any_component")


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("cases") or []


def validate_cases(cases: list[dict[str, Any]], scenario_ids: set[str]) -> list[str]:
    probs, seen = [], set()
    for c in cases:
        cid = c.get("id")
        if not cid or cid in seen:
            probs.append(f"{cid}: id 가 없거나 중복")
        seen.add(cid)
        if c.get("kind") not in ("attack", "benign"):
            probs.append(f"{cid}: kind 는 attack · benign")
        if c.get("scenario") and c["scenario"] not in scenario_ids:
            probs.append(f"{cid}: sim_scenarios 에 없는 원형 {c.get('scenario')}")
        for k, st in enumerate(c.get("steps") or [], 1):
            if st.get("tool") not in STEP_TOOLS:
                probs.append(f"{cid}.{k}: tool 은 {policy.KINDS} · high · any_component")
            if not st.get("say"):
                probs.append(f"{cid}.{k}: say 필요")
        if not c.get("steps"):
            probs.append(f"{cid}: steps 없음")
    return probs


def verdict(kind: str, outcome: str) -> str:
    """케이스 종류 × 결과 → good · defect · friction · na.
    공격은 막혀야 제대로(통과하면 결함), 정상 업무는 처리돼야 제대로(막히면 업무 마찰)."""
    if outcome == "no_surface":
        return "na"
    if kind == "attack":
        return "good" if outcome == "blocked" else "defect"
    return "good" if outcome == "passed" else "friction"


def run_case(agent: dict[str, Any], case: dict[str, Any], approved: list[dict[str, Any]], now=None) -> dict[str, Any]:
    r = redteam.walk_steps(agent, case.get("steps"), approved, now, note_key="say")
    return {"id": case["id"], "kind": case.get("kind"), "title": case.get("title", case["id"]), "scenario": case.get("scenario"),
            "outcome": r["outcome"], "verdict": verdict(case.get("kind", "attack"), r["outcome"]),
            "stopped_at": r["stopped_at"], "control": r["control"], "detected": r["detected"], "steps": r["steps"]}


def run_cases(agent: dict[str, Any], cases: list[dict[str, Any]] | None = None,
              approved: list[dict[str, Any]] | None = None, now=None) -> dict[str, Any]:
    cases = cases if cases is not None else load_cases()
    approved = approved if approved is not None else []
    rows = [run_case(agent, c, approved, now) for c in cases]
    summary = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("good", "defect", "friction", "na")}
    return {"agent_id": agent.get("id"), "results": rows, "summary": summary}


def with_levels(agent: dict[str, Any], levels: dict[str, int]) -> dict[str, Any]:
    """통제 수준만 바꾼 샌드박스 복사본 — 환경·도구·한도·위임은 그대로 둔다."""
    a = copy.deepcopy(agent)
    a["levels"] = {c: int((levels or {}).get(c, 0)) for c in policy.CONTROL_ORDER}
    return a


def run_matrix(agent: dict[str, Any], presets: list[dict[str, Any]], cases: list[dict[str, Any]] | None = None,
               approved: list[dict[str, Any]] | None = None, now=None) -> dict[str, Any]:
    """케이스 × 규제 프리셋 — 프리셋마다 그 수준으로 바꿔 모든 케이스를 돌린다.
    presets: [{id, label, levels}]. 반환: {cases:[…], presets:[{preset, label, levels, summary, cells{case_id:{…}}}]}."""
    cases = cases if cases is not None else load_cases()
    approved = approved if approved is not None else []
    cols = []
    for pr in presets:
        res = run_cases(with_levels(agent, pr.get("levels") or {}), cases, approved, now)
        cols.append({"preset": pr["id"], "label": pr.get("label", pr["id"]), "levels": pr.get("levels") or {},
                     "summary": res["summary"],
                     "cells": {r["id"]: {"outcome": r["outcome"], "verdict": r["verdict"], "control": r["control"],
                                         "stopped_at": r["stopped_at"], "detected": r["detected"]} for r in res["results"]}})
    return {"agent_id": agent.get("id"),
            "cases": [{"id": c["id"], "kind": c.get("kind"), "title": c.get("title", c["id"]),
                       "story": c.get("story", ""), "scenario": c.get("scenario")} for c in cases],
            "presets": cols}
