"""tests/test_discover_movers_sign.py — movers gainers/losers sign partition.

Regression for P1-A (2026-06-15 daily-sweep finding, routes/discover.py):
``losers = list(reversed(filtered))[:10]`` where ``filtered`` is sorted
change_pct DESCENDING. ``reversed`` = the smallest-GAIN end, NOT actual
decliners — so on an all-up or small (<20) KR pool the "하락 종목" slot
surfaced POSITIVE-% stocks, overlapping the gainers list.

Fix partitions by sign: gainers strictly > 0, losers strictly < 0
(largest loss first). Either side may legitimately be empty.
"""
from __future__ import annotations

import time


def _seed(uid, rows):
    from services import cache_service
    cache_service.discover_cache[uid] = {"data": rows, "ts": time.time()}


def _row(ticker, pct, korean=False):
    return {"ticker": ticker, "name": ticker, "is_korean": korean,
            "price": 100.0, "change_pct": pct}


def _clear():
    from services import cache_service
    cache_service.discover_section_cache_clear()
    cache_service.discover_section_cache_set_ttls(None, None)


def _login(client, user):
    r = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert r.status_code == 200


class TestMoversSignPartition:
    def setup_method(self):
        _clear()

    def teardown_method(self):
        _clear()

    def test_losers_are_strictly_negative_and_disjoint_from_gainers(self, client, auth_user):
        """Mixed tape: every loser < 0, every gainer > 0, no overlap."""
        rows = (
            [_row(f"UP{i}", (i + 1) * 1.5) for i in range(5)]      # +1.5 … +7.5
            + [_row(f"DN{i}", -(i + 1) * 1.2) for i in range(5)]    # -1.2 … -6.0
        )
        _seed(auth_user["id"], rows)
        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()

        gainers, losers = body.get("gainers", []), body.get("losers", [])
        assert gainers and losers
        assert all(m["change_pct"] > 0 for m in gainers), gainers
        assert all(m["change_pct"] < 0 for m in losers), (
            f"losers must be real decliners, got {[m['change_pct'] for m in losers]}"
        )
        # The original bug: a positive-% stock appearing in BOTH lists.
        g_tk, l_tk = {m["ticker"] for m in gainers}, {m["ticker"] for m in losers}
        assert not (g_tk & l_tk), f"gainer/loser overlap (the bug): {g_tk & l_tk}"
        # Losers ordered largest-loss-first.
        pcts = [m["change_pct"] for m in losers]
        assert pcts == sorted(pcts), f"losers must ascend (most negative first): {pcts}"

    def test_all_up_pool_yields_empty_losers_not_fake_positives(self, client, auth_user):
        """All-positive pool: losers is EMPTY (no fabricated positive-% 'losers')."""
        _seed(auth_user["id"], [_row(f"UP{i}", (i + 1) * 0.9) for i in range(8)])
        r = client.get("/api/discover/movers?region=us")
        assert r.status_code == 200
        body = r.get_json()
        assert len(body.get("gainers", [])) >= 3      # one-sided tape still serves
        assert body.get("losers", []) == [], (
            f"all-up day must show NO decliners, got {body.get('losers')}"
        )
