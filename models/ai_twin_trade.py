"""AITwinTrade — paper-only twin trade ledger (Feature 5).

LEGAL POSTURE
-------------
- ``side`` is one of ``BUY`` / ``SELL`` — these are PAPER LABELS for
  the simulated ledger and MUST NEVER be displayed to the user as a
  directive. The ``routes/twin.py`` serializer relabels them to
  ``paper_buy`` / ``paper_sell`` on the wire.
- ``is_paper`` is hard-defaulted to True at the DB layer (CHECK +
  server_default) and the service layer never writes False — see
  ``the paper-isolation regression test``.
- Endpoints filter to ``executed_at <= now`` so prospective rows
  could not be exposed even if they accidentally landed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


# Allowed paper-trade sides — keep in sync with the CHECK constraint
# defined in migration 019 (``ck_ai_twin_trades_side``).
VALID_SIDES = ("BUY", "SELL")


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AITwinTrade(db.Model):
    __tablename__ = "ai_twin_trades"

    id = db.Column(db.Integer, primary_key=True)
    twin_id = db.Column(
        db.BigInteger,
        db.ForeignKey("ai_twin_portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker = db.Column(db.String(20), nullable=False)
    # Paper label only. Never a directive to the human user.
    side = db.Column(db.String(4), nullable=False)
    shares = db.Column(db.Numeric(20, 4), nullable=False)
    price = db.Column(db.Numeric(20, 4), nullable=False)
    executed_at = db.Column(db.DateTime, nullable=False, default=_utc_now_naive)
    rationale = db.Column(db.Text, nullable=True)
    composite_score = db.Column(db.Numeric(5, 2), nullable=True)
    pnl_at_close = db.Column(db.Numeric(20, 4), nullable=True)
    is_paper = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.CheckConstraint(
            "side IN ('BUY','SELL')",
            name="ck_ai_twin_trades_side",
        ),
        db.Index(
            "idx_twin_trades_executed",
            "twin_id", "executed_at",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": int(self.id),
            "twin_id": int(self.twin_id),
            "ticker": self.ticker,
            # Wire format makes the paper-only nature obvious.
            "side": self.side,                       # 'BUY' / 'SELL' (paper label)
            "side_paper_label": f"paper_{self.side.lower()}" if self.side else None,
            "shares": float(self.shares) if self.shares is not None else 0.0,
            "price": float(self.price) if self.price is not None else 0.0,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "rationale": self.rationale,
            "composite_score": (
                float(self.composite_score) if self.composite_score is not None else None
            ),
            "pnl_at_close": (
                float(self.pnl_at_close) if self.pnl_at_close is not None else None
            ),
            # Always True. Surfaced explicitly so the UI cannot accidentally
            # render this row as a real trade.
            "is_paper": True,
        }
