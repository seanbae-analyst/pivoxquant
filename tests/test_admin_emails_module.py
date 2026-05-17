"""tests/test_admin_emails_module.py — services.admin_emails helper.

Wave 13 P2 (PR #442) pins the parsing contract that 5 routes files
used to duplicate. The full admin-gate behavior (403 etc.) is exercised
by test_command_center_smoke + test_admin_preview_smoke + test_admin_fmp_smoke
against the live routes; this file isolates the helper itself.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Each test starts with ADMIN_EMAILS unset."""
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    yield


def test_missing_env_returns_empty_set():
    from services.admin_emails import get_admin_emails
    assert get_admin_emails() == set()


def test_blank_env_returns_empty_set(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "")
    from services.admin_emails import get_admin_emails
    assert get_admin_emails() == set()


def test_comma_separated_lowercased(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "Foo@example.com,BAR@PIVOXQUANT.COM")
    from services.admin_emails import get_admin_emails
    assert get_admin_emails() == {"foo@example.com", "bar@pivoxquant.com"}


def test_whitespace_stripped(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "  a@x.com  ,  b@y.com\t,c@z.com ")
    from services.admin_emails import get_admin_emails
    assert get_admin_emails() == {"a@x.com", "b@y.com", "c@z.com"}


def test_empty_entries_dropped(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "a@x.com,,b@y.com,   ,c@z.com,")
    from services.admin_emails import get_admin_emails
    assert get_admin_emails() == {"a@x.com", "b@y.com", "c@z.com"}


# ── is_admin_email predicate ────────────────────────────────────────────────


def test_is_admin_email_true(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "ceo@pivoxquant.com")
    from services.admin_emails import is_admin_email
    assert is_admin_email("ceo@pivoxquant.com") is True
    # Lowercase normalisation.
    assert is_admin_email("CEO@PIVOXQUANT.COM") is True
    # Whitespace tolerance.
    assert is_admin_email("  ceo@pivoxquant.com  ") is True


def test_is_admin_email_false(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "ceo@pivoxquant.com")
    from services.admin_emails import is_admin_email
    assert is_admin_email("other@user.com") is False
    assert is_admin_email("") is False
    assert is_admin_email(None) is False


def test_is_admin_email_fail_closed_missing_env():
    """ADMIN_EMAILS unset → predicate returns False for everyone.
    Mirrors the fail-closed behaviour of the route-level _deny_non_admin
    helpers in routes/admin_*.py."""
    from services.admin_emails import is_admin_email
    assert is_admin_email("ceo@pivoxquant.com") is False
