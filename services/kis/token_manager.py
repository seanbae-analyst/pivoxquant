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
from datetime import datetime, timedelta
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

# ── Cache file ───────────────────────────────────────────────────────────
# NOTE: kept at the project root (not next to this file) so the cache
# location did not change when the module moved from root → services/kis/
# on 2026-05-02. ``__file__`` is at services/kis/token_manager.py, so we
# walk up two directories to reach the project root.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_CACHE_FILE = os.path.join(_PROJECT_ROOT, ".kis_token_cache.json")


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
                since = (datetime.now() - self._last_issue_attempt).total_seconds()
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
        """Return True when the token is set and has >1h life remaining."""
        if not token or not expires_at:
            return False
        threshold = datetime.now() + timedelta(hours=REFRESH_BEFORE_HOURS)
        return expires_at > threshold

    def _load_from_file(self) -> None:
        """Populate in-memory token from disk, if a valid cache exists."""
        try:
            if not os.path.exists(_CACHE_FILE):
                return
            with open(_CACHE_FILE, "r") as f:
                cache = json.load(f)
            token = cache.get("token")
            expires_raw = cache.get("expires")
            if not token or not expires_raw:
                return
            expires = datetime.fromisoformat(expires_raw)
            if self._is_fresh(token, expires):
                self._token = token
                self._expires_at = expires
                logger.info("KIS token loaded from file cache (expires=%s)", expires.isoformat())
        except Exception as e:
            logger.debug("KIS token cache read failed: %s", e)

    def _save_to_file(self) -> None:
        """Persist token to disk with restrictive permissions (chmod 600)."""
        if not self._token or not self._expires_at:
            return
        try:
            with open(_CACHE_FILE, "w") as f:
                json.dump({"token": self._token, "expires": self._expires_at.isoformat()}, f)
            try:
                os.chmod(_CACHE_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            except Exception:
                pass
        except Exception as e:
            logger.debug("KIS token cache write failed: %s", e)

    def _issue_new_token_unsafe(self) -> Optional[str]:
        """Actually call /oauth2/tokenP. Caller must hold `self._lock`."""
        self._last_issue_attempt = datetime.now()
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
                self._expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
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
