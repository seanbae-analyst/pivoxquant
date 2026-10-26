"""DoorwayCheck — 증권 앱을 여는 순간 남긴 한 줄 (문 앞의 한 줄).

docs/design/doorway-pause_2026-10-15.md. 「멈춤」(pre_trade_reflection.py)은
유저가 사기 전에 PivoxQuant 를 스스로 열어야 작동한다. 그런데 충동은 증권
앱을 여는 순간 시작되고 거래도 거기서 끝난다. 이 행은 유저 폰의 자동화
(아이폰 단축어 '앱 → 열 때', MacroDroid '앱 실행')가 증권 앱이 열릴 때 묻는
한 질문 — "뭘 하러 왔어요?" — 의 답이다.

    look   그냥 보기
    buy    살 게 있음  (+ 한 줄)
    sell   팔 게 있음  (+ 한 줄)
    open   답 없음 — 자동화가 질문 전에 보낸 '열림 신호'만 왔다 (2026-10-26).
           답이 오면 같은 행이 위 셋 중 하나로 바뀐다. ``opened_at`` 이 그 신호의
           시각이다 — 신호 없이 답만 온 행은 NULL.

그 열림이 체결로 이어졌는지는 행에 박지 않는다. 읽기 시점에 서비스가 같은
유저의 체결(trade_history + 대기 중인 pending_trades)과 맞춰 본다
(services/doorway/service.py) — friction_outcome 과 같은 규율이다.

Privacy / legal
---------------
- 한 유저가 모든 행을 소유한다 (FK CASCADE + 서비스 층 소유 필터).
- ``note`` 는 유저가 적은 서술이라 ``EncryptedText`` (at-rest 암호화).
  ``intent`` · ``ticker`` · ``app`` · 시각은 평문 — 집계가 걸러야 하고 서술이
  아니다.
- 증권 앱에 닿지 않는다. 유저 폰의 OS 자동화가 유저 본인의 가져오기 토큰으로
  보낸다. 시세를 부르지 않는다. 우리가 붙이는 문장은 개수뿐이다.
- 스키마는 ``migrations/versions/064_doorway_checks.py`` (+ 069 ``opened_at``) 와 1:1.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db
from services.crypto_service import EncryptedText


# 답 세 가지. 소문자 데이터 값이다 — 화면 문구는 프론트가 붙인다.
INTENT_LOOK = "look"
INTENT_BUY = "buy"
INTENT_SELL = "sell"
INTENTS = (INTENT_LOOK, INTENT_BUY, INTENT_SELL)
# 답이 아직 없는 열림 (열림 신호만 온 행). 답 셋과 따로 둔다 — 답으로 받는 값이 아니다.
INTENT_OPEN = "open"
ROW_INTENTS = INTENTS + (INTENT_OPEN,)

# 어디서 왔나 — 폰 자동화(토큰) / 웹의 /door 화면(세션).
SOURCE_AUTOMATION = "automation"
SOURCE_WEB = "web"
SOURCES = (SOURCE_AUTOMATION, SOURCE_WEB)

MAX_NOTE_CHARS = 200          # 한 줄. 폰 입력창에서 쓰는 길이.
APP_MAX_LEN = 20              # "toss" / "kiwoom" … 자동화가 붙이는 꼬리표
TICKER_MAX_LEN = 20           # pre_trade_reflections / research_notes 와 동일


class DoorwayCheck(db.Model):
    __tablename__ = "doorway_checks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent = db.Column(db.String(8), nullable=False)
    # 한 줄에서 읽어 낸 종목 (마스터에 있는 것만). 못 읽으면 null — 그래도
    # 열림은 기록된다.
    ticker = db.Column(db.String(TICKER_MAX_LEN), nullable=True)
    note = db.Column(EncryptedText, nullable=True)
    app = db.Column(db.String(APP_MAX_LEN), nullable=True)
    source = db.Column(db.String(12), nullable=False, default=SOURCE_AUTOMATION)
    # 열림 신호가 온 시각 (naive UTC) — 이 행이 신호로 시작했다는 표시.
    # NULL = 신호 없이 답만 온 행 (069, 2026-10-26).
    opened_at = db.Column(db.DateTime, nullable=True)
    # 문을 연 시각 = 행이 생긴 시각 (naive UTC).
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.Index("idx_doorway_checks_user_created", "user_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": int(self.id) if self.id is not None else None,
            "intent": self.intent if self.intent in ROW_INTENTS else INTENT_LOOK,
            "ticker": self.ticker,
            "name": offline_name(self.ticker) if self.ticker else None,
            "note": self.note or None,
            "app": self.app,
            "source": self.source if self.source in SOURCES else SOURCE_AUTOMATION,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }


def offline_name(ticker: str) -> str:
    """종목명은 오프라인 레지스트리만 본다 — research_note / observation_note
    to_dict 와 같은 이유(기록 3축은 시세·KIS 네트워크를 부르지 않는다)."""
    try:
        if ticker.endswith((".KS", ".KQ")):
            from services import kr_stock_registry

            return kr_stock_registry.get_name(ticker) or ticker
        from services import us_stock_registry

        return us_stock_registry.get_name(ticker) or ticker
    except Exception:
        return ticker
