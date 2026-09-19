"""POST /api/auth/oauth-finalize — 법정 필수 동의 서버 게이트 회귀 테스트.

우회 재현 (2026-09-17 보안 감사, P1)
------------------------------------
동의 스택이 OAuth **이후** 인터스티셜(``/signup/oauth-finalize``)로 옮겨졌는데
서버는 계속 ``{birthdate}`` 만 받고 있었다. 그래서 OAuth 콜백이 세션을 준
직후, 체크박스를 하나도 건드리지 않은 curl 한 줄로 전 기능이 열렸고,
``cross_border_consent_at`` 은 NULL, 약관·비자문 동의 증거는 0 이었다.

이 파일이 그 우회가 다시 열리지 않는지 지킨다.

2026-09-19 — 생년월일 수집 중단
------------------------------
``age`` 체크박스가 만 14세 이상 자가선언이자 유일한 증거가 됐다. 본문의
``birthdate`` 는 더 이상 받지 않는다 (구버전 번들이 보내면 무시).

여기서 검증하는 계약
--------------------
* 본문은 ``{consents: {terms, non_advisory, cross_border, age}}``.
* 4종이 모두 리터럴 ``true`` 가 아니면 400 ``consents_required`` 이고
  ``missing_consents`` 가 빠진 키를 나열하며, **아무것도 쓰이지 않는다**
  (부분 적용 없음).
* ``consents`` 키가 아예 없는 요청도 거절한다(하위 호환 판단 — 근거는
  ``routes/auth.py`` 의 ``oauth_finalize`` 주석 참조).
* 통과하면 ``age_confirmed_at`` 과 국외이전 동의(PIPA §28-8)
  ``cross_border_consent_at`` 이 **같은 트랜잭션**에서 기록되고 온보딩
  시퀀스가 정확히 한 번 예약된다.
* 재-finalize 는 200 멱등 — 어느 타임스탬프도 움직이지 않고 온보딩도
  다시 예약하지 않는다. 409 는 없다.
* ``terms`` / ``non_advisory`` 는 서버 컬럼이 없다 — 받아서 검증만 한다.

연령 게이트(``app.age_gate_blocks`` + ``AGE_GATE_WHITELIST``)는
``tests/test_age_gate.py`` 가, /register 의 자가선언은
``tests/test_signup_min_age.py`` 가 소유한다.
"""
from datetime import date, datetime
from unittest.mock import patch

import pytest

from extensions import db
from models import User
from routes import auth as auth_mod


ENDPOINT = "/api/auth/oauth-finalize"
FULL_CONSENTS = {"terms": True, "non_advisory": True, "cross_border": True, "age": True}


@pytest.fixture
def oauth_user(app):
    """OAuth 콜백 직후 상태 — 세션은 있고 연령 확인은 없는 반쯤 생성된 계정."""
    with app.app_context():
        u = User(
            email="finalize-consent@test.com",
            name="OAuth User",
            google_id="goog_finalize_consent",
            oauth_provider="google",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.raw.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def _fetch(app, user_id):
    with app.app_context():
        return db.session.get(User, user_id)


def _assert_nothing_written(app, user_id):
    u = _fetch(app, user_id)
    assert u is not None, "거절 요청이 계정을 지우면 안 된다"
    assert u.age_confirmed_at is None
    assert u.birthdate is None
    assert u.cross_border_consent_at is None


# ── 우회 재현 ──────────────────────────────────────────────────────────────

def test_empty_payload_is_rejected(client, app, oauth_user):
    """체크박스 없이 보내면 거절된다 — 4종 전부 missing 으로 나열."""
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={})

    assert r.status_code == 400, r.get_data(as_text=True)
    body = r.get_json()
    assert body["error"] == "consents_required"
    assert body["code"] == "consents_required"
    assert body["error_kr"]
    assert set(body["missing_consents"]) == set(FULL_CONSENTS)
    _assert_nothing_written(app, oauth_user)


