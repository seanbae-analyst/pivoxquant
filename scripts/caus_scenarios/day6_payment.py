"""Day 6 — /pricing page + Stripe checkout entry (READ-ONLY).

Hard rule: NEVER complete a real payment. We only verify:
  - /pricing reachable (200)
  - 3 tiers visible (Free / Pro / Premium) or pricing labels present
  - DisclaimerBanner present (legal requirement)
  - No forbidden cap-markets words
  - Clicking the Pro 'Subscribe' button DOES NOT navigate to a production
    Stripe live URL (only sk_test_*  / test.stripe.com is acceptable);
    if it does, P0 (financial blast radius).
  - We do NOT click checkout in this scenario — we only verify the button
    href / data attributes look test-mode safe.
"""
from __future__ import annotations

import re

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    network_errors: list[dict] = []
    _base.collect_network(page, network_errors)

    status = _base.goto_safe(page, f"{base_url}/pricing")
    snap = _base.snap(page, agent_id, "day6-pricing")

    if _base.is_beta_gate(page):
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/pricing",
            summary=f"/pricing unreachable or 5xx (status={status})",
            repro="GET /pricing", screenshot=snap,
        ))
        return findings

    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
        body_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        body_text = ""

    # Three tiers should be referenced.
    tiers_found = [t for t in ("Free", "Pro", "Premium") if t in body_text]
    if len(tiers_found) < 2:
        findings.append(_base.new_finding(
            severity="P1", category="결제", page="/pricing",
            summary=f"only {len(tiers_found)} tier names visible: {tiers_found}",
            repro="GET /pricing → grep tier names",
            screenshot=snap,
        ))

    # DisclaimerBanner — legal requirement on analysis surfaces.
    has_disclaimer = (
        "면책" in body_text
        or "Disclaimer" in body_text
        or "투자에 대한 책임" in body_text
        or "참고용" in body_text
    )
    if not has_disclaimer:
        findings.append(_base.new_finding(
            severity="P1", category="법규", page="/pricing",
            summary="DisclaimerBanner missing on /pricing",
            repro="GET /pricing → no '면책' / 'Disclaimer' / '참고용' text",
            screenshot=snap,
        ))

    forbidden = _base.grep_forbidden(body_text)
    if forbidden:
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/pricing",
            summary=f"forbidden cap-markets words: {forbidden}",
            repro="GET /pricing → scan visible text",
            screenshot=snap,
        ))

    # Scan all anchor / button hrefs for live Stripe URLs.
    try:
        hrefs = page.evaluate(
            "Array.from(document.querySelectorAll('a, button')).map(el => "
            "({tag: el.tagName, href: el.getAttribute('href') || '', "
            "data: el.getAttribute('data-checkout-url') || ''}))"
        ) or []
    except Exception:
        hrefs = []

    for entry in hrefs:
        candidate = (entry.get("href") or "") + " " + (entry.get("data") or "")
        if "checkout.stripe.com" in candidate and "test" not in candidate.lower():
            findings.append(_base.new_finding(
                severity="P0", category="결제", page="/pricing",
                summary="LIVE Stripe checkout URL found (test mode required pre-launch)",
                repro=f"element {entry.get('tag')} href/data: {candidate[:120]}",
                screenshot=snap,
            ))
            break

    for err in network_errors:
        if err["status"] >= 500:
            findings.append(_base.new_finding(
                severity="P0", category="데이터", page=err["url"][:80],
                summary=f"{err['status']} during /pricing load",
                repro="page load network observation",
                screenshot=snap,
            ))
            break

    return findings
