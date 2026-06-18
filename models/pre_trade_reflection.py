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
from services.crypto_service import EncryptedText


# Minimum length we require for a self-reflection. Below this the user
# is almost certainly typing "buy" or punching keys to skip the prompt
# — see ``services.pre_trade.friction.start_cooldown``.
# 2026-05-22 (CEO "50자 너무 많아 10자"): lowered 50 → 10. Must match the
# frontend MIN_RATIONALE_CHARS (pre-trade-friction-core.tsx).
MIN_RATIONALE_CHARS = 10

# Default cooldown duration. The service layer extends this when the
# market environment trips one of the auto-extend triggers.
#
# 2026-05-22 (CEO directive "2분 없애"): the forced wait after answering the
# 7-question reflection was causing users to abandon mid-flow → lost
# "add asset" saves. Both windows are now 0 → the reflection is
# immediately "ready" (cooldown_ends_at == cooldown_started_at →
# seconds_remaining 0 → proceed() permitted right away). The 7-question
# self-reflection itself is preserved; only the enforced timer is removed.
DEFAULT_COOLDOWN_SECONDS = 0  # was 120 (2 min) — removed per CEO
EXTENDED_COOLDOWN_SECONDS = 0  # was 300 (5 min) — removed per CEO

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
    # Free-text the user pours in (their stated reason, the devil's-advocate
    # they read). Encrypted at rest — see services.crypto_service.EncryptedText.
    # DB type stays TEXT (ciphertext) so no migration is needed; the ORM still
    # reads/writes plaintext. A leaked DB dump cannot read these words.
    rationale = db.Column(EncryptedText, nullable=False)
    devil_advocate_seen = db.Column(EncryptedText, nullable=True)
    market_volatility_at_request = db.Column(db.Numeric(8, 4), nullable=True)
    cooldown_started_at = db.Column(db.DateTime, nullable=False)
    cooldown_ends_at = db.Column(db.DateTime, nullable=False)
    proceeded_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    auto_extended_reason = db.Column(db.String(50), nullable=True)
    # record-as-spine Phase 2 (2026-06-10): JSON snapshot of the observation
    # surfaces at the moment the reflection was opened — the ticker's own
    # signal label/score (POSITIVE/NEGATIVE/NEUTRAL — the legal surface),
    # VIX, last-hour move. Factual record only; never rec_*/target fields
    # (§17). Best-effort: null when collection failed or found nothing.
    # Mirrored in migrations/versions/049_reflection_observed_context.py.
    observed_context_json = db.Column(db.Text, nullable=True)
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

        # Resolve the company name server-side so the journal can lead with
        # the 종목명 (삼성전자) instead of the bare ticker (005930.KS) for
        # every holding — including KR codes the frontend name map lacks.
        # Lazy import avoids a model→service import cycle. Best-effort.
        intended_name = self.intended_ticker
        try:
            from services.name_resolver import resolve_stock_name
            intended_name = resolve_stock_name(self.intended_ticker) or self.intended_ticker
        except Exception:
            pass

        return {
            "id": int(self.id) if self.id is not None else None,
            "intended_ticker": self.intended_ticker,
            "intended_name": intended_name,
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
            "observed_context": self._observed_context(),
            "seconds_remaining": self.seconds_remaining(now),
            "status": self.status_label(now),
        }

    def _observed_context(self) -> dict | None:
        """Parsed ``observed_context_json`` — or None on absence/corruption."""
        if not self.observed_context_json:
            return None
        try:
            import json
            v = json.loads(self.observed_context_json)
            return v if isinstance(v, dict) and v else None
        except Exception:
            return None
