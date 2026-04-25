#!/usr/bin/env python3
"""
Critical endpoints probe — 9 iterations, 5 minutes apart (total ~40 min).

This is what most people would call "synthetic monitoring" — the goal is to
catch intermittent failures (cold starts, KIS rate limits, FMP 402 spikes)
that a single-shot check misses.

Endpoints probed each iteration:
  - GET /api/health                       → must be 200 + {"status":"ok"}
  - GET /api/agent/status                 → must be 200
  - GET /api/search?q=AAPL                → 200 expected (auth) or 401 (unauth mode)
  - GET /api/market/indices?region=us     → 200 expected (auth) or 401 (unauth)
  - GET /api/market/indices?region=kr     → 200 expected (auth) or 401 (unauth)
  - GET /api/realtime/status              → 200 expected (auth) or 401 (unauth)

Issue rules:
  - Any endpoint whose observed-state differs from expected → ISSUE
  - /api/health failing even once in 9 iterations          → ISSUE (higher severity)

Controls:
  - ITER_COUNT env (default 9)
  - ITER_SLEEP_S env (default 300, i.e. 5 min). Tests can set to 1.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import ssl
import urllib.request
import urllib.error

_SSL_CTX: Optional[ssl.SSLContext]
if os.environ.get("INSECURE_SSL") == "1":
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE
else:
    _SSL_CTX = None

BASE_URL = os.environ.get(
    "BASE_URL",
    "https://RAILWAY_BACKEND_HOST.up.railway.app",
).rstrip("/")
RESULTS_PATH = Path(os.environ.get("RESULTS_PATH", "nightly_artifacts/critical_endpoints.jsonl"))
ITER_COUNT = int(os.environ.get("ITER_COUNT", "9"))
ITER_SLEEP_S = float(os.environ.get("ITER_SLEEP_S", "300"))
TIMEOUT_S = float(os.environ.get("HTTP_TIMEOUT_S", "15"))


def _request(method: str, url: str, cookies: Optional[list[str]] = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, method=method)
    if cookies:
        req.add_header("Cookie", "; ".join(cookies))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_SSL_CTX) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b""
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e).encode()


def _login_dev() -> Optional[list[str]]:
    secret = os.environ.get("DEV_LOGIN_SECRET")
    if not secret:
        return None
    req = urllib.request.Request(
        f"{BASE_URL}/api/auth/dev-login",
        data=json.dumps({"secret": secret}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_SSL_CTX) as resp:
            raw = resp.headers.get("Set-Cookie", "")
    except Exception:
        return None
    if not raw:
        return None
    cookies = []
    for chunk in raw.split(","):
        head = chunk.split(";", 1)[0].strip()
        if "=" in head and not head.lower().startswith(
            ("expires", "path", "domain", "max-age", "samesite", "secure", "httponly")
        ):
            cookies.append(head)
    return cookies or [raw.split(";", 1)[0].strip()]


# (name, path, expected_when_authed)
PROBES = [
    ("health",             "/api/health",                    200),
    ("agent_status",       "/api/agent/status",              200),
    ("search_aapl",        "/api/search?q=AAPL",             200),
    ("indices_us",         "/api/market/indices?region=us",  200),
    ("indices_kr",         "/api/market/indices?region=kr",  200),
    ("realtime_status",    "/api/realtime/status",           200),
]

# Which endpoints are public (no auth gate at all)
PUBLIC_PATHS = {"/api/health", "/api/agent/status"}


def evaluate(path: str, status: int, body: bytes, authed: bool) -> tuple[bool, str]:
    # /api/health must return 200 + {"status":"ok"} regardless of auth
    if path == "/api/health":
        if status != 200:
            return True, f"/api/health HTTP {status}"
        try:
            data = json.loads(body)
            if data.get("status") != "ok":
                return True, f"/api/health body status!=ok: {body[:200]!r}"
        except Exception:
            return True, f"/api/health non-JSON body: {body[:200]!r}"
        return False, "ok"

    # /api/agent/status public — 200 expected
    if path == "/api/agent/status":
        if status != 200:
            return True, f"/api/agent/status HTTP {status}"
        return False, "ok"

    # Auth-gated endpoints
    if not authed:
        # In UNAUTH mode, 401 is the correct state
        if status == 401:
            return False, "auth-gate-ok (unauth)"
        return True, f"unauth probe expected 401, got {status}"

    # AUTH mode
    if status != 200:
        return True, f"HTTP {status} (expected 200)"

    # Specific body checks
    if path == "/api/search?q=AAPL":
        try:
            data = json.loads(body)
        except Exception:
            return True, f"search body non-JSON: {body[:200]!r}"
        # Accept either list or {"results":[...]}
        results = data if isinstance(data, list) else data.get("results") or data.get("data") or []
        if not results:
            return True, f"search results empty for q=AAPL: {body[:300]!r}"
        return False, f"ok ({len(results)} results)"

    return False, "ok"


def main() -> int:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cookies = _login_dev()
    authed = cookies is not None
    print(f"[critical_endpoints] mode={'AUTH' if authed else 'UNAUTH'} iters={ITER_COUNT} sleep={ITER_SLEEP_S}s")

    all_results: list[dict] = []
    for i in range(ITER_COUNT):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        print(f"[critical_endpoints] iter {i+1}/{ITER_COUNT} @ {ts}")
        for name, path, _expected in PROBES:
            status, body = _request("GET", f"{BASE_URL}{path}", cookies=cookies)
            is_issue, reason = evaluate(path, status, body, authed)
            all_results.append(
                {
                    "iter": i + 1,
                    "ts": ts,
                    "name": name,
                    "path": path,
                    "status": status,
                    "body_preview": body[:200].decode("utf-8", errors="replace"),
                    "issue": is_issue,
                    "reason": reason,
                    "mode": "AUTH" if authed else "UNAUTH",
                }
            )
            if is_issue:
                print(f"  [ISSUE] {name} iter={i+1}: {reason}")
        if i < ITER_COUNT - 1:
            time.sleep(ITER_SLEEP_S)

    with RESULTS_PATH.open("w") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    issues = [r for r in all_results if r["issue"]]
    print(f"[critical_endpoints] total_probes={len(all_results)} issues={len(issues)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
