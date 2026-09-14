"""tests/test_imports_route.py — Import Inbox (/api/portfolio/imports).

Design: docs/product/IMPORT_INBOX_DESIGN.md §테스트. Fixtures are built
inline as strings (no broker files in the repo).
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest

BASE = "/api/portfolio/imports"

KIS_HEADER = "거래일자,종목명,종목코드,거래구분,수량,단가,거래금액,수수료"
KIS_ROW = "2026-09-01,삼성전자,005930,매수,10,71200,712000,0"
KIS_CSV = f"{KIS_HEADER}\n{KIS_ROW}\n"

OWN_HEADER = "traded_at,ticker,name,action,shares,price_per_share,total_value,currency,pnl"

TOSS_TEXT = "삼성전자 10주 매수 체결 71,200원"


@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _upload(client, data: bytes, filename: str, consent="true"):
    form = {"file": (io.BytesIO(data), filename)}
    if consent is not None:
        form["consent"] = consent
    return client.post(f"{BASE}/", data=form, content_type="multipart/form-data")


def _paste(client, text: str, consent=True):
    return client.post(f"{BASE}/", json={"text": text, "source": "screenshot_text", "consent": consent})


def _approve(client, pid: int, thesis="실적 발표 전에 미리 담아두려고 샀다"):
    return client.post(f"{BASE}/pending/{pid}/approve", json={"thesis": thesis})


# ── consent / input guards ───────────────────────────────────────────

class TestGuards:
    def test_no_consent_file_400(self, client, auth_user):
        r = _upload(client, KIS_CSV.encode("utf-8"), "kis.csv", consent="false")
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_CONSENT_REQUIRED"

    def test_no_consent_text_400(self, client, auth_user):
        r = _paste(client, TOSS_TEXT, consent=False)
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_CONSENT_REQUIRED"

    def test_no_file_or_text_400(self, client, auth_user):
        r = client.post(f"{BASE}/", json={"consent": True})
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_FILE_REQUIRED"

    def test_unsupported_format_400(self, client, auth_user):
        r = _upload(client, b"%PDF-1.4 ...", "statement.pdf")
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_UNSUPPORTED_FORMAT"

    def test_no_rows_400_lists_skipped(self, client, auth_user):
        csv = f"{KIS_HEADER}\n2026-09-01,,,입금,0,0,100000,0\n2026-09-02,삼성전자,005930,배당,0,0,1500,0\n"
        r = _upload(client, csv.encode("utf-8"), "kis.csv")
        assert r.status_code == 400
        body = r.get_json()
        assert body["code"] == "IMPORT_NO_ROWS"
        reasons = " ".join(s["reason"] for s in body["skipped"])
        assert "입금" in reasons and "배당" in reasons

    def test_file_too_large_413_json(self, client, auth_user):
        big = (KIS_CSV + ("x" * 100 + "\n") * 25_000).encode("utf-8")
        assert len(big) > 2 * 1024 * 1024
        r = _upload(client, big, "big.csv")
        assert r.status_code == 413
        assert r.get_json()["code"] == "IMPORT_FILE_TOO_LARGE"

    def test_unauthenticated_401(self, client):
        r = _paste(client, TOSS_TEXT)
        assert r.status_code == 401


# ── parsers through the route ────────────────────────────────────────

class TestCsvParsing:
    def test_kis_style_header(self, client, auth_user):
        r = _upload(client, KIS_CSV.encode("utf-8"), "kis.csv")
        assert r.status_code == 201, r.data
        body = r.get_json()
        assert body["batch"]["source"] == "csv"
        assert body["batch"]["row_count"] == 1
        assert body["batch"]["parsed_count"] == 1
        assert body["batch"]["broker_guess"] != ""
        assert body["mapping"]["side"] == "거래구분"
        assert body["mapping"]["price"] == "단가"
        assert body["unmapped_headers"] == []
        p = body["pending"][0]
        assert p["ticker"] == "005930.KS"
        assert p["name"] == "삼성전자"
        assert p["action"] == "BUY"
        assert p["shares"] == 10.0
        assert p["price"] == 71200.0
        assert p["currency"] == "KRW"
        assert p["traded_at"].startswith("2026-09-01")
        assert p["status"] == "pending"
        assert p["needs_ticker"] is False
        assert p["confidence"] == 1.0

    def test_cp949_encoding(self, client, auth_user):
        r = _upload(client, KIS_CSV.encode("cp949"), "kis_cp949.csv")
        assert r.status_code == 201, r.data
        p = r.get_json()["pending"][0]
        assert p["ticker"] == "005930.KS" and p["name"] == "삼성전자"

    def test_side_skip_and_amount_fallback(self, client, auth_user):
        csv = (
            "체결일자,종목명,매매구분,체결수량,체결금액\n"
            "20260901,삼성전자,현금매도,5,356000\n"
            "20260901,삼성전자,수수료,0,15\n"
        )
        r = _upload(client, csv.encode("utf-8"), "k.csv")
        assert r.status_code == 201, r.data
        body = r.get_json()
        assert len(body["pending"]) == 1
        p = body["pending"][0]
        assert p["action"] == "SELL"
        assert p["price"] == pytest.approx(71200.0)
        assert p["confidence"] < 1.0
        assert body["skipped"][0]["reason"].endswith("수수료")

    def test_xlsx_upload(self, client, auth_user):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["거래일자", "종목명", "종목코드", "거래구분", "수량", "단가"])
        ws.append([datetime(2026, 9, 1, 9, 30), "삼성전자", "005930", "매수", 10, 71200])
        buf = io.BytesIO()
        wb.save(buf)
        r = _upload(client, buf.getvalue(), "kis.xlsx")
        assert r.status_code == 201, r.data
        p = r.get_json()["pending"][0]
        assert p["ticker"] == "005930.KS" and p["traded_at"].startswith("2026-09-01T00:30")  # 09:30 KST → 00:30 UTC

    def test_own_export_round_trip(self, client, auth_user, app):
        """Rows in our own export format re-import 1:1 and, once approved,
        land in trade_history with the same values."""
        rows = [
            "2026-09-01T10:00:00,AAPL,Apple,BUY,5,190.12,950.6,USD,0",
            "2026-09-03T10:00:00,005930.KS,삼성전자,BUY,3,72000,216000,KRW,0",
        ]
        csv = OWN_HEADER + "\n" + "\n".join(rows) + "\n"
        r = _upload(client, csv.encode("utf-8"), "pivoxquant_trades.csv")
        assert r.status_code == 201, r.data
        body = r.get_json()
        assert body["batch"]["broker_guess"] == "pivoxquant"
        assert body["unmapped_headers"] == ["pnl"]
        by_ticker = {p["ticker"]: p for p in body["pending"]}
        assert set(by_ticker) == {"AAPL", "005930.KS"}
        assert by_ticker["AAPL"]["currency"] == "USD"
        assert by_ticker["AAPL"]["price"] == pytest.approx(190.12)
        assert by_ticker["005930.KS"]["name"] == "삼성전자"

        for p in body["pending"]:
            assert _approve(client, p["id"]).status_code == 200

        from models import TradeHistory
        with app.app_context():
            th = {t.ticker: t for t in TradeHistory.query.filter_by(user_id=auth_user["id"]).all()}
        assert th["AAPL"].shares == 5 and th["AAPL"].price_per_share == pytest.approx(190.12)
        assert th["AAPL"].currency == "USD"
        assert th["AAPL"].traded_at == datetime(2026, 9, 1, 10, 0)
        assert th["005930.KS"].total_value == pytest.approx(216000)
        assert th["005930.KS"].traded_at == datetime(2026, 9, 3, 10, 0)


class TestTextParsing:
    def test_toss_notification_line(self, client, auth_user):
        r = _paste(client, TOSS_TEXT)
        assert r.status_code == 201, r.data
        body = r.get_json()
        assert body["batch"]["source"] == "screenshot_text"
        p = body["pending"][0]
        assert p["ticker"] == "005930.KS"
        assert p["name"] == "삼성전자"
        assert p["action"] == "BUY"
        assert p["shares"] == 10.0
        assert p["price"] == 71200.0
        assert p["currency"] == "KRW"
        assert p["confidence"] == pytest.approx(0.6)  # no date on the line
        assert p["traded_at"].startswith(_now().strftime("%Y-%m-%d"))
        assert p["raw_snippet"] == TOSS_TEXT

    def test_multi_line_with_us_and_skips(self, client, auth_user):
        text = "\n".join([
            "체결 알림",
            "매수 체결 삼성전자 10주 @ 71,200원 2026-09-01 10:32",
            "Sold 3 TSLA @ $250.00 2026-09-02 14:05",
            "매수 5주 AAPL 190.12",
        ])
        r = _paste(client, text)
        assert r.status_code == 201, r.data
        body = r.get_json()
        assert len(body["pending"]) == 3
        assert body["skipped"][0]["row"] == 1
        by_ticker = {p["ticker"]: p for p in body["pending"]}
        assert by_ticker["005930.KS"]["traded_at"] == "2026-09-01T01:32:00"  # 10:32 KST → 01:32 UTC
        assert by_ticker["005930.KS"]["confidence"] == pytest.approx(0.9)
        assert by_ticker["TSLA"]["action"] == "SELL"
        assert by_ticker["TSLA"]["currency"] == "USD"
        assert by_ticker["AAPL"]["shares"] == 5.0
        assert by_ticker["AAPL"]["price"] == pytest.approx(190.12)

    def test_account_number_masked_in_snippet(self, client, auth_user):
        r = _paste(client, "계좌 123-45-678901 삼성전자 10주 매수 체결 71,200원 주문번호 20260901123456")
        assert r.status_code == 201, r.data
        snippet = r.get_json()["pending"][0]["raw_snippet"]
        assert "123-45-678901" not in snippet
        assert "20260901123456" not in snippet
        assert "***" in snippet


# ── duplicates ───────────────────────────────────────────────────────

class TestDuplicates:
    def test_same_upload_twice_marks_duplicate(self, client, auth_user):
        r1 = _upload(client, KIS_CSV.encode("utf-8"), "kis.csv")
        assert r1.status_code == 201
        r2 = _upload(client, KIS_CSV.encode("utf-8"), "kis.csv")
        assert r2.status_code == 201
        body = r2.get_json()
        assert body["pending"][0]["status"] == "duplicate"
        assert body["batch"]["duplicate_count"] == 1
        # the duplicate does not show up in the inbox
        lst = client.get(f"{BASE}/pending").get_json()
        assert lst["count"] == 1

    def test_within_batch_duplicate(self, client, auth_user):
        csv = f"{KIS_HEADER}\n{KIS_ROW}\n{KIS_ROW}\n"
        r = _upload(client, csv.encode("utf-8"), "kis.csv")
        assert r.status_code == 201
        statuses = sorted(p["status"] for p in r.get_json()["pending"])
        assert statuses == ["duplicate", "pending"]

    def test_existing_trade_history_marks_duplicate(self, client, auth_user, app):
        from extensions import db
        from models import TradeHistory
        with app.app_context():
            db.session.add(TradeHistory(
                user_id=auth_user["id"], ticker="005930.KS", name="삼성전자",
                action="BUY", shares=10.0, price_per_share=71200.0,
                total_value=712000.0, currency="KRW",
                traded_at=datetime(2026, 9, 1, 14, 20),
            ))
            db.session.commit()
        r = _upload(client, KIS_CSV.encode("utf-8"), "kis.csv")
        assert r.status_code == 201
        assert r.get_json()["pending"][0]["status"] == "duplicate"


# ── needs_ticker → PATCH → approve ───────────────────────────────────

class TestPatchAndApprove:
    def test_needs_ticker_then_patch_then_approve(self, client, auth_user, app):
        csv = f"{KIS_HEADER}\n2026-09-01,미등록종목명,,매수,10,71200,712000,0\n"
        r = _upload(client, csv.encode("utf-8"), "kis.csv")
        assert r.status_code == 201, r.data
        body = r.get_json()
        p = body["pending"][0]
        assert p["needs_ticker"] is True and p["ticker"] is None
        assert body["batch"]["unresolved_count"] == 1

        # approve blocked until a ticker exists
        r = _approve(client, p["id"])
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_TICKER_REQUIRED"

        r = client.patch(f"{BASE}/pending/{p['id']}", json={"ticker": "005930"})
        assert r.status_code == 200, r.data
        p2 = r.get_json()["pending"]
        assert p2["ticker"] == "005930.KS"
        assert p2["needs_ticker"] is False
        assert p2["name"] == "삼성전자"
        assert p2["currency"] == "KRW"

        r = _approve(client, p["id"])
        assert r.status_code == 200, r.data
        out = r.get_json()
        assert out["ok"] is True
        assert out["pending"]["status"] == "approved"
        assert out["pending"]["approved_trade_id"] == out["trade_id"]
        assert out["pending"]["approved_at"] is not None

        from models import Position
        with app.app_context():
            pos = Position.query.filter_by(user_id=auth_user["id"], ticker="005930.KS").one()
            assert pos.shares == 10 and pos.avg_cost == 71200
            assert pos.thesis == "실적 발표 전에 미리 담아두려고 샀다"
            assert pos.thesis_status == "pending"
            assert pos.added_at == datetime(2026, 9, 1)
            assert pos.buy_fx_rate == 0.0

    def test_patch_recomputes_duplicate(self, client, auth_user):
        r1 = _upload(client, KIS_CSV.encode("utf-8"), "kis.csv").get_json()
        csv2 = f"{KIS_HEADER}\n2026-09-01,삼성전자,005930,매수,11,71200,783200,0\n"
        r2 = _upload(client, csv2.encode("utf-8"), "kis.csv").get_json()
        assert r2["pending"][0]["status"] == "pending"
        r = client.patch(f"{BASE}/pending/{r2['pending'][0]['id']}", json={"shares": 10})
        assert r.status_code == 200
        assert r.get_json()["pending"]["status"] == "duplicate"
        assert r1["pending"][0]["status"] == "pending"

    def test_patch_invalid_values(self, client, auth_user):
        pid = _paste(client, TOSS_TEXT).get_json()["pending"][0]["id"]
        for payload in ({"shares": -1}, {"price": "abc"}, {"action": "HOLD"}, {"traded_at": "nope"}):
            r = client.patch(f"{BASE}/pending/{pid}", json=payload)
            assert r.status_code == 400, payload
            assert r.get_json()["code"] == "IMPORT_INVALID_FIELD"

    def test_thesis_required(self, client, auth_user):
        pid = _paste(client, TOSS_TEXT).get_json()["pending"][0]["id"]
        for thesis in (None, "", "  ", "ab", "x" * 501):
            r = client.post(f"{BASE}/pending/{pid}/approve", json={"thesis": thesis})
            assert r.status_code == 400, thesis
            assert r.get_json()["code"] == "IMPORT_THESIS_REQUIRED"
        lst = client.get(f"{BASE}/pending").get_json()
        assert lst["count"] == 1  # still pending

    def test_approve_creates_position_and_trade_no_capital_change(self, client, auth_user, app):
        from extensions import db
        from models import Position, TradeHistory, User
        with app.app_context():
            u = db.session.get(User, auth_user["id"])
            cap_usd, cap_krw = u.available_capital, u.available_capital_krw
        pid = _paste(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01 10:32").get_json()["pending"][0]["id"]
        r = _approve(client, pid)
        assert r.status_code == 200, r.data
        out = r.get_json()
        with app.app_context():
            pos = db.session.get(Position, out["position_id"])
            assert pos.ticker == "005930.KS" and pos.shares == 10
            th = db.session.get(TradeHistory, out["trade_id"])
            assert th.action == "BUY" and th.shares == 10 and th.price_per_share == 71200
            assert th.total_value == 712000 and th.currency == "KRW"
            assert th.traded_at == datetime(2026, 9, 1, 1, 32)  # KST 10:32 stored as UTC
            assert th.name == "삼성전자"
            u = db.session.get(User, auth_user["id"])
            assert u.available_capital == cap_usd
            assert u.available_capital_krw == cap_krw
        # approved rows leave the inbox
        assert client.get(f"{BASE}/pending").get_json()["count"] == 0

    def test_approve_twice_not_pending(self, client, auth_user):
        pid = _paste(client, TOSS_TEXT).get_json()["pending"][0]["id"]
        assert _approve(client, pid).status_code == 200
        r = _approve(client, pid)
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_NOT_PENDING"
        r = client.patch(f"{BASE}/pending/{pid}", json={"shares": 3})
        assert r.get_json()["code"] == "IMPORT_NOT_PENDING"

    def test_buy_more_weighted_average_and_fx(self, client, auth_user, app, add_position):
        add_position(auth_user["id"], ticker="AAPL", shares=10.0, avg_cost=100.0, buy_fx=1000.0)
        pid = _paste(client, "Bought 10 AAPL @ $200.00 2026-09-01 10:00").get_json()["pending"][0]["id"]
        r = _approve(client, pid)
        assert r.status_code == 200, r.data
        from models import Position
        with app.app_context():
            pos = Position.query.filter_by(user_id=auth_user["id"], ticker="AAPL").one()
            assert pos.shares == 20
            assert pos.avg_cost == pytest.approx(150.0)
            # cost-weighted: (1000*1000 + 1300*2000) / 3000
            assert pos.buy_fx_rate == pytest.approx(1200.0)
            assert pos.thesis == "실적 발표 전에 미리 담아두려고 샀다"

    def test_new_usd_position_uses_fx(self, client, auth_user, app):
        pid = _paste(client, "Bought 5 AAPL @ $190.12 2026-09-01").get_json()["pending"][0]["id"]
        assert _approve(client, pid).status_code == 200
        from models import Position
        with app.app_context():
            pos = Position.query.filter_by(user_id=auth_user["id"], ticker="AAPL").one()
            assert pos.buy_fx_rate == 1300.0

    def test_sell_exceeds_holding_400(self, client, auth_user, app, add_position):
        add_position(auth_user["id"], ticker="005930.KS", shares=5.0, avg_cost=70000.0, buy_fx=0.0)
        pid = _paste(client, "삼성전자 10주 매도 체결 71,200원").get_json()["pending"][0]["id"]
        r = _approve(client, pid)
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_SELL_EXCEEDS_HOLDING"
        from models import Position, TradeHistory
        with app.app_context():
            assert Position.query.filter_by(user_id=auth_user["id"], ticker="005930.KS").one().shares == 5
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 0
        assert client.get(f"{BASE}/pending").get_json()["count"] == 1

    def test_sell_without_position_400(self, client, auth_user):
        pid = _paste(client, "삼성전자 1주 매도 체결 71,200원").get_json()["pending"][0]["id"]
        r = _approve(client, pid)
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_SELL_EXCEEDS_HOLDING"

    def test_sell_partial_and_full_close(self, client, auth_user, app, add_position):
        add_position(auth_user["id"], ticker="005930.KS", shares=10.0, avg_cost=70000.0, buy_fx=0.0)
        pid = _paste(client, "삼성전자 4주 매도 체결 71,200원 2026-09-02 10:00").get_json()["pending"][0]["id"]
        out = _approve(client, pid).get_json()
        from extensions import db
        from models import Position, TradeHistory
        with app.app_context():
            pos = Position.query.filter_by(user_id=auth_user["id"], ticker="005930.KS").one()
            assert pos.shares == 6
            th = db.session.get(TradeHistory, out["trade_id"])
            assert th.action == "SELL" and th.pnl == pytest.approx(4 * 1200)
        pid = _paste(client, "삼성전자 6주 매도 체결 71,200원 2026-09-03 10:00").get_json()["pending"][0]["id"]
        assert _approve(client, pid).status_code == 200
        with app.app_context():
            assert Position.query.filter_by(user_id=auth_user["id"], ticker="005930.KS").first() is None

    def test_reject(self, client, auth_user):
        pid = _paste(client, TOSS_TEXT).get_json()["pending"][0]["id"]
        r = client.post(f"{BASE}/pending/{pid}/reject")
        assert r.status_code == 200 and r.get_json()["ok"] is True
        assert client.get(f"{BASE}/pending").get_json()["count"] == 0
        r = client.post(f"{BASE}/pending/{pid}/reject")
        assert r.get_json()["code"] == "IMPORT_NOT_PENDING"

    def test_pre_trade_reflection_match(self, client, auth_user, app):
        from extensions import db
        from models import PreTradeReflection
        traded = datetime(2026, 9, 1, 10, 32)
        with app.app_context():
            old = PreTradeReflection(
                user_id=auth_user["id"], intended_ticker="005930.KS", intended_side="BUY",
                rationale="열흘 전 기록", cooldown_started_at=traded - timedelta(days=10),
                cooldown_ends_at=traded - timedelta(days=10), created_at=traded - timedelta(days=10),
            )
            recent = PreTradeReflection(
                user_id=auth_user["id"], intended_ticker="005930.KS", intended_side="BUY",
                rationale="이틀 전 기록", cooldown_started_at=traded - timedelta(days=2),
                cooldown_ends_at=traded - timedelta(days=2), created_at=traded - timedelta(days=2),
            )
            db.session.add_all([old, recent])
            db.session.commit()
            recent_id = recent.id
        r = _paste(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01 10:32")
        assert r.get_json()["pending"][0]["pre_trade_reflection_id"] == recent_id
        r = _paste(client, "삼성전자 10주 매수 체결 71,300원 2026-09-12 10:32")  # 11d after the reflections → no match
        assert r.get_json()["pending"][0]["pre_trade_reflection_id"] is None


# ── listing + isolation ──────────────────────────────────────────────

class TestListAndIsolation:
    def test_pending_list_newest_first_pending_only(self, client, auth_user):
        a = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 10:00").get_json()["pending"][0]["id"]
        b = _paste(client, "삼성전자 2주 매수 체결 71,200원 2026-09-01 10:00").get_json()["pending"][0]["id"]
        client.post(f"{BASE}/pending/{a}/reject")
        lst = client.get(f"{BASE}/pending").get_json()
        assert [p["id"] for p in lst["pending"]] == [b]
        assert lst["count"] == 1

    def test_user_isolation(self, client, make_user, app):
        owner = make_user(email="owner@test.com")
        other = make_user(email="other@test.com")
        assert client.post("/api/auth/login", json={"email": owner["email"], "password": owner["password"]}).status_code == 200
        pid = _paste(client, TOSS_TEXT).get_json()["pending"][0]["id"]
        client.post("/api/auth/logout")
        assert client.post("/api/auth/login", json={"email": other["email"], "password": other["password"]}).status_code == 200

        assert client.get(f"{BASE}/pending").get_json()["count"] == 0
        assert client.patch(f"{BASE}/pending/{pid}", json={"shares": 1}).status_code == 404
        assert _approve(client, pid).status_code == 404
        assert client.post(f"{BASE}/pending/{pid}/reject").status_code == 404

        # the same fill uploaded by the other user is NOT a duplicate of the owner's
        r = _paste(client, TOSS_TEXT)
        assert r.status_code == 201 and r.get_json()["pending"][0]["status"] == "pending"

        from extensions import db
        from models import Position, TradeHistory
        from models.import_batch import PendingTrade
        with app.app_context():
            assert db.session.get(PendingTrade, pid).status == "pending"
            assert Position.query.filter_by(user_id=owner["id"]).count() == 0
            assert TradeHistory.query.filter_by(user_id=owner["id"]).count() == 0


# ── review fixes 2026-09-14 ───────────────────────────────────────────

class TestReviewFixes:
    def _csv(self, client, body: str, name="f.csv"):
        import io
        return client.post(
            "/api/portfolio/imports/",
            data={"file": (io.BytesIO(body.encode("utf-8")), name), "consent": "true"},
            content_type="multipart/form-data",
        )

    def test_nan_and_huge_amounts_are_rejected(self, client, auth_user):
        # JSON NaN / 1e300 used to pass ``v <= 0`` and poison positions on approve.
        r = client.post("/api/portfolio/imports/", data='{"text": "", "consent": true, "source": "screenshot_text"}',
                        content_type="application/json")
        assert r.status_code == 400
        r = self._csv(client, "거래일자,종목코드,거래구분,수량,단가\n2026-09-01,005930,매수,1000000000000,71200\n")
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"
        assert "범위" in r.get_json()["skipped"][0]["reason"]

    def test_patch_rejects_nan_inf_and_long_ticker(self, client, auth_user):
        r = self._csv(client, "거래일자,종목코드,거래구분,수량,단가\n2026-09-01,005930,매수,10,71200\n")
        pid = r.get_json()["pending"][0]["id"]
        for body in ('{"shares": NaN}', '{"price": Infinity}', '{"shares": 1e300}'):
            rr = client.patch(f"/api/portfolio/imports/pending/{pid}", data=body, content_type="application/json")
            assert rr.status_code == 400 and rr.get_json()["code"] == "IMPORT_INVALID_FIELD", body
        rr = client.patch(f"/api/portfolio/imports/pending/{pid}", json={"ticker": "A" * 21})
        assert rr.status_code == 400 and rr.get_json()["code"] == "IMPORT_INVALID_FIELD"
        rr = client.patch(f"/api/portfolio/imports/pending/{pid}", json={"ticker": "삼성전자"})
        assert rr.status_code == 400
        rr = client.patch(f"/api/portfolio/imports/pending/{pid}", json={"traded_at": "2099-01-01"})
        assert rr.status_code == 400

    def test_signed_sell_quantity_is_kept(self, client, auth_user):
        r = self._csv(client, "거래일자,종목코드,거래구분,수량,단가\n2026-09-01,005930,매수,10,71200\n2026-09-02,005930,매도,-4,73000\n")
        assert r.status_code == 201, r.get_json()
        rows = {p["action"]: p for p in r.get_json()["pending"]}
        assert rows["SELL"]["shares"] == 4.0  # // legal-ok — data field

    def test_header_specificity_beats_column_order(self, client, auth_user):
        # ``구분`` (현금/신용) comes first but ``매매구분`` is the side column.
        r = self._csv(client, "거래일자,구분,종목명,종목코드,매매구분,수량,단가\n2026-09-01,현금,삼성전자,005930,매수,10,71200\n")
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["mapping"]["side"] == "매매구분"

    def test_broker_prefix_is_not_the_security(self, client, auth_user):
        r = client.post("/api/portfolio/imports/",
                        json={"text": "[키움증권] 삼성전자 10주 매수 체결 71,200원", "source": "screenshot_text", "consent": True})
        assert r.status_code == 201, r.get_json()
        p = r.get_json()["pending"][0]
        assert p["ticker"] == "005930.KS" and p["name"] == "삼성전자"

    def test_kst_wallclock_is_stored_as_utc(self, client, auth_user):
        r = self._csv(client, "거래일자,체결시간,종목코드,거래구분,수량,단가\n2026-09-01,10:32:00,005930,매수,10,71200\n")
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["pending"][0]["traded_at"].startswith("2026-09-01T01:32")
        # Our own export is already UTC — round-trips untouched.
        own = "\ufefftraded_at,ticker,name,action,shares,price_per_share,total_value,currency,pnl\n2026-08-20T10:00:00,005930.KS,삼성전자,BUY,5,70000,350000,KRW,0\n"
        r2 = self._csv(client, own, name="export.csv")
        assert r2.get_json()["pending"][0]["traded_at"].startswith("2026-08-20T10:00")

    def test_future_fill_is_skipped(self, client, auth_user):
        r = self._csv(client, "거래일자,종목코드,거래구분,수량,단가\n2099-01-01,005930,매수,10,71200\n")
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"

    def test_rejected_row_does_not_block_reupload(self, client, auth_user):
        body = "거래일자,종목코드,거래구분,수량,단가\n2026-09-01,005930,매수,10,71200\n"
        pid = self._csv(client, body).get_json()["pending"][0]["id"]
        assert client.post(f"/api/portfolio/imports/pending/{pid}/reject").status_code == 200
        r = self._csv(client, body)
        assert r.get_json()["pending"][0]["status"] == "pending"

    def test_scrub_skips_data_fields_only(self, client, auth_user):
        # raw_snippet is the user's own broker text — echoed back verbatim; action stays a data value.
        r = client.post("/api/portfolio/imports/",
                        json={"text": "삼성전자 10주 매수 체결 71,200원", "source": "screenshot_text", "consent": True})
        p = r.get_json()["pending"][0]
        assert p["raw_snippet"] == "삼성전자 10주 매수 체결 71,200원"
        assert p["action"] == "BUY"  # // legal-ok — data field

    def test_free_tier_position_cap_applies_to_imports(self, client, auth_user, add_position):
        for t in ("AAPL", "MSFT", "NVDA"):
            add_position(auth_user["id"], ticker=t)
        r = self._csv(client, "거래일자,종목코드,거래구분,수량,단가\n2026-09-01,005930,매수,10,71200\n")
        pid = r.get_json()["pending"][0]["id"]
        a = client.post(f"/api/portfolio/imports/pending/{pid}/approve", json={"thesis": "반도체 업황 회복"})
        assert a.status_code == 400 and a.get_json()["code"] == "TIER_LIMIT"


# ── order-lifecycle notices are not fills ────────────────────────────

class TestNonFillNotices:
    """A macro forwards every broker notification, not only fills. 접수·정정·
    취소·미체결 lines share the 매수/N주/원 vocabulary and must not land in the
    inbox as trades."""

    def _skipped_reasons(self, r):
        return [s["reason"] for s in r.get_json()["skipped"]]

    def test_order_accepted_notice_is_skipped(self, client, auth_user):
        r = _paste(client, "[토스증권] 삼성전자 10주 매수 주문이 접수되었습니다 71,200원")
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"
        assert self._skipped_reasons(r) == ["주문 접수·정정·취소 알림 (체결 아님)"]

    def test_cancel_and_modify_notices_are_skipped(self, client, auth_user):
        text = "\n".join([
            "삼성전자 10주 매수 주문 취소 71,200원",
            "삼성전자 10주 매수 정정 주문 완료 71,000원",
            "삼성전자 10주 매수 미체결 71,200원",
            "삼성전자 10주 매수 체결 취소 71,200원",
        ])
        r = _paste(client, text)
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"
        assert self._skipped_reasons(r) == [
            "주문 접수·정정·취소 알림 (체결 아님)",
            "주문 접수·정정·취소 알림 (체결 아님)",
            "미체결 알림 (체결 아님)",
            "체결 취소 알림 (기록할 체결 아님)",
        ]

    def test_modified_order_that_filled_is_a_fill(self, client, auth_user):
        r = _paste(client, "[키움증권] 정정 주문이 체결되었습니다 삼성전자 10주 매수 체결단가 71,000원")
        assert r.status_code == 201, r.get_json()
        p = r.get_json()["pending"][0]
        assert p["name"] == "삼성전자" and p["shares"] == 10.0 and p["price"] == 71000.0

    def test_mixed_paste_keeps_only_the_fill(self, client, auth_user):
        text = "삼성전자 10주 매수 주문이 접수되었습니다 71,200원\n삼성전자 10주 매수 체결 71,200원\n"
        r = _paste(client, text)
        assert r.status_code == 201, r.get_json()
        assert len(r.get_json()["pending"]) == 1
        skipped = r.get_json()["skipped"]
        assert len(skipped) == 1 and skipped[0]["row"] == 1

    def test_english_order_placed_is_skipped_but_bought_is_not(self, client, auth_user):
        r = _paste(client, "Order placed: Buy 5 AAPL @ $190.12")
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"
        assert self._skipped_reasons(r) == ["주문 접수·정정·취소 알림 (체결 아님)"]
        ok = _paste(client, "Bought 5 AAPL @ $190.12")
        assert ok.status_code == 201, ok.get_json()
        assert ok.get_json()["pending"][0]["ticker"] == "AAPL"

    def test_webhook_forwarded_cancel_is_skipped(self, client, auth_user):
        tok = client.post(f"{BASE}/tokens", json={"name": "macro", "consent": True}).get_json()["token"]
        r = client.post(f"{BASE}/webhook", data="삼성전자 10주 매수 주문 취소 71,200원",
                        content_type="text/plain", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"
