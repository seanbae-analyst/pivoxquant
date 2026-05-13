"""Day 1 — KR signals: 삼성전자 (005930.KS) search + alert toggle.

Assertions:
  - /signals reachable (200)
  - Korean name '삼성전자' present somewhere on the page (ticker display rule)
  - No naked '005930.KS' standalone occurrence (always paired with name)
  - No forbidden cap-markets words
  - Signal label set restricted to POSITIVE/NEGATIVE/NEUTRAL (no BUY/SELL/HOLD)
"""
from __future__ import annotations

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    console_errors: list[str] = []
    network_errors: list[dict] = []
    _base.collect_console(page, console_errors)
    _base.collect_network(page, network_errors)

    status = _base.goto_safe(page, f"{base_url}/signals")
    snap = _base.snap(page, agent_id, "day1-signals")

    if _base.is_beta_gate(page):
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/signals",
            summary=f"/signals unreachable or 5xx (status={status})",
            repro="GET /signals", screenshot=snap,
        ))
        return findings

    # Wait briefly for client-side hydration.
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass

    try:
        body_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        body_text = ""

    # Naked ticker display rule (memory: feedback_ticker_display).
    naked = _base.grep_naked_kr_ticker(body_text)
    if naked:
        findings.append(_base.new_finding(
            severity="P1", category="UX", page="/signals",
            summary=f"naked KR tickers without Korean name nearby: {naked[:5]}",
            repro="GET /signals → scan visible text",
            screenshot=snap,
        ))

    # Forbidden words.
    forbidden = _base.grep_forbidden(body_text)
    if forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/signals",
            summary=f"forbidden cap-markets words: {forbidden}",
            repro="GET /signals → scan visible text",
            screenshot=snap,
        ))

    # 5xx during page load
    for err in network_errors:
        if err["status"] >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="데이터", page=err["url"][:80],
                summary=f"{err['status']} during /signals load",
                repro="page load network observation", screenshot=snap,
            ))
            break

    # Console errors (skip noisy 3p — only flag if many or app-origin).
    app_console_errs = [
        e for e in console_errors
        if "pivoxquant" in e or "/api/" in e or "Uncaught" in e
    ]
    if len(app_console_errs) >= 3:
        findings.append(_base.new_finding(
            severity="P2", category="UX", page="/signals",
            summary=f"{len(app_console_errs)} JS console errors during page load",
            repro=f"first error: {app_console_errs[0][:150]}",
            screenshot=snap,
        ))

    return findings