def test_legacy_birthdate_only_payload_is_rejected(client, app, oauth_user):
    """감사가 제출한 우회 curl 그대로 — ``{birthdate}`` 만 보내면 거절된다."""
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={"birthdate": "1990-01-01"})

    assert r.status_code == 400
    assert r.get_json()["code"] == "consents_required"
    _assert_nothing_written(app, oauth_user)


def test_rejected_payload_leaves_user_still_gated(client, app, oauth_user):
    """거절 후에도 계정은 half-provisioned — 기능이 열리지 않는다."""
    _login(client, oauth_user)
    client.post(ENDPOINT, json={"consents": {"terms": True}})

    me = client.get("/api/auth/me")
    if me.status_code == 200:
        user_payload = (me.get_json() or {}).get("user") or {}
        assert user_payload.get("age_confirmation_required") is True

    # 전역 연령 게이트가 계속 막는다 (app._require_age_confirmation).
    r = client.get("/api/profile/persona")
    assert r.status_code == 403
    assert r.get_json()["code"] == "AGE_CONFIRMATION_REQUIRED"


@pytest.mark.parametrize("missing_key", ["terms", "non_advisory", "cross_border", "age"])
def test_each_required_consent_is_individually_enforced(
    client, app, oauth_user, missing_key
):
    """4종 중 하나라도 false 면 거절 — 어느 하나도 선택 항목이 아니다."""
    _login(client, oauth_user)
    consents = dict(FULL_CONSENTS, **{missing_key: False})

    r = client.post(ENDPOINT, json={"consents": consents})

    assert r.status_code == 400
    body = r.get_json()
    assert body["code"] == "consents_required"
    assert body["missing_consents"] == [missing_key]
    _assert_nothing_written(app, oauth_user)


def test_missing_age_key_is_listed(client, app, oauth_user):
    """``age`` 키 자체가 없으면 (구버전 번들: 3종만) missing 에 ``age`` 가 뜬다."""
    _login(client, oauth_user)
    three = {k: v for k, v in FULL_CONSENTS.items() if k != "age"}

    r = client.post(ENDPOINT, json={"consents": three})

    assert r.status_code == 400
    assert r.get_json()["missing_consents"] == ["age"]
    _assert_nothing_written(app, oauth_user)


@pytest.mark.parametrize("truthy", ["true", "on", 1, "yes"])
@pytest.mark.parametrize("key", ["terms", "age"])
def test_truthy_non_boolean_is_not_consent(client, app, oauth_user, truthy, key):
    """문자열 "true" / 1 은 명시적 opt-in 이 아니다 — 증거로 인정하지 않는다."""
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={
        "consents": dict(FULL_CONSENTS, **{key: truthy}),
    })

    assert r.status_code == 400
    assert r.get_json()["code"] == "consents_required"
    assert r.get_json()["missing_consents"] == [key]
    _assert_nothing_written(app, oauth_user)


def test_consents_wrong_type_is_rejected(client, app, oauth_user):
    """``consents`` 가 dict 가 아니면 거절 (리스트 / 문자열 / true)."""
    _login(client, oauth_user)
    for bad in ([], "terms", True, 1):
        r = client.post(ENDPOINT, json={"consents": bad})
        assert r.status_code == 400, f"consents={bad!r} 이 통과했다"
        assert r.get_json()["code"] == "consents_required"
    _assert_nothing_written(app, oauth_user)


def test_empty_consents_object_is_rejected(client, app, oauth_user):
    _login(client, oauth_user)
    r = client.post(ENDPOINT, json={"consents": {}})
    assert r.status_code == 400
    assert set(r.get_json()["missing_consents"]) == set(FULL_CONSENTS)


# ── 통과 경로 + 서버 기록 ──────────────────────────────────────────────────

