"""KIS 52-week range adapter — payload parsing contract.

2026-06-11: closes the FIX 2 deferred gap (services/alert.py) — KR tickers
had NO 52w-range alerts because the lookup was FMP-only and FMP's KRX
coverage is unreliable. ``get_52w_range`` reads ``w52_hgpr``/``w52_lwpr``
from the exchange-licensed KIS ``inquire-price`` payload (the same call
``get_name`` already makes). Contract under test: parse the happy path,
and return ``None`` on every degraded shape so the alert layer's
"rather miss than fabricate" rule holds.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.data import kis_market_adapter as kma


def _resp(payload, ok=True):
    r = MagicMock()
    r.ok = ok
    r.json.return_value = payload
    return r


def _payload(hi, lo, rt_cd="0"):
    return {"rt_cd": rt_cd, "output": {"w52_hgpr": hi, "w52_lwpr": lo}}


def _patched(resp):
    """Patch the network + availability plumbing around get_52w_range."""
    return (
        patch.object(kma, "is_available", return_value=True),
        patch.object(kma, "_auth_headers", return_value={"tr_id": "FHKST01010100"}),
        patch.object(kma, "_rate_limit"),
        patch.object(kma.requests, "get", return_value=resp),
    )


def _call(resp, ticker="005930.KS"):
    p1, p2, p3, p4 = _patched(resp)
    with p1, p2, p3, p4:
        return kma.get_52w_range(ticker)


def test_parses_w52_fields():
    assert _call(_resp(_payload("90100", "51200"))) == (90100.0, 51200.0)


def test_kis_error_code_returns_none():
    assert _call(_resp(_payload("90100", "51200", rt_cd="1"))) is None


def test_http_failure_returns_none():
    assert _call(_resp({}, ok=False)) is None


def test_missing_fields_return_none():
    assert _call(_resp({"rt_cd": "0", "output": {}})) is None


def test_garbled_fields_return_none():
    assert _call(_resp(_payload("not-a-number", "51200"))) is None


def test_inverted_range_returns_none():
    # hi < lo can only be a feed glitch — never hand it to the alert layer.
    assert _call(_resp(_payload("50000", "90000"))) is None


def test_unavailable_kis_returns_none():
    with patch.object(kma, "is_available", return_value=False):
        assert kma.get_52w_range("005930.KS") is None


def test_non_krx_ticker_returns_none():
    # _to_code rejects non-KRX shapes — the US path must never reach KIS.
    p1, p2, p3, p4 = _patched(_resp(_payload("1", "1")))
    with p1, p2, p3, p4:
        assert kma.get_52w_range("AAPL") is None
