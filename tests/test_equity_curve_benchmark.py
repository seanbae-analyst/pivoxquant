"""
tests/test_equity_curve_benchmark.py — EQUITY CURVE benchmark overlay
======================================================================
Regression suite for the benchmark field added to /api/portfolio/history
in fix/equity-curve-benchmark.

Frontend contract (frontend/src/components/portfolio/v2/hooks-v2.ts):
    interface EquityPoint { t: string; nav: number; benchmark?: number }
The backend emits each point as ``{date, value, benchmark?}`` — frontend
maps date→t / value→nav and reads `benchmark` when present.

Coverage:
  * US portfolio → SPY benchmark via FMP, field present on points
  * KR portfolio → KOSPI 200 (KIS code "2001") benchmark, field present
  * KIS 2001 fail → 0001 (KOSPI broad) graceful fallback
  * Both benchmark sources fail → benchmark field omitted (기능 100% 보존)
  * Mixed portfolio counts as KR (any .KS/.KQ → KR branch)
  * Non-overlapping benchmark dates → some points keep no benchmark

External APIs are mocked — no network calls (per conftest policy).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from extensions import db
from models import PortfolioNavSnapshot


# ── MARKET_DATA_DISPLAY_ENABLED ──────────────────────────────────────────────
# MARKET_DATA_DISPLAY_ENABLED defaults to OFF (config.py — FMP Data Display
# Agreement pending). These assertions are about the ON behaviour, so they opt
# in explicitly; the OFF contract lives in tests/test_market_data_display_flag.py.
@pytest.fixture(autouse=True)
def _market_display_on(market_display_on):
    yield


# Positions are opened far in the past so the position itself is never the
# limiting factor. The equity curve no longer reconstructs from holdings — it
# plots REAL recorded NAV (PortfolioNavSnapshot). So benchmark tests seed real
# snapshots on RECENT dates (within the period window) and assert the benchmark
# overlay attaches to those real curve dates.
_OPENED = datetime(2000, 1, 1)


def _seed_snapshots(app, user_id, dated_values):
    """Insert real NAV snapshots. ``dated_values``: list[(date, nav_usd)]."""
    with app.app_context():
        for d, v in dated_values:
            db.session.add(PortfolioNavSnapshot(
                user_id=user_id, as_of_date=d,
                nav_total_usd=v, nav_us_usd=v, nav_kr_krw=0, fx_rate=1300,
            ))
        db.session.commit()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _spy_history_df(dates: list[str], closes: list[float]) -> pd.DataFrame:
    """Build a DataFrame matching fmp.get_history() output shape."""
    df = pd.DataFrame({
        "Open":  closes,
        "High":  closes,
        "Low":   closes,
        "Close": closes,
        "Volume": [1_000_000] * len(closes),
    })
    df.index = pd.to_datetime(dates)
    df.index.name = "Date"
    return df


def _kis_index_rows(dates_yyyymmdd: list[str], closes: list[float]) -> list[dict]:
    """Build KISService.get_index_history() output shape."""
    return [
        {"date": d, "open": c, "high": c, "low": c, "close": c, "volume": 0}
        for d, c in zip(dates_yyyymmdd, closes)
    ]


def _portfolio_history_df(dates: list[str], closes: list[float]) -> pd.DataFrame:
    """Position-level history shape consumed by routes.portfolio.portfolio_history."""
    df = pd.DataFrame({
        "Open":  closes,
        "High":  closes,
        "Low":   closes,
        "Close": closes,
        "Volume": [100] * len(closes),
    })
    df.index = pd.to_datetime(dates)
    df.index.name = "Date"
    return df


# ── US portfolio → SPY benchmark ────────────────────────────────────────────

class TestUsPortfolioBenchmark:
    def test_spy_benchmark_attached_to_each_point(
        self, app, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="AAPL", shares=10.0, avg_cost=150.0, added_at=_OPENED)

        d2, d1 = date.today() - timedelta(days=2), date.today() - timedelta(days=1)
        _seed_snapshots(app, auth_user["id"], [(d2, 1500.0), (d1, 1510.0)])
        spy_hist = _spy_history_df([d2.isoformat(), d1.isoformat()], [500.0, 502.0])

        def _fmp_get_history(ticker, period="3mo"):
            # Curve no longer uses position history — only the SPY benchmark.
            return spy_hist if ticker == "SPY" else None

        with patch("services.data.fmp.get_history", side_effect=_fmp_get_history), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        by_date = {pt["date"]: pt for pt in r.get_json()["data"]}
        # Benchmark attaches to the REAL recorded snapshot dates (raw closes —
        # frontend normalises).
        assert by_date[d2.isoformat()]["benchmark"] == 500.0
        assert by_date[d1.isoformat()]["benchmark"] == 502.0

    def test_spy_fetch_failure_omits_benchmark_field(
        self, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="MSFT", shares=5.0, avg_cost=300.0, added_at=_OPENED)

        dates = ["2026-05-05", "2026-05-06"]
        position_hist = _portfolio_history_df(dates, [300.0, 301.0])

        def _fmp_get_history(ticker, period="3mo"):
            if ticker == "SPY":
                # Empty frame — simulates 402 / network miss.
                return pd.DataFrame()
            return position_hist

        with patch("services.data.fmp.get_history", side_effect=_fmp_get_history), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        data = r.get_json()["data"]
        assert len(data) >= 1
        # 메모리 룰 [기능 100% 보존]: bench 실패 시 기존 응답 그대로.
        for pt in data:
            assert "benchmark" not in pt
            assert "date"  in pt
            assert "value" in pt


# ── KR portfolio → KOSPI 200 benchmark ──────────────────────────────────────

class TestKrPortfolioBenchmark:
    def test_kospi200_benchmark_attached_for_kr_portfolio(
        self, app, client, auth_user, add_position
    ):
        # .KS suffix → KR branch
        add_position(auth_user["id"], ticker="005930.KS", shares=10.0,
                     avg_cost=70000.0, added_at=_OPENED)

        d2, d1 = date.today() - timedelta(days=2), date.today() - timedelta(days=1)
        _seed_snapshots(app, auth_user["id"], [(d2, 800.0), (d1, 810.0)])
        dates_kis = [d2.strftime("%Y%m%d"), d1.strftime("%Y%m%d")]

        kis_svc = MagicMock()
        kis_svc.get_index_history.return_value = _kis_index_rows(
            dates_kis, [380.5, 381.2]
        )

        with patch("services.data.fmp.get_history", return_value=None), \
             patch("services.kis.service.KISService", return_value=kis_svc), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        by_date = {pt["date"]: pt for pt in r.get_json()["data"]}
        # First call should ask for KOSPI 200 (code "2001").
        kis_svc.get_index_history.assert_called_with("2001", period="5d")
        assert by_date[d2.isoformat()]["benchmark"] == 380.5
        assert by_date[d1.isoformat()]["benchmark"] == 381.2

    def test_kis_2001_empty_falls_back_to_0001(
        self, app, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="000660.KS", shares=2.0,
                     avg_cost=100000.0, added_at=_OPENED)

        d2, d1 = date.today() - timedelta(days=2), date.today() - timedelta(days=1)
        _seed_snapshots(app, auth_user["id"], [(d2, 200.0), (d1, 205.0)])
        dates_kis = [d2.strftime("%Y%m%d"), d1.strftime("%Y%m%d")]

        kis_svc = MagicMock()
        # 2001 (KOSPI 200) returns empty → 0001 (KOSPI broad) succeeds.
        kis_svc.get_index_history.side_effect = [
            None,
            _kis_index_rows(dates_kis, [2700.1, 2705.5]),
        ]

        with patch("services.data.fmp.get_history", return_value=None), \
             patch("services.kis.service.KISService", return_value=kis_svc), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        by_date = {pt["date"]: pt for pt in r.get_json()["data"]}
        codes_called = [c.args[0] for c in kis_svc.get_index_history.call_args_list]
        assert codes_called == ["2001", "0001"], \
            f"expected 2001 then 0001 fallback, got {codes_called}"
        # 0001 closes attached to the real snapshot dates.
        assert by_date[d2.isoformat()]["benchmark"] in (2700.1, 2705.5)
        assert by_date[d1.isoformat()]["benchmark"] in (2700.1, 2705.5)

    def test_kis_total_failure_omits_benchmark(
        self, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="005930.KS", shares=10.0,
                     avg_cost=70000.0, added_at=_OPENED)

        dates_iso = ["2026-05-05", "2026-05-06"]
        position_hist = _portfolio_history_df(dates_iso, [71000.0, 72000.0])

        kis_svc = MagicMock()
        kis_svc.get_index_history.return_value = None  # both 2001 + 0001 fail

        with patch("services.data.fmp.get_history", return_value=position_hist), \
             patch("services.kis.service.KISService", return_value=kis_svc), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        data = r.get_json()["data"]
        for pt in data:
            assert "benchmark" not in pt

    def test_mixed_portfolio_routes_to_kr_branch(
        self, client, auth_user, add_position
    ):
        # Mixed US + KR portfolio → any .KS triggers KR branch
        # (FMP doesn't cover KRX so currency-weighted blend not viable
        # without additional FX work; KOSPI is the safer single-bench
        # for any KR exposure).
        add_position(auth_user["id"], ticker="AAPL",      shares=5.0,
                     avg_cost=150.0, added_at=_OPENED)
        add_position(auth_user["id"], ticker="005930.KS", shares=10.0,
                     avg_cost=70000.0, added_at=_OPENED)

        dates_iso = ["2026-05-05", "2026-05-06"]
        dates_kis = ["20260505", "20260506"]
        position_hist = _portfolio_history_df(dates_iso, [150.0, 151.0])

        kis_svc = MagicMock()
        kis_svc.get_index_history.return_value = _kis_index_rows(
            dates_kis, [380.0, 381.0]
        )

        with patch("services.data.fmp.get_history", return_value=position_hist), \
             patch("services.kis.service.KISService", return_value=kis_svc), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        # KIS path must be exercised (not SPY).
        kis_svc.get_index_history.assert_called()


# ── Non-overlapping dates ───────────────────────────────────────────────────

class TestBenchmarkDateAlignment:
    def test_partial_overlap_only_matched_points_get_benchmark(
        self, app, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="NVDA", shares=2.0, avg_cost=900.0, added_at=_OPENED)

        d3, d2, d1 = (date.today() - timedelta(days=n) for n in (3, 2, 1))
        # Three real snapshot days; benchmark only covers 2 (e.g. data holiday).
        _seed_snapshots(app, auth_user["id"], [(d3, 900.0), (d2, 905.0), (d1, 910.0)])
        spy_hist = _spy_history_df([d2.isoformat(), d1.isoformat()], [500.0, 502.0])

        def _fmp_get_history(ticker, period="3mo"):
            return spy_hist if ticker == "SPY" else None

        with patch("services.data.fmp.get_history", side_effect=_fmp_get_history), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        by_date = {pt["date"]: pt for pt in r.get_json()["data"]}
        # The earliest snapshot day has no benchmark counterpart.
        assert "benchmark" not in by_date[d3.isoformat()]
        # The overlapping days do.
        assert by_date[d2.isoformat()]["benchmark"] == 500.0
        assert by_date[d1.isoformat()]["benchmark"] == 502.0


# ── Backwards compatibility: empty portfolio still works ────────────────────

def test_empty_portfolio_unchanged_response(client, auth_user):
    """No positions → no benchmark logic, identical legacy shape.

    ``market_data_display`` is the one added key (true here, since this module
    opts into display-on); ``benchmark`` must still be absent.
    """
    r = client.get("/api/portfolio/history")
    assert r.status_code == 200
    assert r.get_json() == {"data": [], "market_data_display": True}
