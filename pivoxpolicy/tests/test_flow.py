"""명령 흐름(노선도) — 그림이 정책 엔진의 관문별 판정(checks)을 그대로 옮기는지, 페이지 · 보고서에 들어가는지."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pivoxpolicy import experiment as X
from pivoxpolicy import flow


@pytest.fixture(scope="module")
def F():
    return X.flows()


def _states(html: str) -> list[str]:
    return re.findall(r'data-state="(\w+)"', html)


def _all_results(F):
    for f in F.values():
        for case, rs in f["cases"]:
            for r in rs.values():
                yield case, r


def test_nodes_mirror_engine_checks(F):
    """노선의 관문 일곱 개 = 결정 단계의 checks. 승인 의존이면 승인 관문 뒤는 '승인 뒤 재판정' 의 checks."""
    n = 0
    for case, r in _all_results(F):
        rt = flow.route(r)
        if rt is None:
            continue
        last = flow._last_per_step(r["steps"])[-1]
        want = [c[2] for c in flow._norm(last["checks"])]
        ia = r.get("if_approved")
        if last["decision"] == "require_approval" and ia and ia.get("steps"):
            after = [c[2] for c in flow._norm(flow._last_per_step(ia["steps"])[-1]["checks"])]
            want = want[:rt["at"]] + after[rt["at"]:]
        assert _states(flow.track(r, "기준")) == want
        n += 1
    assert n > 100


def test_route_matches_verdict(F):
    """미차단 → 끝까지 실선(실행됨), 승인 의존 → 승인 관문 + 점선(승인되면 실행), 자동 차단 → 끊긴 선(차단)."""
    for case, r in _all_results(F):
        if r["kind"] != "attack" or r["outcome"] == "no_surface":
            continue
        rt = flow.route(r)
        word = flow.end_word(r, rt)[0]
        if r["verdict"] == "defect":
            assert rt["end"] == "exec" and set(rt["segs"]) == {"live"} and word == "실행됨"
        elif r["verdict"] == "held":
            assert rt["end"] == "cond_exec" and rt["nodes"][rt["at"] - 1] == "approval" and "cond" in rt["segs"] and word == "승인되면 실행"
        elif r["verdict"] == "good":
            assert rt["end"] in ("block", "cond_block") and rt["alive_end"] == "dead" and word == "차단"


def test_flow_escapes_and_has_no_script():
    case = {"id": "x", "title": "<b>t</b>", "story": "<script>alert(1)</script>",
            "steps": [{"say": "<i>", "tool": "read", "args": {"q": "<img src=x>"}}]}
    res = {"kind": "attack", "verdict": "defect", "control": None, "outcome": "passed", "if_approved": None,
           "steps": [{"step": 1, "repeat": 1, "note": "<i>", "tool": "t<x>", "decision": "allow", "checks": [], "control": None}]}
    out = flow.figure(case, [("<기준>", res)])
    assert "<script" not in out and "<img" not in out and "&lt;img" in out and "&lt;기준&gt;" in out


def test_experiment_page(F):
    R = X.run()
    page = X.page(R, F)
    assert "명령 흐름" in page and "<svg" not in page and "<script" not in page
    assert page.count('<div class="fr-row">') == sum(len(f["cases"]) for f in F.values())       # 시나리오마다 한 줄
    assert page.count('class="cmp-row') == 3 and 'class="d v-' not in page                        # 그림 1: 기준 셋 막대
    assert "border-radius:50%" not in flow.CSS                                                  # 관문은 세로 막대(동그라미 없음)
    for aid, c, rs in X._featured(F):                                                            # 대표 흐름은 해석 의존
        assert rs["binding_explicit"]["verdict"] in ("defect", "held") and rs["binding_interpretive"]["verdict"] == "good"
    assert len(X._featured(F)) == 2 and "그림 2" in page and "그림 3" in page and "그림 4" in page


def test_diagnosis_report_has_flows():
    from pivoxpolicy import diagnosis, intake
    from pivoxpolicy import obligations as obl
    src = (Path(__file__).resolve().parents[1] / "examples" / "agent_spec_order.yaml").read_text(encoding="utf-8")
    b = intake.build(src)
    agent = {"id": "agt_t", "status": "active", "expires_at": None, **b["agent"], "compliance": b["compliance"], "cases": b["cases"]}
    D = diagnosis.diagnose(agent, b["components"], lib=obl.load_library())
    open_ = [r for r in D["attack"]["results"] if r["kind"] == "attack" and r["verdict"] in ("defect", "held")]
    h = diagnosis.to_html(D)
    assert h.count('<div class="fr-row">') == len(open_) > 0 and "<script" not in h
    assert "명령 흐름이다" in diagnosis.to_markdown(D)
