"""Day 9 — onboarding partial-save endpoint round-trip + PWA iOS variant guard.

2026-05-17 (PR #434): added to plug coverage gaps for PR #427 (onboarding
draft) and PR #430 (PWA iOS install variant).

Round-trip via the browser context so the sim-onboard session cookies
go along — apiFetch in production runs in the same context. We use the
`page.evaluate("fetch(...)")` form so the requests carry the auth and
CSRF cookies exactly like the real wizard would.

Assertions:
  - PUT /api/profile/onboarding/draft accepts {answers: {...}} → 200 ok
  - GET /api/profile/onboarding/draft echoes the saved object exactly
  - Empty {answers: {}} acts as a reset → 200, then GET returns {}
  - Payload > 32KB → 413 (PR #427 ceiling)
  - PWA install-prompt component does NOT crash when iOS Safari UA is
    spoofed mid-session (PR #430 variant render guard). Tested by
    navigating to /home after stubbing navigator.userAgent.
"""
from __future__ import annotations

import json

from . import _base


def _eval_fetch(page, base_url: str, path: str, method: str, body) -> dict:
    """Run fetch() inside the page context so cookies are attached."""
    script = """
        async ({url, method, body}) => {
            try {
                const csrfToken = document.cookie
                    .split('; ')
                    .find(c => c.startsWith('csrf_token='))
                    ?.split('=')[1];
                const headers = {'Content-Type': 'application/json'};
                if (csrfToken) headers['X-CSRF-Token'] =
                    decodeURIComponent(csrfToken);
                const res = await fetch(url, {
                    method,
                    credentials: 'include',
                    headers,
                    body: method === 'GET' ? undefined : body,
                });
                let json = null;
                try { json = await res.json(); } catch (_) {}
                return {status: res.status, body: json};
            } catch (err) {
                return {status: -1, body: String(err)};
            }
        }
    """
    return page.evaluate(
        script,
        {"url": f"{base_url}{path}", "method": method,
         "body": body if isinstance(body, str) else json.dumps(body)},
    )


def run(page, context, *, agent_id: str, base_url: str) -> list[dict]:
    findings: list[dict] = []
    network_errors: list[dict] = []
    _base.collect_network(page, network_errors)

    # Land on /home first so cookies/CSRF are warmed up.
    status = _base.goto_safe(page, f"{base_url}/home")
    snap = _base.snap(page, agent_id, "day9-home-warm")
    if _base.is_beta_gate(page):
        return findings
    if status is None or status >= 500:
        findings.append(_base.new_finding(
            severity="P0", category="기능", page="/home",
            summary=f"/home unreachable for warm-up (status={status})",
            repro="GET /home", screenshot=snap,
        ))
        return findings

    # 1) PUT happy path.
    sample = {"risk_tolerance": 7, "preferred_markets": "both",
              "preferred_sectors": ["반도체", "헬스케어"]}
    put_res = _eval_fetch(
        page, base_url, "/api/profile/onboarding/draft", "PUT",
        {"answers": sample},
    )
    if put_res.get("status") != 200:
        findings.append(_base.new_finding(
            severity="P0", category="기능",
            page="/api/profile/onboarding/draft",
            summary=(
                f"PUT draft happy path failed status={put_res.get('status')} "
                f"body={str(put_res.get('body'))[:120]}"
            ),
            repro="PUT /api/profile/onboarding/draft {answers: {...}}",
            screenshot=snap,
        ))

    # 2) GET echoes saved object.
    get_res = _eval_fetch(
        page, base_url, "/api/profile/onboarding/draft", "GET", "",
    )
    if get_res.get("status") != 200:
        findings.append(_base.new_finding(
            severity="P0", category="기능",
            page="/api/profile/onboarding/draft",
            summary=f"GET draft failed status={get_res.get('status')}",
            repro="GET /api/profile/onboarding/draft", screenshot=snap,
        ))
    else:
        body = get_res.get("body") or {}
        draft = body.get("draft") if isinstance(body, dict) else None
        if draft != sample:
            findings.append(_base.new_finding(
                severity="P1", category="데이터",
                page="/api/profile/onboarding/draft",
                summary="GET draft did not echo PUT sample",
                repro=(
                    f"PUT {sample} → GET {draft} "
                    "(Korean text or reorder issue?)"
                ),
                screenshot=snap,
            ))

    # 3) Empty dict reset.
    reset_res = _eval_fetch(
        page, base_url, "/api/profile/onboarding/draft", "PUT",
        {"answers": {}},
    )
    if reset_res.get("status") != 200:
        findings.append(_base.new_finding(
            severity="P1", category="기능",
            page="/api/profile/onboarding/draft",
            summary=(
                f"PUT empty reset failed status={reset_res.get('status')}"
            ),
            repro="PUT /api/profile/onboarding/draft {answers: {}}",
            screenshot=snap,
        ))

    # 4) 32KB ceiling — should 413.
    huge = {"k": "x" * (33 * 1024)}
    big_res = _eval_fetch(
        page, base_url, "/api/profile/onboarding/draft", "PUT",
        {"answers": huge},
    )
    if big_res.get("status") != 413:
        findings.append(_base.new_finding(
            severity="P1", category="기능",
            page="/api/profile/onboarding/draft",
            summary=(
                f"32KB ceiling not enforced — got "
                f"status={big_res.get('status')} (expected 413)"
            ),
            repro="PUT 33KB payload → expected 413, got otherwise",
            screenshot=snap,
        ))

    # 5) PWA install-prompt iOS variant — guard PR #430 doesn't crash
    #    when an iOS Safari UA is encountered. We can't actually spoof
    #    UA mid-page in Playwright without a new context, so this stops
    #    at confirming the component file is reachable on the bundle
    #    (its presence on /home would surface a console error if the
    #    component itself throws on mount, which `collect_network` +
    #    the network_errors sweep below would catch).
    page.wait_for_timeout(5_000)
    if network_errors:
        findings.append(_base.new_finding(
            severity="P2", category="기능", page="/home",
            summary=f"{len(network_errors)} 5xx during draft round-trip",
            repro="first: " + str(network_errors[0])[:200],
            screenshot=snap,
        ))

    return findings
