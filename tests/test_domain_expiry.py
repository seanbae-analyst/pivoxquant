"""Unit tests: scripts/nightly/domain_expiry_check.py (Wave I E-2)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.nightly.domain_expiry_check import (  # noqa: E402
    THRESHOLD_DAYS,
    days_until,
    format_alert,
    load_state,
    lookup_expiration,
    main,
    pick_threshold,
    record_alert,
    save_state,
    should_alert,
)


# ── pick_threshold ────────────────────────────────────────────────────────────

def test_pick_threshold_above_max_returns_none():
    assert pick_threshold(100) is None  # > 60


def test_pick_threshold_d59_returns_60():
    assert pick_threshold(59) == 60


def test_pick_threshold_d29_returns_30():
    assert pick_threshold(29) == 30


def test_pick_threshold_d30_returns_30():
    assert pick_threshold(30) == 30


def test_pick_threshold_expired_returns_tightest():
    """Negative days = already expired. Should alert at tightest threshold."""
    assert pick_threshold(-5) == 30


# ── days_until ────────────────────────────────────────────────────────────────

def test_days_until_future():
    future = datetime.now(timezone.utc) + timedelta(days=45)
    assert 44 <= days_until(future) <= 45


def test_days_until_past():
    past = datetime.now(timezone.utc) - timedelta(days=10)
    assert days_until(past) <= -10


# ── lookup_expiration ─────────────────────────────────────────────────────────

def test_lookup_expiration_single_datetime():
    expiry = datetime(2027, 1, 15, tzinfo=timezone.utc)
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=expiry),
    )
    assert lookup_expiration("example.com", fake_whois) == expiry


def test_lookup_expiration_list_picks_earliest():
    """python-whois sometimes returns a list — we pick the earliest as the
    conservative reading (closest to expiry)."""
    early = datetime(2027, 1, 15, tzinfo=timezone.utc)
    late = datetime(2028, 1, 15, tzinfo=timezone.utc)
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=[late, early]),
    )
    assert lookup_expiration("example.com", fake_whois) == early


def test_lookup_expiration_naive_datetime_becomes_utc():
    naive = datetime(2027, 1, 15)  # tzinfo=None
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=naive),
    )
    result = lookup_expiration("example.com", fake_whois)
    assert result is not None
    assert result.tzinfo is not None


def test_lookup_expiration_none_field():
    """WHOIS server returned data but expiration_date missing → None."""
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=None),
    )
    assert lookup_expiration("example.com", fake_whois) is None


def test_lookup_expiration_no_attribute():
    """Edge case: returned object has no expiration_date attr at all."""
    class NoExpiry:
        pass
    fake_whois = SimpleNamespace(whois=lambda d: NoExpiry())
    assert lookup_expiration("example.com", fake_whois) is None


def test_lookup_expiration_raises_returns_none():
    """python-whois raises WhoisError for blocked servers / unknown TLDs.
    We must NOT propagate — return None so caller surfaces as INFO."""
    def raiser(d):
        raise RuntimeError("whois server timeout")
    fake_whois = SimpleNamespace(whois=raiser)
    assert lookup_expiration("example.com", fake_whois) is None


def test_lookup_expiration_list_with_invalid_entries():
    """List with non-datetime entries (e.g. string) — filter to valid only."""
    valid = datetime(2027, 6, 1, tzinfo=timezone.utc)
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=["not-a-date", valid, None]),
    )
    assert lookup_expiration("example.com", fake_whois) == valid


# ── should_alert / record_alert (dedup) ───────────────────────────────────────

def test_should_alert_first_time():
    state: dict = {}
    expiry = datetime(2027, 1, 1, tzinfo=timezone.utc)
    assert should_alert(state, "example.com", expiry, 30) is True


def test_should_alert_same_threshold_dedupes():
    expiry = datetime(2027, 1, 1, tzinfo=timezone.utc)
    state: dict = {}
    record_alert(state, "example.com", expiry, 30)
    assert should_alert(state, "example.com", expiry, 30) is False


def test_should_alert_different_threshold_allowed():
    """Already alerted at D-60 → still alert at D-30 for same expiry."""
    expiry = datetime(2027, 1, 1, tzinfo=timezone.utc)
    state: dict = {}
    record_alert(state, "example.com", expiry, 60)
    assert should_alert(state, "example.com", expiry, 30) is True


def test_should_alert_renewal_resets_dedup():
    """When expiry moves forward (renewal happened), the alert log for the
    old expiry is irrelevant → alert again."""
    old_expiry = datetime(2027, 1, 1, tzinfo=timezone.utc)
    new_expiry = datetime(2028, 1, 1, tzinfo=timezone.utc)
    state: dict = {}
    record_alert(state, "example.com", old_expiry, 30)
    # After renewal, expiry is now 2028 — alert should fire again.
    assert should_alert(state, "example.com", new_expiry, 30) is True


def test_record_alert_preserves_other_domains():
    expiry = datetime(2027, 1, 1, tzinfo=timezone.utc)
    state = {"other.com": {"expiry_iso": "2025-01-01T00:00:00+00:00",
                            "alerted_thresholds": [30]}}
    record_alert(state, "example.com", expiry, 30)
    assert "other.com" in state
    assert state["other.com"]["alerted_thresholds"] == [30]


# ── load/save_state roundtrip ─────────────────────────────────────────────────

def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "domain.json",
    )
    save_state({"example.com": {"expiry_iso": "2027-01-01T00:00:00+00:00",
                                 "alerted_thresholds": [30, 60]}})
    loaded = load_state()
    assert loaded["example.com"]["alerted_thresholds"] == [30, 60]


def test_load_state_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "missing.json",
    )
    assert load_state() == {}


# ── format_alert ──────────────────────────────────────────────────────────────

def test_format_alert_warn():
    expiry = datetime(2027, 1, 15, tzinfo=timezone.utc)
    msg = format_alert("pivoxquant.com", expiry, days_left=25, threshold=30)
    assert "[WARN]" in msg
    assert "D-25" in msg
    assert "pivoxquant.com" in msg


def test_format_alert_expired():
    expiry = datetime(2025, 1, 15, tzinfo=timezone.utc)
    msg = format_alert("pivoxquant.com", expiry, days_left=-5, threshold=30)
    assert "[CRIT]" in msg
    assert "EXPIRED" in msg


# ── main() integration ────────────────────────────────────────────────────────

def test_main_skip_when_whois_missing(tmp_path, monkeypatch):
    """If python-whois isn't installed at all, main exits 0 gracefully."""
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    # Simulate ImportError by forcing the module import to fail.
    with patch.dict(sys.modules, {"whois": None}):
        rc = main()
    assert rc == 0


