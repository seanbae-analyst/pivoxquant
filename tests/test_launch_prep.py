"""Regression guard for services/launch_prep.py boot-time env validation.

The module's job: in production, log a structured inventory of every
recommended/required env var so missing keys surface in Railway
"Deploy Logs" within seconds. The current inventory pins down the
silent-degrade paths this session has hit (SendGrid → 17 mailer no-ops,
FMP → chart/news empty, Anthropic → AI 503, KIS → KR market broken).

These tests verify:
  - The inventory shape is well-formed
  - check_env in non-production mode is silent (returns the report
    without logging — local dev doesn't get spammed)
  - check_env in production mode logs CRITICAL/WARNING on missing keys
  - env_health_summary is small enough for /api/health echo
  - The /api/health endpoint includes the env summary
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def lp():
    """Import services/launch_prep.py as a module."""
    src = REPO_ROOT / "services" / "launch_prep.py"
    spec = importlib.util.spec_from_file_location("launch_prep", src)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["launch_prep"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestInventoryShape:
    def test_inventory_non_empty(self, lp):
        assert len(lp._INVENTORY) > 0

    def test_every_inventory_entry_well_formed(self, lp):
        for entry in lp._INVENTORY:
            assert len(entry) == 3, f"malformed inventory entry: {entry!r}"
            name, severity, purpose = entry
            assert isinstance(name, str) and name == name.upper(), (
                f"env var name must be upper-snake-case: {name!r}"
            )
            assert severity in ("required", "recommended", "optional"), (
                f"invalid severity {severity!r} on {name}"
            )
            assert isinstance(purpose, str) and len(purpose) > 10, (
                f"purpose too short on {name}"
            )

    def test_critical_paths_in_inventory(self, lp):
        """Pin the specific env vars this session's findings depend on."""
        names = {e[0] for e in lp._INVENTORY}
        for must_have in (
            "SENDGRID_API_KEY",  # Wave 5: PDF cron silent drop
            "BREVO_API_KEY",  # middle of the SendGrid->Brevo->SMTP cascade
            "FMP_API_KEY",  # Wave 5: chart + news empty root cause
            "KIS_APP_KEY",  # KR market data sourcing
            "DATABASE_URL",  # core
        ):
            assert must_have in names, f"{must_have} missing from inventory"


class TestCheckEnv:
    def test_non_production_silent(self, lp, caplog):
        """Dev / pytest path must not spam logs."""
        caplog.clear()
        with caplog.at_level(logging.INFO):
            result = lp.check_env(production=False)
        # The module logger is "launch_prep"; we should see NO records
        # from it when production=False.
        lp_records = [r for r in caplog.records if r.name == "launch_prep"]
        assert lp_records == [], (
            f"non-production check_env logged: {[r.message for r in lp_records]}"
        )
        # But the report shape is still well-formed.
        assert result["production"] is False
        assert "checks" in result
        assert "summary" in result
        assert result["summary"]["total_checked"] == len(lp._INVENTORY)

    def test_production_logs_on_missing(self, lp, caplog, monkeypatch):
        """Production mode logs CRITICAL or WARNING for missing recommended."""
        # Strip every inventory var from the env so they all show missing.
        for name, _, _ in lp._INVENTORY:
            monkeypatch.delenv(name, raising=False)
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="launch_prep"):
            lp.check_env(production=True)
        # The header line must fire because we cleared every recommended var.
        header_msgs = [
            r.message for r in caplog.records
            if r.name == "launch_prep" and "LAUNCH_PREP" in r.message
        ]
        assert any("RECOMMENDED" in m for m in header_msgs), (
            "expected a RECOMMENDED-count header line; got " + repr(header_msgs)
        )

    def test_production_all_set_logs_clean(self, lp, caplog, monkeypatch):
        """When every var is set, log the OK line, NOT the missing header."""
        for name, _, _ in lp._INVENTORY:
            monkeypatch.setenv(name, "set-for-test")
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="launch_prep"):
            lp.check_env(production=True)
        msgs = [r.message for r in caplog.records if r.name == "launch_prep"]
        assert any("all recommended/required env vars present" in m for m in msgs), (
            "expected the OK line; got " + repr(msgs)
        )

    def test_summary_counts_correct(self, lp, monkeypatch):
        """summary.missing_recommended must match the inventory + env state."""
        for name, _, _ in lp._INVENTORY:
            monkeypatch.delenv(name, raising=False)
        result = lp.check_env(production=False)
        expected_missing_recommended = sum(
            1 for _, sev, _ in lp._INVENTORY if sev == "recommended"
        )
        assert result["summary"]["missing_recommended"] == expected_missing_recommended


class TestEnvHealthSummary:
    def test_summary_compact(self, lp):
        """Summary must not contain the full per-var purpose strings —
        only counts. Keeps /api/health payload small."""
        s = lp.env_health_summary()
        # Required keys
        assert "missing_required" in s
        assert "missing_recommended" in s
        assert "total_checked" in s
        # No "checks" array (would bloat /api/health).
        assert "checks" not in s

    def test_summary_no_logging(self, lp, caplog):
        """env_health_summary must not log (it's called per /api/health
        hit; we'd flood logs)."""
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="launch_prep"):
            lp.env_health_summary()
        lp_records = [r for r in caplog.records if r.name == "launch_prep"]
        assert lp_records == [], (
            "env_health_summary leaked log messages: "
            + repr([r.message for r in lp_records])
        )

    def test_summary_production_reflects_flask_env(self, lp, monkeypatch):
        """Bug 2026-05-15 post-PR-#400 regression — the summary's
        ``production`` field used to leak the suppress-logging
        parameter (always False) instead of reflecting the real
        ``FLASK_ENV``. External monitors condition alerts on this
        flag, so it must be honest about prod-vs-dev."""
        monkeypatch.setenv("FLASK_ENV", "production")
        s = lp.env_health_summary()
        assert s["production"] is True, (
            "FLASK_ENV=production must surface as production=True"
        )
        monkeypatch.setenv("FLASK_ENV", "development")
        s = lp.env_health_summary()
        assert s["production"] is False


class TestHealthEndpointIncludesEnv:
    def test_health_response_has_env_summary(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.get_json()
        assert "env" in body
        assert "missing_recommended" in body["env"]
        assert "total_checked" in body["env"]
        # The summary must be small.
        assert "checks" not in body["env"]
