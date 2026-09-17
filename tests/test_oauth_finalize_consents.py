"""POST /api/auth/oauth-finalize — 법정 필수 동의 서버 게이트 회귀 테스트.

우회 재현 (2026-09-17 보안 감사, P1)
------------------------------------
동의 스택이 OAuth **이후** 인터스티셜(``/signup/oauth-finalize``)로 옮겨졌는데
서버는 계속 ``{birthdate}`` 만 받고 있었다. 그래서 OAuth 콜백이 세션을 준
직후, 체크박스를 하나도 건드리지 않고

    curl -b <session> -X POST /api/auth/oauth-finalize \\
         -H 'Content-Type: application/json' -d '{"birthdate":"1990-01-01"}'

만 보내면 ``birthdate_required`` 가 false 로 떨어지며 전 기능이 열렸고,
``cross_border_consent_at`` 은 NULL, 약관·비자문 동의 증거는 0 이었다.

이 파일이 그 우회가 다시 열리지 않는지 지킨다.

여기서 검증하는 계약
--------------------
* 본문은 ``{birthdate, consents: {terms, non_advisory, cross_border}}``.
* 3종이 모두 리터럴 ``true`` 가 아니면 400 ``consents_required`` 이고,
  **생년월일도 쓰이지 않는다**(부분 적용 없음).
* ``consents`` 키가 아예 없는 요청도 거절한다(하위 호환 판단 — 근거는
  ``routes/auth.py`` 의 ``oauth_finalize`` 주석 참조).
* 통과하면 국외이전 동의(PIPA §28-8)가 생년월일과 **같은 트랜잭션**에서
  ``cross_border_consent_at`` 에 기록된다.
* ``terms`` / ``non_advisory`` 는 서버 컬럼이 없다 — 받아서 검증만 한다.

연령 게이트(``app.birthdate_gate_blocks`` + ``BIRTHDATE_GATE_WHITELIST``)는
``tests/test_birthdate_gate.py`` 가, 연령 판정 자체는
``tests/test_signup_min_age.py`` 가 소유한다. 여기서는 동의만 본다.
"""
from datetime import date

import pytest

from extensions import db
from models import User


ENDPOINT = "/api/auth/oauth-finalize"
ADULT_BIRTHDATE = "1990-01-01"
FULL_CONSENTS = {"terms": True, "non_advisory": True, "cross_border": True}


@pytest.fixture
def oauth_user(app):
    """OAuth 콜백 직후 상태 — 세션은 있고 birthdate 는 NULL 인 반쯤 생성된 계정."""
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


# ── 우회 재현 ──────────────────────────────────────────────────────────────

def test_birthdate_only_payload_is_rejected(client, app, oauth_user):
    """감사가 제출한 우회 curl 그대로 — ``{birthdate}`` 만 보내면 거절된다."""
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={"birthdate": ADULT_BIRTHDATE})

    assert r.status_code == 400, r.get_data(as_text=True)
    body = r.get_json()
    assert body["error"] == "consents_required"
    assert body["code"] == "consents_required"
    # 한국어 문구가 함께 온다 (services/error_responses.py 3-key 계약).
    assert body["error_kr"]

    # 그리고 아무것도 쓰이지 않았다 — 생년월일도, 동의 타임스탬프도.
    u = _fetch(app, oauth_user)
    assert u is not None, "거절 요청이 계정을 지우면 안 된다"
    assert u.birthdate is None
    assert u.cross_border_consent_at is None


def test_rejected_payload_leaves_user_still_gated(client, app, oauth_user):
    """거절 후에도 계정은 half-provisioned — 기능이 열리지 않는다."""
    _login(client, oauth_user)
    client.post(ENDPOINT, json={"birthdate": ADULT_BIRTHDATE})

    me = client.get("/api/auth/me")
    if me.status_code == 200:
        user_payload = (me.get_json() or {}).get("user") or {}
        assert user_payload.get("birthdate_required") is True

    # 전역 연령 게이트가 계속 막는다 (app._require_birthdate).
    r = client.get("/api/profile/persona")
    assert r.status_code == 403
    assert r.get_json()["code"] == "BIRTHDATE_REQUIRED"


@pytest.mark.parametrize("missing_key", ["terms", "non_advisory", "cross_border"])
def test_each_required_consent_is_individually_enforced(
    client, app, oauth_user, missing_key
):
    """3종 중 하나라도 false 면 거절 — 어느 하나도 선택 항목이 아니다."""
    _login(client, oauth_user)
    consents = dict(FULL_CONSENTS, **{missing_key: False})

    r = client.post(ENDPOINT, json={
        "birthdate": ADULT_BIRTHDATE,
        "consents": consents,
    })

    assert r.status_code == 400
    body = r.get_json()
    assert body["code"] == "consents_required"
    assert missing_key in body["missing_consents"]
    assert _fetch(app, oauth_user).birthdate is None


@pytest.mark.parametrize("truthy", ["true", "on", 1, "yes"])
def test_truthy_non_boolean_is_not_consent(client, app, oauth_user, truthy):
    """문자열 "true" / 1 은 명시적 opt-in 이 아니다 — 증거로 인정하지 않는다."""
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={
        "birthdate": ADULT_BIRTHDATE,
        "consents": dict(FULL_CONSENTS, terms=truthy),
    })

    assert r.status_code == 400
    assert r.get_json()["code"] == "consents_required"
    assert _fetch(app, oauth_user).birthdate is None


