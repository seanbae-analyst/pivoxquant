"""Tests for 리서치 노트 (research notes) — backend.

설계 docs/design/research-notes_2026-10-15.md. Covers the form's
validation (required business + 1–3 theses, caps, fixed choices), the
review day (KST, +1/3/6 months, month-end clamp), scoring, the overview
(due list, judgment × own-fill outcome, per-source counts — counts only),
ownership, the route contract (codes, disclaimer, CSRF/auth), at-rest
encryption, and the PIPA wiring (탈퇴 시 삭제 + 열람권 export).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from extensions import db
from models import ResearchNote, TradeHistory
from models.research_note import (
    MAX_BUSINESS_CHARS,
    MAX_THESES,
    MAX_THESIS_CHARS,
)
from services.research_notes import (
    create_research,
    get_research,
    list_research,
    research_for_ticker,
    research_overview,
    review_research,
)
from services.research_notes.service import add_months, kst_today

FORM = {
    "ticker": "aapl",
    "business": "아이폰과 서비스 구독으로 번다",
    "theses": ["서비스 매출 비중이 계속 오른다", "  ", "신제품 교체 주기가 짧아진다"],
    "invalidation": "서비스 매출이 두 분기 연속 줄어든다",
    "risk": "한 지역 의존도",
    "numbers": "",
    "info_source": "report",
    "review_months": 3,
}


def _create(user_id: int, **over) -> dict:
    return create_research(user_id, {**FORM, **over})


def _backdate(note_id: int, *, written: datetime, review_on: date) -> None:
    row = db.session.get(ResearchNote, note_id)
    row.created_at = written
    row.review_on = review_on
    db.session.commit()


def _sell(user_id: int, ticker: str, pnl: float, when: datetime, source=None) -> None:
    db.session.add(TradeHistory(
        user_id=user_id, ticker=ticker, action="SELL", shares=1.0,
        price_per_share=100.0, total_value=100.0, pnl=pnl, currency="USD",
        traded_at=when, source=source,
    ))
    db.session.commit()


# ─────────────────────────────────────────────────────────────────────
# Dates
# ─────────────────────────────────────────────────────────────────────

def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 10, 15), 3) == date(2027, 1, 15)
    assert add_months(date(2028, 11, 30), 3) == date(2029, 2, 28)


def test_kst_today_is_the_korean_calendar_day():
    # 2026-10-14 16:00 UTC = 2026-10-15 01:00 KST.
    assert kst_today(datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)) == date(2026, 10, 15)


# ─────────────────────────────────────────────────────────────────────
# Service — the form
# ─────────────────────────────────────────────────────────────────────

def test_create_stores_the_form(app, make_user):
    user = make_user(email="rn-create@test.com")
    with app.app_context():
        out = _create(user["id"])
        assert out["ticker"] == "AAPL"
        assert out["business"] == FORM["business"]
        # Blank thesis lines are dropped, order kept.
        assert out["theses"] == ["서비스 매출 비중이 계속 오른다", "신제품 교체 주기가 짧아진다"]
        assert out["invalidation"] == FORM["invalidation"]
        assert out["numbers"] is None  # 비우면 "안 봄"
        assert out["info_source"] == "report"
        assert out["surface"] == "journal"
        assert out["review_on"] == add_months(kst_today(), 3).isoformat()
        assert out["due"] is False
        assert out["verdicts"] == []
        assert out["reviewed_at"] is None
        assert out["outcome"] == "open"


@pytest.mark.parametrize("months", [1, 3, 6])
def test_review_months_choices(app, make_user, months):
    user = make_user(email=f"rn-months-{months}@test.com")
    with app.app_context():
        out = _create(user["id"], review_months=months)
        assert out["review_on"] == add_months(kst_today(), months).isoformat()


@pytest.mark.parametrize("bad", [
    {"ticker": ""},
    {"ticker": None},
    {"business": ""},
    {"business": "   "},
    {"business": "가" * (MAX_BUSINESS_CHARS + 1)},
    {"theses": []},
    {"theses": ["", "  "]},
    {"theses": "한 줄"},
    {"theses": ["a"] * (MAX_THESES + 1)},
    {"theses": ["가" * (MAX_THESIS_CHARS + 1)]},
    {"theses": [1]},
    {"info_source": "tv"},
    {"surface": "elsewhere"},
    {"review_months": 2},
    {"review_months": True},
    {"review_months": "3"},
    {"risk": 42},
])
def test_create_rejects_bad_input(app, make_user, bad):
    user = make_user(email="rn-bad@test.com")
    with app.app_context():
        with pytest.raises(ValueError):
            _create(user["id"], **bad)
        assert ResearchNote.query.filter_by(user_id=user["id"]).count() == 0


def test_narrative_is_encrypted_at_rest(app, make_user):
    from sqlalchemy import text as sa_text

    user = make_user(email="rn-enc@test.com")
    with app.app_context():
        out = _create(user["id"])
        raw = db.session.execute(
            sa_text("SELECT business, theses_json, invalidation FROM research_notes WHERE id = :i"),
            {"i": out["id"]},
        ).one()
        for column in raw:
            assert "서비스" not in column and "아이폰" not in column
        assert get_research(out["id"], user["id"])["business"] == FORM["business"]


# ─────────────────────────────────────────────────────────────────────
# Service — scoring + overview
# ─────────────────────────────────────────────────────────────────────

def test_review_sets_verdicts_once(app, make_user):
    user = make_user(email="rn-review@test.com")
    with app.app_context():
        out = _create(user["id"])
        with pytest.raises(ValueError):
            review_research(out["id"], user["id"], {"verdicts": ["right"]})  # 2 theses
        with pytest.raises(ValueError):
            review_research(out["id"], user["id"], {"verdicts": ["right", "maybe"]})
        scored = review_research(out["id"], user["id"], {"verdicts": ["right", "wrong"], "note": "반은 맞았다"})
        assert scored["verdicts"] == ["right", "wrong"]
        assert scored["review_note"] == "반은 맞았다"
        assert scored["reviewed_at"]
        # Locked: a second scoring would be made after seeing the result.
        with pytest.raises(ValueError):
            review_research(out["id"], user["id"], {"verdicts": ["right", "unknown"]})
        assert get_research(out["id"], user["id"])["verdicts"] == ["right", "wrong"]


def test_overview_due_counts_and_judgment_by_own_fills(app, make_user):
    user = make_user(email="rn-overview@test.com")
    uid = user["id"]
    today = kst_today()
    written = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=100)
    with app.app_context():
        # A — AAPL, scored right/wrong, sold at a gain after writing.
        a = _create(uid)
        _backdate(a["id"], written=written, review_on=today - timedelta(days=5))
        review_research(a["id"], uid, {"verdicts": ["right", "wrong"]})
        _sell(uid, "AAPL", 120.0, written + timedelta(days=30))
        # Sells that must NOT count: before the note, and a registration row.
        _sell(uid, "AAPL", -999.0, written - timedelta(days=3))
        _sell(uid, "AAPL", -999.0, written + timedelta(days=40), source="holding_adjust")

        # B — 005930, due and not scored (review day passed).
        b = _create(uid, ticker="005930", info_source="youtube", theses=["메모리 가격이 오른다"])
        _backdate(b["id"], written=written, review_on=today - timedelta(days=1))

        # C — MSFT, scored right, never sold → open; source = none.
        c = _create(uid, ticker="MSFT", info_source=None, theses=["클라우드가 자란다"])
        _backdate(c["id"], written=written, review_on=today)
        review_research(c["id"], uid, {"verdicts": ["right"]})

        # D — waiting (review day ahead).
        _create(uid, ticker="NVDA", theses=["데이터센터 수요"], review_months=6)

        ov = research_overview(uid)
        assert [n["id"] for n in ov["due"]] == [b["id"]]
        assert ov["due"][0]["due"] is True
        assert ov["counts"] == {"notes": 4, "scored": 2, "due": 1, "waiting": 1}
        assert ov["judgment"]["right"] == {"gain": 1, "loss": 0, "flat": 0, "open": 1}
        assert ov["judgment"]["wrong"] == {"gain": 1, "loss": 0, "flat": 0, "open": 0}
        assert ov["unknown"] == 0
        assert ov["by_source"]["report"] == {"right": 1, "wrong": 1, "unknown": 0}
        assert ov["by_source"]["none"] == {"right": 1, "wrong": 0, "unknown": 0}
        assert ov["by_source"]["youtube"] == {"right": 0, "wrong": 0, "unknown": 0}


def test_outcome_loss_and_list_carries_outcome(app, make_user):
    user = make_user(email="rn-loss@test.com")
    uid = user["id"]
    written = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    with app.app_context():
        a = _create(uid)
        _backdate(a["id"], written=written, review_on=kst_today())
        _sell(uid, "AAPL", -50.0, written + timedelta(days=2))
        _sell(uid, "AAPL", 20.0, written + timedelta(days=3))
        listed = list_research(uid)
        assert listed["notes"][0]["outcome"] == "loss"


def test_outcome_ignores_a_sale_from_before_the_note_on_the_same_utc_date(app, make_user):
    """2026-10-15: outcomes compared UTC *dates*, so a note written 00:00–09:00
    KST took a sale from the previous KST day as its result."""
    uid = make_user(email="rn-instant@test.com")["id"]
    # Written 2026-10-15 08:00 KST = 2026-10-14 23:00 UTC.
    written = datetime(2026, 10, 14, 23, 0)
    with app.app_context():
        a = _create(uid)
        _backdate(a["id"], written=written, review_on=date(2027, 1, 15))
        _sell(uid, "AAPL", -50.0, datetime(2026, 10, 14, 1, 0))     # 10-14 10:00 KST, 22h before
        _sell(uid, "AAPL", -50.0, datetime(2026, 10, 14, 22, 59))   # one minute before
        _sell(uid, "AAPL", -50.0, datetime(2026, 10, 14, 0, 0))     # date-only, 10-14 KST
        assert get_research(a["id"], uid)["outcome"] == "open"
        _sell(uid, "AAPL", 30.0, datetime(2026, 10, 15, 2, 0))      # 10-15 11:00 KST, after
        assert get_research(a["id"], uid)["outcome"] == "gain"


def test_outcome_date_only_sale_counts_from_the_notes_kst_day(app, make_user):
    """A fill typed with only a date has no time — the KST same-day rule of
    pre_trade.friction_outcome._at_or_after: the note's own day counts."""
    uid = make_user(email="rn-dateonly@test.com")["id"]
    # Written 2026-10-15 14:00 KST = 05:00 UTC; the sale is typed as 2026-10-15.
    written = datetime(2026, 10, 15, 5, 0)
    with app.app_context():
        a = _create(uid)
        _backdate(a["id"], written=written, review_on=date(2027, 1, 15))
        _sell(uid, "AAPL", 40.0, datetime(2026, 10, 15, 0, 0))
        assert get_research(a["id"], uid)["outcome"] == "gain"


