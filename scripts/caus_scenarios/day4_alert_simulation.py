"""Day 4 — /alerts page reachable + dropdown surface check + /companion debug leak.

Assertions:
  - /alerts returns 200
  - No raw 5xx / forbidden words
  - /api/alerts responds 200/204 (not 5xx) when logged in
  - 2026-05-15 stronger assertion — /companion does NOT render internal
    backend trace IDs (12-16 char uppercase hex) visibly. PR #384 closed
    the original request_id leak ("919790CD3943" rendered above every
    AI bubble); this assertion guards against the regression class.
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

    # 2026-05-15 — /companion debug leak guard. The Companion chat panel
    # historically rendered the backend request_id (12-char uppercase hex)
    # above every AI bubble. PR #384 closed the original instance; this
    # check protects against regression. We only fail if hex IDs are
    # rendered as visible text — internal data-* attributes are fine.
    comp_status = _base.goto_safe(page, f"{base_url}/companion")
    comp_snap = _base.snap(page, agent_id, "day4-companion")
    if comp_status is not None and comp_status < 500 and not _base.is_beta_gate(page):
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
            comp_text = page.evaluate("document.body.innerText") or ""
        except Exception:
            comp_text = ""
        hex_leaks = _base.grep_internal_hex_id(comp_text)
        if hex_leaks:
            findings.append(_base.new_finding(
                severity="P2", category="UX", page="/companion",
                summary=(
                    f"internal trace IDs visible in chat panel: "
                    f"{hex_leaks[:3]}"
                ),
                repro=(
                    "GET /companion → scan visible text for 12-16 char "
                    "uppercase hex (request_id leak, PR #384 regression)"
                ),
                screenshot=comp_snap,
            ))

    return findings
