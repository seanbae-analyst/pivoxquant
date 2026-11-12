"""런타임 — 정책 엔진 판정 · 저장소(키 해시 · 감사 사슬) · 서비스(등록 · 인증 · 승인 · 즉시 중단) · 레드팀."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pivoxpolicy import sim
from pivoxpolicy.runtime import policy, redteam
from pivoxpolicy.runtime.service import AuthError, PROFILE_TOOLS, Runtime, RuntimeError_
from pivoxpolicy.runtime.store import Store

ALL2 = {c: 2 for c in policy.CONTROL_ORDER}
NONE = {c: 0 for c in policy.CONTROL_ORDER}
APPROVED = [{"name": t["component"]["name"], "version": t["component"]["version"], "sha256": t["component"].get("sha256")}
            for ts in PROFILE_TOOLS.values() for t in ts if t.get("component")]


def agent(levels=None, tools_level="pay", profile="trading", **env):
    return {"id": "agt_test01", "status": "active", "expires_at": None, "levels": dict(levels or ALL2),
            "env": {"tools": tools_level, "untrusted_input": True, "open_components": False, "memory": False, "multi_agent": False, **env},
            "tools": [dict(t) for t in PROFILE_TOOLS[profile]], "limits": {"max_amount": 1_000_000, "max_high_risk_per_min": 5}, "delegates": []}


def ctx(**kw):
    return {"auth": "token", "now": datetime(2026, 11, 12, tzinfo=timezone.utc), "recent_high_risk": 0, "approval": None,
            "approved_components": APPROVED, **kw}


# ── 정책 엔진 ──

def test_each_control_blocks_at_its_place():
    a = agent()
    pay = {"tool": "transfer", "args": {"amount": 100}}
    assert policy.decide(a, {"tool": "nope"}, ctx())["control"] == "inventory"
    assert policy.decide(a, {**pay, "component": {"name": "pay-gateway-mcp", "version": "9.9.9"}}, ctx())["control"] == "vendors"
    assert policy.decide(a, pay, ctx(auth="key"))["control"] == "unique_id"
    assert policy.decide(a, {**pay, "args": {"amount": 5_000_000}}, ctx())["control"] == "least_privilege"
    r = policy.decide(a, {**pay, "input_sources": [{"kind": "web", "trusted": False}]}, ctx())
    assert (r["decision"], r["control"]) == ("deny", "least_privilege")
    r = policy.decide(a, pay, ctx())
    assert (r["decision"], r["control"]) == ("require_approval", "human_approval")
    ok = {"status": "approved", "request_hash": r["request_hash"], "agent_id": a["id"]}
    assert policy.decide(a, pay, ctx(approval=ok))["decision"] == "allow"
    assert policy.decide(a, {**pay, "args": {"amount": 101}}, ctx(approval=ok))["decision"] == "require_approval"   # 승인 뒤 금액을 바꾸면 다른 요청


def test_level_one_is_human_process_only_and_off_lets_it_through():
    a = agent(levels={c: 1 for c in policy.CONTROL_ORDER})
    r = policy.decide(a, {"tool": "transfer", "args": {"amount": 9_000_000}, "input_sources": [{"kind": "web", "trusted": False}]}, ctx(auth="key"))
    assert r["decision"] == "allow" and all(c["note"] == "사람 절차만" for c in r["checks"])


def test_burst_detected_and_auto_suspended_only_with_kill_switch():
    lv = dict(NONE, audit_trail=2, kill_switch=2)
    r = policy.decide(agent(lv), {"tool": "transfer", "args": {"amount": 10}}, ctx(recent_high_risk=5))
    assert (r["decision"], r["control"], r["suspend"]) == ("deny", "kill_switch", True)
    r = policy.decide(agent(dict(NONE, audit_trail=2)), {"tool": "transfer", "args": {"amount": 10}}, ctx(recent_high_risk=5))
    assert r["decision"] == "allow" and "burst" in r["flags"]                    # 알아채도 멈출 수단이 없다


def test_declared_environment_is_enforced():
    a = agent(untrusted_input=False)
    r = policy.decide(a, {"tool": "market_news", "input_sources": [{"kind": "web", "trusted": False}]}, ctx())
    assert r["control"] == "least_privilege" and "등록된" in r["reason"]
    assert policy.decide(agent(), {"tool": "market_news", "on_behalf_of": "agt_other1"}, ctx())["control"] == "unique_id"


def test_status_and_expiry():
    assert policy.decide({**agent(), "status": "suspended"}, {"tool": "market_news"}, ctx())["control"] == "kill_switch"
    assert policy.decide({**agent(), "status": "revoked"}, {"tool": "market_news"}, ctx())["control"] == "inventory"
    old = {**agent(), "expires_at": "2026-01-01T00:00:00Z"}
    assert policy.decide(old, {"tool": "market_news"}, ctx())["control"] == "inventory"
    assert policy.decide({**old, "levels": NONE}, {"tool": "market_news"}, ctx())["decision"] == "allow"   # 인벤토리 통제 없이는 만료를 모른다


# ── 저장소 · 서비스 ──

@pytest.fixture()
def rt(tmp_path):
    return Runtime(Store(tmp_path / "rt.db"))


def reg(rt, **kw):
    data = {"name": "트레이딩 봇", "owner": "리스크관리팀", "profile": "trading",
            "env": {"tools": "pay", "untrusted_input": True}, "levels": ALL2, **kw}
    return rt.register(data)


def test_keys_are_stored_as_digests_and_tokens_are_short_lived(rt, tmp_path):
    a, key = reg(rt)
    raw = (tmp_path / "rt.db").read_bytes()
    assert key.startswith("pvx_") and key.encode() not in raw                   # 원문은 DB 에 없다
    tok = rt.exchange_token("Bearer " + key)
    assert tok["token"].startswith("pvt_") and tok["token"].encode() not in (tmp_path / "rt.db").read_bytes()
    assert rt.authenticate("Bearer " + tok["token"])[1] == "token"
    with pytest.raises(AuthError):
        rt.authenticate("Bearer pvt_nope")
    s2, _ = rt.rotate_key(a["id"])
    with pytest.raises(AuthError):
        rt.exchange_token("Bearer " + key)                                      # 회전하면 옛 키는 끝
    with pytest.raises(AuthError):
        rt.authenticate("Bearer " + tok["token"])                               # 그 키로 받은 토큰도 끝
    assert rt.exchange_token("Bearer " + s2)["agent_id"] == a["id"]


def test_decide_approve_and_audit_chain(rt):
    a, key = reg(rt)
    auth = "Bearer " + rt.exchange_token("Bearer " + key)["token"]
    body = {"tool": "transfer", "args": {"amount": 500_000, "target": "vendor-1"}, "input_sources": [{"kind": "user", "trusted": True}]}
    r = rt.decide(auth, body)
    assert r["decision"] == "require_approval" and r["approval_id"].startswith("apr_")
    assert rt.approval_for_agent(auth, r["approval_id"])["status"] == "pending"
    rt.decide_approval(r["approval_id"], True, "운영자")
    r2 = rt.decide(auth, {**body, "approval_id": r["approval_id"]})
    assert r2["decision"] == "allow"
    with pytest.raises(RuntimeError_):
        rt.decide_approval(r["approval_id"], False, "운영자")                   # 이미 처리
    v = rt.store.verify_audit()
    assert v["ok"] and v["checked"] >= 5
    rt.store.db.execute("UPDATE audit SET payload='{\"x\":1}' WHERE seq=2")      # 기록을 고치면 사슬이 끊긴다
    assert rt.store.verify_audit() == {"ok": False, "checked": 1, "broken_at": 2}


def test_kill_switch_needs_the_control_and_stops_everything(rt):
    a, key = reg(rt, levels=dict(ALL2, kill_switch=0))
    with pytest.raises(RuntimeError_) as e:
        rt.set_status(a["id"], "suspended")
    assert e.value.status == 409
    b, kb = reg(rt)
    auth = "Bearer " + rt.exchange_token("Bearer " + kb)["token"]
    rt.set_status(b["id"], "suspended", reason="이상 행위")
    with pytest.raises(AuthError):
        rt.decide(auth, {"tool": "market_news"})                                # 살아 있던 토큰도 끊긴다
    rt.set_status(b["id"], "active")
    auth = "Bearer " + rt.exchange_token("Bearer " + kb)["token"]
    assert rt.decide(auth, {"tool": "market_news"})["decision"] == "allow"
    rt.set_status(b["id"], "revoked")
    with pytest.raises(AuthError):
        rt.exchange_token("Bearer " + kb)


def test_input_validation(rt):
    a, key = reg(rt)
    auth = "Bearer " + key
    for bad in (None, [], {"tool": ""}, {"tool": "x" * 65}, {"tool": "t", "input_sources": "web"}, {"tool": "t", "args": {"x": "y" * 5000}}):
        with pytest.raises(RuntimeError_):
            rt.decide(auth, bad)
    for bad in ({"name": "", "owner": "o", "env": {"tools": "pay"}}, {"name": "n", "owner": "o", "env": {"tools": "root"}},
                {"name": "n", "owner": "o", "env": {"tools": "read"}, "levels": {"inventory": 3}},
                {"name": "n", "owner": "o", "env": {"tools": "read"}, "tools": [{"name": "Bad Name", "kind": "read"}]}):
        with pytest.raises(RuntimeError_):
            rt.register(bad)


# ── 레드팀 ──

def test_playbook_covers_every_scenario():
    ids = {s["id"] for s in sim.load_scenarios()["scenarios"]}
    assert redteam.validate_playbook(redteam.load_playbook(), ids) == []


def test_redteam_all_controls_vs_none():
    full = redteam.run_all(agent(), APPROVED)
    by = {r["scenario"]: r for r in full["results"]}
    assert by["prompt_injection"]["outcome"] == "blocked" and by["prompt_injection"]["control"] == "least_privilege"
    assert by["ai_credentials"]["control"] == "unique_id" and by["supply_chain"]["control"] == "vendors"
    assert by["ai_attacker"]["outcome"] == "runtime_na"
    assert by["code_execution"]["outcome"] == "no_surface"                     # 트레이딩 에이전트엔 코드 실행 도구가 없다
    bare = redteam.run_all(agent(NONE), APPROVED)
    assert {r["outcome"] for r in bare["results"]} <= {"damage", "runtime_na", "no_surface"}
    assert bare["summary"]["damage"] > full["summary"]["damage"]


def test_redteam_does_not_touch_the_real_agent():
    a = agent(dict(NONE, audit_trail=2, kill_switch=2))
    r = redteam.run(a, "rogue_agent", redteam.load_playbook()["rogue_agent"], APPROVED)
    assert r["outcome"] == "blocked" and r["control"] == "kill_switch" and r["detected"]
    assert a["status"] == "active"


# ── 버그 회귀 (2026-11-12 버그 사냥) ──

def test_amount_format_cannot_slip_past_the_limit():
    """문자열 · NaN · 음수 · bool 금액이 한도 검사를 비켜 가던 것(fail-open)."""
    a = agent()
    trusted = [{"kind": "user", "trusted": True}]
    for amt in ("90000000", float("nan"), -90_000_000, True):
        r = policy.decide(a, {"tool": "transfer", "args": {"amount": amt}, "input_sources": trusted}, ctx())
        assert (r["decision"], r["control"]) == ("deny", "least_privilege"), amt
    assert policy.decide(a, {"tool": "transfer", "args": {"amount": 100}, "input_sources": trusted}, ctx())["decision"] == "require_approval"


def test_customer_scope_needs_the_context():
    r = policy.decide(agent(), {"tool": "market_news", "args": {"customer": "c-777"}}, ctx())
    assert r["decision"] == "deny" and "밝히지" in r["reason"]


def test_unregistered_tool_cannot_self_declare_low_risk():
    """등록부 밖 도구가 kind: read 라고 신고하면 사람 승인을 건너뛰던 것."""
    a = agent(dict(ALL2, inventory=0, least_privilege=0))
    r = policy.decide(a, {"tool": "wire_out", "kind": "read", "args": {"amount": 90_000_000}}, ctx())
    assert r["decision"] == "require_approval" and r["high"] and r["unregistered"]
    r = policy.decide(agent(dict(ALL2, inventory=0)), {"tool": "wire_out", "kind": "read"}, ctx())
    assert (r["decision"], r["control"]) == ("deny", "least_privilege")      # 최소 권한: 준 적 없는 도구
    assert policy.decide(agent(NONE), {"tool": "wire_out", "kind": "read"}, ctx())["decision"] == "allow"   # 통제가 없으면 모른다


def test_limits_reject_booleans(rt):
    with pytest.raises(RuntimeError_):
        reg(rt, limits={"max_amount": True})
    with pytest.raises(RuntimeError_):
        reg(rt, limits={"max_high_risk_per_min": True})


def test_approved_action_is_counted_once_for_burst(rt):
    """승인받은 행위를 두 번 세어, 정상 송금 몇 건만으로 자동 중단이 걸리던 것."""
    a, key = reg(rt, limits={"max_amount": 1_000_000, "max_high_risk_per_min": 3})
    h = "Bearer " + rt.exchange_token("Bearer " + key)["token"]
    for i in range(3):                                   # 1분에 3건까지는 승인만 받으면 실행된다
        body = {"tool": "transfer", "args": {"amount": 100 + i, "target": "v"}, "input_sources": [{"kind": "user", "trusted": True}]}
        r1 = rt.decide(h, body)
        rt.decide_approval(r1["approval_id"], True)
        assert rt.decide(h, {**body, "approval_id": r1["approval_id"]})["decision"] == "allow", i
    body = {"tool": "transfer", "args": {"amount": 999, "target": "v"}, "input_sources": [{"kind": "user", "trusted": True}]}
    r1 = rt.decide(h, body)
    rt.decide_approval(r1["approval_id"], True)
    r = rt.decide(h, {**body, "approval_id": r1["approval_id"]})          # 4번째 — 3건 초과
    assert r["decision"] == "deny" and r["control"] == "kill_switch" and r.get("suspended")
