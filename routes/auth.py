"""Auth routes: register, login, logout, me, Google OAuth."""
import os

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, request, jsonify, redirect, session, url_for
from flask_login import login_user, logout_user, current_user

from extensions import db
from models import User
from security import auth_rate_limit
from services.serializers import serialize_user
from .decorators import api_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# ── Google OAuth setup ───────────────────────────────────────────────────────
oauth = OAuth()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def init_oauth(app):
    """Call from create_app() to bind OAuth to the Flask app."""
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
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
    login_user(u, remember=True)
    return jsonify({"ok": True, "user": serialize_user(u)})


@auth_bp.route("/login", methods=["POST"])
@auth_rate_limit
def login():
    d = request.get_json() or {}
    u = User.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.chk_pw(d.get("password") or ""):
        return jsonify({"error": "Invalid email or password"}), 401
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
    redirect_uri = url_for("auth.google_callback", _external=True)
    nonce = generate_token()
    session["oauth_nonce"] = nonce
    return oauth.google.authorize_redirect(redirect_uri, nonce=nonce)


@auth_bp.route("/google/callback")
def google_callback():
    """Handle the OAuth callback from Google."""
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
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
            if avatar and not user.avatar_url:
                user.avatar_url = avatar
        else:
            # Create new Google user
            user = User(
                email=email,
                name=name,
                google_id=google_id,
                avatar_url=avatar,
            )
            db.session.add(user)
        db.session.commit()

    login_user(user, remember=True)
    return redirect(f"{FRONTEND_URL}/home")
