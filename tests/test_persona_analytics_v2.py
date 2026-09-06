"""
tests/test_persona_analytics_v2.py — multi-dimensional persona classifier
=========================================================================
Unit + integration coverage for
:mod:`services.profile.persona_classifier_v2` and the new
``GET /api/profile/persona-detail`` / ``persona-explain`` endpoints.

Contract:
    - 8 personas (unchanged from v1)
    - Returns a dict with ``persona``, ``confidence`` (0..100),
      ``features``, ``present``, ``ranking``, ``breakdown``.
    - Degrades gracefully for brand-new users (confidence low,
      ``data_sparse=True``).
    - Does NOT break v1 ``/api/profile/persona`` response shape.

External APIs are NOT called — everything runs against the test SQLite
DB via the fixtures declared in ``tests/conftest.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _add_trades(app, user_id: int, specs: list[dict]) -> None:
    from extensions import db
    from models import TradeHistory

    now = _utc_now()
    with app.app_context():
        for s in specs:
            db.session.add(TradeHistory(
                user_id=user_id,
                ticker=s["ticker"],
                action=s["action"],
                shares=float(s["shares"]),
                price_per_share=float(s.get("price", 100.0)),
                total_value=float(s.get("shares", 1)) * float(s.get("price", 100.0)),
                pnl=float(s.get("pnl", 0.0)),
                traded_at=now - timedelta(days=float(s.get("days_ago", 1))),
            ))
        db.session.commit()


def _set_profile(app, user_id: int, profile_type: str = "growth", risk_tolerance: int = 7) -> None:
    from extensions import db
    from models import InvestmentProfile

    with app.app_context():
        p = InvestmentProfile.query.filter_by(user_id=user_id).first()
        if p is None:
            p = InvestmentProfile(user_id=user_id)
            db.session.add(p)
        p.profile_type = profile_type
        p.risk_tolerance = risk_tolerance
        p.apply_preset()
        db.session.commit()


def _add_pulse(app, user_id: int, confidences: list[int]) -> None:
    from extensions import db
    from models import WeeklyPulse
    now = _utc_now()
    with app.app_context():
        for i, c in enumerate(confidences):
            db.session.add(WeeklyPulse(
                user_id=user_id,
                mood=3,
                confidence=int(c),
                worry="",
                topics="[]",
                learn="",
                cadence="weekly",
                submitted_at=now - timedelta(days=7 * i),
            ))
        db.session.commit()


def _add_feedback(app, user_id: int, votes: list[str]) -> None:
    from extensions import db
    from models import ArtifactFeedback
    now = _utc_now()
    with app.app_context():
        for i, v in enumerate(votes):
            db.session.add(ArtifactFeedback(
                user_id=user_id,
                artifact_id=f"memo-{i}",
                section="opener",
                vote=v,
                created_at=now - timedelta(days=i),
            ))
        db.session.commit()


def _build_daytrader_specs(n_pairs: int = 15) -> list[dict]:
    """Intraday BUY/SELL pairs — tiny hold time, high turnover."""
    specs = []
    for i in range(n_pairs):
        specs.append({"ticker": "AAPL", "action": "BUY",  "shares": 10, "price": 150, "days_ago": 10 - i * 0.3, "pnl": 0.0})
        specs.append({"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 151, "days_ago": 10 - i * 0.3 - 0.01, "pnl": 10.0})
    return specs


def _build_value_specs() -> list[dict]:
    """Long-hold, diversified — Value CFO."""
    specs = []
    tickers = ["AAPL", "BRK", "KO", "JNJ", "PG", "WMT", "XOM", "CVX", "MCD"]
    for i, tk in enumerate(tickers):
        specs.append({"ticker": tk, "action": "BUY", "shares": 10, "price": 100, "days_ago": 180 - i})
    # Two realized trades to compute hold times (both wins — long hold).
    specs.append({"ticker": "AAPL", "action": "SELL", "shares": 5, "price": 130, "days_ago": 10, "pnl": 150.0})
    specs.append({"ticker": "KO", "action": "SELL", "shares": 5, "price": 115, "days_ago": 5, "pnl": 75.0})
    return specs


# ═════════════════════════════════════════════════════════════════════
# Unit: classify_persona_multi — pure function on the DB
# ═════════════════════════════════════════════════════════════════════

class TestClassifyPersonaMulti:
    def test_empty_user_returns_balanced_fallback_low_confidence(self, app, auth_user):
        from services.profile import classify_persona_multi
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        assert r["persona"] in ("balanced", "beginner", "growth", "value",
                                "income", "quant", "speculator", "daytrader")
        # Brand-new users get low confidence.
        assert 0 <= r["confidence"] <= 60
        assert r["data_sparse"] is True
        assert r["trade_count"] == 0
        # Every feature must appear in the vector.
        assert set(r["features"].keys()) == {
            "holding_period", "turnover", "sector_diversity",
            "ticker_diversity", "hold_variance", "loss_cut_discipline",
            "declared_risk", "conviction_stability", "feedback_engagement",
        }

    def test_features_all_in_unit_interval(self, app, auth_user):
        from services.profile import classify_persona_multi
        _set_profile(app, auth_user["id"], profile_type="growth", risk_tolerance=8)
        _add_trades(app, auth_user["id"], _build_daytrader_specs(12))
        _add_pulse(app, auth_user["id"], [4, 4, 5])
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        for k, v in r["features"].items():
            assert 0.0 <= v <= 1.0, f"feature {k} out of [0,1]: {v}"

    def test_daytrader_pattern_classifies_toward_daytrader_family(self, app, auth_user):
        from services.profile import classify_persona_multi
        _set_profile(app, auth_user["id"], profile_type="aggressive", risk_tolerance=9)
        _add_trades(app, auth_user["id"], _build_daytrader_specs(20))
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        # Extremely short-hold / high-turnover pattern must pick one of
        # the short-horizon personas.
        assert r["persona"] in ("daytrader", "speculator", "growth")
        assert r["features"]["turnover"] > 0.5
        assert r["features"]["holding_period"] < 0.3
        assert r["data_sparse"] is False

    def test_value_pattern_classifies_toward_long_hold_family(self, app, auth_user):
        from services.profile import classify_persona_multi
        _set_profile(app, auth_user["id"], profile_type="value_hunter", risk_tolerance=4)
        _add_trades(app, auth_user["id"], _build_value_specs())
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        assert r["persona"] in ("value", "balanced", "income", "beginner", "quant")
        assert r["features"]["holding_period"] > 0.4
        # Value-hunter fixture uses 2 unique tickers (AAPL + KO) → log(2)/log(25) ≈ 0.215.
        # Assert > 0.2 (proves ticker_diversity > default 0.0/0.5 floor, i.e. present=1).
        assert r["features"]["ticker_diversity"] > 0.2

    def test_ranking_is_sorted_descending(self, app, auth_user):
        from services.profile import classify_persona_multi
        _add_trades(app, auth_user["id"], _build_daytrader_specs(10))
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        sims = [row["similarity"] for row in r["ranking"]]
        assert sims == sorted(sims, reverse=True)
        # 8 personas, 8 rows.
        assert len(r["ranking"]) == 8

    def test_breakdown_contains_all_contributing_features_sorted(self, app, auth_user):
        """breakdown covers every axis that actually took part, in order.

        2026-09-02: this used to assert breakdown == the full 9-key feature
        vector. It no longer does, and the difference is deliberate rather
        than incidental — ``feedback_engagement`` is weighted 0.0 because it
        reads deleted artefact data (see FEATURE_WEIGHTS). The raw ``features``
        vector still carries all nine (it is the snapshot/export schema), but
        ``breakdown`` answers "why this persona", so an axis the maths never
        used has no row there. The invariant being checked is unchanged in
        spirit: breakdown is complete over contributing axes, and sorted.
        """
        from services.profile.persona_classifier_v2 import FEATURE_WEIGHTS
        from services.profile import classify_persona_multi
        _add_trades(app, auth_user["id"], _build_value_specs())
        _set_profile(app, auth_user["id"], risk_tolerance=5)
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        features_in_breakdown = [row["feature"] for row in r["breakdown"]]
        contributing = {k for k in r["features"] if FEATURE_WEIGHTS[k] > 0}
        assert set(features_in_breakdown) == contributing
        # every listed row genuinely contributed
        assert all(row["weight"] > 0 for row in r["breakdown"])
        contribs = [row["closeness"] * row["weight"] for row in r["breakdown"]]
        assert contribs == sorted(contribs, reverse=True)

    def test_dormant_axis_cannot_cap_confidence(self, app, auth_user):
        """A structurally-uncomputable axis must not sit in the evidence ratio.

        ``feedback_engagement`` can never be `present` (its source table is
        never written any more), so if it still carried weight, evidence_ratio
        could never reach 1.0 and confidence was silently capped for every
        user. Weight 0 is what makes a full-evidence user reachable.
        """
        from services.profile.persona_classifier_v2 import (
            FEATURE_KEYS, FEATURE_WEIGHTS,
        )
        assert FEATURE_WEIGHTS["feedback_engagement"] == 0.0
        # the axis is kept (revivable) but contributes nothing
        assert "feedback_engagement" in FEATURE_KEYS
        total_w = sum(FEATURE_WEIGHTS.values())
        computable_w = sum(
            FEATURE_WEIGHTS[k] for k in FEATURE_KEYS
            if k != "feedback_engagement"
        )
        assert total_w == computable_w, (
            "a weighted axis that can never be present would cap confidence"
        )

    def test_present_mask_reflects_sparse_data(self, app, auth_user):
        from services.profile import classify_persona_multi
        # Only a few trades → observation dimensions should NOT be marked present.
        _add_trades(app, auth_user["id"], [
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 150, "days_ago": 5},
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 160, "days_ago": 2},
        ])
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        # holding_period / sector_diversity / hold_variance / loss_cut_discipline
        # all gated on ``MIN_TRADES_FOR_OBSERVATION = 10``.
        assert r["present"]["holding_period"] == 0
        assert r["present"]["sector_diversity"] == 0
        assert r["present"]["hold_variance"] == 0
        assert r["present"]["loss_cut_discipline"] == 0
        # turnover + ticker_diversity are gated on "any trade".
        assert r["present"]["turnover"] == 1
        assert r["present"]["ticker_diversity"] == 1

    def test_confidence_increases_with_evidence(self, app, auth_user):
        from services.profile import classify_persona_multi
        # Phase 1 — minimal data
        _add_trades(app, auth_user["id"], [
            {"ticker": "AAPL", "action": "BUY",  "shares": 10, "price": 150, "days_ago": 5},
        ])
        with app.app_context():
            r_low = classify_persona_multi(auth_user["id"])
        c_low = r_low["confidence"]

        # Phase 2 — richer data (trades, profile, pulse, feedback)
        _set_profile(app, auth_user["id"], profile_type="growth", risk_tolerance=7)
        _add_trades(app, auth_user["id"], _build_daytrader_specs(15))
        _add_pulse(app, auth_user["id"], [4, 4, 5, 4, 5])
        _add_feedback(app, auth_user["id"], ["useful"] * 5 + ["meh"] * 2)

        with app.app_context():
            r_high = classify_persona_multi(auth_user["id"])
        c_high = r_high["confidence"]
        assert c_high >= c_low

    def test_declared_persona_echoed(self, app, auth_user):
        from services.profile import classify_persona_multi
        _set_profile(app, auth_user["id"], profile_type="value_hunter")
        with app.app_context():
            r = classify_persona_multi(auth_user["id"])
        assert r["declared_persona"] == "value"

    def test_window_days_respected(self, app, auth_user):
        from services.profile import classify_persona_multi
        # Old trade — 200 days ago.
        _add_trades(app, auth_user["id"], [
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 100, "days_ago": 200},
        ])
        with app.app_context():
            r_30 = classify_persona_multi(auth_user["id"], window_days=30)
        assert r_30["trade_count"] == 0  # outside window
        with app.app_context():
            r_365 = classify_persona_multi(auth_user["id"], window_days=365)
        assert r_365["trade_count"] == 1


# ═════════════════════════════════════════════════════════════════════
# Unit: explain_persona_classification + get_persona_confidence
# ═════════════════════════════════════════════════════════════════════

class TestExplainAndConfidenceHelpers:
    def test_explain_returns_slim_payload(self, app, auth_user):
        from services.profile import explain_persona_classification
        _add_trades(app, auth_user["id"], _build_daytrader_specs(12))
        with app.app_context():
            r = explain_persona_classification(auth_user["id"])
        assert set(r.keys()) == {"persona", "label", "confidence", "breakdown", "features"}
        assert 0 <= r["confidence"] <= 100

    def test_get_persona_confidence_returns_int(self, app, auth_user):
        from services.profile import get_persona_confidence
        with app.app_context():
            c = get_persona_confidence(auth_user["id"])
        assert isinstance(c, int) and 0 <= c <= 100


# ═════════════════════════════════════════════════════════════════════
# API: GET /api/profile/persona-detail
# ═════════════════════════════════════════════════════════════════════

class TestPersonaDetailEndpoint:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile/persona-detail")
        assert r.status_code == 401

    def test_empty_user_returns_200_with_valid_payload(self, client, auth_user):
        r = client.get("/api/profile/persona-detail")
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert "persona" in d and "confidence" in d
        assert d["data_sparse"] is True
        assert 0 <= d["confidence"] <= 100
        assert isinstance(d["ranking"], list) and len(d["ranking"]) == 8

    def test_with_trades_returns_populated_features(self, app, client, auth_user):
        _set_profile(app, auth_user["id"], profile_type="growth", risk_tolerance=7)
        _add_trades(app, auth_user["id"], _build_daytrader_specs(15))
        r = client.get("/api/profile/persona-detail")
        assert r.status_code == 200
        d = r.get_json()
        assert d["trade_count"] > 0
        assert d["features"]["turnover"] > 0.0
        # Breakdown entries are structured dicts.
        for row in d["breakdown"]:
            assert set(row.keys()) >= {"feature", "label", "value", "centroid", "closeness", "weight"}

    def test_window_days_query_param_respected(self, app, client, auth_user):
        _add_trades(app, auth_user["id"], [
            {"ticker": "AAPL", "action": "BUY", "shares": 10, "price": 100, "days_ago": 200},
        ])
        r_30 = client.get("/api/profile/persona-detail?window_days=30")
        r_365 = client.get("/api/profile/persona-detail?window_days=365")
        assert r_30.status_code == 200 and r_365.status_code == 200
        assert r_30.get_json()["window_days"] == 30
        assert r_365.get_json()["window_days"] == 365
        assert r_30.get_json()["trade_count"] == 0
        assert r_365.get_json()["trade_count"] == 1

    def test_window_days_bounds_clamped(self, client, auth_user):
        # Absurdly small / huge values are clamped to [30, 365].
        r_tiny = client.get("/api/profile/persona-detail?window_days=0")
        r_huge = client.get("/api/profile/persona-detail?window_days=99999")
        assert r_tiny.get_json()["window_days"] == 30
        assert r_huge.get_json()["window_days"] == 365

    def test_user_scoping(self, app, client, make_user, auth_user):
        _add_trades(app, auth_user["id"], _build_daytrader_specs(12))
        other = make_user(email="scope@test.com")
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={
            "email": other["email"], "password": other["password"],
        })
        r = client.get("/api/profile/persona-detail")
        assert r.status_code == 200
        # Other user has no trades → trade_count 0.
        assert r.get_json()["trade_count"] == 0


class TestPersonaExplainEndpoint:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile/persona-explain")
        assert r.status_code == 401

    def test_returns_slim_payload(self, client, auth_user):
        r = client.get("/api/profile/persona-explain")
        assert r.status_code == 200
        d = r.get_json()
        assert set(d.keys()) == {"persona", "label", "confidence", "breakdown", "features"}


# ═════════════════════════════════════════════════════════════════════
# Regression: v1 /api/profile/persona response shape preserved
# ═════════════════════════════════════════════════════════════════════

class TestV1BackwardCompat:
    def test_v1_persona_endpoint_untouched(self, client, auth_user):
        # v1 must continue to ship the same top-level keys.
        r = client.get("/api/profile/persona")
        assert r.status_code == 200
        d = r.get_json()
        assert {"declared", "observed", "sparkline", "last_computed_at", "drift"} <= set(d.keys())
        # observed windows unchanged.
        assert set(d["observed"].keys()) == {"window_30d", "window_60d", "window_90d"}

    def test_v1_does_not_depend_on_v2_side_effects(self, app, auth_user):
        """v1 must still work when the v2 classifier would be called separately."""
        from services.profile import compute_persona_response, classify_persona_multi
        with app.app_context():
            d1 = compute_persona_response(auth_user["id"])
            # Call v2 AFTER v1 — must not mutate v1 response.
            _ = classify_persona_multi(auth_user["id"])
            d1_again = compute_persona_response(auth_user["id"])
        assert d1["declared"] == d1_again["declared"]
        assert d1["observed"] == d1_again["observed"]
