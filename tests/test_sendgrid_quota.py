"""Unit tests: scripts/nightly/sendgrid_quota_check.py (O-B)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ── path 설정 ─────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── import (lazy — SSL/urllib 사용, 외부 호출 없음) ───────────────────────────
from scripts.nightly.sendgrid_quota_check import (
    fetch_sendgrid_stats,
    load_history,
    save_history,
    set_failover_flag,
    clear_failover_flag,
    main,
    WARN_THRESHOLD,
    HARD_LIMIT,
)


# ── fetch_sendgrid_stats ─────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def _stats_response(requests: int = 42) -> bytes:
    return json.dumps([
        {
            "date": "2026-05-19",
            "stats": [{"metrics": {"requests": requests, "delivered": requests - 1}}],
        }
    ]).encode("utf-8")


def test_fetch_sendgrid_stats_ok(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: _FakeResponse(_stats_response(42)),
    )
    count = fetch_sendgrid_stats("fake-key")
    assert count == 42


def test_fetch_sendgrid_stats_empty(monkeypatch):
    """오늘 발송 없음 → 0 반환."""
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: _FakeResponse(json.dumps([]).encode()),
    )
    count = fetch_sendgrid_stats("fake-key")
    assert count == 0


def test_fetch_sendgrid_stats_http_error(monkeypatch):
    """HTTP 오류 → -1 반환."""
    import urllib.error

    def _raise(*a, **kw):
        raise urllib.error.HTTPError(None, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    count = fetch_sendgrid_stats("bad-key")
    assert count == -1


def test_fetch_sendgrid_stats_network_error(monkeypatch):
    import urllib.error

    def _raise(*a, **kw):
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    count = fetch_sendgrid_stats("fake-key")
    assert count == -1


# ── history ──────────────────────────────────────────────────────────────────

def test_save_load_history(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.QUOTA_HISTORY_PATH",
        tmp_path / "sendgrid_quota_history.json",
    )
    save_history({"2026-05-19": 55})
    loaded = load_history()
    assert loaded == {"2026-05-19": 55}


def test_load_history_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.QUOTA_HISTORY_PATH",
        tmp_path / "nonexistent.json",
    )
    assert load_history() == {}


# ── failover flag ─────────────────────────────────────────────────────────────

def test_failover_flag_set_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.STATE_DIR", tmp_path
    )
    set_failover_flag()
    flag = tmp_path / "brevo_failover.flag"
    assert flag.exists()
    clear_failover_flag()
    assert not flag.exists()


# ── main() 통합 ───────────────────────────────────────────────────────────────

def _patch_main(monkeypatch, tmp_path, count: int):
    monkeypatch.setenv("SENDGRID_API_KEY", "test-key")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.QUOTA_HISTORY_PATH",
        tmp_path / "h.json",
    )
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.fetch_sendgrid_stats",
        lambda *a: count,
    )
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.post_slack",
        lambda *a: True,
    )


def test_main_ok_low_count(monkeypatch, tmp_path):
    _patch_main(monkeypatch, tmp_path, count=10)
    rc = main()
    assert rc == 0


def test_main_warn_threshold(monkeypatch, tmp_path):
    _patch_main(monkeypatch, tmp_path, count=WARN_THRESHOLD)
    rc = main()
    assert rc == 0  # warn이지만 exit 0


def test_main_hard_limit(monkeypatch, tmp_path):
    _patch_main(monkeypatch, tmp_path, count=HARD_LIMIT)
    rc = main()
    assert rc == 2  # 한도 초과 → 2
    flag = tmp_path / "brevo_failover.flag"
    assert flag.exists()


def test_main_api_error(monkeypatch, tmp_path):
    _patch_main(monkeypatch, tmp_path, count=-1)
    rc = main()
    assert rc == 1


def test_main_missing_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.setattr(
        "scripts.nightly.sendgrid_quota_check.post_slack",
        lambda *a: True,
    )
    rc = main()
    assert rc == 1
