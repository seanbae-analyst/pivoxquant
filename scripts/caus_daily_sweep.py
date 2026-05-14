#!/usr/bin/env python3
"""
PivoxQuant — Continuous Autonomous User Simulation (CAUS) daily sweep launcher.

Triggered by Claude Code scheduled-tasks (Max plan, $0 incremental cost).
Runs at 03:00 KST every day (18:00 UTC).

Architecture (per docs/specs/continuous-user-sim-spec.md):
  1. Select Day-N scenario from 7-day rotation (Mon=Day 0 가입 ... Sun=Day 6 결제)
  2. Pick a simulated user (Gmail alias seanbae1521+sim{N}@gmail.com)
  3. Mint a session via /api/auth/sim-onboard (HMAC ticket, SIM_ONBOARD_SECRET)
  4. Spawn user-tester agent via Claude Code CLI subprocess with cookies + scenario
  5. Parse JSON findings, create GitHub Issues (auto-labels) and Slack alerts
  6. P0 issues — TODO: spawn self-healing agent for draft PR (Phase 3)

Phase 2 changes (PR #356):
  - Real `claude -p ... --output-format json` subprocess invocation
  - GitHub Issue creation via `gh issue create` (Slack fallback when webhook unset)
  - Idempotent label seeding (`caus`, `severity:p0/p1/p2`)
  - Findings embedded directly in daily report

Phase 3 changes (this PR — feat/caus-phase-3-playwright-scenarios):
  - Replace `claude` CLI subprocess (600s timeout in child context — Claude in
    Chrome MCP unreachable from detached subprocesses) with Playwright Python
    direct browser automation. $0 incremental cost (OSS, already in
    requirements.txt; chromium browser ~120 MB local install).
  - 7 scenario modules under `scripts/caus_scenarios/` — one per Day-N rotation,
    each exposing `run(page, context, *, agent_id, base_url) -> list[dict]`.
  - `--scenario dayN` flag to run a single scenario manually for smoke testing.
  - Timeout per scenario reduced to 180s (browser nav is fast).

Phase 4 (future):
  - Self-healing draft PR for P0
  - Sentry breadcrumb tagging
  - Cross-session learning loop

Cost: $0. stdlib + `gh` CLI + Playwright (OSS).
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import hmac
import json
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# --- Constants ---------------------------------------------------------------

# 2026-05-14: REPO_ROOT was hardcoded to ~/Desktop/취준/stockpilot which broke
# after the relocation to ~/projects/pivoxquant (TCC: ~/Desktop is protected
# from launchd/cron daemons, see HANDOVER v42 final patch). Resolve from
# __file__ so the script follows the repo wherever it lives. Also push
# REPO_ROOT onto sys.path so `scripts.caus_scenarios.*` imports work when
# invoked directly by launchd/cron.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
LOG_DIR = REPO_ROOT / "docs" / "qa" / "auto-sim-reports"
SESSION_DIR = Path.home() / ".pivoxquant-sim" / "sessions"
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "") or os.environ.get(
    "SLACK_WEBHOOK_CAUS", ""
)
# Sim-onboard endpoint — autonomous sim user login (HMAC ticket + sim regex).
# See routes/sim_onboard.py for the security model.
PIVOXQUANT_BASE_URL = os.environ.get(
    "PIVOXQUANT_BASE_URL", "https://www.pivoxquant.com"
).rstrip("/")
SIM_ONBOARD_SECRET = os.environ.get("SIM_ONBOARD_SECRET", "")
SIM_ONBOARD_UA = "PivoxQuantCAUS/1.0"

# Per-scenario Playwright timeout (Phase 3). Browser nav is fast; 180s
# accommodates slow first paint on cold edge cache while staying well under
# the daily cron budget.
PLAYWRIGHT_TIMEOUT_SEC = int(os.environ.get("CAUS_SCENARIO_TIMEOUT_SEC", "180"))
GH_CLI_BIN = os.environ.get("CAUS_GH_BIN", "gh")

# Day-N scenarios (Mon=0 ... Sun=6). Mirrors spec §5.
# `module` is the importable path under `scripts.caus_scenarios`.
DAY_SCENARIOS: list[tuple[str, str]] = [
    ("day0_signup", "Day 0 가입: 온보딩 완료 + /home 진입 검증"),
    ("day1_kr_search", "Day 1: /signals KR 종목 (삼성전자) → 알림 toggle"),
    ("day2_us_watchlist", "Day 2: /watchlist AAPL → /ai 챗 검증"),
    ("day3_portfolio_risk", "Day 3: /portfolio → /risk 7-Layer 노출 검증"),
    ("day4_alert_simulation", "Day 4: /alerts dropdown + mark-all-read"),
    ("day5_reports", "Day 5: /reports brag/memo/prebrief 카드"),
    ("day6_payment", "Day 6: /pricing Stripe test-mode 진입 (실 결제 X)"),
]

# Scenario-id → module path (also accepts the short form `day2` etc.).
SCENARIO_MODULE_MAP: dict[str, int] = {
    name: idx for idx, (name, _) in enumerate(DAY_SCENARIOS)
}
SCENARIO_MODULE_MAP.update({f"day{idx}": idx for idx, _ in enumerate(DAY_SCENARIOS)})

# Severity normalization map — accepts upper/lower, P0/P1/P2 or p0/p1/p2.
VALID_SEVERITIES = {"p0", "p1", "p2"}

# Slack severity icons (no emoji in code/docs per Iron Rule — but Slack accepts shortcodes).
SEVERITY_ICONS: dict[str, str] = {
    "info": ":mag:",
    "warn": ":warning:",
    "p0": ":rotating_light:",
}


# --- SSL context (cron-compat) ----------------------------------------------
#
# macOS system Python (and any environment using LibreSSL or with a stale
# system trust store) raises `SSL: CERTIFICATE_VERIFY_FAILED` against
# pivoxquant.com when urllib uses its default context. Cron runs detached
# from the user shell so `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` env vars
# can't be relied on either.
#
# We build an explicit context off of `certifi.where()` once at import time
# and pass it to every `urlopen()` call (sim-onboard + Slack webhook).
# Falls back to the system default context when certifi is unavailable —
# the sweep still runs, just without the cron-grade trust store.


def _build_ssl_context() -> ssl.SSLContext:
    """Build an SSLContext rooted at certifi's CA bundle when possible.

    Importing certifi at module top would couple unit tests to the package,
    so we lazy-import here. ``ssl.create_default_context()`` is the safe
    fallback — it still verifies, just using the (potentially stale) system
    trust store.
    """
    try:
        import certifi  # type: ignore[import-not-found]
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_SSL_CONTEXT: ssl.SSLContext = _build_ssl_context()


# --- Slack ------------------------------------------------------------------


def slack_notify(text: str, severity: str = "info") -> None:
    """Post to Slack via webhook. severity ∈ {info, warn, p0}.

    Graceful: if SLACK_WEBHOOK env unset, prints to stdout instead.
    Never raises — Slack outage must not break the cron.
    """
    icon = SEVERITY_ICONS.get(severity, ":mag:")
    line = f"{icon} CAUS: {text}"

    if not SLACK_WEBHOOK:
        print(f"[slack-stub] {severity}: {text}")
        return

    payload = json.dumps({"text": line}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT).read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        # Print but never fail — cron must exit 0 on Slack outage.
        print(f"[slack-fail] {exc}", file=sys.stderr)


# --- User rotation ----------------------------------------------------------


def pick_user_id(today: datetime.date) -> str:
    """Rotate through sim1..sim10 by day-of-month.

    Option B (Gmail alias): user IDs map to `seanbae1521+sim{N}@gmail.com`.
    Sessions stored at ~/.pivoxquant-sim/sessions/sim{N}.json after CEO
    completes one-time OAuth onboarding.
    """
    return f"sim{(today.day % 10) + 1}"


def session_file_for(user_id: str) -> Path:
    return SESSION_DIR / f"{user_id}.json"


# --- Sim-onboard (HMAC ticket → session cookie) -----------------------------


def _build_sim_ticket(email: str, secret: str) -> str:
    """Construct the HMAC ticket consumed by /api/auth/sim-onboard.

    Mirrors the format expected by ``routes.sim_onboard._verify_ticket``::

        urlsafe_b64encode(
          f"{utc_isoformat}:{email}:{hex hmac_sha256(ts:email, secret)}"
        )
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sig = hmac.new(
        secret.encode("utf-8"),
        f"{ts}:{email}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{ts}:{email}:{sig}".encode()).decode()


