"""런타임 데모 케이스 — '공격 팀' 케이스가 현재 통제 그대로, 그리고 규제 프리셋 × 케이스 행렬로 돈다."""

from __future__ import annotations

from datetime import datetime, timezone

from pivoxpolicy import sim
from pivoxpolicy.runtime import cases, policy

from tests.test_runtime import ALL2, APPROVED, NONE, agent

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def test_case_library_is_valid():
    cs = cases.load_cases()
    ids = {s["id"] for s in sim.load_scenarios()["scenarios"]}
    assert cases.validate_cases(cs, ids) == []
    kinds = {c["id"]: c["kind"] for c in cs}
    assert sum(v == "attack" for v in kinds.values()) >= 8      # 공격 팀
    assert "benign" in kinds.values()                           # 정상 업무도 있다


def test_no_controls_every_attack_is_a_defect():
    res = cases.run_cases(agent(NONE), approved=APPROVED, now=NOW)
    by = {r["id"]: r for r in res["results"]}
    # 트레이딩 에이전트에 송금 도구가 있어 고위험 케이스는 공격면이 있고, 통제가 없으면 전부 뚫린다(통과 → 결함)
    assert by["news-injection"]["verdict"] == "defect" and by["news-injection"]["outcome"] == "passed"
    assert res["summary"]["defect"] >= 6
    assert res["summary"]["good"] == 0 or all(r["kind"] == "benign" for r in res["results"] if r["verdict"] == "good")


def test_full_controls_block_attacks_but_add_friction():
    res = cases.run_cases(agent(ALL2), approved=APPROVED, now=NOW)
    by = {r["id"]: r for r in res["results"]}
    assert by["news-injection"]["verdict"] == "good" and by["news-injection"]["control"] == "least_privilege"
    # 정상 송금은 사람 승인에서 멈춘다 → 업무 마찰(결함이 아니라 트레이드오프)
    assert by["normal-settlement"]["verdict"] == "friction"
    assert by["normal-lookup"]["verdict"] == "good"             # 조회는 통제를 다 켜도 처리된다
    assert res["summary"]["defect"] == 0


def test_runtime_matrix_shape_and_regime_gradient():
    presets = [{"id": "none", "label": "통제 없음", "levels": NONE},
               {"id": "US-2", "label": "미국 강제", "levels": dict(NONE, inventory=1, least_privilege=1, human_approval=1, audit_trail=1, kill_switch=1)},
               {"id": "all", "label": "모두 AI까지", "levels": ALL2}]
    m = cases.run_matrix(agent(ALL2), presets, approved=APPROVED, now=NOW)
    assert [c["id"] for c in m["cases"]] == [c["id"] for c in cases.load_cases()]
    cols = {p["preset"]: p for p in m["presets"]}
    assert cols["none"]["summary"]["defect"] > cols["all"]["summary"]["defect"]   # 규제가 셀수록 결함이 준다
    assert cols["none"]["cells"]["news-injection"]["verdict"] == "defect"
    assert cols["all"]["cells"]["news-injection"]["verdict"] == "good"


def test_matrix_sandbox_does_not_mutate_agent():
    a = agent(ALL2)
    before = dict(a["levels"])
    cases.run_matrix(a, [{"id": "none", "label": "x", "levels": NONE}], approved=APPROVED, now=NOW)
    assert a["levels"] == before and a["status"] == "active"
