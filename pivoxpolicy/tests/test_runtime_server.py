"""런타임 서버 — 실제 HTTP 로: 관리자 로그인 · CSRF · 등록 · 에이전트 SDK 판정 · 승인 · 즉시 중단 · 레드팀 · 보안 헤더."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from wsgiref.simple_server import make_server

import pytest

from pivoxpolicy.runtime import server
from pivoxpolicy.runtime.sdk import ApprovalRequired, Blocked, Guard

ADMIN = "test-admin-token-0123456789"
ALL2 = {c: 2 for c in ("inventory", "vendors", "unique_id", "least_privilege", "human_approval", "audit_trail", "kill_switch")}


@pytest.fixture()
def srv(tmp_path):
    app, _ = server.build_app(tmp_path / "rt.db", ADMIN, secure_cookie=False)
    httpd = make_server("127.0.0.1", 0, app, server_class=server._Threading, handler_class=server._Quiet)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_port}", app
    httpd.shutdown()


def call(base, method, path, body=None, headers=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, (r.read() if raw else json.loads(r.read() or b"null")), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), dict(e.headers)


def login(base):
    st, body, hd = call(base, "POST", "/admin/login", {"token": ADMIN})
    assert st == 200
    cookie = hd["Set-Cookie"].split(";")[0]
    assert "HttpOnly" in hd["Set-Cookie"] and "SameSite=Strict" in hd["Set-Cookie"]
    return {"Cookie": cookie, "X-CSRF": body["csrf"]}


def test_admin_requires_login_and_csrf(srv):
    base, _ = srv
    assert call(base, "GET", "/admin/api/agents")[0] == 401
    assert call(base, "POST", "/admin/login", {"token": "wrong-token-xxxxxxxx"})[0] == 401
    h = login(base)
    assert call(base, "GET", "/admin/api/agents", headers={"Cookie": h["Cookie"]})[0] == 200
    st, _, _ = call(base, "POST", "/admin/api/agents", {"name": "x"}, headers={"Cookie": h["Cookie"]})      # CSRF 헤더 없음
    assert st == 403
    st, _, _ = call(base, "POST", "/admin/api/agents", {"name": "x"}, headers={**h, "Origin": "https://evil.example"})
    assert st == 403
    st, body, hd = call(base, "GET", "/admin", raw=True)
    assert st == 200 and b"<script src=\"/admin/assets/runtime-ui.js\">" in body and b"<script>" not in body
    assert "script-src 'self'" in hd["Content-Security-Policy"] and hd["X-Content-Type-Options"] == "nosniff"


def test_login_is_rate_limited(srv):
    base, _ = srv
    codes = [call(base, "POST", "/admin/login", {"token": "nope-nope-nope-nope"})[0] for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_end_to_end_register_decide_approve_suspend_redteam(srv):
    base, app = srv
    h = login(base)
    st, r, _ = call(base, "POST", "/admin/api/agents", {"name": "트레이딩 봇", "owner": "리스크관리팀", "profile": "trading",
                                                        "env": {"tools": "pay", "untrusted_input": True}, "levels": ALL2}, headers=h)
    assert st == 201 and r["api_key"].startswith("pvx_")
    aid, key = r["agent"]["id"], r["api_key"]
    g = Guard(base, key)

    @g.tool("transfer")
    def transfer(amount, target):
        return "sent"

    web = [{"kind": "web", "trusted": False}]
    with pytest.raises(Blocked) as e:
        transfer(9_000_000, "attacker", input_sources=web)
    assert e.value.decision["control"] == "least_privilege"
    with pytest.raises(ApprovalRequired) as e:
        transfer(300_000, "vendor-1", input_sources=[{"kind": "user", "trusted": True}])
    apr = e.value.approval_id
    st, pend, _ = call(base, "GET", "/admin/api/approvals?status=pending", headers=h)
    assert [p["id"] for p in pend["approvals"]] == [apr] and pend["approvals"][0]["request"]["args"]["amount"] == 300_000
    assert call(base, "POST", f"/admin/api/approvals/{apr}", {"approve": True}, headers=h)[0] == 200
    assert transfer(300_000, "vendor-1", input_sources=[{"kind": "user", "trusted": True}], approval_id=apr) == "sent"
    # 장기 키 직접 사용 — 고유 식별자 통제가 막는다
    d = Guard(base, key, use_token=False).check("market_news")
    assert d["decision"] == "deny" and d["control"] == "unique_id"
    # 즉시 중단 → 모든 호출 거부(토큰도 끊김)
    assert call(base, "POST", f"/admin/api/agents/{aid}/status", {"status": "suspended", "reason": "시험"}, headers=h)[0] == 200
    with pytest.raises(Exception):
        g.check("market_news")
    # 레드팀 · 감사 사슬
    st, rt, _ = call(base, "POST", f"/admin/api/agents/{aid}/redteam", {}, headers=h)
    assert st == 200 and len(rt["results"]) == 12 and rt["summary"]["damage"] == 0       # 모든 통제를 AI까지 — 피해가 나는 원형 없음
    st, v, _ = call(base, "GET", "/admin/api/audit/verify", headers=h)
    assert v["ok"] and v["checked"] > 5


def test_cases_and_matrix_endpoints(srv):
    base, _ = srv
    h = login(base)
    st, r, _ = call(base, "POST", "/admin/api/agents", {"name": "정산 에이전트", "owner": "재무팀", "profile": "trading",
                                                        "env": {"tools": "pay", "untrusted_input": True}, "levels": ALL2}, headers=h)
    aid = r["agent"]["id"]
    # 공격 팀 — 모든 통제를 AI까지 켠 에이전트엔 결함이 없어야 한다
    st, cs, _ = call(base, "POST", f"/admin/api/agents/{aid}/cases", {}, headers=h)
    assert st == 200 and cs["summary"]["defect"] == 0 and cs["summary"]["friction"] >= 1
    by = {r["id"]: r for r in cs["results"]}
    assert by["news-injection"]["verdict"] == "good" and by["normal-settlement"]["verdict"] == "friction"
    # 규제별 비교 — 통제 없음에서 결함이 가장 많고, 모두 AI까지에서 가장 적다
    st, mx, _ = call(base, "POST", f"/admin/api/agents/{aid}/matrix", {"presets": ["none", "KR-2", "all"]}, headers=h)
    assert st == 200 and [p["preset"] for p in mx["presets"]] == ["none", "KR-2", "all"]
    cols = {p["preset"]: p for p in mx["presets"]}
    assert cols["none"]["summary"]["defect"] > cols["all"]["summary"]["defect"]
    assert call(base, "POST", f"/admin/api/agents/{aid}/matrix", {"presets": ["bogus"]}, headers=h)[0] == 400


def test_cases_preview_levels_and_bad_bodies(srv):
    """버그 회귀: 화면에서 고친 수준(저장 전)으로 돌릴 수 있어야 하고, 객체가 아닌 본문은 500 이 아니라 400."""
    base, _ = srv
    h = login(base)
    st, r, _ = call(base, "POST", "/admin/api/agents", {"name": "정산 에이전트", "owner": "재무팀", "profile": "trading",
                                                        "env": {"tools": "pay", "untrusted_input": True}, "levels": ALL2}, headers=h)
    aid = r["agent"]["id"]
    none = {c: 0 for c in ALL2}
    st, cs, _ = call(base, "POST", f"/admin/api/agents/{aid}/cases", {"levels": none}, headers=h)
    assert st == 200 and cs["preview"] is True and cs["summary"]["defect"] > 0          # 저장 안 한 '통제 없음' 으로 돌았다
    st, a, _ = call(base, "GET", f"/admin/api/agents/{aid}", headers=h)
    assert a["levels"] == ALL2                                                          # 저장된 수준은 그대로
    st, mx, _ = call(base, "POST", f"/admin/api/agents/{aid}/matrix", {"presets": ["all"], "current_levels": none}, headers=h)
    assert [p["preset"] for p in mx["presets"]] == ["current", "all"]
    for path, body in ((f"/admin/api/agents/{aid}/cases", [1]), (f"/admin/api/agents/{aid}/matrix", {"presets": [[1]]}),
                       (f"/admin/api/agents/{aid}/status", [1]), ("/admin/api/components", [1]),
                       (f"/admin/api/agents/{aid}/cases", {"levels": {"inventory": 7}})):
        assert call(base, "POST", path, body, headers=h)[0] == 400, path


def test_agent_api_rejects_bad_input(srv):
    base, _ = srv
    assert call(base, "POST", "/v1/decide", {"tool": "x"})[0] == 401
    assert call(base, "POST", "/v1/decide", {"tool": "x"}, headers={"Authorization": "Bearer pvx_nope"})[0] == 401
    assert call(base, "GET", "/v1/decide")[0] == 405
    assert call(base, "GET", "/nope")[0] == 404


def test_obligations_profile_and_matrix_columns(srv):
    """적용성 프로필 → 적용 조문 · 미적용(이유) · 비교표의 '적용 조문' 열 · 결함과 조문 분류."""
    base, _ = srv
    h = login(base)
    st, r, _ = call(base, "POST", "/admin/api/agents", {"name": "정산 에이전트", "owner": "재무팀", "profile": "trading",
                                                        "env": {"tools": "pay", "untrusted_input": True}, "levels": ALL2}, headers=h)
    aid = r["agent"]["id"]
    assert call(base, "POST", f"/admin/api/agents/{aid}/obligations", {}, headers=h)[0] == 409          # 프로필 없음
    settle = {"activities": ["transfer"], "data": ["personal"], "external_llm": "foreign_api"}
    st, ob, _ = call(base, "POST", f"/admin/api/agents/{aid}/obligations", {"profile": settle}, headers=h)
    assert st == 200 and ob["high_impact"]["value"] is False and ob["reviewed_by_counsel"] is False
    assert "aibasic-34-1-4" in {x["id"] for x in ob["not_applicable"]}
    assert ob["summary"]["unmet"] == 0                                              # 모든 통제를 AI까지 켠 에이전트
    assert call(base, "POST", f"/admin/api/agents/{aid}/obligations", {"profile": {"activities": ["fly"]}}, headers=h)[0] == 400
    # 저장 → 비교표에 적용 조문 열이 붙고, 결함 칸에 조문 분류가 달린다
    assert call(base, "PATCH", f"/admin/api/agents/{aid}", {"compliance": settle}, headers=h)[0] == 200
    st, mx, _ = call(base, "POST", f"/admin/api/agents/{aid}/matrix", {"presets": ["none"]}, headers=h)
    ids = [p["preset"] for p in mx["presets"]]
    assert ids == ["OB-binding_explicit", "OB-binding_interpretive", "OB-guideline", "none"]
    explicit = mx["presets"][0]["cells"]
    assert explicit["other-customer"]["verdict"] == "defect"
    assert explicit["other-customer"]["link"]["kind"] == "interpretive"            # 제13조는 사람·계정 층 — 에이전트엔 해석
    assert "efsr-13-1-1-access" in explicit["other-customer"]["link"]["obligations"]
    assert mx["obligations"]["efsr-13-1-1-access"]["article"] == "제13조 제1항 제1호"


def test_intake_preview_and_register(srv):
    """명세 붙여 넣기 → 미리보기(추정 · 경고 · 케이스) → 등록(키 · 프로필 · 케이스 · 구성요소 승인) → 공격 팀이 그 케이스로 돈다."""
    from pathlib import Path
    base, _ = srv
    h = login(base)
    spec = (Path(__file__).resolve().parents[1] / "examples" / "agent_spec_order.yaml").read_text(encoding="utf-8")
    st, pv, _ = call(base, "POST", "/admin/api/intake/preview", {"spec_text": spec}, headers=h)
    assert st == 200 and "system_prompt" not in pv and len(pv["cases"]) >= 10
    assert {t["name"]: t["kind"] for t in pv["tools"]}["place_order"] == "pay" and pv["assessment"]["applicable"] > 20
    assert call(base, "POST", "/admin/api/intake/preview", {"spec_text": "tools: 3"}, headers=h)[0] == 400
    assert call(base, "POST", "/admin/api/intake/preview", {}, headers=h)[0] == 400
    st, r, _ = call(base, "POST", "/admin/api/intake/register", {"spec_text": spec, "overrides": {"kinds": {"get_quote": "read"}}}, headers=h)
    assert st == 201 and r["api_key"].startswith("pvx_")
    a = r["agent"]
    assert a["compliance"]["activities"] == ["order", "transfer", "customer_service"] and len(a["cases"]) == len(pv["cases"])
    assert {t["name"]: t.get("amount_arg") for t in a["tools"]}["place_order"] == "notional_krw"
    st, comps, _ = call(base, "GET", "/admin/api/components", headers=h)
    assert any(c["name"] == "broker-gw" and c["sha256"] for c in comps["components"])
    st, cs, _ = call(base, "POST", f"/admin/api/agents/{a['id']}/cases", {}, headers=h)
    assert st == 200 and all(x["id"].startswith("gen-") for x in cs["results"])


def test_report_endpoints(srv):
    from pathlib import Path
    base, _ = srv
    h = login(base)
    spec = (Path(__file__).resolve().parents[1] / "examples" / "agent_spec_order.yaml").read_text(encoding="utf-8")
    st, r, _ = call(base, "POST", "/admin/api/intake/register", {"spec_text": spec}, headers=h)
    aid = r["agent"]["id"]
    st, body, hd = call(base, "GET", f"/admin/api/agents/{aid}/report.html", headers={"Cookie": h["Cookie"]}, raw=True)
    assert st == 200 and hd["Content-Type"].startswith("text/html") and "통제 매트릭스".encode() in body and b"<script" not in body
    assert "default-src 'none'" in hd["Content-Security-Policy"]
    st, body, hd = call(base, "GET", f"/admin/api/agents/{aid}/report.rcm.csv", headers={"Cookie": h["Cookie"]}, raw=True)
    assert st == 200 and "attachment" in hd["Content-Disposition"] and body.startswith("﻿".encode())
    assert call(base, "GET", f"/admin/api/agents/{aid}/report.html")[0] == 401                  # 로그인 없이 못 본다
    st, r2, _ = call(base, "POST", "/admin/api/agents", {"name": "x", "owner": "y", "env": {"tools": "read"}}, headers=h)
    assert call(base, "GET", f"/admin/api/agents/{r2['agent']['id']}/report.md", headers={"Cookie": h["Cookie"]})[0] == 409   # 프로필 없음
