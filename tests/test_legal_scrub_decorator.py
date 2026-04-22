"""Tests for the `legal_scrub_response` route decorator.

Verifies the boundary wrapper used by risk / defense / quant endpoints
to rewrite legally risky engine-generated text before it reaches the
client. Complements tests/test_legal_filter.py (which covers the raw
regex scrubber) by exercising the Flask-integration layer.
"""
from __future__ import annotations

import pytest
from flask import Flask, Blueprint, jsonify

from routes.decorators import legal_scrub_response, _deep_scrub


# ── _deep_scrub — structural walker ──────────────────────────────────────────

def test_deep_scrub_scrubs_nested_dict_strings():
    data = {
        "action": "매수 권고",
        "nested": {"advice": "SELL signal", "safe": "value"},
    }
    out = _deep_scrub(data)
    assert "매수 권고" not in out["action"]
    assert "정보 고지" in out["action"]
    assert "SELL signal" not in out["nested"]["advice"]
    assert out["nested"]["safe"] == "value"


def test_deep_scrub_walks_list_of_dicts():
    data = {"warnings": [{"msg": "BUY signal"}, {"msg": "매도 권고"}]}
    out = _deep_scrub(data)
    assert out["warnings"][0]["msg"] == "POSITIVE indicator"
    assert "정보 고지" in out["warnings"][1]["msg"]


def test_deep_scrub_passes_non_string_scalars_through():
    data = {"score": 87, "active": True, "ratio": 1.5, "none": None}
    assert _deep_scrub(data) == data


def test_deep_scrub_passes_unknown_types_through():
    # Tuples, sets, custom objects should pass through (not traversed).
    class Blob:
        pass
    blob = Blob()
    data = {"x": blob, "y": (1, 2)}
    out = _deep_scrub(data)
    assert out["x"] is blob
    assert out["y"] == (1, 2)


# ── legal_scrub_response — Flask view wrapper ────────────────────────────────

# NOTE: fixture is named `scrub_app` (not `app`) to avoid shadowing the
# session-scoped `app` fixture in tests/conftest.py that wires the full
# PivoxQuant test Flask app with SQLAlchemy bindings. A local Flask
# instance is all we need here — the decorator is DB-agnostic.
@pytest.fixture
def scrub_app():
    a = Flask(__name__)
    bp = Blueprint("t", __name__)

    @bp.route("/risky")
    @legal_scrub_response
    def risky():
        return jsonify({
            "action": "매수 권고 즉시",
            "warnings": ["SELL signal detected"],
            "score": 42,
        })

    @bp.route("/with-status")
    @legal_scrub_response
    def with_status():
        return jsonify({"message": "매도 권고 발생"}), 418

    @bp.route("/non-json")
    @legal_scrub_response
    def non_json():
        return "매수 권고 — raw text", 200

    a.register_blueprint(bp)
    return a


def test_decorator_scrubs_json_body(scrub_app):
    with scrub_app.test_client() as c:
        r = c.get("/risky")
        assert r.status_code == 200
        body = r.get_json()
        assert "매수 권고" not in body["action"]
        assert body["warnings"][0] == "NEGATIVE indicator detected"
        assert body["score"] == 42  # numbers pass through


def test_decorator_preserves_custom_status_code(scrub_app):
    with scrub_app.test_client() as c:
        r = c.get("/with-status")
        assert r.status_code == 418
        assert "매도 권고" not in r.get_json()["message"]


def test_decorator_passes_through_non_json_responses(scrub_app):
    with scrub_app.test_client() as c:
        r = c.get("/non-json")
        # Non-JSON body is NOT scrubbed — this is intentional; text/html
        # payloads are out of scope for this decorator. Non-JSON bodies
        # from risk/quant endpoints would be a separate design concern.
        assert r.status_code == 200
        assert "매수 권고" in r.get_data(as_text=True)
