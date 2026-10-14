"""tests/test_rules_confirm.py — POST /api/profile/rules/confirm (내 규칙).

Pins: the onboarding answers become the user's rules only by this explicit
act; it needs auth, a profile and V3 rule answers; it is idempotent (the
first timestamp stays); /api/mirror-home reflects it; re-answering a rule
question clears it, re-answering only the record-habit question does not.
"""
from __future__ import annotations

from tests.test_mirror_home import _LEGAL, _onboard_v3

CONFIRM = "/api/profile/rules/confirm"


def _rules(client):
    return client.get("/api/mirror-home").get_json()["rules"]


def _retake(client, **overrides):
    answers = {
        "declared_holding": "months",
        "declared_frequency": "few",
        "declared_positions": "focused",
        "declared_drawdown_response": "hold",
        "record_habit": "sometimes",
        "legal_confirmations": list(_LEGAL),
    }
    answers.update(overrides)
    r = client.put("/api/profile", json={"answers": answers})
    assert r.status_code == 200, r.get_json()


def test_requires_auth(raw_client):
    assert raw_client.post(CONFIRM).status_code == 401


def test_no_profile_is_404(client, auth_user):
    r = client.post(CONFIRM)
    assert r.status_code == 404 and r.get_json()["code"] == "PROFILE_NOT_FOUND"


def test_profile_without_rule_answers_is_409(client, auth_user, app):
    from extensions import db
    from models import InvestmentProfile
    with app.app_context():
        db.session.add(InvestmentProfile(user_id=auth_user["id"]))
        db.session.commit()
    r = client.post(CONFIRM)
    assert r.status_code == 409 and r.get_json()["code"] == "RULES_NOT_AVAILABLE"


def test_confirm_adopts_the_lines_once(client, auth_user, add_position):
    _onboard_v3(client, auth_user, add_position)
    assert _rules(client)["confirmed"] is False

    first = client.post(CONFIRM)
    assert first.status_code == 200, first.get_json()
    stamp = first.get_json()["rules_confirmed_at"]
    assert stamp

    again = client.post(CONFIRM)
    assert again.status_code == 200 and again.get_json()["rules_confirmed_at"] == stamp

    rules = _rules(client)
    assert rules["confirmed"] is True and rules["confirmed_at"] == stamp
    assert rules["confirmed_on"]


def test_changing_a_rule_answer_clears_the_confirmation(client, auth_user, add_position):
    _onboard_v3(client, auth_user, add_position)
    client.post(CONFIRM)
    _retake(client, declared_frequency="moderate")
    rules = _rules(client)
    assert rules["confirmed"] is False
    freq = next(i for i in rules["items"] if i["id"] == "frequency")
    assert freq["ceiling"] == 15


def test_changing_only_the_record_habit_answer_keeps_it(client, auth_user, add_position):
    _onboard_v3(client, auth_user, add_position)
    client.post(CONFIRM)
    _retake(client, record_habit="regular")
    assert _rules(client)["confirmed"] is True
