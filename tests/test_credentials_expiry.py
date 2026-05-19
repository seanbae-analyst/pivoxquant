"""Unit tests: scripts/nightly/credentials_expiry_check.py (S8)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.nightly.credentials_expiry_check import (  # noqa: E402
    CredentialPolicy,
    POLICIES,
    WARN_DAYS,
    DEDUP_HOURS,
    _parse_iso,
    days_until_expiry,
    format_alert,
    load_state,
    main,
    save_state,
    should_alert,
)


# ── _parse_iso ───────────────────────────────────────────────────────────────

def test_parse_iso_date_only():
    dt = _parse_iso("2026-05-17")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 17
    assert dt.tzinfo is not None


def test_parse_iso_full():
    dt = _parse_iso("2026-05-17T10:30:00+00:00")
    assert dt is not None
    assert dt.hour == 10 and dt.minute == 30


def test_parse_iso_z_suffix():
    dt = _parse_iso("2026-05-17T10:30:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_iso_invalid():
    assert _parse_iso("not-a-date") is None
    assert _parse_iso("") is None


# ── days_until_expiry ────────────────────────────────────────────────────────

def _policy(name="test", days=90, last="2026-01-01"):
    return CredentialPolicy(
        name=name, label=name, rotation_days=days,
        default_last_rotated=last, rotation_instructions="-",
    )


def test_days_until_expiry_uses_state_first(monkeypatch):
    # last_rotated in state overrides default. last_rotated=today → days_left ≈ 90.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = _policy(days=90, last="2020-01-01")  # default would be very overdue
    state = {p.name: {"last_rotated": today}}
    days_left = days_until_expiry(p, state)
    assert days_left is not None
    assert 88 <= days_left <= 90


def test_days_until_expiry_falls_back_to_default():
    long_ago = "2020-01-01"
    p = _policy(days=90, last=long_ago)
    days_left = days_until_expiry(p, state={})
    assert days_left is not None
    assert days_left < 0  # overdue


def test_days_until_expiry_unparseable_returns_none():
    p = _policy(last="not-a-date")
    assert days_until_expiry(p, state={p.name: {"last_rotated": "garbage"}}) is None


# ── should_alert ─────────────────────────────────────────────────────────────

def test_should_alert_outside_window():
    p = _policy()
    assert should_alert(p, state={}, days_left=WARN_DAYS + 1) is False


def test_should_alert_inside_window_no_prior():
    p = _policy()
    assert should_alert(p, state={}, days_left=WARN_DAYS) is True


def test_should_alert_dedup_blocks_recent():
    p = _policy()
    recent = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS - 1)
    state = {p.name: {"last_alert_at": recent.isoformat()}}
    assert should_alert(p, state, days_left=3) is False


def test_should_alert_dedup_allows_old():
    p = _policy()
    old = datetime.now(timezone.utc) - timedelta(hours=DEDUP_HOURS + 1)
    state = {p.name: {"last_alert_at": old.isoformat()}}
    assert should_alert(p, state, days_left=3) is True


def test_should_alert_overdue_with_dedup():
    """Overdue still respects dedup."""
    p = _policy()
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    state = {p.name: {"last_alert_at": recent.isoformat()}}
    assert should_alert(p, state, days_left=-5) is False


# ── format_alert ─────────────────────────────────────────────────────────────

def test_format_alert_warn():
    p = _policy(name="x", days=90, last="2026-01-01")
    msg = format_alert(p, days_left=3)
    assert "[WARN]" in msg and "D-3" in msg and p.label in msg


def test_format_alert_overdue():
    p = _policy(name="x", days=90, last="2026-01-01")
    msg = format_alert(p, days_left=-5)
    assert "[CRIT]" in msg and "OVERDUE" in msg


# ── load/save_state ──────────────────────────────────────────────────────────

def test_save_load_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "credentials_expiry.json",
    )
    save_state({"foo": {"last_rotated": "2026-05-17"}})
    assert load_state() == {"foo": {"last_rotated": "2026-05-17"}}


def test_load_state_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "missing.json",
    )
    assert load_state() == {}


# ── main() integration ───────────────────────────────────────────────────────

def test_main_no_alerts_when_all_fresh(tmp_path, monkeypatch):
    """All policies rotated 'today' → no alerts, exit 0."""
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = {p.name: {"last_rotated": today} for p in POLICIES}
    save_state(seed)

    rc = main()
    assert rc == 0


def test_main_alerts_when_within_window(tmp_path, monkeypatch):
    """Policy with last_rotated set so days_left <= WARN_DAYS triggers alert."""
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    # Use first policy; backdate so days_left ≈ 3 (inside WARN_DAYS=7).
    p0 = POLICIES[0]
    backdate = datetime.now(timezone.utc) - timedelta(days=p0.rotation_days - 3)
    seed = {p0.name: {"last_rotated": backdate.strftime("%Y-%m-%d")}}
    # Other policies recently rotated.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for p in POLICIES[1:]:
        seed[p.name] = {"last_rotated": today}
    save_state(seed)

    rc = main()
    assert rc == 0  # warn-only
    # state should now have last_alert_at for p0
    after = load_state()
    assert "last_alert_at" in after[p0.name]


def test_main_overdue_returns_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    p0 = POLICIES[0]
    long_overdue = datetime.now(timezone.utc) - timedelta(days=p0.rotation_days + 100)
    seed = {p0.name: {"last_rotated": long_overdue.strftime("%Y-%m-%d")}}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for p in POLICIES[1:]:
        seed[p.name] = {"last_rotated": today}
    save_state(seed)

    rc = main()
    assert rc == 2


# ── FMP plan (absolute_expiry_env) — Wave I E-1 ──────────────────────────────

def test_fmp_policy_present_in_catalog():
    """Catalog must include fmp_plan with absolute_expiry_env=FMP_PLAN_EXPIRY."""
    fmp = next((p for p in POLICIES if p.name == "fmp_plan"), None)
    assert fmp is not None, "fmp_plan policy missing from POLICIES"
    assert fmp.absolute_expiry_env == "FMP_PLAN_EXPIRY"
    assert fmp.warn_days == 30  # D-30 alert window


def test_fmp_days_until_uses_env(monkeypatch):
    """FMP policy's days_until_expiry must read FMP_PLAN_EXPIRY env directly,
    NOT compute from last_rotated + rotation_days."""
    future = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%d")
    monkeypatch.setenv("FMP_PLAN_EXPIRY", future)
    fmp = next(p for p in POLICIES if p.name == "fmp_plan")
    days_left = days_until_expiry(fmp, state={})
    assert days_left is not None
    assert 19 <= days_left <= 20


def test_fmp_days_until_env_missing_returns_none(monkeypatch):
    monkeypatch.delenv("FMP_PLAN_EXPIRY", raising=False)
    fmp = next(p for p in POLICIES if p.name == "fmp_plan")
    assert days_until_expiry(fmp, state={}) is None


def test_fmp_days_until_env_malformed_returns_none(monkeypatch):
    monkeypatch.setenv("FMP_PLAN_EXPIRY", "not-a-date")
    fmp = next(p for p in POLICIES if p.name == "fmp_plan")
    assert days_until_expiry(fmp, state={}) is None


def test_fmp_warn_window_uses_d30_not_d7(monkeypatch):
    """FMP warn window = 30. days_left=25 must alert (would not under default
    WARN_DAYS=7). Verifies the per-policy warn_days override works."""
    fmp = next(p for p in POLICIES if p.name == "fmp_plan")
    assert should_alert(fmp, state={}, days_left=25) is True
    assert should_alert(fmp, state={}, days_left=31) is False


def test_fmp_main_alerts_at_d20(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    # FMP expires in 20d → < 30d warn window → should alert.
    future = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%d")
    monkeypatch.setenv("FMP_PLAN_EXPIRY", future)
    # Keep other policies fresh.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = {p.name: {"last_rotated": today} for p in POLICIES if p.name != "fmp_plan"}
    save_state(seed)

    rc = main()
    assert rc == 0  # warn-only
    after = load_state()
    assert "last_alert_at" in after.get("fmp_plan", {})


def test_fmp_main_no_alert_when_env_missing(tmp_path, monkeypatch):
    """No FMP_PLAN_EXPIRY env → fmp_plan policy returns None days_left →
    silent skip (no alert, no state mutation for fmp_plan)."""
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("FMP_PLAN_EXPIRY", raising=False)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = {p.name: {"last_rotated": today} for p in POLICIES if p.name != "fmp_plan"}
    save_state(seed)

    rc = main()
    assert rc == 0
    after = load_state()
    # fmp_plan should NOT have been touched (env missing).
    assert "last_alert_at" not in after.get("fmp_plan", {})


def test_main_dedup_prevents_double_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_DIR", tmp_path
    )
    monkeypatch.setattr(
        "scripts.nightly.credentials_expiry_check.STATE_PATH",
        tmp_path / "s.json",
    )
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    p0 = POLICIES[0]
    backdate = datetime.now(timezone.utc) - timedelta(days=p0.rotation_days - 3)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = {
        p0.name: {
            "last_rotated": backdate.strftime("%Y-%m-%d"),
            "last_alert_at": datetime.now(timezone.utc).isoformat(),  # just alerted
        },
    }
    for p in POLICIES[1:]:
        seed[p.name] = {"last_rotated": today}
    save_state(seed)

    rc = main()
    assert rc == 0  # dedup'd
