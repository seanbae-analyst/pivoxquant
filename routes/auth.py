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
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError


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
    AuthEvent,
)
from security import auth_rate_limit, general_rate_limit
from services.age_verification import (
    BirthdateValidationError,
    check_birthdate_payload,
)
from services.error_responses import api_error
from services.serializers import serialize_user
from .decorators import api_auth

logger = logging.getLogger(__name__)


def _schedule_onboarding_safe(user) -> None:
    """Fire-and-forget D+0/D+3/D+7 onboarding sequence enqueue.

    Wave G S5. Called at every signup completion point (password
    ``/register`` final commit, OAuth-finalize birthdate commit, plus
    the brand-new-OAuth-user inline branch). Never raises — a failure
    to enqueue must never break signup. Feature flag
    (``PIVOX_ONBOARDING_SEQUENCE_ENABLED``) short-circuit lives inside
    ``schedule_onboarding`` so this wrapper is the same cost in both
    modes.

    Commit semantics: ``schedule_onboarding`` only ``add`` + ``flush``,
    so the rows ride the caller's existing commit. If the caller
    already committed (signup happy path), we issue a separate commit
    here so the rows actually persist.

    Also runs the Wave G C-R1 retention enqueue path (D+7 / D+30,
    MARKETING) on the same fire-and-forget contract.
    """
    try:
        from extensions import db
        from services.email.onboarding_sequence import schedule_onboarding
        stats = schedule_onboarding(user)
        if stats.get("enqueued", 0) > 0:
            db.session.commit()
        logger.info(
            "onboarding sequence enqueued for user_id=%s stats=%s",
            getattr(user, "id", "?"), stats,
        )
    except Exception:
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass
        logger.exception(
            "onboarding sequence enqueue failed (non-fatal) for user_id=%s",
            getattr(user, "id", "?"),
        )

    # Wave G C-R1 — retention sequence is independent: own feature flag
    # (PIVOX_RETENTION_ENABLED), own consent gate (marketing_consent_marketing),
    # own queue rows. Run separately so an onboarding enqueue failure does
    # not suppress retention (and vice-versa).
    _schedule_retention_safe(user)


def _schedule_retention_safe(user) -> None:
    """Fire-and-forget D+7/D+30 retention enqueue (Wave G C-R1).

    MARKETING category — schedules only when:
      * ``PIVOX_RETENTION_ENABLED=true`` (default false), AND
      * ``user.marketing_consent_marketing_at`` is set + not revoked.

    Never raises. Both predicates live inside ``schedule_retention`` so
    this wrapper is symmetric with the onboarding helper.
    """
    try:
        from extensions import db
        from services.email.retention_sequence import schedule_retention
        stats = schedule_retention(user)
        if stats.get("enqueued", 0) > 0:
            db.session.commit()
        logger.info(
            "retention sequence enqueued for user_id=%s stats=%s",
            getattr(user, "id", "?"), stats,
        )
    except Exception:
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass
        logger.exception(
            "retention sequence enqueue failed (non-fatal) for user_id=%s",
            getattr(user, "id", "?"),
        )


