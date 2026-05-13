"""Tests for routes/sim_onboard.py — CAUS autonomous sim-user login.

The blueprint is *conditionally registered* in routes/__init__.py — when
SIM_ONBOARD_SECRET is unset at app-boot, the routes don't exist (Flask 404).
We therefore stand up a dedicated test app for this module with the env var
set, parallel to how test_dev_auth_smoke.py handles the same pattern (but
inverse: that file tests the unset case).

Security properties verified:
  * Missing SIM_ONBOARD_SECRET → 404 (blueprint not mounted).
  * Missing/invalid User-Agent prefix → 403.
  * Missing/malformed ticket → 400.
  * Bad HMAC signature → 401.
  * Expired (>5min old) ticket → 401.
  * Email not in sim allow-list → 403.
  * Real (non-simulated) user collision → 409.
  * Valid ticket + sim email → 200, user persisted with is_simulated=True.
  * Re-login same sim user → 200, no duplicate row.
  * IP rate-limit (3/min) → 429 on 4th request.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest


# ── Module-scoped app with SIM_ONBOARD_SECRET set ────────────────────────────

_SIM_SECRET = "test-sim-onboard-secret-do-not-use-in-prod"
_UA = "PivoxQuantCAUS/1.0"


def _build_sim_app():
    """Build a test app with SIM_ONBOARD_SECRET set so the blueprint mounts.

    This mirrors the pattern in tests/conftest.py::_build_test_app but with
    a dedicated SQLite + the sim-onboard env var. We can't reuse the
    session-scoped `app` fixture because env-var-time-of-boot determines
    whether the blueprint is registered.
    """
    from flask import Flask, redirect

    from config import Config
    from extensions import db, login_manager, migrate
    from routes import register_blueprints
    from security import init_security, limiter

    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

    init_security(app)
    limiter.enabled = False  # default off; test_rate_limit re-enables.

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from models import User  # noqa: F401

    @login_manager.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    @app.route("/")
    def index():
        return redirect("/home")

    register_blueprints(app)

    with app.app_context():
        db.create_all()

    return app


@pytest.fixture(scope="module")
def sim_app():
    """Module-scoped Flask app with SIM_ONBOARD_SECRET set at boot."""
    # Distinct SQLite so we don't collide with the session-scoped conftest DB.
    fd, path = tempfile.mkstemp(suffix=".sqlite", prefix="pivoxquant_sim_test_")
    os.close(fd)
    orig_db = os.environ.get("DATABASE_URL")
    orig_secret = os.environ.get("SIM_ONBOARD_SECRET")
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    os.environ["SIM_ONBOARD_SECRET"] = _SIM_SECRET
    try:
        app = _build_sim_app()
        yield app
    finally:
        if orig_db is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = orig_db
        if orig_secret is None:
            os.environ.pop("SIM_ONBOARD_SECRET", None)
        else:
            os.environ["SIM_ONBOARD_SECRET"] = orig_secret
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _reset_sim_db(sim_app):
    """Truncate tables between tests in this module."""
    from extensions import db
    with sim_app.app_context():
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def sim_client(sim_app):
    with sim_app.test_client() as c:
        yield c


# ── Ticket helpers ───────────────────────────────────────────────────────────

def _build_ticket(email: str, secret: str = _SIM_SECRET,
                  ts: datetime | None = None) -> str:
    """Construct an HMAC ticket matching the format in caus_daily_sweep.py."""
    ts = ts or datetime.now(timezone.utc)
    ts_str = ts.isoformat()
    sig = hmac.new(
        secret.encode("utf-8"),
        f"{ts_str}:{email}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{ts_str}:{email}:{sig}".encode()).decode()


# ── Tests: gate / auth ───────────────────────────────────────────────────────

def test_endpoint_404_when_secret_unset(client):
    """When SIM_ONBOARD_SECRET is unset at boot, blueprint isn't mounted.

    Uses the default conftest `client` fixture (no sim secret set there).
    """
    r = client.raw.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA, "Content-Type": "application/json"},
        json={"ticket": "x", "email": "seanbae1521+sim1@gmail.com"},
    )
    assert r.status_code == 404


def test_invalid_user_agent_403(sim_client):
    """Caller without PivoxQuantCAUS/ UA prefix is rejected."""
    email = "seanbae1521+sim1@gmail.com"
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": "Mozilla/5.0"},
        json={"ticket": _build_ticket(email), "email": email},
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "invalid client"


def test_missing_ticket_400(sim_client):
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"email": "seanbae1521+sim1@gmail.com"},
    )
    assert r.status_code == 400


def test_missing_email_400(sim_client):
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket("seanbae1521+sim1@gmail.com")},
    )
    assert r.status_code == 400


def test_bad_hmac_signature_401(sim_client):
    email = "seanbae1521+sim1@gmail.com"
    bad = _build_ticket(email, secret="wrong-secret")
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": bad, "email": email},
    )
    assert r.status_code == 401


def test_expired_ticket_401(sim_client):
    email = "seanbae1521+sim1@gmail.com"
    # 6 minutes old — beyond TICKET_TTL_SECONDS=300.
    old = datetime.now(timezone.utc) - timedelta(minutes=6)
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(email, ts=old), "email": email},
    )
    assert r.status_code == 401


def test_garbage_ticket_401(sim_client):
    """Non-base64, non-parseable ticket → 401, no stack trace leak."""
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": "!!!not-base64!!!", "email": "seanbae1521+sim1@gmail.com"},
    )
    assert r.status_code == 401


def test_body_email_ticket_email_mismatch_400(sim_client):
    """Body email and ticket email must agree (defense in depth)."""
    ticket_email = "seanbae1521+sim1@gmail.com"
    body_email = "seanbae1521+sim2@gmail.com"
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(ticket_email), "email": body_email},
    )
    assert r.status_code == 400


# ── Tests: email allow-list ──────────────────────────────────────────────────

@pytest.mark.parametrize("bad_email", [
    "attacker@gmail.com",
    "seanbae1521@gmail.com",          # bare alias, no +sim suffix
    "seanbae1521+sim0@gmail.com",      # sim0 disallowed (no leading zero/zero)
    "seanbae1521+other@gmail.com",
    "sim1@gmail.com",                  # right pattern wrong domain
    "sim1@pivoxquant.com",             # production domain — never allowed
])
def test_non_sim_email_403(sim_client, bad_email):
    """Email outside the sim regex is rejected even with a valid ticket."""
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(bad_email), "email": bad_email},
    )
    assert r.status_code == 403


def test_real_user_collision_409(sim_client, sim_app):
    """Pre-existing real user with a sim-shaped email cannot be hijacked.

    Manually inserts a real user with is_simulated=False and an alias that
    *would* match the regex. The endpoint must refuse rather than re-login.
    """
    from extensions import db
    from models import User

    sim_email = "seanbae1521+sim7@gmail.com"
    with sim_app.app_context():
        u = User(email=sim_email, is_simulated=False, name="REAL USER")
        db.session.add(u)
        db.session.commit()

    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(sim_email), "email": sim_email},
    )
    assert r.status_code == 409
    assert r.get_json()["error"] == "email reserved for real user"


# ── Tests: happy path ────────────────────────────────────────────────────────

def test_valid_ticket_creates_sim_user(sim_client, sim_app):
    email = "seanbae1521+sim3@gmail.com"
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(email), "email": email},
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ok"] is True
    assert body["email"] == email
    assert body["is_simulated"] is True
    assert isinstance(body["user_id"], int)

    # Persistence check: row exists and is_simulated is server-side TRUE.
    from extensions import db
    from models import User
    with sim_app.app_context():
        u = db.session.get(User, body["user_id"])
        assert u is not None
        assert u.email == email
        assert u.is_simulated is True
        assert u.oauth_provider == "sim"


def test_relogin_same_sim_user_no_duplicate(sim_client, sim_app):
    """Hitting the endpoint twice for the same sim email reuses the row."""
    email = "seanbae1521+sim5@gmail.com"
    r1 = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(email), "email": email},
    )
    assert r1.status_code == 200
    uid1 = r1.get_json()["user_id"]

    r2 = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(email), "email": email},
    )
    assert r2.status_code == 200
    uid2 = r2.get_json()["user_id"]
    assert uid1 == uid2

    from extensions import db
    from models import User
    with sim_app.app_context():
        count = db.session.query(User).filter(
            db.func.lower(User.email) == email.lower()
        ).count()
        assert count == 1


def test_local_domain_email_accepted(sim_client):
    """The .local fallback aliases work too (offline fixture usage)."""
    email = "sim2@pivoxquant-test.local"
    r = sim_client.post(
        "/api/auth/sim-onboard",
        headers={"User-Agent": _UA},
        json={"ticket": _build_ticket(email), "email": email},
    )
    assert r.status_code == 200
    assert r.get_json()["is_simulated"] is True


# ── Tests: rate limit ───────────────────────────────────────────────────────

def test_rate_limit_3_per_minute(sim_client, sim_app):
    """The 4th hit from the same IP within 60s returns 429."""
    from security import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    limiter.enabled = True
    try:
        # Use 4 *distinct* emails so the per-email (1/h) bucket doesn't fire
        # first — we want to assert the IP (3/min) bucket here.
        codes = []
        for i in range(1, 5):
            email = f"seanbae1521+sim{i}@gmail.com"
            r = sim_client.post(
                "/api/auth/sim-onboard",
                headers={"User-Agent": _UA},
                json={"ticket": _build_ticket(email), "email": email},
            )
            codes.append(r.status_code)
        # First three should be 200; the fourth must be 429.
        assert codes[:3] == [200, 200, 200], codes
        assert codes[3] == 429, codes
    finally:
        limiter.enabled = False
        try:
            limiter.reset()
        except Exception:
            pass


# ── Tests: module structure (mirrors test_dev_auth_smoke.py) ─────────────────

class TestSimOnboardModule:
    def test_module_imports_cleanly(self):
        from routes import sim_onboard
        assert hasattr(sim_onboard, "sim_onboard_bp")
        assert hasattr(sim_onboard, "sim_onboard")
        assert hasattr(sim_onboard, "_verify_ticket")
        assert sim_onboard.TICKET_TTL_SECONDS == 300
        assert sim_onboard.REQUIRED_UA_PREFIX == "PivoxQuantCAUS/"

    def test_blueprint_has_one_route(self):
        from routes.sim_onboard import sim_onboard_bp
        assert len(sim_onboard_bp.deferred_functions) == 1

    def test_regex_accepts_known_aliases(self):
        from routes.sim_onboard import SIM_EMAIL_REGEX
        for ok in [
            "seanbae1521+sim1@gmail.com",
            "seanbae1521+sim10@gmail.com",
            "seanbae1521+sim99@gmail.com",
            "sim1@pivoxquant-test.local",
            "sim50@pivoxquant-test.local",
        ]:
            assert SIM_EMAIL_REGEX.match(ok), ok
        for bad in [
            "seanbae1521@gmail.com",
            "seanbae1521+sim0@gmail.com",
            "seanbae1521+sim100@gmail.com",   # 3 digits — beyond sim99
            "seanbae1521+sim1@evil.com",
            "sim1@pivoxquant.com",
            "attacker@pivoxquant-test.local",
            "",
        ]:
            assert not SIM_EMAIL_REGEX.match(bad), bad
