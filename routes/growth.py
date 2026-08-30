"""Viral-loop growth routes — funnel tracking + public card landing.

Endpoints
---------
- ``POST /api/track``                  — 0원 자체 퍼널 이벤트 적재 (PUBLIC).
- ``GET  /api/card/<share_token>``     — 공개 카드 데이터 (PUBLIC, OG 랜딩용).
- ``POST /api/card/<share_token>/visibility`` — 카드 공개/비공개 토글 (소유자).

설계 원칙
---------
1. ``/api/track`` 는 비로그인 랜딩 이벤트도 받아야 하므로 ``@api_auth`` 없음.
   로그인 상태면 ``current_user.id`` 를 자동 귀속한다. event 화이트리스트
   (``FUNNEL_ALLOWED_EVENTS``) 밖 값은 거부 → 테이블 오염/남용 차단.
2. ``/api/card/<token>`` 는 비로그인 열람용 (OG 랜딩 카드). 정수 PK 가 아닌
   추측 불가 ``share_token`` 으로만 접근. ``is_public=True`` 인 카드만 노출 →
   임의 토큰 enumeration 으로 타인 포트폴리오 노출 차단 (PIPA §29). 응답은
   §101 안전 필드(이름/이미지 URL/안전 요약)만 — 종목 권유 문구 절대 미포함.
3. public 엔드포인트는 모두 ``@general_rate_limit`` (60/min) — 비인증 write/
   read 의 sustained 남용 차단. ``/api/track`` 은 자체 DB INSERT 만이므로
   외부 비용 0원.
4. ``meta`` 는 식별정보 금지 — 키 수/총 크기를 라우트에서 제한하고, 자유
   문자열은 길이 cap 으로 잘라 PIPA 최소수집 + payload abuse 를 막는다.

# legal-exempt: 이 블루프린트는 사용자 자유서술/시그널 산문을 생성하지 않는다.
#   - POST /api/track: 텔레메트리 INSERT only (응답 {ok}). 노출 텍스트 없음.
#   - GET /api/card/<token>: summary_safe 는 서버 생성 고정 문구(사용자 본인
#     실현 수익률 + 일반 면책)로 §101 안전. 종목+전망 결합/권유 동사 미포함을
#     인라인으로 보장하며 test_growth_viral_loop 의 §101 회귀 게이트가 검증한다.
#   따라서 legal_scrub_response 데코레이터 대상이 아니다 (scrub 할 산문 없음).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models import Artifact, FunnelEvent, User, UserReferral
from models.funnel_event import ALLOWED_EVENTS
from services.error_responses import api_error
from security import general_rate_limit

logger = logging.getLogger(__name__)

growth_funnel_bp = Blueprint("growth_funnel", __name__)

# Validation caps — keep public writes bounded (PIPA minimisation + abuse).
_MAX_CHANNEL_LEN = 40
_MAX_REF_CODE_LEN = 16
_MAX_ANON_ID_LEN = 64
_MAX_META_KEYS = 12
_MAX_META_VALUE_LEN = 200
_MAX_CARD_TOKEN_LEN = 64


def _clip(value, max_len: int) -> str | None:
    """Coerce to a trimmed string of at most ``max_len`` chars, or None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_len]


def _sanitize_meta(raw) -> dict | None:
    """Bound the free-form meta dict — drop on type mismatch, cap keys/values.

    Strings are length-capped; non-scalar values are coerced to str then
    capped. Never raises — a malformed meta degrades to None rather than
    rejecting the whole event (tracking is best-effort)."""
    if not isinstance(raw, dict):
        return None
    out: dict = {}
    for i, (k, v) in enumerate(raw.items()):
        if i >= _MAX_META_KEYS:
            break
        key = str(k)[:40]
        if isinstance(v, bool) or isinstance(v, (int, float)) or v is None:
            out[key] = v
        else:
            out[key] = str(v)[:_MAX_META_VALUE_LEN]
    return out or None


@growth_funnel_bp.route("/api/track", methods=["POST"])
@general_rate_limit
def track_event():
    """Record one funnel event (PUBLIC — no auth required).

    Body::
        {
          "event":    "landing_view",   # required, must be whitelisted
          "channel":  "instagram",      # optional
          "ref_code": "AB23CD45",       # optional (inviter's code)
          "anon_id":  "<client uuid>",  # optional (non-PII random id)
          "meta":     { ... }           # optional, bounded
        }

    Returns ``{ "ok": true }`` on success. Unknown ``event`` → 400 with
    code ``EVENT_NOT_ALLOWED`` (whitelist guard against table pollution).
    """
    body = request.get_json(silent=True) or {}

    event = _clip(body.get("event"), 64)
    if not event:
        return api_error(en="event is required", kr="event 값이 필요합니다.",
                         code="EVENT_REQUIRED", status=400)
    if event not in ALLOWED_EVENTS:
        return api_error(
            en="event not allowed",
            kr="허용되지 않은 이벤트입니다.",
            code="EVENT_NOT_ALLOWED",
            status=400,
            allowed=sorted(ALLOWED_EVENTS),
        )

    # Logged-in caller → attribute to their id; else anonymous landing.
    user_id = None
    try:
        if getattr(current_user, "is_authenticated", False):
            user_id = int(current_user.id)
    except Exception:
        user_id = None

    row = FunnelEvent(
        user_id=user_id,
        anon_id=_clip(body.get("anon_id"), _MAX_ANON_ID_LEN),
        event=event,
        channel=_clip(body.get("channel"), _MAX_CHANNEL_LEN),
        ref_code=_clip(body.get("ref_code"), _MAX_REF_CODE_LEN),
        meta=_sanitize_meta(body.get("meta")),
        created_at=datetime.now(timezone.utc),
    )
    try:
        db.session.add(row)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        # Tracking must never surface a hard error to the client — it's
        # fire-and-forget telemetry. Log and return ok=false (200) so the
        # frontend beacon doesn't retry-storm.
        logger.warning("track_event insert failed (event=%s): %s", event, exc)
        return jsonify({"ok": False}), 200

    return jsonify({"ok": True})


def _display_name(owner: User, anonymous: bool) -> str:
    """Owner display name for a public card. Anonymous → generic label."""
    if anonymous:
        return "익명 투자자"
    name = (owner.name or "").strip()
    if name:
        return name
    # Never expose the full email locally — first char + mask.
    local = (owner.email or "").split("@")[0]
    if local:
        return local[0] + "***"
    return "투자자"
