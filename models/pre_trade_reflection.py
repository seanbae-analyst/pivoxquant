"""PreTradeReflection — user-imposed cooldown + rationale before a trade.

Powers Feature 6 (Pre-Trade Friction). Lifecycle:

    /api/pre-trade/start            → row inserted (cooldown_started_at,
                                       cooldown_ends_at, rationale,
                                       optional auto_extended_reason)
    /api/pre-trade/<id>             → status / time remaining read
    /api/pre-trade/<id>/proceed     → proceeded_at stamped (frontend then
                                       fires the user's existing broker route)
    /api/pre-trade/<id>/cancel      → cancelled_at stamped

Privacy / legal
---------------
- One user owns every row (FK CASCADE).
- ``intended_side`` is a label the user supplied for their own record;
  we never emit a directive based on it (자본시장법 §49 separation).
- ``rationale`` is rendered only to the originating user.
- Schema is mirrored 1:1 with ``migrations/versions/017_pre_trade_reflections.py``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from extensions import db


# Minimum length we require for a self-reflection. Below this the user
# is almost certainly typing "buy" or punching keys to skip the prompt
# — see ``services.pre_trade.friction.start_cooldown``.
MIN_RATIONALE_CHARS = 50

# Default cooldown duration. The service layer extends this when the
# market environment trips one of the auto-extend triggers.
DEFAULT_COOLDOWN_SECONDS = 120  # 2 min
EXTENDED_COOLDOWN_SECONDS = 300  # 5 min — for FOMC / VIX / big-move windows

# Allowed `auto_extended_reason` values — kept here so service + tests
# share the source of truth without a service-layer import cycle.
AUTO_EXTEND_REASONS = (
    "fomc_30min",
    "high_vix",
    "big_move_1h",
)


class PreTradeReflection(db.Model):
    __tablename__ = "pre_trade_reflections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intended_ticker = db.Column(db.String(20), nullable=False)
    # Free-text label, validated upstream. Allowed: 'BUY' / 'SELL' / null.
    intended_side = db.Column(db.String(4), nullable=True)
    intended_shares = db.Column(db.Numeric(20, 4), nullable=True)
    rationale = db.Column(db.Text, nullable=False)
    devil_advocate_seen = db.Column(db.Text, nullable=True)
    market_volatility_at_request = db.Column(db.Numeric(8, 4), nullable=True)
    cooldown_started_at = db.Column(db.DateTime, nullable=False)
    cooldown_ends_at = db.Column(db.DateTime, nullable=False)
    proceeded_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    auto_extended_reason = db.Column(db.String(50), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )

    # ── Helpers ──────────────────────────────────────────────────────

    def is_active(self) -> bool:
        """True iff the reflection is neither proceeded nor cancelled."""
        return self.proceeded_at is None and self.cancelled_at is None

    def seconds_remaining(self, now: datetime | None = None) -> int:
        """Whole seconds left in the cooldown, never negative."""
        ref = now or datetime.now(timezone.utc).replace(tzinfo=None)
        if not self.cooldown_ends_at:
            return 0
        delta = (self.cooldown_ends_at - ref).total_seconds()
        return max(0, int(delta))

    def status_label(self, now: datetime | None = None) -> str:
        """One of: 'pending' / 'ready' / 'proceeded' / 'cancelled' / 'expired'.

        ``expired`` is only used by the service layer for cleanup — the
        API surface uses 'pending' (still cooling down) / 'ready'
        (cooldown finished, awaiting proceed) / terminal states.
        """
        if self.cancelled_at is not None:
            return "cancelled"
        if self.proceeded_at is not None:
            return "proceeded"
        if self.seconds_remaining(now) > 0:
            return "pending"
        return "ready"

    def to_dict(self, now: datetime | None = None) -> dict:
        # Decimal columns serialise to float for the JSON wire — the
        # frontend only needs display precision, not arithmetic.
        def _f(v):
            if v is None:
                return None
            if isinstance(v, Decimal):
                return float(v)
            return v

        return {
            "id": int(self.id) if self.id is not None else None,
            "intended_ticker": self.intended_ticker,
            "intended_side": self.intended_side,
            "intended_shares": _f(self.intended_shares),
            "rationale": self.rationale,
            "devil_advocate_seen": self.devil_advocate_seen,
            "market_volatility_at_request": _f(self.market_volatility_at_request),
            "cooldown_started_at": self.cooldown_started_at.isoformat() if self.cooldown_started_at else None,
            "cooldown_ends_at": self.cooldown_ends_at.isoformat() if self.cooldown_ends_at else None,
            "proceeded_at": self.proceeded_at.isoformat() if self.proceeded_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "auto_extended_reason": self.auto_extended_reason,
            "seconds_remaining": self.seconds_remaining(now),
            "status": self.status_label(now),
        }