def test_full_consents_finalize_and_record_both_stamps(client, app, oauth_user):
    """필수 4종이 모두 true 면 통과하고, 자가선언 시각 + 국외이전 동의가 같이 기록된다."""
    _login(client, oauth_user)

    with patch.object(auth_mod, "_schedule_onboarding_safe") as sched:
        r = client.post(ENDPOINT, json={"consents": FULL_CONSENTS})

    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["ok"] is True
    assert body["user"]["age_confirmation_required"] is False
    assert body["user"]["birthdate_required"] is False  # deprecated alias
    assert "birthdate" not in body["user"]
    assert "age_confirmed_at" not in body["user"]

    u = _fetch(app, oauth_user)
    assert u.age_confirmed_at is not None
    assert u.age_confirmed_at.tzinfo is None  # naive UTC, like the other consents
    assert u.birthdate is None  # never collected anymore
    # PIPA §28-8 — routes/consents.py 와 같은 두 컬럼, 같은 기록 방식.
    assert u.cross_border_consent_at is not None
    assert u.cross_border_consent_revoked_at is None
    # 온보딩 시퀀스는 첫 finalize 에서 정확히 한 번.
    assert sched.call_count == 1


def test_stamps_land_in_same_transaction(client, app, oauth_user):
    """자가선언 시각과 국외이전 동의는 한 커밋 — 하나만 남는 상태가 없다."""
    _login(client, oauth_user)
    client.post(ENDPOINT, json={"consents": FULL_CONSENTS})

    u = _fetch(app, oauth_user)
    assert u.age_confirmed_at is not None
    assert u.cross_border_consent_at is not None
    assert u.age_confirmed_at == u.cross_border_consent_at


def test_legacy_birthdate_key_is_ignored_not_stored(client, app, oauth_user):
    """구버전 번들이 ``birthdate`` 를 같이 보내도 저장하지 않고 에러도 아니다."""
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={
        "birthdate": "1990-01-01",
        "consents": FULL_CONSENTS,
    })

    assert r.status_code == 200, r.get_data(as_text=True)
    u = _fetch(app, oauth_user)
    assert u.birthdate is None
    assert u.age_confirmed_at is not None


def test_refinalize_is_idempotent_200_and_moves_nothing(client, app, oauth_user):
    """멱등 재전송: 200, 타임스탬프 불변, 온보딩 재예약 없음, 409 없음."""
    _login(client, oauth_user)
    payload = {"consents": FULL_CONSENTS}

    with patch.object(auth_mod, "_schedule_onboarding_safe") as sched:
        assert client.post(ENDPOINT, json=payload).status_code == 200
        first = _fetch(app, oauth_user)
        first_age, first_cb = first.age_confirmed_at, first.cross_border_consent_at
        assert first_age is not None and first_cb is not None

        r2 = client.post(ENDPOINT, json=payload)
        assert r2.status_code == 200
        assert r2.get_json()["ok"] is True

    again = _fetch(app, oauth_user)
    assert again.age_confirmed_at == first_age
    assert again.cross_border_consent_at == first_cb
    assert sched.call_count == 1


def test_legacy_birthdate_user_refinalize_does_not_stamp_age(client, app):
    """생년월일 시대 사용자가 (어떤 이유로) 다시 finalize 해도 ``age_confirmed_at``
    은 찍지 않는다 — 생년월일이 그 사용자의 증거이고 이미 ``age_confirmed`` 다.
    국외이전 동의가 비어 있으면 그것만 채운다."""
    with app.app_context():
        u = User(email="legacy-finalize@test.com", name="Legacy",
                 google_id="goog_legacy", oauth_provider="google",
                 birthdate=date(1990, 1, 1))
        db.session.add(u)
        db.session.commit()
        uid = u.id
    _login(client, uid)

    with patch.object(auth_mod, "_schedule_onboarding_safe") as sched:
        r = client.post(ENDPOINT, json={"consents": FULL_CONSENTS})

    assert r.status_code == 200
    u = _fetch(app, uid)
    assert u.age_confirmed_at is None
    assert u.birthdate == date(1990, 1, 1)
    assert u.cross_border_consent_at is not None
    assert sched.call_count == 0  # not a first finalize — they were already in


