"""Auth routes: register, login, logout, me, Google OAuth, Kakao OAuth."""
from __future__ import annotations

import logging
import os
import secrets
import time
from urllib.parse import urlparse

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, request, jsonify, redirect, session, current_app
from flask_login import login_user, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


def _safe_next(next_url):
    """Open redirect 방어 + 폐기된 경로 차단.

    - 스킴-relative (//evil.com) + 절대 URL 차단
    - 존재하지 않는 Next.js 라우트 (/landing, /beta 등) → 유효 경로로 매핑
    """
    if not next_url or not isinstance(next_url, str):
        return "/home"
    if next_url.startswith("//") or "://" in next_url:
        return "/home"
    if not next_url.startswith("/"):
        return "/home"

    # Path-only 비교용: 쿼리스트링/프래그먼트 제거.
    path_only = next_url.split("?", 1)[0].split("#", 1)[0].rstrip("/")

    # 폐기/존재하지 않는 라우트 매핑.
    # /landing → /home (OAuth 콜백 후 404 방지, P0 hotfix 2026-05-03)
    # /beta → /beta-gate (실제 Next.js 라우트)
    if path_only in ("/landing", ""):
        return "/home"
    if path_only == "/beta":
        return "/beta-gate"

    return next_url

from extensions import db
from models import (
    User, Position, TradeHistory, Alert, Watchlist,
    InvestmentProfile, BrokerConnection, PushSubscription,
    PortfolioShare,
    Artifact, UserReferral,
    ArtifactFeedback, BehavioralScore,
    AITwinPortfolio, AITwinWeeklyReport,
    PreTradeReflection, PersonaSnapshot, WeeklyPulse,
)
from security import auth_rate_limit, general_rate_limit
from services.age_verification import (
    BirthdateValidationError,
    check_birthdate_payload,
)
from services.serializers import serialize_user
from .decorators import api_auth

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Root-level alias blueprint for `/api/logout`. Some clients (user-tester
# probe, legacy mobile) hit this shorter path; the canonical endpoint
# remains `/api/auth/logout`.
auth_alias_bp = Blueprint("auth_alias", __name__)

# ── OAuth setup ──────────────────────────────────────────────────────────────
oauth = OAuth()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Whitelist of origins we are willing to redirect OAuth callbacks to.
# Keeps the open-redirect surface tight even when a user-controlled header
# (Referer / Origin / X-Forwarded-Host) is used to resolve the origin.
_ALLOWED_OAUTH_ORIGINS = frozenset({
    "https://pivoxquant.vercel.app",
    "https://pivoxquant.com",
    "https://www.pivoxquant.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
})


def _resolve_frontend_url() -> str:
    """Return the user-facing origin for OAuth redirects.

    Priority:
      1. Referer header origin (user's actual frontend) — if whitelisted
      2. Origin header — if whitelisted
      3. X-Forwarded-Host (injected by Vercel / Railway edge) — if whitelisted
      4. FRONTEND_URL env var (fallback for CLI/direct tests)

    Only origins in `_ALLOWED_OAUTH_ORIGINS` are honoured; everything else
    falls through to the env var default so an attacker cannot steer the
    OAuth callback to a hostile domain via crafted headers.
    """
    candidates = []

    referrer = request.referrer
    if referrer:
        parsed = urlparse(referrer)
        if parsed.scheme and parsed.netloc:
            candidates.append(f"{parsed.scheme}://{parsed.netloc}")

    origin_hdr = request.headers.get("Origin")
    if origin_hdr:
        candidates.append(origin_hdr.rstrip("/"))

    fwd_host = request.headers.get("X-Forwarded-Host")
    if fwd_host:
        # Forwarded-Host is just a host — pair it with the forwarded proto
        # when available, default to https in production.
        proto = request.headers.get("X-Forwarded-Proto", "https")
        # Take the first host if the header is a comma-separated chain.
        first_host = fwd_host.split(",")[0].strip()
        if first_host:
            candidates.append(f"{proto}://{first_host}".rstrip("/"))

    for origin in candidates:
        if origin in _ALLOWED_OAUTH_ORIGINS:
            return origin

    # Fallback: environment variable (configured per deploy).
    return os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")


# ── Stateless OAuth state (HMAC signed token) ───────────────────────────────
#
# Why stateless:
#   Vercel rewrites `/api/*` to Railway. Session cookies issued on the
#   /api/auth/google redirect don't always round-trip back to the callback,
#   so authlib's session-based state check (`_state_<name>_<state>`) fails
#   with state_mismatch. We sign state as a self-contained token so
#   verification does not require the cookie surviving the round-trip.
#
# The signed state carries everything authlib needs (nonce, redirect_uri)
# plus our own bookkeeping (origin, provider). On the callback we:
#   1. Verify the HMAC signature + timestamp (10-min expiry).
#   2. Rehydrate authlib's `_state_<name>_<state>` session slot in-process
#      so `authorize_access_token()` can read it back out.
#
# This keeps the authlib code path untouched while removing the
# cross-request session-cookie dependency that was causing state_mismatch.

_OAUTH_STATE_MAX_AGE = 300  # seconds (5 minutes; was 600 — security M5 2026-05-10
                            # narrows replay window for leaked state tokens)
_OAUTH_STATE_SALT = "pivoxquant.oauth.state.v1"


def _state_serializer() -> URLSafeTimedSerializer:
    """Serializer bound to the app's SECRET_KEY."""
    secret = current_app.secret_key
    if not secret:
        # Should never happen — config.py always sets one (random fallback).
        logger.critical("OAuth state serializer: SECRET_KEY missing on app")
        raise RuntimeError("SECRET_KEY not configured")
    return URLSafeTimedSerializer(secret, salt=_OAUTH_STATE_SALT)


def _build_signed_state(provider: str, origin: str, redirect_uri: str) -> str:
    """Build a self-contained HMAC-signed state token.

    The full signed string is passed to the OAuth provider as `state=`.
    On the callback the provider echoes it back verbatim; we verify the
    signature, decode the payload, and rehydrate authlib's session slot
    using the signed token itself as the lookup key.
    """
    nonce = secrets.token_urlsafe(16)
    payload = {
        "n": nonce,               # OIDC nonce (Google id_token binding)
        "o": origin,              # frontend origin for final redirect
        "p": provider,            # "google" | "kakao"
        "r": redirect_uri,        # exact redirect_uri used in the request
        "k": secrets.token_urlsafe(8),  # anti-replay nonce for the payload
    }
    return _state_serializer().dumps(payload)


def _verify_signed_state(signed: str | None, expected_provider: str) -> dict | None:
    """Verify a signed state token. Returns the payload dict or None.

    Logs the failure reason at warning level; callers translate None into
    a user-facing error redirect.
    """
    if not signed:
        logger.warning("OAuth state verify: missing state parameter (provider=%s)", expected_provider)
        return None
    try:
        payload = _state_serializer().loads(signed, max_age=_OAUTH_STATE_MAX_AGE)
    except SignatureExpired:
        logger.warning("OAuth state verify: state token expired (provider=%s)", expected_provider)
        return None
    except BadSignature:
        logger.warning("OAuth state verify: state signature invalid (provider=%s)", expected_provider)
        return None
    except Exception:  # noqa: BLE001 — defensive, never let a decode bug 500
        logger.exception("OAuth state verify: unexpected decode error (provider=%s)", expected_provider)
        return None

    if payload.get("p") != expected_provider:
        logger.warning(
            "OAuth state verify: state provider mismatch (got=%s expected=%s)",
            payload.get("p"), expected_provider,
        )
        return None
    return payload


def _rehydrate_authlib_state(provider: str, received_state: str, payload: dict) -> None:
    """Restore the session slot authlib expects, using values from our signed
    token. authlib's `authorize_access_token()` reads
    `session["_state_<provider>_<received_state>"]` to recover `redirect_uri`
    and (for OIDC) `nonce`. The `received_state` is the full signed token the
    provider echoed back in the query string.
    """
    key = f"_state_{provider}_{received_state}"
    data = {
        "redirect_uri": payload.get("r"),
    }
    if payload.get("n"):
        data["nonce"] = payload["n"]
    session[key] = {
        "data": data,
        "exp": time.time() + _OAUTH_STATE_MAX_AGE,
    }


def init_oauth(app):
    """Call from create_app() to bind OAuth to the Flask app."""
    oauth.init_app(app)

    # Google OAuth
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    # Kakao OAuth
    kakao_client_id = os.environ.get("KAKAO_CLIENT_ID")
    if kakao_client_id:
        oauth.register(
            name="kakao",
            client_id=kakao_client_id,
            client_secret=os.environ.get("KAKAO_CLIENT_SECRET", ""),
            authorize_url="https://kauth.kakao.com/oauth/authorize",
            access_token_url="https://kauth.kakao.com/oauth/token",
            api_base_url="https://kapi.kakao.com/",
            client_kwargs={"scope": "profile_nickname profile_image account_email"},
            token_endpoint_auth_method="client_secret_post",
        )


@auth_bp.route("/register", methods=["POST"])
@auth_rate_limit
def register():
    # 2026-05-15 (bug-hunter Wave 7 CRITICAL #2): the register endpoint
    # had NO check for an already-authenticated caller. An attacker
    # could send POST /api/auth/register with a valid CSRF token from
    # any logged-in session and force-create a new user, then
    # `login_user()` at the bottom would silently REPLACE the session
    # with the new account. Wave 7 reproduced this on production —
    # actual DB row id=21 (korean@example.com) was created from a
    # session originally logged in as id=3. Session-fixation /
    # account-takeover risk class.
    #
    # Fix: short-circuit at the top of the handler. An already-authed
    # user has zero legitimate reason to hit this endpoint — the
    # frontend signup form only fires when /api/auth/me returns
    # `authenticated: false`. The 409 surfaces a stable error code
    # the frontend can pattern-match on.
    if current_user.is_authenticated:
        return jsonify({
            "error": "Already logged in. Sign out first.",
            "error_kr": "이미 로그인되어 있습니다. 먼저 로그아웃해 주세요.",
            "code": "ALREADY_AUTHENTICATED",
        }), 409

    d = request.get_json() or {}
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    name = (d.get("name") or "").strip()
    # H1 fix (2026-05-09 release-prep): RFC 5322 simplified email regex.
    import re as _re
    _EMAIL_RE = _re.compile(r"^[^\s@]{1,64}@[^\s@]+\.[^\s@]{2,}$")
    if not email or not pw:
        return jsonify({"error": "Email and password required"}), 400
    if len(email) > 254 or not _EMAIL_RE.match(email):
        return jsonify({"error": "Invalid email format"}), 400
    # H2 fix (2026-05-09 release-prep): bumped from ≥6 to ≥8 (NIST 800-63B).
    if len(pw) < 8:
        return jsonify({"error": "Password must be ≥ 8 characters"}), 400
    # PIPA §22 ⑥ — server-side under-14 gate. The frontend (signup _v1/_v2)
    # already fail-fasts client-side, but a direct curl POST bypasses that.
    # Audit W1.4 P0 finding: the client check was the *only* gate. Every
    # error here returns a stable i18n code matching
    # ``frontend/src/lib/age-verification.ts``.
    try:
        age_result = check_birthdate_payload(d.get("birthdate"))
    except BirthdateValidationError as exc:
        # ``code`` is the stable machine-readable key; frontend matches on it.
        return jsonify({"error": exc.code}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    u = User(
        email=email,
        name=name or email.split("@")[0],
        birthdate=age_result.birthdate,
    )
    u.set_pw(pw)
    db.session.add(u)
    db.session.commit()
    session.clear()  # Session fixation 방어
    login_user(u, remember=True)
    return jsonify({"ok": True, "user": serialize_user(u)})


@auth_bp.route("/login", methods=["POST"])
@auth_rate_limit
def login():
    d = request.get_json() or {}
    u = User.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.chk_pw(d.get("password") or ""):
        return jsonify({"error": "Invalid email or password"}), 401
    session.clear()  # Session fixation 방어
    login_user(u, remember=True)
    return jsonify({"ok": True, "user": serialize_user(u)})


# ── Logout ───────────────────────────────────────────────────────────────────
#
# Design notes (2026-04-23):
#   - Idempotent: calling logout when already logged out returns 200, not 401.
#     Rationale — HttpOnly session cookies can't be cleared client-side, so a
#     401 response would leave the user permanently stuck if their session is
#     somehow partially invalid. The correct response is always "you are now
#     logged out" with all auth cookies cleared.
#   - CSRF exempt (see security.py `_CSRF_EXEMPT_PREFIXES`). We compensate with
#     Origin / Referer verification below so a cross-origin attacker page
#     cannot force logout via a hidden <form> POST.
#   - Cookie cleanup: Flask-Login's `logout_user()` clears the session dict,
#     but we additionally delete `session`, `remember_token`, and `csrf_token`
#     cookies on the response so the browser doesn't keep stale credentials.

# Origin allowlist for logout POSTs. Same set as OAuth redirect whitelist —
# if you're not one of these origins you have no business calling our logout.
# Railway hostname is read from RAILWAY_BACKEND_URL env (set in Railway env);
# falls back to RAILWAY_PUBLIC_DOMAIN (Railway-injected) when present.
_RAILWAY_ORIGIN = (
    os.environ.get("RAILWAY_BACKEND_URL", "").rstrip("/")
    or (
        f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
        if os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        else ""
    )
)
_LOGOUT_ALLOWED_ORIGINS = frozenset(
    {
        "https://pivoxquant.vercel.app",
        "https://pivoxquant.com",
        "https://www.pivoxquant.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Same-origin (Railway direct) — used by curl/tests and the production
        # backend when served without the Vercel edge.
        "http://localhost:5050",
        "http://127.0.0.1:5050",
    }
    | ({_RAILWAY_ORIGIN} if _RAILWAY_ORIGIN else set())
)


def _logout_origin_ok() -> bool:
    """Accept the POST if Origin (or Referer, fallback) is in the allowlist,
    OR if neither header is present (curl, server-to-server, mobile app).
    The missing-header case is safe because a hostile browser page can't
    suppress Origin/Referer on a cross-origin form submit.
    """
    origin = request.headers.get("Origin")
    if origin:
        return origin.rstrip("/") in _LOGOUT_ALLOWED_ORIGINS

    referer = request.headers.get("Referer")
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            candidate = f"{parsed.scheme}://{parsed.netloc}"
            return candidate in _LOGOUT_ALLOWED_ORIGINS
        return False

    # No Origin and no Referer — likely a direct tool (curl, tests, mobile).
    # Browsers always send at least one on cross-origin POSTs, so "absent"
    # is a strong negative signal for CSRF.
    return True


def _clear_auth_cookies(response):
    """Expire every cookie the auth stack may have set.

    2026-05-15 (bug-hunter Wave 7 CRITICAL #1): the previous
    ``response.delete_cookie(name, path="/", domain=cookie_domain)``
    call did NOT pass the original cookie's ``secure``, ``httponly``,
    or ``samesite`` attributes. Some browser cookie policies (notably
    Safari + Firefox in strict mode + cross-origin requests) require
    the SET-Cookie deletion header to mirror the original cookie's
    attributes EXACTLY, otherwise the deletion is silently ignored.
    Wave 7 reproduced this on production: POST /api/auth/logout
    returned 200 + ``was_authenticated: true``, but GET /api/auth/me
    immediately after still returned ``authenticated: true`` —
    cookies hadn't actually been removed by the browser.
    Account-takeover / session-persistence-after-logout risk class.

    Fix: use ``set_cookie('', max_age=0, expires=0)`` with ALL the
    original attributes (Secure / HttpOnly / SameSite / Domain /
    Path) so the deletion mirrors the original Set-Cookie shape
    byte-for-byte. Browsers reliably honor it under all major
    browser cookie policies.
    """
    cookie_domain = current_app.config.get("SESSION_COOKIE_DOMAIN")
    # Flask's session cookie name (defaults to "session")
    session_cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "session")
    # Mirror the SET attributes from security.py:280-287:
    is_secure = bool(current_app.config.get("SESSION_COOKIE_SECURE", False))
    samesite = current_app.config.get("SESSION_COOKIE_SAMESITE") or "Lax"
    # HttpOnly is True for all three auth cookies we manage.
    for name in (session_cookie_name, "remember_token", "csrf_token"):
        response.set_cookie(
            name,
            value="",
            max_age=0,
            expires=0,
            path="/",
            domain=cookie_domain,
            secure=is_secure,
            httponly=True,
            samesite=samesite,
        )
    return response


def _do_logout_response():
    """Shared handler for both `/api/auth/logout` and the `/api/logout` alias."""
    if not _logout_origin_ok():
        logger.warning(
            "Logout rejected: disallowed origin=%r referer=%r",
            request.headers.get("Origin"),
            request.headers.get("Referer"),
        )
        return jsonify({
            "error": "Logout blocked: untrusted origin.",
            "error_kr": "신뢰되지 않은 출처에서의 로그아웃 요청입니다.",
            "code": "UNTRUSTED_ORIGIN",
        }), 403

    was_authenticated = bool(getattr(current_user, "is_authenticated", False))
    try:
        logout_user()
    except Exception:
        # Never let a Flask-Login edge-case (e.g. stale user_loader) 500 the
        # logout path. We still clear the session + cookies below.
        logger.exception("Logout: logout_user() raised; continuing with session clear")

    session.clear()
    response = jsonify({"ok": True, "was_authenticated": was_authenticated})
    return _clear_auth_cookies(response), 200


@auth_bp.route("/logout", methods=["POST"])
@general_rate_limit
def do_logout():
    """POST /api/auth/logout — primary logout endpoint.

    Idempotent: always 200 OK with `{ok: true}` once origin check passes.
    """
    return _do_logout_response()


@auth_alias_bp.route("/api/logout", methods=["POST"])
@general_rate_limit
def do_logout_alias():
    """POST /api/logout — shorter alias for the canonical /api/auth/logout.

    Kept for clients that don't know the /api/auth prefix (user-tester probe,
    legacy mobile). Behaviour is identical.
    """
    return _do_logout_response()


@auth_bp.route("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": serialize_user(current_user)})


