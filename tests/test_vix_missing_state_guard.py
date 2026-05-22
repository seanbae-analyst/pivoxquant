"""
tests/test_vix_missing_state_guard.py
=====================================
FIX 2 (overnight session) — VIX spike mass-email guard.

`RiskBoardService.run_vix_spike_check` persists prev-VIX to a JSON file under
`artifacts/risk_board/`, which is gitignored AND lives on Railway's ephemeral
FS. On every deploy the file vanishes → prev_vix=None. The OLD condition
treated `prev_vix is None` as "was below threshold", so any deploy while
VIX >= 25 fired a spike-edition Risk Board PDF to EVERY premium user.

The fix: a missing/None prior state must NOT count as a below→above crossing.
Instead seed the current observation and return WITHOUT firing. A real
prev<threshold → current>=threshold transition still fires.

These tests use a tmp storage dir (RISK_BOARD_STORAGE_DIR) so no real state
file is touched, and patch `get_current_vix` + `run_for_user` so nothing is
actually emailed.
"""
import json
from unittest.mock import patch

import pytest


def _service():
    from services.artifacts.risk_board_service import RiskBoardService
    return RiskBoardService()


@pytest.fixture
def vix_storage(tmp_path, monkeypatch):
    """Point VIX state at an isolated tmp dir; default threshold 25."""
    monkeypatch.setenv("RISK_BOARD_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("RISK_BOARD_VIX_THRESHOLD", "25")
    return tmp_path


def _state_path(storage_dir):
    return storage_dir / "_vix_state.json"


class TestVixMissingStateGuard:
    def test_missing_state_high_vix_does_not_fire_but_seeds(self, app, vix_storage):
        """No prior state + VIX >= threshold → MUST NOT fire; seeds state."""
        assert not _state_path(vix_storage).exists()

        fired = []

        def _fake_run_for_user(self, u, trigger=None, now=None):
            fired.append(u.id)
            return {"ok": True}

        with app.app_context(), \
                patch("services.artifacts.risk_board_service.get_current_vix",
                      return_value=40.0), \
                patch("services.artifacts.risk_board_service."
                      "RiskBoardService.run_for_user", _fake_run_for_user):
            result = _service().run_vix_spike_check()

        # The crux: no mass email on missing-state.
        assert result["triggered"] is False
        assert result["notified"] == 0
        assert fired == [], "spike must NOT fan out on missing prior state"

        # State must be seeded for the next tick.
        sp = _state_path(vix_storage)
        assert sp.exists(), "current observation must be seeded"
        state = json.loads(sp.read_text())
        assert state["last_vix"] == 40.0
        # No notification recorded — we only seeded.
        assert state.get("last_notified_at") is None

    def test_none_prev_with_high_vix_in_state_file_does_not_fire(self, app, vix_storage):
        """State file present but last_vix is None (corrupt/partial) → no fire."""
        _state_path(vix_storage).write_text(json.dumps({
            "last_vix": None,
            "last_observed_at": "2026-05-22T00:00:00",
            "last_notified_at": None,
        }))

        fired = []

        def _fake_run_for_user(self, u, trigger=None, now=None):
            fired.append(u.id)
            return {"ok": True}

        with app.app_context(), \
                patch("services.artifacts.risk_board_service.get_current_vix",
                      return_value=33.0), \
                patch("services.artifacts.risk_board_service."
                      "RiskBoardService.run_for_user", _fake_run_for_user):
            result = _service().run_vix_spike_check()

        assert result["triggered"] is False
        assert result["notified"] == 0
        assert fired == []

    def test_real_below_to_above_transition_fires(self, app, vix_storage, make_user):
        """prev<threshold then current>=threshold → genuine crossing fires."""
        _state_path(vix_storage).write_text(json.dumps({
            "last_vix": 18.0,  # real prior reading below threshold
            "last_observed_at": "2026-05-22T00:00:00",
            "last_notified_at": None,
        }))

        # One premium user to fan out to.
        make_user(email="prem@test.com", tier="premium")

        fired = []

        def _fake_run_for_user(self, u, trigger=None, now=None):
            fired.append(u.subscription_tier)
            return {"ok": True}

        with app.app_context(), \
                patch("services.artifacts.risk_board_service.get_current_vix",
                      return_value=30.0), \
                patch("services.artifacts.risk_board_service."
                      "RiskBoardService.run_for_user", _fake_run_for_user):
            result = _service().run_vix_spike_check()

        assert result["triggered"] is True, "genuine below→above must fire"
        assert result["notified"] >= 1
        assert "premium" in fired

        # last_notified_at now stamped (notification path ran).
        state = json.loads(_state_path(vix_storage).read_text())
        assert state["last_vix"] == 30.0
        assert state.get("last_notified_at") is not None

    def test_already_elevated_stays_no_op(self, app, vix_storage):
        """prev>=threshold and current>=threshold → no re-fire."""
        _state_path(vix_storage).write_text(json.dumps({
            "last_vix": 28.0,  # already above
            "last_observed_at": "2026-05-22T00:00:00",
            "last_notified_at": "2026-05-22T00:00:00",
        }))

        fired = []

        def _fake_run_for_user(self, u, trigger=None, now=None):
            fired.append(u.id)
            return {"ok": True}

        with app.app_context(), \
                patch("services.artifacts.risk_board_service.get_current_vix",
                      return_value=31.0), \
                patch("services.artifacts.risk_board_service."
                      "RiskBoardService.run_for_user", _fake_run_for_user):
            result = _service().run_vix_spike_check()

        assert result["triggered"] is False
        assert fired == []

    def test_failed_vix_fetch_preserves_state(self, app, vix_storage):
        """get_current_vix None → no fire, state untouched."""
        _state_path(vix_storage).write_text(json.dumps({
            "last_vix": 18.0,
            "last_observed_at": "2026-05-22T00:00:00",
            "last_notified_at": None,
        }))

        with app.app_context(), \
                patch("services.artifacts.risk_board_service.get_current_vix",
                      return_value=None):
            result = _service().run_vix_spike_check()

        assert result["triggered"] is False
        # State preserved (not wiped) on fetch failure.
        state = json.loads(_state_path(vix_storage).read_text())
        assert state["last_vix"] == 18.0
