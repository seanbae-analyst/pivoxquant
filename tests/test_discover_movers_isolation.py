"""tests/test_discover_movers_isolation.py — movers cross-user 격리 (privacy + §101).

Regression for the 2026-05-22 fix: /api/discover/movers derives gainers/losers
from the *per-user* discover_cache (a user's own holdings + watchlist, built
per-user in discover() for §101 isolation). The section cache key used to be
global (``movers:{region}``), so once user A computed movers, the fresh-hit
path served A's private watchlist tickers + prices to user B (TTL 1h).

The fix scopes the section cache key per-user (``movers:{region}:{uid}``).

These tests assert:
  1. The section cache key embeds the current user's id (uid scoping).
  2. After user A seeds + computes movers, user B (with a *different*
     per-user universe) never sees user A's tickers.
"""
from __future__ import annotations

import time


def _clear_section_cache():
    from services import cache_service
    cache_service.discover_section_cache_clear()


def _reset_swr_ttls():
    from services import cache_service
    cache_service.discover_section_cache_set_ttls(None, None)


def _seed_user_discover(uid, prefix, korean=False):
    """Plant analyzed rows into the per-user discover_cache so movers derive."""
    from services import cache_service
    rows = [
        {"ticker": f"{prefix}{i}", "name": f"{prefix} Stock {i}",
         "is_korean": korean, "price": 100.0 + i, "change_pct": (10 - i) * 0.7}
        for i in range(10)
    ]
    cache_service.discover_cache[uid] = {"data": rows, "ts": time.time()}


def _login(client, user):
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200, f"Login failed: {resp.data!r}"


class TestMoversCrossUserIsolation:
    def setup_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def teardown_method(self):
        _clear_section_cache()
        _reset_swr_ttls()

    def test_section_cache_key_is_per_user(self, client, auth_user):
        """After computing movers, the section cache key embeds the uid —
        no global ``movers:{region}`` entry leaks across users."""
        _seed_user_discover(auth_user["id"], "AAA")
        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 200

        from services import cache_service
        keys = list(cache_service._discover_section_cache.keys())
        assert any(str(auth_user["id"]) in k for k in keys), (
            f"expected a per-user movers key containing uid={auth_user['id']}, "
            f"got keys={keys}"
        )
        assert "movers:us" not in keys, (
            "global (non-uid) movers key must NOT exist — that is the leak"
        )

    def test_user_b_never_sees_user_a_tickers(self, client, make_user):
        """User A computes movers (AAA* tickers). User B has a different
        universe (BBB* tickers). B's response must contain only BBB*."""
        user_a = make_user(email="a@test.com")
        user_b = make_user(email="b@test.com")

        # User A: seed A-only universe + warm the movers cache.
        _seed_user_discover(user_a["id"], "AAA")
        _login(client, user_a)
        ra = client.get("/api/discover/movers?region=us")
        assert ra.status_code == 200
        a_tickers = {m["ticker"] for m in
                     ra.get_json().get("gainers", []) + ra.get_json().get("losers", [])}
        assert a_tickers and all(t.startswith("AAA") for t in a_tickers)

        # User B: seed B-only universe, log in (replaces session), call movers.
        _seed_user_discover(user_b["id"], "BBB")
        _login(client, user_b)
        rb = client.get("/api/discover/movers?region=us")
        assert rb.status_code == 200
        b_tickers = {m["ticker"] for m in
                     rb.get_json().get("gainers", []) + rb.get_json().get("losers", [])}

        # B must see ONLY its own universe — none of A's private tickers.
        assert b_tickers, "user B should derive its own movers"
        assert all(t.startswith("BBB") for t in b_tickers), (
            f"cross-user leak: user B saw {b_tickers - {t for t in b_tickers if t.startswith('BBB')}}"
        )
        assert not (a_tickers & b_tickers), "A and B universes must be disjoint"
