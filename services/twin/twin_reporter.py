"""Twin reporter — weekly user-vs-twin paper P&L comparison.

Read path is descriptive only:
    "Last week — you: +X.X% / Twin: +Y.Y% (diff: Y-X pp)"

No prospective language ever crosses the boundary; the route layer
attaches the standard disclaimer.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_

from extensions import db
from models import (
    AITwinPortfolio,
    AITwinTrade,
    AITwinWeeklyReport,
    TradeHistory,
)

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _week_window(week_ending: date) -> tuple[datetime, datetime]:
    """Return [start, end) datetimes for the 7-day window ending on
    ``week_ending`` (inclusive of that date's full day).
    """
    end = datetime.combine(week_ending, datetime.min.time()) + timedelta(days=1)
    start = end - timedelta(days=7)
    return start, end


def _compute_user_return(user_id: int, week_ending: date) -> tuple[float | None, int]:
    """Sum the user's REAL TradeHistory P&L for the week.

    Returns (return_pct, trade_count). The percentage is computed as
    (sum_pnl / sum_invested) * 100 — a simple and falsifiable measure
    that matches the PnL field already populated on every TradeHistory
    row by the closed-trade matcher.

    When the user has zero closed trades in the window, returns
    ``(None, 0)`` — the API renders that as "—" rather than 0%.
    """
    start, end = _week_window(week_ending)
    rows = (
        TradeHistory.query
        .filter(
            and_(
                TradeHistory.user_id == user_id,
                TradeHistory.traded_at >= start,
                TradeHistory.traded_at < end,
            )
        )
        .all()
    )
    if not rows:
        return None, 0
    # Wave-3 P2 (2026-06-10): the old math summed EVERY row's total_value as
    # the denominator. A SELL's total_value is PROCEEDS (cost + pnl), so a
    # same-week $1,000→$1,100 round trip read +4.76% instead of +10%, and
    # mixed KR/US weeks raw-summed ₩ + $ (Pattern-7).
    #
    # Weekly semantics differ from the routes/twin.py lifetime fix (BUY legs
    # only): a week often contains ONLY the closing SELL of a position bought
    # earlier — a BUY-only denominator would null out exactly the weeks with
    # realized results. Match _compute_twin_return's documented measure
    # instead — "realized P&L over realized cost basis": denominator = each
    # SELL's cost basis (proceeds − pnl), both legs normalised to KRW.
    # Same-week round trip: (1100−100)=1000 → 100/1000 = +10% ✓.
    #
    # NOTE: weekly rows persisted by earlier cron runs used the old math and
    # are idempotent-cached; history is left as-is (documented drift).
    from services import fx_service

    fx = fx_service.get_rate()
    realized_cost = 0.0
    pnl = 0.0
    for r in rows:
        try:
            if (r.action or "").upper() != "SELL":
                continue
            proceeds = fx_service.amount_to_krw(
                r.total_value, r.currency, r.ticker, fx
            )
            row_pnl = fx_service.amount_to_krw(r.pnl, r.currency, r.ticker, fx)
            cost = proceeds - row_pnl
            if cost > 0:
                realized_cost += cost
                pnl += row_pnl
        except (TypeError, ValueError):
            logger.debug("silent-fallback: _compute_user_return", exc_info=True)
            continue
    if realized_cost <= 0:
        return None, len(rows)
    return round((pnl / realized_cost) * 100.0, 4), len(rows)


def _compute_twin_return(user_id: int, week_ending: date) -> tuple[float | None, int]:
    """Sum the Twin's PAPER P&L for the week using realized SELL trades.

    A simple, auditable measure: realized P&L over realized cost basis.
    Open positions are intentionally excluded — falsifiability requires
    the comparison be on closed bars only (mirrors the user side).
    """
    twin = AITwinPortfolio.query.filter_by(user_id=user_id).first()
    if twin is None:
        return None, 0
    start, end = _week_window(week_ending)
    sells = (
        AITwinTrade.query
        .filter(
            and_(
                AITwinTrade.twin_id == twin.id,
                AITwinTrade.side == "SELL",
                AITwinTrade.executed_at >= start,
                AITwinTrade.executed_at < end,
            )
        )
        .all()
    )
    buys = (
        AITwinTrade.query
        .filter(
            and_(
                AITwinTrade.twin_id == twin.id,
                AITwinTrade.side == "BUY",
                AITwinTrade.executed_at >= start,
                AITwinTrade.executed_at < end,
            )
        )
        .all()
    )
    trade_count = len(sells) + len(buys)
    if not sells:
        return None, trade_count
    # Pattern-7 fix (2026-06-15): AITwinTrade has no currency column and the
    # twin universe holds BOTH US ($) and KR (₩) names, so raw-summing pnl/cost
    # across a mixed week let a single ₩-scale SELL dominate the %. The user
    # leg (_compute_user_return) and the lifetime path (routes/twin.py
    # twin_comparison) already normalize; only this weekly twin leg did not.
    # Infer currency from the ticker suffix and normalize every leg to KRW
    # before summing. A % is scale-invariant, so single-currency weeks are
    # unchanged (fx cancels in the ratio); only mixed weeks are corrected.
    from services import fx_service

    fx = fx_service.get_rate()
    realized_pnl = Decimal("0")
    cost_basis = Decimal("0")
    for s in sells:
        if s.pnl_at_close is None:
            continue
        ticker = (s.ticker or "").upper()
        currency = "KRW" if ticker.endswith((".KS", ".KQ")) else "USD"
        raw_pnl = float(s.pnl_at_close)
        raw_cost = float(s.shares or 0) * float(s.price or 0) - raw_pnl
        try:
            pnl_krw = fx_service.amount_to_krw(raw_pnl, currency, s.ticker, fx)
            cost_krw = fx_service.amount_to_krw(raw_cost, currency, s.ticker, fx)
        except (TypeError, ValueError):
            logger.debug("silent-fallback: _compute_twin_return fx", exc_info=True)
            pnl_krw, cost_krw = raw_pnl, raw_cost
        realized_pnl += Decimal(str(pnl_krw))
        cost_basis += Decimal(str(cost_krw))
    if cost_basis <= 0:
        return None, trade_count
    return float(round((realized_pnl / cost_basis) * 100, 4)), trade_count


def generate_weekly_report(
    user_id: int,
    week_ending: date | None = None,
    now: datetime | None = None,
) -> AITwinWeeklyReport:
    """Compute (or fetch) the weekly comparison row for a user.

    Idempotent — UNIQUE(user_id, week_ending) means a re-fired cron is
    a no-op (returns the existing row).
    """
    if week_ending is None:
        week_ending = (now or _utc_now_naive()).date() - timedelta(days=1)

    existing = (
        AITwinWeeklyReport.query
        .filter_by(user_id=user_id, week_ending=week_ending)
        .first()
    )
    if existing is not None:
        return existing

    user_pct, user_n = _compute_user_return(user_id, week_ending)
    twin_pct, twin_n = _compute_twin_return(user_id, week_ending)

    diff_pct: float | None = None
    if user_pct is not None and twin_pct is not None:
        diff_pct = round(twin_pct - user_pct, 4)

    rationale_summary = _summarize(user_pct, twin_pct, user_n, twin_n)

    row = AITwinWeeklyReport(
        user_id=user_id,
        week_ending=week_ending,
        user_return_pct=Decimal(str(user_pct)) if user_pct is not None else None,
        twin_return_pct=Decimal(str(twin_pct)) if twin_pct is not None else None,
        diff_pct=Decimal(str(diff_pct)) if diff_pct is not None else None,
        user_trades_count=user_n,
        twin_trades_count=twin_n,
        rationale_summary=rationale_summary,
    )
    db.session.add(row)
    db.session.commit()
    return row


def _summarize(
    user_pct: float | None,
    twin_pct: float | None,
    user_n: int,
    twin_n: int,
) -> str:
    """One-line, descriptive (never imperative) summary string."""
    parts = []
    if user_pct is None:
        parts.append("user: no closed trades")
    else:
        parts.append(f"user: {user_pct:+.2f}% over {user_n} trade(s)")
    if twin_pct is None:
        parts.append("twin (paper): no closed trades")
    else:
        parts.append(f"twin (paper): {twin_pct:+.2f}% over {twin_n} trade(s)")
    return "; ".join(parts)


__all__ = ["generate_weekly_report"]
