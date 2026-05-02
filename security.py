"""
PivoxQuant — Security Middleware
CORS, Rate Limiting, CSRF (Double Submit Cookie), Session Timeout, Security Headers,
Sensitive-header log scrubbing.

Usage:
    from security import init_security
    init_security(app)
"""

import os
import re
import hashlib
import hmac
import secrets
import logging
from datetime import timedelta
from functools import wraps

from flask import request, jsonify, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

# ── Environment Detection ────────────────────────────────────────────────────

_FLASK_ENV = os.environ.get("FLASK_ENV", "development").lower()
_IS_PRODUCTION = _FLASK_ENV == "production"

# ── CORS Origins ─────────────────────────────────────────────────────────────
# CORS_ORIGINS env var: comma-separated list of allowed origins.
# Defaults: development = localhost:3000, production = must be set via env.

_DEFAULT_DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# Production origins that PivoxQuant must always accept, regardless of the
# CORS_ORIGINS env var. Beta users are currently on pivoxquant.vercel.app
# (Vercel preview domain); the apex + www redirect to each other, so all three
# are first-class origins.
_REQUIRED_PROD_ORIGINS = (
    "https://pivoxquant.com",
    "https://www.pivoxquant.com",
    "https://pivoxquant.vercel.app",
)


def _get_cors_origins():
    """Resolve CORS allowed origins from environment.

    Precedence:
      1. `CORS_ORIGINS` env var (comma-separated) — operator override.
         Required production origins are merged in defensively so forgetting
         `https://pivoxquant.vercel.app` doesn't break the current beta.
      2. Production default: the three required PivoxQuant origins.
      3. Development default: localhost on :3000.
    """
    env_origins = os.environ.get("CORS_ORIGINS", "").strip()
    if env_origins:
        parsed = [o.strip().rstrip("/") for o in env_origins.split(",") if o.strip()]
        if _IS_PRODUCTION:
            # Union with required prod origins (preserve operator-specified order)
            for required in _REQUIRED_PROD_ORIGINS:
                if required not in parsed:
                    parsed.append(required)
        return parsed
    if _IS_PRODUCTION:
        # CORS_ORIGINS not set in production — fall back to the known apex +
        # www + Vercel preview instead of denying everything. The prior "empty
        # list" behaviour silently broke the beta when the env var was missing.
        logger.warning(
            "SECURITY: CORS_ORIGINS not set in production — falling back to "
            "required PivoxQuant origins. Set CORS_ORIGINS explicitly in Railway."
        )
        return list(_REQUIRED_PROD_ORIGINS)
    return _DEFAULT_DEV_ORIGINS


# ── Rate Limiter ─────────────────────────────────────────────────────────────

# Storage: in-memory by default. For multi-process prod, use Redis:
#   RATELIMIT_STORAGE_URI=redis://localhost:6379/0
_storage_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    default_limits=["100 per minute"],
    strategy="fixed-window",
)


# ── CSRF Protection (Double Submit Cookie) ───────────────────────────────────

_CSRF_SECRET = os.environ.get("CSRF_SECRET") or os.environ.get("SECRET_KEY") or secrets.token_hex(32)
_CSRF_COOKIE_NAME = "csrf_token"
_CSRF_HEADER_NAME = "X-CSRF-Token"
_CSRF_SAFE_METHODS = frozenset(["GET", "HEAD", "OPTIONS"])
# Endpoints exempt from CSRF:
#   - `/api/billing/webhook` — Stripe webhook, verified by signature
#   - `/api/auth/dev-login`  — dev-only shortcut, never mounted in prod
#   - `/api/auth/logout`, `/api/logout` — logout is idempotent and the worst a
#     CSRF attack can do is sign a user out (no data exposure / state change).
#     The endpoint itself verifies Origin/Referer to reject cross-origin POSTs
#     from hostile pages. Keeping it CSRF-exempt unblocks clients that can't
#     attach the double-submit token (e.g. cookie-partitioning browsers,
#     tools/tests that call the endpoint directly with just the session cookie).
_CSRF_EXEMPT_PREFIXES = (
    "/api/billing/webhook",
    "/api/auth/dev-login",
    "/api/auth/logout",
    "/api/logout",
)


