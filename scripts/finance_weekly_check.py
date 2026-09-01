#!/usr/bin/env python3
"""
PivoxQuant — Weekly finance health check (crontab, 매주 일요일 09:00 KST).

Triggered by macOS crontab. Zero incremental cost:
  - No Anthropic API calls (does not invoke `claude` CLI)
  - No external paid APIs
  - Reads finance_budget.md mtime + parses next-payment date
  - Optionally posts to Slack webhook (env var SLACK_WEBHOOK_URL) — free tier

Outputs:
  - stdout (captured in /tmp/finance-weekly.log)
  - Slack message if SLACK_WEBHOOK_URL is set
  - Non-zero exit code if stale > 21 days (so cron mail / monitoring catches it)

Idempotent. Safe to run multiple times per day.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# Mirror of scripts/legal_monitor/monitor.py::_build_ssl_context (PR #370);
# the same fix originated in the CAUS sweep (PR #362, retired 2026-09-01).
# The launchd / cron daemon
# does not source the user shell environment, so the default urllib SSL
# trust store may resolve before certifi is loaded — Slack webhook posts
# silently fail with SSL: CERTIFICATE_VERIFY_FAILED on some macOS
# configurations. Pin the context to certifi when available, system
# default otherwise. (HANDOVER v42 final flagged this as the next-wave
# wire — closed here.)
def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_SSL_CONTEXT: ssl.SSLContext = _build_ssl_context()

# ---------------------------------------------------------------------------
# Configuration (paths are absolute — script is invoked from cron, no cwd assumed)
# ---------------------------------------------------------------------------

BUDGET_PATH = Path(
    "/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory/finance_budget.md"
)
STALE_WARN_DAYS = 14   # yellow alert
STALE_FAIL_DAYS = 21   # red alert + non-zero exit
NEXT_PAYMENT_PATTERN = re.compile(
    r"Next review:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE
)
LAST_UPDATED_PATTERN = re.compile(
    r"^last_updated:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE | re.MULTILINE
)


def parse_budget(path: Path) -> dict:
    """Extract structured signals from the budget memory file."""
    if not path.exists():
        return {"exists": False}

    text = path.read_text(encoding="utf-8")
    last_updated_m = LAST_UPDATED_PATTERN.search(text)
    next_review_m = NEXT_PAYMENT_PATTERN.search(text)

    last_updated = (
        datetime.strptime(last_updated_m.group(1), "%Y-%m-%d").date()
        if last_updated_m
        else None
    )
    next_review = (
        datetime.strptime(next_review_m.group(1), "%Y-%m-%d").date()
        if next_review_m
        else None
    )

    return {
        "exists": True,
        "last_updated": last_updated,
        "next_review": next_review,
        "size_bytes": path.stat().st_size,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime).date(),
    }


def post_slack(text: str) -> bool:
    """POST to Slack webhook if SLACK_WEBHOOK_URL is set. Free tier, no cost."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return False
    try:
        req = urllib.request.Request(
            webhook,
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[finance-weekly] slack post failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    today = date.today()
    print(f"[finance-weekly] run @ {datetime.now().isoformat(timespec='seconds')}")

    info = parse_budget(BUDGET_PATH)
    if not info["exists"]:
        msg = f"[finance-weekly] CRITICAL: budget file missing at {BUDGET_PATH}"
        print(msg)
        post_slack(":rotating_light: " + msg)
        return 2

    last_updated = info["last_updated"] or info["mtime"]
    next_review = info["next_review"]

    days_since_update = (today - last_updated).days
    days_until_payment = (next_review - today).days if next_review else None

    lines = [
        f"[finance-weekly] PivoxQuant budget health — {today.isoformat()}",
        f"  budget file: {BUDGET_PATH}",
        f"  last_updated: {last_updated.isoformat()} ({days_since_update} days ago)",
    ]
    if next_review:
        lines.append(
            f"  next_review:  {next_review.isoformat()} (D-{days_until_payment})"
        )
    else:
        lines.append("  next_review:  (not parsed)")

    # Stale check
    exit_code = 0
    alert_level = "ok"
    if days_since_update >= STALE_FAIL_DAYS:
        alert_level = "red"
        exit_code = 1
        lines.append(
            f"  STATUS: 🔴 RED — budget stale > {STALE_FAIL_DAYS} days. "
            f"CEO 직접 갱신 필요."
        )
    elif days_since_update >= STALE_WARN_DAYS:
        alert_level = "yellow"
        lines.append(
            f"  STATUS: 🟡 YELLOW — budget stale > {STALE_WARN_DAYS} days."
        )
    else:
        lines.append("  STATUS: 🟢 GREEN")

    # Payment countdown
    if days_until_payment is not None:
        if days_until_payment <= 3:
            lines.append(
                f"  PAYMENT ALERT: 다음 결제 D-{days_until_payment} — "
                "카드 잔액 / 환율 확인 권고"
            )
        elif days_until_payment < 0:
            lines.append(
                f"  PAYMENT OVERDUE: next_review 가 {-days_until_payment} 일 지남. "
                "결제 발생 여부 확인 후 ledger 추가 필요."
            )

    report = "\n".join(lines)
    print(report)

    # Slack notification (only on non-green or when payment imminent)
    if alert_level != "ok" or (
        days_until_payment is not None and days_until_payment <= 3
    ):
        post_slack(report)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