# ── Google OAuth ─────────────────────────────────────────────────────────────

@auth_bp.route("/google")
def google_login():
    """Redirect user to Google's OAuth consent screen.

    Uses a stateless HMAC-signed state token so the callback does not
    depend on session cookies surviving the Vercel → Railway round-trip.
    """
    origin = _resolve_frontend_url()
    redirect_uri = f"{origin}/api/auth/google/callback"
    signed_state = _build_signed_state("google", origin, redirect_uri)
    # Extract the nonce from the signed payload so we pass the exact same
    # value to Google that our callback will later verify against.
    nonce = _state_serializer().loads(signed_state, max_age=_OAUTH_STATE_MAX_AGE)["n"]
    logger.info(
        "OAuth start: provider=google origin=%s redirect_uri=%s",
        origin, redirect_uri,
    )
    # authlib will also write a session slot under _state_google_<signed_state>;
    # that slot is redundant (we rehydrate it on callback) but harmless.
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce, state=signed_state)


@auth_bp.route("/google/callback")
def google_callback():
    """Handle the OAuth callback from Google.

    Verifies our HMAC-signed state (stateless — no session cookie required),
    rehydrates the authlib session slot in-process, then lets authlib
    exchange the code for a token normally.
    """
    received_state = request.args.get("state")
    payload = _verify_signed_state(received_state, expected_provider="google")
    if not payload:
        # Fallback origin for the error redirect only.
        origin = _resolve_frontend_url()
        logger.info("OAuth callback: provider=google origin=%s state_ok=False", origin)
        return redirect(f"{origin}/login?error=state_mismatch")

    origin = payload.get("o") or _resolve_frontend_url()
    _rehydrate_authlib_state("google", received_state, payload)
    logger.info("OAuth callback: provider=google origin=%s state_ok=True", origin)

    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        logger.exception("Google callback error")
        return redirect(f"{origin}/login?error=google_failed")
    userinfo = token.get("userinfo")
    if not userinfo:
        return redirect(f"{origin}/login?error=google_failed")

    try:
        google_id = userinfo.get("sub")
        email = (userinfo.get("email") or "").strip().lower()
        if not google_id or not email:
            return redirect(f"{origin}/login?error=google_failed")
        name = userinfo.get("name") or email.split("@")[0]
        avatar = userinfo.get("picture")

        # Find existing user by google_id or email
        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User.query.filter_by(email=email).first()
            if user:
                # Link existing email account with Google
                user.google_id = google_id
                if not user.oauth_provider:
                    user.oauth_provider = "google"
                if avatar and not user.avatar_url:
                    user.avatar_url = avatar
            else:
                # Create new Google user. ``birthdate`` is left NULL — the
                # frontend interstitial (``/signup/oauth-finalize``) will
                # POST to ``/api/auth/oauth-finalize`` to fill it before
                # the user can reach any other authenticated route.
                # PIPA §22 ⑥: under-14 still fail-fasts there.
                user = User(
                    email=email,
                    name=name,
                    google_id=google_id,
                    oauth_provider="google",
                    avatar_url=avatar,
                )
                db.session.add(user)
            db.session.commit()

        session.clear()  # Session fixation 방어
        login_user(user, remember=True)
    except Exception as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)[:200]
        logger.exception(
            "Google OAuth user-provisioning error (userinfo_keys=%s exc_type=%s msg=%s)",
            list(userinfo.keys()) if isinstance(userinfo, dict) else "n/a",
            exc_type, exc_msg,
        )
        try:
            db.session.rollback()
        except Exception:
            logger.debug("silent-fallback: google_callback", exc_info=True)
            pass
        # Generic error code only — exc_type/exc_msg already logged above.
        # Including them in the redirect URL leaks DB schema / ORM internals
        # to the client (browser URL bar, history, Referer header).
        return redirect(f"{origin}/login?error=provisioning_failed")

    # PIPA §22 ⑥ — birthdate gate. New users *and* legacy users (created
    # before migration 031) reach here with ``birthdate IS NULL`` and must
    # complete the interstitial before any other authenticated route. The
    # frontend ``/signup/oauth-finalize`` page POSTs back to
    # ``/api/auth/oauth-finalize`` once the user enters a valid birthdate.
    if user.birthdate is None:
        next_param = request.args.get("next")
        finalize = "/signup/oauth-finalize"
        if next_param:
            from urllib.parse import quote
            finalize = f"{finalize}?next={quote(_safe_next(next_param), safe='/')}"
        logger.info(
            "Google OAuth: birthdate missing → interstitial (user_id=%s)",
            user.id,
        )
        return redirect(f"{origin}{finalize}")

    # Validate redirect destination — must be relative path, no open redirect
    redirect_url = _safe_next(request.args.get("next"))
    logger.info("Google OAuth success: origin=%s path=%s", origin, redirect_url)
    return redirect(f"{origin}{redirect_url}")


