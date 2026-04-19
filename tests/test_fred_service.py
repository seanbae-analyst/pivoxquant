"""
FRED service tests
==================
Covers:
  - Graceful degradation when FRED_API_KEY is unset
  - Series fetch with mocked HTTP
  - Latest-value delta math
  - Snapshot aggregation across all FRED_SERIES
  - Regime detection (yield-curve inversion, elevated VIX)
  - Memory TTL cache hit/miss
  - Routes return 503 when key missing (unit smoke)

All external HTTP is mocked — these tests never touch the live FRED API.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from services.data.fred_service import (
    FRED_SERIES,
    FREDService,
)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _mock_fred_response(observations):
    """Build a MagicMock that mimics requests.get(...).json() → {'observations': [...]}."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"observations": observations}
    return resp


# ─── basic: no API key = disabled ────────────────────────────────────────────

def test_service_disabled_without_api_key(monkeypatch):
    """FRED_API_KEY unset → service.available == False, all methods return falsy."""
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    svc = FREDService(api_key=None)

    assert svc.available is False
    assert svc.get_series("DGS10") == {}
    assert svc.get_latest("DGS10") == {}

    snap = svc.get_macro_snapshot()
    assert snap["available"] is False
    assert snap["indicators"] == {}
    assert "reason" in snap

    regime = svc.detect_regime()
    assert regime["available"] is False
    assert regime["regime"] == "unknown"
    assert regime["signals"] == {}


def test_explicit_api_key_enables_service():
    """Passing api_key= to the ctor overrides env and enables the service."""
    svc = FREDService(api_key="TEST_KEY_123")
    assert svc.available is True
    assert svc.api_key == "TEST_KEY_123"


# ─── get_series with mocked HTTP ─────────────────────────────────────────────

def test_get_series_parses_and_sorts(monkeypatch):
    svc = FREDService(api_key="TEST_KEY")

    raw = [
        {"date": "2026-04-17", "value": "4.35"},
        {"date": "2026-04-16", "value": "4.31"},
        {"date": "2026-04-15", "value": "."},       # non-numeric sentinel
        {"date": "2026-04-14", "value": "4.25"},
    ]
    with patch("services.data.fred_service.requests.get",
               return_value=_mock_fred_response(raw)):
        out = svc.get_series("DGS10", limit=10)

    assert out["series_id"] == "DGS10"
    assert out["label"] == FRED_SERIES["DGS10"]["label"]
    # "." observation should be skipped; remaining ascending by date
    dates = [o["date"] for o in out["observations"]]
    values = [o["value"] for o in out["observations"]]
    assert dates == ["2026-04-14", "2026-04-16", "2026-04-17"]
    assert values == [4.25, 4.31, 4.35]
    assert out["count"] == 3


def test_get_series_returns_empty_on_http_error():
    svc = FREDService(api_key="TEST_KEY")
    import requests as _rq
    err = _rq.RequestException("boom")
    with patch("services.data.fred_service.requests.get", side_effect=err):
        out = svc.get_series("DGS10")
    assert out == {}


# ─── get_latest: change + pct_change math ────────────────────────────────────

def test_get_latest_computes_delta():
    svc = FREDService(api_key="TEST_KEY")
    raw = [
        {"date": "2026-04-17", "value": "4.40"},
        {"date": "2026-04-16", "value": "4.00"},
    ]
    with patch("services.data.fred_service.requests.get",
               return_value=_mock_fred_response(raw)):
        latest = svc.get_latest("DGS10")

    assert latest["value"] == 4.40
    assert latest["prev_value"] == 4.00
    assert latest["change"] == pytest.approx(0.40)
    assert latest["pct_change"] == pytest.approx(10.0)


# ─── snapshot: fans out across catalog ───────────────────────────────────────

def test_snapshot_covers_all_catalog_ids():
    svc = FREDService(api_key="TEST_KEY")
    raw = [
        {"date": "2026-04-17", "value": "1.0"},
        {"date": "2026-04-16", "value": "0.5"},
    ]
    with patch("services.data.fred_service.requests.get",
               return_value=_mock_fred_response(raw)):
        snap = svc.get_macro_snapshot()

    assert snap["available"] is True
    # Every catalog id should resolve (mocked HTTP returns same payload)
    assert set(snap["indicators"].keys()) == set(FRED_SERIES.keys())
    assert snap["count"] == len(FRED_SERIES)


# ─── regime detection ────────────────────────────────────────────────────────

