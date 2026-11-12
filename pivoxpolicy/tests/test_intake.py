"""에이전트 명세 가져오기 — 도구 형식 정규화 · 종류 추정 · 프로필 · 케이스 생성 · 한도 인자."""

from __future__ import annotations

from pathlib import Path

import pytest

from pivoxpolicy import intake, sim
from pivoxpolicy.runtime import cases, policy

SPEC = (Path(__file__).resolve().parents[1] / "examples" / "agent_spec_order.yaml").read_text(encoding="utf-8")
ALL2 = {c: 2 for c in policy.CONTROL_ORDER}


def tool(**kw):
    return intake.normalize_tool(kw)


def test_formats_and_kinds():
    r = intake.build(SPEC)
    by = {t["name"]: t for t in r["tools"]}
    assert {t["format"] for t in r["tools"]} == {"anthropic", "openai", "mcp"}
    assert by["get_quote"]["kind"] == "read" and by["fetch_news"]["external"] is True
    assert by["place_order"]["kind"] == "pay" and by["place_order"]["amount_arg"] == "notional_krw"
    assert by["transfer_funds"]["kind"] == "pay" and by["send_email"]["kind"] == "send"
    assert by["lookup_account"]["customer_arg"] == "customer_id"
    assert r["compliance"]["activities"] == ["order", "transfer", "customer_service"]
    assert r["compliance"]["external_llm"] == "foreign_api" and r["compliance"]["retail"] is True
    assert {c["name"] for c in r["components"]} == {"broker-gw", "pay-gateway-mcp"}


def test_verb_first_kind_inference():
    assert intake.infer_kind(tool(name="get_order_status", description="주문 상태를 본다"))[0] == "read"
    assert intake.infer_kind(tool(name="createOrder"))[0] == "pay"
    assert intake.infer_kind(tool(name="run_sql"))[0] == "exec"
    assert intake.infer_kind(tool(name="notify_customer"))[0] == "send"
    assert intake.infer_kind(tool(name="update_crm"))[0] == "write"
    k, why, conf = intake.infer_kind(tool(name="frobnicate"))
    assert (k, conf) == ("write", "low") and "보수적" in why
    assert intake.infer_kind(tool(name="req_vendor", description="거래처로 송금한다"))[:2] == ("pay", "설명에 '송금'")


def test_generated_cases_use_real_tools_and_are_valid():
    r = intake.build(SPEC)
    ids = {s["id"] for s in sim.load_scenarios()["scenarios"]}
    assert cases.validate_cases(r["cases"], ids) == []
    by = {c["id"]: c for c in r["cases"]}
    inj = by["gen-injection-place_order"]["steps"]
    assert inj[0]["prefer"] == "fetch_news" and inj[1]["prefer"] == "place_order"
    assert inj[1]["args"]["notional_krw"] == 9_000_000 and inj[1]["args"]["side"] == "buy"
    assert by["gen-other-customer-lookup_account"]["steps"][0]["args"] == {"customer_id": "c-777"}


def test_imported_agent_runs_against_its_own_cases():
    """가져온 에이전트를 그 에이전트의 케이스로 돌린다 — 금액 인자 이름이 달라도 한도가 걸린다."""
    r = intake.build(SPEC)
    a = {"id": "agt_imported01", "status": "active", "expires_at": None, **r["agent"]}
    approved = r["components"]
    res = cases.run_cases({**a, "levels": ALL2}, r["cases"], approved)
    by = {x["id"]: x for x in res["results"]}
    assert res["summary"]["defect"] == 0
    assert by["gen-insider-place_order"]["control"] == "least_privilege"         # notional_krw 8,000만 > 한도 500만
    assert by["gen-other-customer-lookup_account"]["control"] == "least_privilege"
    assert by["gen-tampered-place_order"]["control"] == "vendors"
    assert by["gen-benign-fetch_news"]["verdict"] == "good"
    bare = cases.run_cases({**a, "levels": {c: 0 for c in policy.CONTROL_ORDER}}, r["cases"], approved)
    assert bare["summary"]["defect"] >= 10


