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


class TestKrIndicesKisGate:
    """Bug D: _kis_index_snapshot must consult KIS even when the outer
    `realtime.kis_available` flag is False — KISService has its own
    credential check.
    """


    # ── MARKET_DATA_DISPLAY_ENABLED ──────────────────────────
    # MARKET_DATA_DISPLAY_ENABLED defaults to OFF (config.py — FMP Data Display
    # Agreement pending). These assertions are about the ON behaviour, so they opt
    # in explicitly; the OFF contract lives in tests/test_market_data_display_flag.py.
    @pytest.fixture(autouse=True)
    def _market_display_on(self, market_display_on):
        yield

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

        with patch("services.data.indices.fetcher") as m_f, \
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

