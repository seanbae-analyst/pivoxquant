"""
tests/test_market.py — Market data routes
============================================
/api/prices, /api/market/status, /api/market/overview, /api/chart/<ticker>,
/api/profile/<ticker>. All upstream APIs (Alpaca, FMP, KIS) are mocked.
"""
import json
from unittest.mock import patch, MagicMock

import pytest


class TestMarketStatus:
    def test_market_status_returns_us_and_kr(self, client):
        r = client.get("/api/market/status")
        assert r.status_code == 200
        d = r.get_json()
        assert "us" in d and "kr" in d
        for region in ("us", "kr"):
            assert d[region]["status"] in (
                "OPEN", "CLOSED", "PRE_MARKET", "AFTER_HOURS",
            )


class TestPrices:
    def test_prices_empty_portfolio(self, client, auth_user):
        r = client.get("/api/prices")
        assert r.status_code == 200
        assert r.get_json()["prices"] == {}

    def test_prices_unauth(self, client):
        r = client.get("/api/prices")
        assert r.status_code == 401


class TestMarketOverview:
    def test_market_overview_uses_mocked_data(self, client, auth_user):
        with patch("routes.market.fetcher") as m:
            m.get_enhanced_macro.return_value = {
                "usdkrw": {"price": 1380.0},
                "spy": {"price": 450.0},
            }
            m.generate_gs_view.return_value = {"regime": "neutral"}
            r = client.get("/api/market/overview")
        assert r.status_code == 200
        d = r.get_json()
        assert "macro" in d
        assert "gs_view" in d


class TestChart:
    def test_chart_invalid_period_falls_back_gracefully(self, client, auth_user):
        """Unknown period → default to 6mo, never crash."""
        import pandas as pd
        with patch("routes.market.fetcher") as m_fetcher, \
             patch("routes.market.realtime") as m_rt:
            m_rt.alpaca_available = False
            m_fetcher.get_price_history.return_value = pd.DataFrame()
            # Also patch fmp_service import inside the function scope.
            with patch("fmp_service.get_history", return_value=pd.DataFrame()):
                r = client.get("/api/chart/AAPL?period=wrongvalue")
        assert r.status_code == 200
        d = r.get_json()
        # Even with empty data, should return a consistent envelope.
        assert d["ticker"] == "AAPL"
        assert "data" in d


class TestProfile:
    def test_company_profile_returns_shape(self, client, auth_user):
        with patch("fmp_service.get_info") as m_info:
            m_info.return_value = {
                "shortName": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "website": "https://apple.com",
                "fullTimeEmployees": 164000,
                "country": "US",
                "marketCap": 3000000000000,
                "longBusinessSummary": "Apple designs phones.",
            }
            r = client.get("/api/profile/AAPL")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ticker"] == "AAPL"
        assert d["name"] == "Apple Inc."
        assert d["currency"] == "USD"

    def test_company_profile_korean_ticker(self, client, auth_user):
        with patch("fmp_service.get_info") as m_info:
            m_info.return_value = {"shortName": "Samsung", "sector": "Tech",
                                    "industry": "Semi", "website": "", "country": "KR",
                                    "marketCap": 0, "longBusinessSummary": ""}
            r = client.get("/api/profile/005930.KS")
        assert r.status_code == 200
        assert r.get_json()["currency"] == "KRW"
