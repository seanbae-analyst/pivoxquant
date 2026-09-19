"""
tests/test_signup_min_age.py — PIPA §22 ⑥ server-side minimum-age gate.

Audit W1.4 P0 finding (birthdate era): ``/register`` and the OAuth
callbacks had **zero** server-side age validation — ``curl POST
/api/auth/register`` could create a 13-year-old account, bypassing the
client-only check.

2026-09-19: the product stopped collecting a date of birth. The gate is
now the "만 14세 이상입니다" self-declaration, which the server requires
as a literal ``true`` and stamps into ``users.age_confirmed_at``. This
file is the regression gate for that contract on every path that creates
or completes a ``User`` row. The consent-stack gate on oauth-finalize is
owned by ``tests/test_oauth_finalize_consents.py``; the API gate by
``tests/test_age_gate.py``.
"""
from __future__ import annotations

from datetime import date

import pytest

from extensions import db
from models import User
from services.age_verification import (
    MIN_AGE,
    AgeConfirmationError,
    check_age_confirmation_payload,
)


# ── Pure helper (no Flask) ─────────────────────────────────────────────────

class TestCheckAgeConfirmationPayload:
    def test_min_age_is_fourteen(self):
        assert MIN_AGE == 14

    def test_literal_true_passes(self):
        assert check_age_confirmation_payload(True) is None

    @pytest.mark.parametrize("value", [None, False, "true", "on", 1, "yes", "True", [], {}])
    def test_anything_else_raises_required(self, value):
        with pytest.raises(AgeConfirmationError) as exc:
            check_age_confirmation_payload(value)
        assert exc.value.code == "age_confirmation_required"

    def test_error_is_a_value_error_with_code(self):
        err = AgeConfirmationError("age_confirmation_required")
        assert isinstance(err, ValueError)
        assert err.code == "age_confirmation_required"

    def test_birthdate_helpers_are_gone(self):
        """The birthdate parsers must not quietly survive as dead code."""
        import services.age_verification as mod
        for name in ("BirthdateValidationError", "check_birthdate_payload",
                     "parse_birthdate_strict", "is_at_least_min_age",
                     "compute_age_years"):
            assert not hasattr(mod, name), name


# ── /register endpoint ─────────────────────────────────────────────────────

class TestRegisterMinAge:
    def test_register_without_age_confirmed_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "no-age@test.com",
            "password": "secretpass",
            "name": "No Age",
        })
        assert r.status_code == 400
        body = r.get_json()
        assert body["error"] == "age_confirmation_required"
        assert body["code"] == "age_confirmation_required"
        assert body["error_kr"] == "만 14세 이상임을 확인해 주세요."

    def test_register_age_confirmed_false_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "under14@test.com",
            "password": "secretpass",
            "age_confirmed": False,
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "age_confirmation_required"

    @pytest.mark.parametrize("truthy", ["true", 1, "on"])
    def test_register_truthy_non_boolean_returns_400(self, client, truthy):
        r = client.post("/api/auth/register", json={
            "email": "truthy@test.com",
            "password": "secretpass",
            "age_confirmed": truthy,
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "age_confirmation_required"

    def test_register_does_not_create_row_when_unconfirmed(self, client, app):
        client.post("/api/auth/register", json={
            "email": "leak13@test.com",
            "password": "secretpass",
            "age_confirmed": False,
        })
        with app.app_context():
            assert User.query.filter_by(email="leak13@test.com").first() is None

    def test_register_age_confirmed_true_succeeds_and_stamps(self, client, app):
        r = client.post("/api/auth/register", json={
            "email": "ok14@test.com",
            "password": "secretpass",
            "age_confirmed": True,
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["user"]["email"] == "ok14@test.com"
        assert data["user"]["age_confirmation_required"] is False
        assert data["user"]["birthdate_required"] is False  # deprecated alias
        with app.app_context():
            u = User.query.filter_by(email="ok14@test.com").first()
            assert u is not None
            assert u.age_confirmed_at is not None
            assert u.age_confirmed_at.tzinfo is None  # naive UTC convention
            assert u.birthdate is None  # never collected anymore

    def test_register_ignores_legacy_birthdate_key(self, client, app):
        """An old bundle may still send ``birthdate`` — it is neither stored
        nor an error."""
        r = client.post("/api/auth/register", json={
            "email": "oldbundle@test.com",
            "password": "secretpass",
            "age_confirmed": True,
            "birthdate": "1990-01-01",
        })
        assert r.status_code == 200
        with app.app_context():
            u = User.query.filter_by(email="oldbundle@test.com").first()
            assert u.birthdate is None
            assert u.age_confirmed_at is not None

    def test_register_birthdate_alone_is_not_enough(self, client, app):
        """A birthdate without the self-declaration does not pass the gate."""
        r = client.post("/api/auth/register", json={
            "email": "bd-only@test.com",
            "password": "secretpass",
            "birthdate": "1990-01-01",
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "age_confirmation_required"
        with app.app_context():
            assert User.query.filter_by(email="bd-only@test.com").first() is None


# ── serialize_user gate keys ───────────────────────────────────────────────

class TestSerializeUserAgeConfirmationRequired:
    def _serialize(self, app, **kw):
        from services.serializers import serialize_user
        with app.app_context():
            u = User(name="x", **kw)
            db.session.add(u)
            db.session.commit()
            return serialize_user(u)

    def test_unconfirmed_sets_required_true_on_both_keys(self, app):
        payload = self._serialize(app, email="null-age@test.com")
        assert payload["age_confirmation_required"] is True
        assert payload["birthdate_required"] is True

    def test_stamped_sets_required_false_on_both_keys(self, app):
        from datetime import datetime
        payload = self._serialize(app, email="set-age@test.com",
                                  age_confirmed_at=datetime(2026, 9, 19))
        assert payload["age_confirmation_required"] is False
        assert payload["birthdate_required"] is False

    def test_legacy_birthdate_sets_required_false(self, app):
        payload = self._serialize(app, email="legacy-bd@test.com",
                                  birthdate=date(2000, 1, 1))
        assert payload["age_confirmation_required"] is False
        assert payload["birthdate_required"] is False

    def test_raw_values_not_leaked(self, app):
        """We expose the *boolean gate* but neither the date nor the stamp."""
        from datetime import datetime
        payload = self._serialize(app, email="leak-bd@test.com",
                                  birthdate=date(1990, 6, 15),
                                  age_confirmed_at=datetime(2026, 9, 19))
        assert "birthdate" not in payload
        assert "age_confirmed_at" not in payload
