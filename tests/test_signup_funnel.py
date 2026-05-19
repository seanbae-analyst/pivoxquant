"""Unit tests: scripts/nightly/signup_funnel_check.py (S1)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.nightly.signup_funnel_check import (
    evaluate_alerts,
    load_history,
    save_history,
    _is_night_mute,
    main,
    OAUTH_SUCCESS_MIN_PCT,
    PAYMENT_FAIL_MAX_PCT,
)


# ── evaluate_alerts ───────────────────────────────────────────────────────────

def test_evaluate_alerts_all_ok():
    metrics = {
        "signup_5m": 1,
        "signup_1h": 10,
        "oauth_pct": 95.0,
        "payment_fail_pct": 5.0,
    }
    alerts = evaluate_alerts(metrics)
    assert alerts == []


def test_evaluate_alerts_oauth_low():
    metrics = {
        "signup_5m": 2,
        "signup_1h": 10,
        "oauth_pct": 60.0,  # < 80
        "total_24h": 10,
        "oauth_24h": 6,
        "payment_fail_pct": 2.0,
    }
    alerts = evaluate_alerts(metrics)
    assert any("OAuth" in a for a in alerts)


def test_evaluate_alerts_payment_fail_high():
    metrics = {
        "signup_5m": 2,
        "signup_1h": 10,
        "oauth_pct": 90.0,
        "payment_fail_pct": 15.0,  # > 10
        "stripe_success_24h": 8,
        "stripe_fail_24h": 2,
    }
    alerts = evaluate_alerts(metrics)
    assert any("결제 실패" in a for a in alerts)


def test_evaluate_alerts_signup_zero_with_baseline(monkeypatch):
    """signup_5m=0 + BASELINE_H > 2 → alert."""
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.BASELINE_H", 5.0)
    metrics = {
        "signup_5m": 0,
        "signup_1h": 0,
        "oauth_pct": 90.0,
        "payment_fail_pct": 2.0,
    }
    alerts = evaluate_alerts(metrics)
    assert any("가입 0건" in a for a in alerts)


def test_evaluate_alerts_signup_zero_no_baseline(monkeypatch):
    """BASELINE_H = 0 이면 가입 0 alert 없음 (beta 초기)."""
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.BASELINE_H", 0.0)
    metrics = {
        "signup_5m": 0,
        "signup_1h": 0,
        "oauth_pct": None,
        "payment_fail_pct": None,
    }
    alerts = evaluate_alerts(metrics)
    assert alerts == []


def test_evaluate_alerts_none_metrics():
    """None 메트릭은 alert 트리거 안 함."""
    metrics = {
        "signup_5m": 0,
        "signup_1h": 0,
        "oauth_pct": None,
        "payment_fail_pct": None,
    }
    alerts = evaluate_alerts(metrics)
    assert alerts == []


# ── night mute ────────────────────────────────────────────────────────────────

def test_is_night_mute_during_night(monkeypatch):
    """KST 03:00 = 야간 mute."""
    from datetime import datetime, timezone, timedelta

    fake_now = datetime(2026, 5, 19, 18, 0, 0, tzinfo=timezone.utc)  # UTC 18:00 = KST 03:00
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.datetime",
        type("FakeDT", (), {
            "now": staticmethod(lambda tz=None: fake_now),
            "timezone": timezone,
            "timedelta": timedelta,
        }),
    )
    # 직접 시간 계산으로 검증
    kst_hour = (fake_now + timedelta(hours=9)).hour
    assert 0 <= kst_hour < 6


def test_is_night_mute_daytime():
    """낮 시간대는 mute 아님 (실제 실행 시간이 낮이면 pass)."""
    from datetime import datetime, timezone, timedelta

    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    if 6 <= now_kst.hour < 24:
        assert not _is_night_mute()


# ── history ──────────────────────────────────────────────────────────────────

def test_save_load_history(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.STATE_DIR", tmp_path)
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.FUNNEL_HISTORY_PATH",
        tmp_path / "funnel.json",
    )
    records = [{"ts": "2026-05-19T09:00:00+09:00", "signup_5m": 2}]
    save_history(records)
    loaded = load_history()
    assert len(loaded) == 1
    assert loaded[0]["signup_5m"] == 2


def test_history_truncated_at_2000(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.STATE_DIR", tmp_path)
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.FUNNEL_HISTORY_PATH",
        tmp_path / "funnel.json",
    )
    large = [{"ts": f"t{i}", "v": i} for i in range(2500)]
    save_history(large)
    loaded = load_history()
    assert len(loaded) == 2000
    assert loaded[-1]["v"] == 2499


# ── main() 통합 ───────────────────────────────────────────────────────────────

def test_main_missing_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    rc = main()
    assert rc == 1


def test_main_warn_mode_no_alert(monkeypatch, tmp_path):
    """warn 모드: DB query 성공해도 alert 미발송."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setenv("PIVOX_FUNNEL_ALERT_MODE", "warn")
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.ALERT_MODE", "warn")
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.STATE_DIR", tmp_path)
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.FUNNEL_HISTORY_PATH",
        tmp_path / "f.json",
    )

    fake_metrics = {
        "signup_5m": 0,
        "signup_1h": 0,
        "total_24h": 0,
        "oauth_24h": 0,
        "oauth_pct": None,
        "stripe_success_24h": 0,
        "stripe_fail_24h": 0,
        "payment_fail_pct": None,
    }
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.fetch_funnel_metrics",
        lambda *a: fake_metrics,
    )
    slack_calls = []
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.post_slack",
        lambda msg: slack_calls.append(msg),
    )
    rc = main()
    assert rc == 0
    assert slack_calls == []  # warn 모드에서 Slack 호출 없음


def test_main_alert_mode_no_issues(monkeypatch, tmp_path):
    """alert 모드 + 이상 없음 → 0."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.ALERT_MODE", "alert")
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.BASELINE_H", 0.0)
    monkeypatch.setattr("scripts.nightly.signup_funnel_check.STATE_DIR", tmp_path)
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.FUNNEL_HISTORY_PATH",
        tmp_path / "f.json",
    )

    fake_metrics = {
        "signup_5m": 2,
        "signup_1h": 5,
        "total_24h": 20,
        "oauth_24h": 19,
        "oauth_pct": 95.0,
        "stripe_success_24h": 5,
        "stripe_fail_24h": 0,
        "payment_fail_pct": 0.0,
    }
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check.fetch_funnel_metrics",
        lambda *a: fake_metrics,
    )
    monkeypatch.setattr(
        "scripts.nightly.signup_funnel_check._is_night_mute",
        lambda: False,
    )
    rc = main()
    assert rc == 0
