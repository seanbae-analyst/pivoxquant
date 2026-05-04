"""tests/test_quant_composer_route.py — Wave 10 P2 supplementary HTTP coverage.

Existing ``test_quant_composer.py::TestRoutes`` covers the happy paths
(round-trip, preset apply, backtest determinism). This file pins down the
**onboarding-incomplete branch** + assorted strict validation gaps that
were not previously asserted at the HTTP layer:

  - GET ``/api/quant/composition`` for a user with NO InvestmentProfile
    must return ``onboarded: False`` with empty enabled/weights, not 404.
  - PUT ``/api/quant/composition`` for a user with NO InvestmentProfile
    must return 404 with a clear error.
  - POST ``/api/quant/composition/preset`` with missing ``persona_code``
    field returns 400.
  - POST ``/api/quant/composition/backtest`` with ``days`` below the
    minimum (7) returns 400 — symmetric with the existing >365 case.

All payloads must carry ``disclaimer`` (paper / observation) — Wave 10
P2 explicitly flags every quant_composer response as legal-scrubbed.
"""
from __future__ import annotations


# ── GET — no InvestmentProfile yet ─────────────────────────────────────────


def test_get_composition_no_profile_returns_onboarded_false(
    app, client, make_user,
):
    """A logged-in user who has not finished onboarding (no
    ``InvestmentProfile`` row) gets a stable empty payload — not 404."""
    user = make_user(email="no-profile@test.com")
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200

    resp = client.get("/api/quant/composition")
    assert resp.status_code == 200, resp.data
    data = resp.get_json()
    assert data["ok"] is True
    assert data["enabled"] == []
    assert data["weights"] == {}
    assert data.get("onboarded") is False
    assert "disclaimer" in data and data["disclaimer"]


# ── PUT — no InvestmentProfile yet ─────────────────────────────────────────


def test_put_composition_no_profile_returns_404(app, client, make_user):
    """PUT requires an InvestmentProfile because we cannot fabricate the
    onboarding answers it carries — must be 404, not silent create."""
    user = make_user(email="put-no-profile@test.com")
    client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })

    resp = client.put("/api/quant/composition", json={
        "enabled": ["MeanReversion"],
        "weights": {"MeanReversion": 1.0},
    })
    assert resp.status_code == 404
    body = resp.get_json()
    assert "Investment profile" in body["error"]


# ── POST preset — missing persona_code ─────────────────────────────────────


def test_preset_missing_persona_code_returns_400(app, client, make_user):
    """Empty body / missing ``persona_code`` → 400 with informative error."""
    from models import InvestmentProfile
    from extensions import db as _db

    user = make_user(email="preset-missing@test.com")
    with app.app_context():
        _db.session.add(InvestmentProfile(user_id=user["id"]))
        _db.session.commit()
    client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })

    resp = client.post("/api/quant/composition/preset", json={})
    assert resp.status_code == 400
    assert "persona_code" in resp.get_json()["error"]


# ── POST backtest — days too small ─────────────────────────────────────────


def test_backtest_rejects_days_below_minimum(app, client, make_user):
    """``days`` must be in [7, 365]. The existing suite covers 999;
    this asserts the lower-bound branch (days=3 → 400)."""
    from models import InvestmentProfile
    from extensions import db as _db

    user = make_user(email="backtest-low@test.com")
    with app.app_context():
        _db.session.add(InvestmentProfile(user_id=user["id"]))
        _db.session.commit()
    client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })

    resp = client.post("/api/quant/composition/backtest", json={
        "enabled": [],
        "weights": {},
        "ticker": "AAPL",
        "days": 3,
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert "days" in body["error"]
