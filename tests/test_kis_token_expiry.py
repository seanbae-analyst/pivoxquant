"""tests/test_kis_token_expiry.py — KIS token expiry alert (O-N).

Verifies:
  - ``evaluate()`` decision boundary (within window → alert, outside → no).
  - ``read_token_expiry()`` parses both plaintext-legacy and AES-GCM
    cache formats (the latter through services.crypto_service).
  - main() respects --dry-run, --force, and the dedup state file.
  - Graceful skip when KIS_* env unset or cache absent.
  - Slack post never raises on network failure.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.nightly import kis_token_expiry_check as ek


# ── evaluate() pure decision ───────────────────────────────────────────

def _now():
    return datetime(2026, 5, 19, tzinfo=timezone.utc)


def test_evaluate_no_expiry_no_alert():
    d = ek.evaluate(None, window_days=7, now=_now())
    assert d == {"should_alert": False, "days_left": None, "expires": None}


def test_evaluate_within_window_alerts():
    expires = _now() + timedelta(days=3)
    d = ek.evaluate(expires, window_days=7, now=_now())
    assert d["should_alert"] is True
    assert abs(d["days_left"] - 3.0) < 0.01


def test_evaluate_outside_window_no_alert():
    expires = _now() + timedelta(days=14)
    d = ek.evaluate(expires, window_days=7, now=_now())
    assert d["should_alert"] is False
    assert d["days_left"] > 7


def test_evaluate_already_expired_alerts():
    expires = _now() - timedelta(hours=2)
    d = ek.evaluate(expires, window_days=7, now=_now())
    assert d["should_alert"] is True
    assert d["days_left"] < 0


def test_evaluate_boundary_exact_window():
    expires = _now() + timedelta(days=7)
    d = ek.evaluate(expires, window_days=7, now=_now())
    # ≤ window → alert
    assert d["should_alert"] is True


# ── read_token_expiry: plaintext legacy ────────────────────────────────

def test_read_token_expiry_plaintext_cache(tmp_path: Path):
    cache = tmp_path / "cache.json"
    expires = "2026-12-25T12:00:00+00:00"
    cache.write_text(json.dumps({
        "token": "tok-xyz",
        "expires": expires,
    }))
    got = ek.read_token_expiry(cache)
    assert got is not None
    assert got.isoformat() == expires


def test_read_token_expiry_naive_timestamp_promoted_to_utc(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "token": "tok-xyz",
        "expires": "2026-12-25T12:00:00",  # naive
    }))
    got = ek.read_token_expiry(cache)
    assert got is not None
    assert got.tzinfo is not None
    assert got.utcoffset().total_seconds() == 0


def test_read_token_expiry_missing_file(tmp_path: Path):
    got = ek.read_token_expiry(tmp_path / "nope.json")
    assert got is None


def test_read_token_expiry_empty_file(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_bytes(b"")
    got = ek.read_token_expiry(cache)
    assert got is None


def test_read_token_expiry_no_expires_key(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"token": "tok"}))
    got = ek.read_token_expiry(cache)
    assert got is None


# ── read_token_expiry: AES-GCM ciphertext path ─────────────────────────

def test_read_token_expiry_aes_gcm_cache(tmp_path: Path, monkeypatch):
    """Encrypt with the real crypto_service and decrypt via the helper."""
    # crypto_service requires PIVOX_BROKER_ENCRYPTION_KEY in env.
    # Use a deterministic test key (32 raw bytes → base64).
    import base64 as _b64
    test_key = _b64.b64encode(b"\x01" * 32).decode("ascii")
    monkeypatch.setenv("PIVOX_BROKER_ENCRYPTION_KEY", test_key)

    from services.crypto_service import encrypt as _encrypt

    cache_path = tmp_path / "cache.json"
    payload = json.dumps({
        "token": "tok-ciphertext",
        "expires": "2026-08-15T09:00:00+00:00",
    })
    ct_b64 = _encrypt(payload, aad=ek._CACHE_AAD)
    cache_path.write_bytes(ek._CACHE_HEADER + ct_b64.encode("ascii"))

    got = ek.read_token_expiry(cache_path)
    assert got is not None
    assert got.isoformat() == "2026-08-15T09:00:00+00:00"


def test_read_token_expiry_corrupted_ciphertext_returns_none(
    tmp_path: Path, monkeypatch,
):
    import base64 as _b64
    monkeypatch.setenv(
        "PIVOX_BROKER_ENCRYPTION_KEY", _b64.b64encode(b"\x01" * 32).decode(),
    )
    cache = tmp_path / "cache.json"
    cache.write_bytes(ek._CACHE_HEADER + b"not-valid-base64!!!")
    got = ek.read_token_expiry(cache)
    assert got is None


# ── main() flow ────────────────────────────────────────────────────────

def _write_plaintext_cache(path: Path, expires: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "token": "tok",
        "expires": expires.isoformat(),
    }))


def test_main_skips_when_no_kis_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    rc = ek.main(["--cache-path", str(tmp_path / "x.json")])
    assert rc == 0


def test_main_skips_when_cache_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    rc = ek.main([
        "--cache-path", str(tmp_path / "absent.json"),
        "--state-path", str(tmp_path / "state.json"),
    ])
    assert rc == 0


def test_main_no_alert_when_outside_window(monkeypatch, tmp_path):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    cache = tmp_path / "cache.json"
    _write_plaintext_cache(
        cache, datetime.now(timezone.utc) + timedelta(days=30),
    )
    rc = ek.main([
        "--cache-path", str(cache),
        "--state-path", str(tmp_path / "state.json"),
        "--window-days", "7",
    ])
    assert rc == 0


def test_main_dry_run_alerts_within_window(monkeypatch, tmp_path):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    cache = tmp_path / "cache.json"
    _write_plaintext_cache(
        cache, datetime.now(timezone.utc) + timedelta(days=3),
    )
    rc = ek.main([
        "--cache-path", str(cache),
        "--state-path", str(tmp_path / "state.json"),
        "--dry-run",
    ])
    assert rc == 1  # alert would fire


def test_main_posts_slack_and_writes_state(monkeypatch, tmp_path):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")

    cache = tmp_path / "cache.json"
    expires = datetime.now(timezone.utc) + timedelta(days=2)
    _write_plaintext_cache(cache, expires)
    state_path = tmp_path / "state.json"

    with patch("requests.post") as mp:
        mp.return_value.raise_for_status = lambda: None
        rc = ek.main([
            "--cache-path", str(cache),
            "--state-path", str(state_path),
        ])
    assert rc == 1
    assert mp.call_count == 1
    text = mp.call_args.kwargs["json"]["text"]
    assert "KIS" in text
    # State recorded so re-run dedupes.
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert expires.isoformat() in state


def test_main_dedupes_repeat_alerts(monkeypatch, tmp_path):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")

    cache = tmp_path / "cache.json"
    expires = datetime.now(timezone.utc) + timedelta(days=2)
    _write_plaintext_cache(cache, expires)
    state_path = tmp_path / "state.json"
    # Pre-populate state file with this exact expiry → second run no-op.
    state_path.write_text(json.dumps({
        expires.isoformat(): "2026-05-18T00:00:00+00:00",
    }))

    with patch("requests.post") as mp:
        rc = ek.main([
            "--cache-path", str(cache),
            "--state-path", str(state_path),
        ])
    # Dedupe path → exit 0, Slack NOT called
    assert rc == 0
    assert mp.call_count == 0


def test_main_force_bypasses_dedupe(monkeypatch, tmp_path):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")

    cache = tmp_path / "cache.json"
    expires = datetime.now(timezone.utc) + timedelta(days=2)
    _write_plaintext_cache(cache, expires)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({expires.isoformat(): "older"}))

    with patch("requests.post") as mp:
        mp.return_value.raise_for_status = lambda: None
        rc = ek.main([
            "--cache-path", str(cache),
            "--state-path", str(state_path),
            "--force",
        ])
    assert rc == 1
    assert mp.call_count == 1


def test_main_slack_network_failure_swallowed(monkeypatch, tmp_path):
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")

    cache = tmp_path / "cache.json"
    _write_plaintext_cache(
        cache, datetime.now(timezone.utc) + timedelta(days=2),
    )
    state_path = tmp_path / "state.json"
    with patch("requests.post", side_effect=RuntimeError("network down")):
        rc = ek.main([
            "--cache-path", str(cache),
            "--state-path", str(state_path),
        ])
    # Still rc=1 (alert was attempted) but no exception propagates.
    assert rc == 1


# ── format_alert messaging tiers ───────────────────────────────────────

def test_format_alert_expired():
    msg = ek._format_alert(-0.5, "2026-05-18T00:00:00+00:00")
    assert "이미 만료" in msg


def test_format_alert_within_24h():
    msg = ek._format_alert(0.5, "2026-05-19T12:00:00+00:00")
    assert "24시간 이내" in msg


def test_format_alert_within_3d():
    msg = ek._format_alert(2.0, "2026-05-21T00:00:00+00:00")
    assert "3일 이내" in msg


def test_format_alert_within_7d():
    msg = ek._format_alert(5.5, "2026-05-24T12:00:00+00:00")
    assert "D-7" in msg
