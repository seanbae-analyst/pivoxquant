"""런타임 저장소 — SQLite(표준 라이브러리). 에이전트 등록부 · 키와 단기 토큰 · 승인 구성요소 · 승인 대기열 · 감사 기록.

비밀값은 저장하지 않는다: API 키와 토큰은 HMAC-SHA256(pepper, 값)만 남기고, 원문은 발급할 때 한 번만 돌려준다.
pepper 는 환경변수 PIVOX_KEY_PEPPER, 없으면 DB 에 한 번 만들어 둔다(프로토타입 — 운영이라면 DB 밖에 둘 것).
감사 기록은 해시 사슬이다: 줄마다 앞 줄의 해시를 품고, verify_audit() 가 끊긴 곳을 찾는다.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .policy import canonical

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS api_keys(id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, digest TEXT NOT NULL UNIQUE, prefix TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS tokens(digest TEXT PRIMARY KEY, agent_id TEXT NOT NULL, key_id TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS components(name TEXT NOT NULL, version TEXT NOT NULL, sha256 TEXT, note TEXT, PRIMARY KEY(name, version));
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, request TEXT NOT NULL, request_hash TEXT NOT NULL,
  status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT);
CREATE TABLE IF NOT EXISTS calls(agent_id TEXT NOT NULL, ts REAL NOT NULL, high INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS calls_agent_ts ON calls(agent_id, ts);
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL, agent_id TEXT,
  payload TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL);
"""
GENESIS = "0" * 64
TOKEN_TTL = timedelta(minutes=15)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(t: datetime | None) -> str | None:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def parse(s: str | None) -> datetime | None:
    if not s:
        return None
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def chain_hash(prev: str, ts: str, kind: str, agent_id: str | None, payload: str) -> str:
    return hashlib.sha256(canonical([prev, ts, kind, agent_id or "", payload]).encode("utf-8")).hexdigest()