def test_main_no_alert_when_far_future(tmp_path, monkeypatch):
    """Expiry > 60d away → no alert, exit 0."""
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    future = datetime.now(timezone.utc) + timedelta(days=180)
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=future),
    )
    with patch.dict(sys.modules, {"whois": fake_whois}):
        rc = main()
    assert rc == 0


def test_main_alert_when_within_window(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    soon = datetime.now(timezone.utc) + timedelta(days=20)  # D-20 < 30
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=soon),
    )
    with patch.dict(sys.modules, {"whois": fake_whois}):
        rc = main()
    assert rc == 1
    state = load_state()
    assert "pivoxquant.com" in state
    assert 30 in state["pivoxquant.com"]["alerted_thresholds"]


def test_main_overdue_returns_2(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    overdue = datetime.now(timezone.utc) - timedelta(days=3)
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=overdue),
    )
    with patch.dict(sys.modules, {"whois": fake_whois}):
        rc = main()
    assert rc == 2  # overdue = severity 2


def test_main_parse_failure_info_skip(tmp_path, monkeypatch):
    """WHOIS returns expiration_date=None → graceful info skip, exit 0."""
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=None),
    )
    with patch.dict(sys.modules, {"whois": fake_whois}):
        rc = main()
    assert rc == 0


def test_main_dedup_blocks_second_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.domain_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    soon = datetime.now(timezone.utc) + timedelta(days=20)
    fake_whois = SimpleNamespace(
        whois=lambda d: SimpleNamespace(expiration_date=soon),
    )
    with patch.dict(sys.modules, {"whois": fake_whois}):
        rc1 = main()
        rc2 = main()
    assert rc1 == 1
    # Second run within same expiry+threshold → dedup → exit 0
    assert rc2 == 0
