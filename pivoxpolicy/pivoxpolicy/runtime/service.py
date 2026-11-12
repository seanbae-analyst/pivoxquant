"""런타임 서비스 — 에이전트 등록 · 키/토큰 인증 · 판정 · 승인 · 즉시 중단 · 감사 기록을 묶는다.

서버(server.py)와 테스트가 이 계층만 부른다. 입력은 여기서 검사한다(길이 · 형식 · 크기) — 서버는 HTTP 만 다룬다.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from datetime import timedelta
from typing import Any

from .. import obligations as obligations_mod
from . import policy
from .store import Store, iso, now_utc

CONTROL_IDS = policy.CONTROL_ORDER
TOOLS_LEVELS = ("read", "write", "pay")
ENV_FLAGS = ("untrusted_input", "open_components", "memory", "multi_agent")
NAME_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")      # Anthropic · OpenAI · MCP 도구 이름 규칙과 맞춤
ARG_RX = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]{0,63}$")
ID_RX = re.compile(r"^agt_[a-z0-9]{6,24}$")


class RuntimeError_(ValueError):
    """입력 · 상태 오류 — 서버가 400/404/409 로 바꾼다."""
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


class AuthError(RuntimeError_):
    def __init__(self, msg: str = "인증 실패"):
        super().__init__(msg, 401)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _comp(name: str, version: str, pin: bool = False) -> dict[str, Any]:
    c = {"name": name, "version": version}
    if pin:
        c["sha256"] = _sha(f"{name}@{version}")
    return c


# 에이전트 종류별 기본 도구 등록부 — 모의 테스트의 에이전트 종류(sim_scenarios.yaml agent_profiles)와 같은 id
PROFILE_TOOLS: dict[str, list[dict[str, Any]]] = {
    "support": [{"name": "account_lookup", "kind": "read", "component": _comp("core-banking-api", "3.2.0")},
                {"name": "faq_search", "kind": "read", "component": _comp("docs-index", "1.0.0")}],
    "trading": [{"name": "market_news", "kind": "read", "component": _comp("news-feed", "1.0.0")},
                {"name": "place_order", "kind": "pay", "component": _comp("broker-api", "4.0.1", True)},
                {"name": "transfer", "kind": "pay", "component": _comp("pay-gateway-mcp", "1.4.2", True)}],
    "coding": [{"name": "repo_read", "kind": "read", "component": _comp("git-mcp", "0.9.3")},
               {"name": "repo_write", "kind": "write", "component": _comp("git-mcp", "0.9.3")},
               {"name": "run_code", "kind": "exec", "component": _comp("sandbox-runner", "2.0.0", True)},
               {"name": "pkg_install", "kind": "exec", "component": _comp("pkg-mirror", "1.1.0")}],
    "internal": [{"name": "doc_search", "kind": "read", "component": _comp("docs-index", "1.0.0")}],
    "research": [{"name": "web_fetch", "kind": "read", "component": _comp("fetch-mcp", "1.3.0")},
                 {"name": "memory_write", "kind": "write", "component": _comp("vector-store", "0.7.0")}],
    "workflow": [{"name": "task_delegate", "kind": "write", "component": _comp("a2a-bus", "0.3.0")},
                 {"name": "crm_update", "kind": "write", "component": _comp("crm-api", "5.0.0")},
                 {"name": "send_email", "kind": "send", "component": _comp("mailer", "2.1.0")},
                 {"name": "run_code", "kind": "exec", "component": _comp("sandbox-runner", "2.0.0", True)}],
    "soc": [{"name": "log_query", "kind": "read", "component": _comp("siem-api", "7.2.0")},
            {"name": "run_playbook", "kind": "exec", "component": _comp("soar-runner", "3.0.0", True)},
            {"name": "block_ip", "kind": "write", "component": _comp("fw-api", "1.9.0")}],
    "loan": [{"name": "credit_lookup", "kind": "read", "component": _comp("credit-bureau-api", "2.4.0")},
             {"name": "doc_read", "kind": "read", "component": _comp("docs-index", "1.0.0")}],
}
DEFAULT_LIMITS = {"max_amount": 1_000_000, "max_high_risk_per_min": 5}


def seed_components(store: Store) -> None:
    """기본 도구가 쓰는 구성요소를 승인 목록에 올린다(이미 있으면 그대로)."""
    have = {(c["name"], c["version"]) for c in store.components()}
    for tools in PROFILE_TOOLS.values():
        for t in tools:
            c = t.get("component")
            if c and (c["name"], c["version"]) not in have:
                store.put_component(c["name"], c["version"], c.get("sha256"), "기본 도구")
                have.add((c["name"], c["version"]))


def _str(v: Any, field: str, n: int, required: bool = False) -> str:
    if v is None or v == "":
        if required:
            raise RuntimeError_(f"{field} 필요")
        return ""
    if not isinstance(v, str) or len(v) > n:
        raise RuntimeError_(f"{field} 는 {n}자 이하 문자열")
    return v.strip()


def clean_tools(tools: Any) -> list[dict[str, Any]]:
    if not isinstance(tools, list) or len(tools) > 30:
        raise RuntimeError_("tools 는 30개 이하 목록")
    out, seen = [], set()
    for t in tools:
        if not isinstance(t, dict):
            raise RuntimeError_("도구는 {name, kind, component}")
        name = _str(t.get("name"), "도구 이름", 64, True)
        if not NAME_RX.match(name) or name in seen:
            raise RuntimeError_(f"도구 이름 '{name}' — 영문·숫자·_.- 64자, 중복 없이")
        if t.get("kind") not in policy.KINDS:
            raise RuntimeError_(f"도구 kind 는 {policy.KINDS}")
        item: dict[str, Any] = {"name": name, "kind": t["kind"]}
        if t.get("high_risk") is True:                  # 고객에 대한 결정 등 — 종류와 상관없이 고위험(사람 승인 · 빈도 탐지 대상)
            item["high_risk"] = True
        for k in ("amount_arg", "customer_arg"):        # 한도 · 고객 범위 검사가 볼 인자 이름(없으면 amount · customer)
            v = t.get(k)
            if v:
                if not isinstance(v, str) or not ARG_RX.match(v):
                    raise RuntimeError_(f"{k} 는 인자 이름(영문 64자)")
                item[k] = v
        c = t.get("component")
        if c:
            if not isinstance(c, dict):
                raise RuntimeError_("component 는 {name, version, sha256}")
            item["component"] = {"name": _str(c.get("name"), "구성요소 이름", 60, True), "version": _str(c.get("version"), "구성요소 버전", 40, True)}
            sha = _str(c.get("sha256"), "sha256", 64)
            if sha:
                if not re.fullmatch(r"[0-9a-f]{64}", sha):
                    raise RuntimeError_("sha256 은 소문자 16진수 64자")
                item["component"]["sha256"] = sha
        seen.add(name)
        out.append(item)
    return out


def clean_levels(levels: Any) -> dict[str, int]:
    if not isinstance(levels, dict):
        raise RuntimeError_("levels 는 통제 id → 0|1|2")
    out = {}
    for c in CONTROL_IDS:
        v = levels.get(c, 0)
        if v not in (0, 1, 2):
            raise RuntimeError_(f"levels.{c} 는 0·1·2")
        out[c] = int(v)
    return out


def clean_env(env: Any) -> dict[str, Any]:
    if not isinstance(env, dict) or env.get("tools") not in TOOLS_LEVELS:
        raise RuntimeError_("env.tools 는 read · write · pay")
    return {"tools": env["tools"], **{k: bool(env.get(k)) for k in ENV_FLAGS}}


def clean_limits(limits: Any) -> dict[str, Any]:
    limits = limits or {}
    if not isinstance(limits, dict):
        raise RuntimeError_("limits 는 {max_amount, max_high_risk_per_min}")
    ma = limits.get("max_amount", DEFAULT_LIMITS["max_amount"])
    mb = limits.get("max_high_risk_per_min", DEFAULT_LIMITS["max_high_risk_per_min"])
    if ma is not None and (isinstance(ma, bool) or not isinstance(ma, int) or ma < 0):
        raise RuntimeError_("max_amount 는 0 이상 정수 또는 null")
    if isinstance(mb, bool) or not isinstance(mb, int) or not 1 <= mb <= 1000:
        raise RuntimeError_("max_high_risk_per_min 는 1~1000")
    return {"max_amount": ma, "max_high_risk_per_min": mb}


def clean_request(req: Any) -> dict[str, Any]:
    """에이전트가 보내는 판정 요청 — 모르는 필드는 버리고, 크기를 묶는다."""
    if not isinstance(req, dict):
        raise RuntimeError_("요청 본문은 JSON 객체")
    out: dict[str, Any] = {"tool": _str(req.get("tool"), "tool", 64, True), "action": _str(req.get("action"), "action", 64) or "call"}
    for k in ("args", "context"):
        v = req.get(k) or {}
        if not isinstance(v, dict) or len(policy.canonical(v)) > 4000:
            raise RuntimeError_(f"{k} 는 4000바이트 이하 객체")
        out[k] = v
    srcs = req.get("input_sources") or []
    if not isinstance(srcs, list) or len(srcs) > 20:
        raise RuntimeError_("input_sources 는 20개 이하 목록")
    out["input_sources"] = []
    for s in srcs:
        if not isinstance(s, dict):
            raise RuntimeError_("input_sources 항목은 {kind, trusted, ref}")
        out["input_sources"].append({"kind": _str(s.get("kind"), "input_sources.kind", 32, True), "trusted": s.get("trusted") is True,
                                     **({"ref": _str(s.get("ref"), "input_sources.ref", 300)} if s.get("ref") else {})})
    if req.get("component"):
        c = req["component"]
        if not isinstance(c, dict):
            raise RuntimeError_("component 는 {name, version, sha256}")
        out["component"] = {k: _str(c.get(k), f"component.{k}", 64) for k in ("name", "version", "sha256") if c.get(k)}
    for k, n in (("approval_id", 40), ("on_behalf_of", 40), ("kind", 10)):
        if req.get(k):
            out[k] = _str(req.get(k), k, n)
    return out


def _bearer(header: str | None) -> str:
    if not header or not header.startswith("Bearer "):
        raise AuthError("Authorization: Bearer <키 또는 토큰> 필요")
    return header[7:].strip()


class Runtime:
    def __init__(self, store: Store):
        self.store = store
        self.lib = obligations_mod.load_library("securities")     # 조항 단위 의무(증권부터)
        seed_components(store)

    def clean_compliance(self, p: Any) -> dict[str, Any] | None:
        """에이전트의 적용성 프로필(업권 · 하는 일 · 정보 · 모델 · 고영향 AI) — None 이면 지운다."""
        if p is None:
            return None
        try:
            return obligations_mod.clean_profile(self.lib, p)
        except obligations_mod.ObligationError as e:
            raise RuntimeError_(str(e)) from None

    def clean_cases(self, cs: Any) -> list[dict[str, Any]] | None:
        if cs is None:
            return None
        from .. import sim
        from . import cases as cases_mod
        if not isinstance(cs, list) or len(cs) > 40 or len(policy.canonical(cs)) > 48_000:
            raise RuntimeError_("cases 는 40개 · 48KB 이하 목록")
        probs = cases_mod.validate_cases(cs, {x["id"] for x in sim.load_scenarios()["scenarios"]})
        if probs:
            raise RuntimeError_("케이스 오류: " + "; ".join(probs[:3]))
        return cs

    def import_spec(self, src: Any, overrides: dict[str, Any] | None = None, by: str = "admin") -> tuple[dict[str, Any], str, dict[str, Any]]:
        """명세 → 등록 · 프로필 · 케이스 · 구성요소 승인 목록. (에이전트, 키, 미리보기) 를 돌려준다."""
        from .. import intake
        try:
            r = intake.build(src, overrides)
        except intake.IntakeError as e:
            raise RuntimeError_(str(e)) from None
        agent, secret = self.register(r["agent"], by=by)
        for c in r["components"]:                # 명세에 적힌(지문을 고정했다면 지문까지) 구성요소를 승인 목록에 올린다
            self.store.put_component(c["name"], c["version"], c.get("sha256"), f"명세에서 가져옴: {agent['name']}"[:120])
        meta = {"imported_at": iso(now_utc()), "tools": r["tools"], "warnings": r["warnings"], "skipped": r["skipped"],
                "profile_why": r["profile_why"], "components": r["components"]}
        agent = self.update(agent["id"], {"compliance": r["compliance"], "cases": r["cases"], "intake": meta}, by=by)
        self.store.audit("admin", agent["id"], {"op": "import_spec", "by": by, "tools": len(r["tools"]), "cases": len(r["cases"]),
                                                "warnings": len(r["warnings"])})
        return agent, secret, r

    def assess(self, agent: dict[str, Any], profile: dict[str, Any] | None = None, levels: dict[str, int] | None = None) -> dict[str, Any]:
        prof = profile if profile is not None else agent.get("compliance")
        if not prof:
            raise RuntimeError_("이 에이전트에는 적용성 프로필이 없다(업권 · 하는 일 · 정보 · 모델)", 409)
        return obligations_mod.assess(self.lib, prof, levels if levels is not None else agent.get("levels") or {})

    # ── 등록부 ──
    def register(self, data: dict[str, Any], by: str = "admin") -> tuple[dict[str, Any], str]:
        if not isinstance(data, dict):
            raise RuntimeError_("본문은 JSON 객체")
        prof = data.get("profile") or "custom"
        env = clean_env(data.get("env"))
        tools = clean_tools(data["tools"]) if data.get("tools") is not None else [dict(t) for t in PROFILE_TOOLS.get(prof, [])]
        days = data.get("expires_in_days", 180)
        if days is not None and (not isinstance(days, int) or not 1 <= days <= 3650):
            raise RuntimeError_("expires_in_days 는 1~3650 또는 null")
        agent = {"id": "agt_" + secrets.token_hex(6), "name": _str(data.get("name"), "이름", 80, True),
                 "owner": _str(data.get("owner"), "책임자", 80, True), "purpose": _str(data.get("purpose"), "목적", 300),
                 "profile": prof if prof in PROFILE_TOOLS else "custom", "risk_tier": data.get("risk_tier") if data.get("risk_tier") in ("low", "medium", "high") else "medium",
                 "status": "active", "expires_at": iso(now_utc() + timedelta(days=days)) if days else None,
                 "env": env, "levels": clean_levels(data.get("levels") or {}), "tools": tools,
                 "limits": clean_limits(data.get("limits")), "delegates": []}
        agent = self.store.put_agent(agent)
        secret, key = self.store.issue_key(agent["id"])
        self.store.audit("admin", agent["id"], {"op": "register", "by": by, "name": agent["name"], "profile": agent["profile"],
                                                "levels": agent["levels"], "key": key["prefix"]})
        return agent, secret

    def agent(self, agent_id: str) -> dict[str, Any]:
        a = self.store.get_agent(agent_id) if ID_RX.match(agent_id or "") else None
        if not a:
            raise RuntimeError_("없는 에이전트", 404)
        return a

    def update(self, agent_id: str, patch: dict[str, Any], by: str = "admin") -> dict[str, Any]:
        a = self.agent(agent_id)
        if a["status"] == "revoked":
            raise RuntimeError_("폐기된 에이전트는 고칠 수 없다", 409)
        if not isinstance(patch, dict):
            raise RuntimeError_("본문은 JSON 객체")
        changed = []
        for k, fn in (("levels", clean_levels), ("tools", clean_tools), ("env", clean_env), ("limits", clean_limits)):
            if k in patch:
                a[k] = fn(patch[k])
                changed.append(k)
        for k, n in (("name", 80), ("owner", 80), ("purpose", 300)):
            if k in patch:
                a[k] = _str(patch[k], k, n, k != "purpose")
                changed.append(k)
        if "delegates" in patch:
            d = patch["delegates"]
            if not isinstance(d, list) or len(d) > 20 or any(not isinstance(x, str) or not ID_RX.match(x) for x in d):
                raise RuntimeError_("delegates 는 에이전트 id 목록")
            a["delegates"] = d
            changed.append("delegates")
        if "compliance" in patch:
            a["compliance"] = self.clean_compliance(patch["compliance"])
            changed.append("compliance")
        if "cases" in patch:                       # 이 에이전트의 도구로 만든 공격 케이스(명세 가져오기)
            a["cases"] = self.clean_cases(patch["cases"])
            changed.append("cases")
        if "intake" in patch:                      # 가져온 명세의 추정 · 경고(보고서용). 시스템 프롬프트는 남기지 않는다
            v = patch["intake"]
            if v is not None and (not isinstance(v, dict) or len(policy.canonical(v)) > 32_000):
                raise RuntimeError_("intake 는 32KB 이하 객체")
            a["intake"] = v
            changed.append("intake")
        if "risk_tier" in patch and patch["risk_tier"] in ("low", "medium", "high"):
            a["risk_tier"] = patch["risk_tier"]
            changed.append("risk_tier")
        a = self.store.put_agent({k: v for k, v in a.items() if k not in ("created_at", "updated_at")})
        self.store.audit("admin", agent_id, {"op": "update", "by": by, "fields": changed, "levels": a["levels"]})
        return a

    def set_status(self, agent_id: str, status: str, by: str = "admin", reason: str = "") -> dict[str, Any]:
        a = self.agent(agent_id)
        if status not in ("active", "suspended", "revoked"):
            raise RuntimeError_("status 는 active · suspended · revoked")
        if a["status"] == "revoked":
            raise RuntimeError_("폐기된 에이전트는 되살릴 수 없다", 409)
        if status == "suspended" and a["levels"].get("kill_switch", 0) < 2 and by != "system":
            raise RuntimeError_("이 에이전트에는 즉시 중단 수단이 연결돼 있지 않다(즉시 중단 통제가 AI까지가 아님)", 409)
        a["status"] = status
        a = self.store.put_agent({k: v for k, v in a.items() if k not in ("created_at", "updated_at")})
        if status == "revoked":
            self.store.revoke_keys(agent_id)           # 키 · 토큰 모두 폐기
        elif status == "suspended":
            self.store.drop_tokens(agent_id)           # 살아 있는 단기 토큰을 끊는다(키는 재개 때 다시 쓴다)
        self.store.audit("kill_switch" if status == "suspended" else "admin", agent_id, {"op": "status", "status": status, "by": by, "reason": reason})
        return a

    def rotate_key(self, agent_id: str, by: str = "admin") -> tuple[str, dict[str, Any]]:
        a = self.agent(agent_id)
        if a["status"] == "revoked":
            raise RuntimeError_("폐기된 에이전트", 409)
        n = self.store.revoke_keys(agent_id)
        secret, key = self.store.issue_key(agent_id)
        self.store.audit("admin", agent_id, {"op": "rotate_key", "by": by, "revoked": n, "key": key["prefix"]})
        return secret, key

    # ── 인증 ──
    def exchange_token(self, header: str | None) -> dict[str, Any]:
        k = self.store.resolve_key(_bearer(header))
        if not k:
            raise AuthError("키가 없거나 폐기·만료됐다")
        a = self.agent(k["agent_id"])
        if a["status"] != "active":
            raise AuthError("활성 상태가 아닌 에이전트")
        tok, exp = self.store.issue_token(a["id"], k["id"])
        self.store.audit("auth", a["id"], {"op": "token", "key": k["prefix"], "expires_at": exp})
        return {"token": tok, "expires_at": exp, "agent_id": a["id"]}

    def authenticate(self, header: str | None) -> tuple[dict[str, Any], str]:
        secret = _bearer(header)
        if secret.startswith("pvt_"):
            t = self.store.resolve_token(secret)
            if not t:
                raise AuthError("토큰이 없거나 만료됐다")
            return self.agent(t["agent_id"]), "token"
        k = self.store.resolve_key(secret)
        if not k:
            raise AuthError("키가 없거나 폐기·만료됐다")
        return self.agent(k["agent_id"]), "key"

    # ── 판정 ──
    def decide(self, header: str | None, body: Any) -> dict[str, Any]:
        agent, auth = self.authenticate(header)
        req = clean_request(body)
        ap = None
        if req.get("approval_id"):
            ap = self.store.get_approval(req["approval_id"])
            if ap and ap["agent_id"] != agent["id"]:
                ap = None
        ts = time.time()
        ctx = {"auth": auth, "now": now_utc(), "recent_high_risk": self.store.recent_high(agent["id"], ts),
               "approval": ap, "approved_components": self.store.components()}
        res = policy.decide(agent, req, ctx)
        # 빈도 탐지는 '행위' 를 센다: 승인 대기(require_approval)는 아직 행위가 아니므로 세지 않고, 승인 뒤 다시 묻는
        # 같은 요청이 허용 · 거부로 끝날 때 한 번만 센다(예전에는 처음 물을 때와 승인 뒤 다시 물을 때 두 번 세어,
        # 승인받은 정상 송금 몇 건만으로 자동 중단이 걸렸다). 거부된 시도는 공격 신호라 센다.
        if res["high"] and res["decision"] != "require_approval":
            self.store.record_call(agent["id"], True, ts)
        out = {k: res[k] for k in ("decision", "control", "reason", "checks", "flags", "kind", "request_hash")}
        if res["decision"] == "require_approval":
            if ap and ap.get("status") == "pending" and ap.get("request_hash") == res["request_hash"]:
                out["approval_id"] = ap["id"]
            else:
                out["approval_id"] = self.store.create_approval(agent["id"], req, res["request_hash"])["id"]
        keep_provenance = agent["levels"].get("audit_trail", 0) >= 2
        payload = {"tool": req["tool"], "kind": res["kind"], "decision": res["decision"], "control": res["control"], "reason": res["reason"],
                   "flags": res["flags"], "auth": auth, "request_hash": res["request_hash"], "approval_id": out.get("approval_id")}
        if keep_provenance:   # 감사 기록 통제가 AI까지일 때만 입력 출처 · 인자를 남긴다
            payload.update(input_sources=req["input_sources"], args=req["args"], on_behalf_of=req.get("on_behalf_of"))
        out["decision_id"] = self.store.audit("decision", agent["id"], payload)["seq"]
        if res["suspend"]:
            self.set_status(agent["id"], "suspended", by="system", reason=res["reason"])
            out["suspended"] = True
        return out

    def approval_for_agent(self, header: str | None, aid: str) -> dict[str, Any]:
        agent, _ = self.authenticate(header)
        ap = self.store.get_approval(aid)
        if not ap or ap["agent_id"] != agent["id"]:
            raise RuntimeError_("없는 승인 요청", 404)
        return {k: ap[k] for k in ("id", "status", "created_at", "decided_at")}

    def decide_approval(self, aid: str, approve: bool, by: str = "admin") -> dict[str, Any]:
        ap = self.store.decide_approval(aid, approve, by)
        if not ap:
            raise RuntimeError_("없거나 이미 처리한 승인 요청", 409)
        self.store.audit("approval", ap["agent_id"], {"op": "approve" if approve else "deny", "approval_id": aid, "by": by,
                                                      "request_hash": ap["request_hash"]})
        return ap
