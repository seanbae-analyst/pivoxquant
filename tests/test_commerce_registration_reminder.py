"""Unit tests: scripts/nightly/commerce_registration_reminder.py (Wave I L-3).

Coverage
========
- ``_is_registered`` truthy parsing (true / 1 / yes / y / on / case-insensitive).
- Same-month dedup (``already_alerted_this_month``).
- main() short-circuits when ``PIVOX_COMMERCE_REGISTERED=true`` (no Slack call).
- main() short-circuits when same month already alerted (no Slack call).
- main() dispatches once when flag off AND no prior alert this month.
- Slack failure (post returns False) does NOT raise + state still recorded
  via stdout fallback.
- Alert body contains §12 statute citation + 정부24 + 공정거래위원회 + Q-S3.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.nightly import commerce_registration_reminder as crr  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Redirect state file to a tmp dir to avoid clobbering real state.

    The module reads STATE_PATH at import time (module-level constant), so we
    monkeypatch the module attribute, not just the env.
    """
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "commerce_registration_reminder.json"
    monkeypatch.setattr(crr, "STATE_DIR", state_dir)
    monkeypatch.setattr(crr, "STATE_PATH", state_file)
    return state_file


@pytest.fixture
def no_slack(monkeypatch):
    """Force stdout fallback by clearing the webhook env var."""
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.delenv("PIVOX_COMMERCE_REGISTERED", raising=False)


# ── _is_registered ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("val", ["true", "TRUE", "True", "1", "yes", "Y", "on", "ON"])
def test_is_registered_truthy(monkeypatch, val):
    monkeypatch.setenv("PIVOX_COMMERCE_REGISTERED", val)
    assert crr._is_registered() is True


@pytest.mark.parametrize("val", ["false", "0", "no", "n", "off", "", "  ", "maybe"])
def test_is_registered_falsy(monkeypatch, val):
    monkeypatch.setenv("PIVOX_COMMERCE_REGISTERED", val)
    assert crr._is_registered() is False


def test_is_registered_unset(monkeypatch):
    monkeypatch.delenv("PIVOX_COMMERCE_REGISTERED", raising=False)
    assert crr._is_registered() is False


# ── _month_key + dedup ─────────────────────────────────────────────────────


def test_month_key_uses_kst():
    """A UTC datetime late in the day must roll over to next KST day/month
    correctly. 2026-05-31 22:00 UTC = 2026-06-01 07:00 KST → month '2026-06'.
    """
    dt = datetime(2026, 5, 31, 22, 0, tzinfo=timezone.utc)
    assert crr._month_key(dt) == "2026-06"


def test_already_alerted_same_month():
    now = crr._now_kst()
    state = {"last_alerted_at": now.isoformat()}
    assert crr.already_alerted_this_month(state, now=now) is True


def test_already_alerted_prior_month():
    # 35 days ago is definitely a prior month
    now = crr._now_kst()
    old = now - timedelta(days=35)
    state = {"last_alerted_at": old.isoformat()}
    assert crr.already_alerted_this_month(state, now=now) is False


def test_already_alerted_empty_state():
    assert crr.already_alerted_this_month({}, now=crr._now_kst()) is False


def test_already_alerted_garbage_state():
    state = {"last_alerted_at": "not-a-date"}
    assert crr.already_alerted_this_month(state, now=crr._now_kst()) is False


# ── main(): flag true ──────────────────────────────────────────────────────


def test_main_flag_on_skips_everything(monkeypatch, tmp_state, no_slack):
    """``PIVOX_COMMERCE_REGISTERED=true`` → immediate exit 0, no Slack, no state."""
    monkeypatch.setenv("PIVOX_COMMERCE_REGISTERED", "true")
    called = {"slack": False}

    def fake_post(_text):
        called["slack"] = True
        return True

    monkeypatch.setattr(crr, "post_slack", fake_post)
    rc = crr.main()
    assert rc == 0
    assert called["slack"] is False
    assert not tmp_state.exists(), "no state should be written when flag is on"


