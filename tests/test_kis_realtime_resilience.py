"""Regression: KR realtime hardening (2026-06-08).

After fixing the EGW02004 outage, the 5s KR price structure was hardened so a
*transient* failure never produces a user-facing error:
  - parallel KR batch (was a serial N×per-call loop)
  - shared per-second throttle (no KIS rate-guard trips under parallelism)
  - stale fallback: last-known price (flagged ``stale``) instead of ``null``
  - bounded per-call timeout
  - /status KR health signal (no more silent degradation)

These tests lock that behavior in.
"""
from __future__ import annotations

import time

import requests

from services.data.realtime import RealtimeService
import services.data.realtime as rtmod

_VTS = "https://openapivts.koreainvestment.com:29443"


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def _ok(price):
    return _Resp({
        "rt_cd": "0", "msg_cd": "MCA00000",
        "output": {
            "stck_prpr": str(price), "stck_oprc": str(price),
            "stck_hgpr": str(price), "stck_lwpr": str(price),
            "acml_vol": "1000", "prdy_vrss": "0", "prdy_ctrt": "0",
        },
    })


def _fail():
    # Generic KIS failure (NOT EGW02004 — that path is the self-heal test).
    return _Resp({"rt_cd": "1", "msg_cd": "MCA00001", "output": {}})


def _svc(monkeypatch):
    rt = RealtimeService()
    rt.kis_available = True
    rt.kis_key = "k"
    rt.kis_secret = "s"
    rt.kis_base = _VTS
    rt._cache_ttl = 0  # force every call past the freshness short-circuit
    monkeypatch.setattr(rt, "_ensure_kis_ws", lambda: None)
    monkeypatch.setattr(rt, "_get_kis_token", lambda: "tok")
    monkeypatch.setattr(rt, "_get_fmp_price", lambda t: None)  # no FMP network
    return rt


def test_get_price_degrades_to_stale_not_null(monkeypatch):
    """After a prior success, a transient KIS failure serves last-known stale."""
    rt = _svc(monkeypatch)

    monkeypatch.setattr(requests, "get", lambda *a, **k: _ok(71000))
    p1 = rt.get_price("005930.KS")
    assert p1 and p1["price"] == 71000 and not p1.get("stale")

    # KIS now fails — must NOT vanish; serves last-known flagged stale.
    monkeypatch.setattr(requests, "get", lambda *a, **k: _fail())
    p2 = rt.get_price("005930.KS")
    assert p2 is not None, "price must degrade to stale, never vanish to None"
    assert p2["price"] == 71000
    assert p2["stale"] is True
    assert "stale_at" in p2


def test_get_price_returns_none_when_never_cached(monkeypatch):
    """No stale to serve (cold ticker that has never succeeded) → None."""
    rt = _svc(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _fail())
    assert rt.get_price("005930.KS") is None


def test_batch_resolves_multiple_kr_live(monkeypatch):
    """Parallel KR batch resolves every ticker (no serial-loop drop)."""
    rt = _svc(monkeypatch)
    prices = {"005930": 71000, "000660": 1900000, "035720": 38000}

    def fake_get(url, headers=None, params=None, timeout=None):
        return _ok(prices[params["FID_INPUT_ISCD"]])

    monkeypatch.setattr(requests, "get", fake_get)
    out = rt.get_prices_batch(["005930.KS", "000660.KS", "035720.KS"])

    assert set(out) == {"005930.KS", "000660.KS", "035720.KS"}
    assert out["000660.KS"]["price"] == 1900000
    assert all(not v.get("stale") for v in out.values())


def test_batch_serves_stale_for_failed_kr(monkeypatch):
    """A KR ticker that fails live but was cached degrades to stale in batch."""
    rt = _svc(monkeypatch)
    # Seed a prior good value.
    seed = {"ticker": "005930.KS", "price": 70000, "price_display": "₩70,000",
            "currency": "KRW", "source": "kis", "_ts": time.time() - 100}
    rt._price_cache["005930.KS"] = seed
    rt._price_cache["005930"] = seed

    monkeypatch.setattr(requests, "get", lambda *a, **k: _fail())  # live KIS fails
    out = rt.get_prices_batch(["005930.KS"])

    assert "005930.KS" in out, "failed KR ticker must not drop out of the batch"
    assert out["005930.KS"]["stale"] is True
    assert out["005930.KS"]["price"] == 70000


def test_batch_one_failure_does_not_sink_the_rest(monkeypatch):
    """One KR ticker raising/failing must not error the whole batch."""
    rt = _svc(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        code = params["FID_INPUT_ISCD"]
        if code == "000660":
            raise requests.RequestException("boom")  # one ticker explodes
        return _ok(71000)

    monkeypatch.setattr(requests, "get", fake_get)
    out = rt.get_prices_batch(["005930.KS", "000660.KS"])

    assert out["005930.KS"]["price"] == 71000  # healthy ticker still resolves
    assert "000660.KS" not in out  # exploding ticker simply absent (no crash)


def test_kr_health_tracks_success_then_failure(monkeypatch):
    """kr_health().degraded flips with the live-feed state."""
    rt = _svc(monkeypatch)

    monkeypatch.setattr(requests, "get", lambda *a, **k: _ok(71000))
    rt.get_price("005930.KS")
    h_ok = rt.kr_health()
    assert h_ok["degraded"] is False
    assert h_ok["last_ok_age_s"] is not None

    monkeypatch.setattr(requests, "get", lambda *a, **k: _fail())
    rt.get_price("005930.KS")
    assert rt.kr_health()["degraded"] is True


def test_quote_throttle_spaces_concurrent_calls():
    """The shared throttle enforces the min interval between quote calls."""
    rtmod._kis_quote_last_ts = 0.0  # reset module state
    rtmod._kis_quote_throttle()           # first call: no wait, stamps now
    t0 = time.time()
    rtmod._kis_quote_throttle()           # second: must wait ~min interval
    elapsed = time.time() - t0
    assert elapsed >= rtmod._KIS_QUOTE_MIN_INTERVAL * 0.8


# ── Public stale-status banner overlays live KR health ────────────────────

def test_stale_status_flags_kr_when_feed_degraded(client, monkeypatch):
    """A live KR outage surfaces on the public banner route immediately,
    even before the nightly ticker_health artifact would reflect it."""
    from services.container import realtime as _rt
    monkeypatch.setattr(
        _rt, "kr_health",
        lambda: {"degraded": True, "last_ok_age_s": None, "last_fail_age_s": 3.0},
    )
    resp = client.get("/api/data/stale-status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_stale"] is True
    assert "KR" in body["affected_markets"]


def test_stale_status_clean_when_kr_healthy(client, monkeypatch):
    """Healthy KR feed (+ no artifact on the test host) → no false alarm."""
    from services.container import realtime as _rt
    monkeypatch.setattr(
        _rt, "kr_health",
        lambda: {"degraded": False, "last_ok_age_s": 2.0, "last_fail_age_s": None},
    )
    resp = client.get("/api/data/stale-status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["is_stale"] is False
    assert "KR" not in body["affected_markets"]
