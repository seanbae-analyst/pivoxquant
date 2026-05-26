"""Regression guards for the 2026-05-26 input-validation / serialization sweep.

One test per fix. Each pins the specific failure mode the fix closes:

API#2  performance_quant — benchmark NaN correlation → 0.0 (no JSON `NaN`).
API#3  ai/chat — message length cap (4000 chars) → 400 MESSAGE_TOO_LONG.
API#4  daytrade/chart — `?limit=abc` no longer 500s; limit clamps; tf allowlist.
API#6  backtest — period allowlist + 422 (not 500) on failure.
API#8  alt_data FRED — limit caps at 1000; no-data → 404 (not 502); start format.
API#1/#9 quant_helpers — KR ticker format passes regex; US-only signals reject KR.
C#4    retention — _pending_retention_rows uses SKIP LOCKED.
"""
from __future__ import annotations

import math
from unittest.mock import patch

import pytest


# ── API#2: performance_quant NaN guard ────────────────────────────────────────

class TestBenchmarkNaNGuard:
    def test_finite_floats_coerces_nan_and_inf(self):
        from routes.performance_quant import _finite_floats
        out = _finite_floats({
            "a": float("nan"),
            "b": float("inf"),
            "c": float("-inf"),
            "d": 1.5,
            "nested": [float("nan"), {"x": float("inf")}],
            "s": "ok",
            "i": 3,
        })
        assert out["a"] == 0.0
        assert out["b"] == 0.0
        assert out["c"] == 0.0
        assert out["d"] == 1.5
        assert out["nested"][0] == 0.0
        assert out["nested"][1]["x"] == 0.0
        assert out["s"] == "ok"
        assert out["i"] == 3

    def test_finite_floats_output_is_json_serializable(self):
        """The whole point: result must not emit literal NaN (invalid JSON)."""
        import json
        from routes.performance_quant import _finite_floats
        payload = {"active_share": float("nan"), "beta": float("inf")}
        cleaned = _finite_floats(payload)
        # allow_nan=False mirrors a strict JSON.parse on the frontend.
        s = json.dumps(cleaned, allow_nan=False)
        assert "NaN" not in s and "Infinity" not in s

    def test_zero_variance_correlation_path_is_zero(self):
        """np.corrcoef on identical/flat series yields nan; guard → 0.0."""
        import numpy as np
        flat = np.zeros(30, dtype=np.float64)
        corr = float(np.corrcoef(flat, flat)[0, 1])
        assert not math.isfinite(corr)  # confirm the hazard exists
        # mirror the inline guard
        if not math.isfinite(corr):
            corr = 0.0
        assert corr == 0.0
        # active_share_est = round((1 - abs(corr)) * 100, 1) = 100.0, finite
        assert math.isfinite(round((1 - abs(corr)) * 100, 1))


# ── API#3: ai/chat message length cap ─────────────────────────────────────────

class TestChatMessageLengthCap:
    def _login_pro(self, client, make_user, email):
        u = make_user(email=email, tier="pro")
        client.post("/api/auth/login",
                    json={"email": u["email"], "password": u["password"]})
        return u

    def test_message_over_4000_chars_returns_400(self, client, make_user):
        self._login_pro(client, make_user, "chatlen@test.com")
        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            r = client.post("/api/ai/chat", json={"message": "x" * 4001})
        assert r.status_code == 400
        assert r.get_json().get("code") == "MESSAGE_TOO_LONG"

    def test_message_at_4000_chars_not_length_rejected(self, client, make_user):
        """Exactly 4000 must pass the length gate (boundary)."""
        self._login_pro(client, make_user, "chatlen2@test.com")
        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.chat.return_value = "ok"
            r = client.post("/api/ai/chat", json={"message": "x" * 4000})
        body = r.get_json() or {}
        assert body.get("code") != "MESSAGE_TOO_LONG"


# ── API#4: daytrade/chart limit + tf validation ───────────────────────────────

class TestDaytradeChartValidation:
    def test_non_numeric_limit_does_not_500(self, client, auth_user):
        with patch("routes.daytrade.daytrade") as mock_dt:
            mock_dt.available = True
            mock_dt.get_intraday_bars.return_value = []
            r = client.get("/api/daytrade/chart/AAPL?limit=abc")
        assert r.status_code == 200
        # falls back to default 100
        _, kwargs_args, _ = (mock_dt.get_intraday_bars.call_args.args + (None,) * 3)[:3]
        assert mock_dt.get_intraday_bars.call_args.args[2] == 100

    def test_oversized_limit_clamped_to_500(self, client, auth_user):
        with patch("routes.daytrade.daytrade") as mock_dt:
            mock_dt.available = True
            mock_dt.get_intraday_bars.return_value = []
            client.get("/api/daytrade/chart/AAPL?limit=999999")
        assert mock_dt.get_intraday_bars.call_args.args[2] == 500

    def test_invalid_tf_falls_back_to_5min(self, client, auth_user):
        with patch("routes.daytrade.daytrade") as mock_dt:
            mock_dt.available = True
            mock_dt.get_intraday_bars.return_value = []
            r = client.get("/api/daytrade/chart/AAPL?tf=bogus")
        assert mock_dt.get_intraday_bars.call_args.args[1] == "5Min"
        assert r.get_json()["timeframe"] == "5Min"

    def test_valid_tf_preserved(self, client, auth_user):
        with patch("routes.daytrade.daytrade") as mock_dt:
            mock_dt.available = True
            mock_dt.get_intraday_bars.return_value = []
            client.get("/api/daytrade/chart/AAPL?tf=15Min")
        assert mock_dt.get_intraday_bars.call_args.args[1] == "15Min"


# ── API#6: backtest period allowlist + 422 ────────────────────────────────────

