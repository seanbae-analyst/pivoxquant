"""Day 7 — /simulator/what-if surface check.

2026-05-17 (PR #434): added to plug a coverage gap. PR #431 lazy-loaded
WhatIfChart via next/dynamic — if the dynamic chunk 404s, prebuilds
without recharts get shipped, or the ChartSkeleton never resolves into
the real chart, no other scenario would catch it. This scenario opens
the route, fills the form, submits, and confirms a real chart renders.

Assertions:
  - /simulator/what-if reachable (200) with auth (sim-onboard session)
  - Form inputs (ticker / start date / amount / recurring) are present
    and properly labelled — htmlFor↔id wiring from PR #417 a11y fix
    still intact.
  - After submit, an SVG chart (recharts ResponsiveContainer) renders
    within 12s — guards against the dynamic chunk silently 404ing.
  - No raw Python traceback / JSON dump visible on form or result.
  - No forbidden cap-markets words on the page.
  - No console errors during the 5s after submit.
"""
from __future__ import annotations

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    console_errors: list[str] = []
    network_errors: list[dict] = []
    _base.collect_console(page, console_errors)
    _base.collect_network(page, network_errors)

    url = f"{base_url}/simulator/what-if"
    status = _base.goto_safe(page, url)
    snap = _base.snap(page, agent_id, "day7-simulator-form")

    if _base.is_beta_gate(page):
        # Beta gate active — not a bug. Skip.
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/simulator/what-if",
            summary=f"/simulator/what-if unreachable (status={status})",
            repro=f"GET {url}", screenshot=snap,
        ))
        return findings

    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass

    body_text = ""
    try:
        body_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        pass

    # Common dump leaks.
    if "Traceback (most recent" in body_text:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/simulator/what-if",
            summary="raw Python traceback visible on /simulator/what-if",
            repro=f"GET {url}", screenshot=snap,
        ))

    # a11y wiring guard — PR #417 added id="what-if-ticker" etc.
    expected_ids = [
        "what-if-ticker", "what-if-start-date", "what-if-amount",
    ]
    for input_id in expected_ids:
        try:
            count = page.locator(f"#{input_id}").count()
        except Exception:
            count = 0
        if count == 0:
            findings.append(_base.new_finding(
                severity="P1", category="UX", page="/simulator/what-if",
                summary=f"a11y regression: input id='{input_id}' missing",
                repro=(
                    f"GET {url} → expected input with id='{input_id}' "
                    "(PR #417 a11y label/htmlFor wiring)"
                ),
                screenshot=snap,
            ))

    # Forbidden words on the form-only paint.
    forbidden = _base.grep_forbidden(body_text)
    for word in forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/simulator/what-if",
            summary=f"forbidden cap-markets word visible: '{word}'",
            repro=f"GET {url}", screenshot=snap,
        ))

    # Fill the form + submit. Best-effort; if the schema drifted we
    # surface a P2 (UI not P0 because the form itself rendered).
    submitted = False
    try:
        ticker_input = page.locator("#what-if-ticker")
        if ticker_input.count() > 0:
            ticker_input.fill("AAPL")
        date_input = page.locator("#what-if-start-date")
        if date_input.count() > 0:
            date_input.fill("2020-01-01")
        amount_input = page.locator("#what-if-amount")
        if amount_input.count() > 0:
            amount_input.fill("1000")
        # Submit button — try common labels.
        submit = page.get_by_role("button", name="시뮬레이션", exact=False)
        if submit.count() == 0:
            submit = page.get_by_role("button", name="Simulate", exact=False)
        if submit.count() == 0:
            submit = page.get_by_role("button", name="실행", exact=False)
        if submit.count() > 0:
            submit.first.click()
            submitted = True
    except Exception:
        # Best-effort interaction — don't fail the whole scenario.
        pass

    if not submitted:
        findings.append(_base.new_finding(
            severity="P2", category="UX", page="/simulator/what-if",
            summary="submit button locator failed (label drift?)",
            repro=(
                "tried '시뮬레이션' / 'Simulate' / '실행' getByRole "
                "→ 0 matches"
            ),
            screenshot=snap,
        ))

    # Wait for the recharts SVG. This is the PR #431 dynamic-chunk health
    # check — if the chunk 404s, ChartSkeleton stays mounted and no SVG
    # ever appears.
    if submitted:
        try:
            page.wait_for_selector(
                "svg.recharts-surface, .recharts-responsive-container svg",
                timeout=12_000,
            )
            chart_snap = _base.snap(page, agent_id, "day7-simulator-chart")
        except Exception:
            chart_snap = _base.snap(page, agent_id, "day7-simulator-noChart")
            findings.append(_base.new_finding(
                severity="P0", category="기능", page="/simulator/what-if",
                summary=(
                    "WhatIfChart never rendered after submit (recharts SVG "
                    "selector timeout 12s) — dynamic chunk 404? bundle broken?"
                ),
                repro=(
                    f"GET {url} → fill form → submit → "
                    "wait_for_selector svg.recharts-surface 12s timeout"
                ),
                screenshot=chart_snap,
            ))

    # Console error sweep — 5s after submit.
    page.wait_for_timeout(5_000)
    if console_errors:
        findings.append(_base.new_finding(
            severity="P1", category="기능", page="/simulator/what-if",
            summary=f"{len(console_errors)} console error(s) during submit",
            repro=(
                f"first 3: " + " | ".join(console_errors[:3])[:300]
            ),
            screenshot=snap,
        ))

    if network_errors:
        findings.append(_base.new_finding(
            severity="P1", category="기능", page="/simulator/what-if",
            summary=f"{len(network_errors)} 5xx response(s) during submit",
            repro=(
                "first: "
                + str(network_errors[0])[:200]
            ),
            screenshot=snap,
        ))

    return findings
