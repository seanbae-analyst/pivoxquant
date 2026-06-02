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
from contextlib import contextmanager

import services as _services_pkg

# Build a minimal fake fx_service so check_fx_staleness() doesn't need Flask
_FAKE_FX = types.ModuleType("services.fx_service")
_FAKE_FX.get_rate = lambda: 1380.0
_FAKE_FX.last_updated = lambda: time.time()  # fresh by default
_FAKE_FX.is_stale = lambda: False


@contextmanager
def _use_fake_fx(fake_fx):
    """Force ``from services import fx_service`` to resolve to ``fake_fx``.

    check_fx_staleness() does ``from services import fx_service`` at call
    time, which is ``getattr(services, "fx_service")`` FIRST and only falls
    back to ``sys.modules`` on AttributeError. So if any earlier test in the
    suite did ``from services.fx_service import ...`` (e.g. test_market.py),
    the real module is bound as an attribute on the ``services`` package and
    a bare ``sys.modules`` patch is silently ignored — the source of the
    full-suite-only flakiness. Patch BOTH so isolation holds regardless of
    suite ordering.
    """
    with patch.dict(sys.modules, {"services.fx_service": fake_fx}):
        with patch.object(_services_pkg, "fx_service", fake_fx, create=True):
            yield


def _load_module(tmp_path):
    """Import fx_staleness_check with state I/O redirected into ``tmp_path``.

    The module recomputes ``_STATE_DIR`` / ``_STATE_FILE`` from ``__file__`` at
    exec time (see fx_staleness_check.py ~L58-60), so they MUST be reassigned
    *after* ``exec_module()``. Assigning them *before* exec — as this helper
    used to — is silently clobbered by the module body, making those lines dead.

    That was the real source of the full-suite flake: ``TestFxDedup`` (unlike
    ``TestFxStale24h``) never re-patched the paths after load, so
    ``check_fx_staleness()`` read/wrote the REAL ``state/fx_staleness_alerted.json``.
    Its dedup verdict then hinged on that shared file's ``last_alert_at`` vs
    wall-clock (and on whatever a prior run left behind): suppressed inside the
    6h ``DEDUP_HOURS`` window → ``rc==0`` (pass), outside it → alert → ``rc==1``
    (fail). Hence "passes in isolation right after a run, fails from a clean tree".
    Redirecting here, after exec, isolates every test that loads via this helper.

    ``_PROJECT_ROOT`` is intentionally left at its real value: the module only
    uses it for a ``sys.path`` insert, and pointing it at tmp_path would both
    pollute ``sys.path`` and break the ``from services import fx_service`` import.
    """
    spec = importlib.util.spec_from_file_location(
        "fx_staleness_check",
        _ROOT / "scripts/nightly/fx_staleness_check.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # AFTER exec (see docstring): redirect state reads/writes to the per-test tmp dir.
    mod._STATE_DIR = tmp_path / "state"
    mod._STATE_FILE = tmp_path / "state" / "fx_staleness_alerted.json"
    return mod


# Real on-disk state file the production module touches in prod. No test should
# read or write it — it is shared, runtime-mutable state (git-ignored via the
# ``state/`` rule). ``_load_module`` already redirects every loaded instance to
# tmp_path; this autouse fixture is the backstop: it snapshots the real file and
# restores it around each test, so even if some future path reaches it the
# working tree (and git) can never be left dirty — the way it was before this
# fix (full-suite-only flake + a perpetually ``M state/fx_staleness_alerted.json``).
_REAL_STATE_FILE = _ROOT / "state" / "fx_staleness_alerted.json"


@pytest.fixture(autouse=True)
def _guard_real_fx_state():
    snapshot = _REAL_STATE_FILE.read_bytes() if _REAL_STATE_FILE.exists() else None
    try:
        yield
    finally:
        if snapshot is None:
            # File didn't exist before the test — remove anything a leak created.
            if _REAL_STATE_FILE.exists():
                _REAL_STATE_FILE.unlink()
        elif (not _REAL_STATE_FILE.exists()) or _REAL_STATE_FILE.read_bytes() != snapshot:
            # Restore only if a leak actually mutated/removed it (keeps mtime stable otherwise).
            _REAL_STATE_FILE.write_bytes(snapshot)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestFxFresh:
    """No alert when rate is fresh."""

    def test_fresh_rate_returns_0(self, tmp_path):
        # fx_service.last_updated() returns now — fresh. _use_fake_fx pins
        # the fake on both sys.modules and the services package attribute.
        with _use_fake_fx(_FAKE_FX):
            mod = _load_module(tmp_path)
            rc = mod.check_fx_staleness()
        assert rc == 0, f"Expected 0 (fresh), got {rc}"


class TestFxStale24h:
    """Alert when rate is > 24h stale."""

    def test_stale_returns_1_and_writes_state(self, tmp_path):
        stale_ts = time.time() - (25 * 3600)
        fake_fx = types.ModuleType("services.fx_service")
        fake_fx.get_rate = lambda: 1380.0
        fake_fx.last_updated = lambda: stale_ts

        # Load module + call inside the fake-fx context so both exec_module
        # and the call-time ``from services import fx_service`` see the fake.
        with _use_fake_fx(fake_fx):
            mod = _load_module(tmp_path)
            # Patch module-level _STATE_DIR/_STATE_FILE to use tmp_path
            (tmp_path / "state").mkdir(parents=True, exist_ok=True)
            mod._STATE_DIR = tmp_path / "state"
            mod._STATE_FILE = tmp_path / "state" / "fx_staleness_alerted.json"

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
        fake_fx = types.ModuleType("services.fx_service")
        fake_fx.get_rate = lambda: 1380.0
        fake_fx.last_updated = lambda: 0.0

        # Load module + call inside the fake-fx context (see _use_fake_fx).
        with _use_fake_fx(fake_fx):
            mod = _load_module(tmp_path)
            (tmp_path / "state").mkdir(parents=True, exist_ok=True)
            mod._STATE_DIR = tmp_path / "state"
            mod._STATE_FILE = tmp_path / "state" / "fx_staleness_alerted.json"

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

        # _use_fake_fx so the rate is genuinely stale (not accidentally
        # "fresh" via a real fx_service leaked in from a prior test) — this
        # test must exercise dedup-suppresses-a-stale-alert, not pass by
        # coincidence on a fresh rate.
        with _use_fake_fx(fake_fx):
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
