"""Tests for /api/mirror-home — the composed 거울 home read.

Covers: auth gate, the declared-only "new" stage for a fresh user, the
legal invariant that no 8-code engine persona ever surfaces, and twin
report surfacing.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal


def test_requires_auth(raw_client):
    assert raw_client.get("/api/mirror-home").status_code == 401


def test_new_stage_for_fresh_user(client, auth_user):
    r = client.get("/api/mirror-home")
    assert r.status_code == 200
    data = r.get_json()

    assert data["ok"] is True
    # Fresh user has no closed trades → declared-only "new" stage.
    assert data["stage"] == "new"
    assert data["observed"]["label"] is None
    assert data["gap"] == []

    # Declared label is always one of the 3 disclosed buckets.
    assert data["declared"]["label"] in {"성장형", "균형형", "수익형"}

    # Radar always carries the 9-axis declared shape; observed blank in "new".
    assert len(data["radar"]["keys"]) == 9
    assert len(data["radar"]["labels"]) == 9
    assert len(data["radar"]["declared"]) == 9
    assert data["radar"]["observed"] is None


def test_no_eight_code_persona_leaks(client, auth_user):
    """Legal invariant: short-horizon / non-disclosed personas never surface."""
    blob = json.dumps(client.get("/api/mirror-home").get_json(), ensure_ascii=False).lower()
    for code in ("speculator", "daytrader", "value", "quant", "beginner"):
        assert code not in blob, f"8-code persona '{code}' leaked into mirror-home"


def test_observed_stage_gap_and_radar(client, auth_user, monkeypatch):
    """With enough observed behaviour the endpoint surfaces the gap + observed
    radar, mapping the observed code to a 3-bucket label (never the 8-code)."""
    fake_features = {
        "holding_period": 0.45, "turnover": 0.35, "sector_diversity": 0.40,
        "ticker_diversity": 0.50, "hold_variance": 0.50, "loss_cut_discipline": 0.50,
        "declared_risk": 0.80, "conviction_stability": 0.60, "feedback_engagement": 0.55,
    }
    monkeypatch.setattr(
        "routes.mirror_home.classify_persona_multi",
        lambda *a, **k: {
            "features": fake_features,
            "trade_count": 20,
            "data_sparse": False,
            "persona": "growth",  # 8-code; endpoint must surface only the bucket
        },
    )

    data = client.get("/api/mirror-home").get_json()
    assert data["stage"] == "observed"

    # Gap is populated with neutral dimension facts (label + direction).
    assert 1 <= len(data["gap"]) <= 3
    for g in data["gap"]:
        assert g["direction"] in {"up", "down"}
        assert g["label"] and g["key"]

    # Observed radar shape present, 9 axes.
    assert data["radar"]["observed"] is not None
    assert len(data["radar"]["observed"]) == 9

    # Observed surfaced as a 3-bucket label only — the 8-code never leaks.
    assert data["observed"]["label"] in {"성장형", "균형형", "수익형"}
    blob = json.dumps(data, ensure_ascii=False).lower()
    assert "growth" not in blob and "speculator" not in blob


def _observed_double(features, present):
    return lambda *a, **k: {
        "features": features,
        "present": present,
        "trade_count": 6,
        "data_sparse": True,
        "persona": "balanced",
    }


def test_unmeasured_axes_never_reach_the_gap(client, auth_user, monkeypatch):
    """2026-09-10: below the classifier's evidence thresholds an axis keeps
    the 0.5 default and ``present`` marks it 0. Such an axis must not be
    compared against the declaration, however far the default sits from it."""
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    features = {k: 0.5 for k in FEATURE_KEYS}
    features["turnover"] = 0.9          # measured, and different
    present = {k: 0 for k in FEATURE_KEYS}
    present["turnover"] = 1
    present["ticker_diversity"] = 1
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    assert data["stage"] == "observed"
    keys = {g["key"] for g in data["gap"]}
    assert keys <= {"turnover", "ticker_diversity"}
    assert "holding_period" not in keys
    assert data["radar"]["observed_axes"] == ["turnover", "ticker_diversity"]


def test_no_measured_axis_means_no_gap(client, auth_user, monkeypatch):
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    features = {k: 0.1 for k in FEATURE_KEYS}
    present = {k: 0 for k in FEATURE_KEYS}
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    assert data["stage"] == "observed"
    assert data["gap"] == []
    assert data["radar"]["observed_axes"] == []
