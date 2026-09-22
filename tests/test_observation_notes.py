"""Tests for 관찰 노트 (observation notes) — backend.

설계 docs/design/observation-notes_2026-09-22.md §6. Covers the
service-layer invariants (caps, ticker normalization, ownership, the
by-ticker window) and the route-layer contract (CSRF, status codes,
disclaimer envelope, cursor pagination), plus the PIPA wiring —
탈퇴 시 삭제 + 열람권 export 포함.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import ObservationNote
from models.observation_note import MAX_TAG_CHARS, MAX_TAGS, MAX_TICKERS
from services.observation_notes import (
    create_note,
    delete_note,
    get_note,
    list_notes,
    notes_for_ticker,
)
from services.pre_trade.friction import MAX_TEXT_CHARS


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

BODY = "장 초반 거래량이 평소의 세 배였다. 왜 그런지 모른 채로 적어 둔다."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _seed(user_id: int, body: str = BODY, **kw) -> dict:
    return create_note(user_id=user_id, body=body, **kw)


# ─────────────────────────────────────────────────────────────────────
# Service layer — caps + normalization
# ─────────────────────────────────────────────────────────────────────

def test_create_stores_note(app, make_user):
    user = make_user(email="obs-create@test.com")
    with app.app_context():
        out = _seed(user["id"], tickers=["aapl"], tags=["거래량"])
        assert out["id"] > 0
        assert out["body"] == BODY
        assert out["tickers"] == [{"ticker": "AAPL", "name": "Apple Inc."}] or (
            out["tickers"][0]["ticker"] == "AAPL"
        )
        assert out["tags"] == ["거래량"]
        assert out["source"] == "journal"
        assert out["created_at"]


def test_create_normalizes_and_dedupes_tickers(app, make_user):
    """A bare 6-digit KR code lands canonical, and duplicates collapse."""
    user = make_user(email="obs-norm@test.com")
    with app.app_context():
        out = _seed(user["id"], tickers=["005930", "005930.KS", " aapl "])
        tickers = [t["ticker"] for t in out["tickers"]]
        assert tickers == ["005930.KS", "AAPL"]
        # 종목명이 서버에서 붙는다 — 프론트 이름 맵이 모르는 KR 코드까지.
        assert out["tickers"][0]["name"] != "005930.KS"


def test_body_cap_rejected(app, make_user):
    user = make_user(email="obs-bodycap@test.com")
    with app.app_context():
        with pytest.raises(ValueError):
            _seed(user["id"], body="가" * (MAX_TEXT_CHARS + 1))


def test_blank_body_rejected(app, make_user):
    user = make_user(email="obs-blank@test.com")
    with app.app_context():
        for bad in ("", "   ", "\n\t "):
            with pytest.raises(ValueError):
                _seed(user["id"], body=bad)


def test_non_text_body_rejected(app, make_user):
    user = make_user(email="obs-nontext@test.com")
    with app.app_context():
        for bad in (None, 42, ["a"], {"a": 1}):
            with pytest.raises(ValueError):
                _seed(user["id"], body=bad)


def test_ticker_and_tag_caps_rejected(app, make_user):
    user = make_user(email="obs-caps@test.com")
    with app.app_context():
        with pytest.raises(ValueError):
            _seed(user["id"], tickers=["A", "B", "C", "D", "E", "F"])
        with pytest.raises(ValueError):
            _seed(user["id"], tags=[f"t{i}" for i in range(MAX_TAGS + 1)])
        with pytest.raises(ValueError):
            _seed(user["id"], tags=["가" * (MAX_TAG_CHARS + 1)])
        # Non-list shapes are a 400, not a 500.
        with pytest.raises(ValueError):
            _seed(user["id"], tickers="AAPL")
        with pytest.raises(ValueError):
            _seed(user["id"], tags="거래량")


def test_caps_are_the_documented_numbers():
    """The caps the plan pins — a silent widening should fail here."""
    assert (MAX_TICKERS, MAX_TAGS, MAX_TAG_CHARS) == (5, 10, 40)
    assert MAX_TEXT_CHARS == 5000


def test_empty_tickers_allowed(app, make_user):
    """시장 전반 노트 — 종목이 없어도 기록된다 (설계 §8 Q2)."""
    user = make_user(email="obs-market@test.com")
    with app.app_context():
        out = _seed(user["id"], tickers=[])
        assert out["tickers"] == []


def test_invalid_source_rejected(app, make_user):
    user = make_user(email="obs-source@test.com")
    with app.app_context():
        assert _seed(user["id"], source="portfolio")["source"] == "portfolio"
        with pytest.raises(ValueError):
            _seed(user["id"], source="somewhere_else")


# ─────────────────────────────────────────────────────────────────────
# Service layer — list / ownership / by-ticker
# ─────────────────────────────────────────────────────────────────────

def test_list_excludes_other_users(app, make_user):
    mine = make_user(email="obs-mine@test.com")
    theirs = make_user(email="obs-theirs@test.com")
    with app.app_context():
        _seed(mine["id"], body="내 노트")
        _seed(theirs["id"], body="남의 노트")
        bodies = [n["body"] for n in list_notes(mine["id"])["notes"]]
        assert bodies == ["내 노트"]


def test_list_cursor_pagination(app, make_user):
    user = make_user(email="obs-cursor@test.com")
    with app.app_context():
        ids = [_seed(user["id"], body=f"노트 {i}")["id"] for i in range(5)]

        page1 = list_notes(user["id"], limit=2)
        assert [n["id"] for n in page1["notes"]] == [ids[4], ids[3]]
        assert page1["next_before"] == ids[3]

        page2 = list_notes(user["id"], limit=2, before=page1["next_before"])
        assert [n["id"] for n in page2["notes"]] == [ids[2], ids[1]]

        page3 = list_notes(user["id"], limit=2, before=page2["next_before"])
        assert [n["id"] for n in page3["notes"]] == [ids[0]]
        # 마지막 페이지에는 다음 커서가 없다.
        assert page3["next_before"] is None


def test_list_limit_is_clamped(app, make_user):
    user = make_user(email="obs-limit@test.com")
    with app.app_context():
        for i in range(3):
            _seed(user["id"], body=f"노트 {i}")
        assert len(list_notes(user["id"], limit=99999)["notes"]) == 3
        assert len(list_notes(user["id"], limit="not-a-number")["notes"]) == 3
        assert len(list_notes(user["id"], limit=0)["notes"]) == 3


def test_list_filters_by_ticker_and_tag(app, make_user):
    user = make_user(email="obs-filter@test.com")
    with app.app_context():
        _seed(user["id"], body="반도체 노트", tickers=["005930"], tags=["반도체"])
        _seed(user["id"], body="애플 노트", tickers=["AAPL"], tags=["하드웨어"])

        by_ticker = list_notes(user["id"], ticker="005930")["notes"]
        assert [n["body"] for n in by_ticker] == ["반도체 노트"]
        # 필터도 정규화를 거친다 — 접미사 유무가 결과를 바꾸지 않는다.
        assert list_notes(user["id"], ticker="005930.KS")["notes"] == by_ticker

        by_tag = list_notes(user["id"], tag="하드웨어")["notes"]
        assert [n["body"] for n in by_tag] == ["애플 노트"]


def test_tag_filter_wildcard_is_escaped(app, make_user):
    """A LIKE wildcard inside a tag must not widen the match to every row."""
    user = make_user(email="obs-wildcard@test.com")
    with app.app_context():
        _seed(user["id"], body="와일드카드", tags=["%"])
        _seed(user["id"], body="평범한 노트", tags=["관찰"])
        rows = list_notes(user["id"], tag="%")["notes"]
        assert [n["body"] for n in rows] == ["와일드카드"]


def test_get_and_delete_reject_other_owner(app, make_user):
    mine = make_user(email="obs-owner@test.com")
    theirs = make_user(email="obs-intruder@test.com")
    with app.app_context():
        note = _seed(theirs["id"], body="남의 노트")
        with pytest.raises(LookupError):
            get_note(note["id"], mine["id"])
        with pytest.raises(LookupError):
            delete_note(note["id"], mine["id"])
        # 원 소유자는 지울 수 있고, 두 번은 못 지운다.
        assert delete_note(note["id"], theirs["id"]) == note["id"]
        with pytest.raises(LookupError):
            delete_note(note["id"], theirs["id"])


def test_notes_for_ticker_window_and_limit(app, make_user):
    user = make_user(email="obs-byticker@test.com")
    with app.app_context():
        for i in range(3):
            _seed(user["id"], body=f"최근 {i}", tickers=["AAPL"])
        old = _seed(user["id"], body="오래된 노트", tickers=["AAPL"])
        outside = _seed(user["id"], body="다른 종목", tickers=["MSFT"])

        # 창 밖으로 밀어낸다 — created_at 을 직접 과거로 옮긴다.
        row = db.session.get(ObservationNote, old["id"])
        row.created_at = _utc_now() - timedelta(days=90)
        db.session.commit()

        out = notes_for_ticker(user["id"], "aapl", days=30, limit=2)
        assert out["ticker"] == "AAPL"
        # 창 안 3건 — count 는 limit 이전의 진짜 개수다.
        assert out["count"] == 3
        assert len(out["notes"]) == 2
        assert out["notes"][0]["body"] == "최근 2"

        bodies = [n["body"] for n in notes_for_ticker(user["id"], "AAPL")["notes"]]
        assert "오래된 노트" not in bodies
        assert outside["body"] not in bodies


def test_notes_for_ticker_requires_ticker(app, make_user):
    user = make_user(email="obs-noticker@test.com")
    with app.app_context():
        with pytest.raises(ValueError):
            notes_for_ticker(user["id"], "")


# ─────────────────────────────────────────────────────────────────────
# Route layer
# ─────────────────────────────────────────────────────────────────────

def test_route_create_returns_201_with_disclaimer(client, auth_user):
    resp = client.post("/api/observation-notes", json={
        "body": BODY,
        "tickers": ["005930"],
        "tags": ["거래량"],
    })
    assert resp.status_code == 201, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert "권유가 아닙니다" in body["disclaimer"]
    assert body["note"]["body"] == BODY
    assert body["note"]["tickers"][0]["ticker"] == "005930.KS"
    assert body["note"]["tags"] == ["거래량"]
    assert body["note"]["source"] == "journal"


def test_route_create_bad_input_codes(client, auth_user):
    cases = [
        {"body": ""},
        {"body": "   "},
        {"body": "가" * (MAX_TEXT_CHARS + 1)},
        {"body": BODY, "tickers": ["A", "B", "C", "D", "E", "F"]},
        {"body": BODY, "tags": [f"t{i}" for i in range(MAX_TAGS + 1)]},
        {"body": BODY, "tags": ["가" * (MAX_TAG_CHARS + 1)]},
        {"body": BODY, "source": "elsewhere"},
    ]
    for payload in cases:
        resp = client.post("/api/observation-notes", json=payload)
        assert resp.status_code == 400, payload
        assert resp.get_json()["code"] == "OBS_NOTE_BAD_INPUT", payload


def test_route_non_object_body_is_400(client, auth_user):
    for payload in ([1, 2, 3], "text", 42):
        resp = client.post("/api/observation-notes", json=payload)
        assert resp.status_code == 400, payload
        assert resp.get_json()["code"] == "OBS_NOTE_BAD_INPUT"


def test_route_list_excludes_other_users(client, app, make_user, auth_user):
    other = make_user(email="obs-route-intruder@test.com")
    with app.app_context():
        _seed(other["id"], body="남의 노트")
    client.post("/api/observation-notes", json={"body": "내 노트"})

    resp = client.get("/api/observation-notes/list")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "disclaimer" in body
    assert [n["body"] for n in body["notes"]] == ["내 노트"]
    assert body["next_before"] is None


def test_route_list_cursor_and_filters(client, auth_user):
    for i in range(3):
        client.post("/api/observation-notes", json={
            "body": f"노트 {i}", "tickers": ["AAPL"], "tags": ["관찰"],
        })
    client.post("/api/observation-notes", json={
        "body": "다른 종목", "tickers": ["MSFT"], "tags": ["기타"],
    })

    page1 = client.get("/api/observation-notes/list?limit=2").get_json()
    assert len(page1["notes"]) == 2
    assert page1["next_before"] is not None

    page2 = client.get(
        f"/api/observation-notes/list?limit=2&before={page1['next_before']}"
    ).get_json()
    assert [n["id"] for n in page2["notes"]] < [n["id"] for n in page1["notes"]]

    filtered = client.get("/api/observation-notes/list?ticker=MSFT").get_json()
    assert [n["body"] for n in filtered["notes"]] == ["다른 종목"]
    tagged = client.get("/api/observation-notes/list?tag=기타").get_json()
    assert [n["body"] for n in tagged["notes"]] == ["다른 종목"]


def test_route_get_and_delete_roundtrip(client, auth_user):
    created = client.post(
        "/api/observation-notes", json={"body": BODY}
    ).get_json()["note"]

    got = client.get(f"/api/observation-notes/{created['id']}")
    assert got.status_code == 200
    assert got.get_json()["note"]["body"] == BODY

    deleted = client.delete(f"/api/observation-notes/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["deleted"] == created["id"]

    assert client.get(f"/api/observation-notes/{created['id']}").status_code == 404


def test_route_other_users_note_is_404_never_403(client, app, make_user, auth_user):
    """존재를 노출하지 않는다 — 타인 소유도 '없음'으로 답한다."""
    other = make_user(email="obs-404@test.com")
    with app.app_context():
        note = _seed(other["id"], body="남의 노트")

    for resp in (
        client.get(f"/api/observation-notes/{note['id']}"),
        client.delete(f"/api/observation-notes/{note['id']}"),
    ):
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "OBS_NOTE_NOT_FOUND"

    # 그리고 실제로 지워지지 않았다.
    with app.app_context():
        assert ObservationNote.query.filter_by(user_id=other["id"]).count() == 1


def test_route_by_ticker(client, auth_user):
    client.post("/api/observation-notes", json={
        "body": "삼성 관찰", "tickers": ["005930"],
    })
    client.post("/api/observation-notes", json={
        "body": "애플 관찰", "tickers": ["AAPL"],
    })
    resp = client.get("/api/observation-notes/by-ticker/005930.KS?days=30&limit=5")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ticker"] == "005930.KS"
    assert body["count"] == 1
    assert [n["body"] for n in body["notes"]] == ["삼성 관찰"]
    assert "disclaimer" in body


def test_route_csrf_required(raw_client, make_user):
    """POST / DELETE without the CSRF header are rejected by init_security."""
    u = make_user(email="obs-csrf@test.com", password="password123")
    login = raw_client.post("/api/auth/login", json={
        "email": u["email"], "password": u["password"],
    })
    assert login.status_code == 200, f"login failed: {login.data!r}"

    posted = raw_client.post("/api/observation-notes", json={"body": BODY})
    assert posted.status_code in (400, 401, 403), posted.status_code
    removed = raw_client.delete("/api/observation-notes/1")
    assert removed.status_code in (400, 401, 403), removed.status_code


def test_route_requires_auth(client):
    assert client.get("/api/observation-notes/list").status_code in (401, 403)
    assert client.post(
        "/api/observation-notes", json={"body": BODY}
    ).status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────
# PIPA — 탈퇴 캐스케이드 + 열람권 export
# ─────────────────────────────────────────────────────────────────────

def test_account_deletion_purges_notes(client, app, auth_user):
    created = client.post(
        "/api/observation-notes", json={"body": BODY}
    ).get_json()["note"]
    user_id = auth_user["id"]
    with app.app_context():
        assert ObservationNote.query.filter_by(user_id=user_id).count() == 1

    resp = client.delete("/api/auth/delete-account")
    assert resp.status_code == 200, resp.data
    with app.app_context():
        assert ObservationNote.query.filter_by(user_id=user_id).count() == 0
        assert db.session.get(ObservationNote, created["id"]) is None


def test_export_includes_observation_notes(client, auth_user):
    client.post("/api/observation-notes", json={
        "body": "열람권 확인용 노트", "tickers": ["AAPL"], "tags": ["관찰"],
    })
    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "observation_notes" in body
    assert body["counts"]["observation_notes"] == 1
    assert body["observation_notes"][0]["body"] == "열람권 확인용 노트"


# ─────────────────────────────────────────────────────────────────────
# At-rest encryption — body 는 평문으로 저장되지 않는다
# ─────────────────────────────────────────────────────────────────────

def test_body_is_encrypted_at_rest(app, make_user):
    from sqlalchemy import text as sa_text

    user = make_user(email="obs-enc@test.com")
    with app.app_context():
        note = _seed(user["id"], body="암호화되어야 하는 관찰 기록")
        raw = db.session.execute(
            sa_text("SELECT body FROM observation_notes WHERE id = :i"),
            {"i": note["id"]},
        ).scalar()
        assert "암호화되어야 하는 관찰 기록" not in raw
        # ORM 을 통하면 평문으로 되돌아온다.
        assert get_note(note["id"], user["id"])["body"] == "암호화되어야 하는 관찰 기록"
