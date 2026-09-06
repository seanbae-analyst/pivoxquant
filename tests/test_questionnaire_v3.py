"""tests/test_questionnaire_v3.py — Questionnaire V3 (2026-09-06).

Design doc: docs/strategy/onboarding-questionnaire-v3_2026-09-06.md.

Contracts pinned here:

  S1  calculate_profile_v3 — rule table → 8-code persona; risk_tolerance
      1..10 from the drawdown answer; declared_vector carries ONLY the axes
      the user answered (never padded with 0.5).
  S2  Declared values sit on the observed feature scale — each bucket value
      lands between the _norm_log values of its neighbouring buckets.
  S3  GET /api/profile/questionnaire serves V3 (5 + legal); the legal block
      text no longer describes AI processing that was deleted.
  S4  POST /api/profile/onboarding with V3 ids persists the raw answers,
      the declared vector, risk_tolerance / time_horizon / profile_type,
      returns the user's statements verbatim, and never a grade.
  S5  The legal gate still fires for V3 (missing block → 400; partial → 400)
      and the empty-skip path is unchanged.
  S6  PUT /api/profile re-take accepts V3 and rewrites the stored answers.
  S7  /api/mirror-home uses the user's own declared axes when present
      (source="self", radar.declared on those axes == the answer) and the
      centroid otherwise (source="centroid", declared_axes == []).
  S8  The gap is computed only over declared axes.
"""
from __future__ import annotations

import json

import pytest

LEGAL = ["age_18", "experience_acknowledged", "risk_acknowledged",
         "past_performance", "ai_advisory"]


def _v3(**overrides) -> dict:
    ans = {
        "declared_holding": "months",
        "declared_frequency": "few",
        "declared_positions": "focused",
        "declared_drawdown_response": "hold",
        "record_habit": "sometimes",
        "legal_confirmations": list(LEGAL),
    }
    ans.update(overrides)
    return ans


# ═════════════════════════════════════════════════════════════════════════
# S1 — pure scorer
# ═════════════════════════════════════════════════════════════════════════

class TestCalculateProfileV3:
    def test_rule_table_examples(self):
        from services.profile.questionnaire import calculate_profile_v3 as f
        assert f(_v3(declared_holding="intraday"))["investor_type"] == "daytrader"
        assert f(_v3(declared_holding="days", declared_frequency="frequent"))["investor_type"] == "speculator"
        assert f(_v3(declared_holding="days", declared_frequency="few"))["investor_type"] == "growth"
        assert f(_v3(declared_holding="weeks"))["investor_type"] == "growth"
        assert f(_v3(declared_holding="months", declared_drawdown_response="hold"))["investor_type"] == "balanced"
        assert f(_v3(declared_holding="months", declared_drawdown_response="sell_half"))["investor_type"] == "income"
        assert f(_v3(declared_holding="years", declared_drawdown_response="buy_some"))["investor_type"] == "value"
        assert f(_v3(declared_holding="years", declared_drawdown_response="hold"))["investor_type"] == "income"
        assert f(_v3(declared_holding="months", record_habit="never"))["investor_type"] == "beginner"

    def test_every_output_is_a_canonical_persona_code(self):
        from services.profile.questionnaire import (
            calculate_profile_v3, QUESTIONNAIRE_V3,
        )
        from services.profile.persona_analytics import PERSONA_CODES, DECLARED_TO_PERSONA
        opts = {q["id"]: [o["value"] for o in q["options"]]
                for q in QUESTIONNAIRE_V3 if q["id"] != "legal_confirmations"}
        seen = set()
        for h in opts["declared_holding"]:
            for fr in opts["declared_frequency"]:
                for d in opts["declared_drawdown_response"]:
                    for r in opts["record_habit"]:
                        code = calculate_profile_v3(_v3(
                            declared_holding=h, declared_frequency=fr,
                            declared_drawdown_response=d, record_habit=r,
                        ))["investor_type"]
                        assert code in PERSONA_CODES
                        # Identity-mapped by the resolver → mirror/benchmark keep working.
                        assert DECLARED_TO_PERSONA[code] == code
                        seen.add(code)
        # quant is observed-only by design; every other code is reachable.
        assert seen == set(PERSONA_CODES) - {"quant"}

    def test_risk_tolerance_from_drawdown_answer(self):
        from services.profile.questionnaire import calculate_profile_v3 as f
        assert f(_v3(declared_drawdown_response="sell_all"))["risk_tolerance"] == 1
        assert f(_v3(declared_drawdown_response="hold"))["risk_tolerance"] == 6
        assert f(_v3(declared_drawdown_response="buy_heavy"))["risk_tolerance"] == 10
        # risk_score is kept for callers that still read the V2 name.
        assert f(_v3(declared_drawdown_response="buy_heavy"))["risk_score"] == 100

    def test_declared_vector_only_answered_axes(self):
        from services.profile.questionnaire import calculate_profile_v3 as f
        partial = {"declared_holding": "weeks", "legal_confirmations": list(LEGAL)}
        vec = f(partial)["declared_vector"]
        assert set(vec) == {"holding_period"}
        assert vec["holding_period"] == pytest.approx(0.60)

        full = f(_v3())["declared_vector"]
        assert set(full) == {"holding_period", "turnover", "ticker_diversity", "declared_risk"}
        # (rt - 1) / 9 — the classifier's own D7 projection.
        assert full["declared_risk"] == pytest.approx((6 - 1) / 9, abs=1e-3)

    def test_statements_are_verbatim_option_labels_in_question_order(self):
        from services.profile.questionnaire import calculate_profile_v3 as f
        st = f(_v3())["statements"]
        assert [s["id"] for s in st] == [
            "declared_holding", "declared_frequency", "declared_positions",
            "declared_drawdown_response", "record_habit",
        ]
        assert st[0]["label_kr"] == "몇 달"
        assert st[3]["label_kr"] == "그냥 둬요"
        # Unknown option value → dropped, not invented.
        st2 = f(_v3(declared_holding="nonsense"))["statements"]
        assert "declared_holding" not in {s["id"] for s in st2}

    def test_no_grade_fields(self):
        """V3 must not resurrect the V2 score/grade vocabulary."""
        from services.profile.questionnaire import calculate_profile_v3 as f
        out = f(_v3())
        for banned in ("knowledge_score", "ui_complexity", "capital_tier",
                       "expected_return", "max_drawdown_tolerance",
                       "loss_aversion_score", "volatility_tolerance"):
            assert banned not in out

    def test_is_v3_answers(self):
        from services.profile.questionnaire import is_v3_answers
        assert is_v3_answers(_v3()) is True
        assert is_v3_answers({"declared_holding": "days"}) is True
        assert is_v3_answers({"experience_years": "lt1"}) is False
        assert is_v3_answers({}) is False
        assert is_v3_answers(None) is False


