"""tests/test_imports_image.py — fill-screen screenshot import (server half).

Design: docs/product/SCREENSHOT_IMPORT_DESIGN.md. The screenshot is read in
the browser (Tesseract.js + frontend/src/lib/fill-ocr/parse.ts; accuracy eval
in frontend/src/lib/fill-ocr/__tests__/eval.test.ts). The server only gets
the rows the user reviewed and completed, as JSON — no image, no model call.
These tests pin that contract: strict re-validation, fuzzy-name handling,
the confirm gate, and that nothing reaches the ledger before approval.
"""
from __future__ import annotations

import math

import pytest

BASE = "/api/portfolio/imports"


def _row(**kw):
    base = {
        "date": "2026-09-01", "time": "10:15", "tz": "KST", "name": "삼성전자",
        "code": "005930", "action": "buy", "shares": 10, "price": 71200,
        "currency": "KRW", "source_text": "09.01 10:15 삼성전자 매수 10주 71,200원",
        "user_filled": [],
    }
    base.update(kw)
    return base


def _post(client, *rows, consent=True, **extra):
    body = {"rows": list(rows), "consent": consent, **extra}
    return client.post(f"{BASE}/image", json=body)


@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)


# ── contract / validation ────────────────────────────────────────────

class TestContract:
    def test_unauthenticated_401(self, client):
        assert _post(client, _row()).status_code == 401

    def test_no_consent_400(self, client, auth_user):
        r = _post(client, _row(), consent=False)
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_CONSENT_REQUIRED"

    def test_no_rows_400(self, client, auth_user):
        r = client.post(f"{BASE}/image", json={"consent": True, "rows": []})
        assert r.get_json()["code"] == "IMPORT_INVALID_FIELD"

    def test_multipart_image_is_not_accepted(self, client, auth_user):
        import io
        r = client.post(f"{BASE}/image",
                        data={"image": (io.BytesIO(b"\x89PNG...."), "c.png"), "consent": "true"},
                        content_type="multipart/form-data")
        assert r.status_code == 400  # JSON rows only — images never reach the server

    @pytest.mark.parametrize("patch", [
        {"action": None}, {"action": "hold"}, {"shares": None}, {"shares": 0},
        {"price": -1}, {"price": float("nan")}, {"currency": "JPY"}, {"date": None},
        {"date": "2026-13-40"}, {"date": "09-01"}, {"time": "25:00"},
        {"name": "", "code": ""}, {"shares": 1.5},  # KRW fractional
    ])
    def test_incomplete_or_invalid_row_400(self, client, auth_user, app, patch):
        r = _post(client, _row(**patch))
        assert r.status_code == 400, patch
        assert r.get_json()["code"] == "IMPORT_INVALID_FIELD"
        from models.import_batch import ImportBatch
        with app.app_context():
            assert ImportBatch.query.count() == 0

    def test_future_date_skipped(self, client, auth_user):
        body = _post(client, _row(), _row(code="000660", name="SK하이닉스", date="2099-01-01")).get_json()
        assert [p["ticker"] for p in body["pending"]] == ["005930.KS"]
        assert any("범위 밖" in s["reason"] for s in body["skipped"])


# ── rows → pending ───────────────────────────────────────────────────

