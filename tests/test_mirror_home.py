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
    assert data["gap"] == []

    # No type label on either side (CEO 2026-09-29 — mirrors show facts).
    assert "label" not in data["declared"]
    assert "tagline" not in data["declared"]
    assert "label" not in data["observed"]
    assert "bucket_changed" not in data["observed"]

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


def test_observed_stage_gap_and_radar(client, auth_user, add_position, monkeypatch):
    """With enough observed behaviour the endpoint surfaces the gap + observed
    radar — and never a persona name, 8-code or 3-bucket."""
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
            "persona": "growth",  # internal code; the endpoint must not surface it
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

    # No persona name at all — neither the code nor a 3-bucket label.
    assert "label" not in data["observed"]
    blob = json.dumps(data, ensure_ascii=False).lower()
    assert "growth" not in blob and "speculator" not in blob
    for name in ("성장형", "균형형", "수익형"):
        assert name not in blob


def _observed_double(features, present):
    return lambda *a, **k: {
        "features": features,
        "present": present,
        "trade_count": 6,
        "data_sparse": True,
        "persona": "balanced",
    }


def test_unmeasured_axes_never_reach_the_gap(client, auth_user, add_position, monkeypatch):
    """2026-09-10: below the classifier's evidence thresholds an axis keeps
    the 0.5 default and ``present`` marks it 0. Such an axis must not be
    compared against the declaration, however far the default sits from it."""
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    # 2026-09-29: ticker_diversity is measured from open positions on the mirror.
    add_position(auth_user["id"], ticker="AAPL", shares=1.0)
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


def test_no_measured_axis_means_no_gap(client, auth_user, add_position, monkeypatch):
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    features = {k: 0.1 for k in FEATURE_KEYS}
    present = {k: 0 for k in FEATURE_KEYS}
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    assert data["stage"] == "observed"
    assert data["gap"] == []
    assert data["radar"]["observed_axes"] == []


_LEGAL = ["age_18", "experience_acknowledged", "risk_acknowledged",
          "past_performance", "ai_advisory"]


def _onboard_v3(client, user, add_position, **overrides):
    # 온보딩은 보유 종목이 1개 이상 있어야 끝난다 (2026-09-28,
    # ONBOARDING_HOLDINGS_REQUIRED). 0주 행을 두어 게이트만 통과시키고,
    # 보유 종목 수(shares > 0)로 재는 축에는 영향을 주지 않는다.
    add_position(user["id"], ticker="ONBOARD", shares=0.0)
    answers = {
        "declared_holding": "months",
        "declared_frequency": "few",          # declared turnover 0.45
        "declared_positions": "focused",
        "declared_drawdown_response": "hold",  # risk_tolerance 6
        "record_habit": "sometimes",
        "legal_confirmations": list(_LEGAL),
    }
    answers.update(overrides)
    r = client.post("/api/profile/onboarding", json={"answers": answers})
    assert r.status_code == 200, r.get_json()


def test_declared_risk_is_never_an_observed_axis(client, auth_user, add_position, monkeypatch):
    """2026-09-29: the classifier's ``declared_risk`` is ``profile.risk_tolerance``
    — written from the same Q4 answer as the declared vector — so comparing it
    with the declaration is the answer against itself (always delta≈0, shown as
    "선언한 위험 감내 ↑0%p" and inflating the 정합도). It is not behaviour."""
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    _onboard_v3(client, auth_user, add_position)
    features = {k: 0.5 for k in FEATURE_KEYS}
    features["declared_risk"] = (6 - 1) / 9.0
    features["holding_period"] = 0.2       # declared months 0.85 → real gap
    present = {k: 1 for k in FEATURE_KEYS}
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    assert data["stage"] == "observed"
    assert "declared_risk" not in {g["key"] for g in data["gap"]}
    assert "declared_risk" not in data["radar"]["observed_axes"]


def test_near_zero_delta_is_not_a_gap_chip(client, auth_user, add_position, monkeypatch):
    """A chip that would read "↑0%p" says nothing — drop |delta| < 0.01."""
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    _onboard_v3(client, auth_user, add_position)
    features = {k: 0.5 for k in FEATURE_KEYS}
    features["turnover"] = 0.452           # declared "few" = 0.45
    features["holding_period"] = 0.2
    present = {k: 0 for k in FEATURE_KEYS}
    present["turnover"] = 1
    present["holding_period"] = 1
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    keys = [g["key"] for g in data["gap"]]
    assert keys == ["holding_period"]
    for g in data["gap"]:
        assert abs(g["delta"]) >= 0.01


