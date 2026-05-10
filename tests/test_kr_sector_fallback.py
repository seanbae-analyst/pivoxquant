"""tests/test_kr_sector_fallback.py — Bug #10: KR sector "Unknown" fix.

Covers the 3-step sector resolution chain in
``services.data.fetcher._resolve_sector``:

  1. FMP info["sector"] (US-friendly path; usually empty for KR)
  2. KIS bstp_kor_isnm via info["sector_kr"]
     (services.data.kr_fundamentals.get_kr_fundamentals)
  3. KOREAN_SECTORS hardcoded fallback (124500.KQ etc.)
  4. "Unknown" terminal fallback

Plus the parser change in ``kr_fundamentals.get_kr_fundamentals`` —
``sector_kr`` key populated from ``output.bstp_kor_isnm``.

Network calls are mocked; no live KIS / FMP traffic.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.data.fetcher import (
    KOREAN_SECTORS,
    _resolve_sector,
)


# ── _resolve_sector unit tests ──────────────────────────────────────────────


def test_resolve_sector_us_uses_fmp_field():
    """US ticker — FMP sector wins, KOREAN_SECTORS not consulted."""
    info = {"sector": "Technology"}
    assert _resolve_sector("AAPL", info, is_kr=False) == "Technology"


def test_resolve_sector_us_unknown_when_fmp_empty():
    """US ticker with empty FMP sector → "Unknown" (no KR mapping path)."""
    assert _resolve_sector("AAPL", {"sector": ""}, is_kr=False) == "Unknown"
    assert _resolve_sector("AAPL", {}, is_kr=False) == "Unknown"


def test_resolve_sector_kr_kis_path():
    """KR ticker — KIS sector_kr (bstp_kor_isnm) chosen when FMP empty.

    Reproduces Bug #10 fix: 124500.KQ previously returned "Unknown"
    because FMP gives "" and the hardcoded mapping had no entry.
    With KIS sector_kr populated by kr_fundamentals, we now display
    the KIS Korean sector label verbatim.
    """
    info = {"sector": "", "sector_kr": "IT 서비스"}
    assert _resolve_sector("124500.KQ", info, is_kr=True) == "IT 서비스"


def test_resolve_sector_kr_falls_through_to_korean_sectors():
    """KR ticker — when KIS path returns nothing, KOREAN_SECTORS wins."""
    info = {"sector": "", "sector_kr": None}
    # 005930.KS has been in KOREAN_SECTORS since the original fix.
    assert _resolve_sector("005930.KS", info, is_kr=True) == "Technology"


def test_resolve_sector_kr_terminal_unknown():
    """KR ticker — all 3 sources empty → "Unknown" (no regression)."""
    info = {"sector": "", "sector_kr": ""}
    # Use a synthetic ticker not in KOREAN_SECTORS.
    assert _resolve_sector("999999.KQ", info, is_kr=True) == "Unknown"


def test_resolve_sector_124500_safety_net_added():
    """KOREAN_SECTORS now includes 124500.KQ as a safety net.

    Even if KIS is unreachable (token fail / rate-limit), the bug-#10
    reporter's specific holding shouldn't show "Unknown".
    """
    assert KOREAN_SECTORS.get("124500.KQ") == "Technology"

    info = {"sector": "", "sector_kr": None}  # KIS path failed.
    assert _resolve_sector("124500.KQ", info, is_kr=True) == "Technology"


def test_resolve_sector_fmp_wins_over_kr_chain():
    """If FMP ever provides a non-empty KR sector, it wins (no override)."""
    info = {"sector": "Technology", "sector_kr": "다른 업종"}
    assert _resolve_sector("005930.KS", info, is_kr=True) == "Technology"


def test_resolve_sector_handles_whitespace_only_fmp_sector():
    """Whitespace-only FMP sector treated as empty → falls to KR chain."""
    info = {"sector": "   ", "sector_kr": "IT 서비스"}
    assert _resolve_sector("124500.KQ", info, is_kr=True) == "IT 서비스"


# ── kr_fundamentals.get_kr_fundamentals — sector_kr parsing ────────────────


def _mock_kis_response(output: dict, *, rt_cd: str = "0", ok: bool = True):
    """Build a mock requests.Response-like object for the KIS API."""
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = 200 if ok else 500
    resp.json.return_value = {"rt_cd": rt_cd, "msg1": "OK", "output": output}
    return resp


@patch("services.data.kr_fundamentals._auth_headers")
@patch("services.data.kr_fundamentals._rate_limit", lambda: None)
@patch("services.data.kr_fundamentals.requests.get")
def test_kr_fundamentals_parses_bstp_kor_isnm(mock_get, mock_headers):
    """KIS output.bstp_kor_isnm parsed into result["sector_kr"]."""
    mock_headers.return_value = {"appkey": "x", "appsecret": "y", "tr_id": "FHKST01010100", "authorization": "Bearer z", "Content-Type": "application/json; charset=utf-8"}
    mock_get.return_value = _mock_kis_response({
        "per": "12.34",
        "eps": "5432",
        "pbr": "1.23",
        "hts_avls": "5100000",  # 억원
        "bstp_kor_isnm": "IT 서비스",
    })

    from services.data.kr_fundamentals import get_kr_fundamentals
    info = get_kr_fundamentals("124500.KQ")

    assert info is not None
    assert info["sector_kr"] == "IT 서비스"
    # Existing fields preserved (regression guard).
    assert info["trailingPE"] == 12.34
    assert info["trailingEps"] == 5432.0
    assert info["priceToBook"] == 1.23
    assert info["marketCap"] == 5100000 * 1e8


@patch("services.data.kr_fundamentals._auth_headers")
@patch("services.data.kr_fundamentals._rate_limit", lambda: None)
@patch("services.data.kr_fundamentals.requests.get")
def test_kr_fundamentals_missing_bstp_kor_isnm(mock_get, mock_headers):
    """KIS output without bstp_kor_isnm → sector_kr is None (not '')."""
    mock_headers.return_value = {"appkey": "x", "appsecret": "y", "tr_id": "FHKST01010100", "authorization": "Bearer z", "Content-Type": "application/json; charset=utf-8"}
    mock_get.return_value = _mock_kis_response({
        "per": "12.34",
        "eps": "5432",
        # bstp_kor_isnm omitted (e.g. ETF/SPAC)
    })

    from services.data.kr_fundamentals import get_kr_fundamentals
    info = get_kr_fundamentals("124500.KQ")

    assert info is not None
    assert info["sector_kr"] is None
    # Numerics still parsed.
    assert info["trailingPE"] == 12.34


@patch("services.data.kr_fundamentals._auth_headers")
@patch("services.data.kr_fundamentals._rate_limit", lambda: None)
@patch("services.data.kr_fundamentals.requests.get")
def test_kr_fundamentals_empty_bstp_kor_isnm(mock_get, mock_headers):
    """KIS output with empty bstp_kor_isnm string → sector_kr None.

    Empty string must become None so caller's truthy fallback chain
    works (otherwise "" would short-circuit the OR chain in
    _resolve_sector to "" which renders as falsy/empty in the UI).
    """
    mock_headers.return_value = {"appkey": "x", "appsecret": "y", "tr_id": "FHKST01010100", "authorization": "Bearer z", "Content-Type": "application/json; charset=utf-8"}
    mock_get.return_value = _mock_kis_response({
        "per": "12.34",
        "bstp_kor_isnm": "   ",  # whitespace only
    })

    from services.data.kr_fundamentals import get_kr_fundamentals
    info = get_kr_fundamentals("124500.KQ")

    assert info is not None
    assert info["sector_kr"] is None


@patch("services.data.kr_fundamentals._auth_headers")
@patch("services.data.kr_fundamentals._rate_limit", lambda: None)
@patch("services.data.kr_fundamentals.requests.get")
def test_kr_fundamentals_kis_unavailable(mock_get, mock_headers):
    """KIS credentials missing → return None; no sector_kr key leak."""
    mock_headers.return_value = None  # simulate unset KIS_APP_KEY

    from services.data.kr_fundamentals import get_kr_fundamentals
    info = get_kr_fundamentals("124500.KQ")

    assert info is None
    mock_get.assert_not_called()


@patch("services.data.kr_fundamentals._auth_headers")
@patch("services.data.kr_fundamentals._rate_limit", lambda: None)
@patch("services.data.kr_fundamentals.requests.get")
def test_kr_fundamentals_kis_rt_cd_error(mock_get, mock_headers):
    """KIS rt_cd != "0" → return None (caller falls back to KOREAN_SECTORS)."""
    mock_headers.return_value = {"appkey": "x", "appsecret": "y", "tr_id": "FHKST01010100", "authorization": "Bearer z", "Content-Type": "application/json; charset=utf-8"}
    mock_get.return_value = _mock_kis_response({}, rt_cd="1")

    from services.data.kr_fundamentals import get_kr_fundamentals
    info = get_kr_fundamentals("124500.KQ")

    assert info is None


# ── End-to-end ish: kr_fundamentals → fetcher chain ────────────────────────


def test_resolve_sector_uses_kr_fundamentals_output_shape():
    """Integration shape — kr_fundamentals returns "sector_kr" key,
    fetcher._resolve_sector reads info["sector_kr"]. Wires the contract.
    """
    # Simulate the merged info dict that fmp.get_info() produces after
    # the KR-fundamentals overlay at fmp.py:867-876.
    info = {
        "sector": "",                # FMP empty (KR coverage gap)
        "trailingPE": 12.34,         # from KIS
        "sector_kr": "전기·전자",     # from KIS bstp_kor_isnm
    }
    assert _resolve_sector("005930.KS", info, is_kr=True) == "전기·전자"
