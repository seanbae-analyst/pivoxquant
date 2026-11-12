"""모의 테스트 — sim.py 계산 규칙 · 시나리오 파일 · 페이지 빌드 · JS 엔진과 결과 대조."""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from pivoxpolicy import sim
from pivoxpolicy.incidents import load_incidents
from pivoxpolicy.registry import load_controls

CONTROLS = load_controls()
CIDS = [c.id for c in CONTROLS]
STAGE_OF = {c.id: c.stage for c in CONTROLS}
ENGINE_JS = Path(sim.__file__).resolve().parent / "templates" / "sim-engine.js"


def lv(**kw):
    return {c: kw.get(c, 0) for c in CIDS}


SCN = {"id": "t", "requires": ["untrusted_input"], "impact": {"by_tools": {"read": "R", "write": "W", "pay": "P"}},
       "stages": [{"checks": []},
                  {"checks": [{"control": "least_privilege", "layer": "agent", "effect": "prevent"},
                              {"control": "unique_id", "layer": "agent", "effect": "limit"}]},
                  {"checks": [{"control": "audit_trail", "layer": "agent", "effect": "detect"},
                              {"control": "kill_switch", "layer": "agent", "effect": "contain"}]}]}
ENV = {"tools": "pay", "untrusted_input": True, "open_components": False}


def test_covers_layers():
    assert sim.covers(1, "analog") and not sim.covers(1, "agent") and sim.covers(2, "agent") and not sim.covers(0, "analog")


def test_scenario_outcomes():
    assert sim.run_scenario(SCN, dict(ENV, untrusted_input=False), lv())["outcome"] == "no_surface"
    r = sim.run_scenario(SCN, ENV, lv())
    assert r["outcome"] == "damage" and r["impact"] == "P" and r["stage"] == 3
    r = sim.run_scenario(SCN, ENV, lv(least_privilege=2))
    assert (r["outcome"], r["stage"], r["steps"][-1]["blocked_by"]) == ("blocked", 2, "least_privilege")
    assert sim.run_scenario(SCN, ENV, lv(least_privilege=1))["outcome"] == "damage"   # 사람·계정만으로는 AI 층 check 를 못 덮는다
    assert sim.run_scenario(SCN, ENV, lv(unique_id=2))["outcome"] == "reduced"
    r = sim.run_scenario(SCN, ENV, lv(audit_trail=2, kill_switch=2))
    assert (r["outcome"], r["contained"], r["detected_at"]) == ("reduced", "early", 3)
    r = sim.run_scenario(SCN, ENV, lv(kill_switch=2))   # 알아챌 기록 없이 멈추면 늦다 — 피해 축소로 치지 않는다
    assert (r["outcome"], r["contained"]) == ("damage", "late")


def test_replay_bounds_and_unknown():
    f = [{"control": "least_privilege", "layer": "agent", "level": "stated"},
         {"control": "kill_switch", "layer": "analog", "level": "inferred"}]
    assert sim.replay_one([], lv(), STAGE_OF, False) == "unknown"
    assert sim.replay_one(f, lv(), STAGE_OF, False) == "unchanged"
    assert sim.replay_one(f, lv(least_privilege=2), STAGE_OF, False) == "blocked_maybe"
    assert sim.replay_one(f, lv(least_privilege=2, kill_switch=1), STAGE_OF, False) == "blocked"
    assert sim.replay_one(f, lv(kill_switch=1), STAGE_OF, False) == "reduced"
    assert sim.replay_one(f, lv(least_privilege=2), STAGE_OF, True) == "blocked"     # 원문이 적은 것만 → 추론 칸은 빠진다
    assert sim.replay_one(f[1:], lv(), STAGE_OF, True) == "unknown"
    r = sim.replay({"a": f, "b": []}, lv(least_privilege=2), STAGE_OF)
    assert (r["blocked_lo"], r["blocked_hi"], r["unknown"], r["total"]) == (0, 1, 1, 2)


