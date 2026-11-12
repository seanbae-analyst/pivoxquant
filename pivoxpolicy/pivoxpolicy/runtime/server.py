"""런타임 서버 — 표준 라이브러리(wsgiref)만 쓰는 WSGI 앱. `python3 -m pivoxpolicy.cli serve` 로 띄운다.

에이전트 API (Authorization: Bearer <키 pvx_… 또는 토큰 pvt_…>)
  POST /v1/token                 장기 키 → 15분짜리 단기 토큰
  POST /v1/decide                도구 호출 하나 판정 → {decision: allow|deny|require_approval, reason, control, checks, approval_id}
  GET  /v1/approvals/<id>        승인 요청 상태
관리자 (세션 쿠키 + CSRF 헤더, 관리자 토큰으로 로그인)
  GET  /admin                    콘솔
  POST /admin/login · /admin/logout · GET /admin/api/session
  /admin/api/meta · agents · agents/<id> · agents/<id>/status · rotate · redteam · approvals · audit · audit/verify · components

보안: 본문 64KB · JSON 만 · 관리자 쓰기 요청은 CSRF 헤더와 같은 출처만 · 로그인 시도 제한 · 쿠키 HttpOnly SameSite=Strict ·
모든 응답에 nosniff · no-store · 엄격한 CSP(script-src 'self').
"""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Callable
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .. import obligations as obligations_mod
from . import cases as cases_mod
from . import redteam
from .service import AuthError, PROFILE_TOOLS, Runtime, RuntimeError_, clean_levels
from .store import Store

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
MAX_BODY = 64 * 1024
SESSION_TTL = 8 * 3600
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
       "font-src https://cdn.jsdelivr.net; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
BASE_HEADERS = [("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"), ("Cache-Control", "no-store"),
                ("X-Frame-Options", "DENY"), ("Content-Security-Policy", CSP)]


