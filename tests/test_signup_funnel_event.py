"""routes/auth._record_signup_funnel — 가입 퍼널 이벤트 (2026-09-29).

이 함수는 퍼널 이벤트를 쓴 뒤 ``from routes.growth import attribute_referral``
을 불렀는데, 그 모듈·함수는 git 이력 어디에도 없었다 — 새 가입마다 ImportError
를 삼키고 "referral attribution failed" 경고를 남겼다. 호출을 지웠다.
"""
from __future__ import annotations

import logging


def test_signup_funnel_writes_event_without_attribution_warning(app, make_user, caplog):
    from models import FunnelEvent, User
    from routes.auth import _record_signup_funnel

    uid = make_user(email="funnel@test.com")["id"]
    with app.app_context():
        user = User.query.get(uid)
        with caplog.at_level(logging.WARNING, logger="routes.auth"):
            _record_signup_funnel(user, "ABCD1234")
        ev = FunnelEvent.query.filter_by(user_id=uid, event="signup").all()
        assert [e.ref_code for e in ev] == ["ABCD1234"]
    assert "referral attribution failed" not in caplog.text
    assert "signup funnel event failed" not in caplog.text