def test_ticker_diversity_measured_from_open_positions(
    client, auth_user, add_position, monkeypatch,
):
    """2026-09-29: Q3 asks how many stocks you HOLD at once; the classifier's
    ticker_diversity counts distinct tickers TRADED in 30 days. A buy-and-hold
    user holding 20 names who traded 2 of them was shown a false top gap. The
    mirror measures this axis from open positions on the declared scale."""
    import pytest
    from services.profile.persona_analytics import _norm_log
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    _onboard_v3(client, auth_user, add_position, declared_positions="diversified")   # 16–25 → 0.90
    for i in range(20):
        add_position(auth_user["id"], ticker=f"T{i:02d}", shares=1.0)
    add_position(auth_user["id"], ticker="SOLD", shares=0.0)  # closed row
    features = {k: 0.5 for k in FEATURE_KEYS}
    features["ticker_diversity"] = _norm_log(2.0, floor=1.0, ceil=25.0)  # traded 2
    features["holding_period"] = 0.2
    present = {k: 0 for k in FEATURE_KEYS}
    present["ticker_diversity"] = 1
    present["holding_period"] = 1
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    keys = data["radar"]["keys"]
    obs = data["radar"]["observed"][keys.index("ticker_diversity")]
    assert obs == pytest.approx(_norm_log(20.0, floor=1.0, ceil=25.0), abs=1e-3)
    assert data["gap"][0]["key"] == "holding_period"
    for g in data["gap"]:
        if g["key"] == "ticker_diversity":
            assert abs(g["delta"]) < 0.1


def test_ticker_diversity_unmeasured_without_positions(client, auth_user, add_position, monkeypatch):
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    _onboard_v3(client, auth_user, add_position)
    features = {k: 0.5 for k in FEATURE_KEYS}
    features["ticker_diversity"] = 0.1
    present = {k: 1 for k in FEATURE_KEYS}
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    assert "ticker_diversity" not in data["radar"]["observed_axes"]
    assert "ticker_diversity" not in {g["key"] for g in data["gap"]}


def test_declared_carries_no_score(client, auth_user):
    """2026-09-29 — the declared side had a ``score`` (25 + risk_tolerance*7)
    that no screen rendered. Scores are not made; the declared side is the
    user's own answers (``declared.source``) projected onto the radar."""
    data = client.get("/api/mirror-home").get_json()
    assert "score" not in data["declared"]


def test_observed_inside_declared_bucket_is_not_a_gap(
    client, auth_user, add_position, monkeypatch,
):
    """2026-09-29: 답은 한 점이 아니라 구간이다. "1~3종목" 을 고르고 1종목을
    들고 있으면 선언대로다 — 전에는 구간 중앙값(0.20)과 비교해 ↓20%p 간극을
    헤드라인에 띄웠다."""
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    _onboard_v3(client, auth_user, add_position,
                declared_positions="ultra_focused", declared_frequency="few")
    add_position(auth_user["id"], ticker="AAPL", shares=1.0)     # 1종목 → 0.0
    features = {k: 0.5 for k in FEATURE_KEYS}
    features["turnover"] = 0.55     # "3~5번" 구간 [0.411, 0.589] 안 (중앙값 0.45)
    present = {k: 0 for k in FEATURE_KEYS}
    present["turnover"] = 1
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    assert data["stage"] == "observed"
    assert data["gap"] == []


def test_gap_outside_bucket_is_measured_to_the_nearest_edge(
    client, auth_user, add_position, monkeypatch,
):
    import pytest
    from services.profile.persona_classifier_v2 import FEATURE_KEYS
    from services.profile.questionnaire import DECLARED_RANGE_MAP
    _onboard_v3(client, auth_user, add_position, declared_frequency="few")
    features = {k: 0.5 for k in FEATURE_KEYS}
    features["turnover"] = 0.9
    present = {k: 0 for k in FEATURE_KEYS}
    present["turnover"] = 1
    monkeypatch.setattr("routes.mirror_home.classify_persona_multi",
                        _observed_double(features, present))

    data = client.get("/api/mirror-home").get_json()
    _, hi = DECLARED_RANGE_MAP["declared_frequency"]["few"]
    assert [g["key"] for g in data["gap"]] == ["turnover"]
    assert data["gap"][0]["direction"] == "up"
    assert data["gap"][0]["delta"] == pytest.approx(0.9 - hi, abs=1e-3)
