"""Smoke tests — fast end-to-end deploy-sanity checks.

Marked ``@pytest.mark.smoke`` so the pre-push hook can gate on them
(``PIVOX_PREPUSH_BLOCK=1 pytest -m smoke``). These exist to catch the kind
of deploy-breaking regression that bit prod in v46.2 (a missing migration
column made every authenticated request 500/503) — the cheapest possible
"is the app even alive and serving authenticated traffic" net.

Intentionally minimal and dependency-light: health probe, the auth gate on a
protected route, and a logged-in portfolio fetch. No external network, no
artefact rendering. Keep this file < a few seconds.
"""
import pytest


@pytest.mark.smoke
def test_health_ok(client):
    """/api/health returns 200 with status ok (no auth, cheap DB ping)."""
    resp = client.get("/api/health")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body is not None
    assert body.get("status") == "ok"
    # DB ping is best-effort but should report ok in the test app.
    assert body.get("db") in (None, "ok"), body


@pytest.mark.smoke
def test_protected_route_requires_auth(client):
    """A protected route rejects an unauthenticated request (no 500/leak)."""
    resp = client.get("/api/portfolio")
    assert resp.status_code == 401, resp.data


@pytest.mark.smoke
def test_login_then_portfolio_ok(client, auth_user):
    """After a real /login, the portfolio endpoint serves 200 JSON.

    Guards the v46.2 failure mode: an authenticated User query that 500s
    because the live schema drifted from the model.
    """
    resp = client.get("/api/portfolio")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert isinstance(body, (dict, list)), type(body)