# ── main(): same-month dedup ───────────────────────────────────────────────


def test_main_dedup_same_month_skips_slack(monkeypatch, tmp_state, no_slack, flag_off):
    """If state.last_alerted_at is in current KST month → no Slack call."""
    now = crr._now_kst()
    tmp_state.parent.mkdir(parents=True, exist_ok=True)
    tmp_state.write_text(json.dumps({"last_alerted_at": now.isoformat()}), encoding="utf-8")

    called = {"slack": False}

    def fake_post(_text):
        called["slack"] = True
        return True

    monkeypatch.setattr(crr, "post_slack", fake_post)
    rc = crr.main()
    assert rc == 0
    assert called["slack"] is False, "dedup must block Slack dispatch"


# ── main(): happy path ─────────────────────────────────────────────────────


def test_main_dispatches_alert_when_flag_off_and_no_prior(
    monkeypatch, tmp_state, no_slack, flag_off
):
    """Flag off + empty state → alert dispatched + state written with last_alerted_at."""
    captured = {}

    def fake_post(text):
        captured["msg"] = text
        return True

    monkeypatch.setattr(crr, "post_slack", fake_post)
    rc = crr.main()
    assert rc == 0
    assert "msg" in captured, "Slack should have been called"
    # Statute + filing portals + Q-S3 reference must all appear in the body.
    msg = captured["msg"]
    assert "전자상거래법" in msg
    assert "§12" in msg
    assert "§44" in msg
    assert "gov.kr" in msg
    assert "ftc.go.kr" in msg
    assert "PIVOX_COMMERCE_REGISTERED=true" in msg
    assert "Q-S3" in msg

    # State must record this run's timestamp.
    state = json.loads(tmp_state.read_text("utf-8"))
    assert "last_alerted_at" in state
    parsed = crr._parse_iso(state["last_alerted_at"])
    assert parsed is not None
    assert state["last_alert_delivered_via"] == "slack"


# ── main(): Slack failure → stdout fallback, no raise ──────────────────────


def test_main_slack_failure_falls_back_stdout(
    monkeypatch, tmp_state, no_slack, flag_off, capsys
):
    """Slack returns False → state still recorded (audit trail), exit 0."""

    def fake_post(_text):
        return False  # webhook unreachable

    monkeypatch.setattr(crr, "post_slack", fake_post)
    rc = crr.main()
    assert rc == 0
    state = json.loads(tmp_state.read_text("utf-8"))
    assert state["last_alert_delivered_via"] == "stdout_fallback"


# ── main(): dedup re-blocks immediate re-run ──────────────────────────────


def test_main_second_run_same_month_is_noop(monkeypatch, tmp_state, no_slack, flag_off):
    """Idempotency: running main() twice in the same minute → 1 alert only."""
    counter = {"n": 0}

    def fake_post(_text):
        counter["n"] += 1
        return True

    monkeypatch.setattr(crr, "post_slack", fake_post)
    crr.main()
    crr.main()
    assert counter["n"] == 1, "second run must hit same-month dedup"


# ── build_alert_message: shape ────────────────────────────────────────────


def test_build_alert_message_contains_required_segments():
    """The alert body is the only place where the legal citation lives.
    A regression that drops §12 / §44 / portal URLs would silently degrade
    the actionability of the alert.
    """
    msg = crr.build_alert_message()
    required = [
        "통신판매업 신고",
        "전자상거래법",
        "§12",
        "§44",
        "정부24",
        "공정거래위원회",
        "https://www.gov.kr",
        "https://www.ftc.go.kr",
        "459-01-03808",
        "PIVOX_COMMERCE_REGISTERED=true",
        "Q-S3",
    ]
    for token in required:
        assert token in msg, f"alert body missing required token: {token!r}"
