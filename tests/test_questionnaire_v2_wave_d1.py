"""
tests/test_questionnaire_v2_wave_d1.py — questionnaire V2 regression suite
========================================================================
Wave D-1 (2026-05-17) — guard the 6 bugs the audit fixed so they don't
regress:

  Q1  apply_preset must use V2 presets for V2 types (was silently falling
      back to "balanced" for all 8 V2 types)
  Q2  legal_confirmed must be enforced — partial-V2 submissions missing
      the legal block must 400 (was silently accepted)
  Q3  V2 answers must persist to ORM columns under the correct mapping
      (was overwriting with V1-ID defaults — "beginner"/"growth"/5/etc.)
  Q4  knowledge_self_rating type safety — None / list / dict / string
      must not crash (was raising TypeError swallowed by bare-except)
  Q5  monthly_investable must influence capital_tier (was dead-code —
      computed and discarded)
  Q6  update_profile (PUT /api/profile) must also use V2 classifier
      (was V1-only — re-take silently downgraded to 4-tier)

All checks are pure-Python over the scoring function or use the standard
``client`` + ``auth_user`` fixtures from conftest.py.
"""
from __future__ import annotations

import json


# ═════════════════════════════════════════════════════════════════════════
# Q4 — knowledge_self_rating type safety (pure-fn unit tests)
# ═════════════════════════════════════════════════════════════════════════

class TestKnowledgeSelfRatingTypeSafety:
    def test_none_does_not_crash(self):
        from services.profile.questionnaire import calculate_profile_v2
        result = calculate_profile_v2({"knowledge_self_rating": None})
        assert isinstance(result["knowledge_score"], int)
        assert 0 <= result["knowledge_score"] <= 10

    def test_list_does_not_crash(self):
        from services.profile.questionnaire import calculate_profile_v2
        result = calculate_profile_v2({"knowledge_self_rating": [1, 2, 3]})
        assert 0 <= result["knowledge_score"] <= 10

    def test_dict_does_not_crash(self):
        from services.profile.questionnaire import calculate_profile_v2
        result = calculate_profile_v2({"knowledge_self_rating": {"a": 1}})
        assert 0 <= result["knowledge_score"] <= 10

    def test_non_numeric_string_falls_back_to_default(self):
        from services.profile.questionnaire import calculate_profile_v2
        result = calculate_profile_v2({"knowledge_self_rating": "abc"})
        assert 0 <= result["knowledge_score"] <= 10

    def test_float_accepted(self):
        from services.profile.questionnaire import calculate_profile_v2
        result = calculate_profile_v2({"knowledge_self_rating": 3.5})
        assert 0 <= result["knowledge_score"] <= 10

    def test_out_of_range_is_clamped(self):
        """Slider documented range is 1..5. Out-of-range input must clamp
        rather than skew the composite (pre-fix 999 produced knowledge_score=10)."""
        from services.profile.questionnaire import calculate_profile_v2
        high = calculate_profile_v2({"knowledge_self_rating": 999})
        low = calculate_profile_v2({"knowledge_self_rating": -999})
        # 999 clamps to 5 -> (0 + 10) / 2 = 5
        # -999 clamps to 1 -> (0 + 2) / 2 = 1
        assert high["knowledge_score"] == 5
        assert low["knowledge_score"] == 1


# ═════════════════════════════════════════════════════════════════════════
# Q5 — monthly_investable influences capital_tier
# ═════════════════════════════════════════════════════════════════════════

class TestMonthlyInvestableWired:
    def test_high_monthly_lifts_low_portfolio_tier(self):
        """Pre-fix monthly_investable value was computed and discarded
        (no ``+=`` / no assignment). A student saver with lt1k saved but
        5k_plus/month flow should not stay pinned at micro forever."""
        from services.profile.questionnaire import calculate_profile_v2
        low = calculate_profile_v2({
            "portfolio_size": "lt1k",
            "monthly_investable": "lt100",
        })
        high = calculate_profile_v2({
            "portfolio_size": "lt1k",
            "monthly_investable": "5k_plus",
        })
        # Same portfolio_size, different monthly — tier should differ.
        assert low["capital_tier"] != high["capital_tier"], (
            "monthly_investable must influence capital_tier "
            f"(both got {low['capital_tier']!r})"
        )

    def test_portfolio_size_still_dominates(self):
        """Weighting is 70/30 — large portfolio with zero monthly must
        not collapse to micro."""
        from services.profile.questionnaire import calculate_profile_v2
        result = calculate_profile_v2({
            "portfolio_size": "200k_plus",
            "monthly_investable": "lt100",
        })
        assert result["capital_tier"] in ("large", "whale")


