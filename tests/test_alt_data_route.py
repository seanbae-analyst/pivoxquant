"""tests/test_alt_data_route.py — /api/alt-data/* HTTP smoke tests.

Wave 11 (P1 critical path) — alt_data_bp 11 endpoints had zero direct
HTTP tests (only the underlying FRED/SEC service unit tests existed).
We exercise the auth gate, response envelope, and FRED 503 fail-mode.

Strategy:
  - pyKRX endpoints are mocked — pyKRX hits the wire on cold caches and
    we don't want CI flake.
  - FRED endpoints rely on FRED_API_KEY being absent (the conftest pops
    it) so the route returns the documented 503 envelope.
  - SEC EDGAR endpoints are mocked to avoid HTTP.
"""
from __future__ import annotations

from unittest.mock import patch


class TestAltDataMacroSnapshot:
    def test_alt_data_macro_snapshot_503_when_no_fred_key(
        self, client, auth_user, monkeypatch
    ):
        """Without FRED_API_KEY → 503 with FRED_NOT_CONFIGURED code.

        Conftest clears FRED_API_KEY at import time. We additionally pop
        from the live process env to be defensive in case a CI runner
        injects it.
        """
        monkeypatch.delenv("FRED_API_KEY", raising=False)

        # Force the cached service instance to mirror the env state.
        with patch(
            "routes.alt_data.get_fred_service"
        ) as mock_get:
            mock_svc = mock_get.return_value
            mock_svc.available = False
            r = client.get("/api/alt-data/macro/snapshot")

        assert r.status_code == 503, r.get_json()
        body = r.get_json()
        assert body.get("code") == "FRED_NOT_CONFIGURED"


class TestAltDataShortInterest:
    def test_alt_data_short_interest_authenticated(
        self, client, auth_user
    ):
        """Authenticated call returns the standard pyKRX envelope."""
        with patch("routes.alt_data.pykrx_service") as mock_svc:
            mock_svc.get_short_interest.return_value = [
                {"date": "20260501", "short_volume": 1000}
            ]
            mock_svc.get_short_balance_ratio.return_value = {"ratio": 0.012}
            mock_svc.cached_at.return_value = "2026-05-01T00:00:00"

            r = client.get("/api/alt-data/kr/short-interest/005930")

        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body.get("ticker") == "005930"
        assert body.get("source") == "pyKRX"
        assert "data" in body
        assert "series" in body["data"]
        assert "latest_ratio" in body["data"]


class TestAltData13F:
    def test_alt_data_13f_unauthenticated_401(self, raw_client):
        """13F endpoint must require auth — SEC quota is a shared resource."""
        r = raw_client.get("/api/alt-data/us/13f/berkshire")
        assert r.status_code == 401


class TestAltDataForeignFlow:
    def test_alt_data_foreign_flow_response_shape(
        self, client, auth_user
    ):
        """Foreign-flow envelope: ticker + data list + cached_at + source."""
        with patch("routes.alt_data.pykrx_service") as mock_svc:
            mock_svc.get_foreign_flow.return_value = [
                {"date": "20260501", "foreign_net": 100, "inst_net": -50},
            ]
            mock_svc.cached_at.return_value = "2026-05-01T00:00:00"

            r = client.get("/api/alt-data/kr/foreign-flow/005930")

        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        # Required envelope keys.
        for k in ("ticker", "data", "cached_at", "source"):
            assert k in body, f"missing envelope key: {k}"
        assert body["ticker"] == "005930"
        assert body["source"] == "pyKRX"
        assert isinstance(body["data"], list)
