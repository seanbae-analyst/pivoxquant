"""Auth routes: register, login, logout, me, Google OAuth, Kakao OAuth."""
import logging
import os

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, request, jsonify, redirect, session, url_for
from flask_login import login_user, logout_user, current_user

from extensions import db
from models import (
    User, Position, TradeHistory, Alert, Watchlist,
    SignalCache, InvestmentProfile, BrokerConnection, PushSubscription,
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
    """Redirect user to Google's OAuth consent screen."""
    from authlib.common.security import generate_token
    redirect_uri = f"{FRONTEND_URL}/api/auth/google/callback"
    nonce = generate_token()
    session["oauth_nonce"] = nonce
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)


@auth_bp.route("/google/callback")
def google_callback():
    """Handle the OAuth callback from Google."""
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        logger.exception("Google callback error")
        return redirect(f"{FRONTEND_URL}/login?error=google_failed")
    userinfo = token.get("userinfo")
    if not userinfo:
        return redirect(f"{FRONTEND_URL}/login?error=google_failed")

    google_id = userinfo["sub"]
    email = userinfo["email"].strip().lower()
    name = userinfo.get("name", email.split("@")[0])
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

    # Validate redirect destination — must be relative path, no open redirect
    redirect_url = request.args.get("next", "/home")
    if not redirect_url.startswith("/") or "://" in redirect_url:
        redirect_url = "/home"
    return redirect(f"{FRONTEND_URL}{redirect_url}")


# ── Kakao OAuth ─────────────────────────────────────────────────────────────

@auth_bp.route("/kakao")
def kakao_login():
    """Redirect user to Kakao's OAuth consent screen."""
    if not os.environ.get("KAKAO_CLIENT_ID"):
        return redirect(f"{FRONTEND_URL}/login?error=kakao_not_configured")
    redirect_uri = f"{FRONTEND_URL}/api/auth/kakao/callback"
    return oauth.kakao.authorize_redirect(redirect_uri)


@auth_bp.route("/kakao/callback")
def kakao_callback():
    """Handle the OAuth callback from Kakao."""
    try:
        token = oauth.kakao.authorize_access_token()
    except Exception as e:
        logger.exception("Kakao callback error")
        return redirect(f"{FRONTEND_URL}/login?error=kakao_failed")

    # Fetch user profile from Kakao
    try:
        resp = oauth.kakao.get("v2/user/me")
        resp.raise_for_status()
        profile = resp.json()
    except Exception as e:
        logger.exception("Kakao profile fetch error")
        return redirect(f"{FRONTEND_URL}/login?error=kakao_failed")

    kakao_id = str(profile.get("id", ""))
    if not kakao_id:
        return redirect(f"{FRONTEND_URL}/login?error=kakao_failed")

    kakao_account = profile.get("kakao_account", {})
    kakao_profile = kakao_account.get("profile", {})

    email = kakao_account.get("email", "").strip().lower()
    name = kakao_profile.get("nickname", "")
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

    # Validate redirect destination — must be relative path, no open redirect
    redirect_url = request.args.get("next", "/home")
    if not redirect_url.startswith("/") or "://" in redirect_url:
        redirect_url = "/home"
    return redirect(f"{FRONTEND_URL}{redirect_url}")


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
        SignalCache.query.filter_by(user_id=user_id).delete()
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
