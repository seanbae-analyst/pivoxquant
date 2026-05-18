"""
tests/test_kis_token.py — KIS OAuth token manager
===================================================
KIS allows 1 token issue per minute (EGW00133). The singleton + lock must
prevent accidental re-issuance under concurrency.
No real HTTP calls are made — requests.post is mocked.
"""
import os
import sys
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Project root on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def clean_token_env(monkeypatch, tmp_path):
    """Provide fake KIS credentials and redirect the cache file to a tmp path."""
    from services.kis import token_manager as ktm

    monkeypatch.setenv("KIS_APP_KEY", "TEST_KEY_123")
    monkeypatch.setenv("KIS_APP_SECRET", "TEST_SECRET_ABC")
    monkeypatch.setenv("KIS_USE_REAL", "")  # VTS

    fake_cache = tmp_path / ".kis_token_cache.json"
    monkeypatch.setattr(ktm, "_CACHE_FILE", str(fake_cache))

    # Reset the singleton to pick up new env.
    ktm.KISTokenManager._instance = None
    yield ktm
    # Cleanup
    ktm.KISTokenManager._instance = None


class TestKISTokenManager:
    def test_singleton_returns_same_instance(self, clean_token_env):
        ktm = clean_token_env
        a = ktm.get_kis_token_manager()
        b = ktm.get_kis_token_manager()
        assert a is b, "get_kis_token_manager must be a process-wide singleton"

    def test_missing_credentials_returns_none(self, monkeypatch, tmp_path):
        """When KIS_APP_KEY is unset, get_token() must return None — never crash."""
        from services.kis import token_manager as ktm
        monkeypatch.delenv("KIS_APP_KEY", raising=False)
        monkeypatch.delenv("KIS_APP_SECRET", raising=False)
        monkeypatch.setattr(ktm, "_CACHE_FILE", str(tmp_path / "nope.json"))
        ktm.KISTokenManager._instance = None

        manager = ktm.get_kis_token_manager()
        assert manager.available is False
        assert manager.get_token() is None

    def test_cache_hit_avoids_http_call(self, clean_token_env):
        """A fresh in-memory token should be returned without hitting requests.post."""
        ktm = clean_token_env
        manager = ktm.get_kis_token_manager()
        # Pre-populate a valid token.
        manager._token = "cached-token-xyz"
        manager._expires_at = datetime.now() + timedelta(hours=11)

        with patch("services.kis.token_manager.requests.post") as mock_post:
            t = manager.get_token()

        assert t == "cached-token-xyz"
        mock_post.assert_not_called(), "Cache hit must not make HTTP call"

    def test_cache_miss_triggers_issue_call(self, clean_token_env):
        """When cache is empty, exactly one HTTP call must be made."""
        ktm = clean_token_env
        manager = ktm.get_kis_token_manager()
        manager._token = None
        manager._expires_at = None
        manager._last_issue_attempt = None

        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        resp.json.return_value = {
            "access_token": "freshly-minted", "expires_in": 43200,
        }

        with patch("services.kis.token_manager.requests.post", return_value=resp) as mock_post:
            t = manager.get_token()

        assert t == "freshly-minted"
        assert mock_post.call_count == 1

    def test_concurrent_requests_share_single_http_call(self, clean_token_env):
        """Lock guarantees: 10 concurrent get_token() → exactly 1 HTTP issue."""
        ktm = clean_token_env
        manager = ktm.get_kis_token_manager()
        manager._token = None
        manager._expires_at = None
        manager._last_issue_attempt = None

        call_count = {"n": 0}
        call_lock = threading.Lock()

        def slow_post(*a, **kw):
            with call_lock:
                call_count["n"] += 1
            # Simulate network latency so threads pile up on the lock.
            import time
            time.sleep(0.05)
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            resp.json.return_value = {
                "access_token": "single-shared-token", "expires_in": 43200,
            }
            return resp

        results = []
        def worker():
            results.append(manager.get_token())

        with patch("services.kis.token_manager.requests.post", side_effect=slow_post):
            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads: t.start()
            for t in threads: t.join()

        assert call_count["n"] == 1, (
            f"Expected 1 HTTP call under lock, got {call_count['n']} — race condition!"
        )
        assert all(r == "single-shared-token" for r in results)


# ── Wave 13 P2 (PR #441) — load vs refresh threshold split ──────────────────


def test_is_loadable_accepts_token_under_refresh_threshold():
    """A 30-min-remaining token must be loadable (was discarded pre-fix
    because _is_fresh required >1h). Pinned so the redeploy race
    (EGW00133 / KIS 60s rate-limit window) can't regress."""
    from services.kis.token_manager import KISTokenManager
    from datetime import datetime, timezone, timedelta

    expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    assert KISTokenManager._is_loadable("tok", expires) is True
    # 30-min remaining is BELOW the 1h refresh threshold, so _is_fresh
    # should still return False (proactive refresh kicks in).
    assert KISTokenManager._is_fresh("tok", expires) is False


def test_is_loadable_rejects_already_expired_token():
    from services.kis.token_manager import KISTokenManager
    from datetime import datetime, timezone, timedelta

    expired = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert KISTokenManager._is_loadable("tok", expired) is False


