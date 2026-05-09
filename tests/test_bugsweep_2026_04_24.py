"""Regression tests for the 2026-04-24 backend bug sweep.

Covers:
  * Bug A — /api/risk/layers independent per-layer compute + partial fallback
  * Bug C — price_overlay.parse_price_display fallback for watchlist/portfolio
  * Bug D — KR indices always try KIS (no _rt.kis_available gate)
  * Bug F — alerts migration replaces legacy "Rec:" with "Sized:"
  * Bug G — /api/discover/sectors all-zero rejection → mock fallback
"""
from __future__ import annotations

import json
from unittest.mock import patch

import numpy as np
import pytest


# ══════════════════════════════════════════════════════════════════════
# Bug A — risk.check_all partial-failure fallback
# ══════════════════════════════════════════════════════════════════════


class TestRiskLayersPartialFallback:
    """Bug A: when check_all() raises, routes/risk.py used to return the
    "No positions under observation" default_layers payload for ALL 7
    layers — even though the portfolio had positions and we had a
    valid returns matrix. The fix makes each per-layer metric
    independent: check_all is attempted but any exception there only
    blanks the `layers_triggered` set, NOT the metric strings.
    """

    def _seed_positions(self, app, user_id, tickers):
        from extensions import db
        from models import Position
        with app.app_context():
            for t in tickers:
                db.session.add(Position(
                    user_id=user_id, ticker=t, shares=10.0, avg_cost=100.0,
                ))
            db.session.commit()

    def test_layers_returns_real_metrics_even_when_check_all_raises(
        self, client, auth_user, app,
    ):
        """check_all() blows up → metric strings still come from _portfolio_snapshot."""
        self._seed_positions(app, auth_user["id"], ["AAPL", "MSFT", "GOOG"])

        # Build a deterministic returns matrix (60 rows × 3 tickers).
        import pandas as pd
        rng = np.random.default_rng(42)
        n = 60

        def _hist(_t, period="3mo"):
            closes = 100 + np.cumsum(rng.normal(0, 1.0, n))
            return pd.DataFrame({
                "Close": closes, "Open": closes, "High": closes + 1,
                "Low": closes - 1, "Volume": [1000] * n,
            }, index=pd.date_range("2026-02-01", periods=n, freq="D"))

        # Force RiskDefenseSystem.check_all to raise so we prove the
        # partial-fallback path kicks in.
        def _boom(*a, **kw):
            raise RuntimeError("simulated check_all blowup (Bug A repro)")

        with patch("routes.risk.fetcher") as m_fetcher, \
             patch("services.container.realtime") as m_rt, \
             patch("services.quant.risk_defense.RiskDefenseSystem.check_all", side_effect=_boom):
            m_fetcher.get_price_history.side_effect = _hist
            m_fetcher.get_macro_data.return_value = {"vix": 18.5}
            m_rt.get_prices_batch.return_value = {
                "AAPL": {"price": 170.0},
                "MSFT": {"price": 310.0},
                "GOOG": {"price": 140.0},
            }
            r = client.get("/api/risk/layers")

        assert r.status_code == 200
        data = r.get_json()
        # The endpoint returns either {layers: [...]} or a bare list
        # depending on whether a score was computable. Accept both.
        if isinstance(data, dict) and "layers" in data:
            layers = data["layers"]
        else:
            layers = data
        assert isinstance(layers, list)
        assert len(layers) == 7

        # Core invariant: metric_value is NOT all "—". At least VaR
        # (L1) and Correlation (L2) should have concrete values because
        # the matrix + weights are fine. If this fails, check_all's
        # exception is still poisoning per-layer rendering.
        non_placeholder = [
            ly for ly in layers
            if ly.get("metric_value") not in ("—", "0.00%", None, "")
        ]
        assert non_placeholder, (
            f"Every layer blank after check_all failure — Bug A regression. "
            f"layers={layers!r}"
        )

        # VIX (L3) was supplied via macro — should render as "18.5".
        vix_layer = next((ly for ly in layers if ly["no"] == 3), None)
        assert vix_layer is not None
        assert "18" in str(vix_layer["metric_value"]), (
            f"VIX metric missing despite macro feed: {vix_layer}"
        )

    def test_risk_defense_handles_mismatched_weights_shape(self):
        """Unit: RiskDefenseSystem._layer1_var must not raise when
        the weights vector length disagrees with the returns_matrix
        column count (tickers dropped by _build_returns_matrix)."""
        from services.quant.risk_defense import RiskDefenseSystem

        rds = RiskDefenseSystem.from_profile("steady_accumulator")
        rng = np.random.default_rng(0)
        # Matrix has 2 cols (dropped 1), positions has 3 — drop-alignment case.
        matrix = rng.normal(0, 0.01, size=(60, 2))
        positions = [
            {"ticker": "A", "weight": 0.4, "value": 100, "sector": "X",
             "returns_20d": 0.0},
            {"ticker": "B", "weight": 0.3, "value": 100, "sector": "Y",
             "returns_20d": 0.0},
            {"ticker": "C", "weight": 0.3, "value": 100, "sector": "Z",
             "returns_20d": 0.0},
        ]
        # Should not raise.
        result = rds.check_all({
            "positions": positions,
            "portfolio_value": 300.0,
            "daily_return": 0.0,
            "vix": None,
            "regime": "TRANSITION",
            "returns_matrix": matrix,
        })
        assert "defense_score" in result

    def test_risk_defense_handles_zero_sum_weights(self):
        """Unit: all-zero weights must NOT divide by zero / NaN-out."""
        from services.quant.risk_defense import RiskDefenseSystem

        rds = RiskDefenseSystem.from_profile("steady_accumulator")
        matrix = np.zeros((30, 2))  # trivially short but shaped OK
        # All positions have weight 0 (zero-valued portfolio).
        positions = [
            {"ticker": "A", "weight": 0.0, "value": 0, "sector": "X"},
            {"ticker": "B", "weight": 0.0, "value": 0, "sector": "Y"},
        ]
        # Should not raise and should not produce NaN scores.
        result = rds.check_all({
            "positions": positions,
            "portfolio_value": 0.0,  # layer gate triggers early-return
            "daily_return": 0.0,
            "vix": None,
            "regime": "TRANSITION",
            "returns_matrix": matrix,
        })
        # portfolio_value<=0 short-circuits in check_all — still must be clean.
        assert isinstance(result["defense_score"], int)