class HttpError(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status, self.msg = status, msg


_REASON = {200: "OK", 201: "Created", 204: "No Content", 302: "Found", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
           404: "Not Found", 405: "Method Not Allowed", 409: "Conflict", 413: "Payload Too Large", 415: "Unsupported Media Type",
           429: "Too Many Requests", 500: "Internal Server Error"}


def _meta_payload() -> dict[str, Any]:
    """콘솔이 쓰는 고정 데이터 — 통제 설명 · 에이전트 종류 · 관할 프리셋 · 기본 도구 · 원형 이름."""
    from .. import sim
    p = sim.payload()
    cs = cases_mod.load_cases()
    return {"controls": p["controls"], "profiles": p["agent_profiles"], "presets": [{k: x[k] for k in ("id", "label", "levels")} for x in p["presets"]],
            "profile_tools": PROFILE_TOOLS, "scenarios": [{"id": s["id"], "title": s["title"]} for s in p["scenarios"]],
            "cases": [{k: c.get(k) for k in ("id", "kind", "title", "story", "scenario")} for c in cs],
            "matrix_default": ["none", "US-2", "EU-2", "KR-2", "all"], "kinds": ["read", "write", "send", "exec", "pay"],
            "regulation": p["regulation"], "jurisdictions": p["jurisdictions"], "obligations": _obligations_meta()}


def _obligations_meta() -> dict[str, Any]:
    lib = obligations_mod.load_library("securities")
    return {"sector": lib.get("sector"), "label": lib.get("label"), "reviewed_by_counsel": bool(lib.get("reviewed_by_counsel")),
            "as_of": str(lib.get("as_of") or ""), "profile": lib.get("profile") or {}, "modes": list(obligations_mod.MODES),
            "mode_ko": obligations_mod.MODE_KO, "force_ko": obligations_mod.FORCE_KO}


class App:
    def __init__(self, rt: Runtime, admin_token: str, secure_cookie: bool = False):
        if not admin_token or len(admin_token) < 16:
            raise ValueError("관리자 토큰은 16자 이상")
        self.rt, self.admin_token, self.secure = rt, admin_token, secure_cookie
        self.sessions: dict[str, dict[str, Any]] = {}
        self.login_tries: dict[str, list[float]] = {}
        self.lock = threading.Lock()
        self._meta: dict[str, Any] | None = None
        self.routes: list[tuple[str, re.Pattern, Callable]] = [
            ("GET", re.compile(r"^/$"), self.root), ("GET", re.compile(r"^/healthz$"), self.health),
            ("POST", re.compile(r"^/v1/token$"), self.v1_token), ("POST", re.compile(r"^/v1/decide$"), self.v1_decide),
            ("GET", re.compile(r"^/v1/approvals/(apr_[0-9a-f]{16})$"), self.v1_approval),
            ("GET", re.compile(r"^/admin/?$"), self.console), ("GET", re.compile(r"^/admin/assets/(runtime-ui\.js)$"), self.asset),
            ("POST", re.compile(r"^/admin/login$"), self.login), ("POST", re.compile(r"^/admin/logout$"), self.logout),
            ("GET", re.compile(r"^/admin/api/session$"), self.session_info),
            ("GET", re.compile(r"^/admin/api/meta$"), self.a(self.meta)),
            ("GET", re.compile(r"^/admin/api/agents$"), self.a(self.agents)), ("POST", re.compile(r"^/admin/api/agents$"), self.a(self.register)),
            ("GET", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)$"), self.a(self.agent)),
            ("PATCH", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)$"), self.a(self.update)),
            ("POST", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)/status$"), self.a(self.status)),
            ("POST", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)/rotate$"), self.a(self.rotate)),
            ("POST", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)/redteam$"), self.a(self.redteam)),
            ("POST", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)/cases$"), self.a(self.run_cases)),
            ("POST", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)/matrix$"), self.a(self.run_matrix)),
            ("POST", re.compile(r"^/admin/api/agents/(agt_[a-z0-9]+)/obligations$"), self.a(self.obligations)),
            ("GET", re.compile(r"^/admin/api/approvals$"), self.a(self.approvals)),
            ("POST", re.compile(r"^/admin/api/approvals/(apr_[0-9a-f]{16})$"), self.a(self.approve)),
            ("GET", re.compile(r"^/admin/api/audit$"), self.a(self.audit)), ("GET", re.compile(r"^/admin/api/audit/verify$"), self.a(self.verify)),
            ("GET", re.compile(r"^/admin/api/components$"), self.a(self.components)),
            ("POST", re.compile(r"^/admin/api/components$"), self.a(self.add_component)),
            ("POST", re.compile(r"^/admin/api/components/delete$"), self.a(self.del_component)),
        ]

    # ── WSGI ──
    def __call__(self, environ, start_response):
        method, path = environ.get("REQUEST_METHOD", "GET"), environ.get("PATH_INFO", "/")
        try:
            for m, rx, fn in self.routes:
                mt = rx.match(path)
                if mt:
                    if m != method:
                        continue
                    return fn(environ, start_response, *mt.groups())
            if any(rx.match(path) for _, rx, _ in self.routes):
                raise HttpError(405, "허용하지 않는 메서드")
            raise HttpError(404, "없는 경로")
        except HttpError as e:
            return self.json(start_response, {"error": e.msg}, e.status)
        except AuthError as e:
            return self.json(start_response, {"error": str(e)}, 401)
        except RuntimeError_ as e:
            return self.json(start_response, {"error": str(e)}, e.status)
        except Exception as e:  # noqa: BLE001 — 내부 오류 내용을 밖으로 내보내지 않는다
            print(f"[pivoxpolicy runtime] 500 {method} {path}: {type(e).__name__}: {e}", file=sys.stderr)
            return self.json(start_response, {"error": "내부 오류"}, 500)

    def json(self, start_response, obj: Any, status: int = 200, extra: list | None = None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        start_response(f"{status} {_REASON.get(status, 'Status')}", [("Content-Type", "application/json; charset=utf-8"),
                       ("Content-Length", str(len(body))), *BASE_HEADERS, *(extra or [])])
        return [body]

    def body(self, environ) -> Any:
        ctype = (environ.get("CONTENT_TYPE") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise HttpError(415, "Content-Type: application/json 만 받는다")
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            raise HttpError(400, "Content-Length 오류") from None
        if n > MAX_BODY:
            raise HttpError(413, "본문이 너무 크다(64KB 까지)")
        raw = environ["wsgi.input"].read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8") or "null")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HttpError(400, "JSON 이 아니다") from None

    def obj(self, environ) -> dict[str, Any]:
        """본문이 JSON 객체(또는 비어 있음)일 때만 — 목록 · 숫자 본문이 handler 안에서 500 이 되지 않게."""
        d = self.body(environ)
        if d is None:
            return {}
        if not isinstance(d, dict):
            raise HttpError(400, "본문은 JSON 객체여야 한다")
        return d

    # ── 공개 ──
    def root(self, environ, sr):
        sr("302 Found", [("Location", "/admin"), *BASE_HEADERS])
        return [b""]

    def health(self, environ, sr):
        return self.json(sr, {"ok": True})

    # ── 에이전트 API ──
    def v1_token(self, environ, sr):
        return self.json(sr, self.rt.exchange_token(environ.get("HTTP_AUTHORIZATION")), 201)

    def v1_decide(self, environ, sr):
        auth = environ.get("HTTP_AUTHORIZATION")
        self.rt.authenticate(auth)              # 본문을 읽기 전에 인증부터
        return self.json(sr, self.rt.decide(auth, self.body(environ)))

    def v1_approval(self, environ, sr, aid):
        return self.json(sr, self.rt.approval_for_agent(environ.get("HTTP_AUTHORIZATION"), aid))

    # ── 관리자: 세션 ──
    def _cookie(self, environ) -> str | None:
        for part in (environ.get("HTTP_COOKIE") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "pvx_admin":
                return v
        return None

    def _session(self, environ) -> dict[str, Any] | None:
        sid = self._cookie(environ)
        with self.lock:
            s = self.sessions.get(sid or "")
            if s and s["exp"] < time.time():
                self.sessions.pop(sid, None)
                return None
            return s

    def _same_origin(self, environ) -> bool:
        origin = environ.get("HTTP_ORIGIN")
        if not origin:
            return True          # 같은 출처 fetch 는 Origin 을 안 보낼 수도 있다 — CSRF 헤더가 따로 지킨다
        host = environ.get("HTTP_HOST", "")
        return origin.split("://", 1)[-1] == host

    def a(self, fn: Callable) -> Callable:
        """관리자 API 감싸기 — 세션 필수, GET 이 아니면 CSRF 헤더 · 같은 출처."""
        def wrapped(environ, sr, *args):
            s = self._session(environ)
            if not s:
                raise HttpError(401, "관리자 로그인 필요")
            if environ.get("REQUEST_METHOD") != "GET":
                if not hmac.compare_digest(environ.get("HTTP_X_CSRF") or "", s["csrf"]) or not self._same_origin(environ):
                    raise HttpError(403, "CSRF 확인 실패")
            return fn(environ, sr, *args)
        return wrapped

    def login(self, environ, sr):
        ip = environ.get("REMOTE_ADDR", "?")
        now = time.time()
        with self.lock:
            tries = [t for t in self.login_tries.get(ip, []) if t > now - 300]
            if len(tries) >= 10:
                raise HttpError(429, "로그인 시도가 너무 많다. 5분 뒤에 다시")
            self.login_tries[ip] = tries + [now]
        if not self._same_origin(environ):
            raise HttpError(403, "다른 출처에서 온 로그인")
        data = self.body(environ)
        tok = data.get("token") if isinstance(data, dict) else None
        if not isinstance(tok, str) or not hmac.compare_digest(tok, self.admin_token):
            raise HttpError(401, "관리자 토큰이 맞지 않다")
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        with self.lock:
            self.sessions[sid] = {"csrf": csrf, "exp": now + SESSION_TTL}
            self.login_tries.pop(ip, None)
        self.rt.store.audit("admin", None, {"op": "login", "ip": ip})
        cookie = f"pvx_admin={sid}; Path=/admin; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL}" + ("; Secure" if self.secure else "")
        return self.json(sr, {"ok": True, "csrf": csrf}, 200, [("Set-Cookie", cookie)])

    def logout(self, environ, sr):
        sid = self._cookie(environ)
        with self.lock:
            self.sessions.pop(sid or "", None)
        return self.json(sr, {"ok": True}, 200, [("Set-Cookie", "pvx_admin=; Path=/admin; HttpOnly; SameSite=Strict; Max-Age=0")])

    def session_info(self, environ, sr):
        s = self._session(environ)
        return self.json(sr, {"logged_in": bool(s), **({"csrf": s["csrf"]} if s else {})})

    # ── 관리자 콘솔 ──
    def console(self, environ, sr):
        page = (TEMPLATES / "runtime.html").read_text(encoding="utf-8")
        for k in ("tokens.css", "base.css", "runtime.css"):
            page = page.replace("{{" + k.replace(".", "_").upper() + "}}", (TEMPLATES / k).read_text(encoding="utf-8"))
        body = page.encode("utf-8")
        sr("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body))), *BASE_HEADERS])
        return [body]

    def asset(self, environ, sr, name):
        body = (TEMPLATES / name).read_bytes()
        sr("200 OK", [("Content-Type", "text/javascript; charset=utf-8"), ("Content-Length", str(len(body))), *BASE_HEADERS])
        return [body]

    # ── 관리자 API ──
    def meta_data(self) -> dict[str, Any]:
        if self._meta is None:
            self._meta = _meta_payload()
        return self._meta

    def meta(self, environ, sr):
        return self.json(sr, self.meta_data())

    def _with_keys(self, a: dict[str, Any]) -> dict[str, Any]:
        return {**a, "keys": self.rt.store.list_keys(a["id"])}

    def agents(self, environ, sr):
        return self.json(sr, {"agents": [self._with_keys(a) for a in self.rt.store.list_agents()]})

    def register(self, environ, sr):
        agent, secret = self.rt.register(self.body(environ))
        return self.json(sr, {"agent": self._with_keys(agent), "api_key": secret}, 201)

    def agent(self, environ, sr, aid):
        return self.json(sr, self._with_keys(self.rt.agent(aid)))

    def update(self, environ, sr, aid):
        return self.json(sr, self._with_keys(self.rt.update(aid, self.body(environ))))

    def status(self, environ, sr, aid):
        d = self.obj(environ)
        return self.json(sr, self._with_keys(self.rt.set_status(aid, d.get("status"), "admin", str(d.get("reason") or "")[:200])))

    def rotate(self, environ, sr, aid):
        secret, key = self.rt.rotate_key(aid)
        return self.json(sr, {"api_key": secret, "key": key})

    def redteam(self, environ, sr, aid):
        a = self.rt.agent(aid)
        res = redteam.run_all(a, self.rt.store.components())
        self.rt.store.audit("redteam", aid, {"op": "redteam", "summary": res["summary"]})
        return self.json(sr, res)

    def run_cases(self, environ, sr, aid):
        """현재 통제로 공격 팀을 돌린다. levels 를 주면 저장하지 않은 화면의 수준으로 돌린다(샌드박스 — 저장 안 함)."""
        a = self.rt.agent(aid)
        d = self.obj(environ)
        preview = "levels" in d
        if preview:
            a = cases_mod.with_levels(a, clean_levels(d["levels"]))
        res = cases_mod.run_cases(a, approved=self.rt.store.components())
        res["preview"] = preview
        self.rt.store.audit("cases", aid, {"op": "cases", "summary": res["summary"], "preview": preview})
        return self.json(sr, res)

    def run_matrix(self, environ, sr, aid):
        """케이스 × 규제 프리셋. current_levels 를 주면 맨 앞에 '지금 설정' 열을 붙인다."""
        a = self.rt.agent(aid)
        d = self.obj(environ)
        by_id = {p["id"]: p for p in self.meta_data()["presets"]}
        raw = d.get("presets")
        ids = raw if isinstance(raw, list) and raw else self.meta_data()["matrix_default"]
        if any(not isinstance(i, str) for i in ids):
            raise HttpError(400, "presets 는 프리셋 id 문자열 목록")
        chosen = [by_id[i] for i in dict.fromkeys(ids) if i in by_id][:10]
        if not chosen:
            raise HttpError(400, "알 수 없는 규제 프리셋")
        # 적용성 프로필이 있으면(저장된 것 또는 화면의 미리보기) 관할 프리셋 앞에 '이 에이전트에 걸리는 조문' 열 세 개
        prof = self.rt.clean_compliance(d["profile"]) if d.get("profile") is not None else a.get("compliance")
        assessment = obligations_mod.assess(self.rt.lib, prof) if prof else None
        if assessment:
            chosen = [*obligations_mod.preset_columns(assessment), *chosen]
        if "current_levels" in d:
            chosen = [{"id": "current", "label": "지금 설정", "levels": clean_levels(d["current_levels"])}, *chosen]
        res = cases_mod.run_matrix(a, chosen, approved=self.rt.store.components())
        if assessment:   # 결함마다 그 통제를 요구하는 적용 조문과 분류(위반 소지 · 해석 · 가이드라인 · 공백)
            for col in res["presets"]:
                for cell in col["cells"].values():
                    if cell.get("fixes"):
                        cell["link"] = obligations_mod.classify(assessment, cell["fixes"])
            res["obligations"] = {r["id"]: {k: r.get(k) for k in ("doc", "article", "force_ko", "binding", "quote", "quote_verified",
                                                                   "source", "requires", "control", "layer", "extends", "note")}
                                  for r in assessment["applicable"]}
            res["high_impact"] = assessment["high_impact"]
        self.rt.store.audit("cases", aid, {"op": "matrix", "presets": [p["preset"] for p in res["presets"]]})
        return self.json(sr, res)

    def obligations(self, environ, sr, aid):
        """적용 조문 · 미적용 조문(이유) · 모드별 통제 수준 · 지금 수준 기준 충족 여부. profile · levels 를 주면 저장 전 미리보기."""
        a = self.rt.agent(aid)
        d = self.obj(environ)
        prof = self.rt.clean_compliance(d["profile"]) if d.get("profile") is not None else None
        lv = clean_levels(d["levels"]) if "levels" in d else None
        return self.json(sr, self.rt.assess(a, prof, lv))

    def approvals(self, environ, sr):
        qs = environ.get("QUERY_STRING", "")
        st = "pending" if "status=pending" in qs else None
        return self.json(sr, {"approvals": self.rt.store.list_approvals(st)})

    def approve(self, environ, sr, aid):
        d = self.obj(environ)
        return self.json(sr, self.rt.decide_approval(aid, d.get("approve") is True, "admin"))

    def audit(self, environ, sr):
        m = re.search(r"(?:^|&)agent=(agt_[a-z0-9]+)", environ.get("QUERY_STRING", ""))
        return self.json(sr, {"rows": self.rt.store.audit_rows(200, m.group(1) if m else None)})

    def verify(self, environ, sr):
        return self.json(sr, self.rt.store.verify_audit())

    def components(self, environ, sr):
        return self.json(sr, {"components": self.rt.store.components()})

    def add_component(self, environ, sr):
        d = self.obj(environ)
        name, ver, sha = d.get("name"), d.get("version"), d.get("sha256") or None
        if not (isinstance(name, str) and 0 < len(name) <= 60 and isinstance(ver, str) and 0 < len(ver) <= 40):
            raise HttpError(400, "name(60자) · version(40자) 필요")
        if sha is not None and not (isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)):
            raise HttpError(400, "sha256 은 소문자 16진수 64자")
        self.rt.store.put_component(name.strip(), ver.strip(), sha, str(d.get("note") or "")[:120])
        self.rt.store.audit("admin", None, {"op": "component_add", "name": name, "version": ver, "pinned": bool(sha)})
        return self.json(sr, {"components": self.rt.store.components()}, 201)

    def del_component(self, environ, sr):
        d = self.obj(environ)
        n = self.rt.store.del_component(str(d.get("name")), str(d.get("version")))
        self.rt.store.audit("admin", None, {"op": "component_delete", "name": d.get("name"), "version": d.get("version"), "removed": n})
        return self.json(sr, {"components": self.rt.store.components()})


class _Threading(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class _Quiet(WSGIRequestHandler):
    def log_message(self, fmt, *args):          # 요청 줄만 — 헤더(토큰)는 찍지 않는다
        sys.stderr.write("[pivoxpolicy runtime] %s %s\n" % (self.address_string(), fmt % args))


def build_app(db: str | Path, admin_token: str | None = None, secure_cookie: bool | None = None) -> tuple[App, str]:
    token = admin_token or os.environ.get("PIVOX_ADMIN_TOKEN") or secrets.token_urlsafe(24)
    secure = bool(os.environ.get("PIVOX_SECURE_COOKIE")) if secure_cookie is None else secure_cookie
    return App(Runtime(Store(db)), token, secure), token


def serve(host: str = "127.0.0.1", port: int = 8787, db: str | Path = "runtime.db") -> None:
    gave = bool(os.environ.get("PIVOX_ADMIN_TOKEN"))
    app, token = build_app(db)
    srv = make_server(host, port, app, server_class=_Threading, handler_class=_Quiet)
    print(f"PivoxPolicy 런타임 — http://{host}:{port}/admin  (DB {db})")
    if not gave:
        print(f"관리자 토큰(이번 실행에만): {token}\n  고정하려면 PIVOX_ADMIN_TOKEN 환경변수를 16자 이상으로 지정한다.")
    srv.serve_forever()
