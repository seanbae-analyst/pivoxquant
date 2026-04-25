"""AITwinPosition — open paper position held by a Twin (Feature 5).

100% simulated. ``shares`` and ``avg_cost`` are paper accounting; no
broker side-effect ever issues against this row.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AITwinPosition(db.Model):
    __tablename__ = "ai_twin_positions"

    id = db.Column(db.Integer, primary_key=True)
    twin_id = db.Column(
        db.BigInteger,
        db.ForeignKey("ai_twin_portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker = db.Column(db.String(20), nullable=False)
    shares = db.Column(db.Numeric(20, 4), nullable=False)
    avg_cost = db.Column(db.Numeric(20, 4), nullable=False)
    opened_at = db.Column(db.DateTime, nullable=False, default=_utc_now_naive)

    __table_args__ = (
        db.UniqueConstraint(
            "twin_id", "ticker",
            name="uq_ai_twin_positions_twin_ticker",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": int(self.id),
            "twin_id": int(self.twin_id),
            "ticker": self.ticker,
            "shares": float(self.shares) if self.shares is not None else 0.0,
            "avg_cost": float(self.avg_cost) if self.avg_cost is not None else 0.0,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }
