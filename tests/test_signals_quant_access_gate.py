"""§101 access-gate regression guard for routes/signals_quant.py (2026-05-25).

The 6 per-ticker quant signal endpoints (short-interest, insider, disposition,
ofi, sentiment-divergence, anchoring) previously analysed ANY ticker for any
authenticated user — arbitrary-ticker analysis reads as 미등록 투자자문업
(자본시장법 §101 gray zone). The fix adds
``is_user_allowed_ticker(current_user.id, ticker)`` at each entry, returning a
403 ``ticker_not_in_user_scope`` for tickers the user neither holds nor watches.

These tests pin both directions:
  - ticker NOT in scope → 403 (gate denies, before any data fetch)
  - ticker IN scope (seeded Position) → NOT 403 (gate passes; normal flow runs)

The herding endpoint (/api/signals/herding) takes no ticker and is intentionally
NOT gated — covered by the negative assertion below.
"""
from __future__ import annotations

import pytest

from extensions import db

# (path template, concrete ticker) — all 6 per-ticker gated endpoints.
_GATED_ENDPOINTS = [
    "/api/signals/short-interest/{t}",
    "/api/signals/insider/{t}",
    "/api/signals/disposition/{t}",
    "/api/signals/ofi/{t}",
    "/api/signals/sentiment-divergence/{t}",
    "/api/signals/anchoring/{t}",
]


def _seed_position(user, ticker: str, app):
    """Add a position so is_user_allowed_ticker passes for `ticker`."""
    from models import Position
    with app.app_context():
        p = Position(user_id=user["id"], ticker=ticker, shares=1.0, avg_cost=1.0)
        db.session.add(p)
        db.session.commit()


@pytest.mark.parametrize("path_tmpl", _GATED_ENDPOINTS)
def test_unowned_ticker_returns_403(path_tmpl, client, auth_user, app):
    """A ticker the user neither holds nor watches → 403 ticker_not_in_user_scope.

    The gate fires at function entry, before any FMP / OHLCV fetch, so no data
    mocking is needed for the denied path.
    """
    ticker = "ZZZZ"  # valid AAA-AAAAA format, not seeded for this user
    r = client.get(path_tmpl.format(t=ticker))
    assert r.status_code == 403, (
        f"{path_tmpl}: expected 403 for unowned ticker, got {r.status_code}"
    )
    body = r.get_json()
    assert body.get("error") == "ticker_not_in_user_scope", (
        f"{path_tmpl}: unexpected error body {body}"
    )


@pytest.mark.parametrize("path_tmpl", _GATED_ENDPOINTS)
def test_owned_ticker_passes_gate(path_tmpl, client, auth_user, app):
    """A ticker the user holds → gate passes (status is NOT 403).

    Downstream may still return 200/404/5xx depending on data availability;
    the gate's contract is only that it does not deny an in-scope ticker.
    """
    ticker = "AAPL"
    _seed_position(auth_user, ticker, app)
    r = client.get(path_tmpl.format(t=ticker))
    assert r.status_code != 403, (
        f"{path_tmpl}: in-scope ticker was wrongly denied (403)"
    )
    if r.status_code == 403:  # pragma: no cover — defensive
        return
    body = r.get_json() or {}
    assert body.get("error") != "ticker_not_in_user_scope"


def test_herding_endpoint_not_gated(client, auth_user, app):
    """/api/signals/herding takes no ticker → must not be access-gated."""
    r = client.get("/api/signals/herding")
    body = r.get_json() or {}
    # Whatever the data outcome, it must never be the ticker-scope 403.
    assert not (
        r.status_code == 403 and body.get("error") == "ticker_not_in_user_scope"
    ), "herding endpoint should not have a per-ticker access gate"
