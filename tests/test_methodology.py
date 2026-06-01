"""Tests for routes/methodology.py — Data-trust Stage 1 transparency surface.

Guards the public methodology / data-provenance endpoint that backs the
``/methodology`` page (see docs/strategy/DATA_TRUST_STRATEGY.md). Three things
matter and must never silently regress:

  1. Schema — the frontend (``MethodologyResponse`` in lib/types.ts) depends on
     these exact field names.
  2. Legal posture — observation-only surface, flag-gated behind login by
     default (METHODOLOGY_PUBLIC; Q-DT4). No 추천 / 조언 / 매수 / 매도 / buy /
     sell / hold may appear anywhere in the payload (mirrors the model_catalog
     observation-only guarantee).
  3. Provenance truthfulness — with no user context the data lineage must list
     ONLY the always-on system sources (FMP / SEC EDGAR / FRED) and never a
     broker (same rule as services/artifacts/data_source_resolver.py).
"""
from __future__ import annotations

import json

import pytest

_REQUIRED_FIELDS = {
    "ok", "categories", "category_counts", "total", "active",
    "models", "data_lineage", "risk_metrics", "reproducibility", "disclaimer",
}

# Word-boundary-sensitive for the English directives so we don't false-match
# inside larger words; the Korean tokens are unambiguous substrings.
_BANNED_KO = ("매수", "매도", "추천", "조언")
_BANNED_EN = (" buy ", " sell ", " hold ", "recommend", "advice")

# System sources are the only provenance a user-less public request may claim.
_SYSTEM_SOURCES = {"FMP v4", "SEC EDGAR", "FRED"}
_BROKER_SOURCES = {"Alpaca", "KIS"}


@pytest.fixture(autouse=True)
def _open_methodology_gate(monkeypatch):
    """Open the public flag for the schema / legal / provenance assertions.

    Those are gate-independent — the payload is identical once past the login
    wall — so the flag lets them exercise the 200 path. The dedicated gate
    tests below clear it to assert the default-locked posture.
    """
    monkeypatch.setenv("METHODOLOGY_PUBLIC", "1")


def _hit(client) -> dict:
    r = client.get("/api/methodology")
    assert r.status_code == 200, r.data
    data = r.get_json()
    assert isinstance(data, dict)
    assert _REQUIRED_FIELDS.issubset(data.keys()), (
        f"missing fields: {_REQUIRED_FIELDS - data.keys()}"
    )
    return data


def test_endpoint_returns_200_and_schema(client):
    data = _hit(client)
    assert data["ok"] is True
    assert isinstance(data["categories"], list) and data["categories"]
    assert isinstance(data["category_counts"], dict)
    assert isinstance(data["total"], int) and data["total"] > 0
    assert isinstance(data["active"], int) and 0 < data["active"] <= data["total"]
    assert isinstance(data["models"], list) and data["models"]
    assert isinstance(data["data_lineage"], list)
    assert isinstance(data["disclaimer"], str) and data["disclaimer"]


def test_category_counts_sum_to_total(client):
    data = _hit(client)
    assert sum(data["category_counts"].values()) == data["total"]
    # Every counted category is a declared category.
    assert set(data["category_counts"]).issubset(set(data["categories"]))


def test_every_model_carries_an_academic_source(client):
    """The academic source IS the reproducibility hook — it must be present."""
    data = _hit(client)
    for m in data["models"]:
        for field in ("name", "category", "module",
                      "description_kr", "description_en", "academic_source"):
            assert m.get(field), f"model {m.get('name')!r} missing {field}"
        assert m["category"] in data["categories"]


def test_no_banned_terms_anywhere(client):
    """Observation-only surface — zero advisory / order language."""
    data = _hit(client)
    blob = json.dumps(data, ensure_ascii=False)
    for tok in _BANNED_KO:
        assert tok not in blob, f"banned KO token leaked: {tok!r}"
    padded = f" {blob.lower()} "
    for tok in _BANNED_EN:
        assert tok not in padded, f"banned EN token leaked: {tok!r}"


def test_data_lineage_is_truthful_system_only(client):
    """No user context → only always-on system sources, never a broker."""
    data = _hit(client)
    sources = {row["source"] for row in data["data_lineage"]}
    assert sources.issubset(_SYSTEM_SOURCES), f"unexpected sources: {sources}"
    assert not (sources & _BROKER_SOURCES), "broker source leaked into public lineage"
    for row in data["data_lineage"]:
        for field in ("source", "description", "coverage"):
            assert row.get(field), f"lineage row missing {field}: {row}"


def test_risk_metrics_present_and_shaped(client):
    """Risk-metric methodology catalog — the risk-surface reproducibility anchor."""
    data = _hit(client)
    rm = data["risk_metrics"]
    assert isinstance(rm, list) and rm, "risk_metrics must be a non-empty list"
    for m in rm:
        for field in ("key", "label_kr", "label_en", "methodology", "academic_source"):
            assert m.get(field), f"risk metric {m.get('key')!r} missing {field}"


def test_reproducibility_statement_present_bilingual(client):
    data = _hit(client)
    repro = data["reproducibility"]
    assert isinstance(repro, dict)
    assert repro.get("statement_kr"), "missing KR reproducibility statement"
    assert repro.get("statement_en"), "missing EN reproducibility statement"


def test_locked_behind_login_by_default(client, monkeypatch):
    """Default (no METHODOLOGY_PUBLIC) → anonymous request is walled (Q-DT4)."""
    monkeypatch.delenv("METHODOLOGY_PUBLIC", raising=False)
    r = client.get("/api/methodology")
    assert r.status_code == 401
    assert r.get_json()["code"] == "SESSION_EXPIRED"


def test_authenticated_user_passes_the_gate(client, auth_user, monkeypatch):
    """A logged-in user reaches the surface even with the public flag off."""
    monkeypatch.delenv("METHODOLOGY_PUBLIC", raising=False)
    r = client.get("/api/methodology")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
