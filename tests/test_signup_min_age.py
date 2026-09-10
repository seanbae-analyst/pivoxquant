"""
tests/test_signup_min_age.py — PIPA §22 ⑥ server-side birthdate gate.

Audit W1.4 P0 finding: ``routes/auth.py:252 /register`` and the OAuth
callbacks had **zero** server-side birthdate validation. ``curl POST
/api/auth/register`` could create a 13-year-old account, bypassing the
client-only check in ``frontend/src/app/(auth)/signup/_v2/page-v2.tsx``.

This file is the regression gate. Every gate that creates a ``User``
row must reject under-14, and every error code must match
``frontend/src/lib/age-verification.ts``.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from extensions import db
from models import User
from services.age_verification import (
    BirthdateValidationError,
    MIN_AGE_YEARS,
    check_birthdate_payload,
    compute_age_years,
    is_at_least_min_age,
    parse_birthdate_strict,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _years_ago(n: int) -> str:
    """Return a yyyy-mm-dd birthdate exactly ``n`` years before today."""
    today = date.today()
    try:
        bd = today.replace(year=today.year - n)
    except ValueError:
        # Feb 29 fallback — pin to Feb 28 in non-leap target years.
        bd = today.replace(year=today.year - n, day=28)
    return bd.isoformat()


# ── Pure helpers (no Flask) ────────────────────────────────────────────────

class TestParseBirthdateStrict:
    def test_valid_yyyy_mm_dd(self):
        assert parse_birthdate_strict("2000-01-15") == date(2000, 1, 15)

    def test_missing_field_raises_required(self):
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict(None)
        assert exc.value.code == "birthdate_required"

    def test_empty_string_raises_required(self):
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict("")
        assert exc.value.code == "birthdate_required"

    def test_non_string_raises_invalid_format(self):
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict(20000115)
        assert exc.value.code == "birthdate_invalid_format"

    def test_wrong_separator_raises_invalid_format(self):
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict("2000/01/15")
        assert exc.value.code == "birthdate_invalid_format"

    def test_short_form_raises_invalid_format(self):
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict("00-01-15")
        assert exc.value.code == "birthdate_invalid_format"

    def test_unparseable_calendar_raises_invalid_format(self):
        # Feb 30 doesn't exist
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict("2020-02-30")
        assert exc.value.code == "birthdate_invalid_format"

    def test_future_date_raises_unrealistic(self):
        future = (date.today() + timedelta(days=10)).isoformat()
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict(future)
        assert exc.value.code == "birthdate_unrealistic"

    def test_year_2200_raises_unrealistic(self):
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict("2200-01-01")
        assert exc.value.code == "birthdate_unrealistic"

    def test_year_below_1900_raises_unrealistic(self):
        with pytest.raises(BirthdateValidationError) as exc:
            parse_birthdate_strict("1899-12-31")
        assert exc.value.code == "birthdate_unrealistic"


class TestComputeAgeYears:
    def test_birthday_today_counts_full_year(self):
        today = date(2026, 5, 10)
        bd = date(2010, 5, 10)
        assert compute_age_years(bd, today) == 16

    def test_birthday_tomorrow_subtracts_one(self):
        today = date(2026, 5, 10)
        bd = date(2010, 5, 11)
        assert compute_age_years(bd, today) == 15

    def test_birthday_yesterday_no_change(self):
        today = date(2026, 5, 10)
        bd = date(2010, 5, 9)
        assert compute_age_years(bd, today) == 16


class TestIsAtLeastMinAge:
    def test_exactly_min_age_passes(self):
        today = date(2026, 5, 10)
        bd = date(2026 - MIN_AGE_YEARS, 5, 10)
        assert is_at_least_min_age(bd, today=today) is True

    def test_one_day_under_fails(self):
        today = date(2026, 5, 10)
        bd = date(2026 - MIN_AGE_YEARS, 5, 11)
        assert is_at_least_min_age(bd, today=today) is False


class TestCheckBirthdatePayload:
    def test_under_14_raises_below_min_age(self):
        thirteen = _years_ago(13)
        with pytest.raises(BirthdateValidationError) as exc:
            check_birthdate_payload(thirteen)
        assert exc.value.code == "below_min_age"

    def test_exactly_14_returns_ok(self):
        fourteen = _years_ago(14)
        result = check_birthdate_payload(fourteen)
        assert result.ok is True
        assert result.years >= MIN_AGE_YEARS


# ── /register endpoint ─────────────────────────────────────────────────────

class TestRegisterMinAge:
    def test_register_without_birthdate_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "no-bd@test.com",
            "password": "secretpass",
            "name": "No Birthdate",
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "birthdate_required"

    def test_register_under_14_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "under14@test.com",
            "password": "secretpass",
            "birthdate": _years_ago(13),
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "below_min_age"

    def test_register_at_least_14_succeeds(self, client, app):
        r = client.post("/api/auth/register", json={
            "email": "ok14@test.com",
            "password": "secretpass",
            "birthdate": _years_ago(14),
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["user"]["email"] == "ok14@test.com"
        # Frontend gate flag should now be False (birthdate persisted).
        assert data["user"]["birthdate_required"] is False
        # DB persisted the birthdate.
        with app.app_context():
            u = User.query.filter_by(email="ok14@test.com").first()
            assert u is not None
            assert u.birthdate is not None
            assert u.birthdate.isoformat() == _years_ago(14)

    def test_register_future_birthdate_returns_400(self, client):
        future = (date.today() + timedelta(days=30)).isoformat()
        r = client.post("/api/auth/register", json={
            "email": "future@test.com",
            "password": "secretpass",
            "birthdate": future,
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "birthdate_unrealistic"

    def test_register_year_2200_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "y2200@test.com",
            "password": "secretpass",
            "birthdate": "2200-01-01",
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "birthdate_unrealistic"

    def test_register_malformed_birthdate_returns_400(self, client):
        r = client.post("/api/auth/register", json={
            "email": "malformed@test.com",
            "password": "secretpass",
            "birthdate": "not-a-date",
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "birthdate_invalid_format"

    def test_register_does_not_create_row_when_under_14(self, client, app):
        client.post("/api/auth/register", json={
            "email": "leak13@test.com",
            "password": "secretpass",
            "birthdate": _years_ago(13),
        })
        with app.app_context():
            assert User.query.filter_by(email="leak13@test.com").first() is None


# ── /oauth-finalize endpoint ───────────────────────────────────────────────

class TestOAuthFinalize:
    """Exercise the interstitial that captures birthdate after OAuth.

    The OAuth callback creates a User row with ``birthdate=NULL`` and
    logs the user in, then redirects to the frontend ``/signup/oauth-finalize``
    page which POSTs back here.
    """

    def _make_oauth_user(self, app, email="oauth@test.com", with_bd=False):
        """Insert a User row that mimics post-OAuth-callback state."""
        with app.app_context():
            u = User(
                email=email,
                name="OAuth User",
                google_id=f"goog_{email}",
                oauth_provider="google",
            )
            if with_bd:
                u.birthdate = date(2000, 1, 1)
            db.session.add(u)
            db.session.commit()
            return u.id

    def _login_as(self, client, app, user_id):
        """Establish a logged-in session for ``user_id`` via Flask-Login."""
        with client.raw.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

    def test_finalize_without_login_returns_401(self, client):
        r = client.post("/api/auth/oauth-finalize", json={
            "birthdate": _years_ago(20),
        })
        # ``@api_auth`` returns 401 for unauthenticated requests.
        assert r.status_code == 401

    def test_finalize_under_14_returns_400(self, client, app):
        uid = self._make_oauth_user(app)
        self._login_as(client, app, uid)
        r = client.post("/api/auth/oauth-finalize", json={
            "birthdate": _years_ago(13),
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "below_min_age"
        # 2026-09-10 (PIPA §22 ⑥): the half-provisioned account is erased,
        # not just left without a birthdate, and the session is ended.
        with app.app_context():
            assert db.session.get(User, uid) is None
        me = client.get("/api/auth/me")
        # The session is gone: either 401, or a 200 that carries no user.
        assert me.status_code == 401 or not (me.get_json() or {}).get("user")

    def test_finalize_at_least_14_persists_birthdate(self, client, app):
        uid = self._make_oauth_user(app, email="ok-finalize@test.com")
        self._login_as(client, app, uid)
        r = client.post("/api/auth/oauth-finalize", json={
            "birthdate": _years_ago(14),
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["user"]["birthdate_required"] is False
        with app.app_context():
            u = db.session.get(User, uid)
            assert u.birthdate is not None

    def test_finalize_missing_birthdate_returns_400(self, client, app):
        uid = self._make_oauth_user(app, email="missing-finalize@test.com")
        self._login_as(client, app, uid)
        r = client.post("/api/auth/oauth-finalize", json={})
        assert r.status_code == 400
        assert r.get_json()["error"] == "birthdate_required"

    def test_finalize_overwrite_with_different_value_returns_409(
        self, client, app
    ):
        """Once set, birthdate cannot be silently changed.

        PIPA audit-trail requirement — a user can't lower their stored
        age via repeated POSTs.
        """
        uid = self._make_oauth_user(
            app, email="set-finalize@test.com", with_bd=True
        )
        self._login_as(client, app, uid)
        r = client.post("/api/auth/oauth-finalize", json={
            "birthdate": _years_ago(14),  # different from the seeded 2000-01-01
        })
        assert r.status_code == 409
        assert r.get_json()["error"] == "birthdate_already_set"

    def test_finalize_idempotent_same_value(self, client, app):
        """POSTing the same already-stored value is a no-op success."""
        uid = self._make_oauth_user(
            app, email="idem-finalize@test.com", with_bd=True
        )
        self._login_as(client, app, uid)
        r = client.post("/api/auth/oauth-finalize", json={
            "birthdate": "2000-01-01",
        })
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


# ── serialize_user.birthdate_required gate ─────────────────────────────────

class TestSerializeUserBirthdateRequired:
    def test_null_birthdate_sets_required_true(self, app):
        from services.serializers import serialize_user
        with app.app_context():
            u = User(email="null-bd@test.com", name="x")
            db.session.add(u)
            db.session.commit()
            payload = serialize_user(u)
            assert payload["birthdate_required"] is True

    def test_set_birthdate_sets_required_false(self, app):
        from services.serializers import serialize_user
        with app.app_context():
            u = User(
                email="set-bd@test.com", name="x", birthdate=date(2000, 1, 1)
            )
            db.session.add(u)
            db.session.commit()
            payload = serialize_user(u)
            assert payload["birthdate_required"] is False

    def test_raw_birthdate_value_not_leaked(self, app):
        """We expose the *boolean gate* but not the date itself."""
        from services.serializers import serialize_user
        with app.app_context():
            u = User(
                email="leak-bd@test.com", name="x", birthdate=date(1990, 6, 15)
            )
            db.session.add(u)
            db.session.commit()
            payload = serialize_user(u)
            assert "birthdate" not in payload
