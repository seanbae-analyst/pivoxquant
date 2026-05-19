"""
Tests for Wave I Q-1 — FX rate staleness detection.

scripts/nightly/fx_staleness_check.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Module-under-test ────────────────────────────────────────────────────────
# We import the module directly to avoid relying on services that need Flask.
import importlib
import types

# Build a minimal fake fx_service so check_fx_staleness() doesn't need Flask
_FAKE_FX = types.ModuleType("services.fx_service")
_FAKE_FX.get_rate = lambda: 1380.0
_FAKE_FX.last_updated = lambda: time.time()  # fresh by default
_FAKE_FX.is_stale = lambda: False


def _load_module(tmp_path):
    """Import fx_staleness_check with patched _PROJECT_ROOT."""
    spec = importlib.util.spec_from_file_location(
        "fx_staleness_check",
        _ROOT / "scripts/nightly/fx_staleness_check.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Patch _PROJECT_ROOT before exec so state files land in tmp_path
    mod.__dict__["_PROJECT_ROOT"] = tmp_path
    mod.__dict__["_STATE_DIR"] = tmp_path / "state"
    mod.__dict__["_STATE_FILE"] = tmp_path / "state" / "fx_staleness_alerted.json"
    spec.loader.exec_module(mod)
    return mod


# ── Tests ────────────────────────────────────────────────────────────────────

class TestFxFresh:
    """No alert when rate is fresh."""

    def test_fresh_rate_returns_0(self, tmp_path):
        mod = _load_module(tmp_path)
        # fx_service.last_updated() returns now — fresh
        with patch.dict(sys.modules, {"services": MagicMock(), "services.fx_service": _FAKE_FX}):
            with patch.object(mod, "_fetch_fx_service", create=True, return_value=_FAKE_FX):
                # Directly mock the import path inside the module
                with patch.dict(sys.modules, {"services.fx_service": _FAKE_FX}):
                    rc = mod.check_fx_staleness()
        assert rc == 0, f"Expected 0 (fresh), got {rc}"


class TestFxStale24h:
    """Alert when rate is > 24h stale."""

    def test_stale_returns_1_and_writes_state(self, tmp_path):
        mod = _load_module(tmp_path)
        # Patch module-level _STATE_DIR/_STATE_FILE to use tmp_path
        (tmp_path / "state").mkdir(parents=True, exist_ok=True)
        mod._STATE_DIR = tmp_path / "state"
        mod._STATE_FILE = tmp_path / "state" / "fx_staleness_alerted.json"

        stale_ts = time.time() - (25 * 3600)
        fake_fx = types.ModuleType("services.fx_service")
        fake_fx.get_rate = lambda: 1380.0
        fake_fx.last_updated = lambda: stale_ts

        with patch.dict(sys.modules, {"services.fx_service": fake_fx}):
            with patch.object(mod, "_post_slack", return_value=True) as mock_slack:
                with patch.object(mod, "_capture_sentry"):
                    rc = mod.check_fx_staleness()

        assert rc == 1, f"Expected 1 (stale+alert), got {rc}"
        mock_slack.assert_called_once()
        state_file = tmp_path / "state" / "fx_staleness_alerted.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert "last_alert_at" in state

    def test_never_fetched_returns_1(self, tmp_path):
        """last_updated() == 0.0 means never fetched — treated as stale."""
        mod = _load_module(tmp_path)
        (tmp_path / "state").mkdir(parents=True, exist_ok=True)
        mod._STATE_DIR = tmp_path / "state"
        mod._STATE_FILE = tmp_path / "state" / "fx_staleness_alerted.json"

        fake_fx = types.ModuleType("services.fx_service")
        fake_fx.get_rate = lambda: 1380.0
        fake_fx.last_updated = lambda: 0.0

        with patch.dict(sys.modules, {"services.fx_service": fake_fx}):
            with patch.object(mod, "_post_slack", return_value=True):
                with patch.object(mod, "_capture_sentry"):
                    rc = mod.check_fx_staleness()

        assert rc == 1


class TestFxDedup:
    """Dedup window prevents repeated alerts."""

    def test_dedup_suppresses_alert(self, tmp_path):
        """If alerted < DEDUP_HOURS ago, should return 0 (dedup)."""
        mod = _load_module(tmp_path)
        from datetime import datetime, timezone

        # Write a recent alert state
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "fx_staleness_alerted.json"
        recent_ts = datetime.now(timezone.utc).isoformat()
        state_file.write_text(json.dumps({"last_alert_at": recent_ts}))

        stale_ts = time.time() - (25 * 3600)
        fake_fx = types.ModuleType("services.fx_service")
        fake_fx.get_rate = lambda: 1380.0
        fake_fx.last_updated = lambda: stale_ts

        with patch.dict(sys.modules, {"services.fx_service": fake_fx}):
            with patch.object(mod, "_post_slack", return_value=True) as mock_slack:
                rc = mod.check_fx_staleness()

        assert rc == 0, "Dedup should have suppressed the alert"
        mock_slack.assert_not_called()


class TestFxSlack:
    """Slack helper — graceful when URL unset."""

    def test_post_slack_no_url(self, tmp_path, capsys):
        mod = _load_module(tmp_path)
        with patch.dict(mod.os.environ, {}, clear=True):
            # Remove SLACK_WEBHOOK_URL
            if "SLACK_WEBHOOK_URL" in mod.os.environ:
                del mod.os.environ["SLACK_WEBHOOK_URL"]
            result = mod._post_slack("test alert")
        assert result is False
        captured = capsys.readouterr()
        assert "FX-STALENESS-ALERT" in captured.out


class TestFxShouldAlert:
    """should_alert() dedup logic."""

    def test_no_prior_alert(self, tmp_path):
        mod = _load_module(tmp_path)
        assert mod._should_alert({}) is True

    def test_old_alert_should_alert(self, tmp_path):
        from datetime import datetime, timedelta, timezone
        mod = _load_module(tmp_path)
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
        assert mod._should_alert({"last_alert_at": old_ts}) is True

    def test_recent_alert_suppressed(self, tmp_path):
        from datetime import datetime, timezone
        mod = _load_module(tmp_path)
        recent_ts = datetime.now(timezone.utc).isoformat()
        assert mod._should_alert({"last_alert_at": recent_ts}) is False