class TestIngest:
    def test_rows_land_in_pending_not_ledger(self, client, auth_user, app):
        r = _post(client, _row(),
                  _row(name="Apple", code="AAPL", action="sell", shares=0.25, price=231.5,
                       currency="USD", tz="ET", time="15:42:18"),
                  broker="toss")
        assert r.status_code == 201, r.get_json()
        body = r.get_json()
        assert body["batch"]["source"] == "screenshot_image"
        assert body["batch"]["broker_guess"] == "toss"
        rows = {p["ticker"]: p for p in body["pending"]}
        sam, aapl = rows["005930.KS"], rows["AAPL"]
        assert sam["action"] == "BUY" and sam["shares"] == 10 and sam["price"] == 71200
        assert sam["traded_at"].startswith("2026-09-01T01:15")  # 10:15 KST → UTC
        assert sam["needs_confirm"] is False and sam["confidence"] >= 0.7
        assert aapl["shares"] == 0.25 and aapl["currency"] == "USD"
        # ET clock is not converted by a guessed offset — date only.
        assert aapl["traded_at"].startswith("2026-09-01T00:00")
        from models import Position, TradeHistory
        with app.app_context():
            assert Position.query.filter_by(user_id=auth_user["id"]).count() == 0
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 0

    def test_bare_kr_code_normalised(self, client, auth_user):
        p = _post(client, _row(code="005930", name="")).get_json()["pending"][0]
        assert p["ticker"] == "005930.KS" and p["currency"] == "KRW"

    def test_exact_name_resolves_without_confirm(self, client, auth_user):
        p = _post(client, _row(code="", name="SK하이닉스")).get_json()["pending"][0]
        assert p["ticker"] == "000660.KS" and p["needs_confirm"] is False

    def test_fuzzy_name_needs_confirm(self, client, auth_user):
        p = _post(client, _row(code="", name="SK하이닉")).get_json()["pending"][0]
        assert p["ticker"] == "000660.KS"
        assert p["needs_confirm"] is True
        assert "읽은 이름" in p["raw_snippet"]

    def test_unmatched_name_needs_ticker(self, client, auth_user):
        p = _post(client, _row(code="", name="어떤이상한종목이름")).get_json()["pending"][0]
        assert p["ticker"] is None and p["needs_ticker"] is True

    def test_user_filled_fields_noted(self, client, auth_user):
        p = _post(client, _row(user_filled=["price", "side"])).get_json()["pending"][0]
        assert "직접 입력: 단가·구분" in p["raw_snippet"]

    def test_account_number_masked(self, client, auth_user):
        p = _post(client, _row(source_text="계좌 12345678-01 삼성전자 매수 10주")).get_json()["pending"][0]
        assert "12345678" not in p["raw_snippet"]

    def test_unknown_broker_value_ignored(self, client, auth_user):
        body = _post(client, _row(), broker="<script>").get_json()
        assert body["batch"]["broker_guess"] == "unknown"

    def test_overlapping_captures_dedupe(self, client, auth_user):
        a = _row(time="10:15")
        b = _row(name="SK하이닉스", code="000660", price=180000, time="11:00")
        c = _row(name="NAVER", code="035420", price=200000, time="13:30")
        _post(client, a, b)
        body = _post(client, b, c).get_json()
        assert {p["ticker"]: p["status"] for p in body["pending"]} == {
            "000660.KS": "duplicate", "035420.KS": "pending"}

    def test_user_isolation(self, client, auth_user, app, make_user):
        body = _post(client, _row()).get_json()
        other = make_user(email="other@test.com")
        from extensions import db
        from models.import_batch import ImportBatch, PendingTrade
        with app.app_context():
            assert db.session.get(ImportBatch, body["batch"]["id"]).user_id == auth_user["id"]
            assert PendingTrade.query.filter_by(user_id=other["id"]).count() == 0


# ── confirm gate for fuzzy-matched rows ──────────────────────────────

class TestConfirmGate:
    def _fuzzy(self, client):
        return _post(client, _row(code="", name="SK하이닉")).get_json()["pending"][0]

    def test_approve_without_confirm_400(self, client, auth_user, app):
        p = self._fuzzy(client)
        r = client.post(f"{BASE}/pending/{p['id']}/approve", json={"thesis": "기록으로 남긴다"})
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_CONFIRM_REQUIRED"
        from models import TradeHistory
        with app.app_context():
            assert TradeHistory.query.count() == 0

    def test_approve_with_confirm_ok(self, client, auth_user):
        p = self._fuzzy(client)
        r = client.post(f"{BASE}/pending/{p['id']}/approve",
                        json={"thesis": "기록으로 남긴다", "confirm_values": True})
        assert r.status_code == 200, r.get_json()

    def test_patch_makes_row_user_verified(self, client, auth_user):
        p = self._fuzzy(client)
        r = client.patch(f"{BASE}/pending/{p['id']}", json={"ticker": "000660.KS"})
        assert r.status_code == 200 and r.get_json()["pending"]["needs_confirm"] is False
        r = client.post(f"{BASE}/pending/{p['id']}/approve", json={"thesis": "기록으로 남긴다"})
        assert r.status_code == 200

    def test_text_import_low_confidence_unaffected(self, client, auth_user):
        r = client.post(f"{BASE}/", json={"text": "삼성전자 10주 매수 체결 71,200원",
                                          "source": "screenshot_text", "consent": True})
        p = r.get_json()["pending"][0]
        assert p["confidence"] < 0.7 and p["needs_confirm"] is False
        r = client.post(f"{BASE}/pending/{p['id']}/approve", json={"thesis": "기록으로 남긴다"})
        assert r.status_code == 200


# ── prices: screen values only; approval stays NaN-free ──────────────