def test_ownership_everywhere(app, make_user):
    me = make_user(email="rn-me@test.com")
    other = make_user(email="rn-other@test.com")
    with app.app_context():
        theirs = _create(other["id"])
        assert list_research(me["id"])["notes"] == []
        with pytest.raises(LookupError):
            get_research(theirs["id"], me["id"])
        with pytest.raises(LookupError):
            review_research(theirs["id"], me["id"], {"verdicts": ["right", "right"]})
        assert research_for_ticker(me["id"], "AAPL")["note"] is None
        assert research_overview(me["id"])["counts"]["notes"] == 0


def test_research_for_ticker_returns_latest(app, make_user):
    user = make_user(email="rn-ticker@test.com")
    with app.app_context():
        _create(user["id"], business="첫 리서치")
        _create(user["id"], business="둘째 리서치")
        _create(user["id"], ticker="MSFT")
        out = research_for_ticker(user["id"], "aapl")
        assert out["ticker"] == "AAPL"
        assert out["count"] == 2
        assert out["note"]["business"] == "둘째 리서치"
        with pytest.raises(ValueError):
            research_for_ticker(user["id"], "")


def test_list_cursor_pagination(app, make_user):
    user = make_user(email="rn-cursor@test.com")
    with app.app_context():
        ids = [_create(user["id"], business=f"리서치 {i}")["id"] for i in range(3)]
        page1 = list_research(user["id"], limit=2)
        assert [n["id"] for n in page1["notes"]] == ids[::-1][:2]
        page2 = list_research(user["id"], limit=2, before=page1["next_before"])
        assert [n["id"] for n in page2["notes"]] == [ids[0]]
        assert page2["next_before"] is None


