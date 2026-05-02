"""Smoke tests for routes/autotrade.py — DEAD CODE since 2026-04-27.

Per CEO + legal (투자일임업 회피), the autotrade blueprint is no longer
registered (see routes/__init__.py). The file is preserved for rollback.

These smoke tests are import-only — they verify the module is still
syntactically valid and exposes the historical surface, so a future
rollback isn't blocked by silent rot.
"""
from __future__ import annotations


class TestAutotradeNotRegistered:
    """Blueprint is intentionally unregistered. Routes must 404."""

    def test_autotrade_status_returns_404(self, client):
        r = client.get("/api/autotrade/status")
        assert r.status_code == 404

    def test_autotrade_start_returns_404(self, client):
        r = client.post("/api/autotrade/start", json={})
        assert r.status_code == 404


class TestAutotradeImportable:
    def test_module_imports_without_error(self):
        # Catches import-time syntax/decorator errors silently introduced
        # while the blueprint is unregistered (no boot-time exercise).
        from routes import autotrade
        assert hasattr(autotrade, "autotrade_bp")
        # All historical endpoints must still be deferred on the blueprint.
        # Status, start, stop, sell-all, pending, approve, reject, halt → 8.
        assert len(autotrade.autotrade_bp.deferred_functions) == 8