# ═════════════════════════════════════════════════════════════════════════
# S2 — declared values share the observed scale
# ═════════════════════════════════════════════════════════════════════════

class TestDeclaredScale:
    def test_holding_buckets_bracket_norm_log(self):
        from services.profile.persona_analytics import _norm_log
        from services.profile.questionnaire import DECLARED_VECTOR_MAP
        m = DECLARED_VECTOR_MAP["declared_holding"]
        # "a few days" (~3d) < weeks (~21d) < months (~90d) < years (365d)
        assert m["intraday"] <= _norm_log(1.0, floor=1, ceil=180) + 0.05
        assert _norm_log(2, floor=1, ceil=180) <= m["days"] <= _norm_log(7, floor=1, ceil=180)
        assert _norm_log(14, floor=1, ceil=180) <= m["weeks"] <= _norm_log(30, floor=1, ceil=180)
        assert _norm_log(60, floor=1, ceil=180) <= m["months"] <= _norm_log(180, floor=1, ceil=180)
        assert m["years"] == 1.0

    def test_turnover_buckets_bracket_norm_log(self):
        from services.profile.persona_analytics import _norm_log
        from services.profile.questionnaire import DECLARED_VECTOR_MAP
        m = DECLARED_VECTOR_MAP["declared_frequency"]
        per_day = lambda per_month: per_month / 30.0  # noqa: E731
        assert _norm_log(per_day(3), floor=0.02, ceil=1.0) <= m["few"] <= _norm_log(per_day(5), floor=0.02, ceil=1.0)
        assert _norm_log(per_day(6), floor=0.02, ceil=1.0) <= m["moderate"] <= _norm_log(per_day(15), floor=0.02, ceil=1.0)
        assert _norm_log(per_day(16), floor=0.02, ceil=1.0) <= m["frequent"] <= 1.0
        assert m["daily"] == 1.0

    def test_ticker_buckets_bracket_norm_log(self):
        from services.profile.persona_analytics import _norm_log
        from services.profile.questionnaire import DECLARED_VECTOR_MAP
        m = DECLARED_VECTOR_MAP["declared_positions"]
        assert _norm_log(1, floor=1, ceil=25) <= m["ultra_focused"] <= _norm_log(3, floor=1, ceil=25)
        assert _norm_log(4, floor=1, ceil=25) <= m["focused"] <= _norm_log(8, floor=1, ceil=25)
        assert _norm_log(9, floor=1, ceil=25) <= m["moderate"] <= _norm_log(15, floor=1, ceil=25)
        assert _norm_log(16, floor=1, ceil=25) <= m["diversified"] <= 1.0
        assert m["broad"] == 1.0