# ══════════════════════════════════════════════════════════════════════
# Bug C — price_display parse fallback
# ══════════════════════════════════════════════════════════════════════


class TestPriceDisplayParser:
    """Unit tests for services.price_overlay.parse_price_display."""

    def test_dollar_plain(self):
        from services.price_overlay import parse_price_display
        assert parse_price_display("$402.91") == pytest.approx(402.91)

    def test_dollar_with_thousands(self):
        from services.price_overlay import parse_price_display
        assert parse_price_display("$1,234.56") == pytest.approx(1234.56)

    def test_krw_with_symbol(self):
        from services.price_overlay import parse_price_display
        assert parse_price_display("₩42,100") == pytest.approx(42100.0)

    def test_bare_number(self):
        from services.price_overlay import parse_price_display
        assert parse_price_display("170.25") == pytest.approx(170.25)

    def test_placeholder_returns_none(self):
        from services.price_overlay import parse_price_display
        assert parse_price_display("—") is None
        assert parse_price_display("") is None
        assert parse_price_display(None) is None
        assert parse_price_display("N/A") is None

    def test_zero_rejected(self):
        """$0 is not a useful fallback price."""
        from services.price_overlay import parse_price_display
        assert parse_price_display("$0.00") is None

    def test_euro_supported(self):
        from services.price_overlay import parse_price_display
        assert parse_price_display("€1,234.56") == pytest.approx(1234.56)


