"""tests/test_share_route.py — /api/portfolio/share/<token>.

Wave 11 (P1 critical path) — share_bp had zero HTTP test coverage. We
verify the public read path (no auth required) for the three failure
modes and the happy path.

  - Invalid/unknown token → 404.
  - Expired token → 410 Gone.
  - Valid live token → 200 with public-readable shape (no avg_cost).

We bypass the create endpoint and insert PortfolioShare rows directly so
each test pins an exact ``expires_at`` value.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


def _utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_share(app, user_id, *, expired=False, token=None):
    """Insert a PortfolioShare row directly. Returns the token."""
    from extensions import db
    from models.portfolio_share import PortfolioShare
    import secrets

    token = token or secrets.token_urlsafe(16)
    if expired:
        # 1 day in the past → /<token> must return 410.
        created = _utc_naive() - timedelta(days=8)
        expires = _utc_naive() - timedelta(days=1)
    else:
        created = _utc_naive()
        expires = _utc_naive() + timedelta(days=7)

    with app.app_context():
        share = PortfolioShare(
            user_id=user_id,
            token=token,
            created_at=created,
            expires_at=expires,
        )
        db.session.add(share)
        db.session.commit()
    return token


class TestShareInvalidToken:
    def test_share_invalid_token_404(self, raw_client):
        """Unknown token → 404 (not 410, not 500)."""
        r = raw_client.get("/api/portfolio/share/this-token-does-not-exist")
        assert r.status_code == 404
        assert "not found" in (r.get_json().get("error", "")).lower()


class TestShareExpiredToken:
    def test_share_expired_token_410(self, raw_client, app, make_user):
        """A row that exists but whose expires_at < now must return 410."""
        user = make_user(email="shareowner1@test.com")
        token = _make_share(app, user["id"], expired=True)

        r = raw_client.get(f"/api/portfolio/share/{token}")
        assert r.status_code == 410
        assert "expired" in (r.get_json().get("error", "")).lower()


class TestShareValidToken:
    def test_share_valid_token_200_public_read(
        self, raw_client, app, make_user
    ):
        """Live token → 200 with public-readable envelope.

        Critical: avg_cost / buy_fx_rate must NOT appear in the response —
        those are sensitive owner-only fields and the route deliberately
        excludes them. This test is the regression guard.
        """
        from extensions import db
        from models import Position

        user = make_user(email="shareowner2@test.com", name="Owner Two")
        token = _make_share(app, user["id"], expired=False)

        # Add one position so the response shape is non-trivial.
        with app.app_context():
            db.session.add(Position(
                user_id=user["id"],
                ticker="AAPL",
                shares=10.0,
                avg_cost=150.0,
                buy_fx_rate=1300.0,
            ))
            db.session.commit()

        r = raw_client.get(f"/api/portfolio/share/{token}")
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body.get("owner_name") == "Owner Two"
        assert isinstance(body.get("positions"), list)
        assert len(body["positions"]) == 1
        pos = body["positions"][0]
        # Public-readable fields must be present.
        for k in ("ticker", "shares", "price", "market_value", "pnl_pct"):
            assert k in pos, f"missing public field: {k}"
        # Sensitive fields must be absent.
        assert "avg_cost" not in pos, (
            "avg_cost leaked to public share response — privacy regression"
        )
        assert "buy_fx_rate" not in pos, (
            "buy_fx_rate leaked to public share response — privacy regression"
        )


class TestShareGetRateLimited:
    """Fix 3 (2026-05-22): the public GET endpoint must carry a per-endpoint
    rate limit consistent with the create/POST side (@general_rate_limit)."""

    def test_get_endpoint_has_rate_limit_decorator(self, app):
        """The view function must be wrapped by @general_rate_limit, exactly
        like its create/POST sibling. ``general_rate_limit`` (in security.py)
        uses ``@wraps`` so the name is preserved, but it adds a ``__wrapped__``
        attribute and the wrapper is defined in the ``security`` module.
        We assert the GET endpoint matches the known-decorated POST endpoint's
        wrapper shape."""
        get_view = app.view_functions["share.get_shared_portfolio"]
        post_view = app.view_functions["share.create_share"]  # known-decorated
        # Both must be wrapped (undecorated views have no __wrapped__).
        assert hasattr(post_view, "__wrapped__"), "test premise broken"
        assert hasattr(get_view, "__wrapped__"), (
            "share GET has no decorator wrapper — Fix 3 missing"
        )
        # The wrapper must actually wrap a DIFFERENT inner function (proving a
        # real decorator ran, not just a stray attribute), matching the POST.
        assert get_view.__wrapped__ is not get_view
        assert get_view.__wrapped__.__name__ == "get_shared_portfolio"

    def test_get_endpoint_429_when_limit_exceeded(
        self, raw_client, app, make_user, enable_rate_limit
    ):
        """With enforcement on, hammering the GET past 60/min returns 429 —
        proving the limit is live, not just decorative."""
        user = make_user(email="sharelimit@test.com")
        token = _make_share(app, user["id"], expired=False)
        saw_429 = False
        # general_rate_limit = 60/min; 70 calls must trip it.
        for _ in range(70):
            r = raw_client.get(f"/api/portfolio/share/{token}")
            if r.status_code == 429:
                saw_429 = True
                break
        assert saw_429, "share GET never returned 429 — rate limit not enforced"