def test_warnings_and_skips():
    spec = {"agent": {"name": "x"}, "tools": [
        {"name": "buy_stock", "input_schema": {"type": "object", "properties": {"qty": {"type": "integer"}}}},
        {"name": "frobnicate"}]}
    r = intake.build(spec)
    w = " ".join(r["warnings"])
    assert "deployment" in w and "controls" in w and "수량만" in w and "frobnicate" in w
    assert any("금액 인자" in s for s in r["skipped"]) and any("구성요소" in s for s in r["skipped"])
    assert r["agent"]["levels"] == {c: 0 for c in policy.CONTROL_ORDER}


def test_overrides_and_bad_input():
    r = intake.build(SPEC, {"kinds": {"send_email": "write"}})
    assert {t["name"]: t for t in r["tools"]}["send_email"]["kind"] == "write"
    for bad in ("", "tools: 3", "[1, 2]", "a: [", {"tools": [{"name": "bad name!"}]}):
        with pytest.raises(intake.IntakeError):
            intake.build(bad)
    with pytest.raises(intake.IntakeError):
        intake.build(SPEC, {"kinds": {"send_email": "fly"}})
    with pytest.raises(intake.IntakeError):
        intake.build("x" * (70 * 1024))


def test_policy_uses_registered_amount_and_customer_args():
    a = {"id": "agt_t", "status": "active", "levels": ALL2, "limits": {"max_amount": 1000, "max_high_risk_per_min": 5},
         "env": {"tools": "pay", "untrusted_input": True},
         "tools": [{"name": "po", "kind": "pay", "amount_arg": "notional_krw"}, {"name": "acct", "kind": "read", "customer_arg": "customer_id"}]}
    ctx = {"auth": "token", "recent_high_risk": 0, "approval": None, "approved_components": []}
    U = [{"kind": "user", "trusted": True}]
    assert policy.decide(a, {"tool": "po", "args": {"notional_krw": 5000}, "input_sources": U}, ctx)["control"] == "least_privilege"
    assert policy.decide(a, {"tool": "po", "args": {"notional_krw": "5000"}, "input_sources": U}, ctx)["control"] == "least_privilege"
    assert policy.decide(a, {"tool": "acct", "args": {"customer_id": "c-2"}, "context": {"customer": "c-1"}}, ctx)["control"] == "least_privilege"


def test_decision_tools_are_high_risk():
    """신용공여 승인 · 한도 설정 같은 고객에 대한 결정은 종류가 쓰기여도 고위험 — 사람 승인 · 빈도 탐지 대상."""
    spec = {"agent": {"name": "신용공여 심사", "model": {"deployment": "onprem"}, "automated_decision": True},
            "tools": [{"name": "get_credit_report", "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}}},
                      {"name": "approve_margin_loan", "description": "신용융자 한도를 승인한다",
                       "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}, "limit": {"type": "integer"}}}}]}
    r = intake.build(spec)
    t = {x["name"]: x for x in r["tools"]}["approve_margin_loan"]
    assert t["kind"] == "write" and t["high_risk"] and t["amount_arg"] == "limit" and "고위험" in t["why"]
    assert "credit" in r["compliance"]["activities"]
    a = {"id": "agt_t", "status": "active", **r["agent"], "levels": dict(ALL2)}
    ctx = {"auth": "token", "recent_high_risk": 0, "approval": None, "approved_components": []}
    d = policy.decide(a, {"tool": "approve_margin_loan", "args": {"customer_id": "c-1", "limit": 100}, "context": {"customer": "c-1"},
                          "input_sources": [{"kind": "user", "trusted": True}]}, ctx)
    assert d["decision"] == "require_approval" and d["high"]
    assert any(c["id"].startswith("gen-insider-approve_margin_loan") for c in r["cases"])
