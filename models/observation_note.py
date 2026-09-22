"""ObservationNote — 거래 없이 적어 두는 관찰 기록.

관찰 노트는 기록의 *앞단*이다. 지금까지 유저 텍스트가 저장되는 자리는 전부
거래에 묶인 순간(``pre_trade_reflections.rationale`` · ``positions.thesis`` ·
``pending_trades.approved_thesis``)뿐이라, 관찰만 하고 있는 동안에는 쓸 곳이
없었다. 이 테이블이 그 빈칸이다 —
docs/design/observation-notes_2026-09-22.md §0.

Lifecycle (append-only + 삭제, 수정 없음 — §8 Q1)

    POST   /api/observation-notes            → row inserted
    GET    /api/observation-notes/list       → 본인 노트 커서 페이지네이션
    GET    /api/observation-notes/<id>       → 단건
    DELETE /api/observation-notes/<id>       → hard delete
    GET    /api/observation-notes/by-ticker/<ticker>
                                             → /pre-trade 가 되비출 최근 노트

Privacy / legal
---------------
- 한 유저가 모든 행을 소유한다 (FK CASCADE + 서비스 층 소유 필터).
- ``body`` 는 유저 본인의 사적 기록이다. 원문 그대로 본인에게만 돌려준다
  (``@legal_scrub_response`` 를 붙이지 않는 이유 — 서버가 고쳐서 돌려주면
  그건 기록이 아니다). 대신 EncryptedText 로 at-rest 암호화한다.
- ``tickers_json`` 은 유저가 적어 둔 관찰 대상일 뿐, 우리가 내는 지시가
  아니다 (자본시장법 §49 분리). 시세는 부르지 않는다.
- 스키마는 ``migrations/versions/054_observation_notes.py`` 와 1:1.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from extensions import db
from services.crypto_service import EncryptedText


# 어느 표면에서 적었는지 — 베타 질문("어디서 기록하나")의 계측.
# /pre-trade 는 읽기 전용 진입점이지만, 향후 다른 표면이 노트를 남길 때를
# 위해 값 자체는 허용한다 (설계 §5 진입점).
VALID_SOURCES = ("journal", "portfolio", "pre_trade")
DEFAULT_SOURCE = "journal"

# 캡 — 요청 위생용. 저장은 TEXT 라 폭 문제는 없고, 한 노트가 무한정 커지거나
# 태그가 수백 개 달리는 경로를 막는 것이 목적이다.
MAX_TICKERS = 5              # 0개 허용 = 시장 전반 노트 (§8 Q2)
MAX_TAGS = 10                # routes/profile.py _PULSE_TOPIC_MAX 와 동일
MAX_TAG_CHARS = 40           # routes/profile.py _PULSE_TOPIC_LEN 과 동일
TICKER_MAX_LEN = 20          # pre_trade_reflections.intended_ticker String(20)


class ObservationNote(db.Model):
    __tablename__ = "observation_notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 유저가 쏟아 넣는 자유 텍스트. 암호화 at rest —
    # services.crypto_service.EncryptedText. DB 타입은 TEXT(암호문) 그대로라
    # 스키마는 평문 컬럼과 동일하다.
    body = db.Column(EncryptedText, nullable=False)
    # JSON array. 정규화된 티커 0~MAX_TICKERS 개. 평문 TEXT 로 두는 이유는
    # 종목별 조회(by-ticker)가 SQL 에서 걸러야 하기 때문 — 티커 자체는
    # 본문과 달리 식별 정보가 아니다.
    tickers_json = db.Column(db.Text, nullable=True)
    tags_json = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(20), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )

    __table_args__ = (
        # 읽기 경로는 전부 (user_id, created_at desc) — list · by-ticker.
        db.Index("idx_observation_notes_user_created", "user_id", "created_at"),
    )

    # ── Helpers ──────────────────────────────────────────────────────

    def tickers_list(self) -> list:
        """Safely decode the tickers JSON column."""
        return _json_list(self.tickers_json)

    def tags_list(self) -> list:
        """Safely decode the tags JSON column."""
        return _json_list(self.tags_json)

    def to_dict(self) -> dict:
        # 종목명은 서버에서 붙인다 — 프론트의 이름 맵이 모르는 KR 코드
        # (005930.KS) 까지 종목명으로 읽히게. PreTradeReflection.to_dict 의
        # ``intended_name`` 관례와 동일. Lazy import 로 model→service
        # 순환을 피하고, 실패는 티커 자체로 폴백한다.
        try:
            from services.name_resolver import resolve_stock_name
        except Exception:  # pragma: no cover - import guard
            resolve_stock_name = None

        def _name(tk: str) -> str:
            if resolve_stock_name is None:
                return tk
            try:
                return resolve_stock_name(tk) or tk
            except Exception:
                return tk

        return {
            "id": int(self.id) if self.id is not None else None,
            "body": self.body,
            "tickers": [
                {"ticker": tk, "name": _name(tk)} for tk in self.tickers_list()
            ],
            "tags": self.tags_list(),
            "source": self.source or DEFAULT_SOURCE,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def _json_list(raw: str | None) -> list:
    """Decode a JSON array column — never raises, never returns non-list."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
    except Exception:
        return []
    return val if isinstance(val, list) else []
