#!/usr/bin/env python3
"""
PivoxQuant — Continuous Autonomous User Simulation (CAUS) daily sweep launcher.

Triggered by Claude Code scheduled-tasks (Max plan, $0 incremental cost).
Runs at 03:00 KST every day (18:00 UTC).

Architecture (per docs/specs/continuous-user-sim-spec.md):
  1. Select Day-N scenario from 7-day rotation (Mon=Day 0 가입 ... Sun=Day 6 결제)
  2. Pick a simulated user (cookies/session persisted at
     ~/.pivoxquant-sim/sessions/sim{N}.json — option B, Gmail alias)
  3. Spawn user-tester agent via Claude Code CLI with that user's scenario prompt
  4. Collect findings, post to Slack #pivoxquant-alerts via webhook
  5. P0 issues → also create draft PR via self-healing agent (Phase 2)

This script is a launcher only — the actual browser automation runs inside
user-tester agent (Claude in Chrome MCP).

Phase 1 MVP scope:
  - Daily report stub at docs/qa/auto-sim-reports/YYYY-MM-DD.md
  - Slack notify (or stub print if SLACK_WEBHOOK_URL unset)
  - Graceful no-op when session file missing (CEO D+0 onboarding required)

Phase 2 (placeholder):
  - Actual user-tester agent invocation via Claude Code CLI
  - Sentry breadcrumb tagging
  - Self-healing draft PR for P0

Cost: $0. Zero non-stdlib dependencies (urllib only).
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# --- Constants ---------------------------------------------------------------

REPO_ROOT = Path("/Users/seanbae/Desktop/취준/stockpilot")
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

# Day-N scenarios (Mon=0 ... Sun=6). Mirrors spec §5.
DAY_SCENARIOS: list[str] = [
    "Day 0 가입: OAuth 가입 → 온보딩 20문항 → 투자자 유형",
    "Day 1: KR 종목 검색 (삼성전자, 카카오) → 시그널 → 알림 toggle",
    "Day 2: 미국 종목 (AAPL, NVDA) → 워치리스트 → AI 챗 1턴",
    "Day 3: portfolio 입력 → 리스크 페이지 → 시뮬레이터",
    "Day 4: price alert 시뮬 → push notification 검증",
    "Day 5: brag card / weekly memo / earnings prebrief → /reports 열기",
    "Day 6: 결제 페이지 → Stripe test mode → 구독 시뮬 (sk_test_* 강제)",
]

# Slack severity icons (no emoji in code/docs per Iron Rule — but Slack accepts shortcodes).
SEVERITY_ICONS: dict[str, str] = {
    "info": ":mag:",
    "warn": ":warning:",
    "p0": ":rotating_light:",
}


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
        urllib.request.urlopen(req, timeout=10).read()
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
        with urllib.request.urlopen(req, timeout=15) as resp:
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
    # Persist enough state for the user-tester agent (Phase 2) to replay the
    # cookie. We intentionally store the Set-Cookie header verbatim — the
    # browser-automation layer parses it. NEVER log the secret.
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


# --- Report stub ------------------------------------------------------------


def write_daily_report_stub(
    today: datetime.date, user_id: str, scenario: str
) -> Path:
    """Write a placeholder daily report; user-tester agent (Phase 2) will append findings."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{today.isoformat()}.md"

    started_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    )
    body = (
        f"# CAUS — {today.isoformat()}\n\n"
        f"- user: `{user_id}` (Gmail alias: `seanbae1521+{user_id}@gmail.com`)\n"
        f"- scenario: {scenario}\n"
        f"- started: {started_iso}\n"
        f"- launcher: `scripts/caus_daily_sweep.py` (Phase 1 MVP)\n\n"
        f"## Findings\n\n_pending — see Slack thread_\n\n"
        f"## Evidence paths\n\n"
        f"- screenshots: `artifacts/caus/{today.isoformat()}/{user_id}/*.png` (Phase 2)\n"
        f"- console: appended by user-tester agent (Phase 2)\n"
        f"- network 4xx/5xx: appended by user-tester agent (Phase 2)\n"
    )
    log_path.write_text(body, encoding="utf-8")
    return log_path


# --- Main -------------------------------------------------------------------


def main() -> int:
    today = datetime.date.today()
    day_idx = today.weekday()  # 0=Mon..6=Sun
    scenario = DAY_SCENARIOS[day_idx]
    user_id = pick_user_id(today)

    log_path = write_daily_report_stub(today, user_id, scenario)
    print(f"[caus] report stub: {log_path}")

    slack_notify(
        f"daily sweep started · {user_id} · day-{day_idx} · {scenario}",
        "info",
    )

    # Sim-onboard bypass — if SIM_ONBOARD_SECRET is set we can mint a session
    # autonomously via the /api/auth/sim-onboard HMAC ticket endpoint, with no
    # operator-side OAuth onboarding. Falls back to the legacy session-file
    # gate when the secret is unset (D+0 manual flow).
    sess = session_file_for(user_id)
    if SIM_ONBOARD_SECRET:
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
            return 0
    elif not sess.exists():
        slack_notify(
            (
                f"user `{user_id}` session missing at `{sess}`. "
                f"One-time OAuth onboarding required: login as "
                f"`seanbae1521+{user_id}@gmail.com` and save cookies "
                f"(see spec §8.B + scripts/README.md), OR set "
                f"SIM_ONBOARD_SECRET for autonomous HMAC ticket login."
            ),
            "warn",
        )
        return 0

    # Phase 2 placeholder — actual user-tester agent invocation goes here.
    # Intentionally NOT calling subprocess for `claude` CLI in Phase 1 to keep
    # this script side-effect-free and easy to dry-run on the CEO's laptop.
    slack_notify(
        (
            f"day-{day_idx} scenario logged for `{user_id}`. "
            f"user-tester agent invocation deferred to Phase 2."
        ),
        "info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