# ── Kakao OAuth ─────────────────────────────────────────────────────────────

@auth_bp.route("/kakao")
def kakao_login():
    """Redirect user to Kakao's OAuth consent screen.

    Uses a stateless HMAC-signed state token (see google_login for rationale).
    """
    origin = _resolve_frontend_url()
    if not os.environ.get("KAKAO_CLIENT_ID"):
        return redirect(f"{origin}/login?error=kakao_not_configured")
    redirect_uri = f"{origin}/api/auth/kakao/callback"
    signed_state = _build_signed_state("kakao", origin, redirect_uri)
    logger.info(
        "OAuth start: provider=kakao origin=%s redirect_uri=%s",
        origin, redirect_uri,
    )
    return oauth.kakao.authorize_redirect(redirect_uri, state=signed_state)


@auth_bp.route("/kakao/callback")
def kakao_callback():
    """Handle the OAuth callback from Kakao.

    Stateless state verification — see google_callback for rationale.
    """
    received_state = request.args.get("state")
    payload = _verify_signed_state(received_state, expected_provider="kakao")
    if not payload:
        origin = _resolve_frontend_url()
        logger.info("OAuth callback: provider=kakao origin=%s state_ok=False", origin)
        return redirect(f"{origin}/login?error=state_mismatch")

    origin = payload.get("o") or _resolve_frontend_url()
    _rehydrate_authlib_state("kakao", received_state, payload)
    logger.info("OAuth callback: provider=kakao origin=%s state_ok=True", origin)

    try:
        oauth.kakao.authorize_access_token()
    except Exception:
        logger.exception("Kakao callback error")
        return redirect(f"{origin}/login?error=kakao_failed")

    # Fetch user profile from Kakao
    try:
        resp = oauth.kakao.get("v2/user/me")
        resp.raise_for_status()
        profile = resp.json()
    except Exception:
        logger.exception("Kakao profile fetch error")
        return redirect(f"{origin}/login?error=kakao_failed")

    try:
        kakao_id = str(profile.get("id", ""))
        if not kakao_id:
            return redirect(f"{origin}/login?error=kakao_failed")

        kakao_account = profile.get("kakao_account") or {}
        kakao_profile = kakao_account.get("profile") or {}

        email = (kakao_account.get("email") or "").strip().lower()
        name = kakao_profile.get("nickname") or ""
        avatar = kakao_profile.get("profile_image_url")

        # If Kakao didn't provide an email, generate a placeholder
        if not email:
            email = f"kakao_{kakao_id}@kakao.local"

        # Find existing user by kakao_id or email
        user = User.query.filter_by(kakao_id=kakao_id).first()
        if not user:
            user = User.query.filter_by(email=email).first()
            if user:
                # Link existing account with Kakao
                user.kakao_id = kakao_id
                if not user.oauth_provider:
                    user.oauth_provider = "kakao"
                if avatar and not user.avatar_url:
                    user.avatar_url = avatar
            else:
                # Create new Kakao user
                user = User(
                    email=email,
                    name=name or email.split("@")[0],
                    kakao_id=kakao_id,
                    oauth_provider="kakao",
                    avatar_url=avatar,
                )
                db.session.add(user)
            db.session.commit()

        session.clear()  # Session fixation 방어
        login_user(user, remember=True)
    except Exception as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)[:200]
        logger.exception(
            "Kakao OAuth user-provisioning error (profile_keys=%s exc_type=%s msg=%s)",
            list(profile.keys()) if isinstance(profile, dict) else "n/a",
            exc_type, exc_msg,
        )
        try:
            db.session.rollback()
        except Exception:
            logger.debug("silent-fallback: kakao_callback", exc_info=True)
            pass
        # Generic error code only — exc_type/exc_msg already logged above.
        # Including them in the redirect URL leaks DB schema / ORM internals
        # to the client (browser URL bar, history, Referer header).
        return redirect(f"{origin}/login?error=provisioning_failed")

    # PIPA §22 ⑥ — birthdate gate (mirrors google_callback).
    if user.birthdate is None:
        next_param = request.args.get("next")
        finalize = "/signup/oauth-finalize"
        if next_param:
            from urllib.parse import quote
            finalize = f"{finalize}?next={quote(_safe_next(next_param), safe='/')}"
        logger.info(
            "Kakao OAuth: birthdate missing → interstitial (user_id=%s)",
            user.id,
        )
        return redirect(f"{origin}{finalize}")

    # Validate redirect destination — must be relative path, no open redirect
    redirect_url = _safe_next(request.args.get("next"))
    logger.info("Kakao OAuth success: origin=%s path=%s", origin, redirect_url)
    return redirect(f"{origin}{redirect_url}")


