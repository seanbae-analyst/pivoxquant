"""Tests for services/mirror_ingest/screenshot.py.

# noqa: legal — the BUY/SELL literals below are TradeHistory.action fixture
# values, the case the guard's own whitelist names ("test fixture"). They
# are what the user already did, never a label this product shows anyone.

The behaviour under test is mostly refusal. A mirror's only claim is that
it reports the user's own record back to them, so the extraction must fail
loudly rather than fill a gap with a plausible value — every test below
that asserts a row lands in ``unreadable`` is guarding that promise.

No network: the vision call is exercised through an injected fake client,
and the response parser is tested directly.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from services.mirror_ingest.screenshot import (
    ExtractionResult,
    _coerce_row,
    _parse_response,
    _parse_when,
    extract_trades_from_image,
)

PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"padding"
JPEG_HEADER = b"\xff\xd8\xff" + b"padding"


# ── input guards ────────────────────────────────────────────────────────

def test_empty_image_rejected():
    r = extract_trades_from_image(b"")
    assert not r.ok
    assert "비어" in r.error


def test_oversized_image_rejected_before_any_call():
    # 6MB — over Anthropic's 5MB per-image limit. Must be caught locally so
    # the user gets a fixable message instead of an opaque API failure.
    r = extract_trades_from_image(PNG_HEADER + b"\x00" * (6 * 1024 * 1024))
    assert not r.ok
    assert "5MB" in r.error


def test_non_image_bytes_rejected():
    r = extract_trades_from_image(b"%PDF-1.7 this is a pdf")
    assert not r.ok
    assert "형식" in r.error


@pytest.mark.parametrize("data", [PNG_HEADER, JPEG_HEADER])
def test_supported_formats_reach_the_client(data):
    class _Fake:
        def __init__(self):
            self.messages = self
            self.seen = {}

        def create(self, **kw):
            self.seen.update(kw)
            return type("R", (), {"content": [
                type("B", (), {"type": "text", "text": '{"trades": [], "unreadable": []}'})()
            ]})()

    fake = _Fake()
    r = extract_trades_from_image(data, client=fake)
    assert r.ok
    assert fake.seen["model"]


# ── date parsing: unreadable beats guessed ──────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("2026-03-14", datetime(2026, 3, 14)),
    ("2026/03/14", datetime(2026, 3, 14)),
    ("2026.03.14", datetime(2026, 3, 14)),
    ("2026-03-14 09:31", datetime(2026, 3, 14, 9, 31)),
    ("2026-03-14 09:31:22", datetime(2026, 3, 14, 9, 31, 22)),
])
def test_parses_the_separators_korean_brokers_use(raw, expected):
    assert _parse_when(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, 20260314, "3월 14일", "어제"])
def test_unparseable_date_returns_none_rather_than_a_guess(raw):
    # "3월 14일" has no year. Inferring the current year would silently place
    # the trade in the wrong window and change every hold-period number.
    assert _parse_when(raw) is None


# ── row validation ──────────────────────────────────────────────────────

def _row(**over):
    base = {
        "ticker": "005930", "name": "삼성전자", "action": "BUY",
        "shares": 10, "price_per_share": 71500,
        "traded_at": "2026-03-14", "currency": "KRW",
    }
    base.update(over)
    return base


def test_valid_row_maps_onto_the_tradehistory_shape():
    trade, rejection = _coerce_row(_row())
    assert rejection is None
    assert (trade.ticker, trade.name, trade.action) == ("005930", "삼성전자", "BUY")
    assert trade.shares == 10
    assert trade.price_per_share == 71500
    assert trade.total_value == 715000
    assert trade.traded_at == datetime(2026, 3, 14)


@pytest.mark.parametrize("action,ok", [
    ("BUY", True), ("SELL", True), ("buy", True), ("sell", True),
    ("매수", False), ("", False), ("HOLD", False), (None, False),
])
def test_only_buy_and_sell_are_accepted(action, ok):
    trade, rejection = _coerce_row(_row(action=action))
    assert (trade is not None) is ok
    if not ok:
        assert "매수/매도" in rejection


@pytest.mark.parametrize("shares,price", [(0, 71500), (-5, 71500), (10, 0), (10, -1)])
def test_zero_or_negative_quantities_are_refused(shares, price):
    # These would not merely be wrong rows — a zero-share fill distorts
    # turnover counts and breaks FIFO pairing for every later trade.
    trade, rejection = _coerce_row(_row(shares=shares, price_per_share=price))
    assert trade is None
    assert "0 이하" in rejection


@pytest.mark.parametrize("bad", ["abc", None, "", "1,000"])
def test_non_numeric_quantities_are_refused(bad):
    trade, rejection = _coerce_row(_row(shares=bad))
    assert trade is None
    assert "숫자가 아님" in rejection


def test_unreadable_date_rejects_the_row():
    trade, rejection = _coerce_row(_row(traded_at="어제쯤"))
    assert trade is None
    assert "거래일시" in rejection


def test_unknown_currency_falls_back_to_krw():
    # Safe because currency only groups figures for display; it is never
    # used to convert between them. Mixing KRW and USD into one number is
    # what the mirrors already refuse to do.
    trade, _ = _coerce_row(_row(currency="EUR"))
    assert trade.currency == "KRW"


def test_usd_is_preserved():
    trade, _ = _coerce_row(_row(currency="usd"))
    assert trade.currency == "USD"


# ── response parsing ────────────────────────────────────────────────────

def test_parses_a_clean_reply():
    r = _parse_response(
        '{"trades": [{"ticker":"005930","name":"삼성전자","action":"BUY",'
        '"shares":10,"price_per_share":71500,"traded_at":"2026-03-14",'
        '"currency":"KRW"}], "unreadable": [], "source_note": "키움"}'
    )
    assert r.ok
    assert len(r.trades) == 1
    assert r.source_note == "키움"
    assert not r.needs_review


def test_tolerates_a_code_fence():
    r = _parse_response('```json\n{"trades": [], "unreadable": []}\n```')
    assert r.ok
    assert r.trades == []


def test_non_json_reply_is_an_error_not_an_empty_read():
    # An empty result would read as "you have no trades", which is a
    # different and much worse claim than "we could not read this".
    r = _parse_response("죄송합니다, 이미지를 볼 수 없습니다.")
    assert not r.ok
    assert r.trades == []


def test_invalid_rows_surface_as_unreadable_rather_than_vanishing():
    r = _parse_response(
        '{"trades": ['
        '{"ticker":"005930","name":"삼성전자","action":"BUY","shares":10,'
        '"price_per_share":71500,"traded_at":"2026-03-14"},'
        '{"ticker":"000660","name":"SK하이닉스","action":"BUY","shares":5,'
        '"price_per_share":null,"traded_at":"2026-03-15"}'
        '], "unreadable": []}'
    )
    assert len(r.trades) == 1
    assert len(r.unreadable) == 1
    assert "SK하이닉스" in r.unreadable[0]["row_hint"]
    assert r.needs_review is True


def test_model_reported_unreadable_rows_are_kept():
    r = _parse_response(
        '{"trades": [], "unreadable": [{"row_hint":"3번째 줄",'
        '"reason":"체결단가가 잘림"}]}'
    )
    assert r.ok
    assert r.needs_review
    assert r.unreadable[0]["reason"] == "체결단가가 잘림"


def test_empty_read_is_a_valid_answer_not_an_error():
    r = _parse_response('{"trades": [], "unreadable": [], "source_note": "거래내역 화면이 아님"}')
    assert r.ok
    assert r.trades == []
    assert not r.needs_review


def test_malformed_shapes_do_not_raise():
    for payload in ('[]', '"a string"', '{"trades": "not a list"}',
                    '{"trades": [null, 42, "x"]}', '{}'):
        r = _parse_response(payload)
        assert isinstance(r, ExtractionResult)
        assert r.trades == []
