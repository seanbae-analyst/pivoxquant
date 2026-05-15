"""Unit tests for `scripts/caus_auto_fix.py` (CAUS Phase 4 auto-fix).

Smoke-only — these tests DO NOT spawn the real `claude` subprocess. The
subprocess invocation is mocked. We verify:

  - safety gates (severity / protected-path / daily budget / cooling-off
    / idempotency)
  - state persistence (rollover, recent-outcomes window, cooling-off
    trigger after 3 consecutive failures)
  - subprocess outcome parsing (PR_URL / INSUFFICIENT_EVIDENCE / ESCALATE
    / unparseable)
  - finding hash stability + truncation
  - finding I/O modes (--finding-json / --finding-stdin)
  - the actual subprocess invocation is end-to-end covered by manual
    smoke runs, not these unit tests.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
import unittest.mock as mock
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def auto_fix():
    """Import scripts/caus_auto_fix.py as a module."""
    src = REPO_ROOT / "scripts" / "caus_auto_fix.py"
    spec = importlib.util.spec_from_file_location("caus_auto_fix", src)
    assert spec and spec.loader, f"failed to spec {src}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["caus_auto_fix"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def isolated_state(auto_fix, tmp_path, monkeypatch):
    """Point STATE_FILE / LOG_DIR at tmp_path so tests don't touch real
    state. Returns the freshly-loaded state dict."""
    monkeypatch.setattr(auto_fix, "STATE_DIR", tmp_path)
    monkeypatch.setattr(auto_fix, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(auto_fix, "LOG_DIR", tmp_path / "log")
    return auto_fix.load_state()


def _finding(**over):
    base = {
        "severity": "P0",
        "category": "데이터",
        "page": "/portfolio",
        "summary": "all rendered money is zero (4/4)",
        "repro": "GET /portfolio",
        "screenshot": "N/A",
    }
    base.update(over)
    return base


# --- Safety gates -----------------------------------------------------------

class TestSafetyGates:
    def test_p0_allowed(self, auto_fix, isolated_state):
        allow, reason = auto_fix.allow_attempt(isolated_state, _finding(severity="P0"))
        assert allow is True
        assert reason == ""

    def test_p1_allowed(self, auto_fix, isolated_state):
        allow, _ = auto_fix.allow_attempt(isolated_state, _finding(severity="P1"))
        assert allow is True

    def test_p2_rejected(self, auto_fix, isolated_state):
        allow, reason = auto_fix.allow_attempt(isolated_state, _finding(severity="P2"))
        assert allow is False
        assert "severity" in reason

    def test_protected_billing_path(self, auto_fix, isolated_state):
        allow, reason = auto_fix.allow_attempt(
            isolated_state, _finding(page="/api/billing/checkout")
        )
        assert allow is False
        assert "protected-path" in reason

    def test_protected_auth_path(self, auto_fix, isolated_state):
        allow, reason = auto_fix.allow_attempt(
            isolated_state, _finding(page="routes/auth.py:42")
        )
        assert allow is False
        assert "protected-path" in reason

    def test_protected_migrations_path(self, auto_fix, isolated_state):
        allow, reason = auto_fix.allow_attempt(
            isolated_state, _finding(page="migrations/versions/034_xyz.py")
        )
        assert allow is False
        assert "protected-path" in reason

    def test_protected_portfolio_path(self, auto_fix, isolated_state):
        """Migration 034 policy: routes/portfolio.py is protected against
        auto-mutation (AAPL dirty-row decision)."""
        allow, reason = auto_fix.allow_attempt(
            isolated_state, _finding(page="routes/portfolio.py")
        )
        assert allow is False
        assert "protected-path" in reason

    def test_self_rewrite_blocked(self, auto_fix, isolated_state):
        """Defense-in-depth: never let the auto-fix loop rewrite itself
        or the cron driver."""
        allow, _ = auto_fix.allow_attempt(
            isolated_state, _finding(page="scripts/caus_auto_fix.py")
        )
        assert allow is False
        allow, _ = auto_fix.allow_attempt(
            isolated_state, _finding(page="scripts/caus_daily_sweep.py")
        )
        assert allow is False

    def test_daily_budget_exhaustion(self, auto_fix, isolated_state):
        isolated_state["today_fix_count"] = auto_fix.DAILY_BUDGET
        allow, reason = auto_fix.allow_attempt(isolated_state, _finding())
        assert allow is False
        assert "budget" in reason

    def test_cooling_off_blocks(self, auto_fix, isolated_state):
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            hours=12
        )
        isolated_state["cooling_off_until"] = future.strftime("%Y-%m-%dT%H:%M:%SZ")
        allow, reason = auto_fix.allow_attempt(isolated_state, _finding())
        assert allow is False
        assert "cooling-off" in reason

    def test_cooling_off_expired_does_not_block(self, auto_fix, isolated_state):
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            hours=12
        )
        isolated_state["cooling_off_until"] = past.strftime("%Y-%m-%dT%H:%M:%SZ")
        allow, _ = auto_fix.allow_attempt(isolated_state, _finding())
        assert allow is True

    def test_idempotency_blocks_repeat_finding(self, auto_fix, isolated_state):
        f = _finding()
        isolated_state["recent_finding_hashes"] = [auto_fix.finding_hash(f)]
        allow, reason = auto_fix.allow_attempt(isolated_state, f)
        assert allow is False
        assert "already attempted" in reason


# --- Outcome parsing --------------------------------------------------------

class TestOutcomeParsing:
    def test_pr_url_success(self, auto_fix):
        out = "Done.\nPR_URL https://github.com/seanbae/repo/pull/123"
        outcome, detail = auto_fix.parse_subprocess_outcome(out)
        assert outcome == "success"
        assert detail == "https://github.com/seanbae/repo/pull/123"

    def test_insufficient_evidence(self, auto_fix):
        outcome, _ = auto_fix.parse_subprocess_outcome(
            "Reading code...\nINSUFFICIENT_EVIDENCE"
        )
        assert outcome == "insufficient"

    def test_escalate(self, auto_fix):
        outcome, detail = auto_fix.parse_subprocess_outcome(
            "Found a contested bug.\nESCALATE migration needed"
        )
        assert outcome == "escalate"
        assert "migration" in detail

    def test_unparseable(self, auto_fix):
        outcome, detail = auto_fix.parse_subprocess_outcome("blah\nfoo bar baz")
        assert outcome == "unparseable"
        assert "foo bar baz" in detail

    def test_empty_stdout(self, auto_fix):
        outcome, _ = auto_fix.parse_subprocess_outcome("")
        assert outcome == "unparseable"


# --- State persistence ------------------------------------------------------

class TestStatePersistence:
    def test_fresh_state_shape(self, auto_fix):
        s = auto_fix._fresh_state()
        assert s["today_fix_count"] == 0
        assert s["recent_outcomes"] == []
        assert s["cooling_off_until"] is None

    def test_save_load_round_trip(self, auto_fix, isolated_state):
        isolated_state["today_fix_count"] = 2
        auto_fix.save_state(isolated_state)
        loaded = auto_fix.load_state()
        assert loaded["today_fix_count"] == 2

    def test_daily_rollover_resets_count(
        self, auto_fix, isolated_state, monkeypatch
    ):
        """When today_date is stale, load_state resets count + hashes."""
        isolated_state["today_date"] = "1999-01-01"
        isolated_state["today_fix_count"] = 99
        isolated_state["recent_finding_hashes"] = ["a", "b", "c"]
        auto_fix.save_state(isolated_state)
        loaded = auto_fix.load_state()
        assert loaded["today_fix_count"] == 0
        assert loaded["recent_finding_hashes"] == []

    def test_record_outcome_increments_count(
        self, auto_fix, isolated_state
    ):
        f = _finding()
        auto_fix.record_outcome(isolated_state, f, "success", "https://example.com/pr/1")
        assert isolated_state["today_fix_count"] == 1
        assert isolated_state["recent_outcomes"] == ["success"]

    def test_three_failures_trigger_cooling_off(
        self, auto_fix, isolated_state
    ):
        for i in range(3):
            f = _finding(summary=f"failure #{i}")
            auto_fix.record_outcome(isolated_state, f, "escalate", "x")
        # State must record cooling-off; the exact gate that fires next
        # depends on whether the daily budget is also exhausted (it is —
        # 3 attempts == DAILY_BUDGET — and the budget gate runs first).
        # Once the day rolls over, the budget resets but cooling-off
        # persists and IS the blocker.
        assert isolated_state["cooling_off_until"] is not None
        # Simulate day rollover: budget + recent-hashes reset, cooling
        # stays. allow_attempt should now block on cooling-off.
        isolated_state["today_fix_count"] = 0
        isolated_state["recent_finding_hashes"] = []
        allow, reason = auto_fix.allow_attempt(isolated_state, _finding(summary="next-day-attempt"))
        assert allow is False
        assert "cooling-off" in reason

    def test_mixed_outcomes_do_not_trigger_cooling_off(
        self, auto_fix, isolated_state
    ):
        auto_fix.record_outcome(isolated_state, _finding(summary="a"), "escalate", "")
        auto_fix.record_outcome(isolated_state, _finding(summary="b"), "success", "url")
        auto_fix.record_outcome(isolated_state, _finding(summary="c"), "escalate", "")
        # Last 3 are escalate / success / escalate — NOT all failures.
        assert isolated_state["cooling_off_until"] is None


# --- finding_hash ----------------------------------------------------------

class TestFindingHash:
    def test_same_finding_same_hash(self, auto_fix):
        f1 = _finding()
        f2 = _finding()
        assert auto_fix.finding_hash(f1) == auto_fix.finding_hash(f2)

    def test_different_summary_different_hash(self, auto_fix):
        f1 = _finding(summary="x")
        f2 = _finding(summary="y")
        assert auto_fix.finding_hash(f1) != auto_fix.finding_hash(f2)

    def test_hash_truncated_to_12_chars(self, auto_fix):
        assert len(auto_fix.finding_hash(_finding())) == 12


# --- run_one dry-run --------------------------------------------------------

class TestRunOneDryRun:
    def test_dry_run_does_not_invoke_claude(
        self, auto_fix, isolated_state, capsys, monkeypatch
    ):
        """Dry-run path must NOT call claude subprocess; it just plans."""
        monkeypatch.setattr(
            auto_fix, "invoke_claude",
            mock.Mock(side_effect=AssertionError("must not call")),
        )
        rc = auto_fix.run_one(_finding(), dry_run=True)
        assert rc == 0
        out = capsys.readouterr().out
        assert "DRY-RUN" in out

    def test_protected_path_skip(self, auto_fix, isolated_state, capsys):
        """run_one should return 0 with SKIP message on protected path."""
        rc = auto_fix.run_one(_finding(page="routes/auth.py"))
        assert rc == 0
        assert "SKIP" in capsys.readouterr().out

    def test_budget_exhausted_skip(self, auto_fix, isolated_state, capsys):
        isolated_state["today_fix_count"] = auto_fix.DAILY_BUDGET
        auto_fix.save_state(isolated_state)
        rc = auto_fix.run_one(_finding())
        assert rc == 0
        assert "SKIP" in capsys.readouterr().out
