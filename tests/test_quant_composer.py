"""Quant Composer — Feature 1 + Feature 2 tests.

Coverage targets
----------------
- Catalog shape (40 models, 6 categories, every entry has every field).
- Persona presets — all 8 codes, exact composition counts per spec.
- Validate composition — happy path, unknown model, NaN/inf, range guard,
  bad type, max-count cap.
- Engine integration — empty composition is a no-op (backward compat),
  bounded ±50% authority, clamped to [0, 100].
- Routes — auth required (401), get/put round-trip, preset apply, backtest
  determinism, disclaimer present on every payload.
- Legal — every catalog description + every persona rationale passes
  ``contains_forbidden_term``.
"""
from __future__ import annotations

import json

import pytest

from services.legal.forbidden_terms import contains_forbidden_term
from services.quant.composer import (
    MAX_ENABLED_COUNT,
    PERSONA_QUANT_PRESETS,
    WEIGHT_MAX,
    apply_user_composition,
    get_persona_preset,
    validate_composition,
)
from services.quant.model_catalog import (
    CATEGORIES,
    MODEL_BY_NAME,
    MODEL_CATALOG,
)


# ═══════════════════════════════════════════════════════════════════════════
# Catalog shape
# ═══════════════════════════════════════════════════════════════════════════


class TestCatalog:
    def test_exactly_forty_models(self):
        assert len(MODEL_CATALOG) == 40

    def test_no_duplicate_names(self):
        names = [m["name"] for m in MODEL_CATALOG]
        assert len(set(names)) == 40

    def test_six_categories(self):
        assert set(CATEGORIES) == {
            "Quant Edge", "Risk", "Portfolio", "Signal", "AI", "System",
        }

    def test_every_model_has_required_fields(self):
        required = {
            "name", "category", "module",
            "description_kr", "description_en",
            "academic_source", "default_weight",
            "personas_recommended", "data_sparse_compatible",
        }
        for m in MODEL_CATALOG:
            missing = required - set(m.keys())
            assert not missing, f"{m.get('name')} missing fields: {missing}"

    def test_every_category_value_is_canonical(self):
        for m in MODEL_CATALOG:
            assert m["category"] in CATEGORIES, f"{m['name']} bad category {m['category']}"

    def test_default_weight_is_neutral(self):
        for m in MODEL_CATALOG:
            assert m["default_weight"] == 1.0

    def test_personas_recommended_uses_known_codes(self):
        valid = set(PERSONA_QUANT_PRESETS.keys())
        for m in MODEL_CATALOG:
            for code in m["personas_recommended"]:
                assert code in valid, f"{m['name']} references unknown persona {code!r}"