# ── OAuth signup finalization (PIPA §22 ⑥ birthdate interstitial) ────────────

@auth_bp.route("/oauth-finalize", methods=["POST"])
@auth_rate_limit
@api_auth
def oauth_finalize():
    """Capture birthdate for an OAuth user who hasn't supplied one yet.

    Reached by the frontend ``/signup/oauth-finalize`` interstitial after
    the OAuth callback redirected the user there because
    ``user.birthdate IS NULL`` (new sign-up *or* legacy account from
    before migration 031).

    Idempotent — overwriting an already-set ``birthdate`` is rejected so
    a user can't lower their stored age via repeated POSTs. Re-running
    with the same value is a no-op success (200).
    """
    if not current_user.is_authenticated:
        # ``@api_auth`` already gates this, but double-check explicitly so
        # the contract is obvious to anyone reading the route.
        return jsonify({"error": "unauthenticated"}), 401

    d = request.get_json() or {}
    try:
        age_result = check_birthdate_payload(d.get("birthdate"))
    except BirthdateValidationError as exc:
        return jsonify({"error": exc.code}), 400

    user = current_user
    if user.birthdate is not None and user.birthdate != age_result.birthdate:
        # Already set to a *different* value — refuse rather than silently
        # overwrite. PIPA audit trail requirement.
        return jsonify({"error": "birthdate_already_set"}), 409

    if user.birthdate is None:
        user.birthdate = age_result.birthdate
        db.session.commit()
        logger.info(
            "OAuth finalize: birthdate set (user_id=%s provider=%s)",
            user.id, user.oauth_provider,
        )

    return jsonify({"ok": True, "user": serialize_user(user)})