# ─────────────────────────────────────────────────────────────────────
# Route layer
# ─────────────────────────────────────────────────────────────────────

def test_route_create_201_with_disclaimer(client, auth_user):
    resp = client.post("/api/research-notes", json=FORM)
    assert resp.status_code == 201, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert "권유가 아닙니다" in body["disclaimer"]
    assert body["note"]["ticker"] == "AAPL"


def test_route_bad_input_and_non_object(client, auth_user):
    # A typed name is not a symbol (it would never match the user's fills).
    for payload in ({**FORM, "business": ""}, {**FORM, "theses": []}, {**FORM, "ticker": "삼성전자"},
                    [1, 2], "text"):
        resp = client.post("/api/research-notes", json=payload)
        assert resp.status_code == 400, payload
        assert resp.get_json()["code"] == "RESEARCH_BAD_INPUT"


def test_route_list_overview_by_ticker_review_delete(client, auth_user):
    created = client.post("/api/research-notes", json=FORM).get_json()["note"]

    listed = client.get("/api/research-notes/list").get_json()
    assert [n["id"] for n in listed["notes"]] == [created["id"]]

    ov = client.get("/api/research-notes/overview").get_json()
    assert ov["counts"]["notes"] == 1 and "disclaimer" in ov

    bt = client.get("/api/research-notes/by-ticker/AAPL").get_json()
    assert bt["note"]["id"] == created["id"]

    bad = client.post(f"/api/research-notes/{created['id']}/review", json={"verdicts": ["right"]})
    assert bad.status_code == 400
    ok = client.post(
        f"/api/research-notes/{created['id']}/review", json={"verdicts": ["right", "unknown"]}
    )
    assert ok.status_code == 200
    assert ok.get_json()["note"]["verdicts"] == ["right", "unknown"]
    again = client.post(
        f"/api/research-notes/{created['id']}/review", json={"verdicts": ["wrong", "wrong"]}
    )
    assert again.status_code == 400

    # User text survives the scrub verbatim; it is not rewritten.
    quoted = client.post("/api/research-notes", json={
        **FORM, "theses": ["리포트에 목표가 상향이라고 나옴"], "business": "추천 종목이라 들었다",
    }).get_json()["note"]
    assert quoted["theses"] == ["리포트에 목표가 상향이라고 나옴"]
    assert quoted["business"] == "추천 종목이라 들었다"

    assert client.delete(f"/api/research-notes/{created['id']}").status_code == 200
    assert client.get(f"/api/research-notes/{created['id']}").status_code == 404


