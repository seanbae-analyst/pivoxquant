#!/usr/bin/env python3
"""
Nightly market indices consistency check.

Validates:
  - /api/market/indices?region=us
  - /api/market/indices?region=kr

For each index returned:
  - range_52w == [0, 0]                  → ISSUE
  - level deviates >30% from range_52w   → ISSUE (stale/corrupt)
  - is_stale=true + range_52w=null       → OK (documented fallback)
  - range_52w=null + is_stale!=true      → ISSUE (silent degradation)

If endpoint returns 401 (auth-gated), this is treated as OK in unauth mode —
the check is SKIPPED with status=auth-gated, not an issue.

Exit code: always 0 — results written to RESULTS_PATH.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

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
RESULTS_PATH = Path(os.environ.get("RESULTS_PATH", "nightly_artifacts/indices_consistency.jsonl"))
TIMEOUT_S = float(os.environ.get("HTTP_TIMEOUT_S", "15"))


def _request(
    method: str,
    url: str,
    *,
    body: Optional[bytes] = None,
    headers: Optional[dict] = None,
    cookies: Optional[list[str]] = None,
) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, data=body, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if cookies:
        req.add_header("Cookie", "; ".join(cookies))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_SSL_CTX) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", dict(e.headers or {})
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e).encode(), {}


def _login_dev() -> Optional[list[str]]:
    secret = os.environ.get("DEV_LOGIN_SECRET")
    if not secret:
        return None
    status, _, hdrs = _request(
        "POST",
        f"{BASE_URL}/api/auth/dev-login",
        body=json.dumps({"secret": secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    if status != 200:
        return None
    raw = hdrs.get("Set-Cookie") or hdrs.get("set-cookie") or ""
    cookies = []
    for chunk in raw.split(","):
        head = chunk.split(";", 1)[0].strip()
        if "=" in head and not head.lower().startswith(
            ("expires", "path", "domain", "max-age", "samesite", "secure", "httponly")
        ):
            cookies.append(head)
    return cookies or [raw.split(";", 1)[0].strip()] if raw else None


def _evaluate_index(item: dict) -> tuple[bool, str]:
    """Return (is_issue, reason)."""
    level = item.get("level") or item.get("price") or item.get("value")
    range_52w = item.get("range_52w") or item.get("range52w") or item.get("yearRange")
    is_stale = bool(item.get("is_stale") or item.get("stale"))

    # Acceptable: stale + null range
    if is_stale and (range_52w is None or range_52w == [] or range_52w == [None, None]):
        return False, "stale-with-null-range (documented fallback)"

    # range_52w == [0, 0] → corruption
    if range_52w == [0, 0] or range_52w == [0.0, 0.0]:
        return True, "range_52w=[0,0] (corrupt data)"

    # null range without stale flag
    if range_52w is None or range_52w in ([], [None, None]):
        return True, "range_52w=null but is_stale is falsy (silent degradation)"

    # deviation check
    if isinstance(range_52w, list) and len(range_52w) == 2:
        try:
            lo, hi = float(range_52w[0]), float(range_52w[1])
            lv = float(level) if level is not None else None
        except (TypeError, ValueError):
            return True, f"range_52w or level not numeric: range={range_52w}, level={level}"
        if lv is None:
            return True, "level missing"
        if lo <= 0 or hi <= 0 or hi < lo:
            return True, f"range_52w invalid: [{lo}, {hi}]"
        # Deviation: level vs [lo, hi]. If level is more than 30% outside band, flag.
        span = hi - lo
        if span == 0:
            return True, f"range_52w span=0 (lo==hi=={lo})"
        # Allow level in [lo - 0.3*span, hi + 0.3*span]
        tolerance = 0.3 * span
        if lv < (lo - tolerance) or lv > (hi + tolerance):
            pct_out = max((lo - lv) / span, (lv - hi) / span) * 100
            return True, f"level {lv} deviates {pct_out:.1f}% of span from [{lo},{hi}]"

    return False, "ok"


def probe_region(region: str, cookies: Optional[list[str]]) -> list[dict]:
    url = f"{BASE_URL}/api/market/indices?region={region}"
    status, body, _ = _request("GET", url, cookies=cookies)
    out: list[dict] = []
    base = {"region": region, "url": url, "status": status}

    if status == 401:
        out.append({**base, "index": "(endpoint)", "issue": False, "reason": "auth-gated (skipped)"})
        return out
    if status != 200:
        out.append({**base, "index": "(endpoint)", "issue": True, "reason": f"HTTP {status}"})
        return out

    try:
        data = json.loads(body)
    except Exception as e:
        out.append({**base, "index": "(endpoint)", "issue": True, "reason": f"JSON parse error: {e}"})
        return out

    # Accept both dict-of-indices and list-of-indices shapes
    items: list[dict] = []
    if isinstance(data, list):
        items = [d for d in data if isinstance(d, dict)]
    elif isinstance(data, dict):
        # Might be {"indices": [...]} or {"KOSPI": {...}}
        if "indices" in data and isinstance(data["indices"], list):
            items = [d for d in data["indices"] if isinstance(d, dict)]
        else:
            for k, v in data.items():
                if isinstance(v, dict):
                    v = {**v, "symbol": v.get("symbol") or k}
                    items.append(v)

    if not items:
        out.append(
            {
                **base,
                "index": "(empty)",
                "issue": True,
                "reason": f"no index items parsed — body preview: {body[:300].decode('utf-8','replace')}",
            }
        )
        return out

    for item in items:
        sym = item.get("symbol") or item.get("name") or item.get("index") or "?"
        is_issue, reason = _evaluate_index(item)
        out.append(
            {
                **base,
                "index": sym,
                "issue": is_issue,
                "reason": reason,
                "level": item.get("level") or item.get("price") or item.get("value"),
                "range_52w": item.get("range_52w") or item.get("range52w") or item.get("yearRange"),
                "is_stale": bool(item.get("is_stale") or item.get("stale")),
            }
        )
    return out


def main() -> int:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cookies = _login_dev()
    print(f"[indices_consistency] mode={'AUTH' if cookies else 'UNAUTH'}")

    results = probe_region("us", cookies) + probe_region("kr", cookies)
    with RESULTS_PATH.open("w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    issues = [r for r in results if r.get("issue")]
    print(f"[indices_consistency] checked={len(results)} issues={len(issues)}")
    for r in issues[:10]:
        print(f"  - [{r['region']}] {r['index']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
