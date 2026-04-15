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

# ── Path + environment isolation ─────────────────────────────────────────────
# Must happen BEFORE importing the app, so env-backed constants pick up the
# test values (DATABASE_URL, SECRET_KEY, rate-limit storage, etc).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Force a clean, throwaway environment.
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".sqlite", prefix="stockpilot_test_")
os.close(_test_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-prod-" + "x" * 16
os.environ["CSRF_SECRET"] = "test-csrf-secret-" + "y" * 32
os.environ["FLASK_ENV"] = "testing"
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"
# Prevent flask-limiter from enforcing limits by default (per-test opt-in).
os.environ["RATELIMIT_ENABLED"] = "False"
# Kill any real external API keys that might be in .env.
for _k in (
    "ANTHROPIC_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY",
    "KIS_APP_KEY", "KIS_APP_SECRET", "FMP_API_KEY",
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_PRO", "STRIPE_PRICE_PREMIUM",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "KAKAO_CLIENT_ID", "KAKAO_CLIENT_SECRET",
    "SENTRY_DSN",
):
    os.environ.pop(_k, None)

# Prevent the app factory (if ever imported) from spinning up a scheduler.
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
              capital_usd=10000.0, capital_krw=1_000_000.0, tier="free"):
        with app.app_context():
            u = User(email=email, name=name,
                     available_capital=capital_usd,
                     available_capital_krw=capital_krw,
                     subscription_tier=tier)
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

    def _add(user_id, ticker="AAPL", shares=10.0, avg_cost=150.0, buy_fx=1000.0):
        with app.app_context():
            p = Position(user_id=user_id, ticker=ticker, shares=shares,
                         avg_cost=avg_cost, buy_fx_rate=buy_fx)
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
    with patch("routes.market.realtime", mock), \
         patch("routes.portfolio.realtime", mock):
        yield mock


@pytest.fixture
def mock_engine():
    mock = MagicMock()
    mock.portfolio_analytics.return_value = {
        "total_value": 0, "sector_alloc": {}, "risk_score": 50
    }
    with patch("routes.market.engine", mock), \
         patch("routes.portfolio.engine", mock):
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