# ═════════════════════════════════════════════════════════════════════════
# Q1 — apply_preset must dispatch on V2 types
# ═════════════════════════════════════════════════════════════════════════

class TestApplyPresetV2Dispatch:
    def test_v2_momentum_rider_uses_v2_preset(self, app):
        """Pre-fix: every V2 type fell back to balanced because V1
        PROFILE_PRESETS has no overlapping keys. ``momentum_rider`` should
        get tp_max=30.0 / max_positions=6 from PROFILE_PRESETS_V2, not
        15.0 / 15 from balanced."""
        from extensions import db
        from models import InvestmentProfile

        with app.app_context():
            # No need for a real user — apply_preset is pure on the row.
            p = InvestmentProfile(user_id=999999, profile_type="momentum_rider")
            p.apply_preset()
            assert p.tp_max == 30.0, (
                f"momentum_rider must use V2 preset (tp_max=30.0), "
                f"got {p.tp_max}"
            )
            assert p.max_positions == 6
            assert p.ai_coaching_style == "aggressive"

    def test_v2_passive_index_hugger_uses_v2_preset(self, app):
        from extensions import db
        from models import InvestmentProfile

        with app.app_context():
            p = InvestmentProfile(user_id=999998, profile_type="passive_index_hugger")
            p.apply_preset()
            # V2: tp_max=8.0, max_positions=10, buy_threshold=78.0
            assert p.tp_max == 8.0
            assert p.max_positions == 10
            assert p.buy_threshold == 78.0

    def test_v1_balanced_still_works(self, app):
        """Backward compatibility — V1 types must still resolve."""
        from extensions import db
        from models import InvestmentProfile

        with app.app_context():
            p = InvestmentProfile(user_id=999997, profile_type="balanced")
            p.apply_preset()
            assert p.tp_max == 15.0
            assert p.max_positions == 15

    def test_unknown_type_falls_back_to_balanced(self, app):
        from extensions import db
        from models import InvestmentProfile

        with app.app_context():
            p = InvestmentProfile(user_id=999996, profile_type="nonexistent_type")
            p.apply_preset()
            # Falls through both V2 (None) and V1 (.get default) to balanced.
            assert p.tp_max == 15.0


# ═════════════════════════════════════════════════════════════════════════
# Q2 — legal_confirmed enforcement on POST /api/profile/onboarding
# ═════════════════════════════════════════════════════════════════════════

class TestLegalGate:
    def _v2_payload(self, with_legal: bool = True) -> dict:
        ans = {
            "experience_years": "1to3",
            "asset_types_traded": ["stocks", "etfs"],
            "portfolio_size": "1k_10k",
            "monthly_investable": "100_500",
            "income_stability": "stable",
            "trading_frequency": "few",
            "holding_period": "months",
            "rebalance_preference": "monthly",
            "concentration_preference": "moderate",
            "leverage_appetite": "never",
            "scenario_portfolio_drop": "hold",
            "scenario_single_stock_crash": "hold",
            "scenario_market_crash_relative": "acceptable",
            "expected_annual_return": "5to10",
            "return_vs_stability": "mostly_steady",
            "min_acceptable_return": "beat_bank",
            "knowledge_concepts": ["pe_ratio", "market_cap"],
            "knowledge_self_rating": 3,
        }
        if with_legal:
            ans["legal_confirmations"] = [
                "age_18", "experience_acknowledged", "risk_acknowledged",
                "past_performance", "ai_advisory",
            ]
        return ans

    def test_v2_without_legal_rejected_400(self, client, auth_user):
        """Partial V2 submission missing the legal block must 400, not
        silently complete onboarding without a disclaimer ack."""
        resp = client.post("/api/profile/onboarding", json={
            "answers": self._v2_payload(with_legal=False),
        })
        assert resp.status_code == 400
        body = resp.get_json() or {}
        assert "LEGAL" in (body.get("code") or "").upper() or "legal" in str(body).lower()

    def test_v2_with_legal_accepted(self, client, auth_user):
        resp = client.post("/api/profile/onboarding", json={
            "answers": self._v2_payload(with_legal=True),
        })
        assert resp.status_code == 200, resp.data

    def test_skip_path_still_allowed(self, client, auth_user):
        """Empty answers (Skip button) must still work — only partial-V2
        submissions need the legal gate."""
        resp = client.post("/api/profile/onboarding", json={"answers": {}})
        assert resp.status_code == 200, resp.data

    def test_non_dict_answers_rejected_400(self, client, auth_user):
        resp = client.post("/api/profile/onboarding", json={"answers": ["a", "b"]})
        assert resp.status_code == 400