def sim_onboard_login(user_id: str) -> Path | None:
    """POST to /api/auth/sim-onboard and persist the session cookie.

    Returns the path the session JSON was written to on success, or None if
    SIM_ONBOARD_SECRET is unset / the endpoint returned non-2xx. Never raises
    — the cron must exit 0 on transient failure (the Slack notify upstream
    surfaces the issue to the operator).
    """
    if not SIM_ONBOARD_SECRET:
        return None

    email = f"seanbae1521+{user_id}@gmail.com"
    ticket = _build_sim_ticket(email, SIM_ONBOARD_SECRET)
    url = f"{PIVOXQUANT_BASE_URL}/api/auth/sim-onboard"
    payload = json.dumps({"ticket": ticket, "email": email}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": SIM_ONBOARD_UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CONTEXT) as resp:
            status = resp.status
            cookie_header = resp.headers.get("Set-Cookie", "") or ""
            body_text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        slack_notify(
            f"sim-onboard HTTP {exc.code} for `{user_id}` ({exc.reason})",
            "warn",
        )
        return None
    except (urllib.error.URLError, TimeoutError) as exc:
        slack_notify(f"sim-onboard transport error for `{user_id}`: {exc}", "warn")
        return None

    if status != 200:
        slack_notify(f"sim-onboard non-200 ({status}) for `{user_id}`", "warn")
        return None

    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    sess_path = session_file_for(user_id)
    # Persist enough state for the user-tester agent to replay the cookie.
    # We intentionally store the Set-Cookie header verbatim — the browser
    # automation layer parses it. NEVER log the secret.
    sess_path.write_text(
        json.dumps({
            "user_id": user_id,
            "email": email,
            "set_cookie": cookie_header,
            "obtained_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(timespec="seconds"),
            "response_body": json.loads(body_text) if body_text else {},
        }, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(sess_path, 0o600)
    except OSError:
        pass
    return sess_path


# --- Scenario invocation (Phase 3 — Playwright Python) ----------------------


REQUIRED_FINDING_KEYS = {"severity", "category", "page", "summary"}


def _load_scenario_module(module_name: str):
    """Import scripts.caus_scenarios.<module_name>.

    Returns the module or None on failure (logs to Slack).

    When the script is executed directly (`python scripts/caus_daily_sweep.py`),
    REPO_ROOT is not on sys.path. We add it here so `scripts.*` imports resolve
    whether invoked via cron or via pytest.
    """
    import importlib

    repo_str = str(REPO_ROOT)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)

    try:
        return importlib.import_module(f"scripts.caus_scenarios.{module_name}")
    except ImportError as exc:
        slack_notify(
            f"scenario `{module_name}` import failed: {exc}", "warn"
        )
        return None


def _validate_finding(finding: dict, agent_id: str) -> dict | None:
    """Ensure finding has the required schema. Returns sanitized dict or None."""
    if not isinstance(finding, dict):
        return None
    missing = REQUIRED_FINDING_KEYS - set(finding.keys())
    if missing:
        slack_notify(
            f"scenario `{agent_id}` finding missing keys {missing}", "warn"
        )
        return None
    # Coerce all string fields to str — never let an unexpected type crash
    # the downstream GitHub Issue body.
    out = dict(finding)
    for k in ("severity", "category", "page", "summary", "repro", "screenshot"):
        if k in out:
            out[k] = str(out[k])
    out.setdefault("agent_id", agent_id)
    return out


def run_user_tester(
    cookies_path: Path,
    scenario_module_name: str,
    day_idx: int,
    agent_id: str,
    *,
    dry_run: bool = False,
) -> list[dict]:
    """Run a Playwright scenario module and return its findings.

    Replaces the Phase 2 `claude` CLI subprocess (which timed out at 600s in
    the cron child context — Claude in Chrome MCP unreachable from detached
    subprocesses).

    Returns [] on any failure (import error / playwright missing / scenario
    raises). Never re-raises — the cron must exit 0.
    """
    if dry_run:
        print("[caus][dry-run] would run Playwright scenario:")
        print(f"  module       : scripts.caus_scenarios.{scenario_module_name}")
        print(f"  timeout      : {PLAYWRIGHT_TIMEOUT_SEC}s")
        print(f"  agent_id     : {agent_id}")
        print(f"  cookies      : {cookies_path}")
        print(f"  base_url     : {PIVOXQUANT_BASE_URL}")
        return []

    # Lazy import — playwright is optional at install time for parts of the
    # codebase that only need the rest of the sweep helpers (e.g. unit tests).
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        slack_notify(
            "Playwright not installed — run `pip install playwright && "
            "python3 -m playwright install chromium`. Scenario skipped.",
            "warn",
        )
        return []

    module = _load_scenario_module(scenario_module_name)
    if module is None:
        return []

    run_fn = getattr(module, "run", None)
    if not callable(run_fn):
        slack_notify(
            f"scenario `{scenario_module_name}` has no callable run()", "warn"
        )
        return []

    # Lazy import — keep _base import on the same path as scenarios.
    from scripts.caus_scenarios import _base as scenario_base

    findings: list[dict] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36 PivoxQuantCAUS/3.0"
                    ),
                    viewport={"width": 1440, "height": 900},
                    locale="ko-KR",
                )
                # Per-scenario hard timeout cap.
                context.set_default_navigation_timeout(
                    min(30_000, PLAYWRIGHT_TIMEOUT_SEC * 1000)
                )
                context.set_default_timeout(15_000)

                scenario_base.inject_session(
                    context, cookies_path, PIVOXQUANT_BASE_URL
                )

                page = context.new_page()
                raw_findings = run_fn(
                    page,
                    context,
                    agent_id=agent_id,
                    base_url=PIVOXQUANT_BASE_URL,
                )
                if not isinstance(raw_findings, list):
                    slack_notify(
                        f"scenario `{scenario_module_name}` returned "
                        f"non-list ({type(raw_findings).__name__})",
                        "warn",
                    )
                    raw_findings = []

                for f in raw_findings:
                    validated = _validate_finding(f, agent_id)
                    if validated is not None:
                        findings.append(validated)
            finally:
                browser.close()
    except Exception as exc:
        slack_notify(
            f"Playwright scenario `{scenario_module_name}` crashed: {exc}",
            "warn",
        )
        return findings  # may still have partial findings collected pre-crash

    return findings