def test_consents_wrong_type_is_rejected(client, app, oauth_user):
    """``consents`` 가 dict 가 아니면 거절 (리스트 / 문자열 / true)."""
    _login(client, oauth_user)
    for bad in ([], "terms", True, 1):
        r = client.post(ENDPOINT, json={
            "birthdate": ADULT_BIRTHDATE,
            "consents": bad,
        })
        assert r.status_code == 400, f"consents={bad!r} 이 통과했다"
        assert r.get_json()["code"] == "consents_required"
    assert _fetch(app, oauth_user).birthdate is None


def test_empty_consents_object_is_rejected(client, app, oauth_user):
    _login(client, oauth_user)
    r = client.post(ENDPOINT, json={
        "birthdate": ADULT_BIRTHDATE,
        "consents": {},
    })
    assert r.status_code == 400
    assert set(r.get_json()["missing_consents"]) == set(FULL_CONSENTS)


# ── 통과 경로 + 서버 기록 ──────────────────────────────────────────────────

def test_full_consents_finalize_and_record_cross_border(client, app, oauth_user):
    """필수 3종이 모두 true 면 통과하고, 국외이전 동의가 같이 기록된다."""
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={
        "birthdate": ADULT_BIRTHDATE,
        "consents": FULL_CONSENTS,
    })

    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["ok"] is True
    assert r.get_json()["user"]["birthdate_required"] is False

    u = _fetch(app, oauth_user)
    assert u.birthdate == date(1990, 1, 1)
    # PIPA §28-8 — routes/consents.py 와 같은 두 컬럼, 같은 기록 방식.
    assert u.cross_border_consent_at is not None
    assert u.cross_border_consent_revoked_at is None


def test_cross_border_recorded_in_same_transaction_as_birthdate(
    client, app, oauth_user
):
    """생년월일과 동의는 한 커밋 — 하나만 남는 상태가 없다."""
    _login(client, oauth_user)
    client.post(ENDPOINT, json={
        "birthdate": ADULT_BIRTHDATE,
        "consents": FULL_CONSENTS,
    })

    u = _fetch(app, oauth_user)
    assert (u.birthdate is None) == (u.cross_border_consent_at is None)
    assert u.birthdate is not None


def test_refinalize_does_not_move_the_consent_timestamp(
    client, app, oauth_user
):
    """멱등 재전송이 최초 동의 시각을 덮어쓰지 않는다 (감사 추적 보존)."""
    _login(client, oauth_user)
    payload = {"birthdate": ADULT_BIRTHDATE, "consents": FULL_CONSENTS}

    assert client.post(ENDPOINT, json=payload).status_code == 200
    first = _fetch(app, oauth_user).cross_border_consent_at
    assert first is not None

    assert client.post(ENDPOINT, json=payload).status_code == 200
    assert _fetch(app, oauth_user).cross_border_consent_at == first


def test_terms_and_non_advisory_have_no_server_column(client, app, oauth_user):
    """증거 강도 한계를 명시적으로 고정한다.

    ``terms`` / ``non_advisory`` 는 대응하는 서버 컬럼이 **없다**(컬럼 신설은
    마이그레이션이라 CEO 승인 대상). 서버는 요청에서 필수로 받아 검증만 하고
    타임스탬프는 남기지 않는다 — 즉 "동의 없이는 가입이 완료되지 않는다"는
    사실만이 증거다. 이 테스트는 그 한계가 **조용히 바뀌는 것**을 막는다:
    누군가 컬럼을 추가하면 여기서 실패하고, 그때 문서
    (docs/legal/policy-audit-2026-09-17.md B-1)도 같이 고치게 된다.
    """
    _login(client, oauth_user)
    client.post(ENDPOINT, json={
        "birthdate": ADULT_BIRTHDATE,
        "consents": FULL_CONSENTS,
    })

    u = _fetch(app, oauth_user)
    columns = {c.name for c in User.__table__.columns}
    assert not [c for c in columns if "terms_consent" in c or "terms_agreed" in c]
    assert not [c for c in columns if "non_advisory" in c]
    # 간접 증거: 동의 없이는 birthdate 가 절대 채워지지 않으므로,
    # birthdate 가 있다는 것은 3종 동의를 받았다는 뜻이다.
    assert u.birthdate is not None


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
    올리면 창 자체가 생기지 않는다(구버전 서버는 ``consents`` 를 무시할 뿐).

    이 판단을 바꾸려면 이 테스트를 **의도적으로** 고쳐야 한다.
    """
    _login(client, oauth_user)

    r = client.post(ENDPOINT, json={"birthdate": ADULT_BIRTHDATE})

    assert r.status_code == 400
    assert r.get_json()["code"] == "consents_required"
    assert _fetch(app, oauth_user).birthdate is None


def test_unauthenticated_still_401_before_consent_check(client):
    """동의 검증이 인증 게이트보다 앞서지 않는다."""
    r = client.post(ENDPOINT, json={"birthdate": ADULT_BIRTHDATE})
    assert r.status_code == 401