def test_existing_cross_border_timestamp_is_never_overwritten(client, app):
    """이미 있는 국외이전 동의 시각은 첫 finalize 에서도 건드리지 않는다."""
    earlier = datetime(2026, 9, 1, 12, 0, 0)
    with app.app_context():
        u = User(email="cb-set@test.com", name="CB",
                 google_id="goog_cb", oauth_provider="google",
                 cross_border_consent_at=earlier)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    _login(client, uid)

    assert client.post(ENDPOINT, json={"consents": FULL_CONSENTS}).status_code == 200
    u = _fetch(app, uid)
    assert u.cross_border_consent_at == earlier
    assert u.age_confirmed_at is not None


def test_terms_and_non_advisory_have_no_server_column(client, app, oauth_user):
    """증거 강도 한계를 명시적으로 고정한다.

    ``terms`` / ``non_advisory`` 는 대응하는 서버 컬럼이 **없다**(컬럼 신설은
    마이그레이션이라 CEO 승인 대상). 서버는 요청에서 필수로 받아 검증만 하고
    타임스탬프는 남기지 않는다 — 즉 "동의 없이는 가입이 완료되지 않는다"는
    사실만이 증거다. ``age`` 는 예외다: ``age_confirmed_at`` 에 시각이 남는다.
    이 테스트는 그 한계가 **조용히 바뀌는 것**을 막는다: 누군가 컬럼을
    추가하면 여기서 실패하고, 그때 문서
    (docs/legal/policy-audit-2026-09-17.md B-1)도 같이 고치게 된다.
    """
    _login(client, oauth_user)
    client.post(ENDPOINT, json={"consents": FULL_CONSENTS})

    u = _fetch(app, oauth_user)
    columns = {c.name for c in User.__table__.columns}
    assert not [c for c in columns if "terms_consent" in c or "terms_agreed" in c]
    assert not [c for c in columns if "non_advisory" in c]
    assert "age_confirmed_at" in columns
    # 간접 증거: 동의 없이는 age_confirmed_at 이 절대 채워지지 않으므로,
    # 값이 있다는 것은 4종 동의를 받았다는 뜻이다.
    assert u.age_confirmed_at is not None


# ── 하위 호환 판단 고정 ────────────────────────────────────────────────────

def test_missing_consents_key_is_rejected_not_silently_accepted(
    client, app, oauth_user
):
    """``consents`` 키 부재에 대한 판단을 코드에 고정한다.

    선택지는 두 개였다 — (a) 경고 로깅 후 통과, (b) 거절. (b) 를 골랐다:
    (a) 를 고르면 파일 상단의 우회 curl 이 그대로 성공하므로 고친 것이
    아니게 된다. (b) 의 실패 모드(배포 순간 열려 있던 구버전 번들)는
    새로고침 한 번으로 자가 치유되고 계정도 손상되지 않는 반면, (a) 의
    실패 모드는 조용하고 무기한이다. 완화책은 배포 순서다 — 프론트를 먼저
    올리면 창 자체가 생기지 않는다(구버전 서버는 모르는 키를 무시할 뿐).

    이 판단을 바꾸려면 이 테스트를 **의도적으로** 고쳐야 한다.
    """
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={"birthdate": "1990-01-01"})

    assert r.status_code == 400
    assert r.get_json()["code"] == "consents_required"
    _assert_nothing_written(app, oauth_user)


def test_unauthenticated_still_401_before_consent_check(client):
    """동의 검증이 인증 게이트보다 앞서지 않는다."""
    r = client.post(ENDPOINT, json={"consents": FULL_CONSENTS})
    assert r.status_code == 401
