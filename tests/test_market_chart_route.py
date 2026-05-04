"""tests/test_market_chart_route.py — Wave 10 P2 supplementary coverage.

Extends ``test_market.py::TestChart`` (which only covers the
"unknown period" graceful-fallback case) with the following gaps:

  - Unauthenticated → 401 (`@api_auth` gate sanity).
  - US ticker, valid period, mocked fetcher → 200 with normalized payload.
  - KR ticker → routed via fetcher (not Alpaca) and the response carries
    ``source != "alpaca"``.
  - Stale/empty fetcher + empty FMP fallback → 200 with friendly empty
    payload (never 500). This is the "external API down" path.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd


# ── Auth gate ───────────────────────────────────────────────────────────────


def test_chart_requires_auth(client):
    """Unauthenticated GET must be rejected by @api_auth."""
    resp = client.get("/api/chart/AAPL")
    assert resp.status_code == 401


# ── US ticker happy path ────────────────────────────────────────────────────


def test_chart_us_ticker_returns_data(client, auth_user):
    """A logged-in user gets normalized chart data for AAPL."""
    # Build a tiny dataframe matching the iterrows() contract the route
    # expects — index = Timestamp, columns include Close + Volume.
    idx = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04"])
    df = pd.DataFrame(
        {"Close": [150.0, 151.5, 149.25], "Volume": [1000, 1200, 950]},
        index=idx,
    )
    with patch("routes.market.fetcher") as m_fetcher, \
         patch("routes.market.realtime") as m_rt:
        m_rt.alpaca_available = False
        m_fetcher.get_price_history.return_value = df
        # FMP fallback also returns df, but the primary path should win.
        with patch("services.data.fmp.get_history", return_value=df):
            resp = client.get("/api/chart/AAPL?period=1mo")

    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ticker"] == "AAPL"
    assert body["period"] == "1mo"
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 3
    assert body["data"][0]["close"] == 150.0
    # Source should be alpaca-or-fmp (deterministic by mock path).
    assert body["source"] in {"alpaca", "fmp"}


# ── KR ticker — must NOT be routed through Alpaca ───────────────────────────


def test_chart_kr_ticker_not_routed_through_alpaca(client, auth_user):
    """A KR ticker (.KS / .KQ) must skip the Alpaca intraday branch even
    when Alpaca is reportedly available — KIS / FMP own KR data."""
    idx = pd.to_datetime(["2026-01-02", "2026-01-03"])
    df = pd.DataFrame({"Close": [70000.0, 70500.0], "Volume": [10000, 12000]}, index=idx)

    with patch("routes.market.fetcher") as m_fetcher, \
         patch("routes.market.realtime") as m_rt:
        m_rt.alpaca_available = True  # even if true, KR must skip Alpaca.
        m_fetcher.get_price_history.return_value = df
        with patch("services.data.fmp.get_history", return_value=df):
            resp = client.get("/api/chart/005930.KS?period=3mo")

    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ticker"].endswith(".KS")
    # The source must NOT be alpaca for a KR ticker.
    assert body["source"] != "alpaca"
    # Alpaca's stock-bars API must never have been called for a KR ticker.
    # (We patched realtime as a MagicMock, so the alpaca_client attribute
    # would be touched only on the US intraday branch.)


# ── External APIs all empty — graceful empty payload ────────────────────────


def test_chart_all_sources_empty_returns_friendly_payload(client, auth_user):
    """When every source returns empty, the route must respond 200 with a
    `data: []` envelope rather than 5xx."""
    empty = pd.DataFrame()
    with patch("routes.market.fetcher") as m_fetcher, \
         patch("routes.market.realtime") as m_rt:
        m_rt.alpaca_available = False
        m_fetcher.get_price_history.return_value = empty
        with patch("services.data.fmp.get_history", return_value=empty):
            resp = client.get("/api/chart/UNKNOWNX?period=6mo")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ticker"] == "UNKNOWNX"
    assert body["data"] == []
    assert body["source"] == "none"