# ═════════════════════════════════════════════════════════════════════════
# 2026-05-22 — v1-keys legal-gate bypass (자본시장법 §6)
# ═════════════════════════════════════════════════════════════════════════
#
# Pre-fix the legal gate only fired for V2-shaped submissions
# (``is_v2_submission`` — required experience_years/portfolio_size/
# scenario_portfolio_drop/legal_confirmations). A direct API caller
# posting legacy v1-style keys (e.g. {"experience_level": "beginner",
# "investment_goal": "growth"}) had is_v2_submission=False → SKIPPED the
# gate → onboarding_completed=True with no disclaimer ack. The frontend
# only ever sends ``{}`` (skip) or a full V2 payload carrying the legal
# block, so any non-empty submission without legal_confirmations is a
# direct-API bypass. We reject it (400).

class TestV1KeysLegalBypass:
    def test_v1_only_keys_with_content_rejected_400(self, app, client, auth_user):
        """The exact bypass payload from the audit: v1 keys, no v2 markers,
        no legal_confirmations → must 400, must NOT complete onboarding."""
        resp = client.post("/api/profile/onboarding", json={
            "answers": {
                "experience_level": "beginner",
                "investment_goal": "growth",
            },
        })
        assert resp.status_code == 400, resp.data
        body = resp.get_json() or {}
        assert "LEGAL" in (body.get("code") or "").upper()

        # Side-effect check: onboarding must NOT have been marked complete.
        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, auth_user["id"])
            assert not bool(getattr(u, "onboarding_completed", False)), (
                "v1-keys bypass must not silently complete onboarding"
            )

    def test_v1_single_key_rejected_400(self, client, auth_user):
        """Even a single non-legal answer key triggers the gate."""
        resp = client.post("/api/profile/onboarding", json={
            "answers": {"risk_tolerance": 5},
        })
        assert resp.status_code == 400, resp.data

    def test_empty_dict_still_completes(self, app, client, auth_user):
        """Regression: the skip path ({}) must still complete onboarding."""
        resp = client.post("/api/profile/onboarding", json={"answers": {}})
        assert resp.status_code == 200, resp.data
        from extensions import db
        from models import User
        with app.app_context():
            u = db.session.get(User, auth_user["id"])
            assert bool(getattr(u, "onboarding_completed", False)), (
                "empty {} skip path must still complete onboarding"
            )

    def test_proper_v2_still_completes(self, app, client, auth_user):
        """Regression: a full V2 payload with legal_confirmations still works."""
        gate = TestLegalGate()
        resp = client.post("/api/profile/onboarding", json={
            "answers": gate._v2_payload(with_legal=True),
        })
        assert resp.status_code == 200, resp.data

    def test_put_v1_keys_with_content_rejected_400(self, app, client, auth_user):
        """PUT /api/profile must enforce the same v1-keys gate as POST."""
        # Seed a profile first via the legitimate skip path.
        resp = client.post("/api/profile/onboarding", json={"answers": {}})
        assert resp.status_code == 200
        resp = client.put("/api/profile", json={
            "answers": {"experience_level": "beginner", "investment_goal": "growth"},
        })
        assert resp.status_code == 400, resp.data


# ═════════════════════════════════════════════════════════════════════════
# Q3 — V2 answers persist to ORM columns
# ═════════════════════════════════════════════════════════════════════════