def test_only_the_named_user_text_keys_skip_the_scrub():
    """skip_keys works by key name at every depth — pin the exact set so a
    new field named like one of them is a deliberate decision, and show that
    everything else (종목명 · 면책 · 집계) is still scrubbed."""
    from routes.research_notes import _USER_TEXT
    from services.legal_filter import scrub_response

    assert _USER_TEXT == ("business", "theses", "invalidation", "risk", "numbers", "review_note")
    payload = {"note": {
        "business": "리포트에 목표가 상향이라고 나옴",
        "theses": ["목표가 상향"],
        "name": "목표가 상향",          # not user text → scrubbed
    }}
    out = scrub_response(payload, skip_keys=_USER_TEXT)
    assert out["note"]["business"] == "리포트에 목표가 상향이라고 나옴"
    assert out["note"]["theses"] == ["목표가 상향"]
    assert out["note"]["name"] != "목표가 상향"


def test_route_other_users_note_is_404(client, app, make_user, auth_user):
    other = make_user(email="rn-route-other@test.com")
    with app.app_context():
        theirs = _create(other["id"])
    for resp in (
        client.get(f"/api/research-notes/{theirs['id']}"),
        client.delete(f"/api/research-notes/{theirs['id']}"),
        client.post(f"/api/research-notes/{theirs['id']}/review", json={"verdicts": ["right", "right"]}),
    ):
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "RESEARCH_NOT_FOUND"
    with app.app_context():
        assert ResearchNote.query.filter_by(user_id=other["id"]).count() == 1


def test_route_requires_auth(client):
    assert client.get("/api/research-notes/overview").status_code in (401, 403)
    assert client.post("/api/research-notes", json=FORM).status_code in (401, 403)


def test_route_csrf_required(raw_client, make_user):
    u = make_user(email="rn-csrf@test.com", password="password123")
    login = raw_client.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    assert login.status_code == 200, login.data
    assert raw_client.post("/api/research-notes", json=FORM).status_code in (400, 401, 403)
    assert raw_client.delete("/api/research-notes/1").status_code in (400, 401, 403)


# ─────────────────────────────────────────────────────────────────────
# PIPA — 탈퇴 캐스케이드 + 열람권 export
# ─────────────────────────────────────────────────────────────────────

def test_account_deletion_purges_research(client, app, auth_user):
    client.post("/api/research-notes", json=FORM)
    uid = auth_user["id"]
    with app.app_context():
        assert ResearchNote.query.filter_by(user_id=uid).count() == 1
    assert client.delete("/api/auth/delete-account").status_code == 200
    with app.app_context():
        assert ResearchNote.query.filter_by(user_id=uid).count() == 0


def test_export_includes_research_notes(client, auth_user):
    client.post("/api/research-notes", json=FORM)
    body = client.get("/api/profile/export").get_json()
    assert body["counts"]["research_notes"] == 1
    assert body["research_notes"][0]["business"] == FORM["business"]