def test_registry_scenarios_cover_every_incident_once():
    data = sim.load_scenarios()
    incs = load_incidents(control_ids=set(CIDS))
    assert sim.validate_scenarios(data, set(CIDS), {i.id for i in incs}) == []
    bad = {"scenarios": [{"id": "x", "impact": {"fixed": "f"}, "stages": [{"checks": [{"control": "nope", "layer": "ai", "effect": "zap"}]}],
                          "incidents": ["ghost"]}]}
    probs = " ".join(sim.validate_scenarios(bad, set(CIDS), {"real"}))
    for frag in ("모르는 통제", "layer", "effect", "why", "모르는 사건 ghost", "원형이 없는 사건 1건"):
        assert frag in probs, frag


def test_presets_follow_the_matrix():
    p = {x["id"]: x for x in sim.payload()["presets"]}
    assert set(p["none"]["levels"].values()) == {0} and set(p["all"]["levels"].values()) == {2}
    kr = p["KR-2"]["levels"]   # 한국 강제 규제: 일반 통제 7개 구속력, AI 층은 사람 승인(AI 기본법)만
    assert kr["human_approval"] == 2 and all(v == 1 for k, v in kr.items() if k != "human_approval")
    assert "INTL-2" not in p   # 국제 권고에는 구속력 문서가 없다


def test_build_writes_page(tmp_path):
    names = {q.name for q in sim.build(out_dir=tmp_path)}
    assert {"sim.html", "sim-engine.js", "sim-ui.js", "sim-data.js", "simulation.md"} <= names
    html = (tmp_path / "sim.html").read_text(encoding="utf-8")
    assert "{{" not in html and "<script>" not in html     # CSP script-src 'self' — 인라인 스크립트 없음
    assert (tmp_path / "sim-data.js").read_text(encoding="utf-8").startswith("window.PIVOX_SIM = ")


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_js_engine_matches_python(tmp_path):
    p = sim.payload()
    fails = {i["id"]: i["fails"] for i in p["incidents"]}
    rnd = random.Random(20261112)
    cases = []
    for _ in range(60):
        levels = {c: rnd.choice([0, 1, 2]) for c in CIDS}
        env = {"tools": rnd.choice(["read", "write", "pay"]), "untrusted_input": rnd.random() < 0.7, "open_components": rnd.random() < 0.5}
        cases.append({"levels": levels, "env": env, "stated": rnd.random() < 0.5})
    (tmp_path / "in.json").write_text(json.dumps({"scenarios": p["scenarios"], "fails": fails, "stage": STAGE_OF, "cases": cases}), encoding="utf-8")
    script = (
        "const E=require(process.argv[1]);const d=require(process.argv[2]);"
        "const out=d.cases.map(c=>({s:d.scenarios.map(s=>E.runScenario(s,c.env,c.levels)),"
        "r:E.replay(d.fails,c.levels,d.stage,c.stated),b:E.bestNext(d.fails,c.levels,d.stage,c.stated)}));"
        "process.stdout.write(JSON.stringify(out));"
    )
    res = subprocess.run(["node", "-e", script, str(ENGINE_JS), str(tmp_path / "in.json")], capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    for c, j in zip(cases, js):
        assert [sim.run_scenario(s, c["env"], c["levels"]) for s in p["scenarios"]] == j["s"]
        assert sim.replay(fails, c["levels"], STAGE_OF, c["stated"]) == j["r"]
        assert [list(x) for x in sim.best_next(fails, c["levels"], STAGE_OF, c["stated"])] == j["b"]


def test_regulation_basis_names_the_clause():
    p = sim.payload()
    kr = p["regulation"]["least_privilege"]["KR"]
    assert kr["analog"]["score"] == 2 and kr["analog"]["doc"] == "kr-efsr-art13" and "최소" in kr["analog"]["quote"]
    assert kr["agent"]["score"] == 1 and kr["agent"]["agent_named"]["doc"]   # AI 층은 자율 — 에이전트를 이름 붙인 자율 문서가 따로 있다
    eu = p["regulation"]["unique_id"]["EU"]
    assert eu["analog"]["score"] == 0 and "doc" not in eu["analog"]          # 다루지 않으면 문서를 싣지 않는다
    assert all(len(r[j][layer].get("quote", "")) <= 202 for r in p["regulation"].values() for j in r for layer in r[j])
    assert all(c["help"].get("analog") and c["help"].get("agent") for c in p["controls"])