class TestPriceSafety:
    def test_import_never_calls_quote_services(self, client, auth_user, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("quote service must not be called during image import")

        monkeypatch.setattr("routes.portfolio.overlay_prices", boom, raising=False)
        p = _post(client, _row(price=71200)).get_json()["pending"][0]
        assert p["price"] == 71200

    def _approve_all(self, client, pending):
        for p in pending:
            r = client.post(f"{BASE}/pending/{p['id']}/approve",
                            json={"thesis": "캡처로 옮긴 기존 체결 기록"})
            assert r.status_code == 200, r.get_json()

    def _assert_finite(self, obj):
        if isinstance(obj, float):
            assert math.isfinite(obj), obj
        elif isinstance(obj, dict):
            for v in obj.values():
                self._assert_finite(v)
        elif isinstance(obj, list):
            for v in obj:
                self._assert_finite(v)

    def _approve_kr_and_fractional_us(self, client):
        body = _post(client, _row(code="005930"),
                     _row(name="Apple", code="AAPL", shares=0.5, price=230.0, currency="USD")).get_json()
        self._approve_all(client, body["pending"])

    def test_portfolio_after_approve_display_off(self, client, auth_user, market_display_off):
        self._approve_kr_and_fractional_us(client)
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        assert b"NaN" not in r.data and b"Infinity" not in r.data
        body = r.get_json()
        self._assert_finite(body)
        rows = {p["ticker"]: p for p in body["positions"]}
        assert set(rows) == {"005930.KS", "AAPL"}
        assert rows["005930.KS"]["avg_cost"] == 71200 and rows["005930.KS"]["price"] is None
        assert rows["AAPL"]["shares"] == 0.5 and rows["AAPL"]["avg_cost"] == 230.0

    def test_portfolio_after_approve_no_quote_yet(self, client, auth_user, market_display_on, monkeypatch):
        monkeypatch.setattr("routes.portfolio.overlay_prices", lambda tickers: {})
        self._approve_kr_and_fractional_us(client)
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        assert b"NaN" not in r.data and b"Infinity" not in r.data
        body = r.get_json()
        self._assert_finite(body)
        rows = {p["ticker"]: p for p in body["positions"]}
        assert rows["005930.KS"]["price"] == 71200 and rows["AAPL"]["price"] == 230.0
        assert rows["005930.KS"]["currency"] == "KRW" and rows["AAPL"]["currency"] == "USD"


class TestFuzzyUnit:
    def test_needs_clear_margin(self):
        from services.imports.ocr_rows import fuzzy_kr_ticker
        index = {"삼성전자": "005930.KS", "삼성전기": "009150.KS", "SK하이닉스": "000660.KS"}
        assert fuzzy_kr_ticker("삼성전", index) is None  # 전자 vs 전기 — ambiguous
        assert fuzzy_kr_ticker("SK하이닉", index) == ("000660.KS", "SK하이닉스")
        assert fuzzy_kr_ticker("AB", index) is None  # no Hangul

    def test_unique_hangul_tail(self):
        from services.imports.ocr_rows import fuzzy_kr_ticker
        index = {"SK하이닉스": "000660.KS", "이닉스": "452400.KQ", "삼성전자": "005930.KS", "LG전자": "066570.KS"}
        # "SK" misread next to the logo — "이닉스" is closer by ratio, not by tail.
        assert fuzzy_kr_ticker("이하이닉스", index) == ("000660.KS", "SK하이닉스")
        assert fuzzy_kr_ticker("하이닉스", index) == ("000660.KS", "SK하이닉스")
        assert fuzzy_kr_ticker("XX전자", index) is None  # tail "X전자" is not four Hangul


# ── review fixes (2026-09-27): Postgres lock, currency, codes ───────

class TestReviewFixes:
    def test_approve_lock_query_has_no_outer_join_on_postgres(self, app):
        """SELECT … FOR UPDATE must not carry a LEFT OUTER JOIN (Postgres
        rejects it); SQLite hides this, so compile against the PG dialect."""
        from sqlalchemy.dialects import postgresql
        from extensions import db
        from models.import_batch import PendingTrade
        with app.app_context():
            q = db.session.query(PendingTrade).filter_by(id=1, user_id=1).with_for_update()
            sql = str(q.statement.compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql
        assert "JOIN" not in sql.upper()

    def test_us_code_with_krw_price_is_skipped(self, client, auth_user):
        body = _post(client, _row(),
                     _row(name="애플", code="AAPL", price=312000, currency="KRW")).get_json()
        assert [p["ticker"] for p in body["pending"]] == ["005930.KS"]
        assert any("통화 불일치" in s["reason"] for s in body["skipped"])

    def test_patch_ticker_to_other_currency_refused(self, client, auth_user):
        p = _post(client, _row(code="", name="어떤이상한종목이름")).get_json()["pending"][0]
        r = client.patch(f"{BASE}/pending/{p['id']}", json={"ticker": "AAPL"})
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_CURRENCY_MISMATCH"
        again = client.get(f"{BASE}/pending").get_json()["pending"][0]
        assert again["ticker"] is None and again["currency"] == "KRW"

    def test_editing_numbers_does_not_clear_fuzzy_confirm(self, client, auth_user):
        p = _post(client, _row(code="", name="SK하이닉")).get_json()["pending"][0]
        r = client.patch(f"{BASE}/pending/{p['id']}", json={"price": 71300})
        assert r.get_json()["pending"]["needs_confirm"] is True

    def test_unlisted_six_digit_code_ignored(self, client, auth_user):
        p = _post(client, _row(code="372500", name="삼성전자")).get_json()["pending"][0]
        assert p["ticker"] == "005930.KS"  # resolved by the name, not the price-shaped "code"
        assert "코드 무시" in p["raw_snippet"]

    def test_code_name_conflict_needs_confirm(self, client, auth_user):
        p = _post(client, _row(code="000660", name="삼성전자")).get_json()["pending"][0]
        assert p["needs_confirm"] is True


# ── second review (2026-09-27) ────────────────────────────────────────

class TestSecondReview:
    def test_patch_ticker_with_explicit_currency_still_refused(self, client, auth_user):
        p = _post(client, _row(code="", name="어떤이상한종목이름", price=312000)).get_json()["pending"][0]
        r = client.patch(f"{BASE}/pending/{p['id']}", json={"ticker": "AAPL", "currency": "KRW"})
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_CURRENCY_MISMATCH"
        again = client.get(f"{BASE}/pending").get_json()["pending"][0]
        assert again["ticker"] is None and again["currency"] == "KRW" and again["price"] == 312000

    def test_patch_currency_alone_refused_on_screenshot_row(self, client, auth_user):
        p = _post(client, _row(code="", name="어떤이상한종목이름")).get_json()["pending"][0]
        r = client.patch(f"{BASE}/pending/{p['id']}", json={"currency": "USD"})
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_CURRENCY_MISMATCH"

    def test_latin_korean_etf_name_in_won_is_not_a_us_symbol(self, client, auth_user):
        body = _post(client, _row(code="", name="TIGER", price=12000)).get_json()
        assert body["skipped"] == [] or all("통화" not in s["reason"] for s in body["skipped"])
        p = body["pending"][0]
        assert p["ticker"] is None and p["needs_ticker"] is True and p["currency"] == "KRW"

    def test_latin_name_in_usd_still_resolves(self, client, auth_user):
        p = _post(client, _row(code="", name="AAPL", price=231.5, currency="USD")).get_json()["pending"][0]
        assert p["ticker"] == "AAPL"

    def test_all_rows_skipped_returns_reasons(self, client, auth_user):
        r = _post(client, _row(name="애플", code="AAPL", price=312000, currency="KRW"))
        assert r.status_code == 400
        body = r.get_json()
        assert body["code"] == "IMPORT_NO_ROWS"
        assert any("통화 불일치" in s["reason"] for s in body["skipped"])

    def test_renaming_does_not_clear_fuzzy_confirm(self, client, auth_user):
        p = _post(client, _row(code="", name="SK하이닉")).get_json()["pending"][0]
        r = client.patch(f"{BASE}/pending/{p['id']}", json={"name": "SK하이닉스"})
        assert r.get_json()["pending"]["needs_confirm"] is True


class TestFuzzyJamo:
    """OCR garbles strokes, not syllables: 뉴→느, 워→표, 조→소 (2026-09-28, iPhone
    captures). Jamo-level matching is a fallback after the syllable match."""

    def test_stroke_level_misreads_match(self):
        from services.imports.ocr_rows import fuzzy_kr_ticker
        index = {"뉴스케일파워": "SMR", "스카이라이프": "053210.KQ", "조비에비에이션": "JOBY",
                 "삼성전자": "005930.KS", "삼성전자우": "005935.KS", "삼성전기": "009150.KS",
                 "아이티센글로벌": "124500.KQ", "아이센스": "099190.KQ", "아이티센엔텍": "010280.KS"}
        assert fuzzy_kr_ticker("느스케일표", index) == ("SMR", "뉴스케일파워")
        assert fuzzy_kr_ticker("는스커 (일파이효워", index) == ("SMR", "뉴스케일파워")
        assert fuzzy_kr_ticker("소비에비에이션", index) == ("JOBY", "조비에비에이션")
        assert fuzzy_kr_ticker("아이티센글 =u", index) == ("124500.KQ", "아이티센글로벌")
        assert fuzzy_kr_ticker("심성전자", index) == ("005930.KS", "삼성전자")

    def test_ambiguous_or_foreign_words_stay_unmatched(self):
        from services.imports.ocr_rows import fuzzy_kr_ticker
        index = {"삼성전자": "005930.KS", "삼성전기": "009150.KS", "뉴스케일파워": "SMR"}
        assert fuzzy_kr_ticker("삼성전", index) is None  # 전자 / 전기
        assert fuzzy_kr_ticker("해외주식", index) is None
        assert fuzzy_kr_ticker("현재가", index) is None
