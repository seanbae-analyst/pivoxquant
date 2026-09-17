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


# Where a login lands when there is nowhere better to go. This is /mirror,
# not /home: /home was deleted and the frontend answers it with a 308 to
# /mirror, so every single OAuth login was paying a redirect hop to reach the
# screen we could have named. Worse, the function below exists to map dead
# routes onto live ones — its own docstring says so — and its fallback was a
# dead route. The /landing → 404 P0 hotfix of 2026-05-03 was this same class.
_POST_LOGIN_DEFAULT = "/mirror"


def _safe_next(next_url):
    """Open redirect 방어 + 폐기된 경로 차단.

    - 스킴-relative (//evil.com) + 절대 URL 차단
    - 존재하지 않는 Next.js 라우트 (/landing, /beta 등) → 유효 경로로 매핑
    """
    if not next_url or not isinstance(next_url, str):
        return _POST_LOGIN_DEFAULT
    if next_url.startswith("//") or "://" in next_url:
        return _POST_LOGIN_DEFAULT
    if not next_url.startswith("/"):
        return _POST_LOGIN_DEFAULT

    # Path-only 비교용: 쿼리스트링/프래그먼트 제거.
    path_only = next_url.split("?", 1)[0].split("#", 1)[0].rstrip("/")

    # 폐기/존재하지 않는 라우트 매핑.
    # /landing → 홈 (OAuth 콜백 후 404 방지, P0 hotfix 2026-05-03)
    # /beta → / (베타 게이트 2026-09-04 폐기 — 옛 링크만 흡수)
    if path_only in ("/landing", ""):
        return _POST_LOGIN_DEFAULT
    if path_only == "/beta":
        return "/"

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
    PositionDDCheck, Inquiry,
    ScheduledEmail, NpsFeedback,
    AuthEvent,
    CheckoutExpiration, PortfolioNavSnapshot, UserAgentAudit, CompanionWaitlist,
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


class OAuthLinkRefused(Exception):
    """Raised when an OAuth callback is asked to link a *new* provider id onto
    an *existing* account by email collision, but the link is unsafe.

    This guards the account-takeover vector: a provider asserting an email it
    did not verify (or an email that belongs to a password account) must not be
    silently merged into the existing account and logged in. The callback
    catches this and bounces the user to /login?error=oauth_link_refused
    instead of completing the login.

    The two dominant *safe* paths are unaffected:
      1. brand-new user (no existing account)               → create + login
      2. returning user whose google_id/kakao_id matches     → login
    Only the EMAIL-MATCH-but-NEW-provider-id linking branch consults this.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _email_is_provider_verified(provider: str, raw: dict) -> bool:
    """Return whether ``raw`` (provider userinfo / kakao_account) asserts the
    email as *verified*.

    Decision (a): both providers reliably expose a verified flag, so we honour
    it for the linking guard:
      * Google OIDC userinfo includes ``email_verified`` (boolean). Some legacy
        shapes use ``verified_email``.
      * Kakao ``kakao_account`` includes ``is_email_verified`` (boolean).

    Conservative default: treat the email as verified UNLESS the flag is
    explicitly ``False``. An explicit ``False`` is the only reliable signal of
    a spoofable / unverified email and is the documented takeover vector. A
    *missing* key (should not happen for these scopes) defaults to verified so
    a legitimate login is never broken by an unexpected response shape — see
    the module REPORT for rationale.
    """
    if provider == "google":
        flag = raw.get("email_verified")
        if flag is None:
            flag = raw.get("verified_email")
    elif provider == "kakao":
        flag = raw.get("is_email_verified")
    else:  # pragma: no cover — defensive
        flag = None
    # Only an explicit boolean False (or the string "false") blocks linking.
    if flag is False:
        return False
    if isinstance(flag, str) and flag.strip().lower() == "false":
        return False
    return True


def _guard_oauth_email_link(provider: str, existing_user, verified_email: bool):
    """Decide whether linking a NEW provider id onto ``existing_user`` (matched
    by email) is allowed. Raises :class:`OAuthLinkRefused` if not.

    Two refusal conditions (defense-in-depth — Fix 1, decision (a)):
      * the incoming email is NOT provider-verified (``verified_email`` False)
        → a provider is asserting an email it did not verify; refusing closes
          the cross-provider takeover vector.
      * the existing account has a non-null ``password_hash`` → never merge a
        social identity onto a credentialed account. Harmless today (OAuth-only
        app, password_hash ~always NULL) but closes the vector if a password
        login is ever added.

    Returns nothing on success (caller proceeds to link + login).
    """
    if getattr(existing_user, "password_hash", None) is not None:
        raise OAuthLinkRefused("password_account")
    if not verified_email:
        raise OAuthLinkRefused("email_unverified")


def _send_oauth_link_alert(user, *, provider: str) -> bool:
    """Fire a TRANSACTIONAL security-notification email to ``user`` telling the
    real owner that a new login provider (``provider``) was just linked to
    their account. Best-effort: failure is swallowed by the caller.

    PIPA / 정통망법 §50 — security/account mail is transactional and bypasses
    the marketing-consent gate (mirrors ``_send_deletion_request_email``).
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory
    from html import escape

    provider_label = {"google": "Google", "kakao": "Kakao"}.get(provider, provider)
    user_name = escape((getattr(user, "name", "") or "").strip() or "고객")
    safe_provider = escape(provider_label)

    html_body = f"""<!doctype html>
<html lang="ko"><body style="margin:0;padding:24px;background:#F6F3EC;
font-family:'Source Serif 4',Georgia,serif;color:#0A0A0A;">
  <div style="max-width:560px;margin:0 auto;background:#FBFAF6;padding:32px;">
    <p style="margin:0;font-size:11px;letter-spacing:0.28em;
      text-transform:uppercase;color:#B8956A;">PIVOXQUANT &middot; 보안 안내</p>
    <h1 style="margin:16px 0 8px 0;font-size:20px;line-height:1.32;
      font-weight:600;letter-spacing:-0.01em;">
      {user_name}님, 새 로그인 수단이 연결되었습니다.
    </h1>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      회원님의 계정에 <strong>{safe_provider}</strong> 로그인이 연결되었습니다.
      직접 진행하신 것이라면 별도 조치가 필요하지 않습니다.
    </p>
    <p style="margin:12px 0;line-height:1.6;color:#202020;font-size:15px;">
      본인이 하지 않은 경우 즉시 고객센터(support@pivoxquant.com)로
      연락해주세요.
    </p>
    <p style="margin:24px 0 0 0;font-size:11px;color:#888;">
      본 메일은 보안/계정 관련(transactional) 정보로 §50 광고성 정보 발신에
      해당하지 않습니다.
    </p>
  </div>
</body></html>"""

    return EmailSender().send(
        user,
        subject="[PivoxQuant] 새 로그인 수단 연결 안내",
        html_body=html_body,
        from_env_var="SECURITY_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.TRANSACTIONAL,
    )


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


