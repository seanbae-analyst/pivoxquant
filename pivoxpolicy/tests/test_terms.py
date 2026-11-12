"""용어 — 단일 출처(terms.py)와, 버린 구어체 표현이 화면 · 보고서 · 엔진에 다시 들어오지 않는지."""

from __future__ import annotations

from pathlib import Path

from pivoxpolicy import terms

ROOT = Path(__file__).resolve().parents[1]
FILES = ["pivoxpolicy/templates/runtime-ui.js", "pivoxpolicy/templates/runtime.html", "pivoxpolicy/diagnosis.py", "pivoxpolicy/obligations.py",
         "pivoxpolicy/runtime/cases.py", "pivoxpolicy/runtime/llm_redteam.py", "registry/obligations/kr-securities.yaml"]
RETIRED = ["사람 승인에 기댐", "승인 기댐", "결함(뚫림)", "업무 마찰", "처방", "설계 충돌", "위반 소지", "칸 해부", "공격 팀", "규제 공백",
           "가이드라인 미이행", "뚫리", "뚫림"]


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
