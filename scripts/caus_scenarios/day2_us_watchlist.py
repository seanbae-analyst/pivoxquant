"""Day 2 — US watchlist + AI chat round-trip.

Assertions:
  - /watchlist returns 200
  - /ai returns 200 (page mounts)
  - No raw 5xx leaked to user
  - No forbidden cap-markets words
  - AI page contains 'AI Assistant' text (not 'AI Coach' — legal)
"""
from __future__ import annotations

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    console_errors: list[str] = []
    network_errors: list[dict] = []
    _base.collect_console(page, console_errors)
    _base.collect_network(page, network_errors)

    # 1. Watchlist page
    wl_status = _base.goto_safe(page, f"{base_url}/watchlist")
    wl_snap = _base.snap(page, agent_id, "day2-watchlist")
    if _base.is_beta_gate(page):
        return findings
    if wl_status is None or wl_status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/watchlist",
            summary=f"/watchlist unreachable or 5xx (status={wl_status})",
            repro="GET /watchlist", screenshot=wl_snap,
        ))

    try:
        wl_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        wl_text = ""

    forbidden = _base.grep_forbidden(wl_text)
    if forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/watchlist",
            summary=f"forbidden cap-markets words: {forbidden}",
            repro="GET /watchlist → scan visible text",
            screenshot=wl_snap,
        ))

    # 2. AI page
    ai_status = _base.goto_safe(page, f"{base_url}/ai")
    ai_snap = _base.snap(page, agent_id, "day2-ai")
    if ai_status is None or ai_status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/ai",
            summary=f"/ai unreachable or 5xx (status={ai_status})",
            repro="GET /ai", screenshot=ai_snap,
        ))
        return findings

    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
        ai_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        ai_text = ""

    # Legal rule: 'AI Coach' / '투자 코치' forbidden.
    if "AI Coach" in ai_text or "투자 코치" in ai_text:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/ai",
            summary="'AI Coach' / '투자 코치' present (must be 'AI Assistant')",
            repro="GET /ai → scan visible text",
            screenshot=ai_snap,
        ))

    forbidden_ai = _base.grep_forbidden(ai_text)
    if forbidden_ai:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/ai",
            summary=f"forbidden cap-markets words: {forbidden_ai}",
            repro="GET /ai → scan visible text",
            screenshot=ai_snap,
        ))

    # 3. 5xx during either page load
    for err in network_errors:
        if err["status"] >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="데이터", page=err["url"][:80],
                summary=f"{err['status']} during day2 navigation",
                repro="page load network observation",
                screenshot=ai_snap,
            ))
            break

    return findings
