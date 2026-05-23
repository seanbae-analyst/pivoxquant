"""Smoke tests for routes/daytrade.py — intraday scan & analyze.

External calls (FMP, Alpaca quotes) are mocked at the daytrade service
boundary. Auth: every endpoint is @api_auth.
"""
from __future__ import annotations

from unittest.mock import patch


class TestDaytradeStatusSmoke:
    def test_unauthenticated_status_returns_401(self, client):
        r = client.get("/api/daytrade/status")
        assert r.status_code == 401

    def test_status_authenticated(self, client, auth_user):
        r = client.get("/api/daytrade/status")
        assert r.status_code == 200
        d = r.get_json()
        assert "available" in d
        assert isinstance(d["available"], bool)


class TestDaytradeScanSmoke:
    def test_unauthenticated_scan_returns_401(self, client):
        r = client.get("/api/daytrade/scan")
        assert r.status_code == 401

    def test_scan_returns_503_when_unconfigured(self, client, auth_user):
        # Contract: when BOTH the US (Alpaca/daytrade) and KR (KIS) scanners
        # are unavailable, /scan returns an explicit 503 rather than an empty
        # 200. Must mock KIS too: the route falls through to a KIS scan when
        # daytrade is down, so if a prior test in the full suite left the KIS
        # singleton "available", the scan returns KR results + 200 and this
        # assertion fails (the original full-suite-only flake).
        with patch("routes.daytrade.daytrade") as mock_dt, \
                patch("services.kis.service.KISService") as MockKIS:
            mock_dt.available = False
            MockKIS.return_value.available = False
            r = client.get("/api/daytrade/scan")
        assert r.status_code == 503
        assert "error" in r.get_json()


class TestDaytradeAnalyzeSmoke:
    def test_unauthenticated_analyze_returns_401(self, client):
        r = client.get("/api/daytrade/analyze/AAPL")
        assert r.status_code == 401


class TestDaytradeChartSmoke:
    def test_unauthenticated_chart_returns_401(self, client):
        r = client.get("/api/daytrade/chart/AAPL")
        assert r.status_code == 401


class TestDaytradePricesSmoke:
    def test_unauthenticated_prices_returns_401(self, client):
        r = client.get("/api/daytrade/prices")
        assert r.status_code == 401