def _record_signup_funnel(user, ref_code: str | None) -> None:
    """Viral loop — log a ``signup`` funnel event + attribute referral.

    Best-effort and fully contained: any failure here must NEVER break the
    OAuth login (the user is already logged in by the time we reach this).
    Attribution itself (``attribute_referral``) is idempotent + immutable and
    logs its own ``referral_signup`` event when a valid inviter is found.
    """
    try:
        from models import FunnelEvent
        from datetime import datetime as _dt, timezone as _tz
        db.session.add(FunnelEvent(
            user_id=int(user.id),
            event="signup",
            channel=getattr(user, "oauth_provider", None),
            ref_code=(str(ref_code).strip()[:16] if ref_code else None),
            created_at=_dt.now(_tz.utc),
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning("signup funnel event failed (user_id=%s)",
                       getattr(user, "id", None), exc_info=True)
    try:
        from routes.growth import attribute_referral
        attribute_referral(user, ref_code)
    except Exception:
        logger.warning("referral attribution failed (user_id=%s)",
                       getattr(user, "id", None), exc_info=True)


def _build_signed_state(provider: str, origin: str, redirect_uri: str,
                        ref_code: str | None = None) -> str:
    """Build a self-contained HMAC-signed state token.

    The full signed string is passed to the OAuth provider as `state=`.
    On the callback the provider echoes it back verbatim; we verify the
    signature, decode the payload, and rehydrate authlib's session slot
    using the signed token itself as the lookup key.

    ``ref_code`` (viral loop) is the inviter's referral code, captured from
    the ``?ref=`` query param at login-start. It rides inside the SIGNED
    state so it can't be tampered with mid-flight, and is consumed once on
    the callback for a brand-new user (``attribute_referral``).
    """
    nonce = secrets.token_urlsafe(16)
    payload = {
        "n": nonce,               # OIDC nonce (Google id_token binding)
        "o": origin,              # frontend origin for final redirect
        "p": provider,            # "google" | "kakao"
        "r": redirect_uri,        # exact redirect_uri used in the request
        "k": secrets.token_urlsafe(8),  # anti-replay nonce for the payload
    }
    if ref_code:
        # Defensive cap — referral codes are 8-char; never carry more than 16.
        payload["ref"] = str(ref_code).strip()[:16]
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

    # 2026-05-25 (security-agent): cross-origin account-precreation / CSRF guard.
    #
    # The CSRF double-submit check in security.py:_csrf_protect() SKIPS
    # unauthenticated callers (`if not current_user.is_authenticated: return`),
    # so a logged-out POST /register has NO CSRF or Origin verification. A
    # hostile page (or off-platform attacker) could pre-create an account with
    # a victim's email + an attacker-chosen password. Because the app is
    # OAuth-only (Google/Kakao; CLAUDE.md "email+password 없음" — the frontend
    # `signup()`/`login()` helpers in lib/auth.tsx are dead, never invoked), the
    # victim's later OAuth login hits _guard_oauth_email_link(), sees a non-null
    # password_hash, raises OAuthLinkRefused("password_account") → the legitimate
    # owner is locked out permanently. Reproduced on prod (2026-05-25): POST
    # /register with `Origin: https://evil.example.com` returned 200.
    #
    # Fix: reuse the existing logout Origin allowlist (`_logout_origin_ok`).
    # A real browser ALWAYS sends Origin/Referer on a cross-origin POST and
    # cannot forge an allowlisted value; the absent-header case (curl, tests,
    # native clients) stays permitted exactly like /logout. This blocks the
    # browser-driven attack without breaking any same-origin flow.
    if not _logout_origin_ok():
        return api_error(
            en="Cross-origin registration is not allowed.",
            kr="허용되지 않은 출처에서의 가입 요청입니다.",
            code="AUTH_ORIGIN_NOT_ALLOWED",
            status=403,
        )

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
    # 2026-05-25 (security-agent): same cross-origin / CSRF guard as /register.
    # Unauthenticated POSTs skip security.py:_csrf_protect(), so without this an
    # attacker page could drive credential-stuffing against /login from a
    # victim's browser. Reuses the logout Origin allowlist (browser cross-origin
    # POSTs always carry Origin/Referer and can't forge an allowlisted value;
    # header-absent curl/tests stay permitted).
    if not _logout_origin_ok():
        return api_error(
            en="Cross-origin login is not allowed.",
            kr="허용되지 않은 출처에서의 로그인 요청입니다.",
            code="AUTH_ORIGIN_NOT_ALLOWED",
            status=403,
        )

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
    # Mirror each cookie's original HttpOnly: session/remember_token are
    # HttpOnly, but csrf_token is set HttpOnly=False (security.py:495 — the SPA
    # reads it via JS). Strict cookie jars match deletion on attributes, so a
    # mismatch could leave csrf_token uncleared on logout in some clients.
    for name in (session_cookie_name, "remember_token", "csrf_token"):
        response.set_cookie(
            name,
            value="",
            max_age=0,
            expires=0,
            path="/",
            domain=cookie_domain,
            secure=is_secure,
            httponly=(name != "csrf_token"),
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
    # Viral loop — capture inviter's referral code from ?ref=, carry it in
    # the signed state so the callback can attribute a brand-new signup.
    ref_code = (request.args.get("ref") or "").strip()[:16] or None
    signed_state = _build_signed_state("google", origin, redirect_uri, ref_code)
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
        email_verified = _email_is_provider_verified("google", userinfo)
        # Fix 1: track when we LINK a new provider id onto an existing account
        # so the owner gets a security email after a successful commit.
        link_alert = {"user": None}
        # Viral loop — flag a brand-new signup so we can attribute referral
        # + log a funnel signup event after the commit succeeds.
        signup_flag = {"new": False}
        # Inviter code rides inside the signed state (verified, untamperable).
        ref_code = payload.get("ref") if isinstance(payload, dict) else None

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
                # Fix 1 — EMAIL-MATCH-but-new-provider-id linking branch.
                # Refuse to silently merge an unverified email or merge onto a
                # credentialed (password) account. Raises OAuthLinkRefused,
                # which the callback maps to a clean /login error (NOT a
                # provisioning_failed DB-retry path).
                _guard_oauth_email_link("google", user, email_verified)
                # Link existing email account with Google
                user.google_id = google_id
                if not user.oauth_provider:
                    user.oauth_provider = "google"
                if avatar and not user.avatar_url:
                    user.avatar_url = avatar
                link_alert["user"] = user
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
                # Viral loop — mint this user's own referral code at signup
                # (mirrored onto users.referral_code; UserReferral side-table
                # is the authoritative store and is allocated lazily later).
                try:
                    from models import generate_referral_code
                    user.referral_code = generate_referral_code()
                except Exception:
                    logger.debug("referral_code mint skipped (google)", exc_info=True)
                db.session.add(user)
                signup_flag["new"] = True
            return user

        user = _provision_oauth_user("google", _provision_google)

        session.clear()  # Session fixation 방어
        login_user(user, remember=True)
    except OAuthLinkRefused as refused:
        # Fix 1 — refused cross-provider/email-collision link. NOT a server
        # error: bounce the user to /login with a clear error code. Session is
        # untouched (login_user never ran); the existing account is unchanged.
        try:
            db.session.rollback()
        except Exception:
            logger.debug("silent-fallback: google link refused rollback", exc_info=True)
        logger.warning(
            "Google OAuth link refused (reason=%s) — not linking/login", refused.reason,
        )
        _log_auth_event(email, "google", "fail", f"link_refused_{refused.reason}")
        return redirect(f"{origin}/login?error=oauth_link_refused")
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

    # Viral loop — brand-new signup: log a signup funnel event + attribute
    # the inviter's referral code (if any). Best-effort, never blocks login.
    if signup_flag.get("new"):
        _record_signup_funnel(user, ref_code)

    # Fix 1 — a new provider id was linked onto an existing account this
    # request. Alert the real owner (best-effort, non-fatal).
    if link_alert.get("user") is not None:
        try:
            _send_oauth_link_alert(link_alert["user"], provider="google")
        except Exception:
            logger.exception(
                "google link-alert email failed (non-fatal) user_id=%s",
                getattr(link_alert.get("user"), "id", None),
            )

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
    ref_code = (request.args.get("ref") or "").strip()[:16] or None
    signed_state = _build_signed_state("kakao", origin, redirect_uri, ref_code)
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

        # Kakao exposes the verified signal inside kakao_account
        # (is_email_verified). Compute BEFORE the placeholder fallback so a
        # real Kakao-asserted email is judged on its own flag.
        email_verified = _email_is_provider_verified("kakao", kakao_account)

        # If Kakao didn't provide an email, generate a placeholder. A
        # placeholder is unique per kakao_id and cannot collide with a real
        # account's email, so it never reaches the link-guard refusal path.
        if not email:
            email = f"kakao_{kakao_id}@kakao.local"

        # Fix 1: track when we LINK a new provider id onto an existing account.
        link_alert = {"user": None}
        # Viral loop — flag brand-new signup + carry verified inviter code.
        signup_flag = {"new": False}
        ref_code = payload.get("ref") if isinstance(payload, dict) else None

        # Find existing user by kakao_id or email. Wrapped in the shared
        # _provision_oauth_user helper so a transient Railway PG flap during
        # the SELECT×2 + INSERT + COMMIT is retried (mirrors google_callback).
        def _provision_kakao():
            user = User.query.filter_by(kakao_id=kakao_id).first()
            if user:
                return user
            user = User.query.filter_by(email=email).first()
            if user:
                # Fix 1 — EMAIL-MATCH-but-new-provider-id linking branch.
                # Same guard as Google: refuse unverified-email or
                # password-account merges. Raises OAuthLinkRefused.
                _guard_oauth_email_link("kakao", user, email_verified)
                # Link existing account with Kakao
                user.kakao_id = kakao_id
                if not user.oauth_provider:
                    user.oauth_provider = "kakao"
                if avatar and not user.avatar_url:
                    user.avatar_url = avatar
                link_alert["user"] = user
            else:
                # Create new Kakao user
                user = User(
                    email=email,
                    name=name or email.split("@")[0],
                    kakao_id=kakao_id,
                    oauth_provider="kakao",
                    avatar_url=avatar,
                )
                try:
                    from models import generate_referral_code
                    user.referral_code = generate_referral_code()
                except Exception:
                    logger.debug("referral_code mint skipped (kakao)", exc_info=True)
                db.session.add(user)
                signup_flag["new"] = True
            return user

        user = _provision_oauth_user("kakao", _provision_kakao)

        session.clear()  # Session fixation 방어
        login_user(user, remember=True)
    except OAuthLinkRefused as refused:
        # Fix 1 — refused cross-provider/email-collision link (mirrors Google).
        try:
            db.session.rollback()
        except Exception:
            logger.debug("silent-fallback: kakao link refused rollback", exc_info=True)
        logger.warning(
            "Kakao OAuth link refused (reason=%s) — not linking/login", refused.reason,
        )
        _log_auth_event(email, "kakao", "fail", f"link_refused_{refused.reason}")
        return redirect(f"{origin}/login?error=oauth_link_refused")
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

    # Viral loop — brand-new signup: funnel signup event + referral attribution.
    if signup_flag.get("new"):
        _record_signup_funnel(user, ref_code)

    # Fix 1 — new provider id linked onto an existing account (best-effort).
    if link_alert.get("user") is not None:
        try:
            _send_oauth_link_alert(link_alert["user"], provider="kakao")
        except Exception:
            logger.exception(
                "kakao link-alert email failed (non-fatal) user_id=%s",
                getattr(link_alert.get("user"), "id", None),
            )

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

# 법정 필수 동의 3종 — 인터스티셜의 제출 게이트와 1:1 로 맞춘다.
#
# 프론트의 필수 항목은 4종(terms / non_advisory / age / cross_border)이지만
# ``age`` 는 생년월일에서 자동 도출되는 파생 체크박스이고, 그 사실은 아래
# ``check_birthdate_payload`` 가 서버에서 다시 검증한다. 그래서 본문으로
# 받아야 하는 것은 나머지 3종이다.
#
#   terms        — 이용약관 + 개인정보처리방침 동의
#   non_advisory — 자본시장법상 투자자문업이 아니라는 고지 확인
#   cross_border — 개인정보 국외 이전 동의 (PIPA §28-8)
_OAUTH_FINALIZE_REQUIRED_CONSENTS = ("terms", "non_advisory", "cross_border")


@auth_bp.route("/oauth-finalize", methods=["POST"])
@auth_rate_limit
@api_auth
def oauth_finalize():
    """Capture birthdate + the mandatory consents for a fresh OAuth user.

    Reached by the frontend ``/signup/oauth-finalize`` interstitial after
    the OAuth callback redirected the user there because
    ``user.birthdate IS NULL`` (new sign-up *or* legacy account from
    before migration 031).

    Request body::

        {
          "birthdate": "yyyy-mm-dd",
          "consents": {
            "terms": true,
            "non_advisory": true,
            "cross_border": true
          }
        }

    All three consents must be literal ``true`` or the request is
    refused with 400 ``consents_required`` and **nothing is written** —
    not the birthdate, not the consent timestamp.

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

    d = request.get_json(silent=True) or {}
    if not isinstance(d, dict):
        return api_error(
            en="invalid_payload",
            kr="요청 형식이 올바르지 않습니다.",
            code="invalid_payload",
            status=400,
        )

    # ── 필수 동의 검증 (생년월일보다 *먼저*) ────────────────────────────
    #
    # 2026-09-17 P1 (보안 감사): 동의 스택이 OAuth **이후** 인터스티셜로
    # 옮겨졌는데(로그인 화면으로 들어온 신규 가입자도 덮으려면 그래야 한다)
    # 서버는 계속 ``{birthdate}`` 만 받았다. 그래서 OAuth 콜백이 세션을 준
    # 직후 체크박스를 하나도 건드리지 않고
    #
    #     curl -b <session> -X POST /api/auth/oauth-finalize \
    #          -d '{"birthdate":"1990-01-01"}'
    #
    # 만 보내면 ``birthdate_required`` 가 false 로 떨어지며 전 기능이 열렸고,
    # ``cross_border_consent_at`` 은 NULL, 약관·비자문 동의 증거는 0 이었다.
    # 클라이언트 게이트는 증거가 아니다 — 서버가 게이트다.
    #
    # 순서가 중요하다: 동의를 먼저 보고 거절하면 birthdate 는 파싱조차 하지
    # 않으므로, 동의 없는 요청은 어떤 컬럼도 건드리지 못한다.
    #
    # ── 하위 호환: ``consents`` 키가 아예 없는 요청은 400 으로 거절한다 ──
    #
    # 판단 근거
    #   1. 통과시키면 고친 것이 아니다. 위 curl 은 ``consents`` 키가 없는
    #      요청이고, "없으면 경고 로깅 + 통과" 로 두면 감사가 제출한 우회
    #      재현 명령이 그대로 성공한다. 로그는 사후 관측이지 게이트가 아니고,
    #      그 사이 가입한 사용자는 동의 증거가 영구히 0 인 채로 남는다.
    #      P1 의 노출 창을 "언젠가 TODO 를 처리할 때까지" 로 열어 두는 셈이다.
    #   2. 거절의 실패 모드는 복구 가능하고 자가 치유된다. 배포 순간 이미
    #      인터스티셜을 열어 둔 구버전 번들만 400 을 받고, 새로고침하면 새
    #      번들을 받아 정상 진행한다. 계정은 half-provisioned 상태 그대로
    #      남으므로(birthdate NULL) 데이터 손상도 없다. 노출 범위는 배포
    #      창에 제출 버튼을 누른 소수이고, 지속 시간은 새로고침 1회다.
    #      통과의 실패 모드는 그 반대다 — 조용하고, 무기한이고, 사후에만
    #      보인다.
    #   3. 배포 순서는 운영으로 해결한다. **프론트(Vercel) 를 먼저 배포하고
    #      백엔드(Render) 를 뒤에 배포하면 창 자체가 생기지 않는다** —
    #      구버전 서버는 ``consents`` 를 무시할 뿐이라 신버전 프론트가
    #      먼저 떠 있어도 아무것도 깨지지 않는다. 순서가 보장되지 않는다는
    #      이유로 컴플라이언스 게이트를 여는 대신, 순서를 보장하는 쪽이
    #      비용이 훨씬 싸다.
    consents = d.get("consents")
    if consents is None:
        logger.warning(
            "OAuth finalize: 'consents' missing → rejected "
            "(user_id=%s provider=%s) — 구버전 번들이면 새로고침 후 재시도",
            getattr(current_user, "id", None),
            getattr(current_user, "oauth_provider", None),
        )
        return api_error(
            en="consents_required",
            kr="필수 동의 항목을 모두 확인해주세요. 화면을 새로고침한 뒤 다시 시도해주세요.",
            code="consents_required",
            status=400,
            missing_consents=list(_OAUTH_FINALIZE_REQUIRED_CONSENTS),
        )

    if not isinstance(consents, dict):
        return api_error(
            en="consents_required",
            kr="필수 동의 항목을 모두 확인해주세요.",
            code="consents_required",
            status=400,
            missing_consents=list(_OAUTH_FINALIZE_REQUIRED_CONSENTS),
        )

    # ``is not True`` — 문자열 "true" / 1 / "on" 같은 truthy 값은 동의로
    # 인정하지 않는다. 명시적 opt-in 만 증거가 된다.
    missing = [
        key
        for key in _OAUTH_FINALIZE_REQUIRED_CONSENTS
        if consents.get(key) is not True
    ]
    if missing:
        logger.info(
            "OAuth finalize: required consents missing=%s (user_id=%s)",
            missing, getattr(current_user, "id", None),
        )
        return api_error(
            en="consents_required",
            kr="필수 동의 항목을 모두 확인해주셔야 가입이 완료됩니다.",
            code="consents_required",
            status=400,
            missing_consents=missing,
        )

    try:
        age_result = check_birthdate_payload(d.get("birthdate"))
    except BirthdateValidationError as exc:
        if exc.code == "below_min_age" and current_user.birthdate is None:
            # PIPA §22 ⑥ — no processing of an under-14's data without a
            # guardian's consent. 2026-09-10: the OAuth callback had already
            # created the row (email, name, avatar, provider id) and this
            # branch only refused the birthdate, leaving the account in place
            # with no exit. Erase it now, the same way the 30-day purge does,
            # but without the "purge complete" email to the child's address.
            erased_id, erased_email = current_user.id, current_user.email
            try:
                from scripts.nightly.pipa_purge import _delete_user_cascade
                _delete_user_cascade(erased_id, erased_email, send_email=False)
                logger.info("OAuth finalize: under-14 account erased (user_id=%s)", erased_id)
            except Exception:
                db.session.rollback()
                logger.exception("OAuth finalize: under-14 erasure failed user_id=%s", erased_id)
            logout_user()
            session.clear()
            _err = api_error(
                en=exc.code,
                kr="만 14세 미만은 가입할 수 없어 입력하신 정보를 삭제했습니다.",
                code=exc.code,
                status=400,
            )
            # api_error returns (response, status); cookies go on the response.
            if isinstance(_err, tuple):
                return (_clear_auth_cookies(_err[0]),) + tuple(_err[1:])
            return _clear_auth_cookies(_err)
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

    # ── 국외이전 동의 기록 (PIPA §28-8) — 생년월일과 같은 트랜잭션 ──────
    #
    # 기록 방식은 ``routes/consents.py``
    # (``record_cross_border_consent`` / ``_utcnow_naive``) 를 그대로 따른다:
    # 같은 두 컬럼, 같은 naive-UTC 컨벤션. 두 번째 구현을 만들지 않으려고
    # 헬퍼를 그 모듈에서 import 한다.
    #
    # 프론트가 별도로 ``POST /api/consents/cross-border`` 를 때리던 best-effort
    # 경로는 이 커밋으로 제거했다 — 같은 사실을 두 번 기록하면 타임스탬프가
    # 실제 동의 시각에서 밀린다.
    #
    # ``cross_border_consent_at`` 이 이미 있으면 다시 스탬프하지 않는다.
    # 재-finalize(같은 생년월일 멱등 경로)가 최초 동의 시각을 덮어써서
    # 감사 추적을 뒤로 미는 것을 막는다.
    from routes.consents import _utcnow_naive  # 기록 컨벤션 단일 SoT

    consent_written = False
    if getattr(user, "cross_border_consent_at", None) is None:
        now = _utcnow_naive()
        user.cross_border_consent_at = now
        user.cross_border_consent_revoked_at = None
        consent_written = True

    # ⚠️ 증거 강도 한계 (의도적 현행 유지)
    #   ``terms`` / ``non_advisory`` 는 대응하는 서버 컬럼이 **없다**.
    #   컬럼 신설은 마이그레이션이라 CEO 승인 대상이므로, 여기서는 요청의
    #   필수 필드로 받아 *검증*만 하고 타임스탬프는 남기지 않는다. 즉 이
    #   두 건은 "동의 없이는 가입이 완료되지 않는다"는 사실이 증거이고,
    #   개별 동의 시각은 서버에 남지 않는다(프론트 localStorage 스냅숏도
    #   가입 완료 시 지워진다 — 그쪽은 애초에 증거로 쓸 수 없었다).
    #   → docs/legal/policy-audit-2026-09-17.md B-1 에 같은 내용을 적어 두었다.

    if user.birthdate is None:
        user.birthdate = age_result.birthdate
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(
                "OAuth finalize commit failed (user_id=%s)", user.id,
            )
            return api_error(
                en="finalize_failed",
                kr="가입 완료 처리에 실패했습니다. 잠시 후 다시 시도해주세요.",
                code="finalize_failed",
                status=500,
            )
        logger.info(
            "OAuth finalize: birthdate set (user_id=%s provider=%s "
            "cross_border_consent_written=%s)",
            user.id, user.oauth_provider, consent_written,
        )
        # Wave G S5 — OAuth signups don't complete until birthdate
        # lands here (PIPA §22 ⑥ gate). Enqueue D+0/D+3/D+7 sequence
        # only when we actually transition from NULL → set; re-finalize
        # attempts are 409'd above so this branch fires exactly once
        # per OAuth user. Fire-and-forget — never blocks signup.
        _schedule_onboarding_safe(user)
    elif consent_written:
        # 멱등 경로(같은 생년월일 재전송)인데 국외이전 동의만 아직 없던
        # 케이스 — 동의 기록은 커밋한다.
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(
                "OAuth finalize cross-border consent commit failed "
                "(user_id=%s)", user.id,
            )
            return api_error(
                en="finalize_failed",
                kr="가입 완료 처리에 실패했습니다. 잠시 후 다시 시도해주세요.",
                code="finalize_failed",
                status=500,
            )

    return jsonify({"ok": True, "user": serialize_user(user)})


# ── Account Deletion (PIPA compliance) ─────────────────────────────────────

@auth_bp.route("/delete-account", methods=["DELETE"])
@api_auth
@general_rate_limit
def delete_account():
    """Delete user account and all associated data. Required by Korean PIPA."""
    user_id = current_user.id
    user_email = current_user.email

    try:
        # Delete every user-owned row, each in its own SAVEPOINT.
        #
        # Why per-table savepoints (2026-06-07 — fixes a prod-only 500)
        # ------------------------------------------------------------
        # delete_account had NEVER run against prod until self-service deletion
        # shipped (the UI was a mailto link). Its first real run 500'd because
        # PostgreSQL aborts the WHOLE transaction on the first failing statement
        # — so a single drifted FK or a table the model declares ``ondelete=
        # CASCADE`` but whose prod constraint predates that clause (Railway's
        # hybrid create_all + _do_migrations strategy lags alembic) blocks the
        # user-row delete and 500s the entire erasure.
        #
        # Each purge now runs in a nested transaction (SAVEPOINT): one table's
        # failure is isolated + logged, never poisoning the rest, and the user
        # row delete below no longer depends on DB-level cascade being correct
        # on prod. Belt-and-suspenders over the FK ondelete clauses.
        #
        # SignalCache is global (ticker-keyed, no user_id) — skipped.
        # Keep this list in sync with scripts/nightly/pipa_purge._delete_user_cascade.
        _d = lambda q: q.delete(synchronize_session=False)  # noqa: E731
        purge_ops = [
            ("positions", lambda: _d(Position.query.filter_by(user_id=user_id))),
            ("trade_history", lambda: _d(TradeHistory.query.filter_by(user_id=user_id))),
            ("alerts", lambda: _d(Alert.query.filter_by(user_id=user_id))),
            ("watchlist", lambda: _d(Watchlist.query.filter_by(user_id=user_id))),
            ("investment_profiles", lambda: _d(InvestmentProfile.query.filter_by(user_id=user_id))),
            ("broker_connections", lambda: _d(BrokerConnection.query.filter_by(user_id=user_id))),
            ("push_subscriptions", lambda: _d(PushSubscription.query.filter_by(user_id=user_id))),
            ("portfolio_shares", lambda: _d(PortfolioShare.query.filter_by(user_id=user_id))),
            ("artifacts", lambda: _d(Artifact.query.filter_by(user_id=user_id))),
            ("user_referrals", lambda: _d(UserReferral.query.filter_by(user_id=user_id))),
            ("artifact_feedback", lambda: _d(ArtifactFeedback.query.filter_by(user_id=user_id))),
            ("behavioral_scores", lambda: _d(BehavioralScore.query.filter_by(user_id=user_id))),
            ("ai_twin_portfolios", lambda: _d(AITwinPortfolio.query.filter_by(user_id=user_id))),
            ("ai_twin_weekly_reports", lambda: _d(AITwinWeeklyReport.query.filter_by(user_id=user_id))),
            ("pre_trade_reflections", lambda: _d(PreTradeReflection.query.filter_by(user_id=user_id))),
            ("persona_snapshots", lambda: _d(PersonaSnapshot.query.filter_by(user_id=user_id))),
            ("weekly_pulse", lambda: _d(WeeklyPulse.query.filter_by(user_id=user_id))),
            ("scheduled_emails", lambda: _d(ScheduledEmail.query.filter_by(user_id=user_id))),
            ("nps_feedback", lambda: _d(NpsFeedback.query.filter_by(user_id=user_id))),
            ("position_dd_checks", lambda: _d(PositionDDCheck.query.filter_by(user_id=user_id))),
            ("inquiries", lambda: _d(Inquiry.query.filter_by(user_id=user_id))),
            # 2026-06-07 — tables with a users FK that were MISSING from the
            # explicit list (the prod 500 culprit class). Model ondelete is
            # CASCADE, so a schema-correct prod cascades them — purging here
            # makes erasure independent of prod FK drift.
            ("checkout_expirations", lambda: _d(CheckoutExpiration.query.filter_by(user_id=user_id))),
            ("portfolio_nav_snapshots", lambda: _d(PortfolioNavSnapshot.query.filter_by(user_id=user_id))),
            # user_agent_audit: model FK is CASCADE (deleted with the user today
            # regardless of the old "retain" comment, which tracked an
            # unimplemented P1). Purge explicitly so a drifted prod FK can't
            # block erasure. Real 2-yr retention, if pursued, needs nullable
            # user_id + SET NULL + counsel sign-off (legal_question_queue).
            ("user_agent_audit", lambda: _d(UserAgentAudit.query.filter_by(user_id=user_id))),
            # companion_waitlist: SET NULL semantics — keep the (now anonymous)
            # waitlist signal, just detach the user.
            ("companion_waitlist", lambda: CompanionWaitlist.query.filter_by(
                user_id=user_id).update({CompanionWaitlist.user_id: None},
                                        synchronize_session=False)),
        ]
        purge_failures = []
        for label, op in purge_ops:
            try:
                with db.session.begin_nested():
                    op()
            except Exception as exc:  # noqa: BLE001 — isolate per-table failure
                purge_failures.append(label)
                logger.warning(
                    "delete_account: purge of %s failed (continuing): %s",
                    label, exc,
                )

        # Dynamic safety net (2026-06-07): the explicit list covers ORM models,
        # but a MIGRATION-ONLY table with a users FK and no model — e.g.
        # ``morning_briefs`` (mig 003), whose FK is a plain ``ForeignKey(
        # "users.id")`` with NO ON DELETE CASCADE — is invisible to it and
        # BLOCKS the user-row delete on prod (ForeignKeyViolation, the actual
        # 500 the user hit). Introspect the LIVE DB and clear every remaining
        # users-referencing row so erasure can't be defeated by an unknown /
        # cascade-less table. Each delete in its own SAVEPOINT.
        #
        # Tables already handled above (incl. companion_waitlist SET NULL) match
        # zero rows here and are no-ops. funnel_events has no FK (deliberate
        # analytics snapshot) so it is never touched.
        try:
            from sqlalchemy import inspect as _sa_inspect, text as _sa_text
            _insp = _sa_inspect(db.engine)
            for _tbl in _insp.get_table_names():
                if _tbl == "users":
                    continue
                for _fk in _insp.get_foreign_keys(_tbl):
                    if _fk.get("referred_table") != "users":
                        continue
                    if "id" not in (_fk.get("referred_columns") or []):
                        continue
                    _cols = _fk.get("constrained_columns") or []
                    if not _cols:
                        continue
                    _col = _cols[0]
                    try:
                        with db.session.begin_nested():
                            db.session.execute(
                                _sa_text(f'DELETE FROM "{_tbl}" WHERE "{_col}" = :uid'),
                                {"uid": user_id},
                            )
                    except Exception as exc:  # noqa: BLE001
                        purge_failures.append(_tbl)
                        logger.warning(
                            "delete_account: dynamic purge of %s.%s failed: %s",
                            _tbl, _col, exc,
                        )
        except Exception:
            logger.exception(
                "delete_account: dynamic FK sweep init failed (continuing)"
            )

        # 2026-06-08 — model-less, FK-less user_id tables. The explicit ORM list
        # can't reach them (no model) and the FK-driven sweep above skips them
        # (no users FK on prod — e.g. ``anthropic_usage_log``: migration 042
        # declares the FK but never ran on prod, so the app.py self-heal CREATE
        # TABLE owns the live schema and omits it). Without this, a deleted
        # user's rows survive → orphaned PII (PIPA §21 right-to-erasure).
        # Allowlist ONLY — a blanket "every user_id table" would wrongly wipe
        # ``funnel_events`` (the deliberately-retained anonymous analytics
        # snapshot). Each delete in its own SAVEPOINT so it can never block the
        # user-row delete. Keep in sync with
        # scripts/nightly/pipa_purge._delete_user_cascade.
        try:
            from sqlalchemy import inspect as _ml_inspect, text as _ml_text
            _ml_insp = _ml_inspect(db.engine)
            _ml_existing = set(_ml_insp.get_table_names())
            for _ml_tbl in ("anthropic_usage_log",):
                if _ml_tbl not in _ml_existing:
                    continue
                if "user_id" not in {c["name"] for c in _ml_insp.get_columns(_ml_tbl)}:
                    continue
                try:
                    with db.session.begin_nested():
                        db.session.execute(
                            _ml_text(f'DELETE FROM "{_ml_tbl}" WHERE "user_id" = :uid'),
                            {"uid": user_id},
                        )
                except Exception as exc:  # noqa: BLE001
                    purge_failures.append(_ml_tbl)
                    logger.warning(
                        "delete_account: model-less purge of %s failed: %s",
                        _ml_tbl, exc,
                    )
        except Exception:
            logger.exception(
                "delete_account: model-less user_id sweep init failed (continuing)"
            )

        # auth_events is keyed by email with no users FK, so neither the list
        # above nor the FK sweep reaches it. 2026-09-10: only the 30-day purge
        # anonymized it, so "delete now" left the plaintext email in the login
        # log indefinitely (privacy policy: access logs ≤ 30 days). Anonymize
        # in place exactly as scripts/nightly/pipa_purge does — the aggregate
        # audit trail survives, the person does not.
        if user_email:
            try:
                from scripts.nightly.pipa_purge import _hash_email
                with db.session.begin_nested():
                    AuthEvent.query.filter(AuthEvent.email == user_email).update(
                        {AuthEvent.email: _hash_email(user_email)},
                        synchronize_session=False,
                    )
            except Exception as exc:  # noqa: BLE001
                purge_failures.append("auth_events")
                logger.warning("delete_account: auth_events anonymize failed: %s", exc)

        # SHIP-BLOCKER: cancel any live Stripe subscription BEFORE dropping the
        # user row, otherwise Stripe keeps billing the card and the webhook can
        # no longer map the charge back to a user (전자상거래법 §17 / PIPA §21).
        # Non-fatal — a Stripe outage must not block the user's erasure right.
        _cancel_stripe_subscription(current_user)

        # Delete the user row. All FK children are purged above, so this no
        # longer depends on the DB-level cascade being present/correct on prod.
        db.session.delete(current_user)
        db.session.commit()

        if purge_failures:
            # The user row WAS deleted; some auxiliary tables couldn't be purged
            # (missing table / drifted FK that didn't block the user delete).
            # Log loudly for ops follow-up — the account itself is gone.
            logger.error(
                "delete_account: user_id=%s deleted but unpurged tables=%s",
                user_id, purge_failures,
            )

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
    except Exception as exc:
        db.session.rollback()
        logger.exception("Account deletion failed for user_id=%s", user_id)
        # Surface only the exception CLASS NAME in the response. The earlier
        # form appended str(exc)[:240] on the claim that "SQLAlchemy errors
        # carry table/constraint names, not row data" — true for
        # ForeignKeyViolation but NOT universally: a Postgres UniqueViolation/
        # CheckViolation DETAIL can embed the offending value (e.g.
        # "Key (email)=(x@y.com)"). 2026-06-09 bug-hunt W2-P3: whitelist to
        # the type name; the full message stays in the server log above.
        return api_error(
            en="An internal error occurred. Please try again.",
            kr="계정 삭제 중 오류가 발생했습니다. 다시 시도해주세요.",
            code="AUTH_DELETE_ACCOUNT_FAILED",
            status=500,
            detail=type(exc).__name__,
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
            # SHIP-BLOCKER: cancel the Stripe subscription at the REQUEST moment
            # (not at purge) so no invoice fires during the 30-day grace window
            # — otherwise the user is double-charged after asking to leave
            # (전자상거래법 §17 / PIPA §21). Only on the NULL→set transition so a
            # repeated request doesn't re-hit Stripe. Non-fatal.
            _cancel_stripe_subscription(user)

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


def _cancel_stripe_subscription(user) -> None:
    """Cancel the user's live Stripe subscription, if any. Never raises.

    SHIP-BLOCKER (전자상거래법 §17 청약철회 / PIPA §21 파기): account
    deletion / 30-day deletion-request previously dropped the ``users`` row
    (or anonymised it) without telling Stripe, so the subscription kept
    billing the card forever. Worse, Stripe's webhook then could not map the
    incoming ``invoice.*`` events back to a user, so the charge was silent
    and unrefundable from our side.

    We cancel at the *request* moment (delete-request) and at hard-delete so
    no invoice fires during the 30-day grace window or after purge. Stripe
    failures are logged and swallowed — a Stripe outage must never block the
    user's right to erasure (PIPA §21 takes precedence; we re-reconcile via
    the billing dashboard if a cancel call fails).
    """
    sub_id = getattr(user, "stripe_subscription_id", None)
    if not sub_id:
        return
    try:
        import stripe  # lazy — keeps stripe optional for tests that mock it
        stripe.Subscription.cancel(sub_id)
        logger.info(
            "stripe subscription cancelled on account deletion: user_id=%s sub=%s",
            getattr(user, "id", "?"), sub_id,
        )
    except stripe.StripeError:
        # Includes "no such subscription" (already cancelled) — non-fatal.
        logger.exception(
            "stripe subscription cancel failed (non-fatal) user_id=%s sub=%s",
            getattr(user, "id", "?"), sub_id,
        )
    except Exception:
        logger.exception(
            "unexpected error cancelling stripe subscription user_id=%s sub=%s",
            getattr(user, "id", "?"), sub_id,
        )


# ── PIPA §21 deletion-request self-service cancel (token-authenticated) ──────
#
# A user inside the 30-day grace window is LOGGED OUT and OAuth login is
# refused (deletion_requested_at != NULL), so they cannot authenticate a
# session to undo the request. We instead email an unforgeable, time-limited
# token (HMAC over SECRET_KEY) that the /delete-cancel page exchanges for a
# restore — the same trust model as a password-reset link. No ambient session,
# no CSRF cookie required (security.py:_csrf_protect skips unauthenticated POSTs).
_DELETE_CANCEL_SALT = "pivoxquant.delete-cancel.v1"
# Token lifetime = grace window + small clock buffer. Past this the row is
# already hard-deleted by the pipa_purge cron, so a stale token restores nothing.
_DELETE_CANCEL_MAX_AGE = 31 * 24 * 3600  # 31 days (30d grace + 1d buffer)


def _delete_cancel_serializer() -> URLSafeTimedSerializer:
    """Serializer for deletion-cancel tokens, bound to the app SECRET_KEY."""
    secret = current_app.secret_key
    if not secret:
        logger.critical("delete-cancel serializer: SECRET_KEY missing on app")
        raise RuntimeError("SECRET_KEY not configured")
    return URLSafeTimedSerializer(secret, salt=_DELETE_CANCEL_SALT)


def _make_delete_cancel_token(user_id, requested_at=None) -> str:
    """Sign a {uid, req} payload the /delete-cancel page later exchanges for a restore.

    ``req`` pins the token to ONE deletion request. 2026-09-10: the payload was
    only ``{uid}`` and a token lives 31 days, so after request → cancel →
    request again, the first email's link could still silently undo the second
    request. Tokens issued before this change carry no ``req`` and are honoured
    until they expire on their own (≤ 31 days).
    """
    payload = {"uid": int(user_id)}
    if requested_at is not None:
        payload["req"] = requested_at.isoformat()
    return _delete_cancel_serializer().dumps(payload)


def _delete_cancel_url(user_id, requested_at=None) -> str:
    """Absolute frontend URL the user clicks to undo a deletion request.

    Resolves the origin the same way OAuth callbacks do (``_resolve_frontend_url``:
    X-Forwarded-Host / Origin / Referer restricted to ``_ALLOWED_OAUTH_ORIGINS``,
    then the ``FRONTEND_URL`` env). The delete-request POST originates from the
    whitelisted frontend, so this yields the real prod domain even when
    FRONTEND_URL is unset — the same reason OAuth redirects already work in prod.
    Falls back to the env var when called outside a request context (cron/CLI
    re-send), since ``_resolve_frontend_url`` reads ``request``.
    """
    try:
        base = _resolve_frontend_url().rstrip("/")
    except RuntimeError:
        base = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/delete-cancel?token={_make_delete_cancel_token(user_id, requested_at)}"


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
    cancel_url = escape(_delete_cancel_url(
        getattr(user, "id", None), getattr(user, "deletion_requested_at", None)
    ))

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
    <p style="margin:24px 0 12px 0;line-height:1.5;color:#5A5A5A;font-size:13px;">
      실수로 요청하셨거나 마음이 바뀌셨나요? 파기 전까지 아래 버튼으로 직접
      탈퇴를 철회하실 수 있습니다. (이 기간 동안에는 로그인이 차단됩니다.)
    </p>
    <p style="margin:0 0 8px 0;">
      <a href="{cancel_url}" style="display:inline-block;padding:11px 22px;
        background:#B8956A;color:#0A0A0A;text-decoration:none;font-size:13px;
        letter-spacing:0.04em;font-weight:600;border-radius:2px;">탈퇴 철회하기</a>
    </p>
    <p style="margin:8px 0 0 0;font-size:11px;color:#999;word-break:break-all;">
      버튼이 작동하지 않으면 다음 주소를 브라우저에 붙여넣어 주세요:<br>{cancel_url}
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


@auth_bp.route("/delete-cancel", methods=["POST"])
@general_rate_limit
def delete_cancel():
    """Self-service cancel of a PIPA §21 30-day deletion request.

    Token-authenticated, NOT session-authenticated — a user inside the grace
    window is logged out and OAuth login is refused (deletion_requested_at !=
    NULL), so the unforgeable HMAC token emailed at request time is the only
    credential they can present. Clearing ``deletion_requested_at`` +
    ``deleted_at`` returns the account to active; the user then logs in
    normally. Mirrors the password-reset-link trust model.

    Idempotent: a token whose account is no longer pending deletion returns
    200 ``already_active=true`` so a double-click / email pre-fetch is safe.
    Never logs the user in — restoration ≠ authentication.
    """
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return api_error(
            en="Missing cancellation token.",
            kr="철회 토큰이 없습니다.",
            code="AUTH_DELETE_CANCEL_NO_TOKEN", status=400,
        )

    try:
        payload = _delete_cancel_serializer().loads(
            token, max_age=_DELETE_CANCEL_MAX_AGE
        )
    except SignatureExpired:
        return api_error(
            en="This cancellation link has expired. The account data may already be erased.",
            kr="철회 링크가 만료되었습니다. 계정 데이터가 이미 파기되었을 수 있습니다.",
            code="AUTH_DELETE_CANCEL_EXPIRED", status=400,
        )
    except BadSignature:
        return api_error(
            en="Invalid cancellation link.",
            kr="유효하지 않은 철회 링크입니다.",
            code="AUTH_DELETE_CANCEL_INVALID", status=400,
        )

    uid = payload.get("uid") if isinstance(payload, dict) else None
    user = db.session.get(User, uid) if uid is not None else None
    if user is None:
        # Row already hard-deleted (grace elapsed) or token uid is bogus.
        # Same generic answer either way — don't leak account existence.
        return api_error(
            en="This account can no longer be restored.",
            kr="이 계정은 더 이상 복구할 수 없습니다.",
            code="AUTH_DELETE_CANCEL_GONE", status=404,
        )

    try:
        if user.deletion_requested_at is None:
            # Not pending deletion — already active or already cancelled.
            return jsonify({"ok": True, "already_active": True})
        req = payload.get("req")
        if req is not None and req != user.deletion_requested_at.isoformat():
            # A link from an earlier request that was already cancelled.
            return api_error(
                en="This cancellation link belongs to an earlier deletion request.",
                kr="이전 삭제 요청의 철회 링크입니다. 가장 최근 메일의 링크를 사용해 주세요.",
                code="AUTH_DELETE_CANCEL_STALE", status=400,
            )
        user.deletion_requested_at = None
        user.deleted_at = None
        db.session.commit()
        logger.info("PIPA delete-cancel: user_id=%s restored to active", uid)
        return jsonify({"ok": True, "restored": True})
    except Exception:
        db.session.rollback()
        logger.exception("delete-cancel failed for user_id=%s", uid)
        return api_error(
            en="An internal error occurred. Please try again.",
            kr="철회 처리 중 오류가 발생했습니다. 다시 시도해주세요.",
            code="AUTH_DELETE_CANCEL_FAILED", status=500,
        )