# ═══════════════════════════════════════════════════════════════════════════
# Persona presets — Feature 2 contract
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonaPresets:
    EXPECTED_COUNTS = {
        "beginner": 4, "income": 6, "value": 8, "balanced": 10,
        "growth": 14, "quant": 22, "speculator": 12, "daytrader": 8,
    }

    def test_all_eight_personas_defined(self):
        assert set(PERSONA_QUANT_PRESETS.keys()) == set(self.EXPECTED_COUNTS.keys())

    @pytest.mark.parametrize("persona,expected", list(EXPECTED_COUNTS.items()))
    def test_preset_counts_match_spec(self, persona, expected):
        spec = PERSONA_QUANT_PRESETS[persona]
        assert len(spec["enabled"]) == expected, (
            f"{persona} expected {expected} models, got {len(spec['enabled'])}"
        )

    def test_every_preset_references_only_catalogued_names(self):
        for persona, spec in PERSONA_QUANT_PRESETS.items():
            for name in spec["enabled"]:
                assert name in MODEL_BY_NAME
            for name in spec["weights"]:
                assert name in MODEL_BY_NAME

    def test_every_preset_has_rationale(self):
        for persona, spec in PERSONA_QUANT_PRESETS.items():
            assert spec["rationale"]
            assert isinstance(spec["rationale"], str)

    def test_get_persona_preset_returns_copy(self):
        first = get_persona_preset("balanced")
        first["enabled"].append("FAKE")
        second = get_persona_preset("balanced")
        assert "FAKE" not in second["enabled"]

    def test_get_persona_preset_unknown_returns_none(self):
        assert get_persona_preset("not_a_real_persona") is None
        assert get_persona_preset(None) is None  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateComposition:
    def test_empty_payload_is_valid(self):
        enabled, weights = validate_composition(None, None)
        assert enabled == []
        assert weights == {}

    def test_happy_path(self):
        enabled, weights = validate_composition(
            ["MeanReversion", "MinVariance"],
            {"MeanReversion": 1.5},
        )
        assert enabled == ["MeanReversion", "MinVariance"]
        assert weights == {"MeanReversion": 1.5}

    def test_unknown_model_in_enabled_rejected(self):
        with pytest.raises(ValueError, match="unknown model"):
            validate_composition(["NotARealModel"], {})

    def test_unknown_model_in_weights_rejected(self):
        with pytest.raises(ValueError, match="unknown model"):
            validate_composition([], {"FakeModel": 1.0})

    def test_nan_weight_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            validate_composition(["MeanReversion"], {"MeanReversion": float("nan")})

    def test_inf_weight_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            validate_composition(["MeanReversion"], {"MeanReversion": float("inf")})

    def test_negative_weight_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            validate_composition(["MeanReversion"], {"MeanReversion": -0.1})

    def test_too_large_weight_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            validate_composition(["MeanReversion"], {"MeanReversion": WEIGHT_MAX + 0.1})

    def test_bool_weight_rejected(self):
        with pytest.raises(ValueError, match="must be a number"):
            validate_composition(["MeanReversion"], {"MeanReversion": True})

    def test_non_string_enabled_rejected(self):
        with pytest.raises(ValueError):
            validate_composition([123], {})

    def test_duplicate_enabled_collapsed(self):
        enabled, _ = validate_composition(
            ["MeanReversion", "MeanReversion", "MinVariance"], {}
        )
        assert enabled == ["MeanReversion", "MinVariance"]

    def test_max_enabled_count_enforced(self):
        # 41 entries — over the 40 cap. Use repeats so the validation
        # bails on length BEFORE seeing a real name.
        enabled = ["MeanReversion"] * (MAX_ENABLED_COUNT + 1)
        with pytest.raises(ValueError, match="exceeds cap"):
            validate_composition(enabled, {})

    def test_non_list_enabled_rejected(self):
        with pytest.raises(ValueError, match="must be a list"):
            validate_composition("MeanReversion", {})  # type: ignore[arg-type]

    def test_non_dict_weights_rejected(self):
        with pytest.raises(ValueError, match="must be an object"):
            validate_composition([], [("a", 1.0)])  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# Engine integration — backward compat + bounded authority
# ═══════════════════════════════════════════════════════════════════════════


