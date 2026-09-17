"""월간 거울 리포트 — 발송/전달 계층 테스트.

렌더러(``services/reports/mirror_pdf.py``) 는 다른 에이전트 소관이고 아직
없을 수 있다. 여기서는 확정된 두 함수 시그니처만 믿고 monkeypatch 로
가짜 렌더러를 꽂아 **전달** 쪽만 검증한다:

    build_mirror_report(user_id, period_days=30) -> dict   # has_content
    render_mirror_pdf(data, locale="ko")          -> bytes

커버
----
1. 온디맨드 라우트: 200 + Content-Type / Content-Disposition
2. 온디맨드 라우트: ``has_content=False`` → 404 + 코드
3. 온디맨드 라우트: 비로그인 401, user id 파라미터 무시(본인 것만)
4. 발송 게이트: 알림 설정 email 기본값 off → 스킵
5. 발송 게이트: 정보성 수신 동의 없음 → 스킵 (렌더조차 하지 않는다)
6. 발송: 카테고리 INFORMATION + PDF 첨부 인자 확인
7. 한 사용자의 실패가 나머지 발송을 멈추지 않는다
8. 시뮬 사용자 / 탈퇴 유예 사용자는 후보 쿼리에서 빠진다
9. 알림 id 와 기본값이 모델에 등록돼 있다
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import services.reports_delivery as rd


PDF_MAGIC = b"%PDF-1.7\n% fake\n"


# ── 가짜 렌더러 ──────────────────────────────────────────────────────────────

@pytest.fixture
def fake_renderer(monkeypatch):
    """``build_mirror_report`` / ``render_mirror_pdf`` 를 가짜로 바꾼다.

    두 경로(라우트·크론)가 모두 모듈 전역을 통해 렌더러를 부르므로 이
    한 곳만 바꾸면 된다.
    """
    calls = {"build": [], "render": []}

    def _build(user_id, period_days=30):
        calls["build"].append((user_id, period_days))
        return {"has_content": True, "user_id": user_id}

    def _render(data, locale="ko"):
        calls["render"].append((data, locale))
        return PDF_MAGIC + str(data.get("user_id", "")).encode()

    monkeypatch.setattr(rd, "build_mirror_report", _build)
    monkeypatch.setattr(rd, "render_mirror_pdf", _render)
    return calls


@pytest.fixture
def empty_renderer(monkeypatch):
    """되비출 기록이 없는 사용자."""
    def _build(user_id, period_days=30):
        return {"has_content": False}

    def _render(data, locale="ko"):  # pragma: no cover - 불려선 안 된다
        raise AssertionError("render_mirror_pdf must not run on empty content")

    monkeypatch.setattr(rd, "build_mirror_report", _build)
    monkeypatch.setattr(rd, "render_mirror_pdf", _render)


# ── 사용자 헬퍼 ──────────────────────────────────────────────────────────────

def _grant(app, user_id, *, email_on=True, information_consent=True,
           is_simulated=False, deletion_requested=False, locale="ko"):
    """알림 설정 / 동의 / 상태 플래그를 사용자 행에 직접 쓴다."""
    from extensions import db
    from models import User

    with app.app_context():
        u = db.session.get(User, user_id)
        u.notification_prefs = {"monthly_mirror": {"email": bool(email_on)}}
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if information_consent:
            u.marketing_consent_at = now - timedelta(days=1)
            u.marketing_consent_information_at = now - timedelta(days=1)
        u.is_simulated = is_simulated
        u.deletion_requested_at = now if deletion_requested else None
        u.locale = locale
        db.session.commit()


def _dispatch(app, user_ids, *, now=None):
    """사용자 행을 읽고 그 자리에서 발송한다.

    행을 app_context 밖으로 들고 나가면 detached 가 되므로 로드와 발송을
    한 컨텍스트 안에서 끝낸다.
    """
    from extensions import db
    from models import User

    with app.app_context():
        rows = [db.session.get(User, uid) for uid in user_ids]
        return rd.dispatch_monthly_reports(now=now, users=rows)


# ── 1-3. 온디맨드 라우트 ─────────────────────────────────────────────────────

def test_mirror_pdf_download_returns_pdf(client, auth_user, fake_renderer):
    resp = client.get("/api/reports/mirror.pdf")
    assert resp.status_code == 200, resp.data[:400]
    assert resp.headers["Content-Type"].startswith("application/pdf")
    disposition = resp.headers["Content-Disposition"]
    assert disposition.startswith("attachment; ")
    assert 'filename="pivoxquant_mirror_' in disposition
    assert disposition.endswith('.pdf"')
    assert resp.data.startswith(b"%PDF")
    # 본인 id 로만 렌더된다.
    assert fake_renderer["build"] == [(auth_user["id"], 30)]


def test_mirror_pdf_filename_carries_year_month(client, auth_user, fake_renderer):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    resp = client.get("/api/reports/mirror.pdf")
    assert f'pivoxquant_mirror_{now:%Y-%m}.pdf' in resp.headers["Content-Disposition"]


def test_mirror_pdf_empty_record_is_404_not_empty_pdf(client, auth_user, empty_renderer):
    resp = client.get("/api/reports/mirror.pdf")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["code"] == "MIRROR_REPORT_EMPTY"
    assert body["error_kr"]


def test_mirror_pdf_render_failure_is_500(client, auth_user, monkeypatch):
    def _boom(user_id, period_days=30):
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(rd, "build_mirror_report", _boom)
    resp = client.get("/api/reports/mirror.pdf")
    assert resp.status_code == 500
    assert resp.get_json()["code"] == "MIRROR_REPORT_FAILED"


def test_mirror_pdf_requires_login(client, fake_renderer):
    resp = client.get("/api/reports/mirror.pdf")
    assert resp.status_code == 401
    assert resp.get_json()["code"] == "SESSION_EXPIRED"


def test_mirror_pdf_ignores_user_id_parameter(client, auth_user, make_user,
                                              fake_renderer):
    """다른 사람 id 를 붙여도 언제나 current_user 의 리포트가 나온다."""
    other = make_user(email="other@test.com")
    assert other["id"] != auth_user["id"]

    resp = client.get(f"/api/reports/mirror.pdf?user_id={other['id']}")
    assert resp.status_code == 200
    assert fake_renderer["build"] == [(auth_user["id"], 30)]


def test_mirror_pdf_is_not_publicly_cacheable(client, auth_user, fake_renderer):
    resp = client.get("/api/reports/mirror.pdf")
    assert "no-store" in resp.headers.get("Cache-Control", "")


# ── 4-6. 발송 게이트 ─────────────────────────────────────────────────────────

class _RecordingSender:
    """``EmailSender`` 대역 — send() 인자를 그대로 붙잡는다."""

    calls: list[dict] = []
    result = True

    def send(self, user, **kwargs):
        type(self).calls.append({"user_id": user.id, **kwargs})
        return type(self).result


@pytest.fixture
def recording_sender(monkeypatch):
    _RecordingSender.calls = []
    _RecordingSender.result = True
    monkeypatch.setattr("services.email.EmailSender", _RecordingSender)
    return _RecordingSender


def test_email_channel_default_is_opt_in(app, make_user, fake_renderer,
                                         recording_sender):
    """알림 설정을 건드리지 않은 사용자에게는 나가지 않는다 (기본값 off)."""
    from models.user import NOTIFICATION_PREF_DEFAULTS

    assert NOTIFICATION_PREF_DEFAULTS["monthly_mirror"]["email"] is False

    u = make_user(email="default-off@test.com")
    _grant(app, u["id"], email_on=False)

    summary = _dispatch(app, [u["id"]])

    assert summary["sent"] == 0
    assert summary["skipped_pref"] == 1
    assert recording_sender.calls == []
    # 설정에서 막혔으면 PDF 는 애초에 만들지 않는다.
    assert fake_renderer["build"] == []


def test_missing_information_consent_skips_before_render(app, make_user,
                                                         fake_renderer,
                                                         recording_sender):
    u = make_user(email="no-consent@test.com")
    _grant(app, u["id"], email_on=True, information_consent=False)

    summary = _dispatch(app, [u["id"]])

    assert summary["skipped_consent"] == 1
    assert summary["sent"] == 0
    assert recording_sender.calls == []
    assert fake_renderer["build"] == []


def test_revoked_information_consent_skips(app, make_user, fake_renderer,
                                           recording_sender):
    from extensions import db
    from models import User

    u = make_user(email="revoked@test.com")
    _grant(app, u["id"], email_on=True, information_consent=True)
    with app.app_context():
        row = db.session.get(User, u["id"])
        row.marketing_consent_information_revoked_at = (
            row.marketing_consent_information_at + timedelta(hours=1)
        )
        db.session.commit()

    summary = _dispatch(app, [u["id"]])

    assert summary["skipped_consent"] == 1
    assert recording_sender.calls == []


def test_empty_record_user_is_skipped(app, make_user, empty_renderer,
                                      recording_sender):
    u = make_user(email="empty@test.com")
    _grant(app, u["id"])

    summary = _dispatch(app, [u["id"]])

    assert summary["skipped_empty"] == 1
    assert summary["sent"] == 0
    assert recording_sender.calls == []


def test_send_attaches_pdf_as_information_category(app, make_user,
                                                   fake_renderer,
                                                   recording_sender):
    from services.email.sender import EmailCategory

    u = make_user(email="opted-in@test.com")
    _grant(app, u["id"])

    now = datetime(2026, 10, 1, 0, 0)  # KST 09:00 — 크론이 도는 날
    summary = _dispatch(app, [u["id"]], now=now)

    assert summary["sent"] == 1
    assert summary["errors"] == 0
    assert len(recording_sender.calls) == 1
    call = recording_sender.calls[0]

    assert call["email_category"] is EmailCategory.INFORMATION
    assert call["email_category"] is not EmailCategory.TRANSACTIONAL
    assert call["pdf_bytes"].startswith(b"%PDF")
    # 1일 아침 발송분의 파일명은 리포트가 덮는 지난달이다.
    assert call["pdf_filename"] == "pivoxquant_mirror_2026-09.pdf"
    assert call["event_id"] == "monthly_mirror"
    assert call["from_default"] == "reports@pivoxquant.com"


def test_send_copy_has_no_score_or_directive_language(app, make_user,
                                                      fake_renderer,
                                                      recording_sender):
    from services.legal import assert_legal_safe

    u = make_user(email="copy@test.com")
    _grant(app, u["id"])

    _dispatch(app, [u["id"]])

    call = recording_sender.calls[0]
    for blob, where in ((call["subject"], "subject"), (call["html_body"], "body")):
        assert_legal_safe(blob, f"test/{where}")
        lowered = blob.lower()
        assert "점수" not in lowered
        assert "등급" not in lowered
        assert "score" not in lowered
        assert "grade" not in lowered


def test_english_locale_uses_english_copy(app, make_user, fake_renderer,
                                          recording_sender):
    u = make_user(email="en@test.com")
    _grant(app, u["id"], locale="en")

    _dispatch(app, [u["id"]])

    call = recording_sender.calls[0]
    assert "monthly mirror" in call["subject"].lower()
    # 렌더러에도 사용자의 locale 이 그대로 전달된다.
    assert fake_renderer["render"][0][1] == "en"


def test_sender_refusal_counts_as_skipped_send(app, make_user, fake_renderer,
                                               recording_sender):
    recording_sender.result = False
    u = make_user(email="refused@test.com")
    _grant(app, u["id"])

    summary = _dispatch(app, [u["id"]])

    assert summary["skipped_send"] == 1
    assert summary["sent"] == 0


# ── 7. 크론 전체가 죽지 않는다 ───────────────────────────────────────────────

def test_one_user_failure_does_not_stop_the_run(app, make_user, monkeypatch,
                                                recording_sender):
    good_a = make_user(email="good-a@test.com")
    bad = make_user(email="bad@test.com")
    good_b = make_user(email="good-b@test.com")
    for u in (good_a, bad, good_b):
        _grant(app, u["id"])

    def _build(user_id, period_days=30):
        if user_id == bad["id"]:
            raise RuntimeError("renderer blew up for this one user")
        return {"has_content": True, "user_id": user_id}

    monkeypatch.setattr(rd, "build_mirror_report", _build)
    monkeypatch.setattr(rd, "render_mirror_pdf",
                        lambda data, locale="ko": PDF_MAGIC)

    summary = _dispatch(app, [good_a["id"], bad["id"], good_b["id"]])

    assert summary["candidates"] == 3
    assert summary["errors"] == 1
    assert summary["sent"] == 2
    assert {c["user_id"] for c in recording_sender.calls} == {
        good_a["id"], good_b["id"],
    }


def test_missing_renderer_module_raises_named_error(monkeypatch):
    monkeypatch.setattr(rd, "build_mirror_report", None)
    monkeypatch.setattr(rd, "render_mirror_pdf", None)
    with pytest.raises(rd.RendererUnavailable):
        rd.build_mirror_pdf(1)


# ── 8. 후보 쿼리 ─────────────────────────────────────────────────────────────

def test_recipient_query_excludes_simulated_and_deleting_users(app, make_user):
    keep = make_user(email="keep@test.com")
    sim = make_user(email="sim@test.com")
    leaving = make_user(email="leaving@test.com")
    _grant(app, keep["id"])
    _grant(app, sim["id"], is_simulated=True)
    _grant(app, leaving["id"], deletion_requested=True)

    with app.app_context():
        ids = {u.id for u in rd.find_report_recipients()}

    assert keep["id"] in ids
    assert sim["id"] not in ids
    assert leaving["id"] not in ids


def test_recipient_query_excludes_global_opt_out(app, make_user):
    from extensions import db
    from models import User

    u = make_user(email="optout@test.com")
    _grant(app, u["id"])
    with app.app_context():
        row = db.session.get(User, u["id"])
        row.email_opt_out = True
        db.session.commit()

    with app.app_context():
        assert u["id"] not in {r.id for r in rd.find_report_recipients()}


# ── 9. 알림 항목 등록 ────────────────────────────────────────────────────────

def test_notification_event_is_registered_with_defaults():
    from models.user import (
        NOTIFICATION_CHANNELS,
        NOTIFICATION_EVENT_IDS,
        NOTIFICATION_PREF_DEFAULTS,
    )

    assert rd.REPORT_EVENT_ID == "monthly_mirror"
    assert rd.REPORT_EVENT_ID in NOTIFICATION_EVENT_IDS
    defaults = NOTIFICATION_PREF_DEFAULTS[rd.REPORT_EVENT_ID]
    assert set(defaults) == set(NOTIFICATION_CHANNELS)
    assert defaults["email"] is False


def test_notification_preferences_endpoint_exposes_the_event(client, auth_user):
    resp = client.get("/api/notifications/preferences")
    assert resp.status_code == 200
    prefs = resp.get_json()["prefs"]
    assert "monthly_mirror" in prefs
    assert prefs["monthly_mirror"]["email"] is False
