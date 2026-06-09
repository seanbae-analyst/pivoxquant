"""Regression: KIS app-key / domain mismatch self-heal (EGW02004).

Root cause (2026-06-08): the configured KIS app-key is a 모의투자(VTS) key,
but ``KIS_USE_REAL=1`` routed live-quote calls to the 실전(real) domain, which
rejects the VTS key with ``EGW02004`` ("실전투자 도메인은 모의투자 앱키로
호출하실 수 없습니다."). Live KR quotes then silently fell back to the daily
close, so prices looked frozen/wrong intraday.

These tests lock in the self-heal: on EGW02004 the realtime service flips to
the opposite KIS REST domain, re-pins the token there, and retries once — so
live KR prices keep flowing regardless of the env var. A correctly-configured
deployment never returns EGW02004, so the heal path stays inert there.
"""
from __future__ import annotations

import requests

from services.data.realtime import RealtimeService
from services.kis.token_manager import KISTokenManager, REST_URL_REAL, REST_URL_VTS

_REAL = "https://openapi.koreainvestment.com:9443"
_VTS = "https://openapivts.koreainvestment.com:29443"


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def test_realtime_self_heals_on_egw02004(monkeypatch):
    """EGW02004 on the real domain → auto-flip to VTS, retry, return price."""
    calls = {"n": 0, "urls": []}

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        calls["urls"].append(url)
        if calls["n"] == 1:
            # 실전 domain rejects the 모의 app-key.
            return _Resp({
                "rt_cd": "1", "msg_cd": "EGW02004",
                "msg1": "실전투자 도메인은 모의투자 앱키로 호출하실 수 없습니다.",
                "output": {},
            })
        # Corrected (VTS) domain returns a live quote.
        return _Resp({
            "rt_cd": "0", "msg_cd": "MCA00000",
            "output": {
                "stck_prpr": "71000", "stck_oprc": "70000",
                "stck_hgpr": "72000", "stck_lwpr": "69000",
                "acml_vol": "1234567", "prdy_vrss": "500", "prdy_ctrt": "0.71",
            },
        })

    monkeypatch.setattr(requests, "get", fake_get)

    rt = RealtimeService()
    rt.kis_available = True
    rt.kis_key = "k"
    rt.kis_secret = "s"
    rt.kis_base = _REAL  # simulate the misconfigured (KIS_USE_REAL=1 + VTS key) state
    monkeypatch.setattr(rt, "_ensure_kis_ws", lambda: None)
    monkeypatch.setattr(rt, "_get_kis_token", lambda: "tok")

    out = rt._get_kis_price("005930.KS")

    assert out is not None, "self-heal should recover a live price after EGW02004"
    assert out["price"] == 71000
    assert out["source"] == "kis"
    assert calls["n"] == 2, "should retry exactly once on the corrected domain"
    assert rt.kis_base == _VTS, "REST domain should flip real → VTS"
    assert rt._kis_domain_corrected is True
    # First call hit real, retry hit VTS.
    assert _REAL in calls["urls"][0]
    assert _VTS in calls["urls"][1]


