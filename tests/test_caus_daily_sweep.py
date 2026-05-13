"""Tests for scripts/caus_daily_sweep.py — Phase 2 user-tester + GitHub Issue.

We cover the pure-logic helpers (no subprocess, no network):
  - _normalize_severity: P0/P1/P2/aliases/None/unknown → canonical
  - _parse_agent_findings: CLI envelope shapes + markdown fencing + malformed
  - _build_agent_prompt: includes scenario, cookies path, agent_id, prod URL
  - ensure_labels(dry_run=True): no subprocess + prints expected label set
  - create_github_issue(dry_run=True): returns None + prints + correct title
  - alert_finding(dry_run=True): graceful, returns None
  - write_daily_report: findings rendered, count summary correct
  - main(--dry-run): exits 0 without spawning agent

These are intentionally fast — no Flask test app, no network, no subprocess
side-effects. Slow integration smoke (real `gh` / real `claude`) lives in
manual verification (see PR body).
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "caus_daily_sweep.py"


@pytest.fixture(scope="module")
def caus():
    """Import the script as a module (it's not a package, so spec-based load)."""
    spec = importlib.util.spec_from_file_location("caus_daily_sweep", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["caus_daily_sweep"] = mod
    spec.loader.exec_module(mod)
    return mod


# --- _normalize_severity ---------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("P0", "p0"),
        ("p0", "p0"),
        ("P1", "p1"),
        ("P2", "p2"),
        ("high", "p1"),
        ("major", "p1"),
        ("blocker", "p0"),
        ("critical", "p0"),
        ("ship-blocker", "p0"),
        (None, "p2"),
        ("", "p2"),
        ("nonsense", "p2"),
        ("  P0  ", "p0"),
    ],
)
def test_normalize_severity(caus, raw, expected):
    assert caus._normalize_severity(raw) == expected


# --- _parse_agent_findings -------------------------------------------------


def test_parse_findings_clean_envelope(caus):
    """Standard claude-cli envelope with assistant text containing JSON array."""
    payload = json.dumps([
        {"severity": "P1", "category": "UX", "page": "/home", "summary": "x", "repro": "y", "screenshot": "/tmp/a.png"},
    ])
    envelope = json.dumps({"type": "result", "result": payload})
    findings = caus._parse_agent_findings(envelope, "agent-x")
    assert len(findings) == 1
    assert findings[0]["severity"] == "P1"


def test_parse_findings_markdown_fenced(caus):
    """Some models wrap output in ```json ... ``` fences — we strip them."""
    payload = "```json\n" + json.dumps([{"severity": "P0", "summary": "boom"}]) + "\n```"
    envelope = json.dumps({"result": payload})
    findings = caus._parse_agent_findings(envelope, "agent-x")
    assert len(findings) == 1
    assert findings[0]["summary"] == "boom"


def test_parse_findings_empty_array(caus):
    """Clean sweep — agent reports no issues."""
    envelope = json.dumps({"result": "[]"})
    assert caus._parse_agent_findings(envelope, "agent-x") == []


def test_parse_findings_envelope_not_json(caus):
    """Malformed CLI stdout — graceful empty return."""
    assert caus._parse_agent_findings("not-json-at-all", "agent-x") == []


def test_parse_findings_payload_not_array(caus):
    """Agent returned an object, not a list — graceful empty."""
    envelope = json.dumps({"result": json.dumps({"severity": "P0"})})
    assert caus._parse_agent_findings(envelope, "agent-x") == []


def test_parse_findings_empty_stdout(caus):
    """Empty stdout — graceful empty."""
    assert caus._parse_agent_findings("", "agent-x") == []
    assert caus._parse_agent_findings("   ", "agent-x") == []


def test_parse_findings_top_level_array(caus):
    """If CLI somehow returned the array directly, accept it."""
    raw = json.dumps([{"severity": "P2", "summary": "z"}])
    findings = caus._parse_agent_findings(raw, "agent-x")
    assert len(findings) == 1


def test_parse_findings_messages_format(caus):
    """Alt CLI schema: {messages: [{role: assistant, content: '...'}]}."""
    payload = json.dumps([{"severity": "P1", "summary": "via-messages"}])
    envelope = json.dumps({
        "messages": [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": payload},
        ]
    })
    findings = caus._parse_agent_findings(envelope, "agent-x")
    assert len(findings) == 1
    assert findings[0]["summary"] == "via-messages"


def test_parse_findings_filters_non_dicts(caus):
    """If agent returns mixed list, only dict entries survive."""
    payload = json.dumps([{"severity": "P1"}, "garbage", 42, None])
    envelope = json.dumps({"result": payload})
    findings = caus._parse_agent_findings(envelope, "agent-x")
    assert len(findings) == 1


# --- _build_agent_prompt ----------------------------------------------------


def test_build_agent_prompt_contents(caus, tmp_path):
    cookies = tmp_path / "sim3.json"
    cookies.write_text("{}")
    prompt = caus._build_agent_prompt(
        cookies, "Day 2: AAPL", 2, "caus-day2-2026-05-13-sim3"
    )
    assert "Day 2: AAPL" in prompt
    assert str(cookies) in prompt
    assert "caus-day2-2026-05-13-sim3" in prompt
    assert "pivoxquant.com" in prompt
    # Iron Rule: forbids recommendation lexicon in prod UI — agent must enforce.
    assert "BUY/SELL" in prompt or "BUY" in prompt


# --- ensure_labels + create_github_issue (dry-run) -------------------------


