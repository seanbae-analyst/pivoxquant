"""Regression guard: scripts/legal_monitor/monitor.py must use a hardened
SSL context for runtime DB scans.

The legal_monitor cron / GitHub Action runs detached from the user shell,
so urllib's default context can fall back to a stale system trust store
and yield ``CERTIFICATE_VERIFY_FAILED`` — mirrors the failure that
already bit the CAUS daily sweep (PR #362; that script was retired
2026-09-01, but the SSL failure mode it found is general).

This test pins the same defense: a module-level ``_SSL_CONTEXT`` rooted
at certifi when available, fallback to ``ssl.create_default_context()``,
and the ``scan_runtime_db`` urlopen call must pass it.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "legal_monitor" / "monitor.py"


@pytest.fixture(scope="module")
def monitor():
    """Import the legal monitor script as an isolated module."""
    spec = importlib.util.spec_from_file_location(
        "legal_monitor_monitor", SCRIPT_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["legal_monitor_monitor"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ssl_context_is_built_at_import(monitor):
    """Module-level _SSL_CONTEXT must be a verifying SSLContext.

    Regression guard mirroring the CAUS SSL fix in PR #362. If a future
    edit drops the context or downgrades it to ``CERT_NONE``, this test
    must fail loudly — silent verify-disabled is unacceptable for a
    legal monitor that talks to admin endpoints over HTTPS.
    """
    import ssl as _ssl

    ctx = monitor._SSL_CONTEXT
    assert isinstance(ctx, _ssl.SSLContext)
    assert ctx.verify_mode == _ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_build_ssl_context_prefers_certifi(monitor):
    """When certifi is installed, the context must load its CA bundle."""
    try:
        import certifi  # noqa: F401
    except ImportError:
        pytest.skip("certifi not installed in this env")

    ctx = monitor._build_ssl_context()
    assert len(ctx.get_ca_certs()) > 0


def test_scan_runtime_db_passes_ssl_context(monitor, monkeypatch):
    """``scan_runtime_db`` must forward _SSL_CONTEXT to urlopen.

    This guards against a regression where a future edit drops the
    ``context=...`` kwarg and silently falls back to the default
    (potentially-broken) trust store.
    """
    import urllib.request as _urlreq

    captured: dict = {}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"hits": []}'

    def fake_urlopen(req, timeout=20, context=None):
        captured["context"] = context
        captured["timeout"] = timeout
        captured["url"] = req.full_url
        return _FakeResp()

    monkeypatch.setenv("DB_SCAN_URL", "https://example.invalid/admin/scan")
    monkeypatch.setenv("DB_SCAN_TOKEN", "test-token")
    monkeypatch.setattr(_urlreq, "urlopen", fake_urlopen)

    findings = monitor.scan_runtime_db()

    assert captured["context"] is monitor._SSL_CONTEXT, (
        "scan_runtime_db must pass _SSL_CONTEXT to urlopen"
    )
    # Clean hits → no findings appended.
    assert findings == []
