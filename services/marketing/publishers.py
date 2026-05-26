"""Threads / Bluesky 퍼블리셔 — 토큰 게이트, graceful no-op.

설계 원칙
=========
- **추가 비용 0원**: Bluesky AT Protocol + Threads Graph API 둘 다 공식
  *무료* API. 새 유료 SaaS 0건.
- **토큰 없으면 비활성**: env 미설정 시 ``PublishResult(status="skipped")``
  를 반환 — 빌드/런타임 안 깨짐 (Kakao 키 패턴 동일).
- **예외 삼킴**: 발행 실패가 파이프 전체(다른 채널/항목)를 죽이지 않도록
  모든 네트워크 예외를 잡아 ``status="error"`` 로 변환한다. 상위 디스패처가
  Slack 경고를 띄운다.

반환 계약
=========
모든 publisher 는 :class:`PublishResult` 를 반환한다::

    status == "ok"      → 발행 성공 (status 갱신 대상)
    status == "skipped" → 토큰 없음 (no-op, 정상)
    status == "error"   → 발행 시도했으나 실패 (Slack 경고 대상)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# 짧은 타임아웃 — cron 틱이 hung 외부 API 로 블록되지 않게.
_HTTP_TIMEOUT = 20


@dataclass
class PublishResult:
    channel: str
    status: str  # "ok" | "skipped" | "error"
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def skipped(self) -> bool:
        return self.status == "skipped"


def _requests():
    """Lazy import — keeps scheduler boot light & lets envs without requests
    degrade to skip rather than ImportError at registration time."""
    try:
        import requests  # noqa: PLC0415

        return requests
    except ImportError:  # pragma: no cover - requests is a hard dep in prod
        return None


# ─────────────────────────────────────────────────────────────────────
# Bluesky — AT Protocol (com.atproto.repo.createRecord)
# ─────────────────────────────────────────────────────────────────────
#
# CEO 토큰 발급 TODO:
#   1. https://bsky.app 계정 생성 (무료).
#   2. Settings → App Passwords 에서 앱 비밀번호 발급 (계정 비밀번호 아님).
#   3. Railway Variables 에 추가:
#        BLUESKY_HANDLE        = your-handle.bsky.social
#        BLUESKY_APP_PASSWORD  = xxxx-xxxx-xxxx-xxxx
#   토큰 없으면 이 함수는 영구 no-op (skipped).

_BLUESKY_PDS = "https://bsky.social"


def publish_bluesky(text: str, image_path: str | None = None) -> PublishResult:
    """Post ``text`` to Bluesky via AT Protocol. No-op when creds missing."""
    handle = os.environ.get("BLUESKY_HANDLE")
    app_pw = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not app_pw:
        logger.info("[marketing] bluesky skipped — BLUESKY_HANDLE/APP_PASSWORD unset")
        return PublishResult("bluesky", "skipped", "creds unset")

    requests = _requests()
    if requests is None:
        return PublishResult("bluesky", "error", "requests not installed")

    try:
        # 1) Create session (auth) → access JWT.
        sess = requests.post(
            f"{_BLUESKY_PDS}/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": app_pw},
            timeout=_HTTP_TIMEOUT,
        )
        sess.raise_for_status()
        auth = sess.json()
        jwt = auth["accessJwt"]
        did = auth["did"]

        # AT Protocol record: 작성 시각은 RFC-3339 UTC.
        from datetime import datetime, timezone

        record = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # 2) createRecord.
        resp = requests.post(
            f"{_BLUESKY_PDS}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        uri = resp.json().get("uri", "")
        logger.info("[marketing] bluesky posted: %s", uri)
        return PublishResult("bluesky", "ok", uri)
    except Exception as exc:  # noqa: BLE001 - never let one channel kill the pipe
        logger.exception("[marketing] bluesky publish failed")
        return PublishResult("bluesky", "error", str(exc))


# ─────────────────────────────────────────────────────────────────────
# Threads — Meta Threads Graph API (2-step: create container → publish)
# ─────────────────────────────────────────────────────────────────────
#
# CEO 토큰 발급 TODO:
#   1. https://developers.facebook.com 에서 앱 생성 + Threads API 제품 추가.
#   2. Threads 계정 연결 → long-lived access token + Threads user id 획득.
#   3. Railway Variables 에 추가:
#        THREADS_USER_ID       = 17841xxxxxxxxxxx
#        THREADS_ACCESS_TOKEN  = THAA...
#   토큰 없으면 이 함수는 영구 no-op (skipped). 이미지 첨부는 공개 URL 이
#   필요하므로(Threads API 제약) image_path 는 현재 미사용 — 텍스트 전용 발행.

_THREADS_API = "https://graph.threads.net/v1.0"


def publish_threads(text: str, image_path: str | None = None) -> PublishResult:
    """Post ``text`` to Threads via the official Graph API. No-op when unset.

    Threads API 는 2단계: (1) media container 생성 → (2) publish.
    이미지 첨부는 *공개 URL* 만 받으므로(로컬 파일 직접 업로드 불가) 현재는
    텍스트 전용. 이미지가 필요하면 인스타 리마인더 경로(수동 1탭)를 쓴다.
    """
    user_id = os.environ.get("THREADS_USER_ID")
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not user_id or not token:
        logger.info("[marketing] threads skipped — THREADS_USER_ID/ACCESS_TOKEN unset")
        return PublishResult("threads", "skipped", "creds unset")

    requests = _requests()
    if requests is None:
        return PublishResult("threads", "error", "requests not installed")

    try:
        # 1) Create media container (TEXT).
        create = requests.post(
            f"{_THREADS_API}/{user_id}/threads",
            data={"media_type": "TEXT", "text": text, "access_token": token},
            timeout=_HTTP_TIMEOUT,
        )
        create.raise_for_status()
        container_id = create.json().get("id")
        if not container_id:
            return PublishResult("threads", "error", "no container id returned")

        # 2) Publish the container.
        publish = requests.post(
            f"{_THREADS_API}/{user_id}/threads_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=_HTTP_TIMEOUT,
        )
        publish.raise_for_status()
        post_id = publish.json().get("id", "")
        logger.info("[marketing] threads posted: %s", post_id)
        return PublishResult("threads", "ok", post_id)
    except Exception as exc:  # noqa: BLE001 - never let one channel kill the pipe
        logger.exception("[marketing] threads publish failed")
        return PublishResult("threads", "error", str(exc))


def resolve_image_abspath(image_path: str | None) -> str | None:
    """Resolve a repo-relative image_path to an absolute path if it exists.

    인스타 Slack 리마인더에서 CEO 가 파일을 찾을 수 있도록 절대경로를 준다.
    파일 없으면 ``None`` (캡션만 전송).
    """
    if not image_path:
        return None
    repo_root = Path(__file__).resolve().parent.parent.parent
    p = (repo_root / image_path) if not Path(image_path).is_absolute() else Path(image_path)
    return str(p) if p.exists() else None


__all__ = [
    "PublishResult",
    "publish_bluesky",
    "publish_threads",
    "resolve_image_abspath",
]