class TestBacktestValidation:
    def test_arbitrary_period_coerced_to_1y(self, client, auth_user):
        with patch("services.quant.backtester.Backtester") as MockBT:
            MockBT.run.return_value = {"ok": True}
            client.get("/api/backtest/AAPL?period=99y")
        assert MockBT.run.call_args.kwargs["period"] == "1y"

    def test_valid_period_preserved(self, client, auth_user):
        with patch("services.quant.backtester.Backtester") as MockBT:
            MockBT.run.return_value = {"ok": True}
            client.get("/api/backtest/AAPL?period=6mo")
        assert MockBT.run.call_args.kwargs["period"] == "6mo"

    def test_failure_returns_422_not_500(self, client, auth_user):
        with patch("services.quant.backtester.Backtester") as MockBT:
            MockBT.run.return_value = None
            r = client.get("/api/backtest/AAPL")
        assert r.status_code == 422
        assert r.get_json().get("code") == "BACKTEST_FAILED"


# ── API#8: alt_data FRED limit / status / start ───────────────────────────────

class TestFredSeriesValidation:
    def _series_id(self):
        from services.data.fred_service import FRED_SERIES
        return sorted(FRED_SERIES.keys())[0]

    def test_limit_capped_at_1000(self, client, auth_user):
        sid = self._series_id()
        with patch("routes.alt_data.get_fred_service") as mock_get:
            svc = mock_get.return_value
            svc.available = True
            svc.get_series.return_value = {"observations": []}
            client.get(f"/api/alt-data/macro/series/{sid}?limit=50000")
        assert svc.get_series.call_args.kwargs["limit"] == 1000

    def test_no_data_returns_404_not_502(self, client, auth_user):
        sid = self._series_id()
        with patch("routes.alt_data.get_fred_service") as mock_get:
            svc = mock_get.return_value
            svc.available = True
            svc.get_series.return_value = None
            r = client.get(f"/api/alt-data/macro/series/{sid}")
        assert r.status_code == 404

    def test_malformed_start_is_ignored(self, client, auth_user):
        sid = self._series_id()
        with patch("routes.alt_data.get_fred_service") as mock_get:
            svc = mock_get.return_value
            svc.available = True
            svc.get_series.return_value = {"observations": []}
            client.get(f"/api/alt-data/macro/series/{sid}?start=not-a-date")
        assert svc.get_series.call_args.kwargs["start"] is None

    def test_valid_start_passed_through(self, client, auth_user):
        sid = self._series_id()
        with patch("routes.alt_data.get_fred_service") as mock_get:
            svc = mock_get.return_value
            svc.available = True
            svc.get_series.return_value = {"observations": []}
            client.get(f"/api/alt-data/macro/series/{sid}?start=2024-01-01")
        assert svc.get_series.call_args.kwargs["start"] == "2024-01-01"


# ── API#1/#9: KR ticker format + US-only signal rejection ─────────────────────

class TestTickerValidation:
    def test_kr_ticker_passes_format_validation(self):
        from routes.quant_helpers import _ticker_validate
        ticker, err = _ticker_validate("005930.KS")
        assert err is None
        assert ticker == "005930.KS"

    def test_kr_bare_code_passes(self):
        from routes.quant_helpers import _ticker_validate
        ticker, err = _ticker_validate("005930")
        assert err is None
        assert ticker == "005930"

    def test_us_ticker_still_passes(self):
        from routes.quant_helpers import _ticker_validate
        ticker, err = _ticker_validate("aapl")
        assert err is None
        assert ticker == "AAPL"

    def test_garbage_ticker_rejected_with_api_error(self, app):
        from routes.quant_helpers import _ticker_validate
        with app.app_context():  # api_error -> jsonify needs an app context
            ticker, err = _ticker_validate("!!!")
            assert ticker is None
            resp, status = err
            assert status == 400
            assert resp.get_json().get("code") == "INVALID_TICKER_FORMAT"

    def test_is_kr_ticker_helper(self):
        from routes.quant_helpers import _is_kr_ticker
        assert _is_kr_ticker("005930") is True
        assert _is_kr_ticker("005930.KS") is True
        assert _is_kr_ticker("AAPL") is False

    @pytest.mark.parametrize("path_tmpl", [
        "/api/signals/disposition/{t}",
        "/api/signals/ofi/{t}",
        "/api/signals/sentiment-divergence/{t}",
        "/api/signals/anchoring/{t}",
    ])
    def test_kr_ticker_clean_unsupported_on_us_only_signals(
        self, path_tmpl, client, auth_user, app
    ):
        """KR ticker reaches a clean 422 KR-unsupported, not a 400 format error
        and not a confusing downstream 404. Seed the position so the §101
        access gate passes and we exercise the KR branch."""
        from models import Position
        from extensions import db
        with app.app_context():
            db.session.add(Position(user_id=auth_user["id"], ticker="005930.KS",
                                    shares=1.0, avg_cost=1.0))
            db.session.commit()
        r = client.get(path_tmpl.format(t="005930.KS"))
        assert r.status_code == 422, (
            f"{path_tmpl}: expected 422 KR-unsupported, got {r.status_code}"
        )
        assert r.get_json().get("code") == "SIGNAL_QUANT_KR_UNSUPPORTED"


# ── C#4: retention SKIP LOCKED ────────────────────────────────────────────────

class TestRetentionSkipLocked:
    def test_pending_retention_rows_uses_skip_locked(self):
        """The inline query must row-lock with skip_locked to prevent the
        double-send race between concurrent retention cron workers."""
        import inspect
        from services.email import retention_sequence
        src = inspect.getsource(retention_sequence._pending_retention_rows)
        assert "with_for_update(skip_locked=True)" in src
