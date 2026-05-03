"""PIPA §28-8 — column shape tests for users.cross_border_consent_*.

Covers the *data layer* of the 국외이전 별도 동의 infrastructure added by
migration 024_cross_border_consent. Endpoint behaviour and the signup
checkbox are exercised in a follow-up PR (PR #73 머지 후).

Why these tests exist
---------------------
``getattr(user, "cross_border_consent_at", None)`` 패턴이 향후 이전·위탁
경로의 가드로 도입될 예정이다. 컬럼이 누락되면 ``getattr`` 가 항상
NULL 을 반환하여 가드가 살아 있는 것처럼 보이지만 실제로는
"동의 미수령" 으로 모든 사용자를 차단하거나 (보수적 기본값) 또는
모두를 통과시키는 (느슨한 기본값) 잘못된 동작을 한다 — 어느 쪽도
§28-8 요건을 위배한다. 따라서 컬럼 존재성 자체를 회귀 가드로 잠근다.

PIPA §28-8 background
---------------------
2024-09 시행. 개인정보 국외이전 시 *명시적 별도* 동의 의무. 위탁 vs
이전 분류와 무관하게 보수적으로 별도 동의를 받는 것이 안전하다.
PivoxQuant 이전·위탁처: Anthropic PBC (미국, Claude API), Stripe Inc.
(미국, 결제), Vercel Inc. / Railway Inc. (미국, 호스팅·DB).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import inspect


# ── Column shape ────────────────────────────────────────────────────────────


def test_cross_border_consent_at_column_exists(app):
    """Migration 024 must provision ``cross_border_consent_at``.

    NULL 은 "동의 미수령" 의미 신호이므로 컬럼은 nullable 이어야 한다.
    """
    from extensions import db

    with app.app_context():
        cols = {c["name"]: c for c in inspect(db.engine).get_columns("users")}
        assert "cross_border_consent_at" in cols, (
            "users.cross_border_consent_at missing — migration 024 did not run"
        )
        col = cols["cross_border_consent_at"]
        type_str = str(col["type"]).upper()
        # SQLAlchemy DateTime materialises as DATETIME on SQLite, TIMESTAMP
        # on PostgreSQL. Accept either.
        assert "DATETIME" in type_str or "TIMESTAMP" in type_str, (
            f"unexpected type for cross_border_consent_at: {type_str}"
        )
        assert col["nullable"] is True, (
            "cross_border_consent_at must be nullable — NULL is the "
            "'consent never given' sentinel"
        )


def test_cross_border_consent_revoked_at_column_exists(app):
    """Migration 024 must provision ``cross_border_consent_revoked_at``."""
    from extensions import db

    with app.app_context():
        cols = {c["name"]: c for c in inspect(db.engine).get_columns("users")}
        assert "cross_border_consent_revoked_at" in cols, (
            "users.cross_border_consent_revoked_at missing — migration 024 "
            "did not run"
        )
        col = cols["cross_border_consent_revoked_at"]
        type_str = str(col["type"]).upper()
        assert "DATETIME" in type_str or "TIMESTAMP" in type_str, (
            f"unexpected type for cross_border_consent_revoked_at: {type_str}"
        )
        assert col["nullable"] is True, (
            "cross_border_consent_revoked_at must be nullable — NULL is "
            "the 'never revoked' sentinel"
        )


# ── Default values ──────────────────────────────────────────────────────────


def test_default_is_null_for_new_user(app, make_user):
    """A freshly created user must default to NULL on both columns.

    NULL = "동의 미수령" / "철회 이력 없음". 가입 플로우에서 5번째
    체크박스가 추가되면 그때 ``cross_border_consent_at`` 가 채워진다.
    """
    from extensions import db
    from models import User

    user = make_user(email="cb-consent-default@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u is not None
        assert u.cross_border_consent_at is None, (
            "New users must start with cross_border_consent_at = NULL "
            "(consent never given) so the §28-8 guard short-circuits "
            "transfers until an explicit checkbox is submitted."
        )
        assert u.cross_border_consent_revoked_at is None


# ── Round-trip writes ───────────────────────────────────────────────────────


def test_can_set_consent_timestamp(app, make_user):
    """The column must accept and persist a UTC datetime."""
    from extensions import db
    from models import User

    user = make_user(email="cb-consent-set@test.com")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.cross_border_consent_at = now
        db.session.commit()

        # Re-read in a fresh load to confirm persistence.
        db.session.expire_all()
        u2 = db.session.get(User, user["id"])
        assert u2.cross_border_consent_at is not None
        # SQLite drops sub-second precision in some configs — compare to the
        # second.
        assert (
            u2.cross_border_consent_at.replace(microsecond=0)
            == now.replace(microsecond=0)
        )


def test_can_set_revoked_timestamp(app, make_user):
    """Revocation timestamp can be set independently of the grant ts."""
    from extensions import db
    from models import User

    user = make_user(email="cb-consent-revoke@test.com")
    grant = datetime(2026, 5, 1, 12, 0, 0)
    revoke = datetime(2026, 5, 3, 9, 30, 0)
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.cross_border_consent_at = grant
        u.cross_border_consent_revoked_at = revoke
        db.session.commit()

        db.session.expire_all()
        u2 = db.session.get(User, user["id"])
        assert u2.cross_border_consent_at == grant
        assert u2.cross_border_consent_revoked_at == revoke
