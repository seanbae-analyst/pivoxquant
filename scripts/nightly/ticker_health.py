#!/usr/bin/env python3
"""
Nightly ticker health scan — probe /api/realtime/price/{ticker} for 50 symbols.

Behavior:
- Requires DEV_LOGIN_SECRET env var to authenticate via /api/auth/dev-login.
  If DEV_LOGIN_SECRET is unset → falls back to UNAUTHENTICATED mode.
  In unauth mode, a 401 response is EXPECTED (auth gate intact) and NOT an issue;
  a 200/other is flagged (auth bypass regression).

- For each ticker: 200ms pacing between requests to protect prod.
- Writes newline-delimited JSON results to RESULTS_PATH.

Issue rules (authenticated mode):
  - HTTP != 200 (except the transient 5xx that recovers after 1 retry) → ISSUE
  - price missing / null / <= 0 → ISSUE
  - response body not JSON → ISSUE

Issue rules (unauthenticated mode):
  - HTTP != 401 → ISSUE (auth gate regression)

Exit code: always 0 (workflow aggregates via JSON artifact, not exit status).
"""
from __future__ import annotations

import json
import os
import sys
import time
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
    _SSL_CTX = None  # use default system trust store

BASE_URL = os.environ.get(
    "BASE_URL",
    "https://RAILWAY_BACKEND_HOST.up.railway.app",
).rstrip("/")
RESULTS_PATH = Path(os.environ.get("RESULTS_PATH", "nightly_artifacts/ticker_health.jsonl"))
SLEEP_BETWEEN = float(os.environ.get("SLEEP_BETWEEN_S", "0.2"))  # 200ms
TIMEOUT_S = float(os.environ.get("HTTP_TIMEOUT_S", "15"))

US_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "JPM", "UBER", "COIN",
    "PLTR", "RBLX", "HOOD", "SHOP", "SNOW",
    "CRWD", "NET", "DDOG", "SPY", "QQQ",
    "IWM", "VTI", "ARKK", "BRK.B", "BRK-B",
]
KR_TICKERS = [
    "005930", "000660", "373220", "207940", "005380",
    "035720", "035420", "068270", "005490", "006400",
    "000270", "051910", "028260", "017670", "105560",
    "055550", "086790", "012330", "012450", "011200",
    "066570", "034020", "247540", "018260", "000810",
]


def _request(
    method: str,
    url: str,
    *,
    body: Optional[bytes] = None,
    headers: Optional[dict] = None,
    cookie_jar: Optional[list[str]] = None,
) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, data=body, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if cookie_jar:
        req.add_header("Cookie", "; ".join(cookie_jar))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_SSL_CTX) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", dict(e.headers or {})
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e).encode(), {}


def _login_dev() -> Optional[list[str]]:
    """Return a Set-Cookie list usable in subsequent requests, or None."""
    secret = os.environ.get("DEV_LOGIN_SECRET")
    if not secret:
        return None
    body = json.dumps({"secret": secret}).encode()
    status, payload, hdrs = _request(
        "POST",
        f"{BASE_URL}/api/auth/dev-login",
        body=body,
        headers={"Content-Type": "application/json"},
    )
    if status != 200:
        print(
            f"[ticker_health] dev-login failed: HTTP {status} — "
            f"{payload[:200]!r} (running in UNAUTH mode)",
            file=sys.stderr,
        )
        return None
    # Parse Set-Cookie. urllib flattens multi-header into one, so we split defensively.
    raw = hdrs.get("Set-Cookie") or hdrs.get("set-cookie") or ""
    if not raw:
        print("[ticker_health] dev-login 200 but no Set-Cookie — UNAUTH mode", file=sys.stderr)
        return None
    # Each cookie looks like "name=value; Path=/; ..." — keep only "name=value".
    cookies = []
    # urllib joins multiple Set-Cookie with ", " which collides with "expires=, ";
    # be conservative and split on ", name=" pattern by scanning cookie starts.
    # Easier: try both single and multi paths.
    for chunk in raw.split(","):
        head = chunk.split(";", 1)[0].strip()
        if "=" in head and not head.lower().startswith(("expires", "path", "domain", "max-age", "samesite", "secure", "httponly")):
            cookies.append(head)
    if not cookies:
        cookies = [raw.split(";", 1)[0].strip()]
    return cookies


def probe_ticker(ticker: str, cookies: Optional[list[str]]) -> dict[str, Any]:
    url = f"{BASE_URL}/api/realtime/price/{ticker}"
    status, body, _ = _request("GET", url, cookie_jar=cookies)
    entry: dict[str, Any] = {
        "ticker": ticker,
        "url": url,
        "status": status,
        "body_preview": body[:400].decode("utf-8", errors="replace"),
        "issue": False,
        "reason": "",
        "price": None,
    }

    # Try to parse body as JSON
    parsed: Any = None
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        parsed = None

    if cookies is None:
        # Unauth mode: 401 is expected, anything else is a regression
        if status == 401:
            entry["reason"] = "auth-gate-ok (unauth mode)"
        else:
            entry["issue"] = True
            entry["reason"] = f"unauth probe expected 401, got {status}"
        return entry

    # Authenticated mode
    if status != 200:
        entry["issue"] = True
        entry["reason"] = f"HTTP {status} (expected 200)"
        return entry
    if not isinstance(parsed, dict):
        entry["issue"] = True
        entry["reason"] = "response body not a JSON object"
        return entry
    price = parsed.get("price")
    if price is None:
        # Some shapes nest under "data" or "quote"
        for key in ("data", "quote", "payload"):
            inner = parsed.get(key)
            if isinstance(inner, dict) and "price" in inner:
                price = inner["price"]
                break
    try:
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_f = None
    entry["price"] = price_f
    if price_f is None:
        entry["issue"] = True
        entry["reason"] = f"price field missing/null — body: {entry['body_preview']}"
    elif price_f <= 0:
        entry["issue"] = True
        entry["reason"] = f"price<=0 (got {price_f})"
    else:
        entry["reason"] = "ok"
    return entry


def main() -> int:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cookies = _login_dev()
    mode = "AUTH" if cookies else "UNAUTH"
    print(f"[ticker_health] mode={mode} base={BASE_URL} tickers={len(US_TICKERS)+len(KR_TICKERS)}")

    issues: list[dict] = []
    all_results: list[dict] = []

    for tkr in US_TICKERS + KR_TICKERS:
        entry = probe_ticker(tkr, cookies)
        entry["mode"] = mode
        all_results.append(entry)
        if entry["issue"]:
            issues.append(entry)
        time.sleep(SLEEP_BETWEEN)

    with RESULTS_PATH.open("w") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[ticker_health] scanned={len(all_results)} issues={len(issues)} mode={mode}")
    if issues:
        print("[ticker_health] issue samples (first 5):")
        for r in issues[:5]:
            print(f"  - {r['ticker']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
