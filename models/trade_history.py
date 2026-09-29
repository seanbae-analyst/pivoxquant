from datetime import datetime, timezone
from extensions import db

# 2026-09-29 — ``TradeHistory.source`` 값. 보유 등록(POST /positions,
# /position, 보유 캡처 가져오기)이 주식을 더할 때 쓰는 "시드" 매수 행.
# 거울들이 FIFO 로트를 이력에서만 다시 세우므로, 등록 보유분에 행이 없으면
# 그 종목의 매도·추가매수가 로트를 잃었다. 시드는 로트(보유 수량·평단)에는
# 들어가지만 등록 시각이 실제 매수일이 아니라서 보유기간 통계에서 빠지고,
# 체결 수·추가매수 수에도 세지 않는다 (services/profile/fifo_util.is_holding_seed).
HOLDING_SEED_SOURCE = "holding_seed"


class TradeHistory(db.Model):
    __tablename__ = "trade_history"
    id              = db.Column(db.Integer,  primary_key=True)
    user_id         = db.Column(db.Integer,  db.ForeignKey("users.id", ondelete="CASCADE"),
                                  nullable=False, index=True)
    ticker          = db.Column(db.String(20))
    name            = db.Column(db.String(100), default="")
    action          = db.Column(db.String(10))   # BUY | SELL
    shares          = db.Column(db.Float)
    price_per_share = db.Column(db.Float)
    total_value     = db.Column(db.Float)
    pnl             = db.Column(db.Float, default=0.0)
    pnl_pct         = db.Column(db.Float, default=0.0)
    currency        = db.Column(db.String(5), default="USD")
    traded_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    # NULL = 체결 기록 (기존 모든 행). "holding_seed" = 보유 등록 시드 (위 상수).
    source          = db.Column(db.String(20), nullable=True)
