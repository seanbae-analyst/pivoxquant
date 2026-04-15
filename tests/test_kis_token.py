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
    import kis_token_manager as ktm

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
        import kis_token_manager as ktm
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

        with patch("kis_token_manager.requests.post") as mock_post:
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

        with patch("kis_token_manager.requests.post", return_value=resp) as mock_post:
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

        with patch("kis_token_manager.requests.post", side_effect=slow_post):
            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads: t.start()
            for t in threads: t.join()

        assert call_count["n"] == 1, (
            f"Expected 1 HTTP call under lock, got {call_count['n']} — race condition!"
        )
        assert all(r == "single-shared-token" for r in results)