def _get_session_bind_id():
    """Return a stable session-bound identifier for CSRF binding.
    Falls back to empty string for unauthenticated requests so that
    token generation/validation still works before login.
    """
    return session.get("_id", "") or ""


def _generate_csrf_token():
    """Generate a new CSRF token: random_bytes.signature
    The signature includes the session ID so the token is bound to the session.
    """
    random_part = secrets.token_hex(32)
    bind_id = _get_session_bind_id()
    payload = f"{random_part}:{bind_id}"
    sig = hmac.new(
        _CSRF_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{random_part}.{sig}"


def _validate_csrf_token(token):
    """Validate CSRF token signature, including session binding."""
    if not token or "." not in token:
        return False
    try:
        random_part, sig = token.rsplit(".", 1)
        bind_id = _get_session_bind_id()
        payload = f"{random_part}:{bind_id}"
        expected = hmac.new(
            _CSRF_SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


# ── Session Configuration ────────────────────────────────────────────────────

_SESSION_LIFETIME = timedelta(hours=24)
_INACTIVITY_TIMEOUT = timedelta(hours=2)


# ── Sensitive Header Masking (shared with app.py Sentry filter) ──────────────

# Headers whose values must never appear in logs, Sentry events, or request dumps.
# Broker headers (appkey/appsecret) are set by services/broker/user_kis_service.py
# during authenticated KIS requests; if an upstream 4xx/5xx is logged naively,
# the raw credentials would be exposed.
SENSITIVE_HEADERS = frozenset({
    "authorization", "cookie", "set-cookie",
    "x-csrf-token", "x-api-key",
    "appkey", "appsecret",
    "proxy-authorization",
})


def mask_headers(headers):
    """Return a NEW dict with sensitive header values replaced by '***'.
    Case-insensitive. Non-sensitive values are passed through unchanged.

    Use this before logging any dict of HTTP headers. Example:

        logger.debug("KIS request headers=%s", mask_headers(headers))
    """
    if not headers:
        return {}
    out = {}
    for k, v in headers.items():
        out[k] = "***" if isinstance(k, str) and k.lower() in SENSITIVE_HEADERS else v
    return out


# Regex patterns that match accidental leakage of sensitive fields anywhere in a
# log message (e.g., `repr(headers)` or an f-string that spliced a token in).
# These are a defensive second layer: the primary defense is `mask_headers` +
# the Sentry before_send hook.
_SECRET_VALUE_PATTERNS = [
    # "appkey": "XXXX..." or appkey=XXXX...  (JSON/dict/query forms)
    re.compile(r'(?i)("?(?:appkey|appsecret|authorization|x-api-key|cookie)"?\s*[:=]\s*"?)[^"\s,}&]+', re.MULTILINE),
    # Bearer <token>
    re.compile(r'(?i)(Bearer\s+)[A-Za-z0-9\-_\.=]+'),
]


class _SensitiveHeaderScrubber(logging.Filter):
    """logging.Filter that rewrites LogRecord.msg/args to mask secret-looking
    values. Attached to the root logger inside init_security().
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            # Format the final message once, then scrub it. We store it back
            # on .msg and clear .args so downstream formatters don't re-interpolate.
            msg = record.getMessage()
            for pat in _SECRET_VALUE_PATTERNS:
                msg = pat.sub(lambda m: m.group(1) + "***", msg)
            record.msg = msg
            record.args = None
        except Exception:
            # Never let log scrubbing break logging itself.
            pass
        return True


# ── Init Function ────────────────────────────────────────────────────────────

def init_security(app):
    """
    Initialize all security middleware on the Flask app.
    Call this AFTER app.config.from_object(Config) but BEFORE blueprint registration.
    """

    # ── 0. Log Scrubber (attach first so every subsequent logger inherits) ─
    # Mask secrets that may accidentally be logged by third-party libraries
    # (requests, urllib3) or by our own debug logs. Paired with the Sentry
    # `before_send` hook in app.py (which also masks request headers).
    root_logger = logging.getLogger()
    if not any(isinstance(f, _SensitiveHeaderScrubber) for f in root_logger.filters):
        root_logger.addFilter(_SensitiveHeaderScrubber())
    logger.info("SECURITY: sensitive-header log scrubber attached")

    # ── 1. CORS ──────────────────────────────────────────────────────────
    origins = _get_cors_origins()
    CORS(
        app,
        origins=origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", _CSRF_HEADER_NAME],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        max_age=600,
    )
    logger.info(f"SECURITY: CORS configured — origins={origins}")

    # ── 2. Rate Limiting ─────────────────────────────────────────────────
    limiter.init_app(app)

    # Custom 429 handler
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({
            "error": "Too many requests. Please try again later.",
            "error_kr": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
            "retry_after": e.description,
        }), 429

    logger.info("SECURITY: Rate limiting configured — default 100/min")

    # ── 3. Session Configuration ─────────────────────────────────────────
    app.config["PERMANENT_SESSION_LIFETIME"] = _SESSION_LIFETIME
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if _IS_PRODUCTION:
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_DOMAIN"] = os.environ.get("SESSION_COOKIE_DOMAIN")
    app.config["REMEMBER_COOKIE_DURATION"] = _SESSION_LIFETIME
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    if _IS_PRODUCTION:
        app.config["REMEMBER_COOKIE_SECURE"] = True

    logger.info(
        f"SECURITY: Session lifetime={_SESSION_LIFETIME}, "
        f"inactivity timeout={_INACTIVITY_TIMEOUT}"
    )

    # ── 4. Before-request hooks ──────────────────────────────────────────

    @app.before_request
    def _enforce_session():
        """Make sessions permanent and enforce inactivity timeout for authenticated users only."""
        from datetime import datetime, timezone
        from flask_login import current_user
        session.permanent = True

        is_authenticated = bool(getattr(current_user, "is_authenticated", False))
        now = datetime.now(timezone.utc)
        last_active = session.get("_last_active")

        if last_active:
            try:
                if isinstance(last_active, str):
                    last_active = datetime.fromisoformat(last_active)
                if not last_active.tzinfo:
                    last_active = last_active.replace(tzinfo=timezone.utc)
                if (now - last_active) > _INACTIVITY_TIMEOUT:
                    was_authenticated = is_authenticated
                    session.clear()
                    if was_authenticated:
                        from flask_login import logout_user
                        try:
                            logout_user()
                        except Exception as e:
                            logger.debug(
                                "SECURITY: logout_user() failed during session expiry — %s", e
                            )
                        if request.path.startswith("/api/"):
                            return jsonify({
                                "error": "Session expired due to inactivity.",
                                "error_kr": "비활성으로 인해 세션이 만료되었습니다.",
                                "code": "SESSION_EXPIRED",
                            }), 401
                    return
            except (ValueError, TypeError):
                pass

        if is_authenticated:
            session["_last_active"] = now.isoformat()

    @app.before_request
    def _csrf_protect():
        """Enforce CSRF validation on state-changing requests."""
        # Skip safe methods
        if request.method in _CSRF_SAFE_METHODS:
            return

        # Skip exempt endpoints (e.g., Stripe webhooks)
        for prefix in _CSRF_EXEMPT_PREFIXES:
            if request.path.startswith(prefix):
                return

        # Skip if no session cookie (unauthenticated user making first request)
        from flask_login import current_user
        if not current_user.is_authenticated:
            return

        cookie_token = request.cookies.get(_CSRF_COOKIE_NAME)
        header_token = request.headers.get(_CSRF_HEADER_NAME)

        if not cookie_token or not header_token:
            logger.warning(
                f"CSRF: Missing token — path={request.path}, "
                f"cookie={'yes' if cookie_token else 'no'}, "
                f"header={'yes' if header_token else 'no'}"
            )
            return jsonify({
                "error": "CSRF token missing.",
                "error_kr": "CSRF 토큰이 누락되었습니다.",
                "code": "CSRF_MISSING",
            }), 403

        # Double Submit: cookie and header must match, and be validly signed
        if not hmac.compare_digest(cookie_token, header_token):
            logger.warning(f"CSRF: Token mismatch — path={request.path}")
            return jsonify({
                "error": "CSRF token mismatch.",
                "error_kr": "CSRF 토큰이 일치하지 않습니다.",
                "code": "CSRF_MISMATCH",
            }), 403

        if not _validate_csrf_token(cookie_token):
            logger.warning(f"CSRF: Invalid token signature — path={request.path}")
            return jsonify({
                "error": "CSRF token invalid.",
                "error_kr": "CSRF 토큰이 유효하지 않습니다.",
                "code": "CSRF_INVALID",
            }), 403

    # ── 5. After-request hooks ───────────────────────────────────────────

    @app.after_request
    def _set_security_headers(response):
        """Add security headers and CSRF cookie to every response."""

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # X-XSS-Protection 헤더 제거됨 — Chrome 78+ 미지원, 레거시 공격 벡터 존재.
        # CSP로 대체 방어.
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if _IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Set CSRF cookie on every response so the SPA can read it
        # (httpOnly=False so JavaScript can read the token value)
        csrf_token = request.cookies.get(_CSRF_COOKIE_NAME)
        if not csrf_token or not _validate_csrf_token(csrf_token):
            csrf_token = _generate_csrf_token()

        # Double-submit 패턴상 httpOnly=False 불가피 (SPA가 JS로 토큰 읽어 헤더에 실음).
        # XSS가 1건이라도 발생하면 이 토큰은 탈취 가능 → XSS 방어가 1차 방어선.
        # TODO: frontend CSP에서 'unsafe-inline' 제거 필요 (script-src, style-src).
        response.set_cookie(
            _CSRF_COOKIE_NAME,
            csrf_token,
            httponly=False,        # SPA needs to read this via JS
            samesite="Lax",
            secure=_IS_PRODUCTION,
            max_age=int(_SESSION_LIFETIME.total_seconds()),
            path="/",
        )

        return response

    logger.info("SECURITY: All middleware initialized successfully.")
    return app


# ── Rate Limit Decorators for Routes ─────────────────────────────────────────
# Usage in route files:
#   from security import ai_rate_limit, trade_rate_limit
#   @ai_bp.route("/chat", methods=["POST"])
#   @ai_rate_limit
#   def chat(): ...

def ai_rate_limit(f):
    """10 requests/minute — protects AI endpoints (Claude API cost)."""
    @wraps(f)
    @limiter.limit("10 per minute")
    def wrapped(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapped


def trade_rate_limit(f):
    """30 requests/minute — protects trading endpoints."""
    @wraps(f)
    @limiter.limit("30 per minute")
    def wrapped(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapped


def auth_rate_limit(f):
    """5 requests/minute — protects login/register (brute-force prevention)."""
    @wraps(f)
    @limiter.limit("5 per minute")
    def wrapped(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapped


def artifact_rate_limit(f):
    """3 requests/minute — protects PDF/artifact generation (WeasyPrint CPU cost).

    Applied to artifacts.py trigger endpoints to prevent abuse of expensive
    PDF generation pipelines (FMP fetch + AI summarisation + WeasyPrint render).
    """
    @wraps(f)
    @limiter.limit("3 per minute")
    def wrapped(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapped


def general_rate_limit(f):
    """60 requests/minute — generic write-endpoint guard.

    Applied to POST/PUT/DELETE endpoints that don't fit ai/trade/auth/artifact
    buckets (e.g. alerts read/clear, watchlist add, profile update). Prevents
    sustained abuse without throttling normal user activity.
    """
    @wraps(f)
    @limiter.limit("60 per minute")
    def wrapped(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapped
