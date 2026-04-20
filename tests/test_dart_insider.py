"""
PivoxQuant — DART insider data service tests
============================================
Covers:
  - ``services/data/dart_corp_code.py``  — CORPCODE.xml resolver + cache.
  - ``services/data/dart_insider.py``    — elestock.json insider trades.

All HTTP egress to DART is **mocked**. Tests never hit the wire, so CI can
run without a ``DART_API_KEY``. Real-API smoke test is `test_elestock_live`
at the bottom — gated on the env var and skipped otherwise.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90</corp_name>
    <corp_eng_name>Samsung Electronics</corp_eng_name>
    <stock_code>005930</stock_code>
    <modify_date>20200101</modify_date>
  </list>
  <list>
    <corp_code>00164779</corp_code>
    <corp_name>SK\xed\x95\x98\xec\x9d\xb4\xeb\x8b\x89\xec\x8a\xa4</corp_name>
    <corp_eng_name>SK hynix</corp_eng_name>
    <stock_code>000660</stock_code>
    <modify_date>20200101</modify_date>
  </list>
  <list>
    <corp_code>00434003</corp_code>
    <corp_name>Unlisted Inc</corp_name>
    <stock_code></stock_code>
    <modify_date>20200101</modify_date>
  </list>
</result>
"""


def _make_zip(xml_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("CORPCODE.xml", xml_bytes)
    return buf.getvalue()


@pytest.fixture
def tmp_cache(monkeypatch):
    """Point the corp_code cache at a temp file and wipe in-memory state."""
    from services.data import dart_corp_code

    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, prefix="dart_corp_code_test_"
    )
    tmp.close()
    Path(tmp.name).unlink(missing_ok=True)
    monkeypatch.setenv("DART_CORP_CODE_CACHE", tmp.name)
    dart_corp_code.clear_cache()
    yield Path(tmp.name)
    dart_corp_code.clear_cache()
    Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def with_api_key(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "test-key-0123456789")
    yield


# ═════════════════════════════════════════════════════════════════════════════
# dart_corp_code
# ═════════════════════════════════════════════════════════════════════════════

def test_corp_code_parses_xml_and_filters_unlisted(tmp_cache, with_api_key):
    from services.data import dart_corp_code

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = _make_zip(SAMPLE_XML)

    with patch("services.data.dart_corp_code._requests.get",
               return_value=mock_resp) as mget:
        mapping = dart_corp_code.load_mapping(force=True)

    assert mget.call_count == 1
    assert mapping["005930"] == "00126380"
    assert mapping["000660"] == "00164779"
    # Unlisted row (empty stock_code) must be dropped.
    assert len(mapping) == 2


def test_corp_code_for_accepts_suffixes(tmp_cache, with_api_key):
    from services.data import dart_corp_code

    dart_corp_code.seed_cache({"005930": "00126380", "000660": "00164779"})

    assert dart_corp_code.corp_code_for("005930") == "00126380"
    assert dart_corp_code.corp_code_for("005930.KS") == "00126380"
    assert dart_corp_code.corp_code_for("000660.KQ") == "00164779"
    # Non-KR or bogus inputs.
    assert dart_corp_code.corp_code_for("AAPL") is None
    assert dart_corp_code.corp_code_for("") is None
    assert dart_corp_code.corp_code_for(None) is None   # type: ignore[arg-type]
    assert dart_corp_code.corp_code_for("12345") is None  # too short
    # Unknown but well-formed ticker → None.
    assert dart_corp_code.corp_code_for("999999") is None


def test_corp_code_uses_disk_cache(tmp_cache, with_api_key):
    from services.data import dart_corp_code

    # Seed the disk cache.
    dart_corp_code.seed_cache({"005930": "00126380"})
    # Wipe in-memory so we force a disk read.
    dart_corp_code._mem_cache = None
    dart_corp_code._mem_cache_ts = 0.0

    with patch("services.data.dart_corp_code._requests.get") as mget:
        mapping = dart_corp_code.load_mapping()
        assert mapping == {"005930": "00126380"}
        mget.assert_not_called()  # disk hit → no HTTP


def test_corp_code_no_api_key_returns_empty(tmp_cache, monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    from services.data import dart_corp_code

    with patch("services.data.dart_corp_code._requests.get") as mget:
        assert dart_corp_code.load_mapping(force=True) == {}
        assert dart_corp_code.corp_code_for("005930.KS") is None
        mget.assert_not_called()


def test_corp_code_bad_zip_does_not_raise(tmp_cache, with_api_key):
    from services.data import dart_corp_code

    bad = MagicMock(status_code=200, content=b'{"status":"020","message":"bad key"}')
    with patch("services.data.dart_corp_code._requests.get", return_value=bad):
        assert dart_corp_code.load_mapping(force=True) == {}


def test_corp_code_http_failure_falls_back_to_stale(tmp_cache, with_api_key):
    """When the download fails but a disk cache exists, reuse it."""
    from services.data import dart_corp_code

    # Pre-seed a (stale-looking) cache file directly.
    stale = {
        "fetched_at": time.time() - (100 * 24 * 3600),  # 100 days ago
        "count":      1,
        "mapping":    {"005930": "00126380"},
    }
    tmp_cache.write_text(json.dumps(stale), encoding="utf-8")
    dart_corp_code.clear_cache()
    # Must NOT delete tmp_cache here; clear_cache unlinks it if present.
    tmp_cache.write_text(json.dumps(stale), encoding="utf-8")

    # Simulate network failure.
    with patch("services.data.dart_corp_code._requests.get",
               side_effect=RuntimeError("network down")):
        mapping = dart_corp_code.load_mapping(force=True)

    assert mapping == {"005930": "00126380"}


# ═════════════════════════════════════════════════════════════════════════════
# dart_insider
# ═════════════════════════════════════════════════════════════════════════════

def test_insider_no_key_short_circuits(monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    from services.data import dart_insider

    assert dart_insider.is_configured() is False
    # Even with a corp_code, no key → empty.
    assert dart_insider.get_insider_trades("00126380", days=7) == []
    assert dart_insider.ticker_to_corp_code("005930.KS") is None


def test_insider_ticker_to_corp_code_uses_resolver(tmp_cache, with_api_key):
    from services.data import dart_corp_code, dart_insider

    dart_corp_code.seed_cache({"005930": "00126380"})
    assert dart_insider.ticker_to_corp_code("005930.KS") == "00126380"
    # US ticker must return None even with a valid key.
    assert dart_insider.ticker_to_corp_code("AAPL") is None


def test_elestock_parses_buy_and_sell(with_api_key):
    """elestock.json response → normalised buy/sell rows."""
    from services.data import dart_insider

    # Reset module caches so the test is hermetic.
    dart_insider._cache.clear()

    sample = {
        "status": "000",
        "message": "\uc815\uc0c1",
        "list": [
            {
                "rcept_no":   "20260418000123",
                "corp_code":  "00126380",
                "corp_name":  "\uc0bc\uc131\uc804\uc790",
                "stock_code": "005930",
                "repror":     "\ud64d\uae38\ub3d9",
                "isu_rel":    "\uc784\uc6d0",
                "isu_exctn":  "\uc7a5\ub0b4\ub9e4\uc218",
                "isu_stock":  "10,000",
                "trd_dd":     "20260418",
            },
            {
                "rcept_no":   "20260417000456",
                "corp_code":  "00126380",
                "corp_name":  "\uc0bc\uc131\uc804\uc790",
                "stock_code": "005930",
                "repror":     "\uc774\uc21c\uc2e0",
                "isu_rel":    "\uc8fc\uc694\uc8fc\uc8fc",
                "isu_exctn":  "\uc7a5\ub0b4\ub9e4\ub3c4",
                "isu_stock":  "5,500",
                "trd_dd":     "20260417",
            },
        ],
    }
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = sample

    with patch("services.data.dart_insider._requests.get",
               return_value=mock_resp) as mget:
        trades = dart_insider.get_insider_trades("00126380", days=7)

    assert mget.call_count == 1
    # Sorted newest first.
    assert len(trades) == 2
    assert trades[0]["direction"] == "buy"
    assert trades[0]["transaction_code"] == "P"
    assert trades[0]["shares"] == 10_000
    assert trades[0]["transaction_date"] == "2026-04-18"
    assert trades[0]["source"] == "DART"
    assert trades[0]["ticker"] == "005930.KS"
    assert trades[0]["disclosure_url"].startswith("https://dart.fss.or.kr")

    assert trades[1]["direction"] == "sell"
    assert trades[1]["transaction_code"] == "S"
    assert trades[1]["shares"] == 5_500


def test_elestock_empty_list_ok(with_api_key):
    """DART `013 no-data` status is treated as a successful empty result."""
    from services.data import dart_insider

    dart_insider._cache.clear()
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"status": "013", "message": "no-data",
                                    "list": []}
    with patch("services.data.dart_insider._requests.get",
               return_value=mock_resp):
        trades = dart_insider.get_insider_trades("00126380", days=30)
    assert trades == []


def test_elestock_http_error_returns_empty(with_api_key):
    from services.data import dart_insider

    dart_insider._cache.clear()
    mock_resp = MagicMock(status_code=500, text="boom")
    with patch("services.data.dart_insider._requests.get",
               return_value=mock_resp):
        assert dart_insider.get_insider_trades("00126380", days=7) == []


def test_elestock_invalid_corp_code():
    from services.data import dart_insider

    # Non-numeric / empty → empty, regardless of key presence.
    assert dart_insider.get_insider_trades("", days=7) == []
    assert dart_insider.get_insider_trades("ABC", days=7) == []


# ═════════════════════════════════════════════════════════════════════════════
# Live smoke test (opt-in)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not os.environ.get("DART_API_KEY"),
    reason="DART_API_KEY not set — skipping live smoke test",
)
def test_elestock_live_samsung():
    """Opt-in integration test: hit real DART for Samsung Electronics.

    Zero rows is a valid outcome — we only assert the call does not raise
    and returns a list. Run with:

        DART_API_KEY=<key> pytest tests/test_dart_insider.py::test_elestock_live_samsung
    """
    from services.data import dart_corp_code, dart_insider

    corp = dart_corp_code.corp_code_for("005930.KS")
    assert corp, "CORPCODE.xml did not resolve Samsung Electronics"
    trades = dart_insider.get_insider_trades(corp, days=30)
    assert isinstance(trades, list)
