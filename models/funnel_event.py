"""FunnelEvent — 0원 자체 퍼널/바이럴 루프 추적.

``POST /api/track`` 가 이 테이블에 적재한다. 비로그인 랜딩 이벤트도 받아야
하므로 ``user_id`` 는 nullable. 외부 분석 SaaS (GA / Mixpanel / Amplitude)
없이 자체 DB 만 사용 — 추가 비용 0원 + 외부 전송 없음 (PIPA).

이벤트 화이트리스트
------------------
허용 event 만 적재한다 (``ALLOWED_EVENTS``). 화이트리스트 밖 event 는
``POST /api/track`` 단에서 거부 → 임의 문자열 적재로 인한 테이블 오염/남용
차단.

식별가능 최소화 (PIPA)
---------------------
``anon_id`` 는 클라이언트가 생성하는 난수 (예: crypto.randomUUID) 로,
이메일/IP/디바이스 지문이 아니다. 로그인 후 이벤트는 ``user_id`` 로 귀속되며
``anon_id`` 는 비로그인 구간에서만 의미를 갖는다. ``meta`` 에는 식별정보를
넣지 않는다 (라우트 단에서 크기/키 제한).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import JSONB

from extensions import db


# 허용 이벤트 화이트리스트. 라우트(`POST /api/track`)가 이 집합으로 검증한다.
ALLOWED_EVENTS = frozenset({
    "landing_view",       # 비로그인 랜딩 노출 (퍼널 최상단 / acquisition)
    "signup",             # 가입 완료
    "onboarding_done",    # 온보딩 완료 (activation 직전)
    "artifact_opened",    # 아티팩트 열람 (engagement)
    "share_clicked",      # 공유 버튼 클릭 (viral — invites)
    "referral_signup",    # 추천 링크 경유 가입 (viral — conversions)
})


# JSONB on PG, generic JSON elsewhere (SQLite stores as TEXT).
_MetaType = db.JSON().with_variant(JSONB(), "postgresql")
# BIGSERIAL on PG; SQLite uses INTEGER PK (rowid autoincrement).
_IdType = BigInteger().with_variant(db.Integer(), "sqlite")


class FunnelEvent(db.Model):
    __tablename__ = "funnel_events"

    id         = db.Column(_IdType, primary_key=True, autoincrement=True)
    # Nullable: 비로그인 랜딩 이벤트는 user 가 없다. FK 를 의도적으로 두지
    # 않는다 — 익명 이벤트 보존 + user hard-delete(PIPA purge) 후에도 집계용
    # 행이 cascade 로 사라지지 않게 한다 (집계는 user_id 매칭이 아니라 count
    # 중심). user_id 는 단순 정수 스냅샷.
    user_id    = db.Column(_IdType, nullable=True, index=True)
    anon_id    = db.Column(db.Text, nullable=True)
    event      = db.Column(db.Text, nullable=False)
    channel    = db.Column(db.Text, nullable=True)
    ref_code   = db.Column(db.Text, nullable=True, index=True)
    meta       = db.Column(_MetaType, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        db.Index("ix_funnel_events_event_created", "event", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "user_id":    self.user_id,
            "anon_id":    self.anon_id,
            "event":      self.event,
            "channel":    self.channel,
            "ref_code":   self.ref_code,
            "meta":       self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (f"<FunnelEvent id={self.id} event={self.event!r} "
                f"user={self.user_id} ref={self.ref_code!r}>")
