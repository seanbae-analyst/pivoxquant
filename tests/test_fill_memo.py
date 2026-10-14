"""tests/test_fill_memo.py — a fill arrives by webhook → "write down why" push.

services/fill_memo.py · routes/imports.py::webhook_import. Pins: one push per
webhook call, only for fills that are actually waiting; a link to that fill's
reason box in the push and in the webhook response (`memo_url`, for an iOS
Shortcut to open); the user's `fill_memo` push setting silences it; nothing
about the trade's direction in the push text; a push failure never fails the
import.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.test_import_tokens_route import WEBHOOK, _bearer, _issue, webhook_client  # noqa: F401  (fixture)

FILL = "[키움] 삼성전자 3주 매수 체결 71,200원"


@pytest.fixture
def token(client, auth_user):
    r = _issue(client)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


def _post(webhook_client, token, text=FILL):  # noqa: F811
    return webhook_client.post(WEBHOOK, json={"text": text}, headers=_bearer(token))


def test_new_fill_pushes_once_with_a_link_to_its_reason_box(webhook_client, token):  # noqa: F811
    with patch("services.push_service.send_push_to_user") as send:
        r = _post(webhook_client, token)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    pid = body["pending"][0]["id"]
    assert send.call_count == 1
    kw = send.call_args.kwargs
    assert kw["url"] == f"/journal?pending={pid}"
    assert kw["transactional"] is True
    assert "삼성전자" in kw["body"] and "이유" in kw["body"]
    for word in ("매수", "매도", "BUY", "SELL", "추천", "조언"):
        assert word not in kw["body"] and word not in kw["title"]
    assert body["memo_url"].endswith(f"/journal?pending={pid}")
    assert body["memo_url"].startswith("http")


def test_the_same_fill_again_does_not_push(webhook_client, token):  # noqa: F811
    with patch("services.push_service.send_push_to_user") as send:
        _post(webhook_client, token)
        r = _post(webhook_client, token)
    assert r.status_code == 201
    assert all(p["status"] != "pending" for p in r.get_json()["pending"])
    assert send.call_count == 1
    assert r.get_json()["memo_url"] is None


def test_push_setting_off_silences_it(webhook_client, token, app, auth_user):  # noqa: F811
    from extensions import db
    from models import User
    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        u.notification_prefs = {"fill_memo": {"push": False}}
        db.session.commit()
    with patch("services.push_service.send_push_to_user") as send:
        r = _post(webhook_client, token)
    assert r.status_code == 201 and send.call_count == 0
    assert r.get_json()["memo_url"]  # the automation can still open it


def test_push_failure_never_fails_the_import(webhook_client, token):  # noqa: F811
    with patch("services.push_service.send_push_to_user", side_effect=RuntimeError("vapid")):
        r = _post(webhook_client, token)
    assert r.status_code == 201 and r.get_json()["pending"]


def test_several_fills_one_push(webhook_client, token):  # noqa: F811
    text = FILL + "\n[키움] 카카오 5주 매도 체결 41,000원"
    with patch("services.push_service.send_push_to_user") as send:
        r = _post(webhook_client, token, text=text)
    waiting = [p for p in r.get_json()["pending"] if p["status"] == "pending"]
    assert send.call_count == 1
    if len(waiting) > 1:
        assert f"{len(waiting)}건" in send.call_args.kwargs["body"]


# ── 내 규칙 line in the push (2026-10-14) ────────────────────────────────

def _declare_rare(client, auth_user, app, confirm=True):
    """Onboard with declared_frequency="rare" (≤ 2 fills / month) and, unless
    ``confirm=False``, adopt it as the user's line (POST /rules/confirm)."""
    from tests.test_mirror_home import _LEGAL
    from extensions import db
    from models import Position
    with app.app_context():
        db.session.add(Position(user_id=auth_user["id"], ticker="ONBOARD", shares=0.0,
                                avg_cost=1.0, buy_fx_rate=1.0))
        db.session.commit()
    r = client.post("/api/profile/onboarding", json={"answers": {
        "declared_holding": "months", "declared_frequency": "rare",
        "declared_positions": "focused", "declared_drawdown_response": "hold",
        "record_habit": "sometimes", "legal_confirmations": list(_LEGAL),
    }})
    assert r.status_code == 200, r.get_json()
    if confirm:
        assert client.post("/api/profile/rules/confirm").status_code == 200


def _record_fills(app, user_id, n):
    from datetime import datetime, timezone
    from extensions import db
    from models import TradeHistory
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        for _ in range(n):
            db.session.add(TradeHistory(
                user_id=user_id, ticker="005930.KS", action="BUY", shares=1.0,
                price_per_share=70000.0, total_value=70000.0, currency="KRW", traded_at=now,
            ))
        db.session.commit()


def test_push_names_the_month_count_past_the_users_own_line(
    webhook_client, token, client, auth_user, app,  # noqa: F811
):
    _declare_rare(client, auth_user, app)
    _record_fills(app, auth_user["id"], 2)          # 2 recorded + this fill = 3 > 2
    with patch("services.push_service.send_push_to_user") as send:
        r = _post(webhook_client, token)
    assert r.status_code == 201
    body = send.call_args.kwargs["body"]
    assert "이번 달 들어온 거래가 3번이에요 — 정해 둔 선은 2번." in body
    assert body.index("체결이 들어왔습니다") < body.index("이번 달") < body.index("이유")
    for word in ("매수", "매도", "BUY", "SELL", "추천", "조언", "위반"):
        assert word not in body


def test_push_says_nothing_extra_within_the_line(
    webhook_client, token, client, auth_user, app,  # noqa: F811
):
    _declare_rare(client, auth_user, app)
    _record_fills(app, auth_user["id"], 1)          # 1 + this fill = 2 = line
    with patch("services.push_service.send_push_to_user") as send:
        _post(webhook_client, token)
    assert "이번 달" not in send.call_args.kwargs["body"]


def test_push_without_declared_answers_is_unchanged(webhook_client, token):  # noqa: F811
    with patch("services.push_service.send_push_to_user") as send:
        _post(webhook_client, token)
    assert "이번 달" not in send.call_args.kwargs["body"]


def test_push_says_nothing_extra_before_the_user_adopted_the_line(
    webhook_client, token, client, auth_user, app,  # noqa: F811
):
    """"정해 둔 선" would name a line the user never set — answered, not adopted."""
    _declare_rare(client, auth_user, app, confirm=False)
    _record_fills(app, auth_user["id"], 5)
    with patch("services.push_service.send_push_to_user") as send:
        _post(webhook_client, token)
    assert "이번 달" not in send.call_args.kwargs["body"]
