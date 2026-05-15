"""Day 3 — Portfolio entry (read-only) + Risk page 7-Layer surface check.

Assertions:
  - /portfolio reachable (200) — historically 404 (CEO bug #1)
  - /portfolio renders non-zero money — 2026-05-15 stronger assertion. The
    bug-hunter sweep caught every Holdings row rendering as ₩0/$0/0.00%
    for every user (camelCase / snake_case adapter mismatch). The
    previous CAUS-day3 scenario only checked HTTP 200 + 7-Layer keyword
    presence and reported "0 findings clean" against the broken page.
    Now we count rendered money strings and fire P0 when EVERY money
    string on the page is literal zero (find_pervasive_zero_money in
    _base.py).
  - /risk reachable (200) and not blank
  - At least one of the 7-Layer keywords visible on /risk
  - No raw 5xx / forbidden words / 'AI Coach'
"""
from __future__ import annotations

from . import _base

RISK_LAYER_KEYWORDS: tuple[str, ...] = (
    "VaR", "Correlation", "VIX", "Tail", "Daily", "Sector", "Cash",
    "리스크", "Risk", "7-Layer", "7층", "방어",
)


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    network_errors: list[dict] = []
    _base.collect_network(page, network_errors)

    # 1. Portfolio
    pf_status = _base.goto_safe(page, f"{base_url}/portfolio")
    pf_snap = _base.snap(page, agent_id, "day3-portfolio")
    if _base.is_beta_gate(page):
        return findings
    if pf_status == 404:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/portfolio",
            summary="/portfolio 404 — page missing (CEO bug #1)",
            repro="GET /portfolio", screenshot=pf_snap,
        ))
    elif pf_status is None or pf_status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/portfolio",
            summary=f"/portfolio unreachable or 5xx (status={pf_status})",
            repro="GET /portfolio", screenshot=pf_snap,
        ))
    else:
        # 2026-05-15 stronger assertion — pervasive-zero money detection.
        # Wait for client-side hydration so SWR-driven money cells settle.
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        try:
            pf_text = page.evaluate("document.body.innerText") or ""
        except Exception:
            pf_text = ""
        total_money, zero_money = _base.find_pervasive_zero_money(pf_text)
        if total_money >= 2 and zero_money == total_money:
            findings.append(_base.new_finding(
                severity="P0", category="데이터", page="/portfolio",
                summary=(
                    f"all rendered money is zero ({zero_money}/{total_money}) "
                    "— Holdings table likely rendering ₩0/$0 for every row "
                    "(see PR #383 / #388 / #389 camelCase fix pattern)"
                ),
                repro="GET /portfolio → count fmtMoney outputs in DOM text",
                screenshot=pf_snap,
            ))
        # Naked ticker check — same memory rule as /signals day1.
        naked = _base.grep_naked_kr_ticker(pf_text)
        if naked:
            findings.append(_base.new_finding(
                severity="P1", category="UX", page="/portfolio",
                summary=f"naked KR tickers without Korean name nearby: {naked[:5]}",
                repro="GET /portfolio → scan visible text",
                screenshot=pf_snap,
            ))

    # 2. Risk page
    risk_status = _base.goto_safe(page, f"{base_url}/risk")
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    risk_snap = _base.snap(page, agent_id, "day3-risk")

    if risk_status is None or risk_status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/risk",
            summary=f"/risk unreachable or 5xx (status={risk_status})",
            repro="GET /risk", screenshot=risk_snap,
        ))
        return findings

    try:
        risk_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        risk_text = ""

    # 7-Layer surface check.
    matched = [k for k in RISK_LAYER_KEYWORDS if k in risk_text]
    if len(matched) == 0:
        findings.append(_base.new_finding(
            severity="P1", category="기능", page="/risk",
            summary="/risk shows no 7-Layer keywords (page blank?)",
            repro=f"GET /risk → text length {len(risk_text)} chars",
            screenshot=risk_snap,
        ))

    forbidden = _base.grep_forbidden(risk_text)
    if forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/risk",
            summary=f"forbidden cap-markets words: {forbidden}",
            repro="GET /risk → scan visible text",
            screenshot=risk_snap,
        ))

    for err in network_errors:
        if err["status"] >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="데이터", page=err["url"][:80],
                summary=f"{err['status']} during day3 navigation",
                repro="page load network observation",
                screenshot=risk_snap,
            ))
            break

    return findings
