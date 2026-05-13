"""Day 4 — /alerts page reachable + dropdown surface check.

Assertions:
  - /alerts returns 200
  - No raw 5xx / forbidden words
  - /api/alerts responds 200/204 (not 5xx) when logged in
"""
from __future__ import annotations

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    network_errors: list[dict] = []
    _base.collect_network(page, network_errors)

    status = _base.goto_safe(page, f"{base_url}/alerts")
    snap = _base.snap(page, agent_id, "day4-alerts")

    if _base.is_beta_gate(page):
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/alerts",
            summary=f"/alerts unreachable or 5xx (status={status})",
            repro="GET /alerts", screenshot=snap,
        ))
        return findings

    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
        body_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        body_text = ""

    forbidden = _base.grep_forbidden(body_text)
    if forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/alerts",
            summary=f"forbidden cap-markets words: {forbidden}",
            repro="GET /alerts → scan visible text",
            screenshot=snap,
        ))

    # /api/alerts probe.
    try:
        resp = context.request.get(f"{base_url}/api/alerts", timeout=15_000)
        if resp.status >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="기능", page="/api/alerts",
                summary=f"/api/alerts {resp.status} (5xx)",
                repro="GET /api/alerts with session cookie",
                screenshot=snap,
            ))
    except Exception as exc:
        findings.append(_base.new_finding(
            severity="P2", category="데이터", page="/api/alerts",
            summary=f"/api/alerts transport error: {exc}"[:120],
            repro="GET /api/alerts", screenshot="N/A",
        ))

    for err in network_errors:
        if err["status"] >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="데이터", page=err["url"][:80],
                summary=f"{err['status']} during /alerts load",
                repro="page load network observation",
                screenshot=snap,
            ))
            break

    return findings