# ── Account Deletion (PIPA compliance) ─────────────────────────────────────

@auth_bp.route("/delete-account", methods=["DELETE"])
@api_auth
@general_rate_limit
def delete_account():
    """Delete user account and all associated data. Required by Korean PIPA."""
    user_id = current_user.id

    try:
        # Delete all user data in dependency-safe order.
        #
        # Why explicit per-model deletes (vs relying on FK CASCADE)
        # ---------------------------------------------------------
        # The Artifact / UserReferral FKs declare ``ondelete="CASCADE"`` and
        # PostgreSQL (prod) will honour them. SQLite (dev) honours them only
        # when ``PRAGMA foreign_keys=ON`` is set — which is now the case via
        # ``extensions._enable_sqlite_fk`` — but explicit deletes give us
        # belt-and-suspenders coverage and remain safe under both backends.
        #
        # IMPORTANT: ``user_agent_audit`` is intentionally NOT deleted here.
        # Audit/decision-trace records have a separate retention obligation
        # (legal review pending) and must outlive the user row. Tracked
        # separately as P1 #14.
        Position.query.filter_by(user_id=user_id).delete()
        TradeHistory.query.filter_by(user_id=user_id).delete()
        Alert.query.filter_by(user_id=user_id).delete()
        Watchlist.query.filter_by(user_id=user_id).delete()
        # SignalCache is a global cache keyed by ticker only (no user_id column).
        # Skipping per-user cleanup; entries are shared and TTL-managed.
        InvestmentProfile.query.filter_by(user_id=user_id).delete()
        BrokerConnection.query.filter_by(user_id=user_id).delete()
        PushSubscription.query.filter_by(user_id=user_id).delete()
        PortfolioShare.query.filter_by(user_id=user_id).delete()

        # P0 + P1 (2026-05-03) — explicit deletion of user-owned rows whose
        # FKs were previously not enforced on SQLite and/or whose models
        # were never wired into delete_account.
        Artifact.query.filter_by(user_id=user_id).delete()
        UserReferral.query.filter_by(user_id=user_id).delete()
        ArtifactFeedback.query.filter_by(user_id=user_id).delete()
        BehavioralScore.query.filter_by(user_id=user_id).delete()
        AITwinPortfolio.query.filter_by(user_id=user_id).delete()
        AITwinWeeklyReport.query.filter_by(user_id=user_id).delete()
        PreTradeReflection.query.filter_by(user_id=user_id).delete()
        PersonaSnapshot.query.filter_by(user_id=user_id).delete()
        WeeklyPulse.query.filter_by(user_id=user_id).delete()

        # Delete user record
        db.session.delete(current_user)
        db.session.commit()

        # Logout
        logout_user()

        return jsonify({"ok": True, "message": "Account and all data deleted."})
    except Exception:
        db.session.rollback()
        logger.exception("Account deletion failed for user_id=%s", user_id)
        return jsonify({"error": "An internal error occurred. Please try again."}), 500
