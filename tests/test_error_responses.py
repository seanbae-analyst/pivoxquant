"""tests/test_error_responses.py — api_error() factory contract.

Pins the {error, error_kr, code} shape so future drift breaks loud.
Background: wave 13 structure audit found 393 jsonify error responses
with only 1 carrying error_kr — this helper + migration sweep closes
that gap; the tests below guard the helper itself.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _app_ctx(app):
    """All assertions touch jsonify, which needs an app context."""
    with app.app_context():
        yield


def test_api_error_minimal_shape():
    from services.error_responses import api_error

    response, status = api_error(en="x", kr="y", code="X", status=400)
    assert status == 400
    body = response.get_json()
    assert body == {"error": "x", "error_kr": "y", "code": "X"}


def test_api_error_default_code_and_status():
    from services.error_responses import api_error, DEFAULT_CODE

    response, status = api_error(en="e", kr="k")
    assert status == 500
    body = response.get_json()
    assert body["code"] == DEFAULT_CODE
    assert body["error"] == "e"
    assert body["error_kr"] == "k"


def test_api_error_extra_fields_merged():
    """Extra kwargs land in the response body alongside the canonical
    three keys — used for `detail`, `retry_after`, etc."""
    from services.error_responses import api_error

    response, _ = api_error(
        en="busy", kr="바쁨", code="BUSY", status=503,
        retry_after=60, detail="upstream timeout",
    )
    body = response.get_json()
    assert body["retry_after"] == 60
    assert body["detail"] == "upstream timeout"


def test_api_error_extras_cannot_override_reserved_keys():
    """Caller mistakes like passing `error=` as extra must NOT silently
    overwrite the canonical key. Guards against typo accidents."""
    from services.error_responses import api_error

    response, _ = api_error(
        en="real english", kr="real korean", code="REAL",
        error="HIJACKED", error_kr="HIJACKED_KR", code_override="HIJACKED",
    )
    body = response.get_json()
    assert body["error"] == "real english"
    assert body["error_kr"] == "real korean"
    assert body["code"] == "REAL"
    # Non-reserved extras still pass through.
    assert body["code_override"] == "HIJACKED"


def test_api_error_status_passes_through():
    """Common HTTP error codes all round-trip without coercion."""
    from services.error_responses import api_error

    for s in (400, 401, 403, 404, 409, 413, 422, 429, 500, 503):
        _, status = api_error(en="x", kr="y", code="X", status=s)
        assert status == s