class TestV2AnswerPersistence:
    def _full_v2(self) -> dict:
        return {
            "experience_years": "5plus",
            "asset_types_traded": ["stocks", "options", "futures"],
            "portfolio_size": "50k_200k",
            "monthly_investable": "2k_5k",
            "income_stability": "very_stable",
            "trading_frequency": "daily",
            "holding_period": "intraday",
            "rebalance_preference": "auto_daily",
            "concentration_preference": "ultra_focused",
            "leverage_appetite": "full",
            "scenario_portfolio_drop": "buy_heavy",
            "scenario_single_stock_crash": "double_down",
            "scenario_market_crash_relative": "regret_upside",
            "expected_annual_return": "40plus",
            "return_vs_stability": "volatile_high",
            "min_acceptable_return": "beat_20",
            "knowledge_concepts": [
                "pe_ratio", "market_cap", "short_selling",
                "candlestick", "rsi_macd", "options_greeks",
                "beta_alpha", "kelly_criterion",
            ],
            "knowledge_self_rating": 5,
            "legal_confirmations": [
                "age_18", "experience_acknowledged", "risk_acknowledged",
                "past_performance", "ai_advisory",
            ],
        }

    def test_v2_submission_persists_classified_type(self, app, client, auth_user):
        """Pre-fix the route persisted V1-ID defaults regardless of V2
        payload. Post-fix the row reflects the V2 classification result."""
        resp = client.post("/api/profile/onboarding", json={
            "answers": self._full_v2(),
        })
        assert resp.status_code == 200, resp.data

        from extensions import db
        from models import InvestmentProfile

        with app.app_context():
            p = InvestmentProfile.query.filter_by(user_id=auth_user["id"]).first()
            assert p is not None
            assert p.profile_type == "aggressive_scalper", (
                f"expected aggressive_scalper from full-aggressive V2 payload, "
                f"got {p.profile_type}"
            )
            # The V2 preset must apply (not the silent balanced fallback).
            assert p.tp_max == 5.0, f"aggressive_scalper V2 preset tp_max=5.0 expected, got {p.tp_max}"
            assert p.max_positions == 5
            # risk_tolerance derives from V2 risk_score / 10 — should be high.
            assert p.risk_tolerance >= 7
            # time_horizon derives from holding_period=intraday → short
            assert p.time_horizon == "short"
            # auto_trade_preference derives from rebalance_preference=auto_daily → full_auto
            assert p.auto_trade_preference == "full_auto"

    def test_v2_resubmission_via_put_uses_v2(self, app, client, auth_user):
        """Q6: re-take questionnaire via PUT /api/profile must also use V2."""
        # First create a profile via POST.
        resp = client.post("/api/profile/onboarding", json={
            "answers": self._full_v2(),
        })
        assert resp.status_code == 200

        # Now re-take with a conservative V2 payload via PUT.
        conservative = {
            "experience_years": "none",
            "asset_types_traded": ["none"],
            "portfolio_size": "lt1k",
            "monthly_investable": "lt100",
            "income_stability": "student",
            "trading_frequency": "rare",
            "holding_period": "years",
            "rebalance_preference": "quarterly",
            "concentration_preference": "broad",
            "leverage_appetite": "never",
            "scenario_portfolio_drop": "sell_all",
            "scenario_single_stock_crash": "cut_loss",
            "scenario_market_crash_relative": "too_much",
            "expected_annual_return": "lt5",
            "return_vs_stability": "ultra_steady",
            "min_acceptable_return": "positive",
            "knowledge_concepts": [],
            "knowledge_self_rating": 1,
            "legal_confirmations": [
                "age_18", "experience_acknowledged", "risk_acknowledged",
                "past_performance", "ai_advisory",
            ],
        }
        resp = client.put("/api/profile", json={"answers": conservative})
        assert resp.status_code == 200, resp.data
        body = resp.get_json() or {}
        # Pre-fix update_profile only knew V1 → would have returned "conservative"
        # (from calculate_profile_type). Post-fix returns the V2 type.
        assert body.get("profile_type") == "passive_index_hugger", (
            f"PUT must use V2 classifier, got {body.get('profile_type')}"
        )

    def test_put_v2_without_legal_rejected(self, app, client, auth_user):
        """PUT must enforce the same legal gate as POST."""
        # Seed a profile first.
        resp = client.post("/api/profile/onboarding", json={"answers": {}})
        assert resp.status_code == 200

        no_legal = self._full_v2()
        del no_legal["legal_confirmations"]
        resp = client.put("/api/profile", json={"answers": no_legal})
        assert resp.status_code == 400