def _log_auth_event(
    email: str | None,
    provider: str,
    event_type: str,
    fail_reason: str | None = None,
) -> None:
    """Append an OAuth lifecycle event row. Never raises.

    Wave I C-1. Powers ``scripts/nightly/oauth_failure_check.py`` which
    runs every 15min, groups ``event_type='fail'`` rows by email over a
    rolling 1h window, and Slack-alerts (+ emails the user) when the
    count reaches 3.

    Email is lowercased + length-trimmed to 255 (RFC 5321) so a
    malformed callback can't poison the table. We accept ``None`` so
    pre-callback failures (state mismatch with no userinfo yet) still
    record a row keyed on the empty string — ops still wants the count.

    Commit semantics
    ----------------
    Uses an *isolated* commit on a nested savepoint where possible so
    logging doesn't pollute the caller's transaction. On any exception
    we rollback and swallow — auth flow must never break because the
    event log is having a bad day.
    """
    try:
        norm_email = ((email or "").strip().lower())[:255]
        norm_provider = provider if provider in ("google", "kakao") else "google"
        norm_event = event_type if event_type in ("start", "success", "fail") else "fail"
        norm_reason = (fail_reason or None)
        if norm_reason and len(norm_reason) > 64:
            norm_reason = norm_reason[:64]

        ev = AuthEvent(
            email=norm_email or "<unknown>",
            provider=norm_provider,
            event_type=norm_event,
            fail_reason=norm_reason,
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception(
            "auth_event log failed (non-fatal) provider=%s event=%s",
            provider, event_type,
        )


# Backoff schedule (seconds) for transient-DB retries during OAuth
# user-provisioning. Length defines the number of *extra* attempts after the
# first try (here: 2 retries → 3 total attempts). Kept short so a worker is
# never tied up longer than ~0.7s on a flapping connection.
_PROVISION_RETRY_BACKOFFS = (0.2, 0.5)


def _is_transient_db_error(exc: Exception) -> bool:
    """True iff ``exc`` is a connection-level fault worth retrying.

    Railway PG flaps at the *connection* layer (refused / dropped sockets),
    surfacing as ``OperationalError`` or, for some psycopg2 disconnect
    classes, a ``DBAPIError`` whose ``connection_invalidated`` flag is set.
    Deterministic failures (``IntegrityError`` — duplicate email/oauth_id,
    ``ProgrammingError`` — missing column) are *not* transient: retrying
    them just burns time and re-raises the same error, so they fall through
    to the caller's existing provisioning_failed path immediately.
    """
    if isinstance(exc, OperationalError):
        return True
    # SQLAlchemy sets connection_invalidated=True when the DBAPI reported a
    # disconnect (pool will hand out a fresh connection on the next checkout,
    # which pool_pre_ping then validates). IntegrityError/ProgrammingError are
    # DBAPIError subclasses too, hence the explicit flag check rather than a
    # bare isinstance(exc, DBAPIError).
    if isinstance(exc, DBAPIError) and getattr(exc, "connection_invalidated", False):
        return True
    return False


def _provision_oauth_user(provider: str, build_user_fn):
    """Run an OAuth find-or-create + commit with transient-DB retries.

    ``build_user_fn`` is a zero-arg callable that performs the provider's
    find-or-create logic (the SELECTs + INSERT/attribute mutation, *without*
    committing) and returns the resolved ``User`` instance. This function
    wraps it so Google and Kakao share one retry policy (철저한 수정 —
    한쪽만 고치지 말 것).

    Retry policy
    ------------
    * Up to ``len(_PROVISION_RETRY_BACKOFFS) + 1`` total attempts.
    * Only ``_is_transient_db_error`` faults are retried. Before each retry we
      ``db.session.rollback()`` to discard the poisoned session — combined
      with ``pool_pre_ping=True`` this means the next attempt checks out a
      freshly validated connection, which clears a momentary flap.
    * Non-transient exceptions (IntegrityError etc.) and exhausted retries
      re-raise to the caller, preserving the existing rollback +
      provisioning_failed redirect behaviour.

    Logs attempt counts and final outcome but never the exception detail in a
    form that could reach the redirect URL (caller policy: generic error code
    only — exc detail is logged server-side, never leaked to the client).
    """
    last_exc: Exception | None = None
    total_attempts = len(_PROVISION_RETRY_BACKOFFS) + 1
    for attempt in range(total_attempts):
        try:
            user = build_user_fn()
            db.session.commit()
            if attempt > 0:
                logger.info(
                    "OAuth provisioning recovered after retry "
                    "(provider=%s attempt=%d/%d)",
                    provider, attempt + 1, total_attempts,
                )
            return user
        except Exception as exc:  # noqa: BLE001 — classified below
            last_exc = exc
            # Always clear the (possibly poisoned) session before deciding.
            try:
                db.session.rollback()
            except Exception:
                logger.debug(
                    "silent-fallback: provision rollback (%s)", provider,
                    exc_info=True,
                )
            transient = _is_transient_db_error(exc)
            is_last = attempt >= total_attempts - 1
            if not transient or is_last:
                if transient and is_last:
                    logger.warning(
                        "OAuth provisioning exhausted retries on transient DB "
                        "error (provider=%s attempts=%d type=%s)",
                        provider, total_attempts, type(exc).__name__,
                    )
                # Re-raise so the caller's existing except-block runs its
                # rollback + provisioning_failed redirect unchanged.
                raise
            backoff = _PROVISION_RETRY_BACKOFFS[attempt]
            logger.warning(
                "OAuth provisioning transient DB error — retrying "
                "(provider=%s attempt=%d/%d backoff=%.2fs type=%s)",
                provider, attempt + 1, total_attempts, backoff,
                type(exc).__name__,
            )
            time.sleep(backoff)
    # Unreachable (loop either returns or raises) — defensive re-raise.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("provisioning loop exited without result")  # pragma: no cover


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
        return api_error(
            en="Email and password required",
            kr="이메일과 비밀번호를 입력해주세요.",
            code="AUTH_CREDENTIALS_REQUIRED",
            status=400,
        )
    if len(email) > 254 or not _EMAIL_RE.match(email):
        return api_error(
            en="Invalid email format",
            kr="이메일 형식이 올바르지 않습니다.",
            code="AUTH_EMAIL_INVALID",
            status=400,
        )
    # H2 fix (2026-05-09 release-prep): bumped from ≥6 to ≥8 (NIST 800-63B).
    if len(pw) < 8:
        return api_error(
            en="Password must be ≥ 8 characters",
            kr="비밀번호는 8자 이상이어야 합니다.",
            code="AUTH_PASSWORD_TOO_SHORT",
            status=400,
        )
    # PIPA §22 ⑥ — server-side under-14 gate. The frontend (signup _v1/_v2)
    # already fail-fasts client-side, but a direct curl POST bypasses that.
    # Audit W1.4 P0 finding: the client check was the *only* gate. Every
    # error here returns a stable i18n code matching
    # ``frontend/src/lib/age-verification.ts``.
    try:
        age_result = check_birthdate_payload(d.get("birthdate"))
    except BirthdateValidationError as exc:
        # ``code`` is the stable machine-readable key; frontend matches on it.
        return api_error(
            en=exc.code,
            kr="생년월일이 올바르지 않습니다.",
            code=exc.code,
            status=400,
        )
    # 2026-05-17 wave 12 P0: TOCTOU race. The previous "check then add"
    # let two concurrent POSTs with the same email both pass the existence
    # check and both reach commit(); the second raised IntegrityError that
    # bubbled as 500 and left the SQLAlchemy session on that gunicorn
    # worker in a failed state until the next request rolled it back.
    # Closing the race by relying on the DB's UNIQUE(email) constraint —
    # the check below is now best-effort UX (faster 409) and the
    # try/except is the actual gate.
    if User.query.filter_by(email=email).first():
        return api_error(
            en="Email already registered",
            kr="이미 가입된 이메일입니다.",
            code="AUTH_EMAIL_ALREADY_REGISTERED",
            status=409,
        )
    u = User(
        email=email,
        name=name or email.split("@")[0],
        birthdate=age_result.birthdate,
    )
    u.set_pw(pw)
    db.session.add(u)
    try:
        db.session.commit()
    except IntegrityError:
        # Concurrent registration won the race. Roll back the session so
        # subsequent requests on this worker aren't poisoned.
        db.session.rollback()
        return api_error(
            en="Email already registered",
            kr="이미 가입된 이메일입니다.",
            code="AUTH_EMAIL_ALREADY_REGISTERED",
            status=409,
        )
    session.clear()  # Session fixation 방어
    login_user(u, remember=True)
    # Wave G S5 — enqueue D+0/D+3/D+7 onboarding sequence. Fire-and-forget;
    # signup must not fail because of email scheduling.
    _schedule_onboarding_safe(u)
    return jsonify({"ok": True, "user": serialize_user(u)})


@auth_bp.route("/login", methods=["POST"])
@auth_rate_limit
def login():
    d = request.get_json() or {}
    u = User.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.chk_pw(d.get("password") or ""):
        return api_error(
            en="Invalid email or password",
            kr="이메일 또는 비밀번호가 올바르지 않습니다.",
            code="AUTH_INVALID_CREDENTIALS",
            status=401,
        )
    # Wave I C-2 — PIPA §21 soft-delete reject. A user with
    # deletion_requested_at != NULL is in the 30-day grace window and
    # must NOT be able to log in (intent must be preserved or actively
    # cancelled via /delete-cancel). Returning a distinct status code so
    # the frontend can surface "탈퇴 진행 중" instead of "wrong password".
    if u.deletion_requested_at is not None:
        return api_error(
            en="Account pending deletion. Contact support to cancel.",
            kr="탈퇴 요청 진행 중인 계정입니다. 철회는 고객센터로 문의해주세요.",
            code="AUTH_ACCOUNT_PENDING_DELETION",
            status=403,
        )
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
    # Wave I C-1 — start events have no email yet; logged with "<unknown>"
    # so the start/fail correlation can be done downstream by IP / time if
    # ever needed. Hidden behind the same fire-and-forget contract.
    _log_auth_event(email=None, provider="google", event_type="start")
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
        _log_auth_event(None, "google", "fail", "state_mismatch")
        return redirect(f"{origin}/login?error=state_mismatch")

    origin = payload.get("o") or _resolve_frontend_url()
    _rehydrate_authlib_state("google", received_state, payload)
    logger.info("OAuth callback: provider=google origin=%s state_ok=True", origin)

    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        logger.exception("Google callback error")
        _log_auth_event(None, "google", "fail", "google_failed")
        return redirect(f"{origin}/login?error=google_failed")
    userinfo = token.get("userinfo")
    if not userinfo:
        _log_auth_event(None, "google", "fail", "userinfo_missing")
        return redirect(f"{origin}/login?error=google_failed")

    try:
        google_id = userinfo.get("sub")
        email = (userinfo.get("email") or "").strip().lower()
        if not google_id or not email:
            _log_auth_event(email, "google", "fail", "userinfo_missing")
            return redirect(f"{origin}/login?error=google_failed")
        name = userinfo.get("name") or email.split("@")[0]
        avatar = userinfo.get("picture")

        # Find existing user by google_id or email. The find-or-create body
        # is wrapped in _provision_oauth_user so a transient Railway PG flap
        # (OperationalError / disconnect) during the SELECT×2 + INSERT + COMMIT
        # is retried with short backoff + pool_pre_ping reconnect instead of
        # failing the login outright. Returns the existing user untouched when
        # found by google_id (no write needed).
        def _provision_google():
            user = User.query.filter_by(google_id=google_id).first()
            if user:
                return user
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
            return user

        user = _provision_oauth_user("google", _provision_google)

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
        try:
            email_local = locals().get("email")
        except Exception:
            email_local = None
        _log_auth_event(email_local, "google", "fail", "provisioning_failed")
        return redirect(f"{origin}/login?error=provisioning_failed")

    # Wave I C-1 — Successful OAuth login: log it for fail-rate computation.
    # PIPA §21 soft-delete reject: a user with deletion_requested_at != NULL
    # gets logged out (login_user above) and bounced to /login?error=...
    if user.deletion_requested_at is not None:
        logger.info(
            "Google OAuth: user %s has deletion_requested_at set — refusing login",
            user.id,
        )
        try:
            logout_user()
            session.clear()
        except Exception:
            pass
        _log_auth_event(email, "google", "fail", "account_pending_deletion")
        return redirect(f"{origin}/login?error=account_pending_deletion")

    _log_auth_event(email, "google", "success")

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
    _log_auth_event(None, "kakao", "start")
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
        _log_auth_event(None, "kakao", "fail", "state_mismatch")
        return redirect(f"{origin}/login?error=state_mismatch")

    origin = payload.get("o") or _resolve_frontend_url()
    _rehydrate_authlib_state("kakao", received_state, payload)
    logger.info("OAuth callback: provider=kakao origin=%s state_ok=True", origin)

    try:
        oauth.kakao.authorize_access_token()
    except Exception:
        logger.exception("Kakao callback error")
        _log_auth_event(None, "kakao", "fail", "kakao_failed")
        return redirect(f"{origin}/login?error=kakao_failed")

    # Fetch user profile from Kakao
    try:
        resp = oauth.kakao.get("v2/user/me")
        resp.raise_for_status()
        profile = resp.json()
    except Exception:
        logger.exception("Kakao profile fetch error")
        _log_auth_event(None, "kakao", "fail", "profile_fetch_failed")
        return redirect(f"{origin}/login?error=kakao_failed")

    try:
        kakao_id = str(profile.get("id", ""))
        if not kakao_id:
            _log_auth_event(None, "kakao", "fail", "userinfo_missing")
            return redirect(f"{origin}/login?error=kakao_failed")

        kakao_account = profile.get("kakao_account") or {}
        kakao_profile = kakao_account.get("profile") or {}

        email = (kakao_account.get("email") or "").strip().lower()
        name = kakao_profile.get("nickname") or ""
        avatar = kakao_profile.get("profile_image_url")

        # If Kakao didn't provide an email, generate a placeholder
        if not email:
            email = f"kakao_{kakao_id}@kakao.local"

        # Find existing user by kakao_id or email. Wrapped in the shared
        # _provision_oauth_user helper so a transient Railway PG flap during
        # the SELECT×2 + INSERT + COMMIT is retried (mirrors google_callback).
        def _provision_kakao():
            user = User.query.filter_by(kakao_id=kakao_id).first()
            if user:
                return user
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
            return user

        user = _provision_oauth_user("kakao", _provision_kakao)

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
        try:
            email_local = locals().get("email")
        except Exception:
            email_local = None
        _log_auth_event(email_local, "kakao", "fail", "provisioning_failed")
        return redirect(f"{origin}/login?error=provisioning_failed")

    # Wave I C-1 — PIPA §21 soft-delete reject + success log.
    if user.deletion_requested_at is not None:
        logger.info(
            "Kakao OAuth: user %s has deletion_requested_at set — refusing login",
            user.id,
        )
        try:
            logout_user()
            session.clear()
        except Exception:
            pass
        _log_auth_event(email, "kakao", "fail", "account_pending_deletion")
        return redirect(f"{origin}/login?error=account_pending_deletion")

    _log_auth_event(email, "kakao", "success")

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
        return api_error(
            en="unauthenticated",
            kr="로그인이 필요합니다.",
            code="AUTH_UNAUTHENTICATED",
            status=401,
        )

    d = request.get_json() or {}
    try:
        age_result = check_birthdate_payload(d.get("birthdate"))
    except BirthdateValidationError as exc:
        return api_error(
            en=exc.code,
            kr="생년월일이 올바르지 않습니다.",
            code=exc.code,
            status=400,
        )

    user = current_user
    if user.birthdate is not None and user.birthdate != age_result.birthdate:
        # Already set to a *different* value — refuse rather than silently
        # overwrite. PIPA audit trail requirement.
        return api_error(
            en="birthdate_already_set",
            kr="생년월일이 이미 설정되어 있습니다.",
            code="birthdate_already_set",
            status=409,
        )

    if user.birthdate is None:
        user.birthdate = age_result.birthdate
        db.session.commit()
        logger.info(
            "OAuth finalize: birthdate set (user_id=%s provider=%s)",
            user.id, user.oauth_provider,
        )
        # Wave G S5 — OAuth signups don't complete until birthdate
        # lands here (PIPA §22 ⑥ gate). Enqueue D+0/D+3/D+7 sequence
        # only when we actually transition from NULL → set; re-finalize
        # attempts are 409'd above so this branch fires exactly once
        # per OAuth user. Fire-and-forget — never blocks signup.
        _schedule_onboarding_safe(user)

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

        # 2026-05-17 thorough cookie cleanup (Wave 7 PR #409 follow-up):
        # delete_account previously called logout_user() then returned a bare
        # jsonify(). Server-side session was cleared but browser cookies were
        # left in the jar — same regression class PR #409 fixed for /logout.
        # Per Safari/Firefox strict cookie policy, the only way to reliably
        # remove cookies is to mirror the original Set-Cookie attributes in
        # the deletion header. Route both through _clear_auth_cookies for
        # consistency (feedback_thorough_fixes — every termination path must
        # clear cookies, not only canonical /logout).
        logout_user()
        session.clear()
        response = jsonify({"ok": True, "message": "Account and all data deleted."})
        return _clear_auth_cookies(response)
    except Exception:
        db.session.rollback()
        logger.exception("Account deletion failed for user_id=%s", user_id)
        return api_error(
            en="An internal error occurred. Please try again.",
            kr="계정 삭제 중 오류가 발생했습니다. 다시 시도해주세요.",
            code="AUTH_DELETE_ACCOUNT_FAILED",
            status=500,
        )


# ── PIPA §21 30-day soft-delete request (Wave I C-2) ──────────────────────────

@auth_bp.route("/delete-request", methods=["POST"])
@api_auth
@general_rate_limit
def delete_request():
    """PIPA §21 30-day soft-delete request.

    Sets ``users.deletion_requested_at = NOW()`` (idempotent — already-set
    users return 200 with the existing timestamp), logs the user out,
    and sends a TRANSACTIONAL email confirming the 30-day grace period.
    The ``pipa_purge`` cron (03:30 KST daily) hard-deletes rows whose
    ``deletion_requested_at`` is ≥ 30 days old.

    PIPA §21 ① — 회원 탈퇴 시 지체 없이 파기.
    PIPA 시행령 §16 ① — 보관·복구 목적의 30일 grace period 허용.

    Distinct from ``/delete-account`` (immediate hard delete, retained for
    legacy clients / "delete now" intent). The new flow is the *default*
    UX path because §21 audit prefers a documented 30d window over an
    irreversible single click.

    Email is TRANSACTIONAL — bypasses §50 marketing-consent gate per
    EmailSender.send() short-circuit (services/email/sender.py).
    """
    # Capture identity + DB row up front. After ``logout_user()`` the
    # ``current_user`` proxy becomes Anonymous and attribute reads raise.
    user = User.query.get(current_user.id)
    if user is None:
        return api_error(
            en="user not found", kr="계정을 찾을 수 없습니다.",
            code="AUTH_USER_NOT_FOUND", status=404,
        )
    user_id = user.id

    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        already_set = user.deletion_requested_at is not None
        if not already_set:
            user.deletion_requested_at = now
            db.session.commit()
            logger.info(
                "PIPA delete-request: user_id=%s deletion_requested_at=%s",
                user_id, now.isoformat(),
            )

        # Snapshot the timestamp BEFORE logout — we still need it for the
        # response and email after the session is cleared.
        requested_at_snapshot = user.deletion_requested_at

        # Send TRANSACTIONAL confirmation email — bypasses §50 consent gate
        # because account/security mail is exempt. Failure is non-fatal.
        try:
            _send_deletion_request_email(user, scheduled_purge_at=requested_at_snapshot)
        except Exception:
            logger.exception(
                "delete-request confirmation email failed (non-fatal) user_id=%s",
                user_id,
            )

        # Log out + clear cookies — mirrors delete_account so the user is
        # immediately bounced (no session preserved during the grace window).
        logout_user()
        session.clear()
        response = jsonify({
            "ok": True,
            "deletion_requested_at": requested_at_snapshot.isoformat()
                if requested_at_snapshot else None,
            "purge_at": _compute_purge_at(requested_at_snapshot),
            "already_requested": already_set,
        })
        return _clear_auth_cookies(response)
    except Exception:
        db.session.rollback()
        logger.exception("delete-request failed for user_id=%s", user_id)
        return api_error(
            en="An internal error occurred. Please try again.",
            kr="탈퇴 요청 중 오류가 발생했습니다. 다시 시도해주세요.",
            code="AUTH_DELETE_REQUEST_FAILED",
            status=500,
        )


def _compute_purge_at(requested_at):
    """Return ISO-8601 string of (requested_at + 30 days), or None."""
    if requested_at is None:
        return None
    from datetime import timedelta
    return (requested_at + timedelta(days=30)).isoformat()


def _send_deletion_request_email(user, *, scheduled_purge_at) -> bool:
    """Send the 30-day deletion-request confirmation. TRANSACTIONAL.

    PIPA §21 ① requires the controller to inform the subject of the
    purge schedule. We hit that requirement by emailing the confirmed
    timestamp + the 30-day target date.
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory
    from html import escape

    purge_iso = _compute_purge_at(scheduled_purge_at) or ""
    purge_display = purge_iso[:10] if purge_iso else "30일 후"
    user_name = escape((getattr(user, "name", "") or "").strip() or "고객")

    html_body = f"""<!doctype html>
<html lang="ko"><body style="margin:0;padding:24px;background:#F6F3EC;
font-family:'Source Serif 4',Georgia,serif;color:#0A0A0A;">
  <div style="max-width:560px;margin:0 auto;background:#FBFAF6;padding:32px;">
    <p style="margin:0;font-size:11px;letter-spacing:0.28em;
      text-transform:uppercase;color:#B8956A;">PIVOXQUANT &middot; 계정 안내</p>
    <h1 style="margin:16px 0 8px 0;font-size:20px;line-height:1.32;
      font-weight:600;letter-spacing:-0.01em;">
      {user_name}님, 탈퇴 요청을 접수했습니다.
    </h1>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      개인정보보호법 §21 ① 및 시행령 §16 ① 에 따라 30일 grace period 동안
      계정 데이터를 보관합니다. 이 기간이 지나면 모든 데이터가 영구 파기되며,
      파기 완료 시 별도로 안내해드립니다.
    </p>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      예정 파기일: <strong>{escape(purge_display)}</strong>
    </p>
    <p style="margin:24px 0 8px 0;line-height:1.5;color:#5A5A5A;font-size:13px;">
      이 기간 동안에는 로그인이 차단됩니다. 탈퇴를 철회하시려면
      고객센터(support@pivoxquant.com)로 연락해주세요.
    </p>
    <p style="margin:24px 0 0 0;font-size:11px;color:#888;">
      본 메일은 거래 관련(transactional) 정보로 §50 광고성 정보 발신에
      해당하지 않습니다.
    </p>
  </div>
</body></html>"""

    return EmailSender().send(
        user,
        subject="[PivoxQuant] 탈퇴 요청 접수 안내 (PIPA §21)",
        html_body=html_body,
        from_env_var="DELETION_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.TRANSACTIONAL,
    )
