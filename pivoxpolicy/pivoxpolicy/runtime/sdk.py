"""에이전트 쪽 클라이언트 — 도구를 쓰기 직전에 런타임에 묻는다. 표준 라이브러리(urllib)만 쓴다.

    from pivoxpolicy.runtime.sdk import Guard, Blocked, ApprovalRequired
    guard = Guard("http://127.0.0.1:8787", api_key=os.environ["PIVOX_AGENT_KEY"])

    @guard.tool("transfer")
    def transfer(amount, target, *, input_sources=()):
        ...                      # 허용될 때만 실행된다

    transfer(500_000, "vendor-1", input_sources=[{"kind": "user", "trusted": True}])

장기 키로 단기 토큰(15분)을 받아 쓰고, 만료되면 다시 받는다. 거부되면 Blocked, 사람 승인이 필요하면 ApprovalRequired(approval_id).
"""

from __future__ import annotations

import functools
import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable


class GuardError(Exception):
    pass


class Blocked(GuardError):
    def __init__(self, decision: dict[str, Any]):
        super().__init__(decision.get("reason") or "거부")
        self.decision = decision


class ApprovalRequired(GuardError):
    def __init__(self, decision: dict[str, Any]):
        super().__init__(decision.get("reason") or "사람 승인 필요")
        self.decision, self.approval_id = decision, decision.get("approval_id")


class Guard:
    def __init__(self, base_url: str, api_key: str, use_token: bool = True, timeout: float = 10.0):
        self.base, self.key, self.use_token, self.timeout = base_url.rstrip("/"), api_key, use_token, timeout
        self._tok: str | None = None
        self._tok_exp = 0.0

    def _call(self, method: str, path: str, bearer: str, body: Any = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + bearer, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error")
            except Exception:  # noqa: BLE001
                msg = e.reason
            raise GuardError(f"{e.code} {msg}") from None

    def _bearer(self) -> str:
        if not self.use_token:
            return self.key
        if not self._tok or time.time() > self._tok_exp - 30:
            r = self._call("POST", "/v1/token", self.key, {})
            self._tok, self._tok_exp = r["token"], time.time() + 14 * 60
        return self._tok

    def check(self, tool: str, *, action: str = "call", args: dict | None = None, input_sources: list | None = None,
              context: dict | None = None, component: dict | None = None, approval_id: str | None = None,
              on_behalf_of: str | None = None) -> dict[str, Any]:
        body = {"tool": tool, "action": action, "args": args or {}, "input_sources": list(input_sources or []), "context": context or {}}
        for k, v in (("component", component), ("approval_id", approval_id), ("on_behalf_of", on_behalf_of)):
            if v:
                body[k] = v
        return self._call("POST", "/v1/decide", self._bearer(), body)

    def approval(self, approval_id: str) -> dict[str, Any]:
        return self._call("GET", f"/v1/approvals/{approval_id}", self._bearer())

    def wait_approval(self, approval_id: str, timeout: float = 300, every: float = 2.0) -> str:
        end = time.time() + timeout
        while time.time() < end:
            st = self.approval(approval_id)["status"]
            if st != "pending":
                return st
            time.sleep(every)
        return "pending"

    def tool(self, name: str, **fixed: Any) -> Callable:
        """함수를 감싼다 — 호출할 때 인자(amount, target, customer …)를 args 로 보내 판정받고, 허용일 때만 실행한다.
        input_sources · context · approval_id 는 키워드로 넘긴다."""
        def deco(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*a: Any, input_sources: list | None = None, context: dict | None = None, approval_id: str | None = None, **kw: Any):
                import inspect
                bound = inspect.signature(fn).bind_partial(*a, **kw)
                args = {k: v for k, v in bound.arguments.items() if isinstance(v, (str, int, float, bool)) or v is None}
                d = self.check(name, args={**fixed, **args}, input_sources=input_sources, context=context, approval_id=approval_id)
                if d["decision"] == "allow":
                    return fn(*a, **kw)
                if d["decision"] == "require_approval":
                    raise ApprovalRequired(d)
                raise Blocked(d)
            return wrapper
        return deco
