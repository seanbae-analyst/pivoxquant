"""용어 — 단일 출처(terms.py)와, 버린 구어체 표현이 화면 · 보고서 · 엔진에 다시 들어오지 않는지."""

from __future__ import annotations

from pathlib import Path

from pivoxpolicy import terms

ROOT = Path(__file__).resolve().parents[1]
FILES = ["pivoxpolicy/templates/runtime-ui.js", "pivoxpolicy/templates/runtime.html", "pivoxpolicy/diagnosis.py", "pivoxpolicy/obligations.py",
         "pivoxpolicy/runtime/cases.py", "pivoxpolicy/runtime/llm_redteam.py", "registry/obligations/kr-securities.yaml",
         "pivoxpolicy/intake.py", "pivoxpolicy/experiment.py", "pivoxpolicy/cli.py", "pivoxpolicy/templates/sim.html",
         "registry/runtime_cases.yaml", "registry/redteam.yaml", "registry/sim_scenarios.yaml", "registry/sim_cases.yaml",
         "registry/experiment_agents.yaml", "README.md"]
RETIRED = ["사람 승인에 기댐", "승인 기댐", "결함(뚫림)", "업무 마찰", "처방", "설계 충돌", "위반 소지", "칸 해부", "공격 팀", "규제 공백",
           "가이드라인 미이행", "뚫리", "뚫린", "뚫림", "기댐", "바꿔치기", "속은 승인자", "받아 내", "몰래", "털리"]


def test_retired_terms_do_not_come_back():
    for f in FILES:
        text = (ROOT / f).read_text(encoding="utf-8")
        for w in RETIRED:
            assert w not in text, f"{f}: '{w}'"


def test_verdict_labels():
    assert terms.verdict_label("attack", "held") == "승인 의존"
    assert terms.verdict_label("attack", "defect", short=True) == "미차단"
    assert terms.verdict_label("benign", "friction", "human_approval") == "승인 대기"
    assert terms.verdict_label("benign", "friction", "least_privilege") == "과잉 차단"
    assert terms.coverage("analog", "direct") == "행위 규율" and terms.coverage("agent", None) == "AI 명시"
    d = terms.as_dict()
    assert set(d["link"]) == set(d["stop"]) == {"violation", "interpretive", "guideline", "gap"}


def test_generated_case_titles_name_the_attack_type():
    """명세에서 만든 공격 시나리오 제목은 '공격 유형: 내용' 꼴이고, 유형 이름은 terms.SCENARIO 에서 온다."""
    from pivoxpolicy import intake
    b = intake.build((ROOT / "examples" / "agent_spec_order.yaml").read_text(encoding="utf-8"))
    att = [c for c in b["cases"] if c["kind"] == "attack"]
    assert att
    for c in att:
        assert c["title"].startswith(terms.SCENARIO[c["scenario"]] + ": "), c["title"]