class TestApplyUserComposition:
    def test_none_user_id_is_noop(self):
        assert apply_user_composition(None, 75.0) == 75.0

    def test_empty_composition_is_noop(self, app, db_session, make_user):
        from models import InvestmentProfile
        with app.app_context():
            user = make_user(email="composer-empty@test.com")
            profile = InvestmentProfile(user_id=user["id"])
            db_session.add(profile)
            db_session.commit()
            # Default is empty list → no-op contract.
            assert apply_user_composition(user["id"], 60.0) == 60.0

    def test_neutral_weights_preserve_score(self, app, db_session, make_user):
        from models import InvestmentProfile
        with app.app_context():
            user = make_user(email="composer-neutral@test.com")
            profile = InvestmentProfile(
                user_id=user["id"],
                enabled_quant_models=json.dumps(["MeanReversion", "MinVariance"]),
                model_weights=json.dumps({"MeanReversion": 1.0, "MinVariance": 1.0}),
            )
            db_session.add(profile)
            db_session.commit()
            assert apply_user_composition(user["id"], 50.0) == 50.0

    def test_high_weights_amplify_within_envelope(self, app, db_session, make_user):
        from models import InvestmentProfile
        with app.app_context():
            user = make_user(email="composer-high@test.com")
            profile = InvestmentProfile(
                user_id=user["id"],
                enabled_quant_models=json.dumps(["MeanReversion"]),
                model_weights=json.dumps({"MeanReversion": 5.0}),
            )
            db_session.add(profile)
            db_session.commit()
            # 5.0 mean → clamped to 1.5× → 50 * 1.5 = 75
            assert apply_user_composition(user["id"], 50.0) == 75.0

    def test_zero_weights_dampen_within_envelope(self, app, db_session, make_user):
        from models import InvestmentProfile
        with app.app_context():
            user = make_user(email="composer-zero@test.com")
            profile = InvestmentProfile(
                user_id=user["id"],
                enabled_quant_models=json.dumps(["MeanReversion"]),
                model_weights=json.dumps({"MeanReversion": 0.0}),
            )
            db_session.add(profile)
            db_session.commit()
            # 0.0 mean → clamped to 0.5× lower bound → 50 * 0.5 = 25
            assert apply_user_composition(user["id"], 50.0) == 25.0

    def test_clamps_to_one_hundred(self, app, db_session, make_user):
        from models import InvestmentProfile
        with app.app_context():
            user = make_user(email="composer-clamp@test.com")
            profile = InvestmentProfile(
                user_id=user["id"],
                enabled_quant_models=json.dumps(["MeanReversion"]),
                model_weights=json.dumps({"MeanReversion": 5.0}),
            )
            db_session.add(profile)
            db_session.commit()
            # 95 * 1.5 = 142.5 → clamped to 100.0
            assert apply_user_composition(user["id"], 95.0) == 100.0

    def test_corrupt_json_falls_back_safely(self, app, db_session, make_user):
        from models import InvestmentProfile
        with app.app_context():
            user = make_user(email="composer-corrupt@test.com")
            profile = InvestmentProfile(
                user_id=user["id"],
                enabled_quant_models="not valid json[[[",
                model_weights="{also broken",
            )
            db_session.add(profile)
            db_session.commit()
            # Corrupt → empty → no-op contract preserved.
            assert apply_user_composition(user["id"], 70.0) == 70.0


# ═══════════════════════════════════════════════════════════════════════════
# Legal compliance — observation-only language across the whole module
# ═══════════════════════════════════════════════════════════════════════════


class TestLegalCleanliness:
    @pytest.mark.parametrize("model", MODEL_CATALOG, ids=lambda m: m["name"])
    def test_descriptions_pass_forbidden_term_filter(self, model):
        for field in ("description_kr", "description_en"):
            hit = contains_forbidden_term(model[field])
            assert hit is None, (
                f"{model['name']}.{field} contains forbidden term {hit!r}: "
                f"{model[field]!r}"
            )

    @pytest.mark.parametrize("persona", list(PERSONA_QUANT_PRESETS.keys()))
    def test_persona_rationale_passes_forbidden_term_filter(self, persona):
        rationale = PERSONA_QUANT_PRESETS[persona]["rationale"]
        hit = contains_forbidden_term(rationale)
        assert hit is None, f"{persona} rationale contains forbidden term {hit!r}"


# ═══════════════════════════════════════════════════════════════════════════
# Routes — HTTP integration tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def composer_user(app, client, make_user):
    """Create a user with InvestmentProfile and log them in."""
    from models import InvestmentProfile
    user = make_user(email="composer-routes@test.com")
    with app.app_context():
        from extensions import db as _db
        profile = InvestmentProfile(user_id=user["id"])
        _db.session.add(profile)
        _db.session.commit()
    resp = client.post("/api/auth/login", json={
        "email": user["email"],
        "password": user["password"],
    })
    assert resp.status_code == 200
    return user


