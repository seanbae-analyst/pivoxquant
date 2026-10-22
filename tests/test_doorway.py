"""Tests for 문 앞의 한 줄 (doorway pause) — backend.

설계 docs/design/doorway-pause_2026-10-15.md. Covers reading the phone
automation's one line (보기 / 살 … / 팔 …, ticker from the line), the daily
cap, the pure matching of opens to the user's own fills (one fill → the one
open right before it, 60-minute window, minute-truncated fill grace, the
"not happened" follow-up), the route contract (Bearer token reuse, session
path, auth, ownership, scrub keeps the user's line), at-rest encryption and
the PIPA wiring (탈퇴 시 삭제 + 열람권 export).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from extensions import db
from models import DoorwayCheck, TradeHistory
from services.doorway import record_check
from services.doorway.service import (
    DAILY_LIMIT,
    DoorwayInputError,
    Fill,
    extract_ticker,
    kst_day_start_utc,
    normalize_app,
    parse_text,
    summarize,
    year_section,
)

TOKENS = "/api/portfolio/imports/tokens"
WEBHOOK = "/api/doorway/webhook"
CHECKS = "/api/doorway/checks"
SUMMARY = "/api/doorway/summary"

NOW = datetime(2026, 10, 15, 6, 0)  # naive UTC = 15:00 KST


def _check(i, at, intent, ticker=None, note=None):
    return SimpleNamespace(id=i, created_at=at, intent=intent, ticker=ticker, note=note, app="toss")


# ─────────────────────────────────────────────────────────────────────
# Reading the line
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,intent,note", [
    ("보기", "look", ""),
    ("그냥 보기", "look", ""),
    ("살 삼성전자 실적 발표 전", "buy", "삼성전자 실적 발표 전"),
    ("살 게 있음: 엔비디아", "buy", "엔비디아"),
    ("팔 테슬라 반등에", "sell", "테슬라 반등에"),
    ("매도 - 정리", "sell", "정리"),
    ("buy AAPL", "buy", "AAPL"),
])
def test_parse_text_heads(text, intent, note):
    assert parse_text(text) == (intent, note)


@pytest.mark.parametrize("text", ["", "삼성전자", "살삼성전자", "몰라"])
def test_parse_text_without_a_head_is_an_error(text):
    with pytest.raises(DoorwayInputError):
        parse_text(text)


@pytest.mark.parametrize("text,ticker", [
    ("삼성전자 실적", "005930.KS"),
    ("삼성전자를 더", "005930.KS"),
    ("엔비디아 눌림", "NVDA"),
    ("TSLA 반등", "TSLA"),
    ("005930 조금", "005930.KS"),
    ("AI 관련주 하나", None),      # stop-listed acronym, not C3.ai
    ("그냥 느낌", None),
    ("", None),
])
def test_extract_ticker(app, text, ticker):
    with app.app_context():
        assert extract_ticker(text) == ticker


def test_normalize_app():
    assert normalize_app("toss") == "toss"
    assert normalize_app("토스증권") == "toss"
    assert normalize_app(" Kiwoom ") == "kiwoom"
    assert normalize_app("이상한 앱 이름!") is None
    assert normalize_app(None) is None


def test_kst_day_start():
    # 2026-10-14 16:00 UTC = 2026-10-15 01:00 KST → day starts 2026-10-14 15:00 UTC.
    assert kst_day_start_utc(datetime(2026, 10, 14, 16, 0)) == datetime(2026, 10, 14, 15, 0)


# ─────────────────────────────────────────────────────────────────────
# record_check
# ─────────────────────────────────────────────────────────────────────

def test_record_from_text_and_explicit_intent(app, make_user):
    user = make_user(email="dw-rec@test.com")
    with app.app_context():
        a = record_check(user["id"], {"text": "살 삼성전자 실적", "app": "토스"}, source="automation", now=NOW)
        assert a["check"]["intent"] == "buy"
        assert a["check"]["ticker"] == "005930.KS"
        assert a["check"]["note"] == "삼성전자 실적"
        assert a["check"]["app"] == "toss"
        assert a["today"] == 1
        b = record_check(user["id"], {"intent": "look"}, source="web", now=NOW + timedelta(minutes=1))
        assert b["check"]["intent"] == "look" and b["check"]["note"] is None
        assert b["today"] == 2


def test_record_truncates_a_long_line_and_rejects_bad_intent(app, make_user):
    user = make_user(email="dw-trunc@test.com")
    with app.app_context():
        out = record_check(user["id"], {"intent": "sell", "note": "가" * 500}, source="web", now=NOW)
        assert len(out["check"]["note"]) == 200
        with pytest.raises(DoorwayInputError):
            record_check(user["id"], {"intent": "hold"}, source="web", now=NOW)
        with pytest.raises(DoorwayInputError):
            record_check(user["id"], {}, source="web", now=NOW)


def test_daily_cap_counts_the_kst_day(app, make_user, monkeypatch):
    import services.doorway.service as svc

    monkeypatch.setattr(svc, "DAILY_LIMIT", 2)
    user = make_user(email="dw-cap@test.com")
    with app.app_context():
        record_check(user["id"], {"intent": "look"}, source="web", now=NOW)
        record_check(user["id"], {"intent": "look"}, source="web", now=NOW)
        with pytest.raises(DoorwayInputError) as exc:
            record_check(user["id"], {"intent": "look"}, source="web", now=NOW)
        assert exc.value.code == "DOORWAY_DAILY_LIMIT" and exc.value.status == 429
        # Next KST day (NOW is 15:00 KST → +10h is 01:00 KST next day).
        record_check(user["id"], {"intent": "look"}, source="web", now=NOW + timedelta(hours=10))
    assert DAILY_LIMIT == 100


def test_note_is_encrypted_at_rest(app, make_user):
    from sqlalchemy import text as sa_text

    user = make_user(email="dw-enc@test.com")
    with app.app_context():
        out = record_check(user["id"], {"text": "살 삼성전자 실적 기대"}, source="web", now=NOW)
        raw = db.session.execute(
            sa_text("SELECT note FROM doorway_checks WHERE id = :i"), {"i": out["check"]["id"]},
        ).scalar()
        assert "실적" not in raw
        assert db.session.get(DoorwayCheck, out["check"]["id"]).note == "삼성전자 실적 기대"


# ─────────────────────────────────────────────────────────────────────
# summarize — pure matching
# ─────────────────────────────────────────────────────────────────────

def test_outcomes_for_each_intent():
    t0 = NOW - timedelta(days=40)  # every follow-up window has closed by NOW
    checks = [
        _check(1, t0, "look"),
        _check(2, t0 + timedelta(hours=2), "look"),
        _check(3, t0 + timedelta(hours=4), "buy", "005930.KS"),
        _check(4, t0 + timedelta(hours=6), "buy", "005930.KS"),
        _check(5, t0 + timedelta(hours=8), "buy", "005930.KS"),
        _check(6, t0 + timedelta(hours=10), "sell", None),
    ]
    fills = [
        Fill(t0 + timedelta(minutes=10), "TSLA", "BUY"),                  # look → traded
        Fill(t0 + timedelta(hours=4, minutes=5), "005930.KS", "BUY"),     # as said
        Fill(t0 + timedelta(hours=6, minutes=5), "000660.KS", "BUY"),     # other ticker
        Fill(t0 + timedelta(hours=10, minutes=3), "AAPL", "SELL"),        # sell w/o ticker → as said
    ]
    out = summarize(checks, fills, now=NOW, days=90, first_check_at=t0)
    assert out["intents"] == {"look": 2, "buy": 3, "sell": 1}
    assert out["look"] == {"n": 2, "traded": 1}
    assert out["said"]["buy"] == {"n": 3, "as_said": 1, "other": 1, "none": 1}
    assert out["said"]["sell"] == {"n": 1, "as_said": 1, "other": 0, "none": 0}
    # check 5: buy 005930 with no fill, never bought within 30 days.
    assert out["not_happened"] == {"n": 1, "later": 0, "never": 1, "open": 0}
    assert out["fills"] == {"total": 4, "through_door": 4}
    assert out["total"] == 6


def test_a_fill_goes_to_the_latest_open_only():
    t0 = NOW - timedelta(hours=5)
    checks = [_check(1, t0, "look"), _check(2, t0 + timedelta(minutes=10), "look")]
    fills = [Fill(t0 + timedelta(minutes=20), "TSLA", "BUY")]
    out = summarize(checks, fills, now=NOW, first_check_at=t0)
    assert out["look"] == {"n": 2, "traded": 1}
    by_id = {r["id"]: r["outcome"] for r in out["recent"]}
    assert by_id == {1: "none", 2: "traded"}


def test_window_edges_grace_and_follow():
    t0 = NOW - timedelta(hours=5)
    checks = [_check(1, t0, "look"), _check(2, t0 + timedelta(hours=3), "look")]
    fills = [
        Fill(t0 - timedelta(seconds=40), "TSLA", "BUY"),           # minute-truncated → open 1
        Fill(t0 + timedelta(hours=3, minutes=61), "TSLA", "BUY"),  # past 60 min → no open
    ]
    out = summarize(checks, fills, now=NOW, first_check_at=t0)
    assert {r["id"]: r["outcome"] for r in out["recent"]} == {1: "traded", 2: "none"}
    # Only fills from the first open on count; the grace fill is 40s earlier.
    assert out["fills"] == {"total": 1, "through_door": 0}


def test_not_happened_later_and_open():
    old = NOW - timedelta(days=20)
    checks = [
        _check(1, old, "buy", "005930.KS"),
        _check(2, NOW - timedelta(days=2), "sell", "TSLA"),
    ]
    fills = [Fill(old + timedelta(days=5), "005930.KS", "BUY")]
    out = summarize(checks, fills, now=NOW, first_check_at=old)
    assert out["not_happened"] == {"n": 2, "later": 1, "never": 0, "open": 1}


def test_window_and_hour_buckets():
    checks = [
        _check(1, NOW - timedelta(days=45), "look"),       # outside 30 days
        _check(2, datetime(2026, 10, 15, 0, 30), "look"),  # 09:30 KST
        _check(3, datetime(2026, 10, 14, 14, 0), "look"),  # 23:00 KST
    ]
    out = summarize(checks, [], now=NOW, days=30, first_check_at=NOW - timedelta(days=45))
    assert out["total"] == 2
    assert out["by_hour_kst"][9] == 1 and out["by_hour_kst"][23] == 1 and sum(out["by_hour_kst"]) == 2
    assert [r["id"] for r in out["recent"]] == [2, 3]
    assert out["caveats"]


def test_no_checks_is_an_empty_summary():
    out = summarize([], [Fill(NOW, "TSLA", "BUY")], now=NOW, first_check_at=None)
    assert out["total"] == 0 and out["recent"] == []
    assert out["fills"] == {"total": 0, "through_door": 0}
    assert out["first_check_at"] is None


def test_year_section_counts_only_that_year():
    # KST 2026 = [2025-12-31 15:00 UTC, 2026-12-31 15:00 UTC).
    start, end = datetime(2025, 12, 31, 15, 0), datetime(2026, 12, 31, 15, 0)
    checks = [
        _check(1, datetime(2025, 12, 31, 14, 0), "look"),               # 2025-12-31 23:00 KST
        _check(2, datetime(2025, 12, 31, 15, 30), "buy", "TSLA", "테슬라"),  # 2026-01-01 00:30 KST
        _check(3, datetime(2026, 3, 2, 1, 0), "look"),
    ]
    fills = [Fill(datetime(2025, 12, 31, 15, 40), "TSLA", "BUY")]
    out = year_section(checks, fills, start=start, end=end, now=NOW, first_check_at=checks[0].created_at)
    assert out["total"] == 2
    assert out["intents"] == {"look": 1, "buy": 1, "sell": 0}
    assert out["said"]["buy"]["as_said"] == 1
    assert out["fills"] == {"total": 1, "through_door": 1}
    # Counts only — no recent rows, no user line.
    assert "recent" not in out and "테슬라" not in str(out)
    assert year_section(checks, fills, start=end, end=end + timedelta(days=365), now=NOW,
                        first_check_at=checks[0].created_at) is None


def test_a_not_happened_open_does_not_shrink_the_window():
    """2026-10-21: the 30-day follow-up rebound ``summarize``'s ``start``/``end``,
    so the first unfilled buy/sell open with a ticker cut every later open and
    fill out of a 90-day window and out of the year."""
    old = NOW - timedelta(days=80)
    checks = [_check(1, old, "buy", "005930.KS")] + [
        _check(i, NOW - timedelta(days=11 - i), "look") for i in range(2, 7)
    ]
    fills = [Fill(NOW - timedelta(days=5, minutes=-10), "TSLA", "BUY")]
    out = summarize(checks, fills, now=NOW, days=90, first_check_at=old)
    assert out["total"] == 6
    assert out["intents"] == {"look": 5, "buy": 1, "sell": 0}
    assert out["not_happened"] == {"n": 1, "later": 0, "never": 1, "open": 0}
    assert out["fills"] == {"total": 1, "through_door": 1}
    assert len(out["recent"]) == 6

    start, end = datetime(2025, 12, 31, 15, 0), datetime(2026, 12, 31, 15, 0)
    year = [
        _check(1, datetime(2026, 1, 10, 1, 0), "buy", "AAPL"),
        _check(2, datetime(2026, 8, 1, 1, 0), "look"),
        _check(3, datetime(2026, 8, 2, 1, 0), "look"),
        _check(4, datetime(2026, 8, 3, 1, 0), "look"),
    ]
    out = year_section(year, [Fill(datetime(2026, 8, 3, 1, 20), "TSLA", "BUY")],
                       start=start, end=end, now=NOW, first_check_at=year[0].created_at)
    assert out["total"] == 4
    assert out["fills"] == {"total": 1, "through_door": 1}


@pytest.mark.parametrize("fill_ticker", ["035720.KS", "035720", "035720.KQ"])
def test_suffix_variants_are_the_same_name(fill_ticker):
    """.KS / .KQ / bare code are one name — friction_outcome.ticker_key."""
    t0 = NOW - timedelta(days=40)
    checks = [_check(1, t0, "buy", "035720.KQ"), _check(2, t0 + timedelta(days=1), "buy", "035720.KQ")]
    fills = [
        Fill(t0 + timedelta(minutes=5), fill_ticker, "BUY"),
        # check 2 has no fill of its own; a later fill of the same name is "later".
        Fill(t0 + timedelta(days=3), fill_ticker, "BUY"),
    ]
    out = summarize(checks, fills, now=NOW, days=90, first_check_at=t0)
    assert out["said"]["buy"] == {"n": 2, "as_said": 1, "other": 0, "none": 1}
    assert out["not_happened"] == {"n": 1, "later": 1, "never": 0, "open": 0}


def test_a_date_only_fill_is_counted_but_never_follows_an_open():
    """A date-only fill is stored as its KST date at 00:00 (= 09:00 KST): it
    has no time, so it must not read as the fill right after a pre-open door."""
    door = datetime(2026, 10, 13, 23, 30)  # 2026-10-14 08:30 KST
    checks = [_check(1, door, "look")]
    fills = [Fill(datetime(2026, 10, 14, 0, 0), "AAPL", "BUY", untimed=True)]
    out = summarize(checks, fills, now=NOW, first_check_at=door)
    assert out["look"] == {"n": 1, "traded": 0}
    assert out["fills"] == {"total": 1, "through_door": 0}


def test_load_fills_marks_date_only_rows(app, auth_user):
    from services.doorway.service import load_fills

    with app.app_context():
        for at in (datetime(2026, 10, 14, 0, 0), datetime(2026, 10, 14, 5, 0)):
            db.session.add(TradeHistory(
                user_id=auth_user["id"], ticker="AAPL", action="BUY", shares=1.0,
                price_per_share=100.0, total_value=100.0, currency="USD", traded_at=at,
            ))
        db.session.commit()
        got = sorted((f.traded_at.hour, f.untimed) for f in load_fills(auth_user["id"], datetime(2026, 10, 1)))
    assert got == [(0, True), (5, False)]


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def bearer_client(app):
    """Session-less caller — each call in its own app context (see
    tests/test_import_tokens_route.py::webhook_client for why)."""
    raw = app.test_client()

    class _Fresh:
        def __getattr__(self, name):
            fn = getattr(raw, name)

            def call(*a, **kw):
                with app.app_context():
                    return fn(*a, **kw)
            return call

    return _Fresh()


def _token(client) -> dict:
    resp = client.post(TOKENS, json={"name": "아이폰 단축어", "consent": True})
    assert resp.status_code == 201, resp.data
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


def test_webhook_records_with_the_import_token(client, bearer_client, auth_user):
    headers = _token(client)
    resp = bearer_client.post(WEBHOOK, json={"text": "살 삼성전자 실적", "app": "toss"}, headers=headers)
    assert resp.status_code == 201, resp.data
    body = resp.get_json()
    assert body["check"]["intent"] == "buy"
    assert body["check"]["ticker"] == "005930.KS"
    assert body["today"] == 1
    assert "오늘 1번째" in body["message"]
    assert body["pause_url"].endswith("/pre-trade?ticker=005930.KS")
    assert body["disclaimer"]

    plain = bearer_client.post(WEBHOOK, data="보기", content_type="text/plain", headers=headers)
    assert plain.status_code == 201
    assert plain.get_json()["check"]["intent"] == "look"
    assert plain.get_json()["pause_url"] is None
    # A token used only at the door still shows as used in Settings.
    assert client.get(TOKENS).get_json()["tokens"][0]["last_used_at"]


def test_token_issued_before_door_consent_is_refused(client, bearer_client, auth_user, app):
    """A token whose issuance consent predates door answers (NULL
    doorway_consent_at) keeps working for fills but cannot leave door
    answers — PIPA §15·§22, legal-kr-fintech review 2026-10-15."""
    from models import ImportToken

    headers = _token(client)
    listed = client.get(TOKENS).get_json()["tokens"]
    assert listed[0]["doorway_ok"] is True
    with app.app_context():
        tok = ImportToken.query.filter_by(user_id=auth_user["id"]).one()
        tok.doorway_consent_at = None
        db.session.commit()
    resp = bearer_client.post(WEBHOOK, json={"text": "살 삼성전자"}, headers=headers)
    assert resp.status_code == 403
    assert resp.get_json()["code"] == "DOORWAY_TOKEN_RECONSENT"
    with app.app_context():
        assert DoorwayCheck.query.filter_by(user_id=auth_user["id"]).count() == 0
    assert client.get(TOKENS).get_json()["tokens"][0]["doorway_ok"] is False
    # The same token still places fills on the pending list.
    fills = bearer_client.post(
        "/api/portfolio/imports/webhook", json={"text": "삼성전자 10주 매수 체결 71,200원"}, headers=headers,
    )
    assert fills.status_code == 201, fills.data


def test_webhook_rejects_bad_tokens_and_bad_text(client, bearer_client, auth_user):
    assert bearer_client.post(WEBHOOK, json={"text": "보기"}).status_code == 401
    assert bearer_client.post(
        WEBHOOK, json={"text": "보기"}, headers={"Authorization": "Bearer pvx_" + "a" * 32},
    ).get_json()["code"] == "IMPORT_TOKEN_INVALID"
    headers = _token(client)
    bad = bearer_client.post(WEBHOOK, json={"text": "몰라"}, headers=headers)
    assert bad.status_code == 400 and bad.get_json()["code"] == "DOORWAY_BAD_INPUT"


def test_session_path_list_summary_delete(client, app, auth_user):
    created = client.post(CHECKS, json={"intent": "buy", "note": "친구가 추천한 테슬라"})
    assert created.status_code == 201, created.data
    cid = created.get_json()["check"]["id"]
    # The user's own line survives the legal scrub verbatim.
    assert created.get_json()["check"]["note"] == "친구가 추천한 테슬라"
    assert created.get_json()["check"]["ticker"] == "TSLA"

    with app.app_context():
        db.session.add(TradeHistory(
            user_id=auth_user["id"], ticker="TSLA", action="BUY", shares=1.0,
            price_per_share=100.0, total_value=100.0, currency="USD",
            traded_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=2),
        ))
        db.session.commit()

    listed = client.get(CHECKS).get_json()
    assert [c["id"] for c in listed["checks"]] == [cid]
    assert listed["checks"][0]["note"] == "친구가 추천한 테슬라"

    s = client.get(SUMMARY).get_json()
    assert s["total"] == 1
    assert s["said"]["buy"]["as_said"] == 1
    assert s["recent"][0]["note"] == "친구가 추천한 테슬라"
    assert client.get(f"{SUMMARY}?days=3").status_code == 400

    assert client.delete(f"{CHECKS}/{cid}").status_code == 200
    assert client.get(CHECKS).get_json()["checks"] == []


def test_year_recap_carries_the_door_counts(client, auth_user):
    from services.year_recap.recap import kst_year

    client.post(CHECKS, json={"intent": "sell", "note": "반등 정리하려고"})
    year = kst_year(datetime.now(timezone.utc).replace(tzinfo=None))
    body = client.get(f"/api/mirror-home/year?year={year}").get_json()
    assert body["doorway"]["total"] == 1
    assert body["doorway"]["intents"]["sell"] == 1
    assert body["empty"] is False and year in body["years"]
    assert "반등" not in str(body["doorway"])


def test_only_note_skips_the_scrub():
    from routes.doorway import _USER_TEXT

    assert _USER_TEXT == ("note",)


def test_other_users_check_is_404(client, app, make_user, auth_user):
    other = make_user(email="dw-other@test.com")
    with app.app_context():
        theirs = record_check(other["id"], {"intent": "look"}, source="web", now=NOW)
    assert client.delete(f"{CHECKS}/{theirs['check']['id']}").status_code == 404
    assert client.get(CHECKS).get_json()["checks"] == []


def test_session_routes_require_auth(client):
    assert client.get(SUMMARY).status_code in (401, 403)
    assert client.get(CHECKS).status_code in (401, 403)
    assert client.post(CHECKS, json={"intent": "look"}).status_code in (401, 403)


def test_session_post_needs_csrf(raw_client, make_user):
    u = make_user(email="dw-csrf@test.com", password="password123")
    login = raw_client.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    assert login.status_code == 200, login.data
    assert raw_client.post(CHECKS, json={"intent": "look"}).status_code in (400, 401, 403)


# ─────────────────────────────────────────────────────────────────────
# PIPA — 탈퇴 캐스케이드 + 열람권 export
# ─────────────────────────────────────────────────────────────────────

def test_account_deletion_purges_doorway(client, app, auth_user):
    client.post(CHECKS, json={"intent": "look"})
    uid = auth_user["id"]
    with app.app_context():
        assert DoorwayCheck.query.filter_by(user_id=uid).count() == 1
    assert client.delete("/api/auth/delete-account").status_code == 200
    with app.app_context():
        assert DoorwayCheck.query.filter_by(user_id=uid).count() == 0


def test_export_includes_doorway_checks(client, auth_user):
    client.post(CHECKS, json={"intent": "sell", "note": "반등 정리"})
    body = client.get("/api/profile/export").get_json()
    assert body["counts"]["doorway_checks"] == 1
    assert body["doorway_checks"][0]["note"] == "반등 정리"
