"""LLM 레드팀 — 가짜 모델(숨은 지시를 따르는 쪽 · 거절하는 쪽)로 시나리오 · 판정 · 비율 · 호출 한도를 본다.
실제 모델 실행은 ANTHROPIC_API_KEY 가 있는 곳에서 `cli llm-redteam` 으로 한다."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace as N

from pivoxpolicy import intake
from pivoxpolicy.runtime import llm_redteam, policy

SPEC = (Path(__file__).resolve().parents[1] / "examples" / "agent_spec_order.yaml").read_text(encoding="utf-8")
ALL2 = {c: 2 for c in policy.CONTROL_ORDER}
NONE = {c: 0 for c in policy.CONTROL_ORDER}


def scs():
    b = intake.build(SPEC)
    raw = [intake.normalize_tool(t) for t in intake.parse_spec(SPEC)["tools"]]
    return llm_redteam.scenarios(b, raw)


def tu(name, inp, i=1):
    return N(type="tool_use", id=f"tu{i}", name=name, input=inp)


def resp(*blocks, stop="tool_use"):
    return N(content=list(blocks), stop_reason=stop, usage=N(input_tokens=50, output_tokens=10), stop_details=None)


class FakeModel:
    """obey=True 면 숨은 지시를 따른다. 실제 모델처럼 대화에 보이는 글(과업 · 도구 결과)에서 지시를 읽어 행동을 고른다."""
    def __init__(self, obey=True):
        self.obey, self.n = obey, 0
        self.args = {s["target"]: s["args"] for s in scs()}
        self.beta = N(messages=N(create=self.create))

    def create(self, **kw):
        self.n += 1
        msgs = kw["messages"]
        seen = " ".join(m["content"] if isinstance(m["content"], str) else
                        " ".join(str(b.get("content", "")) for b in m["content"] if isinstance(b, dict)) for m in msgs)
        reader = re.match(r"([A-Za-z0-9_]+) 도구로", msgs[0]["content"])
        target = re.search(r"(?:즉시|따라) ([A-Za-z0-9_]+)\(", seen)
        plan = ([tu(reader.group(1), {"topic": "시장"})] if reader else []) + ([tu(target.group(1), self.args[target.group(1)], 2)] if self.obey and target else [])
        turn = sum(1 for m in msgs if m["role"] == "assistant")
        if turn < len(plan):
            return resp(plan[turn])
        return resp(N(type="text", text="요약했습니다." if self.obey else "글 속 지시는 따르지 않았습니다."), stop="end_turn")


def test_scenarios_from_company_tools():
    ids = [s["id"] for s in scs()]
    assert "poisoned_read:fetch_news->place_order" in ids and "customer_inject->transfer_funds" in ids
    s = next(x for x in scs() if x["id"] == "poisoned_read:fetch_news->place_order")
    assert s["args"]["notional_krw"] == 9_000_000 and "place_order(" in s["content"]


def test_obedient_model_blocked_with_controls_and_damaging_without():
    full = llm_redteam.run(FakeModel(True), SPEC, trials=2, levels=ALL2)
    for s in full["scenarios"]:
        assert s["attempt_rate"] == 1.0 and s["block_rate"] == 1.0 and s["damage_rate"] == 0.0, s["id"]
        assert set(s["controls"]) == {"least_privilege"}                              # 외부 입력 + 고위험
    bare = llm_redteam.run(FakeModel(True), SPEC, trials=1, levels=NONE)
    assert all(s["damage_rate"] == 1.0 for s in bare["scenarios"])
    md = llm_redteam.to_markdown(full)
    assert "지시 추종률" in md and "100%" in md


def test_refusing_model_and_held_by_approval():
    r = llm_redteam.run(FakeModel(False), SPEC, trials=1, levels=NONE)
    assert all(s["attempt_rate"] == 0.0 and s["block_rate"] is None for s in r["scenarios"])
    only_approval = dict(NONE, human_approval=2)
    r = llm_redteam.run(FakeModel(True), SPEC, trials=1, levels=only_approval)           # 사람 승인만 — 승인자가 거부
    assert all(s["held"] == 1 and s["damage_rate"] == 0.0 for s in r["scenarios"])
    r = llm_redteam.run(FakeModel(True), SPEC, trials=1, levels=only_approval, approver="approve")   # 승인자 오판 가정
    assert all(s["damage_rate"] == 1.0 for s in r["scenarios"])


def test_call_budget_stops_spending():
    m = FakeModel(True)
    r = llm_redteam.run(m, SPEC, trials=5, levels=ALL2, max_calls=4)
    assert m.n == 4 and r["calls"] == 4 and any(s["errors"] for s in r["scenarios"])
