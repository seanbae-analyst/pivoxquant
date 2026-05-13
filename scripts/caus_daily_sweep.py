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

import datetime
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

    # Session-file gate. Option B (Gmail alias) requires CEO to OAuth-onboard
    # each sim alias ONCE and persist cookies/session JSON. Without that file,
    # we cannot drive the browser, so degrade gracefully — never fail the cron.
    sess = session_file_for(user_id)
    if not sess.exists():
        slack_notify(
            (
                f"user `{user_id}` session missing at `{sess}`. "
                f"One-time OAuth onboarding required: login as "
                f"`seanbae1521+{user_id}@gmail.com` and save cookies "
                f"(see spec §8.B + scripts/README.md)."
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
