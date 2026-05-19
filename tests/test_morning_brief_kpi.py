"""Unit tests: scripts/morning_brief/build_brief_kpi.py (S6 + O-M)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.morning_brief.build_brief_kpi import (
    fetch_stripe_kpi,
    fetch_sentry_kpi,
    render_kpi_brief,
    main,
)


# ── fetch_stripe_kpi ─────────────────────────────────────────────────────────

class _FakeResp:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def test_fetch_stripe_kpi_missing_key(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    result = fetch_stripe_kpi()
    assert result["charges_success"] == "N/A"
    assert "caveat" in result


def test_fetch_stripe_kpi_ok(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    data = {
        "data": [
            {"status": "succeeded", "amount_received": 990, "currency": "usd"},
            {"status": "succeeded", "amount_received": 1990, "currency": "usd"},
            {"status": "requires_payment_method", "amount_received": 0, "currency": "usd"},
        ]
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: _FakeResp(json.dumps(data).encode()),
    )
    result = fetch_stripe_kpi()
    assert result["charges_success"] == 2
    assert result["charges_fail"] == 1
    assert result["revenue_today_usd"] == "$29.80"


def test_fetch_stripe_kpi_http_error(monkeypatch):
    import urllib.error
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")

    def _raise(*a, **kw):
        raise urllib.error.HTTPError(None, 403, "Forbidden", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    result = fetch_stripe_kpi()
    # graceful empty-dict on HTTPError (silent fail = 0원 보장 패턴)
    assert result["charges_success"] == 0
    assert result["charges_fail"] == 0


# ── fetch_sentry_kpi ─────────────────────────────────────────────────────────

def test_fetch_sentry_kpi_missing_env(monkeypatch):
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SENTRY_ORG", raising=False)
    monkeypatch.delenv("SENTRY_PROJECT", raising=False)
    result = fetch_sentry_kpi()
    assert result["total_issues_24h"] == "N/A"
    assert "caveat" in result


def test_fetch_sentry_kpi_ok(monkeypatch):
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "fake-token")
    monkeypatch.setenv("SENTRY_ORG", "pivoxquant")
    monkeypatch.setenv("SENTRY_PROJECT", "backend")
    issues = [
        {"level": "error"},
        {"level": "error"},
        {"level": "warning"},
        {"level": "fatal"},
    ]
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: _FakeResp(json.dumps(issues).encode()),
    )
    result = fetch_sentry_kpi()
    assert result["total_issues_24h"] == 4
    assert result["unresolved_critical"] == 3  # error(2) + fatal(1)


def test_fetch_sentry_kpi_http_error(monkeypatch):
    import urllib.error
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "tok")
    monkeypatch.setenv("SENTRY_ORG", "org")
    monkeypatch.setenv("SENTRY_PROJECT", "proj")

    def _raise(*a, **kw):
        raise urllib.error.HTTPError(None, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    result = fetch_sentry_kpi()
    assert "error" in result


# ── render_kpi_brief ─────────────────────────────────────────────────────────

def test_render_kpi_brief_contains_sections():
    db = {"dau": 10, "wau": 50, "new_users_24h": 3, "total_users": 200, "caveat": "추측 테스트"}
    stripe = {"charges_success": 5, "charges_fail": 1, "revenue_today_usd": "$49.50"}
    sentry = {"total_issues_24h": 2, "unresolved_critical": 1}
    brief = render_kpi_brief(db, stripe, sentry)
    assert "DAU" in brief
    assert "Stripe" in brief
    assert "Sentry" in brief
    assert "추측 테스트" in brief


def test_render_kpi_brief_na_values():
    db = {"dau": "N/A", "wau": "N/A", "new_users_24h": "N/A", "total_users": "N/A"}
    stripe = {"charges_success": "N/A", "charges_fail": "N/A", "revenue_today_usd": "N/A"}
    sentry = {"total_issues_24h": "N/A", "unresolved_critical": "N/A"}
    brief = render_kpi_brief(db, stripe, sentry)
    assert "N/A" in brief


# ── main() 통합 ───────────────────────────────────────────────────────────────

def test_main_runs_without_db(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(
        "scripts.morning_brief.build_brief_kpi.BRIEFS_DIR", tmp_path
    )
    rc = main(["--no-slack"])
    assert rc == 0
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text("utf-8")
    assert "Morning Brief KPI" in content
