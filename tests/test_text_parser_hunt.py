"""tests/test_text_parser_hunt.py — fill-notification parser, 2026-10-13 hunt.

Each case is a broker-shaped line that used to be dropped or — worse — stored
as a wrong trade without any needs-check flag. ``parse_text`` is called
directly; the two resolver cases go through ``routes.imports.resolve_ticker``.
"""
from __future__ import annotations

import pytest

from services.imports.text_parser import parse_text


def one(line: str):
    rows = parse_text(line)
    assert len(rows) == 1
    return rows[0]


# ── 토스증권 says 구매/판매, not 매수/매도 ─────────────────────────────

@pytest.mark.parametrize(
    "line, action, shares, price, currency",
    [
        ("[토스증권] 삼성전자 3주 구매 완료 · 1주 72,000원", "BUY", 3.0, 72000.0, "KRW"),
        ("[토스증권] 삼성전자 3주 판매 완료 · 1주 72,000원", "SELL", 3.0, 72000.0, "KRW"),
        ("삼성전자 3주를 1주당 72,000원에 구매했어요", "BUY", 3.0, 72000.0, "KRW"),
        ("애플 0.5주 구매 완료 · 1주 $190.12", "BUY", 0.5, 190.12, "USD"),
    ],
)
def test_toss_buy_sell_words(line, action, shares, price, currency):
    t = one(line)
    assert t.skip_reason is None
    assert (t.action, t.shares, t.price, t.currency) == (action, shares, price, currency)


def test_toss_order_placed_is_not_a_fill():
    assert one("[토스증권] 삼성전자 3주 구매 주문을 넣었어요").skip_reason


# ── silent wrong trades ─────────────────────────────────────────────

def test_order_number_is_not_the_krx_code():
    t = one("삼성전자 10주 매수 체결 71,200원 주문번호 123456")
    assert t.code in ("", None) and t.name == "삼성전자"


def test_account_number_is_not_the_krx_code():
    t = one("계좌 123-45-678901 삼성전자 10주 매수 체결 71,200원")
    assert t.code in ("", None) and t.name == "삼성전자"


@pytest.mark.parametrize(
    "line, price",
    [
        ("삼성전자 10주 매수 체결 체결금액 712,000원", 71200.0),
        ("삼성전자 10주 매도 체결 · 정산금액 701,000원", 70100.0),
        ("삼성전자 10주 매수 체결 71,200원 수수료 107원", 71200.0),
        ("삼성전자 10주 매수 체결 수수료 107원 71,200원", 71200.0),
        ("삼성전자 10주 구매 완료 · 총 720,000원", 72000.0),
        ("삼성전자 10주 구매 완료 · 1주 72,000원 (총 720,000원)", 72000.0),
    ],
)
def test_total_or_fee_is_not_the_per_share_price(line, price):
    assert one(line).price == pytest.approx(price)


@pytest.mark.parametrize(
    "line",
    [
        "삼성전자 매수 10주 중 5주 체결 71,200원",
        "매수 체결 삼성전자 주문수량 10주 체결수량 5주 71,200원",
        "삼성전자 매수 체결 5/10주 71,200원",
        "삼성전자 5주/10주 매수 체결 71,200원",
    ],
)
def test_partial_fill_takes_the_filled_quantity(line):
    t = one(line)
    assert t.shares == 5.0
    assert t.price == pytest.approx(71200.0)


def test_partial_fill_fraction_is_not_a_date():
    from services.imports import today_naive

    t = one("삼성전자 매수 체결 5/10주 71,200원")
    assert t.traded_at.date() == today_naive().date()


def test_unfilled_remainder_is_not_the_filled_quantity():
    t = one("[키움증권] 삼성전자 매수체결 10주 71,200원 미체결수량 0")
    assert t.shares == 10.0 and t.skip_reason is None


@pytest.mark.parametrize(
    "line",
    [
        "애플 5주 매수 체결 $190.12 (약 262,000원)",
        "엔비디아 5주 매수 체결 $118.5 환율 1,380원",
        "AAPL 5주 매수 체결 190.12 USD (261,500원)",
    ],
)
def test_won_equivalent_does_not_make_a_dollar_fill_won(line):
    t = one(line)
    assert t.currency == "USD"
    assert t.price < 1000


def test_bracketed_won_price_is_still_read():
    assert one("삼성전자 10주 매수 (71,200원) 체결").price == pytest.approx(71200.0)


# ── non-fills that became trades ────────────────────────────────────

@pytest.mark.parametrize(
    "line",
    [
        "[토스증권] 삼성전자 1주 매수하면 10,000원 혜택!",
        "(광고) 삼성전자 1주 매수 체결 이벤트 10,000원",
        "삼성전자 10주 보유 중 · 매수 평균가 70,000원 · 현재가 72,000원",
        "삼성전자 5주 평가손익 +12,000원 (매수 평균가 70,000원)",
        "삼성전자 매수 가능 수량 10주 (증거금 712,000원)",
        "삼성전자 10주 매도 예약 · 80,000원 도달 시 자동 판매",
        "[키움증권] 삼성전자 매수 예약주문 10주 71,200원 등록",
        "삼성전자 매수 10주 71,200원 주문 전송 완료",
    ],
)
def test_non_fill_notices_are_skipped(line):
    t = one(line)
    assert t.skip_reason
    assert t.shares == 0


# ── names ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "line, name",
    [
        ("[NH투자증권] 나무 삼성전자 매수 10주 71,200원 체결", "삼성전자"),
        ("[키움증권] 영웅문 체결안내 삼성전자 매도 10주 71,200원", "삼성전자"),
        ("카카오페이 10주 매수 체결 25,000원", "카카오페이"),
        ("LG디스플레이 5주 매도 체결 11,200원", "LG디스플레이"),
        ("나무가 3주 매수 체결 20,000원", "나무가"),
        ("[키움증권] 정정 주문이 체결되었습니다 삼성전자 10주 매수 체결단가 71,000원", "삼성전자"),
    ],
)
def test_security_name(line, name):
    assert one(line).name == name


@pytest.mark.parametrize(
    "name, ticker",
    [("카카오페이", "377300.KS"), ("LG디스플레이", "034220.KS"), ("삼성전자가", "005930.KS")],
)
def test_resolver_keeps_names_ending_in_i_ga_and_drops_a_glued_particle(app, name, ticker):
    from routes.imports import resolve_ticker

    with app.app_context():
        assert resolve_ticker("", name)[0] == ticker


# ── no regressions from the fixes above ────────────────────────────

def test_ticker_ending_in_no_is_not_an_id_label():
    t = one("CNO 5주 매수 체결 $30.10")
    assert (t.code, t.shares, t.price, t.currency) == ("CNO", 5.0, 30.10, "USD")


def test_name_ending_in_yak_keeps_its_price():
    t = one("삼성제약 15,000원 3주 매수 체결")
    assert (t.name, t.shares, t.price) == ("삼성제약", 3.0, 15000.0)


@pytest.mark.parametrize("label", ["No. 123456", "No:123456", "주문번호 123456"])
def test_labelled_order_numbers_are_dropped(label):
    t = one(f"삼성전자 10주 매수 체결 71,200원 {label}")
    assert t.code in ("", None) and t.name == "삼성전자"
