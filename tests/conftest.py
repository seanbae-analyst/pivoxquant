"""
PivoxQuant — pytest conftest
============================
Global fixtures: test Flask app, isolated SQLite DB, auth helpers, CSRF helpers.

We build a **minimal test Flask app** rather than calling the full `create_app()`
from app.py, because the production factory:
  - Starts a background APScheduler (threads leak into pytest)
  - Populates SignalCache by hitting real external APIs (FMP/Alpaca/KIS)
  - Registers Google/Kakao OAuth that requires live client secrets

The test app wires up the same `db`, `login_manager`, all blueprints and the
same `init_security()` middleware, but against an isolated in-memory SQLite
and with **external APIs mocked**.

CSRF: init_security sets the `csrf_token` cookie on every response, and
mutating requests require a matching `X-CSRF-Token` header. The `client`
fixture below is a thin wrapper that automatically copies the cookie onto
the header for state-changing requests — so tests don't have to care.
Security-critical CSRF tests use the raw Flask client directly.
"""
from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ── live_api auto-skip ────────────────────────────────────────────────────────
# Tests marked @pytest.mark.live_api require a live backend + network.
# They are skipped unless the user explicitly selects them:
#     pytest -m live_api
# This keeps the default `pytest tests/` suite (mocked backend) unaffected.
def pytest_collection_modifyitems(config, items):
    if "live_api" not in (config.getoption("-m", default="") or ""):
        skip_live = pytest.mark.skip(reason="live_api: requires live backend + network. Run: pytest -m live_api")
        for item in items:
            if item.get_closest_marker("live_api"):
                item.add_marker(skip_live)


# ── Path + environment isolation ─────────────────────────────────────────────
# Must happen BEFORE importing the app, so env-backed constants pick up the
# test values (DATABASE_URL, SECRET_KEY, rate-limit storage, etc).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── WeasyPrint native libs (macOS) ───────────────────────────────────────────
# On macOS the brew-installed pango/gobject dylibs are not on the default
# dlopen search path, so `from weasyprint import HTML` raises OSError and the
# 170-case artifact render matrix xfails its entire PDF branch. cffi resolves
# libraries through ctypes.util.find_library, which reads this env var at
# CALL time — so setting it here (before any weasyprint import) is sufficient;
# no wrapper script needed. Linux (CI/Railway) resolves via ldconfig — no-op.
if sys.platform == "darwin" and "DYLD_FALLBACK_LIBRARY_PATH" not in os.environ:
    for _brew_lib in ("/opt/homebrew/lib", "/usr/local/lib"):
        if os.path.isdir(_brew_lib):
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = _brew_lib
            break

