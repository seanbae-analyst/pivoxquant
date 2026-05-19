"""Tests for routes/data_status.py — Wave G C-CS3 in-app stale banner.

Locked schema (frontend depends on these field names):
    is_stale: bool
    stale_ratio: float
    affected_markets: list[str]
    updated_at: str | None
    threshold_pct: float

Graceful-fallback contract: no false alarms when the cron artifact is
missing, empty, or malformed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


_REQUIRED_FIELDS = {
    "is_stale", "stale_ratio", "affected_markets", "updated_at", "threshold_pct",
}


def _hit(client) -> dict:
    r = client.get("/api/data/stale-status")
    assert r.status_code == 200, r.data
    data = r.get_json()
    assert isinstance(data, dict)
    assert _REQUIRED_FIELDS.issubset(data.keys()), (
        f"missing fields: {_REQUIRED_FIELDS - data.keys()}"
    )
    return data


def test_endpoint_returns_200_and_schema(client):
    data = _hit(client)
    assert isinstance(data["is_stale"], bool)
    assert isinstance(data["stale_ratio"], (int, float))
    assert isinstance(data["affected_markets"], list)
    assert isinstance(data["threshold_pct"], (int, float))
    assert data["updated_at"] is None or isinstance(data["updated_at"], str)


def test_missing_artifact_returns_not_stale(client, tmp_path, monkeypatch):
    """Cron hasn't run yet → never false-alarm."""
    monkeypatch.setenv("RESULTS_PATH", str(tmp_path / "does-not-exist.jsonl"))
    data = _hit(client)
    assert data["is_stale"] is False
    assert data["stale_ratio"] == 0.0
    assert data["affected_markets"] == []
    assert data["updated_at"] is None


def test_healthy_artifact_returns_not_stale(client, tmp_path, monkeypatch):
    """All tickers healthy → is_stale=false."""
    artifact = tmp_path / "ticker_health.jsonl"
    rows = [
        {"ticker": "AAPL", "issue": False, "reason": "ok"},
        {"ticker": "MSFT", "issue": False, "reason": "ok"},
        {"ticker": "005930", "issue": False, "reason": "ok"},
        {"ticker": "000660", "issue": False, "reason": "ok"},
    ]
    artifact.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setenv("RESULTS_PATH", str(artifact))

    data = _hit(client)
    assert data["is_stale"] is False
    assert data["affected_markets"] == []
    assert data["stale_ratio"] == 0.0


def test_degraded_kr_market_flags_kr_only(client, tmp_path, monkeypatch):
    """Half of KR stale → KR flagged, US clean."""
    artifact = tmp_path / "ticker_health.jsonl"
    rows = [
        # US — all healthy
        {"ticker": "AAPL", "issue": False, "reason": "ok"},
        {"ticker": "MSFT", "issue": False, "reason": "ok"},
        {"ticker": "GOOGL", "issue": False, "reason": "ok"},
        {"ticker": "AMZN", "issue": False, "reason": "ok"},
        # KR — 50% stale (well over 5% threshold)
        {"ticker": "005930", "issue": True, "reason": "HTTP 500"},
        {"ticker": "000660", "issue": True, "reason": "price=0"},
        {"ticker": "035720", "issue": False, "reason": "ok"},
        {"ticker": "035420", "issue": False, "reason": "ok"},
    ]
    artifact.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setenv("RESULTS_PATH", str(artifact))

    data = _hit(client)
    assert data["is_stale"] is True
    assert "KR" in data["affected_markets"]
    assert "US" not in data["affected_markets"]
    assert data["stale_ratio"] > 0.05


def test_empty_artifact_returns_not_stale(client, tmp_path, monkeypatch):
    """Empty file → graceful fallback, not stale."""
    artifact = tmp_path / "ticker_health.jsonl"
    artifact.write_text("")
    monkeypatch.setenv("RESULTS_PATH", str(artifact))

    data = _hit(client)
    assert data["is_stale"] is False
    assert data["affected_markets"] == []


def test_malformed_jsonl_returns_not_stale(client, tmp_path, monkeypatch):
    """Malformed lines are skipped by ticker_health_alert; endpoint stays calm."""
    artifact = tmp_path / "ticker_health.jsonl"
    artifact.write_text("not-json\n{broken\n")
    monkeypatch.setenv("RESULTS_PATH", str(artifact))

    data = _hit(client)
    assert data["is_stale"] is False
    assert data["stale_ratio"] == 0.0


def test_endpoint_is_public_no_auth_required(client):
    """Banner mounts on landing + (dashboard); must respond without session."""
    r = client.get("/api/data/stale-status")
    assert r.status_code == 200