# --- GitHub Issue alerting (Slack fallback) ---------------------------------


CAUS_LABELS: list[tuple[str, str, str]] = [
    ("caus", "Continuous User Simulation", "8b5cf6"),
    ("severity:p0", "ship-blocker", "b91c1c"),
    ("severity:p1", "high", "ea580c"),
    ("severity:p2", "medium/low", "f59e0b"),
]


def ensure_labels(*, dry_run: bool = False) -> None:
    """Idempotent label seeding via `gh label create`. exit 1 = already exists, ignored."""
    if dry_run:
        print(f"[caus][dry-run] would seed labels: {[name for name, _, _ in CAUS_LABELS]}")
        return
    if shutil.which(GH_CLI_BIN) is None:
        # gh missing — alerts will fall back to Slack only. No noise.
        return
    for name, desc, color in CAUS_LABELS:
        try:
            subprocess.run(
                [
                    GH_CLI_BIN, "label", "create", name,
                    "--description", desc,
                    "--color", color,
                ],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            # Best-effort — never block the sweep on label seeding.
            continue


def _normalize_severity(raw: str | None) -> str:
    """Coerce 'P0' / 'p0' / 'high' / None into one of {p0, p1, p2}.

    Defaults to p2 (medium/low) for unknown values.
    """
    if not raw:
        return "p2"
    s = str(raw).strip().lower()
    if s in VALID_SEVERITIES:
        return s
    if s in ("blocker", "critical", "ship-blocker"):
        return "p0"
    if s in ("high", "major"):
        return "p1"
    return "p2"


def create_github_issue(finding: dict, today: datetime.date, *, dry_run: bool = False) -> str | None:
    """Create one GitHub Issue per finding via `gh issue create`.

    Returns the issue URL on success, or None on failure / dry-run.
    """
    severity = _normalize_severity(finding.get("severity"))
    category = str(finding.get("category", "?"))[:40]
    summary = str(finding.get("summary", "no summary"))[:70]
    title = f"[CAUS {today.isoformat()}] {category}: {summary}"

    body = (
        f"**Auto-detected by Continuous User Simulation**\n\n"
        f"- **Severity**: {finding.get('severity', severity.upper())}\n"
        f"- **Category**: {finding.get('category', 'N/A')}\n"
        f"- **Page**: {finding.get('page', 'N/A')}\n"
        f"- **Summary**: {finding.get('summary', 'N/A')}\n\n"
        f"**Repro**:\n{finding.get('repro', 'N/A')}\n\n"
        f"**Evidence**:\n"
        f"- screenshot: {finding.get('screenshot', 'N/A')}\n\n"
        f"**Source**: agent_id = `{finding.get('agent_id', 'unknown')}`\n"
        f"\n_Generated by `scripts/caus_daily_sweep.py` (Phase 2)._\n"
    )
    labels = f"caus,severity:{severity}"

    if dry_run:
        print(f"[caus][dry-run] would create issue: {title!r} (labels={labels})")
        return None

    if shutil.which(GH_CLI_BIN) is None:
        slack_notify(
            f"`{GH_CLI_BIN}` CLI missing — cannot create issue for `{title}`",
            "warn",
        )
        return None

    try:
        result = subprocess.run(
            [
                GH_CLI_BIN, "issue", "create",
                "--title", title,
                "--body", body,
                "--label", labels,
            ],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        slack_notify(f"gh issue create failed for `{title}`: {exc}", "warn")
        return None

    if result.returncode != 0:
        slack_notify(
            f"gh issue create exit {result.returncode}: {(result.stderr or '')[-200:]!r}",
            "warn",
        )
        return None

    url = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    return url or None


def alert_finding(finding: dict, today: datetime.date, *, dry_run: bool = False) -> str | None:
    """Dual alert: GitHub Issue (primary) + Slack notify (best-effort).

    GitHub Issue is the durable record; Slack is the mobile push channel.
    When SLACK_WEBHOOK is unset, slack_notify becomes a stdout stub — that's
    fine, the issue still gets created.
    """
    severity = _normalize_severity(finding.get("severity"))
    issue_url = create_github_issue(finding, today, dry_run=dry_run)

    slack_severity = "p0" if severity == "p0" else "warn"
    summary = str(finding.get("summary", "no summary"))[:80]
    suffix = f" → {issue_url}" if issue_url else ""
    slack_notify(
        f"[{severity.upper()}] {finding.get('category', '?')}: {summary}{suffix}",
        slack_severity,
    )
    return issue_url


# --- Report ------------------------------------------------------------------


def write_daily_report(
    today: datetime.date,
    user_id: str,
    scenario: str,
    findings: list[dict],
    issue_urls: list[str | None],
) -> Path:
    """Write the daily report with findings embedded (Phase 2)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{today.isoformat()}.md"

    started_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    )

    findings_md = ""
    if findings:
        for i, (f, url) in enumerate(zip(findings, issue_urls), start=1):
            sev = _normalize_severity(f.get("severity")).upper()
            findings_md += (
                f"### {i}. [{sev}] {f.get('category', '?')} · "
                f"`{f.get('page', 'N/A')}`\n\n"
                f"- summary: {f.get('summary', 'N/A')}\n"
                f"- repro: {f.get('repro', 'N/A')}\n"
                f"- screenshot: `{f.get('screenshot', 'N/A')}`\n"
                f"- issue: {url or 'N/A'}\n"
                f"- agent_id: `{f.get('agent_id', 'unknown')}`\n\n"
            )
    else:
        findings_md = "_no findings — clean run_\n\n"

    body = (
        f"# CAUS — {today.isoformat()}\n\n"
        f"- user: `{user_id}` (Gmail alias: `seanbae1521+{user_id}@gmail.com`)\n"
        f"- scenario: {scenario}\n"
        f"- started: {started_iso}\n"
        f"- launcher: `scripts/caus_daily_sweep.py` (Phase 3 — Playwright)\n"
        f"- findings: {len(findings)} ({sum(1 for f in findings if _normalize_severity(f.get('severity')) == 'p0')} P0)\n\n"
        f"## Findings\n\n{findings_md}"
    )
    log_path.write_text(body, encoding="utf-8")
    return log_path


# --- Main -------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CAUS daily sweep launcher")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print scenario invocation args + skip browser launch. "
             "Sim-onboard still hits prod (cheap, idempotent).",
    )
    p.add_argument(
        "--skip-onboard",
        action="store_true",
        help="Skip sim-onboard HTTP call (uses existing session file if any).",
    )
    p.add_argument(
        "--scenario",
        default=None,
        help=(
            "Override day-of-week rotation and run a specific scenario "
            "(e.g. `day2` or `day2_us_watchlist`). Useful for manual smoke."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    today = datetime.date.today()
    # Allow --scenario override; falls back to weekday rotation.
    if args.scenario:
        idx = SCENARIO_MODULE_MAP.get(args.scenario)
        if idx is None:
            print(
                f"[caus] unknown --scenario `{args.scenario}`. "
                f"Available: {sorted(SCENARIO_MODULE_MAP.keys())}",
                file=sys.stderr,
            )
            return 2
        day_idx = idx
    else:
        day_idx = today.weekday()  # 0=Mon..6=Sun
    scenario_module, scenario_label = DAY_SCENARIOS[day_idx]
    scenario = scenario_label  # legacy name used in report text
    user_id = pick_user_id(today)
    agent_id = f"caus-day{day_idx}-{today.isoformat()}-{user_id}"

    # Seed labels (idempotent, cheap, safe to run every cycle).
    ensure_labels(dry_run=args.dry_run)

    slack_notify(
        f"daily sweep started · {user_id} · day-{day_idx} · {scenario}"
        + (" (dry-run)" if args.dry_run else ""),
        "info",
    )

    # Sim-onboard bypass — mint a session autonomously via HMAC ticket. Falls
    # back to the legacy session-file gate when the secret is unset.
    sess = session_file_for(user_id)
    if args.skip_onboard:
        if not sess.exists():
            slack_notify(
                f"--skip-onboard requested but no session for `{user_id}` at `{sess}`",
                "warn",
            )
            return 0
    elif SIM_ONBOARD_SECRET:
        minted = sim_onboard_login(user_id)
        if minted is not None:
            slack_notify(
                f"sim-onboard ok for `{user_id}` (session minted via HMAC ticket)",
                "info",
            )
            sess = minted
        elif not sess.exists():
            slack_notify(
                f"sim-onboard failed AND no fallback session for `{user_id}`",
                "warn",
            )
            # Still write a report stub so the cron leaves a trail.
            write_daily_report(today, user_id, scenario, [], [])
            return 0
    elif not sess.exists():
        slack_notify(
            (
                f"user `{user_id}` session missing at `{sess}`. "
                f"One-time OAuth onboarding required: login as "
                f"`seanbae1521+{user_id}@gmail.com` and save cookies, "
                f"OR set SIM_ONBOARD_SECRET for autonomous HMAC login."
            ),
            "warn",
        )
        write_daily_report(today, user_id, scenario, [], [])
        return 0

    # Phase 3 — run Playwright scenario module against prod.
    findings = run_user_tester(
        sess, scenario_module, day_idx, agent_id, dry_run=args.dry_run
    )

    issue_urls: list[str | None] = []
    for finding in findings:
        url = alert_finding(finding, today, dry_run=args.dry_run)
        issue_urls.append(url)

    log_path = write_daily_report(today, user_id, scenario, findings, issue_urls)
    print(f"[caus] report: {log_path}")

    p0_count = sum(
        1 for f in findings if _normalize_severity(f.get("severity")) == "p0"
    )
    slack_notify(
        f"daily sweep done · {user_id} · day-{day_idx} · "
        f"{len(findings)} findings ({p0_count} P0)",
        "p0" if p0_count > 0 else "info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
