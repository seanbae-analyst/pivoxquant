"""명령 흐름 — 그림이 정책 엔진의 단계별 판정(checks)을 그대로 옮기는지, 페이지 · 보고서에 들어가는지."""

from __future__ import annotations

import re

import pytest

from pivoxpolicy import experiment as X
from pivoxpolicy import flow


@pytest.fixture(scope="module")
def F():
    return X.flows()


def _lane_states(html: str) -> list[str]:
    return re.findall(r'class="fl-g s-(\w+)"', html)


def test_lane_mirrors_engine_checks(F):
    """마지막(결정) 단계의 일곱 칸 상태 = 정책 엔진 checks 의 결과. 그림이 판정을 다시 꾸미지 않는다."""
    n = 0
    for f in F.values():
        for case, rs in f["cases"]:
            for r in rs.values():
                # 승인 의존이면 레인의 마지막 펼친 단계는 '승인 뒤' 재판정이다
                src = r["if_approved"]["steps"] if r["verdict"] == "held" and r.get("if_approved") else r["steps"]
                steps = flow._last_per_step(src)
                if not steps or steps[-1].get("decision") == "no_tool":
                    continue
                want = [c[2] for c in flow._norm(steps[-1]["checks"])]
                html = flow.lane(r, case, "기준")
                full = html[html.rindex('<div class="fl-full">'):]
                assert _lane_states(full)[:7] == want
                n += 1
    assert n > 50


def test_verdicts_and_blocks_agree(F):
    """미차단이면 결정 단계에 차단 칸이 없고, 자동 차단(승인 단계를 거치지 않은)이면 차단 칸이 정확히 하나다."""
    for f in F.values():
        for case, rs in f["cases"]:
            for r in rs.values():
                if r["kind"] != "attack" or r["outcome"] == "no_surface":
                    continue
                last = flow._last_per_step(r["steps"])[-1]
                states = [c[2] for c in flow._norm(last["checks"])]
                if r["verdict"] == "defect":
                    assert "block" not in states and "approval" not in states
                if r["verdict"] == "good" and not r.get("if_approved"):
                    assert states.count("block") == 1
                if r["verdict"] == "held":
                    assert states.count("approval") == 1 and r["if_approved"]["outcome"] == "passed"


def test_flow_escapes_and_has_no_script():
    case = {"id": "x", "title": "<b>t</b>", "story": "<script>alert(1)</script>",
            "steps": [{"say": "<i>", "tool": "read", "args": {"q": "<img src=x>"}}]}
    res = {"kind": "attack", "verdict": "defect", "control": None, "outcome": "passed", "if_approved": None,
           "steps": [{"step": 1, "repeat": 1, "note": "<i>", "tool": "t<x>", "decision": "allow", "checks": [], "control": None}]}
    out = flow.compare(case, [("기준", "", res)])
    assert "<script" not in out and "<img" not in out and "&lt;img" in out


def test_experiment_page_has_flows(F):
    R = X.run()
    page = X.page(R, F)
    assert "명령 흐름" in page and page.count('class="fc-case"') == sum(len(f["cases"]) for f in F.values())
    assert "그림 2" in page and "그림 3" in page and "<svg" not in page and "<script" not in page
    # 대표 흐름은 해석 의존(명문 기준에서 미차단 · 승인 의존 → 확장 해석 기준에서 자동 차단)
    for aid, c, rs in X._featured(F):
        assert rs["binding_explicit"]["verdict"] in ("defect", "held") and rs["binding_interpretive"]["verdict"] == "good"


def test_diagnosis_report_has_flows():
    from pathlib import Path

    from pivoxpolicy import diagnosis, intake
    from pivoxpolicy import obligations as obl
    src = (Path(__file__).resolve().parents[1] / "examples" / "agent_spec_order.yaml").read_text(encoding="utf-8")
    b = intake.build(src)
    agent = {"id": "agt_t", "status": "active", "expires_at": None, **b["agent"], "compliance": b["compliance"], "cases": b["cases"]}
    D = diagnosis.diagnose(agent, b["components"], lib=obl.load_library())
    open_ = [r for r in D["attack"]["results"] if r["kind"] == "attack" and r["verdict"] in ("defect", "held")]
    h = diagnosis.to_html(D)
    assert h.count('class="fl"') == len(open_) > 0 and "<script" not in h
    md = diagnosis.to_markdown(D)
    assert "명령 흐름이다" in md