def test_is_loadable_handles_naive_datetime():
    """Legacy cache files were written with naive datetimes; the loader
    must promote to UTC, same as _is_fresh."""
    from services.kis.token_manager import KISTokenManager
    from datetime import datetime, timezone, timedelta

    naive = (datetime.now(timezone.utc) + timedelta(minutes=20)).replace(tzinfo=None)
    assert KISTokenManager._is_loadable("tok", naive) is True


def test_is_loadable_returns_false_for_missing_inputs():
    from services.kis.token_manager import KISTokenManager
    assert KISTokenManager._is_loadable(None, None) is False
    assert KISTokenManager._is_loadable("tok", None) is False
    assert KISTokenManager._is_loadable(None, "2030-01-01") is False


# ── Track A-3 (2026-05-18) — AES-GCM cache encryption ─────────────────────


class TestKISTokenCacheEncryption:
    """Wave G-2 Bug #8 (deferred → implemented): the .kis_token_cache.json
    file must be AES-GCM ciphertext, never plaintext access_token. These
    tests pin the bug closed."""

    def test_save_writes_aes_gcm_header_and_no_plaintext_token(self, clean_token_env):
        """A saved cache file MUST start with PIVOX-AES-GCM-v1\\n and MUST
        NOT contain the raw access_token bytes anywhere in the file."""
        ktm = clean_token_env
        from services.kis import token_manager as _ktm
        manager = ktm.get_kis_token_manager()
        secret_token = "SECRET-PIVOX-A3-TOKEN-do-not-leak-xyz"
        manager._token = secret_token
        manager._expires_at = datetime.now() + timedelta(hours=11)
        manager._save_to_file()

        with open(_ktm._CACHE_FILE, "rb") as f:
            raw = f.read()
        assert raw.startswith(b"PIVOX-AES-GCM-v1\n"), (
            f"Cache file missing AES-GCM header. First 32 bytes: {raw[:32]!r}"
        )
        assert secret_token.encode() not in raw, (
            "Raw access_token leaked into ciphertext file — encryption broken!"
        )

    def test_round_trip_save_load(self, clean_token_env):
        """save → fresh instance → load must recover the exact token."""
        ktm = clean_token_env
        manager = ktm.get_kis_token_manager()
        expected = "round-trip-token-A3"
        expected_exp = (datetime.now() + timedelta(hours=10)).replace(microsecond=0)
        manager._token = expected
        manager._expires_at = expected_exp
        manager._save_to_file()

        # Force re-instantiation so we hit _load_from_file fresh.
        ktm.KISTokenManager._instance = None
        manager2 = ktm.get_kis_token_manager()
        assert manager2._token == expected
        # Loader promotes naive → UTC; compare ignoring tz for the equality.
        assert manager2._expires_at.replace(tzinfo=None) == expected_exp

    def test_legacy_plaintext_cache_still_loadable_then_migrated(
        self, clean_token_env, caplog
    ):
        """A pre-Track-A3 plaintext JSON file must be readable (back-compat)
        AND get re-written as ciphertext on the next save."""
        import json as _json
        from services.kis import token_manager as _ktm

        legacy_token = "legacy-plaintext-token-pre-A3"
        legacy_exp = (datetime.now() + timedelta(hours=8)).isoformat()
        with open(_ktm._CACHE_FILE, "w") as f:
            _json.dump({"token": legacy_token, "expires": legacy_exp}, f)

        # Sanity: the file we just wrote IS plaintext.
        with open(_ktm._CACHE_FILE, "rb") as f:
            assert legacy_token.encode() in f.read()

        ktm = clean_token_env
        ktm.KISTokenManager._instance = None
        with caplog.at_level("WARNING"):
            manager = ktm.get_kis_token_manager()
        assert manager._token == legacy_token, "Legacy plaintext cache not loaded"
        assert any(
            "plaintext detected" in r.message for r in caplog.records
        ), "Expected plaintext-migration warning was not logged"

        # Trigger a save (refresh) → file must now be ciphertext.
        manager._save_to_file()
        with open(_ktm._CACHE_FILE, "rb") as f:
            after = f.read()
        assert after.startswith(b"PIVOX-AES-GCM-v1\n"), "Auto-migration to ciphertext failed"
        assert legacy_token.encode() not in after, "Plaintext leaked after migration"

    def test_corrupt_ciphertext_is_discarded_not_crashing(self, clean_token_env, caplog):
        """A ciphertext file written with a now-rotated key should NOT crash
        startup — it should be silently discarded so get_token() can re-issue."""
        from services.kis import token_manager as _ktm

        # Valid header but garbage body — simulates key rotation.
        with open(_ktm._CACHE_FILE, "wb") as f:
            f.write(b"PIVOX-AES-GCM-v1\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

        ktm = clean_token_env
        ktm.KISTokenManager._instance = None
        with caplog.at_level("WARNING"):
            manager = ktm.get_kis_token_manager()
        assert manager._token is None, "Corrupt ciphertext must not populate the token"
        assert any(
            "decrypt failed" in r.message for r in caplog.records
        ), "Expected decrypt-failure warning was not logged"

    def test_aad_is_not_default_broker(self, clean_token_env):
        """The kis token cache MUST use AAD b'kis-token-cache' so it cannot
        be cross-decrypted with broker_connections rows (which use b'broker').
        Pinned to catch accidental AAD regression."""
        from services.kis import token_manager as _ktm
        assert _ktm._CACHE_AAD == b"kis-token-cache"
        assert _ktm._CACHE_AAD != b"broker"