# ═════════════════════════════════════════════════════════════════════════
# S3 — GET /questionnaire
# ═════════════════════════════════════════════════════════════════════════

class TestGetQuestionnaire:
    def test_default_is_v3(self, client):
        r = client.get("/api/profile/questionnaire")
        assert r.status_code == 200
        data = r.get_json()
        assert data["version"] == 3
        ids = [q["id"] for q in data["questions"]]
        assert ids == [
            "declared_holding", "declared_frequency", "declared_positions",
            "declared_drawdown_response", "record_habit", "legal_confirmations",
        ]

    def test_legal_block_no_longer_claims_ai_processing(self, client):
        """R0 residue: the AI pipeline was deleted 2026-09-01; the consent
        text must not describe it (both versions share the block)."""
        data = client.get("/api/profile/questionnaire").get_json()
        legal = [q for q in data["questions"] if q["id"] == "legal_confirmations"][0]
        blob = json.dumps(legal, ensure_ascii=False)
        assert "AI-generated" not in blob
        assert "AI 분석을 제공" not in blob
        assert "ai_advisory" in blob  # value kept so stored consents stay valid


# ═════════════════════════════════════════════════════════════════════════
# S4 / S5 — POST /onboarding
# ═════════════════════════════════════════════════════════════════════════

class TestSubmitOnboardingV3:
    def test_persists_answers_vector_and_columns(self, client, auth_user, app):
        r = client.post("/api/profile/onboarding", json={"answers": _v3()})
        assert r.status_code == 200, r.data
        data = r.get_json()
        assert data["ok"] is True
        assert data["questionnaire_version"] == 3
        assert data["profile_type"] == "balanced"
        assert [s["id"] for s in data["declared"]] == [
            "declared_holding", "declared_frequency", "declared_positions",
            "declared_drawdown_response", "record_habit",
        ]
        assert data["profile"]["risk_tolerance"] == 6
        assert data["profile"]["time_horizon"] == "medium"
        assert data["profile"]["questionnaire_version"] == 3
        assert set(data["profile"]["declared_vector"]) == {
            "holding_period", "turnover", "ticker_diversity", "declared_risk",
        }
        # No V2 grade vocabulary in the response.
        blob = json.dumps(data, ensure_ascii=False)
        for banned in ("knowledge_score", "capital_tier", "Quant engine"):
            assert banned not in blob

        from models import InvestmentProfile, User
        with app.app_context():
            row = InvestmentProfile.query.filter_by(user_id=auth_user["id"]).first()
            assert row.questionnaire_version == 3
            stored = row.onboarding_answers()
            assert stored["declared_holding"] == "months"
            assert stored["record_habit"] == "sometimes"
            # Consent is a record of its own, not a self-statement.
            assert "legal_confirmations" not in stored
            assert row.declared_vector()["holding_period"] == pytest.approx(0.85)
            u = User.query.get(auth_user["id"])
            assert u.onboarding_completed is True
            assert u.risk_profile == "balanced"
            assert u.onboarding_draft_json is None

    def test_missing_legal_block_rejected(self, client, auth_user):
        ans = _v3(); ans.pop("legal_confirmations")
        r = client.post("/api/profile/onboarding", json={"answers": ans})
        assert r.status_code == 400
        assert r.get_json()["code"] == "ONBOARDING_LEGAL_REQUIRED"

    def test_partial_legal_block_rejected(self, client, auth_user):
        r = client.post("/api/profile/onboarding", json={
            "answers": _v3(legal_confirmations=["age_18", "risk_acknowledged"]),
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "ONBOARDING_LEGAL_REQUIRED"

    def test_skip_path_unchanged(self, client, auth_user, app):
        r = client.post("/api/profile/onboarding", json={"answers": {}})
        assert r.status_code == 200
        from models import InvestmentProfile
        with app.app_context():
            row = InvestmentProfile.query.filter_by(user_id=auth_user["id"]).first()
            assert row.questionnaire_version is None
            assert row.declared_vector() == {}

    def test_legacy_v2_payload_rejected(self, client, auth_user, app):
        """V1/V2 questionnaires were removed 2026-09-06. An old client's
        payload must be refused, not silently classified."""
        v2 = {
            "experience_years": "1to3", "holding_period": "months",
            "trading_frequency": "few", "scenario_portfolio_drop": "hold",
            "legal_confirmations": list(LEGAL),
        }
        r = client.post("/api/profile/onboarding", json={"answers": v2})
        assert r.status_code == 400
        assert r.get_json()["code"] == "ONBOARDING_UNKNOWN_QUESTIONNAIRE"
        from models import User
        with app.app_context():
            assert User.query.get(auth_user["id"]).onboarding_completed is False


# ═════════════════════════════════════════════════════════════════════════
# S6 — PUT /profile re-take
# ═════════════════════════════════════════════════════════════════════════

class TestRetakeV3:
    def test_put_rewrites_declared_answers(self, client, auth_user, app):
        assert client.post("/api/profile/onboarding", json={"answers": _v3()}).status_code == 200
        r = client.put("/api/profile", json={
            "answers": _v3(declared_holding="intraday", declared_drawdown_response="sell_all"),
        })
        assert r.status_code == 200, r.data
        data = r.get_json()
        assert data["questionnaire_version"] == 3
        assert data["profile_type"] == "daytrader"
        assert data["profile"]["risk_tolerance"] == 1
        assert data["profile"]["time_horizon"] == "short"
        from models import InvestmentProfile
        with app.app_context():
            row = InvestmentProfile.query.filter_by(user_id=auth_user["id"]).first()
            assert row.onboarding_answers()["declared_holding"] == "intraday"
            assert row.declared_vector()["holding_period"] == 0.0

    def test_put_without_legal_rejected(self, client, auth_user):
        assert client.post("/api/profile/onboarding", json={"answers": _v3()}).status_code == 200
        ans = _v3(); ans.pop("legal_confirmations")
        r = client.put("/api/profile", json={"answers": ans})
        assert r.status_code == 400
        assert r.get_json()["code"] == "PROFILE_LEGAL_REQUIRED"


# ═════════════════════════════════════════════════════════════════════════
# S7 / S8 — /mirror-home compares against the user's own words
# ═════════════════════════════════════════════════════════════════════════

class TestMirrorUsesDeclaredVector:
    def test_centroid_fallback_when_nothing_declared(self, client, auth_user):
        data = client.get("/api/mirror-home").get_json()
        assert data["declared"]["source"] == "centroid"
        assert data["radar"]["declared_axes"] == []
        assert len(data["radar"]["declared"]) == 9

    def test_self_source_after_v3_onboarding(self, client, auth_user):
        assert client.post("/api/profile/onboarding", json={"answers": _v3(
            declared_holding="years", declared_frequency="rare",
            declared_positions="broad", declared_drawdown_response="buy_heavy",
        )}).status_code == 200
        data = client.get("/api/mirror-home").get_json()
        assert data["declared"]["source"] == "self"
        keys = data["radar"]["keys"]
        dec = data["radar"]["declared"]
        assert set(data["radar"]["declared_axes"]) == {
            "holding_period", "turnover", "ticker_diversity", "declared_risk",
        }
        assert dec[keys.index("holding_period")] == pytest.approx(1.0)
        assert dec[keys.index("turnover")] == pytest.approx(0.05)
        assert dec[keys.index("ticker_diversity")] == pytest.approx(1.0)
        assert dec[keys.index("declared_risk")] == pytest.approx(1.0, abs=1e-3)
        # Still one of the 3 disclosed buckets, never an 8-code.
        assert data["declared"]["label"] in {"성장형", "균형형", "수익형"}
        blob = json.dumps(data, ensure_ascii=False).lower()
        for code in ("speculator", "daytrader", "quant", "beginner"):
            assert code not in blob

    def test_gap_only_over_declared_axes(self, client, auth_user, monkeypatch):
        assert client.post("/api/profile/onboarding", json={"answers": _v3(
            declared_holding="years", declared_frequency="rare",
        )}).status_code == 200
        fake = {k: 0.5 for k in (
            "holding_period", "turnover", "sector_diversity", "ticker_diversity",
            "hold_variance", "loss_cut_discipline", "declared_risk",
            "conviction_stability", "feedback_engagement",
        )}
        # Huge divergence on an UNdeclared axis must not show up as a gap.
        fake["sector_diversity"] = 0.0
        fake["holding_period"] = 0.1   # declared 1.0 → real gap
        monkeypatch.setattr(
            "routes.mirror_home.classify_persona_multi",
            lambda *a, **k: {"features": fake, "trade_count": 20,
                             "data_sparse": False, "persona": "growth"},
        )
        data = client.get("/api/mirror-home").get_json()
        assert data["stage"] == "observed"
        gap_keys = [g["key"] for g in data["gap"]]
        assert "sector_diversity" not in gap_keys
        assert gap_keys[0] == "holding_period"
        assert data["gap"][0]["direction"] == "down"
        assert data["gap"][0]["declared"] == pytest.approx(1.0)
        assert set(gap_keys) <= {"holding_period", "turnover", "ticker_diversity", "declared_risk"}
