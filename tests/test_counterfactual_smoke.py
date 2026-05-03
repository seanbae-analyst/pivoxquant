"""Smoke tests for routes/counterfactual.py — public 'what-if' simulator.

Public/no-auth endpoint — viral growth hook. Validates query params
strictly and emits 자본시장법-compliant disclaimer payload.

External price-history fetch is intentionally NOT triggered for these
smoke tests; we only exercise the validation paths so no FMP calls fire.
"""
from __future__ import annotations


BASE = "/api/simulate/counterfactual"


class TestCounterfactualValidationSmoke:
    def test_no_params_returns_400_ticker_required(self, client):
        r = client.get(BASE)
        assert r.status_code == 400
        d = r.get_json()
        assert d["error_code"] == "TICKER_REQUIRED"
        # 자본시장법: every response must carry the disclaimer payload.
        assert d["disclaimers"]

    def test_invalid_ticker_format_returns_400(self, client):
        r = client.get(BASE + "?ticker=BAD%20TICKER!&start_date=2020-01-01&amount=100")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "TICKER_NOT_FOUND"

    def test_missing_start_date_returns_400(self, client):
        r = client.get(BASE + "?ticker=AAPL&amount=100")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "DATE_INVALID"

    def test_future_start_date_returns_400(self, client):
        r = client.get(BASE + "?ticker=AAPL&start_date=2999-01-01&amount=100")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "DATE_IN_FUTURE"

    def test_too_old_start_date_returns_400(self, client):
        r = client.get(BASE + "?ticker=AAPL&start_date=1980-01-01&amount=100")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "DATE_TOO_OLD"

    def test_zero_amount_returns_400(self, client):
        r = client.get(BASE + "?ticker=AAPL&start_date=2020-01-01&amount=0")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "AMOUNT_REQUIRED"

    def test_amount_above_cap_returns_400(self, client):
        r = client.get(BASE + "?ticker=AAPL&start_date=2020-01-01&amount=99999999999")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "AMOUNT_OUT_OF_RANGE"

    def test_invalid_recurring_returns_400(self, client):
        r = client.get(BASE +
            "?ticker=AAPL&start_date=2020-01-01&amount=100&recurring=daily")
        assert r.status_code == 400
        assert r.get_json()["error_code"] == "RECURRING_INVALID"
