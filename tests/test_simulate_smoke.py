"""Smoke tests for routes/simulate.py — portfolio optimizer simulators.

Endpoints simulate HRP, Tail-Risk Parity, MaxDiv, ERC, MinVariance against
the user's persisted positions. With no positions, all should return a
graceful 'not enough positions' payload — never 500.
"""
from __future__ import annotations


class TestSimulateAuthSmoke:
    def test_unauthenticated_hrp_returns_401(self, client):
        r = client.get("/api/portfolio/simulate/hrp")
        assert r.status_code == 401

    def test_unauthenticated_trp_returns_401(self, client):
        r = client.get("/api/portfolio/simulate/trp")
        assert r.status_code == 401

    def test_unauthenticated_mdp_returns_401(self, client):
        r = client.get("/api/portfolio/simulate/mdp")
        assert r.status_code == 401

    def test_unauthenticated_erc_returns_401(self, client):
        r = client.get("/api/portfolio/simulate/erc")
        assert r.status_code == 401

    def test_unauthenticated_min_variance_returns_401(self, client):
        r = client.get("/api/portfolio/simulate/min-variance")
        assert r.status_code == 401


class TestSimulateEmptyPortfolioSmoke:
    """With <2 positions, every simulator should return a structured error."""

    def test_hrp_with_no_positions(self, client, auth_user):
        r = client.get("/api/portfolio/simulate/hrp")
        # Either a 200 with error key or a 4xx — must not 500.
        assert r.status_code < 500
        assert r.get_json() is not None

    def test_trp_with_no_positions(self, client, auth_user):
        r = client.get("/api/portfolio/simulate/trp")
        assert r.status_code < 500

    def test_mdp_with_no_positions(self, client, auth_user):
        r = client.get("/api/portfolio/simulate/mdp")
        assert r.status_code < 500

    def test_erc_with_no_positions(self, client, auth_user):
        r = client.get("/api/portfolio/simulate/erc")
        assert r.status_code < 500

    def test_min_variance_with_no_positions(self, client, auth_user):
        r = client.get("/api/portfolio/simulate/min-variance")
        assert r.status_code < 500
