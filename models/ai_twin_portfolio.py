"""AITwinPortfolio — paper-only twin portfolio root row (Feature 5).

LEGAL POSTURE
-------------
- 100% paper. No FK or attribute references real money / external broker rows.
- One row per user (UNIQUE user_id) — initialization is idempotent.
- ``current_cash`` and the related ``ai_twin_positions`` rows describe a
  fully simulated $10K USD balance — never a live account.
- See migration 019 docstring for the full legal anchor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from extensions import db


# Paper-only starting balance (USD). Constant so the runner / tests /
# legal review can reference one source of truth.
DEFAULT_STARTING_CASH = Decimal("10000.00")


def _utc_now_naive() -> datetime:
    """UTC timestamp without tzinfo — matches the rest of the codebase."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AITwinPortfolio(db.Model):
    __tablename__ = "ai_twin_portfolios"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    initialized_at = db.Column(db.DateTime, nullable=False, default=_utc_now_naive)
    starting_cash = db.Column(
        db.Numeric(20, 4),
        nullable=False,
        default=DEFAULT_STARTING_CASH,
    )
    current_cash = db.Column(
        db.Numeric(20, 4),
        nullable=False,
        default=DEFAULT_STARTING_CASH,
    )
    persona_at_init = db.Column(db.String(20), nullable=False)
    last_decision_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now_naive)

    positions = db.relationship(
        "AITwinPosition",
        backref="portfolio",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    trades = db.relationship(
        "AITwinTrade",
        backref="portfolio",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def to_dict(self) -> dict:
        return {
            "id": int(self.id),
            "user_id": int(self.user_id),
            "initialized_at": self.initialized_at.isoformat() if self.initialized_at else None,
            "starting_cash": float(self.starting_cash) if self.starting_cash is not None else 0.0,
            "current_cash": float(self.current_cash) if self.current_cash is not None else 0.0,
            "persona_at_init": self.persona_at_init,
            "last_decision_at": self.last_decision_at.isoformat() if self.last_decision_at else None,
            "is_active": bool(self.is_active),
            # Paper-portfolio label — read by the API layer to attach
            # the legally-required UI badge.
            "paper_label": "PAPER PORTFOLIO",
        }
