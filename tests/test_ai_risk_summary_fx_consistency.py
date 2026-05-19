"""Regression test — AIRiskSummary FX consistency (Pattern 7, B2 P1).

Bug: routes/ai.py risk_summary summed `price * shares` directly across KR
(KRW) and US (USD) positions. A ₩75,000 KR price was added to the same
total as a $100 US price, producing a numeraire-mixed `total_value` that
the Claude prompt then formatted as `${value}` — inflating KR holdings
~700x.

Fix: mirror portfolio.py:260-272 pattern. KR positions (`.KS` / `.KQ`
suffix or `sd['is_korean']`) are converted to USD via `fx_service.get_rate()`
before summation.

Wide-scope: same pattern also lived in services/ai/service.py
build_portfolio_context (feeds /api/ai/chat and /api/ai/coaching).
Fixed in the same commit; one of the tests below confirms it.
"""
from __future__ import annotations

import json
from unittest.mock import patch


class TestRiskSummaryFxConsistency:
    def test_mixed_kr_us_portfolio_normalizes_to_usd(
        self, app, client, make_user, add_position,
    ):
        """KR 10 × ₩75,000 + US 5 × $100 → ~$547 + $500 = ~$1,047 USD.
        Without the fix: 750,000 (raw KRW) + 500 = 750,500 ('USD') — 700x off.
        """
        from extensions import db
        from models import SignalCache

        u = make_user(email="fx_user@test.com", tier="pro")
        # KR: Samsung 005930.KS — price 75,000 KRW × 10 shares
        add_position(user_id=u["id"], ticker="005930.KS",
                     shares=10.0, avg_cost=75_000.0)
        # US: AAPL — price $100 × 5 shares
        add_position(user_id=u["id"], ticker="AAPL",
                     shares=5.0, avg_cost=100.0)

        # Seed SignalCache so risk_summary uses CURRENT prices (not avg_cost).
        with app.app_context():
            db.session.add(SignalCache(
                ticker="005930.KS",
                data_json=json.dumps({"price": 75_000.0, "is_korean": True}),
            ))
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({"price": 100.0}),
            ))
            db.session.commit()

        # Log the user in (auth_user fixture pre-creates a different user).
        login_resp = client.post("/api/auth/login", json={
            "email": u["email"], "password": u["password"],
        })
        assert login_resp.status_code == 200

        captured = {}

        def fake_generate(portfolio_data, var_data=None, stress_data=None,
                          user_id=None):
            # Snapshot the value the route passes to AIRiskSummary.
            captured["value"] = portfolio_data["value"]
            captured["top_pct"] = portfolio_data["top_pct"]
            captured["user_id"] = user_id
            return ({
                "summary_en": "ok", "summary_kr": "ok",
                "risk_level": "low", "top_risk_factor": "test",
            }, 200)

        # Force ai.available = True so the 503 guard passes, and stub
        # AIRiskSummary so no Claude call fires.
        with patch("routes.ai.ai") as mock_ai, \
             patch("routes.ai.AIRiskSummary.generate", side_effect=fake_generate), \
             patch("services.fx_service.get_rate", return_value=1370.0):
            mock_ai.available = True
            r = client.post("/api/ai/risk-summary", json={})

        assert r.status_code == 200, r.data
        # KR mv_usd = 75,000 × 10 / 1370 ≈ $547.45
        # US mv_usd = 100 × 5                = $500.00
        # Total                              ≈ $1,047.45
        assert 1000 < captured["value"] < 1100, (
            f"Expected USD-normalized total ~$1,047, got {captured['value']!r}. "
            f"Raw-sum bug would produce ~750,500."
        )
        # Concentration: KR is the bigger one (547 / 1047 ≈ 52%).
        assert 50 < captured["top_pct"] < 55, (
            f"Expected top_pct ~52% (KR position), got {captured['top_pct']!r}. "
            f"Raw-sum bug would compute KR % over the inflated total."
        )
        # Sanity: user_id threaded through for cache isolation (Commit 1).
        assert captured["user_id"] == u["id"]


class TestBuildPortfolioContextFx:
    """Wide-scope companion fix — services/ai/service.py same pattern."""

    def test_build_portfolio_context_converts_kr_to_usd(self, app, make_user):
        from services.ai.service import AIService

        u = make_user(email="ctx_fx@test.com")

        class _P:
            def __init__(self, ticker, shares, avg_cost):
                self.ticker = ticker
                self.shares = shares
                self.avg_cost = avg_cost

        positions = [
            _P("005930.KS", 10.0, 75_000.0),
            _P("AAPL", 5.0, 100.0),
        ]
        sig_cache = {
            "005930.KS": {"price": 75_000.0, "is_korean": True},
            "AAPL":      {"price": 100.0},
        }

        with app.app_context():
            from models import User
            user_row = User.query.get(u["id"])
            with patch("services.fx_service.get_rate", return_value=1370.0):
                svc = AIService()
                ctx = svc.build_portfolio_context(user_row, positions, sig_cache)

        # Expected total ≈ $1,047 USD (547 + 500); raw bug → $750,500.
        # The builder formats as `~${total_val:,.0f}` so we look for ~$1,047.
        assert "Total Portfolio Value: ~$1,047" in ctx, (
            "build_portfolio_context did not FX-normalize KR position. "
            f"Got:\n{ctx[-300:]}"
        )
