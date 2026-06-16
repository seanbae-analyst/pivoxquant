"""Rolling-window behavioural metrics — Living CFO Layer 2.

Produces the ``RollingWindowResponse`` payload defined in
``frontend/src/lib/cfo/hooks.ts``:

    series.window_{30,60,90}d : list[RollingWindowPoint]
    contrast                  : declared-vs-observed summary

Each ``RollingWindowPoint`` carries:
    date          — ISO yyyy-mm-dd (the end of the rolling lookback)
    holdingPeriod — avg days held (FIFO-matched round trips, fallback
                    = elapsed time since first open BUY)
    turnover      — trades per day in the lookback window (0..1, capped)
    sectorTilt    — 1 - HHI on sector-weighted traded volume (0..1)

We use **pandas** so the rolling logic is a single one-liner per metric.
Pandas is already a project dep (``requirements.txt``) — reuse the
shared import rather than pulling in numpy by hand.

Design notes
------------
- No external API calls. Sector comes from the position registry
  lookups when available, otherwise falls back to ``UNKNOWN`` (same
  contract as persona_analytics).
- The ``series`` for a given window is one data point per day for the
  last ``window_days`` days. Missing days — no pandas fill — simply
  don't appear in the list (the frontend handles gaps).
- Empty data path: returns ``{"series": {30:[], 60:[], 90:[]}, contrast:{…}}``.
  The route still ships HTTP 200 so the frontend can degrade gracefully.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

import pandas as pd

from models import TradeHistory, InvestmentProfile
from .common_util import sector_hhi, utc_now as _utc_now
from .fifo_util import fifo_match_closed_trades, fifo_open_position_ages
from .persona_analytics import (
    DECLARED_TO_PERSONA,
    PERSONA_CODES,
    _behaviour_vector,
    _declared_score,
    _fetch_trades,
    _fetch_positions,
    _nearest_centroid,
    _resolve_declared,
    _sector_map_from_positions,
)


def compute_rolling_response(user_id: int, now: datetime | None = None) -> dict:
    """Return the full ``RollingWindowResponse`` payload for ``user_id``."""
    now = _utc_now() if now is None else now
    profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
    declared_code = _resolve_declared(profile)
    declared_score = _declared_score(profile)

    trades = _fetch_trades(user_id)
    positions = _fetch_positions(user_id)
    sector_map = _sector_map_from_positions(positions)

    # Daily dataframe — one row per trade, indexed by date only.
    df = _trades_to_frame(trades, sector_map)

    series = {
        f"window_{d}d": _rolling_series(df, trades, sector_map, window_days=d, now=now)
        for d in (30, 60, 90)
    }

    # Contrast summary uses the 30d observed vector, falling back to
    # balanced / 0 for brand-new users.
    if trades:
        window_trades = [
            t for t in trades
            if t.traded_at and t.traded_at >= now - timedelta(days=30)
        ]
        if window_trades:
            vec = _behaviour_vector(window_trades, sector_map, 30)
            observed_persona, sim = _nearest_centroid(vec)
            observed_score = max(0.0, min(100.0, (sim + 1.0) * 50.0))
        else:
            observed_persona, observed_score = "balanced", 0.0
    else:
        observed_persona, observed_score = "balanced", 0.0

    return {
        "series": series,
        "contrast": {
            "declared_persona": declared_code,
            "declared_score": int(declared_score),
            "observed_persona": observed_persona if observed_persona in PERSONA_CODES else "balanced",
            "observed_score": int(round(observed_score)),
            "window_days": 30,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# pandas plumbing
# ─────────────────────────────────────────────────────────────────────

def _trades_to_frame(
    trades: Iterable[TradeHistory],
    sector_map: dict[str, str],
) -> pd.DataFrame:
    rows = []
    for t in trades:
        if not t.traded_at:
            continue
        rows.append({
            "date": pd.Timestamp(t.traded_at).normalize(),
            "ticker": (t.ticker or "").upper(),
            "action": (t.action or "").upper(),
            "shares": float(t.shares or 0.0),
            "volume": abs(float(t.total_value or 0.0)) or abs(float(t.shares or 0.0)),
            "sector": sector_map.get((t.ticker or "").upper(), "UNKNOWN"),
        })
    if not rows:
        return pd.DataFrame(columns=["date", "ticker", "action", "shares", "volume", "sector"])
    return pd.DataFrame(rows)


def _rolling_series(
    df: pd.DataFrame,
    trades: list[TradeHistory],
    sector_map: dict[str, str],
    *,
    window_days: int,
    now: datetime,
) -> list[dict]:
    """One ``RollingWindowPoint`` per day across ``window_days``."""
    if df.empty or not trades:
        return []

    now_ts = pd.Timestamp(now).normalize()
    out: list[dict] = []

    # Precompute trade list once per day-slice in python (simple + clear
    # and fast enough for 90 days × ~dozens of trades). Using a
    # bona-fide pandas rolling would require a resampled series per
    # metric; the bespoke loop keeps the three metrics aligned.
    trades_sorted = [t for t in trades if t.traded_at]
    trades_sorted.sort(key=lambda x: x.traded_at)

    for i in range(window_days):
        day_end = (now_ts - pd.Timedelta(days=i)).to_pydatetime()
        day_start = day_end - timedelta(days=window_days)

        window_trades = [t for t in trades_sorted if day_start <= t.traded_at < day_end]
        if not window_trades:
            continue

        holding_period = _holding_period_days(window_trades)
        turnover = _turnover(window_trades, window_days)
        sector_tilt = _sector_tilt_hhi(window_trades, sector_map)

        out.append({
            "date": day_end.date().isoformat(),
            "holdingPeriod": _round_float(holding_period, ndigits=2),
            "turnover": _round_float(turnover, ndigits=3),
            "sectorTilt": _round_float(sector_tilt, ndigits=3),
        })

    # Oldest first so the chart draws left-to-right.
    out.reverse()
    return out


# ─────────────────────────────────────────────────────────────────────
# Metric kernels (same semantics as persona_analytics but returned raw)
# ─────────────────────────────────────────────────────────────────────

def _holding_period_days(trades: list[TradeHistory]) -> float:
    """FIFO-match BUY/SELL per ticker; mean days held.

    Delegates to :mod:`fifo_util` so this module agrees byte-for-byte
    with the other 3 callers. Fallback policy: ``trades[-1].traded_at``
    is preferred over ``utcnow`` (canonicalised in ``fifo_util``).
    """
    pairs = fifo_match_closed_trades(trades)
    if pairs:
        return sum(p.hold_days for p in pairs) / len(pairs)
    elapsed = fifo_open_position_ages(trades)
    return sum(elapsed) / len(elapsed) if elapsed else 0.0


def _turnover(trades: list[TradeHistory], window_days: int) -> float:
    per_day = len(trades) / max(window_days, 1)
    return max(0.0, min(1.0, per_day))


def _sector_tilt_hhi(
    trades: list[TradeHistory],
    sector_map: dict[str, str],
) -> float:
    """HHI on traded-volume weighted sector exposure (higher = more tilt)."""
    # Pattern-7 fix (2026-06-15): total_value is in the trade's NATIVE currency
    # (₩ for .KS/.KQ, $ otherwise). Raw-summing across currencies let a ₩-scale
    # KR position dominate the sector weights, distorting the HHI for any mixed
    # US+KR book. Normalize each leg to KRW first. HHI is scale-invariant, so a
    # single-currency book is unaffected (the common case); only mixed books
    # are corrected.
    from services import fx_service

    fx = fx_service.get_rate()
    volume_by_sector: dict[str, float] = {}
    for t in trades:
        sector = sector_map.get((t.ticker or "").upper(), "UNKNOWN")
        money = abs(float(t.total_value or 0.0))
        if money > 0:
            try:
                amount = fx_service.amount_to_krw(money, t.currency, t.ticker, fx)
            except (TypeError, ValueError):
                amount = money
        else:
            # No traded value — fall back to raw share count (a currency-
            # agnostic rough proxy; a count cannot be FX-normalized).
            amount = abs(float(t.shares or 0.0))
        if amount <= 0:
            continue
        volume_by_sector[sector] = volume_by_sector.get(sector, 0.0) + amount
    return sector_hhi(volume_by_sector)


def _round_float(value: float, *, ndigits: int) -> float:
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return 0.0


# Keep symbols referenced by tests happy.
__all__ = [
    "compute_rolling_response",
    "DECLARED_TO_PERSONA",
]