class TestWatchlistStaleDisplayFallback:
    """Bug C: watchlist.serialize must derive last_price from
    SignalCache.price_display when the overlay is empty, instead of
    emitting 0.0000.
    """

    def test_watchlist_uses_price_display_fallback(self, client, auth_user, app):
        from extensions import db
        from models import Watchlist, SignalCache

        with app.app_context():
            db.session.add(Watchlist(
                user_id=auth_user["id"], ticker="AAPL", note="",
            ))
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({
                    "name": "Apple Inc.", "is_korean": False,
                    "currency": "USD",
                    # price omitted — only display is available
                    "price_display": "$402.91",
                }),
            ))
            db.session.commit()

        # Overlay returns empty (realtime down, no fresh cache).
        with patch("routes.watchlist.overlay_prices", return_value={}):
            r = client.get("/api/watchlist")

        assert r.status_code == 200
        items = r.get_json()["watchlist"]
        assert len(items) == 1
        item = items[0]
        # Before fix: last_price == 0. After: 402.91 from price_display.
        assert item["last_price"] == pytest.approx(402.91), (
            f"last_price fallback failed — got {item!r}"
        )
        assert item["price"] == pytest.approx(402.91)


# ══════════════════════════════════════════════════════════════════════
# Bug D — KR indices: always try KIS (no kis_available gate)
# ══════════════════════════════════════════════════════════════════════


class TestKrIndicesKisGate:
    """Bug D: _kis_index_snapshot must consult KIS even when the outer
    `realtime.kis_available` flag is False — KISService has its own
    credential check.
    """

    def test_kr_indices_queries_kis_without_kis_available(
        self, client, auth_user,
    ):
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        # Mock KISService with fresh KIS data — per-code values within
        # PR #188 per-ticker sanity bounds:
        #   ^KS11 [1500,4500] / ^KQ11 [500,1500] /
        #   ^KS200 [300,700]  / ^KQ150 [800,2000]
        _LIVE = {
            "0001": (2540.0, [2510.0 + i * 0.5 for i in range(60)]),  # KOSPI
            "1001": (750.0,  [720.0 + i * 0.5 for i in range(60)]),   # KOSDAQ
            "2001": (337.0,  [325.0 + i * 0.2 for i in range(60)]),   # KOSPI 200
            "2203": (1240.0, [1210.0 + i * 0.5 for i in range(60)]),  # KOSDAQ 150
        }

        class _MockKIS:
            def get_index_price(self_inner, code):
                price, _ = _LIVE.get(code, (2540.0, []))
                return {
                    "index_code": code, "price": price,
                    "change": 10.0, "change_pct": 0.15, "volume": 0,
                }

            def get_index_history(self_inner, code, period="1y"):
                _, hist = _LIVE.get(code, (2540.0, []))
                return [{"date": "", "close": c} for c in hist]

        with patch("routes.market.fetcher") as m_f, \
             patch("services.container.realtime") as m_rt, \
             patch("services.kis.service.KISService", _MockKIS), \
             patch("services.data.fmp.get_history", return_value=None):
            # The regression: realtime.kis_available = False but
            # KISService credentials are valid.
            m_rt.kis_available = False
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        names = {e["name"]: e for e in data}
        # KOSPI tile must still populate from KIS despite kis_available=False.
        assert "KOSPI" in names, (
            f"KOSPI missing when kis_available=False — Bug D regression. "
            f"Got: {list(names)}"
        )
        kospi = names["KOSPI"]
        assert kospi["level"] == pytest.approx(2540.0), (
            f"KIS level should surface: {kospi}"
        )


# ══════════════════════════════════════════════════════════════════════
# Bug F — alerts migration (Rec: → Sized:)
# ══════════════════════════════════════════════════════════════════════


