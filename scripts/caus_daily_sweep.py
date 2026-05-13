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

Phase 2 changes (PR — feat/caus-phase-2-user-tester-invocation-github-issue):
  - Real `claude -p ... --output-format json` subprocess invocation
  - GitHub Issue creation via `gh issue create` (Slack fallback when webhook unset)
  - Idempotent label seeding (`caus`, `severity:p0/p1/p2`)
  - Findings embedded directly in daily report
  - `--dry-run` flag prints all subprocess args without executing

Phase 3 (future):
  - Self-healing draft PR for P0
  - Sentry breadcrumb tagging
  - Cross-session learning loop

Cost: $0. stdlib + `gh` CLI + `claude` CLI (Max plan).
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
import subprocess
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

# User-tester agent invocation — Claude Code CLI (Max plan, $0).
CLAUDE_CLI_TIMEOUT_SEC = int(os.environ.get("CAUS_AGENT_TIMEOUT_SEC", "600"))
CLAUDE_CLI_BIN = os.environ.get("CAUS_CLAUDE_BIN", "claude")
GH_CLI_BIN = os.environ.get("CAUS_GH_BIN", "gh")

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

# Severity normalization map — accepts upper/lower, P0/P1/P2 or p0/p1/p2.
VALID_SEVERITIES = {"p0", "p1", "p2"}

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


# --- User-tester agent invocation (Phase 2) ---------------------------------


def _build_agent_prompt(
    cookies_path: Path, scenario: str, day_idx: int, agent_id: str
) -> str:
    """Build the prompt handed to `claude -p` via subprocess.

    Keep this self-contained — the spawned session has no memory of this
    conversation. File paths must be absolute (per CEO rule).
    """
    return f"""[CAUS Day {day_idx}] PivoxQuant 라이브 prod 시뮬 user 검증.

WD: {REPO_ROOT}
시나리오: {scenario}

세션 cookies 파일: {cookies_path}
prod URL: {PIVOXQUANT_BASE_URL}

작업:
1. Claude in Chrome MCP로 prod 브라우저 열기 ({PIVOXQUANT_BASE_URL})
2. {cookies_path} 의 set_cookie 헤더 + response_body 를 읽어
   document.cookie / Set-Cookie 로 세션 주입
3. 시나리오 따라 페이지 클릭 + 폼 입력 + 검증
4. 발견된 버그 / UX 문제 / 회귀 / 법규 위반 (BUY·SELL·추천·조언) 모두 수집
5. 최종 출력은 반드시 JSON array (top-level), 다른 설명 텍스트 금지:

   [
     {{
       "severity": "P0" | "P1" | "P2",
       "category": "기능" | "법규" | "UX" | "결제" | "성능" | "데이터",
       "page": "/path/or/url",
       "summary": "한 줄 요약",
       "repro": "재현 절차 (단계별)",
       "screenshot": "/tmp/caus-<agent_id>-step-NN.png 또는 'N/A'"
     }}
   ]

룰:
- [feedback_ticker_display] 종목명 우선 표시 검증 (005930.KS → "삼성전자")
- [feedback_no_false_reports] evidence 없으면 admit, 추측 금지
- read-only: 실제 결제 금지, 회원 탈퇴 금지 (Day 7 시나리오만 sk_test_* 모드 한정)
- BUY/SELL/HOLD/추천/조언 단어 prod UI에 등장 시 P0 (자본시장법)
- 발견 0건이면 빈 배열 [] 반환 (이 또한 정상 종료)

agent_id: {agent_id}
"""