# Force a clean, throwaway environment.
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".sqlite", prefix="pivoxquant_test_")
os.close(_test_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-prod-" + "x" * 16
os.environ["CSRF_SECRET"] = "test-csrf-secret-" + "y" * 32
os.environ["FLASK_ENV"] = "testing"
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"
# Prevent flask-limiter from enforcing limits by default (per-test opt-in).
os.environ["RATELIMIT_ENABLED"] = "False"
# Kill any real external API keys that might be in .env.
_KILL_KEYS = (
    "ANTHROPIC_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY",
    "KIS_APP_KEY", "KIS_APP_SECRET", "FMP_API_KEY",
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_PRO", "STRIPE_PRICE_PREMIUM",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "KAKAO_CLIENT_ID", "KAKAO_CLIENT_SECRET",
    "SENTRY_DSN",
    # Dev/QA bypass secrets — a developer's .env commonly sets these, but
    # they conditionally register the dev-login / sim-onboard blueprints
    # (routes/__init__.py). Tests must run in the prod-default state where
    # those routes do NOT exist (test_dev_auth_smoke / test_sim_onboard
    # opt in explicitly via monkeypatch + their own app).
    "DEV_LOGIN_SECRET", "SIM_ONBOARD_SECRET",
)
for _k in _KILL_KEYS:
    os.environ.pop(_k, None)

# Force ALPACA_ENABLED off for tests. The production default is "0" (see
# config.py + Dockerfile), but a developer's .env may override — tests must
# pin it so the kill-switch suite doesn't read the env from the dev's shell.
os.environ["ALPACA_ENABLED"] = "0"

# Prevent the app factory (if ever imported) from spinning up a scheduler.
os.environ["DISABLE_SCHEDULER"] = "1"

# Free-launch flag (models/user.py effective_tier) defaults ON in production so
# the launch opens every paid Artifact + one-way AI to all users. In TESTS we
# pin it OFF so the tier-gating suite keeps exercising the real gating logic
# (which must remain functional for the Stage-1 paywall). The dedicated
# tests/test_free_launch_tiers.py opts the flag back ON per-test via monkeypatch.
os.environ["LAUNCH_FREE_ALL_TIERS"] = "0"

# Eagerly import the app module NOW. ``app.py`` runs
# ``load_dotenv(..., override=True)`` at module import, which RE-injects every
# .env value (incl. DEV_LOGIN_SECRET / SIM_ONBOARD_SECRET). The test app uses
# the pure ``app.birthdate_gate_blocks`` predicate for the PIPA §22 ⑥ age gate,
# so this import is unavoidable. Triggering it here — then stripping the dev
# bypass secrets one more time — guarantees that by the time any test app is
# built (and its blueprints conditionally registered), the dev-login /
# sim-onboard routes are absent (prod-default), which test_dev_auth_smoke /
# test_sim_onboard depend on. (Their own apps opt back in explicitly.)
# Neutralise ``load_dotenv`` BEFORE importing app.py. app.py does
# ``from dotenv import load_dotenv; load_dotenv(..., override=True)`` at module
# top, which would RE-INJECT every real .env value (FMP_API_KEY etc.) — and
# config/service modules capture those into module-level constants AT IMPORT
# TIME, so popping os.environ afterwards is too late (the constant is already
# bound, the price fetcher goes live, and offline-fallback assertions like
# portfolio market_value==shares*avg_cost break). Patching the dotenv attribute
# here means app.py's ``from dotenv import load_dotenv`` binds this no-op, so the
# test env set up above survives intact. (Prod is unaffected — run.py path.)
import dotenv as _dotenv  # noqa: E402
_dotenv.load_dotenv = lambda *a, **k: None  # type: ignore[assignment]
import app as _app_module  # noqa: E402  (predicate source for birthdate gate)
# Belt-and-suspenders: re-apply isolation in case any import already ran.
for _k in _KILL_KEYS:
    os.environ.pop(_k, None)
os.environ["ALPACA_ENABLED"] = "0"
os.environ["DISABLE_SCHEDULER"] = "1"


# ═════════════════════════════════════════════════════════════════════════════
# App factory (test-only)
# ═════════════════════════════════════════════════════════════════════════════

def _build_test_app():
    """Construct a Flask app suitable for unit/integration tests.

    Does NOT start the scheduler, does NOT populate the signal cache,
    does NOT bind live OAuth clients. Uses an isolated SQLite DB.
    """
    from flask import Flask, redirect

    from config import Config
    from extensions import db, login_manager, migrate
    from routes import register_blueprints
    from security import init_security, limiter

    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # not used, but be explicit
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

    # Security middleware — CSRF / CORS / Headers / Session timeout.
    init_security(app)
    # Disable rate limit globally for normal tests; re-enable per test.
    limiter.enabled = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from models import User, Position, TradeHistory  # noqa: F401

    @login_manager.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    @app.route("/")
    def index():
        return redirect("/home")

    # PIPA §22 ⑥ age gate — registered exactly as create_app() wires it, so
    # the half-provisioned-OAuth-user (birthdate NULL) bypass is covered by
    # the integration tests rather than only in prod.
    from flask import request, jsonify as _jsonify
    from flask_login import current_user as _current_user
    birthdate_gate_blocks = _app_module.birthdate_gate_blocks

    @app.before_request
    def _require_birthdate_test():
        if birthdate_gate_blocks(
            request.path,
            bool(getattr(_current_user, "is_authenticated", False)),
            getattr(_current_user, "birthdate", None),
        ):
            return _jsonify({
                "error":    "Birthdate confirmation required.",
                "error_kr": "생년월일 확인이 필요합니다.",
                "code":     "BIRTHDATE_REQUIRED",
            }), 403

    # Register all blueprints exactly as prod does.
    register_blueprints(app)

    with app.app_context():
        db.create_all()

    return app


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask app — built once, DB tables created."""
    application = _build_test_app()
    yield application
    # Cleanup
    try:
        os.remove(_test_db_path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _reset_db(request):
    """Truncate all tables between tests for isolation.

    Only runs when the test actually uses the Flask `app` fixture (or any
    fixture that depends on it). This keeps `test_quant.py` (which has no
    Flask dependency) fast and decoupled.
    """
    # Gate: only if any requested fixture ultimately depends on `app`.
    names = set(getattr(request, "fixturenames", ()))
    app_related = {"app", "client", "raw_client", "db_session", "make_user",
                    "auth_user", "add_position", "mock_fetcher",
                    "mock_realtime", "mock_engine", "enable_rate_limit"}
    if not (names & app_related):
        yield
        return

    app = request.getfixturevalue("app")
    from extensions import db
    with app.app_context():
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
    yield


@pytest.fixture(autouse=True)
def _reset_realtime_kr_health():
    """Isolate the process-wide realtime singleton's transient KR-health state.

    ``services.container.realtime`` is a module singleton that lives for the
    entire test session. A test that drives its KR feed into failure (calls the
    SINGLETON's ``get_price`` on a KR ticker with a stubbed-down fetch) sets
    ``_kr_last_fail = now`` via ``_record_kr_health``. ``kr_health().degraded``
    then stays True for 120 s, and the public ``/api/data/stale-status`` overlay
    (routes/data_status.py) turns that into a forced ``is_stale=True`` — which
    silently pollutes any later test asserting "not stale" (the flaky
    test_data_status_endpoint ``*_returns_not_stale`` cases). Reset to the
    pristine no-signal state before each test so health state can never leak
    across tests through the shared singleton.
    """
    try:
        from services.container import realtime as _rt
        _rt._kr_last_ok = None
        _rt._kr_last_fail = None
    except Exception:
        pass
    yield


class CSRFTestClient:
    """Flask test client that auto-attaches the CSRF token on mutating requests.

    The `init_security` middleware uses double-submit-cookie: the server sends
    the token in a cookie, and the client must echo it in the X-CSRF-Token
    header. This wrapper does that copy transparently.
    """

    def __init__(self, raw_client):
        self._c = raw_client

    def _csrf_headers(self, headers):
        # Grab the latest cookie value the server set.
        token = None
        try:
            for c in self._c._cookies.values():  # Flask 3 test client
                if c.key == "csrf_token":
                    token = c.value
                    break
        except AttributeError:
            pass
        if not token:
            # Trigger a GET to force the cookie to be set.
            self._c.get("/api/auth/me")
            for c in self._c._cookies.values():
                if c.key == "csrf_token":
                    token = c.value
                    break
        h = dict(headers or {})
        if token:
            h.setdefault("X-CSRF-Token", token)
        return h

    def get(self, *a, **kw):
        return self._c.get(*a, **kw)

    def post(self, *a, **kw):
        kw["headers"] = self._csrf_headers(kw.get("headers"))
        return self._c.post(*a, **kw)

    def put(self, *a, **kw):
        kw["headers"] = self._csrf_headers(kw.get("headers"))
        return self._c.put(*a, **kw)

    def delete(self, *a, **kw):
        kw["headers"] = self._csrf_headers(kw.get("headers"))
        return self._c.delete(*a, **kw)

    def patch(self, *a, **kw):
        kw["headers"] = self._csrf_headers(kw.get("headers"))
        return self._c.patch(*a, **kw)

    def set_cookie(self, *a, **kw):
        return self._c.set_cookie(*a, **kw)

    @property
    def raw(self):
        """Expose the underlying Flask test client for security tests."""
        return self._c


@pytest.fixture
def client(app):
    """CSRF-aware test client (use this for most tests)."""
    with app.test_client() as raw:
        yield CSRFTestClient(raw)


@pytest.fixture
def raw_client(app):
    """Plain Flask test client — no CSRF auto-attach (for security tests)."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def db_session(app):
    """Direct DB session for fixture setup."""
    from extensions import db
    with app.app_context():
        yield db.session


@pytest.fixture
def make_user(app):
    """Factory to create a persisted User."""
    from extensions import db
    from models import User

    created = []

    def _make(email="user@test.com", password="password123", name="Tester",
              capital_usd=10000.0, capital_krw=1_000_000.0, tier="free",
              birthdate="_default"):
        # Real provisioned users ALWAYS carry a birthdate — it is captured at
        # /register or /api/auth/oauth-finalize before any feature endpoint is
        # reachable (PIPA §22 ⑥ age gate, enforced by app._require_birthdate).
        # Default the factory to an adult so the common "logged-in user" case
        # mirrors production. Pass ``birthdate=None`` to model the transient
        # half-provisioned OAuth state (birthdate not yet supplied) that the
        # age gate is designed to block.
        from datetime import date
        with app.app_context():
            u = User(email=email, name=name,
                     available_capital=capital_usd,
                     available_capital_krw=capital_krw,
                     subscription_tier=tier)
            if birthdate == "_default":
                u.birthdate = date(1990, 1, 1)
            elif birthdate is not None:
                u.birthdate = birthdate
            u.set_pw(password)
            db.session.add(u)
            db.session.commit()
            created.append((email, password, u.id))
            return {"id": u.id, "email": email, "password": password}
    return _make


@pytest.fixture
def auth_user(client, make_user):
    """Create a user AND log them in via the normal /login endpoint.

    Returns the auth payload dict (incl. id, email).
    """
    user = make_user()
    resp = client.post("/api/auth/login", json={
        "email": user["email"],
        "password": user["password"],
    })
    assert resp.status_code == 200, f"Login failed in fixture: {resp.data!r}"
    return user


@pytest.fixture
def add_position(app):
    """Factory to insert a Position directly in DB (bypasses route)."""
    from extensions import db
    from models import Position

    def _add(user_id, ticker="AAPL", shares=10.0, avg_cost=150.0, buy_fx=1000.0,
             added_at=None):
        with app.app_context():
            p = Position(user_id=user_id, ticker=ticker, shares=shares,
                         avg_cost=avg_cost, buy_fx_rate=buy_fx)
            # Optional opened-date override. The equity-curve endpoint clamps
            # each position's contribution to dates >= added_at (honesty: no
            # fabricated pre-ownership history), so tests exercising a
            # multi-month historical curve must open the position in the past.
            if added_at is not None:
                p.added_at = added_at
            db.session.add(p)
            db.session.commit()
            return p.id
    return _add


@pytest.fixture
def mock_fetcher():
    """Patch the fetcher *bound references* in all route modules.

    Route files do `from services.container import fetcher`, which binds a
    local name. Patching `services.container.fetcher` post-import does NOT
    affect those local names — so we patch each route module directly.
    """
    mock = MagicMock()
    mock.currency.side_effect = lambda t: "KRW" if t.upper().endswith((".KS", ".KQ")) else "USD"
    mock.is_korean.side_effect = lambda t: t.upper().endswith((".KS", ".KQ"))
    with patch("routes.market.fetcher", mock), \
         patch("routes.portfolio.fetcher", mock):
        yield mock


@pytest.fixture
def mock_realtime():
    mock = MagicMock()
    mock.get_prices_batch.return_value = {}
    mock.alpaca_available = False
    # 2026-09-01 — `routes.market` 는 더 이상 `realtime` 을 import 하지 않는다.
    # 이를 쓰던 라우트(/prices, /chart, /market/overview 등 14개)가 프론트
    # 소비자 0 으로 제거되면서 import 도 함께 사라졌다. `mock_engine` 이
    # 같은 이유로 이미 portfolio 만 패치하고 있다 — 같은 패턴을 따른다.
    with patch("routes.portfolio.realtime", mock):
        yield mock


@pytest.fixture
def mock_engine():
    mock = MagicMock()
    mock.portfolio_analytics.return_value = {
        "total_value": 0, "sector_alloc": {}, "risk_score": 50
    }
    # `routes.market` no longer imports `engine` at module level (KR/US market
    # indices go through fetcher + KIS paths instead of QuantEngine). Only
    # portfolio still needs the mock.
    with patch("routes.portfolio.engine", mock):
        yield mock


@pytest.fixture
def enable_rate_limit():
    """Opt-in rate limit enforcement (disabled globally for speed)."""
    from security import limiter
    # Reset storage if supported (flask-limiter >=3 has .reset())
    try:
        limiter.reset()
    except Exception:
        # Fallback: clear the underlying storage directly.
        try:
            limiter.storage.reset()
        except Exception:
            pass
    limiter.enabled = True
    yield limiter
    limiter.enabled = False
    try:
        limiter.reset()
    except Exception:
        pass
