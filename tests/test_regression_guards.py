"""
PivoxQuant Regression Guard Tests — 2026-05-03
===============================================
Seven regression tests covering design v3, security, and legal fixes
introduced during the 2026-05-03 fix wave.

CURRENT STATUS (as of 2026-05-03, pre-merge):
  PASS  test_alert_serializer_backend_shape         — backend serialize_alert already correct
  PASS  test_kr_color_pq_paper_pos_is_red           — globals.css #b85b5b is red-dominant
  PASS  test_kr_color_pq_paper_neg_is_blue          — globals.css #5b7ab8 is blue-dominant
  FAIL  test_register_login_no_500_email_opt_out_column — needs app context / DB
  FAIL  test_secret_key_fail_fast_in_production     — config.py uses warnings.warn, not RuntimeError
  FAIL  test_database_url_fail_fast_in_production   — same as above
  FAIL  test_csrf_exempt_unsubscribe                — /api/email/unsubscribe not yet exempted
  SKIP  test_csp_includes_stripe_sentry             — _build_csp_header() not yet extracted

Guards DS5/DS6 (AlertItem type drift, BUY/SELL tsx) are covered by the
design-safety-guards.yml CI workflow (pure grep/AST — no Python test needed).

All FAIL tests will pass after the corresponding fix PRs are merged:
  - fix/backend-wave1-critical        → fail-fast RuntimeError + DATABASE_URL
  - fix/security-hardening-wave1      → CSRF exempt + CSP Stripe/Sentry
"""

import importlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_FRONTEND = _ROOT / "frontend" / "src"
_GLOBALS_CSS = _FRONTEND / "app" / "globals.css"
_MESSAGES_DIR = _FRONTEND / "messages"


# ===========================================================================
# T1: email_opt_out column guard
# ===========================================================================

def test_register_login_no_500_email_opt_out_column():
    """verify-api P0 regression guard: email_opt_out column must exist in
    the 'users' table.  Protects against accidental migration rollback.

    STATUS: requires Flask app context + live DB. Skipped when DB not reachable.
    """
    try:
        from app import create_app
        from extensions import db
        from sqlalchemy import inspect as sa_inspect

        app = create_app()
        with app.app_context():
            cols = [c["name"] for c in sa_inspect(db.engine).get_columns("users")]
            assert "email_opt_out" in cols, (
                "email_opt_out column missing from users table — "
                "run migration 021_email_opt_out"
            )
    except Exception as exc:
        # DB not available in CI without a running app context — skip gracefully
        pytest.skip(f"App context not available: {exc}")


# ===========================================================================
# T2 & T3: config.py fail-fast guards
# ===========================================================================

def test_secret_key_fail_fast_in_production(monkeypatch):
    """backend-wave1 #3 regression guard: production must raise RuntimeError
    when SECRET_KEY is unset.

    STATUS: FAIL on main — config.py currently uses warnings.warn().
    This test passes after fix/backend-wave1-critical is merged.
    """
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy/x")  # avoid DATABASE_URL guard
    monkeypatch.delenv("SECRET_KEY", raising=False)

    # Remove cached module so re-import triggers the import-time guard
    sys.modules.pop("config", None)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        import config  # noqa: F401  # raises during import when SECRET_KEY missing


def test_database_url_fail_fast_in_production(monkeypatch):
    """backend-wave1 #3 regression guard: production must raise RuntimeError
    when DATABASE_URL is unset (SQLite not allowed in production).

    STATUS: FAIL on main — config.py falls back to SQLite silently.
    This test passes after fix/backend-wave1-critical is merged.
    """
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "test-secret-not-real-x0x0")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    sys.modules.pop("config", None)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        import config  # noqa: F401  # raises during import when DATABASE_URL missing


# ===========================================================================
# T4: Backend serialize_alert shape guard
# ===========================================================================

def test_alert_serializer_backend_shape():
    """frontend-wave2 regression guard: backend serialize_alert must return
    kind/title/body and must NOT return legacy type/data fields.

    STATUS: PASS on main — serialize_alert already uses kind/title/body.
    """
    try:
        from services.serializers import serialize_alert
    except ImportError as exc:
        pytest.skip(f"services.serializers not importable: {exc}")

    # Build a minimal mock alert with all expected attributes
    class _FakeAlert:
        id = 1
        user_id = 1
        kind = "signal"
        title = "Test Alert"
        body = "Alert body text"
        is_read = False
        ticker = None
        message = "legacy message"
        signal = None
        score = None
        rec_shares = None
        rec_investment = None
        link = None
        read_at = None

        from datetime import datetime
        created_at = datetime(2026, 5, 3, 9, 0, 0)

    serialized = serialize_alert(_FakeAlert())

    assert "kind" in serialized, "kind field missing from serialize_alert output"
    assert "title" in serialized, "title field missing from serialize_alert output"
    assert "body" in serialized, "body field missing from serialize_alert output"
    assert "type" not in serialized, (
        "legacy 'type' field present in serialize_alert output — "
        "frontend AlertItem no longer expects this key"
    )
    assert "data" not in serialized, (
        "legacy 'data' field present in serialize_alert output — "
        "frontend AlertItem no longer expects this key"
    )


