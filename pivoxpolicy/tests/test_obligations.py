"""조항 단위 의무 — 적용성 판단 · 모드별 수준 도출 · 충족 판정 · 결함 분류."""

from __future__ import annotations

import pytest

from pivoxpolicy import obligations as O
from pivoxpolicy.runtime.policy import CONTROL_ORDER

LIB = O.load_library("securities")


def prof(**kw):
    return O.clean_profile(LIB, kw)


def test_library_is_valid():
    assert O.validate_library(LIB, set(CONTROL_ORDER)) == []
    assert LIB["reviewed_by_counsel"] is False                  # 변호사 검토 전 — 화면에 그렇게 보여야 한다
    for ob in LIB["obligations"]:                               # 원문을 확인하지 않은 인용은 싣지 않는다
        assert ob.get("quote") is None or ob.get("quote_verified") in ("registry", "primary", "secondary")


def test_profile_validation():
    p = prof(activities=["transfer", "order", "transfer"], external_llm="foreign_api", retail=True)
    assert p["activities"] == ["order", "transfer"] and p["retail"] is True and p["high_impact"] == "auto"
    for bad in ({"activities": ["fly"]}, {"external_llm": "mars"}, {"activities": "order"}):
        with pytest.raises(O.ObligationError):
            O.clean_profile(LIB, bad)
    with pytest.raises(O.ObligationError):
        O.clean_profile(LIB, [1])


def test_ai_basic_act_only_for_high_impact():
    """정산 에이전트에는 AI 기본법 제34조가 걸리지 않는다 — 관할 프리셋이 놓친 적용 조건."""
    settle = O.assess(LIB, prof(activities=["transfer"]))
    assert "aibasic-34-1-4" in {r["id"] for r in settle["not_applicable"]}
    assert settle["levels"]["binding_explicit"]["human_approval"] == 1          # AI 층 강제 의무 없음
    assert max(settle["levels"]["binding_explicit"].values()) == 1
    credit = O.assess(LIB, prof(activities=["credit"]))
    assert credit["high_impact"]["value"] is True and "추정" in credit["high_impact"]["reason"]
    assert credit["levels"]["binding_explicit"]["human_approval"] == 2
    assert credit["basis"]["binding_explicit"]["human_approval"] == ["aibasic-34-1-4"]
    # 회사가 직접 판단하면 그것을 따른다
    assert O.assess(LIB, prof(activities=["credit"], high_impact="not_high"))["levels"]["binding_explicit"]["human_approval"] == 1


def test_modes_are_monotone():
    a = O.assess(LIB, prof(activities=["order", "transfer"], external_llm="foreign_api"))
    for c in CONTROL_ORDER:
        assert a["levels"]["binding_explicit"][c] <= a["levels"]["binding_interpretive"][c] <= a["levels"]["guideline"][c]


def test_external_model_brings_outsourcing_rules():
    onprem = {r["id"] for r in O.assess(LIB, prof(external_llm="onprem"))["applicable"]}
    foreign = {r["id"] for r in O.assess(LIB, prof(external_llm="foreign_api"))["applicable"]}
    assert "outsourcing-4-3" in foreign - onprem


def test_status_partial_when_only_human_layer():
    lv = {c: 1 for c in CONTROL_ORDER}
    a = O.assess(LIB, prof(activities=["transfer"]), levels=lv)
    by = {r["id"]: r for r in a["applicable"]}
    assert by["efsr-13-1-1-access"]["status"] == "partial"     # 사람 · 계정 층은 충족, 에이전트까지는 해석 영역
    assert by["fscai-7-24"]["status"] == "unmet"                # 가이드라인은 AI 까지 요구
    assert by["efsr-37-2-5-2"]["status"] == "offline"
    a2 = O.assess(LIB, prof(activities=["transfer"]), levels={c: 2 for c in CONTROL_ORDER})
    assert a2["summary"]["unmet"] == 0 and a2["summary"]["partial"] == 0


def test_classify_violation_interpretive_gap():
    settle = O.assess(LIB, prof(activities=["transfer"]))
    assert O.classify(settle, ["least_privilege"])["kind"] == "interpretive"
    credit = O.assess(LIB, prof(activities=["credit"]))
    assert O.classify(credit, ["human_approval"])["kind"] == "violation"
    assert O.classify(settle, [])["kind"] == "gap"


def test_preset_columns():
    cols = O.preset_columns(O.assess(LIB, prof(activities=["transfer"])))
    assert [c["id"] for c in cols] == ["OB-binding_explicit", "OB-binding_interpretive", "OB-guideline"]
    assert set(cols[0]["levels"]) == set(CONTROL_ORDER)
