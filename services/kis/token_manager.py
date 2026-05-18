"""
PivoxQuant — KIS Unified Token Manager
=======================================
한국투자증권 OAuth 토큰을 **단일 진실 공급원(single source of truth)**에서
관리한다. KIS는 1분당 1회만 토큰 발급을 허용하므로 (`EGW00133`),
여러 모듈이 각자 발급하면 레이트리밋에 걸린다.

핵심 특징
- 프로세스 싱글톤 (`get_kis_token_manager()`)
- 메모리 캐시 + 파일 캐시 (`.kis_token_cache.json`)
- `threading.Lock`으로 동시 발급 방지 — 여러 스레드가 동시에 요청해도
  실제 HTTP 호출은 1번만 발생하고 나머지는 대기 후 동일 토큰을 받음
- 12h 토큰 수명 중 11h가 지나면 자동 갱신 (만료 1h 전 refresh)
- VTS(모의) / 실전 자동 감지 (`KIS_USE_REAL` 환경변수)
- 레이트리밋 `EGW00133` 발생 시 기존 토큰이 있으면 유지, 없으면 None 반환

모든 KIS 호출자 (`realtime_service`, `kis_service`, `data_fetcher`)는 이
매니저를 통해 토큰을 얻어야 한다. approval_key (WebSocket 전용)는 별도
경로라서 `kis_websocket_service`에서 계속 관리한다.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ── Sensitive-data masking (H3, 2026-04-24) ─────────────────────────────
_KTM_SENSITIVE_RE = re.compile(
    r'("(?:appkey|appsecret|app_key|app_secret|access_token|approval_key|'
    r'authorization|CANO|ACNT_PRDT_CD|ACNT_NO|account_no|token|secret)"\s*:\s*")'
    r'([^"]*)(")',
    re.IGNORECASE,
)


def _ktm_redact(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    return _KTM_SENSITIVE_RE.sub(
        lambda m: f'{m.group(1)}***{m.group(3)}',
        text,
    )[:max_len]

# ── Endpoints ────────────────────────────────────────────────────────────
REST_URL_REAL = "https://openapi.koreainvestment.com:9443"
REST_URL_VTS = "https://openapivts.koreainvestment.com:29443"

# ── Token lifetime policy ────────────────────────────────────────────────
# KIS issues a 24h-valid token, but we rotate at 12h to be safe.
TOKEN_TTL_HOURS = 12
# Refresh when <= REFRESH_BEFORE_HOURS remain in the lifetime.
REFRESH_BEFORE_HOURS = 1

# 2026-05-17 wave 13 P2 (PR #441) — split the load threshold from the
# refresh threshold. Pre-fix `_load_from_file` discarded any cached
# token with <1h life by reusing `_is_fresh`. On a Railway redeploy
# with a 50-min-remaining token on disk, the new worker treated the
# cache as empty and immediately called `/oauth2/tokenP`, racing the
# KIS 60-s rate-limit window (EGW00133). Load accepts any not-yet-
# expired token; the per-request `_is_fresh` check still triggers a
# proactive refresh when <1h remains.
LOAD_GRACE_SECONDS = 0  # accept any token whose expires_at is in the future

# ── Cache file ───────────────────────────────────────────────────────────
# NOTE: kept at the project root (not next to this file) so the cache
# location did not change when the module moved from root → services/kis/
# on 2026-05-02. ``__file__`` is at services/kis/token_manager.py, so we
# walk up two directories to reach the project root.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
# 2026-05-18 Track A-3 (Wave G-2 Bug #8 deferred → implemented): the cache
# file is now AES-GCM encrypted via services.crypto_service. Format:
#
#     PIVOX-AES-GCM-v1\n<base64(nonce(12) || ciphertext || tag(16))>
#
# Key: PIVOX_BROKER_ENCRYPTION_KEY (reused from broker_connections; prod
# fail-fast already enforced by crypto_service._load_master_key when
# missing). AAD = b"kis-token-cache" binds ciphertext to this surface
# and prevents cross-context replay against broker_connections columns
# (which use the default b"broker" AAD).
#
# Backward compatibility: a legacy plaintext JSON cache from older builds
# is still readable on load (warning logged) and re-saved as ciphertext
# on the next _save_to_file call. chmod 0o600 still applied as a defense-
# in-depth secondary control even though confidentiality now derives from
# AES-GCM rather than file permissions.
_CACHE_FILE = os.path.join(_PROJECT_ROOT, ".kis_token_cache.json")

# Header magic — distinguishes ciphertext from legacy plaintext JSON.
_CACHE_HEADER = b"PIVOX-AES-GCM-v1\n"
# AAD binds the ciphertext to this specific cache surface. Reusing the
# generic b"broker" AAD would allow a row from broker_connections to be
# pasted into .kis_token_cache.json and decrypt successfully, leaking
# user broker creds through the global token cache code path.
_CACHE_AAD = b"kis-token-cache"


class KISTokenManager:
    """Process-wide singleton for KIS OAuth tokens.

    Use `get_kis_token_manager()` instead of instantiating directly.
    """

    _instance: "Optional[KISTokenManager]" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self.app_key = os.environ.get("KIS_APP_KEY", "").strip()
        self.app_secret = os.environ.get("KIS_APP_SECRET", "").strip()
        use_real = os.environ.get("KIS_USE_REAL", "").strip() in (
            "1", "true", "True", "TRUE", "yes",
        )
        self.base_url = REST_URL_REAL if use_real else REST_URL_VTS
        self.is_real = use_real

        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._lock = threading.Lock()
        # Remember the last time we actually hit /oauth2/tokenP so we can
        # back off if KIS is rate-limiting us.
        self._last_issue_attempt: Optional[datetime] = None

        # Load any persisted token on startup.
        self._load_from_file()

    # ── Public API ───────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return bool(self.app_key and self.app_secret)

    def get_token(self) -> Optional[str]:
        """Return a valid access token, issuing a new one if needed.

        Thread-safe. Concurrent callers share a single HTTP request.
        """
        if not self.available:
            return None

        # Fast path: current in-memory token is still valid.
        if self._is_fresh(self._token, self._expires_at):
            return self._token

        with self._lock:
            # Re-check after acquiring the lock — another thread may have
            # already issued a token while we were waiting.
            if self._is_fresh(self._token, self._expires_at):
                return self._token

            # Try the file cache one more time (another process may have
            # written a fresh token between our last read and now).
            self._load_from_file()
            if self._is_fresh(self._token, self._expires_at):
                return self._token

            # Rate-limit guard: KIS allows only 1 token/minute. If we just
            # attempted and there's still no fresh token, back off.
            if self._last_issue_attempt is not None:
                # Bug NEW-F fix: use timezone-aware UTC throughout to avoid
                # naive/aware subtraction TypeError + DST/server-tz drift.
                since = (datetime.now(timezone.utc) - self._last_issue_attempt).total_seconds()
                if since < 60:
                    logger.warning(
                        "KIS token rate-limit cooldown (%.1fs since last attempt); "
                        "serving stale token=%s",
                        since, bool(self._token),
                    )
                    return self._token  # may be None or expired-but-recent

            return self._issue_new_token_unsafe()

    def invalidate(self) -> None:
        """Drop cached token. Next `get_token()` will re-issue."""
        with self._lock:
            self._token = None
            self._expires_at = None
            try:
                if os.path.exists(_CACHE_FILE):
                    os.remove(_CACHE_FILE)
            except Exception as e:
                logger.debug("KIS token cache cleanup failed: %s", e)

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _is_fresh(token: Optional[str], expires_at: Optional[datetime]) -> bool:
        """Return True when the token is set and has >1h life remaining.

        Used by the per-request hot path — falling under the 1h threshold
        triggers a proactive refresh so a serving worker never holds an
        almost-expired token.
        """
        if not token or not expires_at:
            return False
        threshold = datetime.now(timezone.utc) + timedelta(hours=REFRESH_BEFORE_HOURS)
        # Bug NEW-F fix: cached tokens loaded from older runs may be naive;
        # treat them as UTC so the comparison below doesn't TypeError.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > threshold

    @staticmethod
    def _is_loadable(token: Optional[str], expires_at: Optional[datetime]) -> bool:
        """Return True when the cached token still has positive lifetime.

        2026-05-17 wave 13 P2 (PR #441): a separate, looser threshold
        from _is_fresh. _load_from_file used to gate on >1h life and
        discarded everything below — Railway redeploys with a 50-min
        cached token then raced the KIS 60-s rate-limit window
        (EGW00133). A loadable token is reused immediately; the next
        request's _is_fresh check is what triggers the eventual
        refresh.
        """
        if not token or not expires_at:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > datetime.now(timezone.utc) + timedelta(
            seconds=LOAD_GRACE_SECONDS
        )

    def _load_from_file(self) -> None:
        """Populate in-memory token from disk, if a valid cache exists.

        2026-05-17 wave 13 P2 (PR #441): gates on _is_loadable, not
        _is_fresh — see the docstring on _is_loadable for the redeploy
        race rationale. The per-request hot path still calls _is_fresh
        and refreshes proactively when <1h remains.

        2026-05-18 Track A-3: file is AES-GCM ciphertext when the
        PIVOX-AES-GCM-v1\\n header is present. Legacy plaintext JSON
        cache files (from before this change) are still accepted on
        read with a warning — they get re-saved as ciphertext on the
        next token refresh (auto-migration).
        """
        try:
            if not os.path.exists(_CACHE_FILE):
                return
            with open(_CACHE_FILE, "rb") as f:
                raw = f.read()
            if not raw:
                return

            cache: Optional[dict] = None
            if raw.startswith(_CACHE_HEADER):
                # Ciphertext path (current format).
                try:
                    from services.crypto_service import decrypt as _decrypt
                    body_b64 = raw[len(_CACHE_HEADER):].decode("ascii").strip()
                    plaintext_json = _decrypt(body_b64, aad=_CACHE_AAD)
                    cache = json.loads(plaintext_json)
                except Exception as e:
                    # Decrypt failure: likely PIVOX_BROKER_ENCRYPTION_KEY
                    # rotated without re-encrypting the cache. Discard
                    # and force a fresh issue (KIS 60s rate-limit
                    # cooldown in get_token will absorb any storm).
                    logger.warning(
                        "KIS token cache decrypt failed (%s) — discarding; "
                        "next get_token() will re-issue",
                        type(e).__name__,
                    )
                    return
            else:
                # Legacy plaintext path — read once, warn, will be
                # re-saved as ciphertext on next _save_to_file call.
                try:
                    cache = json.loads(raw.decode("utf-8"))
                    logger.warning(
                        "KIS token cache plaintext detected — will re-save "
                        "as AES-GCM ciphertext on next refresh"
                    )
                except Exception:
                    return

            if not cache:
                return
            token = cache.get("token")
            expires_raw = cache.get("expires")
            if not token or not expires_raw:
                return
            expires = datetime.fromisoformat(expires_raw)
            # Bug NEW-F fix: legacy cache files were written with naive
            # datetimes; promote them to UTC for safe comparison.
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if self._is_loadable(token, expires):
                self._token = token
                self._expires_at = expires
                logger.info("KIS token loaded from file cache (expires=%s)", expires.isoformat())
        except Exception as e:
            logger.debug("KIS token cache read failed: %s", e)

    def _save_to_file(self) -> None:
        """Persist token to disk as AES-GCM ciphertext + chmod 600.

        2026-05-18 Track A-3: ciphertext only. The plaintext code path
        was removed — Bug #8 (Wave G-2 PR #480) admit. Defense-in-depth:
        chmod 0o600 is retained even though confidentiality now derives
        from AES-GCM (the chmod was the prior sole control and could
        silently fail on Windows dev / network FS).
        """
        if not self._token or not self._expires_at:
            return
        try:
            from services.crypto_service import encrypt as _encrypt
            plaintext_json = json.dumps(
                {"token": self._token, "expires": self._expires_at.isoformat()},
                separators=(",", ":"),
            )
            ct_b64 = _encrypt(plaintext_json, aad=_CACHE_AAD)
            with open(_CACHE_FILE, "wb") as f:
                f.write(_CACHE_HEADER + ct_b64.encode("ascii"))
            try:
                os.chmod(_CACHE_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            except Exception:
                logger.debug("silent-fallback: _save_to_file chmod", exc_info=True)
                pass
        except Exception as e:
            # Fail-soft: token is still good in memory, just not persisted.
            # Next process restart will re-issue (rate-limited).
            logger.warning("KIS token cache write failed: %s", e)

    def _issue_new_token_unsafe(self) -> Optional[str]:
        """Actually call /oauth2/tokenP. Caller must hold `self._lock`."""
        self._last_issue_attempt = datetime.now(timezone.utc)
        try:
            r = requests.post(
                f"{self.base_url}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                },
                timeout=10,
            )
            try:
                data = r.json()
            except Exception:
                data = {}

            if r.ok and data.get("access_token"):
                token = data["access_token"]
                # KIS returns expires_in in seconds; clamp to our 12h policy.
                expires_in = int(data.get("expires_in", TOKEN_TTL_HOURS * 3600))
                expires_in = min(expires_in, TOKEN_TTL_HOURS * 3600)
                self._token = token
                self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
                self._save_to_file()
                logger.info(
                    "KIS token issued (url=%s, expires=%s)",
                    "real" if self.is_real else "vts",
                    self._expires_at.isoformat(),
                )
                return token

            # Non-OK or missing access_token. Log once and keep any stale token.
            err_code = data.get("error_code") or data.get("rt_cd")
            err_desc = (
                data.get("error_description")
                or data.get("msg1")
                # H3: raw body may echo the appkey/appsecret we sent — redact.
                or _ktm_redact(r.text, max_len=200)
            )
            logger.warning(
                "KIS token issue failed (http=%s, code=%s): %s",
                r.status_code, err_code, err_desc,
            )
            return self._token  # may be None, or stale-but-last-known
        except Exception as e:
            logger.error("KIS token HTTP error: %s", e)
            return self._token


# ── Singleton accessor ───────────────────────────────────────────────────

def get_kis_token_manager() -> KISTokenManager:
    """Return the process-wide KISTokenManager singleton."""
    if KISTokenManager._instance is None:
        with KISTokenManager._instance_lock:
            if KISTokenManager._instance is None:
                KISTokenManager._instance = KISTokenManager()
    return KISTokenManager._instance


def get_kis_token() -> Optional[str]:
    """Shortcut: return a valid KIS access token (or None if unavailable)."""
    return get_kis_token_manager().get_token()
