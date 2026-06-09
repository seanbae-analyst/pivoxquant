"""Regression: non-finite floats must never ship as invalid JSON.

Python's stdlib json (Flask's DefaultJSONProvider) emits the bare tokens
``NaN``/``Infinity``/``-Infinity``, which a browser ``response.json()`` rejects
— losing the *entire* payload. ``SafeJSONProvider`` coerces them to ``null`` at
the serialisation boundary so a single missed ``_finite_floats`` guard can't
ship a non-parseable body. See services/json_provider.py + app.create_app.
"""

import json
import math
import pathlib

import flask
import pytest

from services.json_provider import SafeJSONProvider, sanitize_non_finite


def _strict_loads(body: str):
    """Parse like a browser's JSON.parse: reject NaN/Infinity constants."""
    return json.loads(
        body, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s))
    )


def test_sanitize_replaces_non_finite_scalars():
    assert sanitize_non_finite(float("nan")) is None
    assert sanitize_non_finite(float("inf")) is None
    assert sanitize_non_finite(float("-inf")) is None
    assert sanitize_non_finite(1.5) == 1.5
    assert sanitize_non_finite(0.0) == 0.0
    assert sanitize_non_finite(7) == 7
    assert sanitize_non_finite("x") == "x"
    # bool is not a float subclass — must pass through untouched
    assert sanitize_non_finite(True) is True
    assert sanitize_non_finite(False) is False


def test_sanitize_nested_dict_list_tuple():
    out = sanitize_non_finite(
        {
            "a": [float("nan"), 2, {"b": float("inf")}],
            "t": (1.0, float("-inf")),
            "ok": 3.0,
        }
    )
    assert out == {"a": [None, 2, {"b": None}], "t": [1.0, None], "ok": 3.0}


def test_sanitize_clean_payload_returns_same_object():
    # No re-allocation on the common (all-finite) path.
    d = {"a": {"b": [1, 2, 3]}, "c": 1.0, "d": [True, "s", None]}
    assert sanitize_non_finite(d) is d


def test_sanitize_does_not_mutate_input():
    src = {"bad": float("nan"), "keep": 3.0}
    out = sanitize_non_finite(src)
    assert out is not src
    assert math.isnan(src["bad"])  # original left intact (caches stay safe)
    assert out["bad"] is None and out["keep"] == 3.0


def test_provider_emits_strict_valid_json():
    app = flask.Flask(__name__)
    app.json = SafeJSONProvider(app)
    with app.app_context():
        body = app.json.response(
            {"nan": float("nan"), "inf": float("inf"), "ok": 2.5, "b": True}
        ).get_data(as_text=True)
    parsed = _strict_loads(body)  # raises if any NaN/Infinity token leaked
    assert parsed == {"nan": None, "inf": None, "ok": 2.5, "b": True}


def test_premise_default_provider_ships_invalid_json():
    # Documents *why* SafeJSONProvider exists. If a future Flask makes the
    # default safe, this test flips and the provider can be reconsidered.
    app = flask.Flask(__name__)
    with app.app_context():
        body = app.json.response({"x": float("nan")}).get_data(as_text=True)
    with pytest.raises(ValueError):
        _strict_loads(body)


def test_create_app_wires_safe_json_provider():
    # Lock the wiring without paying create_app()'s boot cost.
    src = pathlib.Path(__file__).resolve().parent.parent.joinpath("app.py").read_text()
    assert "from services.json_provider import SafeJSONProvider" in src
    assert "app.json = SafeJSONProvider(app)" in src