def run_user_tester(
    cookies_path: Path,
    scenario: str,
    day_idx: int,
    agent_id: str,
    *,
    dry_run: bool = False,
) -> list[dict]:
    """Spawn user-tester agent via Claude Code CLI and parse JSON findings.

    Returns a list of finding dicts (possibly empty). Never raises — on any
    failure (timeout / non-zero exit / malformed JSON) we slack_notify and
    return []. The cron must exit 0 even when the agent crashes.

    When `dry_run=True`, prints the invocation args + truncated prompt and
    returns [] without spawning.
    """
    prompt = _build_agent_prompt(cookies_path, scenario, day_idx, agent_id)

    cmd = [
        CLAUDE_CLI_BIN,
        "-p",
        prompt,
        "--output-format",
        "json",
        # Long-running browser automation needs Bash + MCP tools. We rely on
        # the operator's existing settings.json for permissions (Max plan,
        # acceptEdits / dontAsk for Chrome MCP). If perms missing, the agent
        # will exit non-zero and we admit gracefully.
        "--permission-mode",
        "acceptEdits",
    ]

    if dry_run:
        print("[caus][dry-run] would invoke:")
        print(f"  bin     : {CLAUDE_CLI_BIN}")
        print(f"  timeout : {CLAUDE_CLI_TIMEOUT_SEC}s")
        print(f"  agent_id: {agent_id}")
        print(f"  cookies : {cookies_path}")
        print(f"  scenario: {scenario}")
        print(f"  prompt[:200]: {prompt[:200]!r}")
        return []

    # Verify CLI exists — if absent we admit instead of subprocess error.
    if shutil.which(CLAUDE_CLI_BIN) is None:
        slack_notify(
            f"`{CLAUDE_CLI_BIN}` CLI not found on PATH — user-tester skipped",
            "warn",
        )
        return []

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=CLAUDE_CLI_TIMEOUT_SEC,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        slack_notify(
            f"user-tester `{agent_id}` timed out after {CLAUDE_CLI_TIMEOUT_SEC}s",
            "warn",
        )
        return []
    except OSError as exc:
        slack_notify(f"user-tester `{agent_id}` OSError: {exc}", "warn")
        return []

    if result.returncode != 0:
        # Stderr may contain auth/permission errors — admit them.
        stderr_tail = (result.stderr or "")[-400:]
        slack_notify(
            f"user-tester `{agent_id}` exit {result.returncode}: {stderr_tail!r}",
            "warn",
        )
        return []

    findings = _parse_agent_findings(result.stdout or "", agent_id)
    # Inject agent_id into every finding for downstream GitHub Issue body.
    for f in findings:
        f.setdefault("agent_id", agent_id)
    return findings


def _parse_agent_findings(raw_stdout: str, agent_id: str) -> list[dict]:
    """Parse `claude -p --output-format json` output and extract findings.

    The CLI wraps the model's final assistant message in a JSON envelope:
      {"type": "result", "result": "<assistant text>", ...}
    The assistant text is itself the JSON array we asked for.

    Graceful: returns [] on any parse failure with a warn-level slack notify.
    """
    if not raw_stdout.strip():
        slack_notify(f"user-tester `{agent_id}` returned empty stdout", "warn")
        return []

    # Step 1: parse the CLI envelope.
    try:
        envelope = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        slack_notify(
            f"user-tester `{agent_id}` envelope not JSON: {exc}", "warn"
        )
        return []

    # Step 2: extract the assistant-text payload. Be defensive — CLI schema
    # has evolved over versions.
    payload: str | None = None
    if isinstance(envelope, dict):
        for key in ("result", "response", "text", "output"):
            v = envelope.get(key)
            if isinstance(v, str) and v.strip():
                payload = v
                break
        # Some versions: {"messages": [..., {"role": "assistant", "content": "..."}]}
        if payload is None and isinstance(envelope.get("messages"), list):
            for msg in reversed(envelope["messages"]):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content")
                    if isinstance(content, str):
                        payload = content
                        break
    elif isinstance(envelope, list):
        # CLI already returned the array directly — accept it.
        return [f for f in envelope if isinstance(f, dict)]

    if not payload:
        slack_notify(
            f"user-tester `{agent_id}` no assistant payload in envelope",
            "warn",
        )
        return []

    # Step 3: assistant text may have markdown fencing — strip ```json ... ```.
    cleaned = payload.strip()
    if cleaned.startswith("```"):
        # Drop first line (``` or ```json) and trailing ```
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        findings = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        slack_notify(
            f"user-tester `{agent_id}` payload not JSON array: {exc}", "warn"
        )
        return []

    if not isinstance(findings, list):
        slack_notify(
            f"user-tester `{agent_id}` payload not a list (got {type(findings).__name__})",
            "warn",
        )
        return []

    # Filter out non-dict entries defensively.
    return [f for f in findings if isinstance(f, dict)]


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
        f"- launcher: `scripts/caus_daily_sweep.py` (Phase 2)\n"
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
        help="Print agent invocation args + skip subprocess calls. "
             "Sim-onboard still hits prod (cheap, idempotent).",
    )
    p.add_argument(
        "--skip-onboard",
        action="store_true",
        help="Skip sim-onboard HTTP call (uses existing session file if any).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    today = datetime.date.today()
    day_idx = today.weekday()  # 0=Mon..6=Sun
    scenario = DAY_SCENARIOS[day_idx]
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

    # Phase 2 — invoke user-tester agent and parse findings.
    findings = run_user_tester(
        sess, scenario, day_idx, agent_id, dry_run=args.dry_run
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