def test_ensure_labels_dry_run(caus, capsys):
    caus.ensure_labels(dry_run=True)
    captured = capsys.readouterr()
    assert "would seed labels" in captured.out
    assert "caus" in captured.out
    assert "severity:p0" in captured.out


def test_create_github_issue_dry_run(caus, capsys):
    finding = {
        "severity": "P0",
        "category": "법규",
        "page": "/ai",
        "summary": "BUY 단어 노출",
        "repro": "1. /ai 진입 2. 챗 입력",
        "screenshot": "/tmp/a.png",
        "agent_id": "caus-test",
    }
    url = caus.create_github_issue(finding, datetime.date(2026, 5, 13), dry_run=True)
    assert url is None
    captured = capsys.readouterr()
    assert "would create issue" in captured.out
    assert "[CAUS 2026-05-13]" in captured.out
    assert "severity:p0" in captured.out


def test_create_github_issue_title_truncation(caus, capsys):
    """Summary >70 chars gets truncated in title."""
    finding = {"severity": "P1", "category": "UX", "summary": "x" * 200}
    caus.create_github_issue(finding, datetime.date(2026, 5, 13), dry_run=True)
    captured = capsys.readouterr()
    # 70-char summary cap from create_github_issue
    assert "x" * 70 in captured.out
    assert "x" * 71 not in captured.out


# --- alert_finding (dry-run) -----------------------------------------------


def test_alert_finding_dry_run(caus, capsys):
    finding = {"severity": "P0", "category": "법규", "summary": "test"}
    url = caus.alert_finding(finding, datetime.date(2026, 5, 13), dry_run=True)
    assert url is None
    # Slack stub should also print (no webhook in test env).
    captured = capsys.readouterr()
    assert "CAUS" in captured.out or "slack-stub" in captured.out


# --- write_daily_report -----------------------------------------------------


def test_write_daily_report_with_findings(caus, tmp_path, monkeypatch):
    monkeypatch.setattr(caus, "LOG_DIR", tmp_path)
    findings = [
        {"severity": "P0", "category": "법규", "page": "/ai", "summary": "x", "repro": "r", "screenshot": "s", "agent_id": "a"},
        {"severity": "P2", "category": "UX", "page": "/h", "summary": "y", "repro": "r2", "screenshot": "s2", "agent_id": "a"},
    ]
    issue_urls = ["https://github.com/x/1", None]
    log_path = caus.write_daily_report(
        datetime.date(2026, 5, 13), "sim4", "Day 1", findings, issue_urls
    )
    assert log_path.exists()
    content = log_path.read_text()
    assert "sim4" in content
    assert "Day 1" in content
    assert "findings: 2 (1 P0)" in content
    assert "https://github.com/x/1" in content
    assert "[P0]" in content
    assert "[P2]" in content


def test_write_daily_report_no_findings(caus, tmp_path, monkeypatch):
    monkeypatch.setattr(caus, "LOG_DIR", tmp_path)
    log_path = caus.write_daily_report(
        datetime.date(2026, 5, 13), "sim1", "Day 0", [], []
    )
    content = log_path.read_text()
    assert "no findings" in content
    assert "findings: 0 (0 P0)" in content


# --- main(--dry-run) end-to-end --------------------------------------------


def test_main_dry_run_skip_onboard(caus, tmp_path, monkeypatch):
    """--dry-run + --skip-onboard with a fake session file exits 0 cleanly."""
    monkeypatch.setattr(caus, "LOG_DIR", tmp_path / "reports")
    fake_sess_dir = tmp_path / "sessions"
    fake_sess_dir.mkdir()
    monkeypatch.setattr(caus, "SESSION_DIR", fake_sess_dir)

    # Create a session file for whichever user main() picks today.
    today = datetime.date.today()
    user_id = caus.pick_user_id(today)
    (fake_sess_dir / f"{user_id}.json").write_text("{}")

    # Force no SIM_ONBOARD_SECRET so we go through the fallback path.
    monkeypatch.setattr(caus, "SIM_ONBOARD_SECRET", "")

    rc = caus.main(["--dry-run", "--skip-onboard"])
    assert rc == 0
    # Report should have been written.
    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1


def test_main_no_session_no_secret_admits(caus, tmp_path, monkeypatch, capsys):
    """No session file + no SIM_ONBOARD_SECRET → warn + exit 0 (graceful)."""
    monkeypatch.setattr(caus, "LOG_DIR", tmp_path / "reports")
    monkeypatch.setattr(caus, "SESSION_DIR", tmp_path / "sessions-empty")
    monkeypatch.setattr(caus, "SIM_ONBOARD_SECRET", "")

    rc = caus.main(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "session missing" in out or "no fallback session" in out


# --- Day scenario rotation invariant ---------------------------------------


def test_day_scenarios_complete(caus):
    """7 scenarios, one per weekday — no IndexError on any weekday."""
    assert len(caus.DAY_SCENARIOS) == 7
    for i in range(7):
        assert isinstance(caus.DAY_SCENARIOS[i], str)
        assert len(caus.DAY_SCENARIOS[i]) > 10


def test_caus_labels_canonical(caus):
    """Labels match spec — name/color/desc tuple shape."""
    names = [name for name, _, _ in caus.CAUS_LABELS]
    assert names == ["caus", "severity:p0", "severity:p1", "severity:p2"]
    for name, desc, color in caus.CAUS_LABELS:
        assert len(color) == 6  # hex without #
        assert desc