def test_regime_recession_on_inversion_plus_vix():
    """T10Y2Y < 0 AND VIX > 25 → regime == 'recession' or 'stress'.

    (Our classifier promotes to 'recession' only when inversion combines with
    VIX elevation *or* rising unemployment; here we include VIX elevation.)
    """
    svc = FREDService(api_key="TEST_KEY")

    def fake_get(url, params=None, timeout=None):
        sid = params["series_id"]
        if sid == "T10Y2Y":
            return _mock_fred_response([
                {"date": "2026-04-17", "value": "-0.25"},
                {"date": "2026-04-16", "value": "-0.20"},
            ])
        if sid == "VIXCLS":
            return _mock_fred_response([
                {"date": "2026-04-17", "value": "32.5"},
                {"date": "2026-04-16", "value": "28.0"},
            ])
        if sid == "UNRATE":
            return _mock_fred_response([
                {"date": "2026-03-01", "value": "4.2"},
                {"date": "2026-02-01", "value": "4.1"},
            ])
        if sid == "FEDFUNDS":
            return _mock_fred_response([
                {"date": "2026-03-01", "value": "5.25"},
            ])
        return _mock_fred_response([
            {"date": "2026-04-17", "value": "1.0"},
        ])

    with patch("services.data.fred_service.requests.get", side_effect=fake_get):
        regime = svc.detect_regime()

    assert regime["available"] is True
    assert regime["regime"] == "recession"
    assert "yield_curve_inverted" in regime["flags"]
    assert "vix_elevated" in regime["flags"]
    assert regime["signals"]["t10y2y"] == -0.25
    assert regime["signals"]["vix"] == 32.5


def test_regime_expansion_when_signals_normal():
    svc = FREDService(api_key="TEST_KEY")

    def fake_get(url, params=None, timeout=None):
        sid = params["series_id"]
        if sid == "T10Y2Y":
            return _mock_fred_response([
                {"date": "2026-04-17", "value": "0.85"},   # positive curve
                {"date": "2026-04-16", "value": "0.80"},
            ])
        if sid == "VIXCLS":
            return _mock_fred_response([
                {"date": "2026-04-17", "value": "15.0"},   # calm
                {"date": "2026-04-16", "value": "14.5"},
            ])
        if sid == "UNRATE":
            return _mock_fred_response([
                {"date": "2026-03-01", "value": "3.8"},
                {"date": "2026-02-01", "value": "3.8"},    # no change
            ])
        return _mock_fred_response([{"date": "2026-04-17", "value": "1.0"}])

    with patch("services.data.fred_service.requests.get", side_effect=fake_get):
        regime = svc.detect_regime()

    assert regime["regime"] == "expansion"
    assert "yield_curve_inverted" not in regime["flags"]
    assert "vix_elevated" not in regime["flags"]


# ─── cache behaviour ─────────────────────────────────────────────────────────

def test_cache_avoids_second_http_call():
    svc = FREDService(api_key="TEST_KEY")
    raw = [{"date": "2026-04-17", "value": "4.35"},
           {"date": "2026-04-16", "value": "4.30"}]
    with patch("services.data.fred_service.requests.get",
               return_value=_mock_fred_response(raw)) as mock_get:
        a = svc.get_series("DGS10", limit=10)
        b = svc.get_series("DGS10", limit=10)
    assert a == b
    assert mock_get.call_count == 1  # second call served from cache


def test_cache_expiry(monkeypatch):
    svc = FREDService(api_key="TEST_KEY", cache_ttl=1)
    raw = [{"date": "2026-04-17", "value": "4.35"},
           {"date": "2026-04-16", "value": "4.30"}]
    with patch("services.data.fred_service.requests.get",
               return_value=_mock_fred_response(raw)) as mock_get:
        svc.get_series("DGS10", limit=10)
        # fast-forward time
        import services.data.fred_service as fs
        real_time = fs.time.time
        monkeypatch.setattr(fs.time, "time", lambda: real_time() + 10)
        svc.get_series("DGS10", limit=10)
    assert mock_get.call_count == 2


# ─── route-level smoke: 503 when key missing ─────────────────────────────────
# These tests confirm the three new endpoints are registered and return the
# expected 503 payload when FRED_API_KEY is unset (which is the baseline in
# conftest — it strips known external keys from the test env).

def test_route_macro_snapshot_returns_503_without_key(client, auth_user):
    # Force a fresh singleton sans key, in case some other test cached one.
    import services.data.fred_service as fs
    fs._default_service = None
    os.environ.pop("FRED_API_KEY", None)

    resp = client.get("/api/alt-data/macro/snapshot")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["code"] == "FRED_NOT_CONFIGURED"


def test_route_macro_regime_returns_503_without_key(client, auth_user):
    import services.data.fred_service as fs
    fs._default_service = None
    os.environ.pop("FRED_API_KEY", None)

    resp = client.get("/api/alt-data/macro/regime")
    assert resp.status_code == 503
    assert resp.get_json()["code"] == "FRED_NOT_CONFIGURED"


def test_route_macro_series_returns_503_without_key(client, auth_user):
    import services.data.fred_service as fs
    fs._default_service = None
    os.environ.pop("FRED_API_KEY", None)

    resp = client.get("/api/alt-data/macro/series/DGS10")
    assert resp.status_code == 503
    assert resp.get_json()["code"] == "FRED_NOT_CONFIGURED"


def test_route_macro_catalog_is_public_to_authed_users(client, auth_user):
    """Catalog is static metadata — should work even without FRED_API_KEY."""
    resp = client.get("/api/alt-data/macro/catalog")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    ids = [entry["series_id"] for entry in body["series"]]
    assert set(ids) == set(FRED_SERIES.keys())
