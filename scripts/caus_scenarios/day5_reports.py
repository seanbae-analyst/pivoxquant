"""Day 5 — /reports page surface check (brag card / weekly memo / earnings prebrief).

Assertions:
  - /reports reachable (200)
  - Page shows artifact cards OR graceful fallback text (e.g. '다시 준비')
  - No raw JSON dump / Python traceback visible
  - No forbidden cap-markets words
  - No 'AI Coach' phrasing
"""
from __future__ import annotations

import re

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    network_errors: list[dict] = []
    _base.collect_network(page, network_errors)

    status = _base.goto_safe(page, f"{base_url}/reports")
    snap = _base.snap(page, agent_id, "day5-reports")

    if _base.is_beta_gate(page):
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/reports",
            summary=f"/reports unreachable or 5xx (status={status})",
            repro="GET /reports", screenshot=snap,
        ))
        return findings

    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
        body_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        body_text = ""

    # Raw JSON / traceback leak detection — common when artifact 500s.
    if "Traceback (most recent" in body_text:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/reports",
            summary="raw Python traceback visible on /reports",
            repro="GET /reports", screenshot=snap,
        ))

    # Heuristic: body starts with '{' or '[' suggests JSON dump leak.
    stripped = body_text.strip()
    if stripped.startswith("{") and stripped.endswith("}") and len(stripped) > 50:
        findings.append(_base.new_finding(
            severity="P0", category="UX", page="/reports",
            summary="raw JSON body visible on /reports (no UI shell)",
            repro=f"first 80 chars: {stripped[:80]}",
            screenshot=snap,
        ))

    if "AI Coach" in body_text or "투자 코치" in body_text:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/reports",
            summary="'AI Coach' / '투자 코치' present",
            repro="GET /reports → scan visible text",
            screenshot=snap,
        ))

    forbidden = _base.grep_forbidden(body_text)
    if forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/reports",
            summary=f"forbidden cap-markets words: {forbidden}",
            repro="GET /reports → scan visible text",
            screenshot=snap,
        ))

    for err in network_errors:
        if err["status"] >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="데이터", page=err["url"][:80],
                summary=f"{err['status']} during /reports load",
                repro="page load network observation",
                screenshot=snap,
            ))
            break

    return findings