def test_self_heal_does_not_loop_when_both_domains_reject(monkeypatch):
    """If EGW02004 persists after the flip, return None (no infinite recursion)."""
    calls = {"n": 0}

    def always_egw(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        return _Resp({"rt_cd": "1", "msg_cd": "EGW02004", "msg1": "x", "output": {}})

    monkeypatch.setattr(requests, "get", always_egw)

    rt = RealtimeService()
    rt.kis_available = True
    rt.kis_key = "k"
    rt.kis_secret = "s"
    rt.kis_base = _REAL
    monkeypatch.setattr(rt, "_ensure_kis_ws", lambda: None)
    monkeypatch.setattr(rt, "_get_kis_token", lambda: "tok")

    out = rt._get_kis_price("005930.KS")

    assert out is None
    assert calls["n"] == 2, "exactly one retry — guard prevents further recursion"


def test_healthy_config_never_triggers_heal(monkeypatch):
    """rt_cd=0 first try → no domain flip, no extra calls (heal path inert)."""
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        return _Resp({
            "rt_cd": "0", "msg_cd": "MCA00000",
            "output": {"stck_prpr": "71000", "stck_oprc": "70000",
                       "stck_hgpr": "72000", "stck_lwpr": "69000",
                       "acml_vol": "1", "prdy_vrss": "0", "prdy_ctrt": "0"},
        })

    monkeypatch.setattr(requests, "get", fake_get)

    rt = RealtimeService()
    rt.kis_available = True
    rt.kis_key = "k"
    rt.kis_secret = "s"
    rt.kis_base = _VTS
    monkeypatch.setattr(rt, "_ensure_kis_ws", lambda: None)
    monkeypatch.setattr(rt, "_get_kis_token", lambda: "tok")

    out = rt._get_kis_price("005930.KS")

    assert out is not None and out["price"] == 71000
    assert calls["n"] == 1
    assert rt.kis_base == _VTS, "domain unchanged on a healthy call"
    assert rt._kis_domain_corrected is False


def test_token_manager_force_domain_re_pins_and_clears(monkeypatch):
    """force_domain flips base_url + drops the cached token for re-mint."""
    monkeypatch.setenv("KIS_APP_KEY", "k")
    monkeypatch.setenv("KIS_APP_SECRET", "s")
    monkeypatch.setenv("KIS_USE_REAL", "1")  # start pinned to real
    tm = KISTokenManager()
    assert tm.base_url == REST_URL_REAL and tm.is_real is True

    tm._token = "stale-real-token"
    from datetime import datetime, timedelta, timezone
    tm._expires_at = datetime.now(timezone.utc) + timedelta(hours=5)

    tm.force_domain(use_real=False)

    assert tm.base_url == REST_URL_VTS
    assert tm.is_real is False
    assert tm._token is None, "cached real-domain token must be dropped"
    assert tm._expires_at is None

    # Idempotent: calling again on the same domain is a no-op.
    tm.force_domain(use_real=False)
    assert tm.base_url == REST_URL_VTS


def test_egw02004_correction_is_once_only_under_concurrency(monkeypatch):
    """Concurrent EGW02004 (the self-heal trigger) must flip the domain EXACTLY
    once. The pre-fix unguarded check-then-set let two threads both 'correct'
    and flip the domain back and forth, permanently stranding kis_base on the
    wrong endpoint (→ every later KIS call EGW02004 → silent stale until restart).
    """
    import threading
    import time as _time

    def always_egw(url, headers=None, params=None, timeout=None):
        _time.sleep(0.01)  # widen the window so an unguarded set would interleave
        return _Resp({"rt_cd": "1", "msg_cd": "EGW02004", "msg1": "x", "output": {}})

    monkeypatch.setattr(requests, "get", always_egw)

    force_calls = {"n": 0}

    class _FakeTM:
        def force_domain(self, use_real=False):
            force_calls["n"] += 1

    monkeypatch.setattr(
        "services.kis.token_manager.get_kis_token_manager",
        lambda: _FakeTM(),
    )

    rt = RealtimeService()
    rt.kis_available = True
    rt.kis_key = "k"
    rt.kis_secret = "s"
    rt.kis_base = _REAL  # misconfigured start (real domain + VTS key)
    monkeypatch.setattr(rt, "_ensure_kis_ws", lambda: None)
    monkeypatch.setattr(rt, "_get_kis_token", lambda: "tok")

    threads = [
        threading.Thread(target=rt._get_kis_price, args=("005930.KS",))
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert rt._kis_domain_corrected is True
    assert rt.kis_base == _VTS, "domain must end corrected (VTS), never reverted to real"
    assert force_calls["n"] == 1, "domain correction must happen exactly once across threads"
