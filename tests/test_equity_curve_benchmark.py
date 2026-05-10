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

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


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
        self, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="AAPL", shares=10.0, avg_cost=150.0)

        dates = ["2026-05-05", "2026-05-06", "2026-05-07"]
        position_hist = _portfolio_history_df(dates, [150.0, 151.0, 152.0])
        spy_hist      = _spy_history_df(dates, [500.0, 502.0, 504.0])

        def _fmp_get_history(ticker, period="3mo"):
            if ticker == "SPY":
                return spy_hist
            return position_hist

        with patch("services.data.fmp.get_history", side_effect=_fmp_get_history), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        payload = r.get_json()
        data = payload["data"]
        assert len(data) >= 1
        assert all("benchmark" in pt for pt in data), \
            f"benchmark missing on at least one point: {data}"
        # SPY closes are passed through raw — frontend normalises.
        for pt in data:
            assert pt["benchmark"] in (500.0, 502.0, 504.0)

    def test_spy_fetch_failure_omits_benchmark_field(
        self, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="MSFT", shares=5.0, avg_cost=300.0)

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
        self, client, auth_user, add_position
    ):
        # .KS suffix → KR branch
        add_position(auth_user["id"], ticker="005930.KS", shares=10.0,
                     avg_cost=70000.0)

        dates_iso = ["2026-05-05", "2026-05-06", "2026-05-07"]
        dates_kis = ["20260505", "20260506", "20260507"]
        position_hist = _portfolio_history_df(dates_iso, [71000.0, 72000.0, 73000.0])

        kis_svc = MagicMock()
        kis_svc.get_index_history.return_value = _kis_index_rows(
            dates_kis, [380.5, 381.2, 382.0]
        )

        with patch("services.data.fmp.get_history", return_value=position_hist), \
             patch("services.kis.service.KISService", return_value=kis_svc), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        data = r.get_json()["data"]
        # First call should ask for KOSPI 200 (code "2001").
        kis_svc.get_index_history.assert_called_with("2001", period="5d")
        assert len(data) >= 1
        for pt in data:
            assert "benchmark" in pt
            assert pt["benchmark"] in (380.5, 381.2, 382.0)

    def test_kis_2001_empty_falls_back_to_0001(
        self, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="000660.KS", shares=2.0,
                     avg_cost=100000.0)

        dates_iso = ["2026-05-05", "2026-05-06"]
        dates_kis = ["20260505", "20260506"]
        position_hist = _portfolio_history_df(dates_iso, [101000.0, 102000.0])

        kis_svc = MagicMock()
        # 2001 (KOSPI 200) returns empty → 0001 (KOSPI broad) succeeds.
        kis_svc.get_index_history.side_effect = [
            None,
            _kis_index_rows(dates_kis, [2700.1, 2705.5]),
        ]

        with patch("services.data.fmp.get_history", return_value=position_hist), \
             patch("services.kis.service.KISService", return_value=kis_svc), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        data = r.get_json()["data"]
        codes_called = [c.args[0] for c in kis_svc.get_index_history.call_args_list]
        assert codes_called == ["2001", "0001"], \
            f"expected 2001 then 0001 fallback, got {codes_called}"
        # 0001 closes attached.
        for pt in data:
            assert pt["benchmark"] in (2700.1, 2705.5)

    def test_kis_total_failure_omits_benchmark(
        self, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="005930.KS", shares=10.0,
                     avg_cost=70000.0)

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
                     avg_cost=150.0)
        add_position(auth_user["id"], ticker="005930.KS", shares=10.0,
                     avg_cost=70000.0)

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
        self, client, auth_user, add_position
    ):
        add_position(auth_user["id"], ticker="NVDA", shares=2.0, avg_cost=900.0)

        port_dates = ["2026-05-05", "2026-05-06", "2026-05-07"]
        # Benchmark only covers 2 of 3 portfolio days (e.g. KIS holiday).
        bench_dates = ["2026-05-06", "2026-05-07"]

        position_hist = _portfolio_history_df(port_dates,  [900.0, 905.0, 910.0])
        spy_hist      = _spy_history_df(bench_dates, [500.0, 502.0])

        def _fmp_get_history(ticker, period="3mo"):
            return spy_hist if ticker == "SPY" else position_hist

        with patch("services.data.fmp.get_history", side_effect=_fmp_get_history), \
             patch("routes.portfolio.realtime") as rt:
            rt.get_prices_batch.return_value = {}
            r = client.get("/api/portfolio/history?period=5d")

        assert r.status_code == 200
        data = r.get_json()["data"]
        by_date = {pt["date"]: pt for pt in data}
        # The first portfolio day has no benchmark counterpart.
        assert "benchmark" not in by_date["2026-05-05"]
        # Subsequent days do.
        assert by_date["2026-05-06"]["benchmark"] == 500.0
        assert by_date["2026-05-07"]["benchmark"] == 502.0


# ── Backwards compatibility: empty portfolio still works ────────────────────

def test_empty_portfolio_unchanged_response(client, auth_user):
    """No positions → no benchmark logic, identical legacy shape."""
    r = client.get("/api/portfolio/history")
    assert r.status_code == 200
    assert r.get_json() == {"data": []}