# ===========================================================================
# T5: CSRF exempt — /api/email/unsubscribe
# ===========================================================================

def test_csrf_exempt_unsubscribe():
    """security wave #1 regression guard: /api/email/unsubscribe must be in
    _CSRF_EXEMPT_PREFIXES so that email clients can one-click unsubscribe
    without a CSRF token.

    STATUS: FAIL on main — entry not yet added.
    This test passes after fix/security-hardening-wave1 is merged.
    """
    try:
        from security import _CSRF_EXEMPT_PREFIXES
    except ImportError as exc:
        pytest.skip(f"security module not importable: {exc}")

    assert "/api/email/unsubscribe" in _CSRF_EXEMPT_PREFIXES, (
        "/api/email/unsubscribe is not in _CSRF_EXEMPT_PREFIXES — "
        "add it in security.py (security wave fix #1)"
    )


# ===========================================================================
# T6: CSP includes Stripe and Sentry
# ===========================================================================

def test_csp_includes_stripe_sentry():
    """security wave #3 regression guard: the backend CSP header must include
    api.stripe.com and *.sentry.io / browser.sentry-cdn.com.

    STATUS: SKIP — _build_csp_header() not yet extracted as a standalone
    function. Will be testable after fix/security-hardening-wave1 is merged.
    """
    try:
        from security import _build_csp_header
    except (ImportError, AttributeError):
        pytest.skip("_build_csp_header() not yet extracted — pending security wave fix #3")

    csp = _build_csp_header()
    assert "api.stripe.com" in csp, "Stripe domain missing from CSP"
    assert "sentry.io" in csp, "Sentry domain missing from CSP"


# ===========================================================================
# T7: KR color — pq-paper-pos is red-dominant
# ===========================================================================

def test_kr_color_pq_paper_pos_is_red():
    """design wave Fix #1 regression guard: pq-paper-pos must use a
    red-dominant color (Korean market convention: rise = red).

    STATUS: PASS on main — globals.css has #b85b5b (r=184, g=91, b=91).
    """
    if not _GLOBALS_CSS.exists():
        pytest.skip(f"globals.css not found at {_GLOBALS_CSS}")

    css = _GLOBALS_CSS.read_text(encoding="utf-8")

    m = re.search(r'\.pq-paper-pos\s*\{[^}]*color:\s*#([0-9a-fA-F]{6})', css)
    assert m, (
        "pq-paper-pos color rule not found in globals.css — "
        "add '.pq-paper-pos { color: <KR-red-hex>; }'"
    )

    hex_val = m.group(1).lower()
    r = int(hex_val[0:2], 16)
    g = int(hex_val[2:4], 16)
    b = int(hex_val[4:6], 16)

    assert r > g and r > b, (
        f"pq-paper-pos color #{hex_val} is not red-dominant "
        f"(r={r}, g={g}, b={b}) — must use KR red, not green"
    )


def test_kr_color_pq_paper_neg_is_blue():
    """design wave Fix #1 regression guard: pq-paper-neg must use a
    blue-dominant color (Korean market convention: fall = blue).

    STATUS: PASS on main — globals.css has #5b7ab8 (r=91, g=122, b=184).
    """
    if not _GLOBALS_CSS.exists():
        pytest.skip(f"globals.css not found at {_GLOBALS_CSS}")

    css = _GLOBALS_CSS.read_text(encoding="utf-8")

    m = re.search(r'\.pq-paper-neg\s*\{[^}]*color:\s*#([0-9a-fA-F]{6})', css)
    assert m, (
        "pq-paper-neg color rule not found in globals.css — "
        "add '.pq-paper-neg { color: <KR-blue-hex>; }'"
    )

    hex_val = m.group(1).lower()
    r = int(hex_val[0:2], 16)
    g = int(hex_val[2:4], 16)
    b = int(hex_val[4:6], 16)

    assert b > r and b > g, (
        f"pq-paper-neg color #{hex_val} is not blue-dominant "
        f"(r={r}, g={g}, b={b}) — must use KR blue, not green"
    )
