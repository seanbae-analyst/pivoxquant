"""tests/test_imports_bughunt_2026_10_21.py — 오전/오후 · AM/PM times.

Korean broker texts and Excel time cells print a 12-hour clock ("오후 2:05").
Read without the marker a 14:05 fill became 02:05 KST — and since dedupe
compares two printed times (2026-10-15), the same fill pasted once as
"14:05" and once as "오후 2:05" was stored twice (``services.imports
.meridiem_hour``).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from services.imports import _parse_time, parse_datetime_has_time
from services.imports.text_parser import _date

IMPORTS = "/api/portfolio/imports"
PENDING = f"{IMPORTS}/pending"


@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)


@pytest.mark.parametrize("line,hour,minute", [
    ("삼성전자 1주 매수 체결 71,200원 2026-09-01 오후 2:05", 14, 5),
    ("삼성전자 1주 매수 체결 71,200원 2026-09-01 14:05", 14, 5),
    ("2026.09.01 오전 9:31 체결", 9, 31),
    ("2026-09-01 PM 2:05 체결", 14, 5),
    ("2026-09-01 2:05 PM 체결", 14, 5),
    ("9/1 2:05 PM 체결", 14, 5),
    ("2026-09-01 오후 12:30 체결", 12, 30),
    ("2026-09-01 오전 12:10 체결", 0, 10),
    ("2026-09-01 오후 14:05 체결", 14, 5),     # already 24-hour
    ("TEAM 2:05 체결", 2, 5),                  # "AM" inside a word is no marker
])
def test_text_lines_read_the_meridiem(line, hour, minute):
    dt, timed = _date(line)
    assert timed is True
    assert (dt.hour, dt.minute) == (hour, minute)


def test_time_only_line_reads_the_meridiem():
    dt, timed = _date("오후 2:05 삼성전자 1주 매수 체결 71,200원")
    assert timed and (dt.hour, dt.minute) == (14, 5)


@pytest.mark.parametrize("cell,expected", [
    ("2026-09-01 오후 2:05:00", (datetime(2026, 9, 1, 14, 5), True)),
    ("2026/09/01 PM 3:10", (datetime(2026, 9, 1, 15, 10), True)),
    ("2026-09-01 14:05:00", (datetime(2026, 9, 1, 14, 5), True)),
    ("2026-09-01", (datetime(2026, 9, 1), False)),
])
def test_file_date_cells_read_the_meridiem(cell, expected):
    assert parse_datetime_has_time(cell) == expected


@pytest.mark.parametrize("cell,expected", [
    ("오후 2:05:00", (14, 5, 0)),
    ("2:05 PM", (14, 5, 0)),
    ("오전 12:01", (0, 1, 0)),
    ("14:05", (14, 5, 0)),
])
def test_separate_time_cells_read_the_meridiem(cell, expected):
    assert _parse_time(cell) == expected


def test_the_same_fill_in_12_and_24_hour_clock_is_one(app, client, auth_user):
    first = client.post(f"{IMPORTS}/", json={
        "text": "삼성전자 1주 매수 체결 71,200원 2026-09-01 14:05", "consent": True,
    }).get_json()["pending"][0]
    ok = client.post(f"{PENDING}/{first['id']}/approve", json={"thesis": "실적 발표 전에 샀다"})
    assert ok.status_code == 200, ok.get_json()
    again = client.post(f"{IMPORTS}/", json={
        "text": "삼성전자 1주 매수 체결 71,200원 2026-09-01 오후 2:05", "consent": True,
    }).get_json()["pending"][0]
    assert again["traded_at"].startswith("2026-09-01T05:05")  # 14:05 KST
    assert again["status"] == "duplicate"


# ── one stock under every spelling (dedupe) ──────────────────────────

def test_a_manual_kq_entry_blocks_the_same_fill_imported_as_ks(app, client, auth_user):
    """``035720.KQ`` (an old manual entry) and ``035720.KS`` (the import) are
    one stock — the same fill must not land twice."""
    from extensions import db
    from models import TradeHistory
    with app.app_context():
        db.session.add(TradeHistory(
            user_id=auth_user["id"], ticker="035720.KQ", name="카카오", action="BUY",  # // legal-ok
            shares=1.0, price_per_share=40000.0, total_value=40000.0, pnl=0.0, pnl_pct=0.0,
            currency="KRW", traded_at=datetime(2026, 9, 1),
        ))
        db.session.commit()
    row = client.post(f"{IMPORTS}/", json={
        "text": "035720 1주 매수 체결 40,000원 2026-09-01 10:30", "consent": True,
    }).get_json()["pending"][0]
    assert row["ticker"] in ("035720.KS", "035720")
    assert row["status"] == "duplicate"