class TestRoutes:
    def test_models_requires_auth(self, client):
        resp = client.get("/api/quant/composition/models")
        assert resp.status_code == 401

    def test_models_lists_forty(self, client, composer_user):
        resp = client.get("/api/quant/composition/models")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["total"] == 40
        assert len(data["models"]) == 40
        assert "disclaimer" in data
        assert set(data["category_counts"].keys()) == set(CATEGORIES)

    def test_get_composition_default_empty(self, client, composer_user):
        resp = client.get("/api/quant/composition")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["enabled"] == []
        assert data["weights"] == {}
        assert "disclaimer" in data

    def test_put_composition_round_trip(self, client, composer_user):
        body = {
            "enabled": ["MeanReversion", "VolatilityRegime"],
            "weights": {"MeanReversion": 1.2, "VolatilityRegime": 0.8},
        }
        resp = client.put("/api/quant/composition", json=body)
        assert resp.status_code == 200, resp.data
        data = resp.get_json()
        assert data["enabled"] == body["enabled"]
        assert data["weights"] == body["weights"]
        # Round-trip read.
        resp2 = client.get("/api/quant/composition")
        d2 = resp2.get_json()
        assert d2["enabled"] == body["enabled"]
        assert d2["weights"] == body["weights"]

    def test_put_composition_rejects_unknown_model(self, client, composer_user):
        resp = client.put("/api/quant/composition", json={
            "enabled": ["NotAModel"],
            "weights": {},
        })
        assert resp.status_code == 400
        assert "unknown model" in resp.get_json()["error"]

    def test_put_composition_rejects_bad_weight(self, client, composer_user):
        resp = client.put("/api/quant/composition", json={
            "enabled": ["MeanReversion"],
            "weights": {"MeanReversion": 999.0},
        })
        assert resp.status_code == 400

    def test_preset_apply_known_persona(self, client, composer_user):
        resp = client.post(
            "/api/quant/composition/preset",
            json={"persona_code": "balanced"},
        )
        assert resp.status_code == 200, resp.data
        data = resp.get_json()
        assert data["applied"] is True
        assert data["enabled_count"] == 10
        # Read back to confirm persistence.
        r2 = client.get("/api/quant/composition")
        d2 = r2.get_json()
        assert len(d2["enabled"]) == 10

    def test_preset_unknown_persona_returns_400(self, client, composer_user):
        resp = client.post(
            "/api/quant/composition/preset",
            json={"persona_code": "no_such_persona"},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "valid" in body
        assert "balanced" in body["valid"]

    def test_backtest_deterministic(self, client, composer_user):
        body = {
            "enabled": ["MeanReversion"],
            "weights": {"MeanReversion": 1.0},
            "ticker": "AAPL",
            "days": 90,
        }
        r1 = client.post("/api/quant/composition/backtest", json=body)
        r2 = client.post("/api/quant/composition/backtest", json=body)
        assert r1.status_code == 200
        assert r2.status_code == 200
        # `computed_at` is a wall-clock timestamp — strip before compare.
        d1 = {k: v for k, v in r1.get_json()["result"].items() if k != "computed_at"}
        d2 = {k: v for k, v in r2.get_json()["result"].items() if k != "computed_at"}
        assert d1 == d2
        assert "disclaimer" in r1.get_json()
        assert r1.get_json()["result"]["kind"] == "paper_simulation"

    def test_backtest_rejects_bad_days(self, client, composer_user):
        resp = client.post("/api/quant/composition/backtest", json={
            "enabled": [], "weights": {}, "ticker": "AAPL", "days": 999,
        })
        assert resp.status_code == 400

    def test_backtest_requires_ticker(self, client, composer_user):
        resp = client.post("/api/quant/composition/backtest", json={
            "enabled": [], "weights": {}, "days": 90,
        })
        assert resp.status_code == 400
