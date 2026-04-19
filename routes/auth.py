"""Auth routes: register, login, logout, me, Google OAuth, Kakao OAuth."""
import logging
import os
import secrets
import time
from urllib.parse import urlparse

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, request, jsonify, redirect, session, url_for, abort, current_app
from flask_login import login_user, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


def _safe_next(next_url):
    """Open redirect 방어: 스킴-relative(//evil.com) + 절대 URL 차단."""
    if not next_url or not isinstance(next_url, str):
        return "/home"
    if next_url.startswith("//") or "://" in next_url:
        return "/home"
    if not next_url.startswith("/"):
        return "/home"
    return next_url

from extensions import db
from models import (
    User, Position, TradeHistory, Alert, Watchlist,
    InvestmentProfile, BrokerConnection, PushSubscription,
    PortfolioShare,
)
from security import auth_rate_limit
from services.serializers import serialize_user
from .decorators import api_auth

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

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

_OAUTH_STATE_MAX_AGE = 600  # seconds (10 minutes)
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
    d = request.get_json() or {}
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    name = (d.get("name") or "").strip()
    if not email or not pw:
        return jsonify({"error": "Email and password required"}), 400
    if len(pw) < 6:
        return jsonify({"error": "Password must be ≥ 6 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409
    u = User(email=email, name=name or email.split("@")[0])
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


@auth_bp.route("/logout", methods=["POST"])
@api_auth
def do_logout():
    logout_user()
    return jsonify({"ok": True})


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
                # Create new Google user
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
    except Exception:
        logger.exception("Google OAuth user-provisioning error (userinfo_keys=%s)", list(userinfo.keys()) if isinstance(userinfo, dict) else "n/a")
        try:
            db.session.rollback()
        except Exception:
            pass
        return redirect(f"{origin}/login?error=google_user_error")

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
        token = oauth.kakao.authorize_access_token()
    except Exception:
        logger.exception("Kakao callback error")
        return redirect(f"{origin}/login?error=kakao_failed")

    # Fetch user profile from Kakao
    try:
        resp = oauth.kakao.get("v2/user/me")
        resp.raise_for_status()
        profile = resp.json()
    except Exception as e:
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
    except Exception:
        logger.exception("Kakao OAuth user-provisioning error (profile_keys=%s)", list(profile.keys()) if isinstance(profile, dict) else "n/a")
        try:
            db.session.rollback()
        except Exception:
            pass
        return redirect(f"{origin}/login?error=kakao_user_error")

    # Validate redirect destination — must be relative path, no open redirect
    redirect_url = _safe_next(request.args.get("next"))
    logger.info("Kakao OAuth success: origin=%s path=%s", origin, redirect_url)
    return redirect(f"{origin}{redirect_url}")


# ── Account Deletion (PIPA compliance) ─────────────────────────────────────

@auth_bp.route("/delete-account", methods=["DELETE"])
@api_auth
def delete_account():
    """Delete user account and all associated data. Required by Korean PIPA."""
    user_id = current_user.id

    try:
        # Delete all user data in dependency-safe order
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

        # Delete user record
        db.session.delete(current_user)
        db.session.commit()

        # Logout
        logout_user()

        return jsonify({"ok": True, "message": "Account and all data deleted."})
    except Exception as e:
        db.session.rollback()
        logger.exception("Account deletion failed for user_id=%s", user_id)
        return jsonify({"error": "An internal error occurred. Please try again."}), 500