class TestAlertsMigrationSizedRename:
    """Bug F: migration 014_alerts_sized_rename.py rewrites legacy rows.

    We can't execute Alembic in-process reliably without messing up
    session state, so we exercise the *SQL* the migration issues
    against our isolated test DB. Any shape mismatch would surface here.
    """

    def test_replace_sql_rewrites_legacy_rows(self, app):
        from extensions import db
        from models import User
        from models.alert import Alert

        with app.app_context():
            u = User(email="alertuser@test.com", name="A",
                      available_capital=0.0, available_capital_krw=0.0,
                      subscription_tier="free")
            u.set_pw("passphrase123")
            db.session.add(u)
            db.session.commit()

            # Seed a mix of legacy + already-updated + unrelated rows.
            legacy = Alert(
                user_id=u.id, ticker="AAPL",
                message="Rec: 0 shares · set capital for sizing",
            )
            updated = Alert(
                user_id=u.id, ticker="MSFT",
                message="Sized: 5 shares · $1,000 allocated",
            )
            unrelated = Alert(
                user_id=u.id, ticker="GOOG",
                message="52-week high observed",
            )
            db.session.add_all([legacy, updated, unrelated])
            db.session.commit()

            # Execute the exact SQL the migration runs.
            db.session.execute(db.text(
                "UPDATE alerts SET message = REPLACE(message, 'Rec:', 'Sized:') "
                "WHERE message LIKE '%Rec:%'"
            ))
            db.session.commit()

            legacy_after = db.session.get(Alert, legacy.id)
            updated_after = db.session.get(Alert, updated.id)
            unrelated_after = db.session.get(Alert, unrelated.id)

            assert legacy_after.message.startswith("Sized:"), (
                f"Legacy row not rewritten: {legacy_after.message!r}"
            )
            assert "Rec:" not in legacy_after.message
            # Idempotent on already-updated / unrelated rows.
            assert updated_after.message == (
                "Sized: 5 shares · $1,000 allocated"
            )
            assert unrelated_after.message == "52-week high observed"


# ══════════════════════════════════════════════════════════════════════
# Bug G — discover/sectors all-zero rejection
# ══════════════════════════════════════════════════════════════════════


class TestDiscoverSectorsAllZero:
    """Bug G v2 (2026-04-28): all-zero rows used to fall through to mock
    fallback (legal risk: fake data shown as live). New contract is
    fail-fast 503 DATA_PROVIDER_DOWN — frontend must show "data unavailable" UI.
    """

    def test_all_zero_rows_return_503(self, client, auth_user):
        import routes.discover as disc
        disc._section_cache.clear()

        flat = [
            {"sector": "Technology", "changesPercentage": "0%"},
            {"sector": "Healthcare", "changesPercentage": "0%"},
            {"sector": "Financials", "changesPercentage": "0%"},
            {"sector": "Energy", "changesPercentage": "0%"},
            {"sector": "Consumer Discretionary", "changesPercentage": "0%"},
            {"sector": "Industrials", "changesPercentage": "0%"},
            {"sector": "Utilities", "changesPercentage": "0%"},
            {"sector": "Communication Services", "changesPercentage": "0%"},
            {"sector": "Real Estate", "changesPercentage": "0%"},
            {"sector": "Materials", "changesPercentage": "0%"},
            {"sector": "Consumer Staples", "changesPercentage": "0%"},
        ]
        with patch("routes.discover.fetcher") as m_f:
            m_f.get_sector_performance.return_value = flat
            r = client.get("/api/discover/sectors")

        assert r.status_code == 503
        data = r.get_json()
        assert data["code"] == "DATA_PROVIDER_DOWN"
        assert data["endpoint"] == "sectors"

    def test_realistic_rows_pass_through_unchanged(self, client, auth_user):
        """Sanity: when FMP returns real data, we don't spuriously fall back."""
        import routes.discover as disc
        disc._section_cache.clear()

        live = [
            {"sector": "Technology", "changesPercentage": "1.23%"},
            {"sector": "Healthcare", "changesPercentage": "-0.45%"},
            {"sector": "Financials", "changesPercentage": "0.12%"},
            {"sector": "Energy", "changesPercentage": "-2.10%"},
            {"sector": "Consumer Discretionary", "changesPercentage": "0.85%"},
        ]
        with patch("routes.discover.fetcher") as m_f:
            m_f.get_sector_performance.return_value = live
            r = client.get("/api/discover/sectors")

        assert r.status_code == 200
        data = r.get_json()
        # 5 rows passed through — must NOT be coerced into the mock's 11 rows.
        assert len(data) == 5
        # Technology d1 should be exactly 1.23 (real data preserved).
        tech = next(row for row in data if row["sector"] == "Technology")
        assert tech["d1"] == pytest.approx(1.23)
