"""
tests/test_dispatcher_pool_dispose.py
======================================
FIX 1 (overnight session) — transient-pool leak in scheduler-registered
dispatchers.

The 5 nightly dispatchers are CLI entry points whose main() calls
create_app(), and they are ALSO registered into the in-process APScheduler
(services/scheduler/cron_jobs.py:_wrap_python_main). In prod each tick spins a
NEW QueuePool that lingers ~300s (pool_recycle) toward Railway PG's 25-conn
ceiling. The fix:

  * set POPULATE_CACHE_ON_BOOT="0" before create_app() (suppress redundant
    FMP-hitting warmup thread), and
  * dispose the engine in a finally so the transient pool is freed even on
    error.

These tests run each dispatcher's real flow against the test app/DB and assert
db.engine.dispose() is invoked. The actual work (queue drains, alert scans) is
stubbed where it would hit network so the test stays light. POPULATE_CACHE_ON_BOOT
suppression is verified by asserting the env var is "0" at create_app() time.
"""
from unittest.mock import patch

import pytest


def _patch_create_app(test_app, captured_env):
    """Return a create_app stub that records POPULATE_CACHE_ON_BOOT and yields
    the shared test app (so db.engine is the real test engine)."""
    import os

    def _fake_create_app(*a, **kw):
        captured_env["populate"] = os.environ.get("POPULATE_CACHE_ON_BOOT")
        return test_app

    return _fake_create_app


@pytest.fixture
def dispose_spy():
    """Spy on extensions.db.engine.dispose without actually tearing down the
    shared session-scoped test engine (which other tests reuse)."""
    from extensions import db
    calls = {"n": 0}
    real = db.engine.dispose

    def _spy(*a, **kw):
        calls["n"] += 1
        # Do NOT call real dispose — the test engine is session-scoped and
        # shared; disposing would break sibling tests. We only need to confirm
        # the dispatcher *attempts* to release the pool.
        return None

    with patch.object(type(db.engine), "dispose", _spy):
        yield calls
    _ = real  # keep ref


class TestCheckoutFollowupDispose:
    def test_main_disposes_and_suppresses_warmup(self, app, dispose_spy):
        # checkout/email import create_app locally (`from app import create_app`
        # inside _drain_once), so we patch the source: app.create_app.
        import app as app_module
        import scripts.nightly.checkout_followup_dispatcher as mod
        captured = {}
        with patch.object(app_module, "create_app",
                          _patch_create_app(app, captured)):
            rc = mod.main()
        assert rc == 0
        assert dispose_spy["n"] >= 1, "engine.dispose must be called"
        assert captured["populate"] == "0", "warmup must be suppressed"


class TestEmailSchedulerDispose:
    def test_main_disposes_and_suppresses_warmup(self, app, dispose_spy):
        import app as app_module
        import scripts.nightly.email_scheduler_dispatcher as mod
        captured = {}
        with patch.object(app_module, "create_app",
                          _patch_create_app(app, captured)), \
                patch("services.email.onboarding_sequence.dispatch_due",
                      return_value={"sent": 0, "due": 0}), \
                patch("services.email.retention_sequence.dispatch_retention",
                      return_value={"sent": 0, "due": 0}):
            rc = mod.main()
        assert rc == 0
        assert dispose_spy["n"] >= 1
        assert captured["populate"] == "0"


class TestOauthFailureCheckDispose:
    def test_main_disposes_and_suppresses_warmup(self, app, dispose_spy):
        import app as app_module
        import scripts.nightly.oauth_failure_check as mod
        captured = {}
        with patch.object(app_module, "create_app",
                          _patch_create_app(app, captured)), \
                patch.object(mod, "run_once", return_value={"candidates": 0}):
            rc = mod.main()
        assert rc == 0
        assert dispose_spy["n"] >= 1
        assert captured["populate"] == "0"


class TestInactiveNudgeDispose:
    def test_main_disposes_and_suppresses_warmup(self, app, dispose_spy):
        import app as app_module
        import scripts.nightly.inactive_nudge_dispatcher as mod
        captured = {}
        with patch.object(app_module, "create_app",
                          _patch_create_app(app, captured)), \
                patch.object(mod, "run_once", return_value={"sent": 0}):
            rc = mod.main()
        assert rc == 0
        assert dispose_spy["n"] >= 1
        assert captured["populate"] == "0"


class TestPipaPurgeDispose:
    def test_main_disposes_and_suppresses_warmup(self, app, dispose_spy):
        import app as app_module
        import scripts.nightly.pipa_purge as mod
        captured = {}
        with patch.object(app_module, "create_app",
                          _patch_create_app(app, captured)), \
                patch.object(mod, "run_once", return_value={"candidates": 0}):
            rc = mod.main()
        assert rc == 0
        assert dispose_spy["n"] >= 1
        assert captured["populate"] == "0"

    def test_dispose_runs_even_on_error(self, app, dispose_spy):
        """finally must release the pool even when run_once raises."""
        import app as app_module
        import scripts.nightly.pipa_purge as mod
        captured = {}
        with patch.object(app_module, "create_app",
                          _patch_create_app(app, captured)), \
                patch.object(mod, "run_once", side_effect=RuntimeError("boom")):
            rc = mod.main()
        assert rc == 1  # crash path
        assert dispose_spy["n"] >= 1, "dispose must run via finally on error"
