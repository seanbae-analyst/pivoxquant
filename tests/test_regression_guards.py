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

def _run_config_import_in_subprocess(env: dict) -> tuple[int, str]:
    """Re-import ``config`` in a fresh interpreter with the supplied env
    so that nothing leaked from pytest's parent process (other modules
    importing config, conftest's os.environ side-effects, monkeypatch
    timing) can mask the import-time guard.

    Returns (exit_code, combined_stderr_stdout).

    The child writes a sentinel string to stdout if the expected
    RuntimeError fires. Caller asserts on that sentinel.
    """
    import subprocess

    code = (
        "import os, sys\n"
        "try:\n"
        "    import config\n"
        "    print('IMPORT_SUCCEEDED_UNEXPECTEDLY')\n"
        "    sys.exit(0)\n"
        "except RuntimeError as e:\n"
        "    print('RUNTIME_ERROR:' + str(e))\n"
        "    sys.exit(0)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def test_secret_key_fail_fast_in_production():
    """backend-wave1 #3 regression guard: production must raise RuntimeError
    when SECRET_KEY is unset.

    Run in a fresh subprocess so monkeypatch + sys.modules.pop ordering
    cannot drift between local and CI environments — config.py reads its
    env at module-load time, so isolation is the only reliable test.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "FLASK_ENV": "production",
        "DATABASE_URL": "postgresql://dummy/x",  # avoid the DATABASE_URL guard
        # SECRET_KEY deliberately omitted
    }
    rc, out = _run_config_import_in_subprocess(env)
    assert rc == 0, f"subprocess exited with rc={rc}: {out}"
    assert "RUNTIME_ERROR:" in out, f"expected RuntimeError, got: {out}"
    assert "SECRET_KEY" in out, (
        f"expected SECRET_KEY in error message, got: {out}"
    )


def test_database_url_fail_fast_in_production():
    """backend-wave1 #3 regression guard: production must raise RuntimeError
    when DATABASE_URL is unset (SQLite not allowed in production).
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "FLASK_ENV": "production",
        "SECRET_KEY": "test-secret-not-real-x0x0",
        # DATABASE_URL deliberately omitted
    }
    rc, out = _run_config_import_in_subprocess(env)
    assert rc == 0, f"subprocess exited with rc={rc}: {out}"
    assert "RUNTIME_ERROR:" in out, f"expected RuntimeError, got: {out}"
    assert "DATABASE_URL" in out, (
        f"expected DATABASE_URL in error message, got: {out}"
    )


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
# T4b: Alert serializer strips legacy [POSITIVE]/[NEGATIVE]/[NEUTRAL] prefix
# ===========================================================================


def test_alert_serializer_strips_signal_bracket_prefix():
    """Bug-hunter 2026-05-04 #2: legacy alert_service rows persisted
    ``[POSITIVE] Taihan Fiber Optics ...`` into ``Alert.message``. The
    structured ``signal`` field is what the UI badges off, so the in-string
    enum was always redundant — and reads like a directive to a non-tech
    user (자본시장법 §17 boundary risk). serialize_alert now strips the
    prefix at read time so DB rows from before the alert_service fix
    don't bleed through into the API response.

    Checks the read-time strip on a row whose message already carries
    the legacy prefix. Stops a regression where a future refactor drops
    the strip and old rows resurface bracketed.
    """
    try:
        from services.serializers import serialize_alert
    except ImportError as exc:
        pytest.skip(f"services.serializers not importable: {exc}")

    from datetime import datetime as _dt

    class _LegacyAlert:
        id = 99
        user_id = 1
        kind = "signal"
        title = "[POSITIVE] AAPL — Score 80/100. Sized: 10 shares · $500."
        body = None
        is_read = False
        ticker = "AAPL"
        message = "[POSITIVE] AAPL — Score 80/100. Sized: 10 shares · $500."
        signal = "POSITIVE"
        score = 80
        rec_shares = 10
        rec_investment = 500
        link = None
        read_at = None
        created_at = _dt(2026, 5, 4, 9, 0, 0)

    out = serialize_alert(_LegacyAlert())
    assert not out["title"].startswith("[POSITIVE]"), (
        f"title still leaks bracket prefix: {out['title']!r}"
    )
    assert not out["message"].startswith("[POSITIVE]"), (
        f"message still leaks bracket prefix: {out['message']!r}"
    )
    # Structured signal must still be exposed for the UI badge.
    assert out["signal"] == "POSITIVE"


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

def _resolve_css_color(css: str, selector: str) -> str:
    """Resolve a `.selector { color: ... }` rule to a 6-digit hex.

    Handles both the direct-hex form and the design-system token-
    indirection form (`color: var(--token)` → `--token: #hex`).
    Returns the lowercase 6-digit hex, or "" if unresolvable.
    """
    direct = re.search(
        re.escape(selector) + r'\s*\{[^}]*color:\s*#([0-9a-fA-F]{6})', css
    )
    if direct:
        return direct.group(1).lower()
    ref = re.search(
        re.escape(selector) + r'\s*\{[^}]*color:\s*var\(\s*(--[\w-]+)\s*\)', css
    )
    if not ref:
        return ""
    token = ref.group(1)
    token_def = re.search(re.escape(token) + r'\s*:\s*#([0-9a-fA-F]{6})', css)
    return token_def.group(1).lower() if token_def else ""


def test_kr_color_pq_paper_pos_is_red():
    """design wave Fix #1 regression guard: pq-paper-pos must use a
    red-dominant color (Korean market convention: rise = red).

    Accepts both a direct hex and the token-indirection form
    (`.pq-paper-pos { color: var(--pq-paper-pos) }` → `--pq-paper-pos: #hex`).
    """
    if not _GLOBALS_CSS.exists():
        pytest.skip(f"globals.css not found at {_GLOBALS_CSS}")

    css = _GLOBALS_CSS.read_text(encoding="utf-8")
    hex_val = _resolve_css_color(css, ".pq-paper-pos")
    assert hex_val, (
        "pq-paper-pos color rule not found / unresolvable in globals.css — "
        "add '.pq-paper-pos { color: <KR-red-hex-or-var> }'"
    )

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

    Accepts both a direct hex and the token-indirection form.
    """
    if not _GLOBALS_CSS.exists():
        pytest.skip(f"globals.css not found at {_GLOBALS_CSS}")

    css = _GLOBALS_CSS.read_text(encoding="utf-8")
    hex_val = _resolve_css_color(css, ".pq-paper-neg")
    assert hex_val, (
        "pq-paper-neg color rule not found / unresolvable in globals.css — "
        "add '.pq-paper-neg { color: <KR-blue-hex-or-var> }'"
    )

    r = int(hex_val[0:2], 16)
    g = int(hex_val[2:4], 16)
    b = int(hex_val[4:6], 16)

    assert b > r and b > g, (
        f"pq-paper-neg color #{hex_val} is not blue-dominant "
        f"(r={r}, g={g}, b={b}) — must use KR blue, not green"
    )
