"""Twin runner — daily paper decisions for Feature 5.

LEGAL POSTURE (자본시장법 §17 회피)
------------------------------------
This whole module is a **self-analysis tool**. The Twin runs paper
trades that the user can review AFTER the fact ("you held PLTR; the
Twin (acting as a 'quant' persona) bought it 4 days earlier"). It is
**not** an advisory feed — no prospective signal ever leaves this
module.

Hard rules
----------
1. No broker call. Ever. The only outbound side-effects are:
   - DB inserts/updates against ``ai_twin_*`` tables.
   - Read-only price fetches via ``services.container.engine`` /
     ``services.container.fetcher`` (FMP / KIS quote — read-only
     paths the rest of the codebase already uses).
2. ``is_paper`` is hard-coded ``True`` on every ``AITwinTrade`` insert.
3. ``side`` values are paper labels — they MUST NEVER be surfaced to
   the user as a directive. Routes are responsible for relabelling.
4. Output is descriptive only ("paper bought NVDA at 480.32") — no
   imperative copy ("you should buy NVDA").
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from extensions import db
from models import (
    AITwinPortfolio,
    AITwinPosition,
    AITwinTrade,
    DEFAULT_STARTING_CASH,
    InvestmentProfile,
)
from services import container as svc
from services.profile.persona_classifier_v2 import classify_persona_multi

logger = logging.getLogger(__name__)


# ── Persona policy table ───────────────────────────────────────────────
# Each persona maps to a tuple of paper-trading parameters. Numbers are
# deliberately conservative for the launch build — the legal review can
# tighten these later without touching the call sites.

# Position sizing (fraction of CURRENT cash) when opening a paper buy.
PERSONA_POSITION_SIZING: dict[str, float] = {
    "beginner":   0.05,
    "income":     0.06,
    "balanced":   0.08,
    "value":      0.08,
    "growth":     0.10,
    "quant":      0.10,
    "speculator": 0.15,
    "daytrader":  0.12,
}

# Composite-score floor for a paper buy — picked to mirror
# investment_profile.PROFILE_PRESETS where comparable.
PERSONA_BUY_THRESHOLD: dict[str, float] = {
    "beginner":   75.0,
    "income":     72.0,
    "balanced":   70.0,
    "value":      70.0,
    "growth":     67.0,
    "quant":      68.0,
    "speculator": 60.0,
    "daytrader":  62.0,
}

# Take-profit / stop-loss percentages on the entry price.
PERSONA_TP_PCT: dict[str, float] = {
    "beginner":   7.0,
    "income":     8.0,
    "balanced":   12.0,
    "value":      15.0,
    "growth":     18.0,
    "quant":      14.0,
    "speculator": 25.0,
    "daytrader":  4.0,
}
PERSONA_SL_PCT: dict[str, float] = {
    "beginner":   3.0,
    "income":     4.0,
    "balanced":   6.0,
    "value":      8.0,
    "growth":     10.0,
    "quant":      8.0,
    "speculator": 12.0,
    "daytrader":  3.0,
}

# Max holding period (days). 0 = no time-stop. daytrader closes intra-day.
PERSONA_MAX_HOLDING_DAYS: dict[str, int] = {
    "beginner":   60,
    "income":     180,
    "balanced":   90,
    "value":      365,
    "growth":     90,
    "quant":      45,
    "speculator": 14,
    "daytrader":  1,
}

# Paper universe is the engine's existing DISCOVER_POOL — same tickers
# the rest of the app already pre-warms via FMP. We never reach beyond
# this list, which keeps the FMP budget contained and means the Twin
# can never trade something outside the user's existing risk surface.
DEFAULT_UNIVERSE: tuple[str, ...] = tuple()  # populated lazily in _scan_universe


# Smallest paper share-count we'll book — guards against penny rounding
# noise creating zero-share positions when cash is very low.
_MIN_PAPER_SHARES = Decimal("0.0001")


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _resolve_persona(user_id: int) -> str:
    """Best-effort persona classification for the runner.

    Falls back to the user's declared profile (or 'balanced') when the
    classifier raises — the cron must NEVER fail an entire user just
    because their persona feature vector is degenerate.
    """
    try:
        result = classify_persona_multi(user_id, window_days=90)
        return str(result.get("persona") or "balanced")
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Twin: persona classify failed user=%s err=%s", user_id, exc)
        prof = InvestmentProfile.query.filter_by(user_id=user_id).first()
        return getattr(prof, "profile_type", None) or "balanced"


# ─────────────────────────────────────────────────────────────────────
# Public — initialization
# ─────────────────────────────────────────────────────────────────────


def initialize_twin(user_id: int) -> AITwinPortfolio:
    """Idempotent. Creates a $10,000 paper twin for ``user_id`` if one
    does not already exist; returns the existing row otherwise.

    This is the ONLY write path that may insert into
    ``ai_twin_portfolios``. The UNIQUE(user_id) constraint at the DB
    layer is the second line of defence.
    """
    existing = AITwinPortfolio.query.filter_by(user_id=user_id).first()
    if existing is not None:
        return existing

    persona = _resolve_persona(user_id)
    twin = AITwinPortfolio(
        user_id=user_id,
        initialized_at=_utc_now_naive(),
        starting_cash=DEFAULT_STARTING_CASH,
        current_cash=DEFAULT_STARTING_CASH,
        persona_at_init=persona,
        is_active=True,
    )
    db.session.add(twin)
    db.session.commit()
    return twin


# ─────────────────────────────────────────────────────────────────────
# Public — daily decision pass
# ─────────────────────────────────────────────────────────────────────


@dataclass
class _ScoredCandidate:
    ticker: str
    composite_score: float
    price: float
    rationale: str


def _engine_universe() -> list[str]:
    """Resolve the paper universe. Centralised so tests can patch it."""
    try:
        from engine import QuantEngine
        return list(QuantEngine.DISCOVER_POOL)
    except Exception:
        return list(DEFAULT_UNIVERSE)


def _score_universe(persona: str, candidates: Iterable[str]) -> list[_ScoredCandidate]:
    """Score each candidate ticker via the existing read-only engine.

    Skips any ticker the engine cannot price (returns ``None``). Logs
    and continues on per-ticker exceptions so one broken FMP response
    cannot poison the whole run.
    """
    out: list[_ScoredCandidate] = []
    engine = svc.engine
    for ticker in candidates:
        try:
            result = engine.analyze(ticker, capital_usd=10_000.0)
        except Exception as exc:
            logger.debug("Twin: engine.analyze raised on %s: %s", ticker, exc)
            continue
        if not result:
            continue
        composite = float(
            result.get("composite_score")
            or result.get("score")
            or 0.0
        )
        price = float(result.get("price") or 0.0)
        if price <= 0:
            continue
        rationale = str(result.get("signal") or result.get("rationale") or "engine")
        out.append(_ScoredCandidate(
            ticker=ticker,
            composite_score=composite,
            price=price,
            rationale=f"persona={persona}; engine={rationale}",
        ))
    out.sort(key=lambda c: c.composite_score, reverse=True)
    return out


def _position_sizing(persona: str, score: float, cash: Decimal) -> Decimal:
    """Cash to allocate on a paper buy.

    Equal-weight by default with a tiny score-bonus (Kelly-lite). Caps
    at 25% of cash so a single buy can never starve the rest.
    """
    base = Decimal(str(PERSONA_POSITION_SIZING.get(persona, 0.08)))
    # Score bonus: 0.5x at 60, 1.0x at 75, 1.4x at 95.
    if score >= 95:
        mult = Decimal("1.4")
    elif score >= 85:
        mult = Decimal("1.2")
    elif score >= 70:
        mult = Decimal("1.0")
    else:
        mult = Decimal("0.7")
    fraction = base * mult
    if fraction > Decimal("0.25"):
        fraction = Decimal("0.25")
    if fraction < Decimal("0.01"):
        fraction = Decimal("0.01")
    return (cash * fraction).quantize(Decimal("0.0001"))


def _close_check(
    twin: AITwinPortfolio,
    persona: str,
    now: datetime,
) -> list[AITwinTrade]:
    """Apply TP/SL/holding-period exits. Returns the paper sells written."""
    sells: list[AITwinTrade] = []
    tp_pct = PERSONA_TP_PCT.get(persona, 12.0)
    sl_pct = PERSONA_SL_PCT.get(persona, 6.0)
    max_hold = PERSONA_MAX_HOLDING_DAYS.get(persona, 90)

    for pos in list(twin.positions):
        try:
            snap = svc.fetcher.get_stock_snapshot(pos.ticker)
        except Exception as exc:
            logger.debug("Twin close_check snapshot failed %s: %s", pos.ticker, exc)
            continue
        if not snap or not snap.get("price"):
            continue
        price_now = Decimal(str(snap["price"]))
        cost = Decimal(str(pos.avg_cost or 0))
        if cost <= 0:
            continue
        pnl_pct = float((price_now - cost) / cost * 100)
        held_days = (now - pos.opened_at).days if pos.opened_at else 0

        reason = None
        if pnl_pct >= tp_pct:
            reason = f"TP hit (+{pnl_pct:.1f}% >= +{tp_pct:.1f}%)"
        elif pnl_pct <= -sl_pct:
            reason = f"SL hit ({pnl_pct:.1f}% <= -{sl_pct:.1f}%)"
        elif max_hold > 0 and held_days >= max_hold:
            reason = f"Time stop (held {held_days}d >= {max_hold}d)"

        if reason is None:
            continue

        proceeds = price_now * pos.shares
        pnl_at_close = proceeds - (cost * pos.shares)
        twin.current_cash = (Decimal(str(twin.current_cash or 0)) + proceeds).quantize(
            Decimal("0.0001")
        )
        sell = AITwinTrade(
            twin_id=twin.id,
            ticker=pos.ticker,
            side="SELL",
            shares=pos.shares,
            price=price_now.quantize(Decimal("0.0001")),
            executed_at=now,
            rationale=f"paper exit — persona={persona}; {reason}",
            composite_score=None,
            pnl_at_close=pnl_at_close.quantize(Decimal("0.0001")),
            is_paper=True,
        )
        db.session.add(sell)
        sells.append(sell)
        # Remove the open position — fully closed.
        db.session.delete(pos)
    return sells


def run_twin_decisions(
    user_id: int,
    now: datetime | None = None,
    universe: Iterable[str] | None = None,
) -> dict:
    """Run one daily decision pass for ``user_id``.

    Steps (in order):
      1. Resolve the user's CURRENT persona (Feature 1+).
      2. Run TP/SL/time-stop checks against open positions (paper sells).
      3. Score the universe via the read-only engine.
      4. Open paper buys for top-N candidates whose composite >=
         the persona's buy threshold and that aren't already held.
      5. Update ``last_decision_at`` so the read endpoints have a
         public clock.

    Returns a small summary dict — opaque to the user, used only by
    cron logs / tests.
    """
    twin = AITwinPortfolio.query.filter_by(user_id=user_id).first()
    if twin is None or not twin.is_active:
        return {"skipped": True, "reason": "no_twin_or_inactive"}

    now = now or _utc_now_naive()
    persona = _resolve_persona(user_id)

    sells = _close_check(twin, persona, now)

    candidates = list(universe) if universe is not None else _engine_universe()
    scored = _score_universe(persona, candidates)

    threshold = PERSONA_BUY_THRESHOLD.get(persona, 70.0)
    held_tickers = {p.ticker for p in twin.positions}
    buys: list[AITwinTrade] = []

    # Cap buys per pass — keeps the FMP budget bounded and prevents the
    # Twin from clearing its cash on a single day.
    max_buys_per_pass = 3

    for cand in scored:
        if cand.composite_score < threshold:
            break  # scored desc — anything below threshold stays below
        if cand.ticker in held_tickers:
            continue
        cash = Decimal(str(twin.current_cash or 0))
        if cash <= Decimal("100"):  # never drain to zero
            break
        alloc = _position_sizing(persona, cand.composite_score, cash)
        if alloc <= 0:
            continue
        price = Decimal(str(cand.price))
        shares = (alloc / price).quantize(Decimal("0.0001"))
        if shares < _MIN_PAPER_SHARES:
            continue

        twin.current_cash = (cash - (price * shares)).quantize(Decimal("0.0001"))
        # Re-check we didn't go negative due to rounding.
        if Decimal(str(twin.current_cash)) < 0:
            twin.current_cash = cash  # rollback
            continue

        new_pos = AITwinPosition(
            twin_id=twin.id,
            ticker=cand.ticker,
            shares=shares,
            avg_cost=price,
            opened_at=now,
        )
        db.session.add(new_pos)
        held_tickers.add(cand.ticker)

        buy = AITwinTrade(
            twin_id=twin.id,
            ticker=cand.ticker,
            side="BUY",
            shares=shares,
            price=price,
            executed_at=now,
            rationale=cand.rationale,
            composite_score=Decimal(str(round(cand.composite_score, 2))),
            pnl_at_close=None,
            is_paper=True,
        )
        db.session.add(buy)
        buys.append(buy)

        if len(buys) >= max_buys_per_pass:
            break

    twin.last_decision_at = now
    db.session.commit()

    return {
        "user_id": user_id,
        "persona": persona,
        "buys": len(buys),
        "sells": len(sells),
        "remaining_cash": float(twin.current_cash or 0),
        "now": now.isoformat(),
    }


__all__ = [
    "initialize_twin",
    "run_twin_decisions",
    "PERSONA_POSITION_SIZING",
    "PERSONA_BUY_THRESHOLD",
    "PERSONA_TP_PCT",
    "PERSONA_SL_PCT",
    "PERSONA_MAX_HOLDING_DAYS",
]