def _locked(fn):
    """연결 하나를 여러 스레드가 쓰므로, 읽기 · 쓰기 모두 잠금 안에서만(RLock 이라 안에서 다시 불러도 된다)."""
    import functools

    @functools.wraps(fn)
    def w(self, *a, **kw):
        with self.lock:
            return fn(self, *a, **kw)
    return w


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.executescript(SCHEMA)
            if self.path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")
        self.pepper = (os.environ.get("PIVOX_KEY_PEPPER") or self._meta("pepper") or self._set_meta("pepper", secrets.token_hex(32))).encode()

    # ── meta ──
    @_locked
    def _meta(self, k: str) -> str | None:
        r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r["v"] if r else None

    @_locked
    def _set_meta(self, k: str, v: str) -> str:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)", (k, v))
        return v

    def digest(self, secret: str) -> str:
        return hmac.new(self.pepper, secret.encode("utf-8"), hashlib.sha256).hexdigest()

    # ── 에이전트 ──
    @_locked
    def put_agent(self, agent: dict[str, Any]) -> dict[str, Any]:
        t = iso(now_utc())
        with self.lock:
            old = self.db.execute("SELECT created_at FROM agents WHERE id=?", (agent["id"],)).fetchone()
            self.db.execute("INSERT OR REPLACE INTO agents(id, data, created_at, updated_at) VALUES(?,?,?,?)",
                            (agent["id"], canonical(agent), old["created_at"] if old else t, t))
        return self.get_agent(agent["id"])

    @_locked
    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT data, created_at, updated_at FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not r:
            return None
        a = json.loads(r["data"])
        a["created_at"], a["updated_at"] = r["created_at"], r["updated_at"]
        return a

    @_locked
    def list_agents(self) -> list[dict[str, Any]]:
        ids = [r["id"] for r in self.db.execute("SELECT id FROM agents ORDER BY created_at")]
        return [a for a in (self.get_agent(i) for i in ids) if a]

    # ── 키 · 토큰 ──
    @_locked
    def issue_key(self, agent_id: str, ttl_days: int | None = 90) -> tuple[str, dict[str, Any]]:
        secret = "pvx_" + secrets.token_urlsafe(32)
        kid = "key_" + secrets.token_hex(6)
        exp = iso(now_utc() + timedelta(days=ttl_days)) if ttl_days else None
        with self.lock:
            self.db.execute("INSERT INTO api_keys(id, agent_id, digest, prefix, created_at, expires_at) VALUES(?,?,?,?,?,?)",
                            (kid, agent_id, self.digest(secret), secret[:10], iso(now_utc()), exp))
        return secret, {"id": kid, "prefix": secret[:10], "expires_at": exp}

    @_locked
    def revoke_keys(self, agent_id: str) -> int:
        with self.lock:
            n = self.db.execute("UPDATE api_keys SET revoked_at=? WHERE agent_id=? AND revoked_at IS NULL", (iso(now_utc()), agent_id)).rowcount
            self.db.execute("DELETE FROM tokens WHERE agent_id=?", (agent_id,))
        return n

    @_locked
    def drop_tokens(self, agent_id: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM tokens WHERE agent_id=?", (agent_id,))

    @_locked
    def list_keys(self, agent_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute(
            "SELECT id, prefix, created_at, expires_at, revoked_at FROM api_keys WHERE agent_id=? ORDER BY created_at", (agent_id,))]

    @_locked
    def resolve_key(self, secret: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM api_keys WHERE digest=?", (self.digest(secret),)).fetchone()
        if not r or r["revoked_at"]:
            return None
        if r["expires_at"] and parse(r["expires_at"]) <= now_utc():
            return None
        return dict(r)

    @_locked
    def issue_token(self, agent_id: str, key_id: str) -> tuple[str, str]:
        tok = "pvt_" + secrets.token_urlsafe(32)
        exp = iso(now_utc() + TOKEN_TTL)
        with self.lock:
            self.db.execute("DELETE FROM tokens WHERE expires_at < ?", (iso(now_utc()),))
            self.db.execute("INSERT INTO tokens(digest, agent_id, key_id, expires_at) VALUES(?,?,?,?)", (self.digest(tok), agent_id, key_id, exp))
        return tok, exp

    @_locked
    def resolve_token(self, tok: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM tokens WHERE digest=?", (self.digest(tok),)).fetchone()
        if not r or parse(r["expires_at"]) <= now_utc():
            return None
        k = self.db.execute("SELECT revoked_at FROM api_keys WHERE id=?", (r["key_id"],)).fetchone()
        return None if (not k or k["revoked_at"]) else dict(r)

    # ── 승인 구성요소 ──
    @_locked
    def components(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT name, version, sha256, note FROM components ORDER BY name, version")]

    @_locked
    def put_component(self, name: str, version: str, sha256: str | None = None, note: str = "") -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO components(name, version, sha256, note) VALUES(?,?,?,?)", (name, version, sha256 or None, note))

    @_locked
    def del_component(self, name: str, version: str) -> int:
        with self.lock:
            return self.db.execute("DELETE FROM components WHERE name=? AND version=?", (name, version)).rowcount

    # ── 승인 대기열 ──
    @_locked
    def create_approval(self, agent_id: str, req: dict[str, Any], rh: str) -> dict[str, Any]:
        aid = "apr_" + secrets.token_hex(8)
        with self.lock:
            self.db.execute("INSERT INTO approvals(id, agent_id, request, request_hash, status, created_at) VALUES(?,?,?,?,?,?)",
                            (aid, agent_id, canonical(req), rh, "pending", iso(now_utc())))
        return self.get_approval(aid)

    @_locked
    def get_approval(self, aid: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM approvals WHERE id=?", (aid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["request"] = json.loads(d["request"])
        return d

    @_locked
    def list_approvals(self, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        q, p = "SELECT id FROM approvals", []
        if status:
            q, p = q + " WHERE status=?", [status]
        ids = [r["id"] for r in self.db.execute(q + " ORDER BY created_at DESC LIMIT ?", (*p, limit))]
        return [self.get_approval(i) for i in ids]

    @_locked
    def decide_approval(self, aid: str, approve: bool, by: str) -> dict[str, Any] | None:
        with self.lock:
            n = self.db.execute("UPDATE approvals SET status=?, decided_at=?, decided_by=? WHERE id=? AND status='pending'",
                                ("approved" if approve else "denied", iso(now_utc()), by, aid)).rowcount
        return self.get_approval(aid) if n else None

    # ── 호출 빈도 (탐지용) ──
    @_locked
    def record_call(self, agent_id: str, high: bool, ts: float) -> None:
        with self.lock:
            self.db.execute("INSERT INTO calls(agent_id, ts, high) VALUES(?,?,?)", (agent_id, ts, int(high)))
            self.db.execute("DELETE FROM calls WHERE ts < ?", (ts - 3600,))

    @_locked
    def recent_high(self, agent_id: str, ts: float, window: float = 60.0) -> int:
        return self.db.execute("SELECT COUNT(*) AS n FROM calls WHERE agent_id=? AND high=1 AND ts >= ?", (agent_id, ts - window)).fetchone()["n"]

    # ── 감사 기록 (해시 사슬) ──
    @_locked
    def audit(self, kind: str, agent_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        body = canonical(payload)
        with self.lock:
            last = self.db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev = last["hash"] if last else GENESIS
            ts = iso(now_utc())
            h = chain_hash(prev, ts, kind, agent_id, body)
            cur = self.db.execute("INSERT INTO audit(ts, kind, agent_id, payload, prev, hash) VALUES(?,?,?,?,?,?)", (ts, kind, agent_id, body, prev, h))
        return {"seq": cur.lastrowid, "ts": ts, "hash": h}

    @_locked
    def audit_rows(self, limit: int = 200, agent_id: str | None = None) -> list[dict[str, Any]]:
        q, p = "SELECT * FROM audit", []
        if agent_id:
            q, p = q + " WHERE agent_id=?", [agent_id]
        rows = [dict(r) for r in self.db.execute(q + " ORDER BY seq DESC LIMIT ?", (*p, limit))]
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    @_locked
    def verify_audit(self) -> dict[str, Any]:
        prev, n = GENESIS, 0
        for r in self.db.execute("SELECT * FROM audit ORDER BY seq"):
            if r["prev"] != prev or chain_hash(r["prev"], r["ts"], r["kind"], r["agent_id"], r["payload"]) != r["hash"]:
                return {"ok": False, "checked": n, "broken_at": r["seq"]}
            prev, n = r["hash"], n + 1
        return {"ok": True, "checked": n, "head": prev}
