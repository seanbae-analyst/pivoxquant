"""런타임 정책 엔진 — 에이전트가 도구를 쓰기 직전의 요청 하나를 판정한다(허용 · 거부 · 사람 승인).

모의 테스트(sim.py)의 통제 7개를 그대로 쓴다. 통제 수준이 2(AI까지)인 것만 런타임에서 집행한다 —
수준 1(사람·계정만)은 사람 절차라 이 엔진 밖이고, 판정 기록에는 '사람 절차만'으로 남는다.

판정 순서(모의 테스트의 단계 배치와 같은 순서):
  상태(폐기·중단·만료) → 인벤토리 → 공급자 관리 → 고유 식별자 → 최소 권한 → 사람 승인 → 감사 기록(탐지) → 즉시 중단(자동)
DB 도 네트워크도 쓰지 않는 순수 함수다. 저장 · 인증 · 승인 대기열은 service.py.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

CONTROL_ORDER = ("inventory", "vendors", "unique_id", "least_privilege", "human_approval", "audit_trail", "kill_switch")
KINDS = ("read", "write", "send", "exec", "pay")
HIGH = frozenset({"pay", "send", "exec"})                     # 송금 · 외부 전송 · 코드 실행
ALLOWED_BY_TOOLS = {"read": {"read"}, "write": {"read", "write", "send", "exec"}, "pay": set(KINDS)}
KIND_KO = {"read": "조회", "write": "쓰기", "send": "외부 전송", "exec": "코드 실행", "pay": "송금·결제"}


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_hash(agent_id: str, req: dict[str, Any]) -> str:
    """승인을 요청 내용에 묶는 지문 — 승인받은 뒤 금액·대상을 바꾸면 다른 요청이다."""
    core = {k: req.get(k) for k in ("tool", "action", "args", "component", "input_sources", "on_behalf_of", "context")}
    return hashlib.sha256(canonical({"agent": agent_id, **core}).encode("utf-8")).hexdigest()


def _untrusted(req: dict[str, Any]) -> bool:
    if req.get("on_behalf_of"):
        return True                                           # 다른 에이전트가 넘긴 일은 외부 입력으로 본다
    return any(not s.get("trusted", False) for s in req.get("input_sources") or [])


def _expired(agent: dict[str, Any], now: datetime) -> bool:
    exp = agent.get("expires_at")
    if not exp:
        return False
    try:
        t = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
    except ValueError:
        return True
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return now >= t


def decide(agent: dict[str, Any], req: dict[str, Any], ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """agent: 등록부 한 줄(status, expires_at, env, levels, tools, limits, delegates).
    req: {tool, action, args, context, input_sources, component, approval_id, on_behalf_of, kind}.
    ctx: {auth: 'token'|'key', now, recent_high_risk, approval, approved_components}.
    반환: {decision, control, reason, checks, flags, suspend, kind, request_hash}."""
    ctx = ctx or {}
    now = ctx.get("now") or datetime.now(timezone.utc)
    lv = {c: int((agent.get("levels") or {}).get(c, 0)) for c in CONTROL_ORDER}
    on = {c: lv[c] >= 2 for c in CONTROL_ORDER}
    limits = agent.get("limits") or {}
    checks: list[dict[str, Any]] = []
    flags: list[str] = []
    rh = request_hash(agent.get("id", ""), req)
    tools = {t["name"]: t for t in agent.get("tools") or []}
    tool = tools.get(req.get("tool") or "")
    kind = (tool or {}).get("kind") or (req.get("kind") if req.get("kind") in KINDS else "write")

    def out(decision: str, control: str | None, reason: str, suspend: bool = False) -> dict[str, Any]:
        for c in CONTROL_ORDER:            # 판정에 오지 않은 통제도 표에 남긴다
            if not any(x["control"] == c for x in checks):
                checks.append({"control": c, "on": on[c], "result": "not_reached" if decision != "allow" else ("off" if not on[c] else "pass"),
                               "note": "" if on[c] else ("사람 절차만" if lv[c] == 1 else "없음")})
        checks.sort(key=lambda x: CONTROL_ORDER.index(x["control"]))
        return {"decision": decision, "control": control, "reason": reason, "checks": checks, "flags": flags,
                "suspend": suspend, "kind": kind, "request_hash": rh}

    def chk(control: str, result: str, note: str = "") -> None:
        checks.append({"control": control, "on": on[control], "result": result, "note": note})

    # 0. 상태 — 폐기·중단은 통제 수준과 상관없이 막는다(등록부에서 지운 것, 운영자가 멈춘 것)
    status = agent.get("status", "active")
    if status == "revoked":
        chk("inventory", "block", "폐기된 에이전트")
        return out("deny", "inventory", "폐기된 에이전트다")
    if status == "suspended":
        chk("kill_switch", "block", "즉시 중단 상태")
        return out("deny", "kill_switch", "즉시 중단된 에이전트다")

    # 1. 인벤토리 — 등록부에 있는 도구만, 만료되지 않은 등록만
    if on["inventory"]:
        if _expired(agent, now):
            chk("inventory", "block", "등록 만료")
            return out("deny", "inventory", "등록 기한이 지났다")
        if tool is None:
            chk("inventory", "block", "등록부에 없는 도구")
            return out("deny", "inventory", f"'{req.get('tool')}' 도구는 이 에이전트 등록부에 없다")
        chk("inventory", "pass")
    else:
        chk("inventory", "off", "사람 절차만" if lv["inventory"] == 1 else "없음")

    # 2. 공급자 관리 — 도구의 구성요소(패키지·MCP 서버)가 승인 목록과 등록 내용 그대로인가
    comp = req.get("component") or (tool or {}).get("component")
    if on["vendors"]:
        if comp:
            reg = (tool or {}).get("component")
            if reg and any(comp.get(k) != reg.get(k) for k in ("name", "version", "sha256") if reg.get(k) or comp.get(k)):
                chk("vendors", "block", "등록된 구성요소와 다름")
                return out("deny", "vendors", f"구성요소 {comp.get('name')}@{comp.get('version')} 가 등록된 것과 다르다")
            ok = [a for a in ctx.get("approved_components") or [] if a.get("name") == comp.get("name") and a.get("version") == comp.get("version")]
            if not ok or (ok[0].get("sha256") and ok[0]["sha256"] != comp.get("sha256")):
                chk("vendors", "block", "승인되지 않은 구성요소")
                return out("deny", "vendors", f"구성요소 {comp.get('name')}@{comp.get('version')} 는 승인 목록에 없다")
        chk("vendors", "pass")
    else:
        chk("vendors", "off", "사람 절차만" if lv["vendors"] == 1 else "없음")

    # 3. 고유 식별자 — 에이전트 전용 단기 토큰, 등록된 위임 관계만
    if on["unique_id"]:
        if ctx.get("auth") != "token":
            chk("unique_id", "block", "장기 키 직접 사용")
            return out("deny", "unique_id", "에이전트 전용 단기 토큰으로 와야 한다(장기 키를 직접 썼다)")
        if req.get("on_behalf_of") and req["on_behalf_of"] not in (agent.get("delegates") or []):
            chk("unique_id", "block", "등록되지 않은 위임")
            return out("deny", "unique_id", f"'{req['on_behalf_of']}' 에서 오는 위임은 등록돼 있지 않다")
        chk("unique_id", "pass")
    else:
        chk("unique_id", "off", "사람 절차만" if lv["unique_id"] == 1 else "없음")

    # 4. 최소 권한 — 도구 권한 · 한도 · 고객 범위 · 외부 입력이 섞인 고위험 행위
    untrusted = _untrusted(req)
    args = req.get("args") or {}
    if on["least_privilege"]:
        env = agent.get("env") or {}
        if any(not s.get("trusted", False) for s in req.get("input_sources") or []) and not env.get("untrusted_input"):
            chk("least_privilege", "block", "선언과 다른 외부 입력")
            return out("deny", "least_privilege", "외부 입력을 읽지 않는다고 등록된 에이전트인데 외부 입력이 섞였다")
        if req.get("on_behalf_of") and not env.get("multi_agent"):
            chk("least_privilege", "block", "선언과 다른 위임")
            return out("deny", "least_privilege", "다른 에이전트와 일을 주고받지 않는다고 등록돼 있다")
        allowed = ALLOWED_BY_TOOLS.get(env.get("tools", "read"), {"read"})
        if kind not in allowed:
            chk("least_privilege", "block", "도구 권한 밖")
            return out("deny", "least_privilege", f"{KIND_KO.get(kind, kind)} 는 이 에이전트의 권한 밖이다")
        if untrusted and kind in HIGH:
            chk("least_privilege", "block", "외부 입력 + 고위험 도구")
            return out("deny", "least_privilege", "외부 입력이 섞인 작업에서는 고위험 도구를 쓸 수 없다")
        cust = (req.get("context") or {}).get("customer")
        if cust and args.get("customer") and args["customer"] != cust:
            chk("least_privilege", "block", "다른 고객의 데이터")
            return out("deny", "least_privilege", "지금 응대 중인 고객이 아닌 다른 고객의 데이터를 요청했다")
        mx = limits.get("max_amount")
        amt = args.get("amount")
        if mx is not None and isinstance(amt, (int, float)) and amt > mx:
            chk("least_privilege", "block", "한도 초과")
            return out("deny", "least_privilege", f"금액 {amt:,} 이 한도 {mx:,} 를 넘는다")
        chk("least_privilege", "pass")
    else:
        chk("least_privilege", "off", "사람 절차만" if lv["least_privilege"] == 1 else "없음")

    # 5. 사람 승인 — 고위험 행위는 이 요청 그대로 승인된 것만
    if on["human_approval"] and kind in HIGH:
        ap = ctx.get("approval")
        if ap and ap.get("status") == "approved" and ap.get("request_hash") == rh and ap.get("agent_id") == agent.get("id"):
            chk("human_approval", "pass", "승인됨")
        else:
            chk("human_approval", "approval", "사람 승인 필요")
            reason = "사람 승인이 필요하다" if not ap else ("승인된 요청과 내용이 다르다" if ap.get("request_hash") != rh else "아직 승인되지 않았다")
            return out("require_approval", "human_approval", reason)
    elif on["human_approval"]:
        chk("human_approval", "pass", "저위험")
    else:
        chk("human_approval", "off", "사람 절차만" if lv["human_approval"] == 1 else "없음")

    # 6. 감사 기록 — 입력 출처를 남기고, 고위험 행위의 이상 빈도를 탐지한다
    if on["audit_trail"]:
        flags.append("provenance")
        burst = int(limits.get("max_high_risk_per_min") or 5)
        if kind in HIGH and int(ctx.get("recent_high_risk") or 0) + 1 > burst:
            flags.append("burst")
            if on["kill_switch"]:
                chk("audit_trail", "flag", f"1분에 고위험 {burst}건 초과")
                chk("kill_switch", "block", "탐지 후 자동 중단")
                return out("deny", "kill_switch", f"1분에 고위험 행위가 {burst}건을 넘어 자동으로 멈췄다", suspend=True)
            chk("audit_trail", "flag", f"1분에 고위험 {burst}건 초과 — 멈출 수단 없음")
        else:
            chk("audit_trail", "pass")
    else:
        chk("audit_trail", "off", "사람 절차만" if lv["audit_trail"] == 1 else "없음")
    chk("kill_switch", "pass" if on["kill_switch"] else "off", "" if on["kill_switch"] else ("사람 절차만" if lv["kill_switch"] == 1 else "없음"))
    return out("allow", None, "허용")
