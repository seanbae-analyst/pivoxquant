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


# --- Phase 3 — _validate_finding -------------------------------------------


def test_validate_finding_accepts_minimal(caus):
    """Required keys present → finding returned with agent_id injected."""
    raw = {"severity": "P0", "category": "법규", "page": "/ai", "summary": "x"}
    out = caus._validate_finding(raw, "agent-x")
    assert out is not None
    assert out["agent_id"] == "agent-x"
    assert out["severity"] == "P0"


def test_validate_finding_rejects_missing_keys(caus, capsys):
    raw = {"severity": "P0", "summary": "x"}  # missing category, page
    out = caus._validate_finding(raw, "agent-x")
    assert out is None


def test_validate_finding_rejects_non_dict(caus):
    assert caus._validate_finding("not-a-dict", "agent-x") is None
    assert caus._validate_finding(None, "agent-x") is None
    assert caus._validate_finding(42, "agent-x") is None


def test_validate_finding_coerces_str_fields(caus):
    """Non-string values for str fields are coerced (no downstream crash)."""
    raw = {"severity": 0, "category": ["x"], "page": "/h", "summary": 9}
    out = caus._validate_finding(raw, "agent-x")
    assert out is not None
    assert isinstance(out["severity"], str)
    assert isinstance(out["summary"], str)


# --- Phase 3 — scenario module surface --------------------------------------


def test_scenario_module_map_complete(caus):
    """All 7 day{N} short forms + 7 module names map into valid indices."""
    for i in range(7):
        assert caus.SCENARIO_MODULE_MAP[f"day{i}"] == i
    for idx, (module_name, _) in enumerate(caus.DAY_SCENARIOS):
        assert caus.SCENARIO_MODULE_MAP[module_name] == idx


def test_load_scenario_module_resolves(caus):
    """All 7 modules import cleanly and expose run()."""
    for module_name, _ in caus.DAY_SCENARIOS:
        mod = caus._load_scenario_module(module_name)
        assert mod is not None, f"failed to import {module_name}"
        assert callable(getattr(mod, "run", None)), \
            f"{module_name} missing run() callable"


def test_load_scenario_module_unknown_returns_none(caus):
    assert caus._load_scenario_module("not_a_real_scenario_xyz") is None


# --- SSL context regression (cron-compat) -----------------------------------


def test_ssl_context_is_built_at_import(caus):
    """Module-level _SSL_CONTEXT must be a verifying SSLContext.

    Regression guard for the 2026-05-13 cron failure where urllib's default
    context could not verify pivoxquant.com against macOS LibreSSL.
    """
    import ssl as _ssl

    ctx = caus._SSL_CONTEXT
    assert isinstance(ctx, _ssl.SSLContext)
    # Must verify — never silently disable cert checking.
    assert ctx.verify_mode == _ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_build_ssl_context_prefers_certifi(caus):
    """When certifi is installed, the context must load its CA bundle."""
    try:
        import certifi  # noqa: F401
    except ImportError:
        import pytest as _pytest
        _pytest.skip("certifi not installed in this env")

    ctx = caus._build_ssl_context()
    # get_ca_certs() returns the loaded trust store. With certifi we expect
    # a non-empty bundle (the system default may also be non-empty, but the
    # certifi path is the one that survived prior LibreSSL failures).
    assert len(ctx.get_ca_certs()) > 0


def test_sim_onboard_passes_ssl_context(caus, monkeypatch):
    """sim_onboard_login must hand _SSL_CONTEXT to urlopen.

    This guards against a regression where a future edit drops the
    `context=...` kwarg and silently falls back to the broken default.
    """
    captured: dict = {}

    class _FakeResp:
        status = 200
        headers = {"Set-Cookie": "sid=test"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(req, timeout=15, context=None):
        captured["context"] = context
        captured["url"] = req.full_url
        return _FakeResp()

    monkeypatch.setattr(caus, "SIM_ONBOARD_SECRET", "test-secret")
    monkeypatch.setattr(
        caus.urllib.request, "urlopen", fake_urlopen
    )
    monkeypatch.setattr(caus, "SESSION_DIR", caus.SESSION_DIR)  # noop

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(caus, "SESSION_DIR", Path(tmp))
        sess = caus.sim_onboard_login("simX")
        assert sess is not None
        assert captured["context"] is caus._SSL_CONTEXT, (
            "sim_onboard_login must pass _SSL_CONTEXT to urlopen"
        )


def test_run_user_tester_dry_run_no_browser(caus, capsys, tmp_path):
    """dry_run prints invocation and returns [] without launching browser."""
    cookies = tmp_path / "sim.json"
    cookies.write_text("{}")
    result = caus.run_user_tester(
        cookies, "day2_us_watchlist", 2, "agent-x", dry_run=True
    )
    assert result == []
    out = capsys.readouterr().out
    assert "Playwright scenario" in out
    assert "day2_us_watchlist" in out


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
    """7 scenarios, one per weekday — no IndexError on any weekday.

    Phase 3 changed DAY_SCENARIOS to a list of (module_name, label) tuples.
    """
    assert len(caus.DAY_SCENARIOS) == 7
    for i in range(7):
        entry = caus.DAY_SCENARIOS[i]
        assert isinstance(entry, tuple) and len(entry) == 2
        module_name, label = entry
        assert isinstance(module_name, str) and module_name.startswith(f"day{i}")
        assert isinstance(label, str) and len(label) > 10


def test_caus_labels_canonical(caus):
    """Labels match spec — name/color/desc tuple shape."""
    names = [name for name, _, _ in caus.CAUS_LABELS]
    assert names == ["caus", "severity:p0", "severity:p1", "severity:p2"]
    for name, desc, color in caus.CAUS_LABELS:
        assert len(color) == 6  # hex without #
        assert desc
