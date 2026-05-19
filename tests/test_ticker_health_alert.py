"""tests/test_ticker_health_alert.py — KIS stale-rate alert wrapper (O-E).

Verifies:
  - KR vs US classification by ticker shape (6-digit numeric → KR).
  - Threshold logic: under-threshold returns 0, over-threshold returns 1.
  - Slack/Sentry side-effects never raise on missing env / network failure.
  - Missing or malformed artifact returns 0 silently (no false alarm).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.nightly import ticker_health_alert as alert


# ── classification ─────────────────────────────────────────────────────

def test_is_kr_ticker():
    assert alert._is_kr_ticker("005930") is True
    assert alert._is_kr_ticker("000660") is True
    assert alert._is_kr_ticker("AAPL") is False
    assert alert._is_kr_ticker("BRK.B") is False
    assert alert._is_kr_ticker("1234") is False  # too short
    assert alert._is_kr_ticker("12345A") is False


def test_classify_routes_correctly():
    assert alert._classify("005930") == "KR"
    assert alert._classify("AAPL") == "US"


# ── compute_stale_stats ────────────────────────────────────────────────

def _row(ticker: str, issue: bool, reason: str = "ok"):
    return {"ticker": ticker, "issue": issue, "reason": reason}


def test_compute_stale_stats_all_market():
    rows = [
        _row("AAPL", False),
        _row("MSFT", True, "HTTP 500"),
        _row("005930", False),
        _row("000660", True, "price=0"),
    ]
    stats = alert.compute_stale_stats(rows, "ALL")
    assert stats["total"] == 4
    assert stats["stale_count"] == 2
    assert stats["stale_ratio"] == 0.5


def test_compute_stale_stats_kr_only():
    rows = [
        _row("AAPL", True),       # US — excluded
        _row("005930", True, "price missing"),
        _row("000660", False),
        _row("373220", True, "HTTP 500"),
    ]
    stats = alert.compute_stale_stats(rows, "KR")
    assert stats["market"] == "KR"
    assert stats["total"] == 3
    assert stats["stale_count"] == 2
    assert abs(stats["stale_ratio"] - (2 / 3)) < 1e-9


def test_compute_stale_stats_us_only():
    rows = [
        _row("AAPL", False),
        _row("MSFT", True),
        _row("005930", True),  # KR — excluded
    ]
    stats = alert.compute_stale_stats(rows, "US")
    assert stats["market"] == "US"
    assert stats["total"] == 2
    assert stats["stale_count"] == 1


def test_compute_stale_stats_empty():
    stats = alert.compute_stale_stats([], "ALL")
    assert stats["total"] == 0
    assert stats["stale_count"] == 0
    assert stats["stale_ratio"] == 0.0


def test_compute_stale_stats_samples_capped():
    rows = [_row(f"T{i:03}", True, "err") for i in range(20)]
    stats = alert.compute_stale_stats(rows, "ALL")
    assert len(stats["samples"]) == 5
    assert stats["samples"][0]["ticker"] == "T000"


def test_compute_stale_stats_invalid_market():
    with pytest.raises(ValueError):
        alert.compute_stale_stats([], "JP")


# ── artifact I/O ───────────────────────────────────────────────────────

def test_read_artifact_missing_file_returns_empty(tmp_path: Path):
    rows = alert._read_artifact(tmp_path / "nope.jsonl")
    assert rows == []


def test_read_artifact_skips_malformed_lines(tmp_path: Path):
    p = tmp_path / "art.jsonl"
    p.write_text(
        json.dumps({"ticker": "AAPL", "issue": False}) + "\n"
        "not-json\n"
        + json.dumps({"ticker": "005930", "issue": True, "reason": "x"})
        + "\n"
    )
    rows = alert._read_artifact(p)
    assert len(rows) == 2
    assert rows[0]["ticker"] == "AAPL"


# ── main() flow + exit codes ───────────────────────────────────────────

def _write_artifact(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_main_returns_0_when_no_artifact(tmp_path: Path):
    rc = alert.main([
        "--results-path", str(tmp_path / "nope.jsonl"),
        "--dry-run",
    ])
    assert rc == 0


def test_main_returns_0_when_under_threshold(tmp_path: Path):
    art = tmp_path / "art.jsonl"
    _write_artifact(art, [
        _row("AAPL", False),
        _row("MSFT", False),
        _row("005930", True, "transient"),  # 1/3 = 33% — but threshold high
    ])
    rc = alert.main([
        "--results-path", str(art),
        "--threshold-pct", "0.5",  # 50% threshold
        "--dry-run",
    ])
    assert rc == 0


def test_main_returns_1_when_over_threshold(tmp_path: Path):
    art = tmp_path / "art.jsonl"
    _write_artifact(art, [
        _row("AAPL", True, "HTTP 500"),
        _row("MSFT", True, "price=0"),
        _row("005930", False),
        _row("000660", False),
    ])  # 2/4 = 50% stale
    rc = alert.main([
        "--results-path", str(art),
        "--threshold-pct", "0.05",
        "--dry-run",
    ])
    assert rc == 1


def test_main_filters_by_market_kr(tmp_path: Path):
    art = tmp_path / "art.jsonl"
    # US 3/3 stale, KR 0/3 stale → ALL = 50%, KR = 0%
    _write_artifact(art, [
        _row("AAPL", True), _row("MSFT", True), _row("NVDA", True),
        _row("005930", False), _row("000660", False), _row("373220", False),
    ])
    rc_kr = alert.main([
        "--results-path", str(art),
        "--market", "KR",
        "--threshold-pct", "0.05",
        "--dry-run",
    ])
    rc_us = alert.main([
        "--results-path", str(art),
        "--market", "US",
        "--threshold-pct", "0.05",
        "--dry-run",
    ])
    assert rc_kr == 0  # KR clean
    assert rc_us == 1  # US 100% stale


# ── Slack / Sentry side-effect safety ──────────────────────────────────

def test_post_slack_skipped_when_env_unset(monkeypatch, capsys):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    ok = alert._post_slack("hello")
    assert ok is False
    # printed to stderr instead
    captured = capsys.readouterr()
    assert "hello" in captured.err


def test_post_slack_returns_false_on_network_error(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    with patch("requests.post", side_effect=RuntimeError("network down")):
        ok = alert._post_slack("hi")
    assert ok is False


def test_post_slack_success(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    with patch("requests.post") as mp:
        mp.return_value.raise_for_status = lambda: None
        ok = alert._post_slack("hi")
    assert ok is True
    assert mp.call_count == 1


def test_main_posts_slack_when_over_threshold_and_env_set(
    tmp_path, monkeypatch,
):
    art = tmp_path / "art.jsonl"
    _write_artifact(art, [
        _row("AAPL", True), _row("MSFT", True),
        _row("NVDA", False), _row("GOOGL", False),
    ])  # 50% stale
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    with patch("requests.post") as mp:
        mp.return_value.raise_for_status = lambda: None
        rc = alert.main([
            "--results-path", str(art),
            "--threshold-pct", "0.05",
        ])
    assert rc == 1
    assert mp.call_count == 1
    text = mp.call_args.kwargs["json"]["text"]
    assert "stale" in text.lower() or "임계치" in text


def test_format_alert_includes_samples():
    stats = {
        "market": "KR", "total": 4, "stale_count": 2,
        "stale_ratio": 0.5,
        "samples": [
            {"ticker": "005930", "reason": "HTTP 500"},
            {"ticker": "000660", "reason": "price=0"},
        ],
    }
    msg = alert._format_alert(stats, 0.05)
    assert "005930" in msg
    assert "HTTP 500" in msg
    assert "50.0%" in msg
