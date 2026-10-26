"""tests/test_imports_file_hunt.py — broker file import, 2026-10-13 bug hunt.

Each case is a CSV a broker app could export that used to be stored as a
wrong trade or dropped without a reason. Uploaded through the real route.
"""
from __future__ import annotations

import io
from datetime import datetime

import pytest

BASE = "/api/portfolio/imports"


@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)


def _upload(client, text: str, name: str = "trades.csv"):
    form = {"file": (io.BytesIO(text.encode("utf-8")), name), "consent": "true"}
    return client.post(f"{BASE}/", data=form, content_type="multipart/form-data")


def _pending(r):
    assert r.status_code == 201, r.get_json()
    return r.get_json()["pending"]


def test_partial_fill_takes_the_filled_quantity(client, auth_user):
    csv = (
        "주문일자,종목명,종목코드,주문구분,주문수량,체결수량,주문단가,체결단가,체결금액\n"
        "2026-10-01,삼성전자,005930,현금매수,10,4,71000,71200,284800\n"
    )
    p = _pending(_upload(client, csv))[0]
    assert (p["action"], p["shares"], p["price"]) == ("BUY", 4.0, 71200.0)  # // legal-ok — stored enum value


def test_order_price_column_alone_uses_the_fill_amount(client, auth_user):
    csv = (
        "주문일자,종목명,종목코드,매매구분,체결수량,주문단가,체결금액\n"
        "2026-10-01,삼성전자,005930,매수,4,71000,284800\n"
    )
    p = _pending(_upload(client, csv))[0]
    assert p["price"] == pytest.approx(71200.0)


def test_usd_row_reads_the_usd_price_column(client, auth_user):
    csv = (
        "거래일자,종목명,종목코드,매매구분,수량,단가(원),단가(USD),거래금액(원),통화\n"
        "2026-10-01,테슬라,TSLA,매수,2,497000,350,994000,USD\n"
    )
    p = _pending(_upload(client, csv))[0]
    assert (p["ticker"], p["price"], p["currency"]) == ("TSLA", 350.0, "USD")


def test_won_only_price_column_is_not_stored_as_dollars(client, auth_user):
    csv = (
        "거래일자,종목명,종목코드,매매구분,수량,단가(원)\n"
        "2026-10-01,테슬라,TSLA,매수,2,497000\n"
    )
    r = _upload(client, csv)
    body = r.get_json()
    stored = [p for p in body.get("pending", []) if p["ticker"] == "TSLA" and p["currency"] == "USD"]
    assert not any(p["price"] == 497000.0 for p in stored)


@pytest.mark.parametrize("label", ["매수취소", "매도정정", "환전매도"])
def test_cancel_amend_and_fx_rows_are_not_fills(client, auth_user, label):
    csv = (
        "거래일자,종목명,종목코드,매매구분,수량,단가\n"
        "2026-10-01,삼성전자,005930,매수,10,71200\n"
        f"2026-10-02,삼성전자,005930,{label},10,71300\n"
    )
    body = _upload(client, csv).get_json()
    assert len(body["pending"]) == 1
    assert any(s["row"] == 3 for s in body["skipped"])


def test_currency_purchase_row_is_not_a_fill(client, auth_user):
    csv = (
        "거래일자,종목명,종목코드,매매구분,수량,단가\n"
        "2026-10-01,삼성전자,005930,매수,10,71200\n"
        "2026-10-02,미국달러,USD,외화매수,1000,1380\n"
    )
    body = _upload(client, csv).get_json()
    assert len(body["pending"]) == 1
    assert any(s["row"] == 3 for s in body["skipped"])


def test_korean_date_keeps_its_year(client, auth_user):
    csv = (
        "거래일자,종목명,종목코드,매매구분,수량,단가\n"
        "2025년 03월 04일,삼성전자,005930,매수,10,71200\n"
    )
    p = _pending(_upload(client, csv))[0]
    assert p["traded_at"].startswith("2025-03-0")  # KST→UTC may move it to the 3rd


def test_numeric_time_cell_keeps_its_time():
    from services.imports import parse_datetime

    assert parse_datetime("2026-10-01", 93000) == datetime(2026, 10, 1, 9, 30, 0)


def test_rows_past_the_cap_are_reported_not_dropped(client, auth_user, monkeypatch):
    monkeypatch.setattr("services.imports.csv_parser.MAX_ROWS", 3)
    lines = ["거래일자,종목명,종목코드,매매구분,수량,단가"]
    lines += [f"2026-10-0{d},삼성전자,005930,매수,{d},71200" for d in range(1, 6)]
    body = _upload(client, "\n".join(lines) + "\n").get_json()
    assert len(body["pending"]) == 3
    assert any("3행까지만" in s["reason"] for s in body["skipped"])
