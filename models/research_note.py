"""ResearchNote — 사기 전에 직접 확인한 것을 양식으로 적고, 정한 날 다시 채점한다.

docs/design/research-notes_2026-10-15.md. 관찰 노트(``observation_note.py``)가
자유 텍스트의 앞단이라면, 리서치 노트는 **모든 종목에 같은 다섯 칸 양식**이다:

    1. 이 회사는 뭘로 돈을 버나            (business, 선택 — 2026-10-25 부터, 비우면 "")
    2. 내가 보는 이유 — 가정 1~3개          (theses, 필수)
    3. 이게 보이면 틀린 것                 (invalidation, 선택)
    4. 가장 큰 위험 하나                   (risk, 선택)
    5. 직접 확인한 숫자                    (numbers, 선택 — 비우면 "안 봄")
    + 어디서 알게 됐나                     (info_source, 선택)
    + 다시 볼 날                           (review_on, 1·3·6개월)

다시 볼 날이 오면 유저가 가정마다 맞음/틀림/모름을 고른다(verdicts). 그 판단을
같은 종목의 **본인 체결**(실현 손익 부호)과 나란히 두는 것은 읽기 시점에
서비스가 계산한다 — 행에 결과를 박지 않는다.

Privacy / legal
---------------
- 한 유저가 모든 행을 소유한다 (FK CASCADE + 서비스 층 소유 필터).
- 서술 칸은 전부 ``EncryptedText`` (at-rest 암호화). 가정 목록도 서술이라
  JSON 을 암호화해서 넣는다. ``ticker`` · ``info_source`` · ``verdicts_json``
  · 날짜는 평문 — 조회·집계가 SQL/서비스에서 걸러야 하고 서술이 아니다.
- 양식은 모든 종목에 같다. 종목별 안내·숫자를 우리가 채우지 않는다
  (투자자문 경계 · FMP §2.2.2 Display Agreement 미체결). 시세를 부르지 않는다.
- 스키마는 ``migrations/versions/063_research_notes.py`` 와 1:1.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from extensions import db
from services.crypto_service import EncryptedText


# 어느 표면에서 적었는지 — 베타 질문("어디서 기록하나")의 계측.
VALID_SURFACES = ("journal", "portfolio", "pre_trade")
DEFAULT_SURFACE = "journal"

# 어디서 알게 됐나 — 유저가 고르는 칩. 지시가 아니라 본인 기록의 꼬리표다.
INFO_SOURCES = ("report", "youtube", "social", "ai", "self")

# 다시 볼 날 — 적은 날로부터 몇 달 뒤 (KST 날짜).
REVIEW_MONTHS = (1, 3, 6)

# 가정 하나에 대한 채점.
VERDICTS = ("right", "wrong", "unknown")

# 캡 — 요청 위생용. 양식이 "짧게"여야 쓰인다는 것이 설계 전제라 칸마다 좁다.
MIN_THESES = 1
MAX_THESES = 3
MAX_BUSINESS_CHARS = 300
MAX_THESIS_CHARS = 300
MAX_INVALIDATION_CHARS = 500
MAX_RISK_CHARS = 500
MAX_NUMBERS_CHARS = 1000
MAX_REVIEW_NOTE_CHARS = 500
TICKER_MAX_LEN = 20          # observation_notes / pre_trade_reflections 와 동일


class ResearchNote(db.Model):
    __tablename__ = "research_notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker = db.Column(db.String(TICKER_MAX_LEN), nullable=False)

    business = db.Column(EncryptedText, nullable=False)
    # JSON array of 1..3 strings, encrypted as one blob.
    theses_json = db.Column(EncryptedText, nullable=False)
    invalidation = db.Column(EncryptedText, nullable=True)
    risk = db.Column(EncryptedText, nullable=True)
    numbers = db.Column(EncryptedText, nullable=True)
    info_source = db.Column(db.String(20), nullable=True)
    surface = db.Column(db.String(20), nullable=True)

    review_on = db.Column(db.Date, nullable=False)
    # JSON array aligned with theses — "right" / "wrong" / "unknown".
    verdicts_json = db.Column(db.Text, nullable=True)
    review_note = db.Column(EncryptedText, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.Index("idx_research_notes_user_created", "user_id", "created_at"),
        db.Index("idx_research_notes_user_review_on", "user_id", "review_on"),
    )

    # ── Helpers ──────────────────────────────────────────────────────

    def theses_list(self) -> list[str]:
        return [t for t in _json_list(self.theses_json) if isinstance(t, str)]

    def verdicts_list(self) -> list[str]:
        return [v for v in _json_list(self.verdicts_json) if v in VERDICTS]

    def is_due(self, today: date) -> bool:
        """Due = the review day has come and it has not been scored yet."""
        return self.reviewed_at is None and self.review_on is not None and self.review_on <= today

    def to_dict(self, *, today: date | None = None) -> dict:
        # 종목명은 오프라인 레지스트리만 본다 — 관찰 노트 to_dict 와 같은 이유
        # (기록 3축은 시세·KIS 네트워크를 부르지 않는다).
        def _name(tk: str) -> str:
            try:
                if tk.endswith((".KS", ".KQ")):
                    from services import kr_stock_registry

                    return kr_stock_registry.get_name(tk) or tk
                from services import us_stock_registry

                return us_stock_registry.get_name(tk) or tk
            except Exception:
                return tk

        out = {
            "id": int(self.id) if self.id is not None else None,
            "ticker": self.ticker,
            "name": _name(self.ticker or ""),
            "business": self.business,
            "theses": self.theses_list(),
            "invalidation": self.invalidation or None,
            "risk": self.risk or None,
            "numbers": self.numbers or None,
            "info_source": self.info_source if self.info_source in INFO_SOURCES else None,
            "surface": self.surface or DEFAULT_SURFACE,
            "review_on": self.review_on.isoformat() if self.review_on else None,
            "verdicts": self.verdicts_list() if self.reviewed_at else [],
            "review_note": self.review_note or None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if today is not None:
            out["due"] = self.is_due(today)
        return out


def _json_list(raw: str | None) -> list:
    """Decode a JSON array column — never raises, never returns non-list."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
    except Exception:
        return []
    return val if isinstance(val, list) else []
