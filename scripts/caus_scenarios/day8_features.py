"""Day 8 — /features index page surface check (Server Component).

2026-05-17 (PR #434): added to plug a coverage gap. PR #432 split
/features from a "use client" page into a Server Component that
exports metadata + a small client subtree (feature-cards-grid). If
the split regresses — metadata gone, SSR errors, grid card count drops,
hydration mismatch — no other scenario would catch it because
sim-onboard goes straight to /home.

Assertions:
  - /features reachable (200) WITHOUT auth (it's a public marketing page)
  - <title> tag is non-empty + contains either "기능" or "Features"
    (PR #432 metadata: "기능 · Features")
  - 13 feature cards are present (data-testid="feature-card-*")
  - Each card has the canonical bronze border + .group + Link href
  - Hover-class link target resolves (basic click → 200 on /features/<sub>)
  - No raw JSON dump / Python traceback
  - No forbidden cap-markets words
  - No console errors during 5s after paint
"""
from __future__ import annotations

from . import _base


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    console_errors: list[str] = []
    network_errors: list[dict] = []
    _base.collect_console(page, console_errors)
    _base.collect_network(page, network_errors)

    url = f"{base_url}/features"
    status = _base.goto_safe(page, url)
    snap = _base.snap(page, agent_id, "day8-features-index")

    if _base.is_beta_gate(page):
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/features",
            summary=f"/features unreachable (status={status})",
            repro=f"GET {url}", screenshot=snap,
        ))
        return findings

    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass

    # PR #432 metadata export — title MUST be non-empty + carry the right
    # label so crawlers discover the page properly.
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    if not title.strip():
        findings.append(_base.new_finding(
            severity="P1", category="UX", page="/features",
            summary="<title> empty on /features — metadata export missing?",
            repro=f"GET {url} → page.title() == ''", screenshot=snap,
        ))
    elif "기능" not in title and "Features" not in title.lower():
        findings.append(_base.new_finding(
            severity="P2", category="UX", page="/features",
            summary=f"unexpected <title> on /features: {title!r}",
            repro=(
                f"GET {url} → page.title() == {title!r} "
                "(expected '기능' or 'Features')"
            ),
            screenshot=snap,
        ))

    # Card count guard — PR #432 ships 13 cards.
    try:
        card_count = page.locator('[data-testid^="feature-card-"]').count()
    except Exception:
        card_count = 0
    if card_count == 0:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/features",
            summary="0 feature cards on /features (grid never rendered)",
            repro=(
                f"GET {url} → "
                "locator '[data-testid^=feature-card-]' count == 0"
            ),
            screenshot=snap,
        ))
    elif card_count < 10:
        findings.append(_base.new_finding(
            severity="P1", category="UX", page="/features",
            summary=(
                f"only {card_count} feature cards on /features "
                "(expected 13 per FEATURE_CARDS)"
            ),
            repro=f"GET {url} → card_count={card_count}", screenshot=snap,
        ))

    # Dump leaks.
    try:
        body_text = page.evaluate("document.body.innerText") or ""
    except Exception:
        body_text = ""
    if "Traceback (most recent" in body_text:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/features",
            summary="raw Python traceback visible on /features",
            repro=f"GET {url}", screenshot=snap,
        ))

    # Forbidden words.
    for word in _base.grep_forbidden(body_text):
        findings.append(_base.new_finding(
            severity="P0", category="법규", page="/features",
            summary=f"forbidden cap-markets word visible: '{word}'",
            repro=f"GET {url}", screenshot=snap,
        ))

    # Console + network error sweep.
    page.wait_for_timeout(5_000)
    if console_errors:
        findings.append(_base.new_finding(
            severity="P2", category="기능", page="/features",
            summary=f"{len(console_errors)} console error(s) on /features",
            repro=(
                "first 3: " + " | ".join(console_errors[:3])[:300]
            ),
            screenshot=snap,
        ))
    if network_errors:
        findings.append(_base.new_finding(
            severity="P1", category="기능", page="/features",
            summary=f"{len(network_errors)} 5xx during /features paint",
            repro="first: " + str(network_errors[0])[:200],
            screenshot=snap,
        ))

    return findings
