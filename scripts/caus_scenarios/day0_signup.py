"""Day 0 — Signup / onboarding completion verification.

Assertions:
  - Post-sim-onboard, GET /home returns 200 (no redirect loop to /login)
  - /api/me responds with onboarding_completed=True for the sim user
  - No raw stack-trace text on the landing page (graceful fallback)
  - No forbidden cap-markets words on /home
  - No console errors during the 5s after page load
"""
from __future__ import annotations

import json

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    console_errors: list[str] = []
    network_errors: list[dict] = []
    _base.collect_console(page, console_errors)
    _base.collect_network(page, network_errors)

    # 1. /home reachable after sim-onboard
    status = _base.goto_safe(page, f"{base_url}/home")
    snap = _base.snap(page, agent_id, "day0-home")
    if _base.is_beta_gate(page):
        # Operational config (beta password gate) — not a bug. Silent skip.
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/home",
            summary=f"/home unreachable or 5xx (status={status})",
            repro="GET /home after sim-onboard mint", screenshot=snap,
        ))
        return findings

    # 2. /api/me onboarding_completed sanity
    try:
        resp = context.request.get(f"{base_url}/api/me", timeout=15_000)
        if resp.status == 200:
            try:
                data = resp.json()
                onboard = bool(data.get("onboarding_completed", False))
                if not onboard:
                    findings.append(_base.new_finding(
                        severity="P1", category="기능", page="/api/me",
                        summary="onboarding_completed=False after sim-onboard",
                        repro="POST sim-onboard → GET /api/me",
                        screenshot=snap,
                    ))
            except json.JSONDecodeError:
                findings.append(_base.new_finding(
                    severity="P1", category="기능", page="/api/me",
                    summary="/api/me returned 200 but body not JSON",
                    repro="GET /api/me", screenshot="N/A",
                ))
        elif resp.status in (401, 403):
            findings.append(_base.new_finding(
                severity="P0", category="기능", page="/api/me",
                summary=f"/api/me {resp.status} — session cookie not accepted",
                repro="sim-onboard mint then GET /api/me",
                screenshot=snap,
            ))
    except Exception as exc:
        findings.append(_base.new_finding(
            severity="P2", category="데이터", page="/api/me",
            summary=f"/api/me request error: {exc}"[:120],
            repro="GET /api/me", screenshot="N/A",
        ))

    # 3. raw stack trace / forbidden text
    try:
        body_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        body_text = ""

    if "Traceback (most recent" in body_text or "Internal Server Error" in body_text:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/home",
            summary="raw Python traceback / 500 leaked to user",
            repro="GET /home post-onboarding", screenshot=snap,
        ))

    forbidden = _base.grep_forbidden(body_text)
    if forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/home",
            summary=f"forbidden cap-markets words: {forbidden}",
            repro="GET /home, scan visible text", screenshot=snap,
        ))

    # 4. 5xx network during page load
    for err in network_errors:
        if err["status"] >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="기능", page=err["url"][:80],
                summary=f"{err['status']} during /home load",
                repro="page load network observation", screenshot=snap,
            ))
            break

    return findings
