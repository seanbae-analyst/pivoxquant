"""Bug hunt 2026-11-03 — 문 앞의 한 줄 "오늘 N번째".

자정(KST)을 넘긴 답·반복 열림 신호의 "오늘 N번째"가 0 이었다 — 돌려준 행은
어제 열렸는데 개수는 지금(오늘)으로 셌다. 그 행의 KST 하루로 센다.

같은 날 고친 다른 둘은 여기 없다: 답한 뒤 웹 문을 새로 고치면 열림이 하나 더
세던 것은 화면 쪽(``/pre-trade/door`` 가 신호를 보낸 뒤 ``launch`` 를 주소에서
지운다) — 서버는 답한 뒤의 열림을 일부러 새로 센다
(test_doorway.py::test_open_signal_dedupe_is_per_app_and_one_minute). 부팅의 RLS
단계 세션 정리는 PostgreSQL 잠금이라 SQLite 로 재현할 수 없다 (로컬 PG 16 에서
재현·확인).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from services.doorway import record_check, reply_line

# 23:59:40 KST
BEFORE_MIDNIGHT = datetime(2026, 11, 2, 14, 59, 40)


def test_an_answer_after_kst_midnight_counts_its_open_day(app, make_user):
    user = make_user(email="dw-midnight@test.com")
    with app.app_context():
        record_check(user["id"], {"intent": "open", "app": "toss"}, source="automation",
                     now=BEFORE_MIDNIGHT)
        out = record_check(user["id"], {"intent": "buy", "note": "삼성전자", "app": "toss"},
                           source="automation", now=BEFORE_MIDNIGHT + timedelta(seconds=30))
        assert out["created"] is False
        assert out["today"] == 1
        assert reply_line(out["check"], out["today"]).endswith("오늘 1번째 열림")


def test_a_repeated_open_signal_after_kst_midnight_is_not_zero(app, make_user):
    user = make_user(email="dw-midnight-open@test.com")
    with app.app_context():
        record_check(user["id"], {"intent": "open", "app": "kiwoom"}, source="automation",
                     now=BEFORE_MIDNIGHT + timedelta(seconds=10))
        out = record_check(user["id"], {"intent": "open", "app": "kiwoom"}, source="automation",
                           now=BEFORE_MIDNIGHT + timedelta(seconds=40))
        assert out["created"] is False
        assert out["today"] == 1


def test_a_new_open_after_midnight_does_not_count_yesterday(app, make_user):
    user = make_user(email="dw-midnight-new@test.com")
    with app.app_context():
        record_check(user["id"], {"intent": "look"}, source="automation", now=BEFORE_MIDNIGHT)
        out = record_check(user["id"], {"intent": "sell"}, source="automation",
                           now=BEFORE_MIDNIGHT + timedelta(minutes=1))
        assert out["created"] is True
        assert out["today"] == 1
