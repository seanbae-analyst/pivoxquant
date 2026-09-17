"""Apply an approved pending fill to ``positions`` / ``trade_history``.

Rules (design §ledger):

Buy rows: existing position → weighted-average cost; USD positions also
      cost-weight ``buy_fx_rate`` with the current FX rate (same rule as
      ``routes/portfolio.py`` add-buy). No position → new ``Position`` with
      the approved thesis, ``thesis_status="pending"``,
      ``added_at=traded_at``.
Sell rows: no position or shares beyond the holding → :class:`LedgerError`
      (``IMPORT_SELL_EXCEEDS_HOLDING``). Otherwise realised pnl against the
      average cost; the position is deleted when fully closed.

Exactly one ``TradeHistory`` row is added per approval, stamped with the
fill's ``traded_at``. Seed capital (``User.available_capital*``) is never
touched (design §원칙 3). This module only ``add``s to ``db.session`` —
the route commits.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from extensions import db
from models import Position, PreTradeReflection, TradeHistory
from models.import_batch import PendingTrade
from services import fx_service
from services.kr_stock_registry import get_name
from services.ticker_normalizer import is_korean_ticker

from . import utcnow_naive

CLOSE_EPS = 0.0001
PRE_TRADE_WINDOW = timedelta(days=7)


class LedgerError(Exception):
    def __init__(self, code: str, en: str, kr: str):
        super().__init__(en)
        self.code = code
        self.en = en
        self.kr = kr


def _display_name(pending: PendingTrade, ticker: str, is_kr: bool) -> str:
    if is_kr:
        return get_name(ticker) or pending.name or ticker
    return pending.name or ticker


def apply_pending(user_id: int, pending: PendingTrade, thesis: str) -> tuple[int, int | None]:
    """Reflect ``pending`` into the ledger. Returns ``(trade_id, position_id)``."""
    ticker = (pending.ticker or "").strip().upper()
    if not ticker:
        raise LedgerError(
            "IMPORT_TICKER_REQUIRED",
            en="A ticker is required before this fill can be recorded.",
            kr="기록하려면 티커가 필요합니다.",
        )
    is_kr = is_korean_ticker(ticker)
    currency = pending.currency or ("KRW" if is_kr else "USD")
    shares = float(pending.shares)
    price = float(pending.price)
    traded_at: datetime = pending.traded_at or utcnow_naive()
    name = _display_name(pending, ticker, is_kr)
    now = utcnow_naive()

    # Same lock as routes/portfolio.py (User→Position order there; we take no
    # User lock because seed capital is never touched, so no cycle). SQLite
    # no-ops the lock; on Postgres it serialises a webhook batch against a
    # manual trade on the same position.
    pos = (
        db.session.query(Position)
        .filter_by(user_id=user_id, ticker=ticker)
        .with_for_update()
        .first()
    )

    if pending.action == "BUY":
        cost = shares * price
        if pos is not None:
            total_cost = pos.shares * pos.avg_cost + cost
            if not is_kr:
                new_fx = fx_service.get_rate() or 0
                if pos.buy_fx_rate and new_fx and total_cost:
                    pos.buy_fx_rate = (
                        pos.buy_fx_rate * pos.shares * pos.avg_cost + new_fx * cost
                    ) / total_cost
                elif not pos.buy_fx_rate and new_fx:
                    pos.buy_fx_rate = new_fx
            pos.shares += shares
            pos.avg_cost = total_cost / pos.shares
            if not (pos.thesis or "").strip():
                pos.thesis = thesis
                pos.thesis_created_at = now
                pos.thesis_status = "pending"
        else:
            # Mirror the manual-entry cap (routes/portfolio.py TIER_LIMIT):
            # an import must not open a 4th position that /positions refuses.
            _enforce_position_cap(user_id)
            pos = Position(
                user_id=user_id,
                ticker=ticker,
                shares=shares,
                avg_cost=price,
                buy_fx_rate=0.0 if is_kr else (fx_service.get_rate() or 0.0),
                added_at=traded_at,
                thesis=thesis,
                thesis_created_at=now,
                thesis_status="pending",
            )
            db.session.add(pos)
        trade = TradeHistory(
            user_id=user_id, ticker=ticker, name=name, action="BUY",  # // legal-ok — trade action data value, not user copy
            shares=shares, price_per_share=round(price, 4),
            total_value=round(cost, 2), pnl=0.0, pnl_pct=0.0,
            currency=currency, traded_at=traded_at,
        )
        db.session.add(trade)
        db.session.flush()
        return trade.id, pos.id

    # SELL  // legal-ok
    if pos is None:
        raise LedgerError(
            "IMPORT_SELL_EXCEEDS_HOLDING",
            en=f"No {ticker} position is held, so a sale of {shares:g} shares cannot be recorded.",
            kr=f"{name} 보유 내역이 없어 {shares:g}주 매도를 기록할 수 없습니다.",
        )
    if shares > pos.shares + 1e-6:
        raise LedgerError(
            "IMPORT_SELL_EXCEEDS_HOLDING",
            en=f"Sale of {shares:g} shares exceeds the {pos.shares:g} shares held in {ticker}.",
            kr=f"{name} 보유 {pos.shares:g}주보다 많은 {shares:g}주 매도는 기록할 수 없습니다.",
        )
    proceeds = shares * price
    cost_basis = shares * pos.avg_cost
    pnl = proceeds - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
    position_id = pos.id
    if shares >= pos.shares - CLOSE_EPS:
        db.session.delete(pos)
    else:
        pos.shares = round(pos.shares - shares, 6)
    trade = TradeHistory(
        user_id=user_id, ticker=ticker, name=name, action="SELL",  # // legal-ok — trade action data value, not user copy
        shares=shares, price_per_share=round(price, 4),
        total_value=round(proceeds, 2), pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2), currency=currency, traded_at=traded_at,
    )
    db.session.add(trade)
    db.session.flush()
    return trade.id, position_id


FREE_POSITION_CAP = 3


def _enforce_position_cap(user_id: int) -> None:
    from models import User
    # Same User row lock as routes/portfolio.py (Bug C#2, 2026-05-26): two
    # concurrent approves must not both count 2 and both open a 4th position.
    # Lock order stays User → Position. No-op on SQLite.
    user = User.query.filter_by(id=user_id).with_for_update().first()
    tier = getattr(user, "effective_tier", None) if user is not None else None
    if tier not in (None, "free"):
        return
    count = Position.query.filter_by(user_id=user_id).filter(Position.shares > 0).count()
    if count >= FREE_POSITION_CAP:
        raise LedgerError(
            "TIER_LIMIT",
            en=f"Free plan is limited to {FREE_POSITION_CAP} positions; this fill would open another.",
            kr=f"무료 플랜은 보유 종목 {FREE_POSITION_CAP}개까지입니다. 이 체결은 새 종목을 여는 건이라 기록할 수 없습니다.",
        )


class PreTradeIndex:
    """Prefetch every reflection that could match a batch, then answer
    ``match(ticker, traded_at)`` in memory (one query per batch, not per row)."""

    def __init__(self, user_id: int, tickers: set[str], start: datetime | None, end: datetime | None):
        self.rows: dict[str, list[tuple[datetime, int]]] = {}
        if not tickers or start is None or end is None:
            return
        candidates: set[str] = set()
        for t in tickers:
            candidates.add(t)
            if "." in t:
                candidates.add(t.split(".", 1)[0])
        found = (
            PreTradeReflection.query
            .filter(PreTradeReflection.user_id == user_id,
                    PreTradeReflection.intended_ticker.in_(list(candidates)),
                    PreTradeReflection.created_at >= start - PRE_TRADE_WINDOW,
                    PreTradeReflection.created_at <= end)
            .order_by(PreTradeReflection.created_at.desc())
            .all()
        )
        for r in found:
            self.rows.setdefault(r.intended_ticker, []).append((r.created_at, r.id))

    def match(self, ticker: str | None, traded_at: datetime | None) -> int | None:
        if not ticker or traded_at is None:
            return None
        keys = [ticker] + ([ticker.split(".", 1)[0]] if "." in ticker else [])
        best: tuple[datetime, int] | None = None
        for k in keys:
            for created, rid in self.rows.get(k, []):
                if created <= traded_at and created >= traded_at - PRE_TRADE_WINDOW:
                    if best is None or created > best[0]:
                        best = (created, rid)
        return best[1] if best else None


def match_pre_trade(user_id: int, ticker: str | None, traded_at: datetime | None) -> int | None:
    """Latest reflection for the same ticker in the 7 days before the fill."""
    if not ticker or traded_at is None:
        return None
    candidates = {ticker}
    if "." in ticker:
        candidates.add(ticker.split(".", 1)[0])
    row = (
        PreTradeReflection.query
        .filter(
            PreTradeReflection.user_id == user_id,
            PreTradeReflection.intended_ticker.in_(list(candidates)),
            PreTradeReflection.created_at <= traded_at,
            PreTradeReflection.created_at >= traded_at - PRE_TRADE_WINDOW,
        )
        .order_by(PreTradeReflection.created_at.desc())
        .first()
    )
    return row.id if row else None


__all__ = ["apply_pending", "match_pre_trade", "PreTradeIndex", "LedgerError", "FREE_POSITION_CAP"]
