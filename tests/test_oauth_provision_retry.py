"""
tests/test_oauth_provision_retry.py — OAuth provisioning transient-DB retry
===========================================================================

P0 OAuth ``provisioning_failed`` hardening (2026-05-20).

Railway PG flaps at the connection layer; the OAuth find-or-create + commit
(SELECT×2 + INSERT + COMMIT) lands inside the flap window and fails the login.
``routes.auth._provision_oauth_user`` wraps that block with short-backoff
retries scoped to *transient* DB faults only.

These are pure unit tests of the retry policy — they patch ``time.sleep`` so
the suite stays fast and do not require a live OAuth flow.
"""
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from routes import auth as auth_mod


def _op_error():
    # OperationalError(statement, params, orig)
    return OperationalError("SELECT 1", {}, Exception("connection refused"))


def _integrity_error():
    return IntegrityError("INSERT", {}, Exception("duplicate key"))


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch.object(auth_mod.time, "sleep") as s:
        yield s


class TestProvisionRetry:
    def test_success_first_attempt_no_sleep(self, app, _no_sleep):
        sentinel = object()
        with app.app_context(), patch.object(auth_mod.db.session, "commit") as commit:
            result = auth_mod._provision_oauth_user("google", lambda: sentinel)
        assert result is sentinel
        commit.assert_called_once()
        _no_sleep.assert_not_called()

    def test_transient_then_success(self, app, _no_sleep):
        sentinel = object()
        calls = {"n": 0}

        def build():
            calls["n"] += 1
            return sentinel

        # First commit raises OperationalError, second succeeds.
        commit_side = [_op_error(), None]
        with app.app_context(), \
                patch.object(auth_mod.db.session, "commit", side_effect=commit_side) as commit, \
                patch.object(auth_mod.db.session, "rollback") as rollback:
            result = auth_mod._provision_oauth_user("kakao", build)
        assert result is sentinel
        assert commit.call_count == 2
        # build() re-run on retry, rollback called once before retry.
        assert calls["n"] == 2
        rollback.assert_called_once()
        _no_sleep.assert_called_once()

    def test_transient_exhausts_retries_reraises(self, app, _no_sleep):
        # 3 total attempts (2 backoffs) → all raise OperationalError → re-raise.
        side = [_op_error(), _op_error(), _op_error()]
        with app.app_context(), \
                patch.object(auth_mod.db.session, "commit", side_effect=side) as commit, \
                patch.object(auth_mod.db.session, "rollback"):
            with pytest.raises(OperationalError):
                auth_mod._provision_oauth_user("google", lambda: object())
        assert commit.call_count == 3
        # Slept between each of the 2 retries.
        assert _no_sleep.call_count == 2

    def test_non_transient_not_retried(self, app, _no_sleep):
        # IntegrityError is deterministic — must re-raise immediately, no retry.
        with app.app_context(), \
                patch.object(auth_mod.db.session, "commit", side_effect=_integrity_error()) as commit, \
                patch.object(auth_mod.db.session, "rollback") as rollback:
            with pytest.raises(IntegrityError):
                auth_mod._provision_oauth_user("google", lambda: object())
        commit.assert_called_once()
        rollback.assert_called_once()
        _no_sleep.assert_not_called()

    def test_build_fn_transient_error_retried(self, app, _no_sleep):
        # The flap can hit the SELECTs inside build_fn, not just commit.
        sentinel = object()
        seq = [_op_error(), sentinel]

        def build():
            v = seq.pop(0)
            if isinstance(v, Exception):
                raise v
            return v

        with app.app_context(), \
                patch.object(auth_mod.db.session, "commit"), \
                patch.object(auth_mod.db.session, "rollback"):
            result = auth_mod._provision_oauth_user("google", build)
        assert result is sentinel
        _no_sleep.assert_called_once()


class TestIsTransient:
    def test_operational_error_is_transient(self):
        assert auth_mod._is_transient_db_error(_op_error()) is True

    def test_integrity_error_not_transient(self):
        assert auth_mod._is_transient_db_error(_integrity_error()) is False

    def test_plain_exception_not_transient(self):
        assert auth_mod._is_transient_db_error(ValueError("x")) is False
