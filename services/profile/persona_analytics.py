"""Persona analytics — declared vs observed CFO persona.

Part of Living CFO Layer 2 (see reports/product/PERSONA_SPEC_2026-04-23.md
§2 persona mapping and frontend/src/lib/cfo/hooks.ts ``PersonaResponse``).

Pipeline
--------
1. ``declared`` persona is read straight from ``InvestmentProfile.profile_type``
   via :data:`DECLARED_TO_PERSONA`. This is deterministic — no ML guess.

2. ``observed`` persona is computed from the user's ``TradeHistory`` rows
   inside a rolling window (30 / 60 / 90 day). We build a 3-dimensional
   behavioural vector and pick the closest 8-persona centroid via cosine
   similarity. The three dimensions:

   - holding_period_norm : avg days held, normalised to [0, 1]
                           (0 = <1 day, 1 = >180 days)
   - turnover_norm       : trades per calendar day, normalised to [0, 1]
                           (0 = <0.02/day, 1 = >1/day)
   - sector_tilt         : 1 - HHI on sector exposure, capped at 1
                           (0 = everything in one sector, 1 = fully spread)

3. ``sparkline`` returns the last 12 weekly observed-persona scores.
   Missing weeks collapse to an empty list (degrade gracefully for
   brand-new users).

All outputs pass through float coercion — no ``nan`` / ``inf`` leaks to
the JSON response.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Iterable

from models import Position, TradeHistory, InvestmentProfile
from .common_util import sector_hhi, to_diversity_score, utc_now as _utc_now
from .fifo_util import fifo_match_closed_trades, fifo_open_position_ages
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Persona metadata — SSOT for label + tagline on the API response.
# Tagline phrasing copied verbatim from PERSONA_SPEC_2026-04-23.md §3
# "One-line identity" — already cleared by the 89-regex legal filter.
# ─────────────────────────────────────────────────────────────────────

PERSONA_CODES = (
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
)

PERSONA_LABELS = {
    "growth":     "Growth CFO",
    "value":      "Value CFO",
    "balanced":   "Balanced CFO",
    "income":     "Income CFO",
    "quant":      "Quant CFO",
    "speculator": "Speculator CFO",
    "daytrader":  "Daytrader CFO",
    "beginner":   "Beginner CFO",
}

PERSONA_TAGLINES = {
    "growth":     "내일의 승자를 오늘 담는다.",
    "value":      "시장이 틀렸다는 확신에 돈을 건다.",
    "balanced":   "극단이 아닌 일관성.",
    "income":     "월세처럼 들어오는 배당.",
    "quant":      "감이 아닌 검증된 엣지.",
    "speculator": "큰 변동성에서만 큰 수익.",
    "daytrader":  "오늘 안에 답을 낸다.",
    "beginner":   "이해하지 못한 것에 돈을 걸지 않는다.",
}

# ─────────────────────────────────────────────────────────────────────
# SURFACE labels — the ONLY persona naming the user ever sees.
#
# §101 compliance (DECISIONS.md ✅확정): the engine keeps all 8 persona
# codes for internal grouping / peer-benchmark cohorts, but the user-
# facing surface must never name a short-horizon persona (speculator /
# daytrader). We collapse 8 engine codes → 3 disclosed labels so no
# short-term trading style is ever called out by name.
#
#   성장형 (Growth)  ← growth · value · speculator · daytrader
#   균형형 (Balanced)← balanced · quant · beginner
#   수익형 (Income)  ← income
#
# CEO-approved mapping (2026-05-31): high risk-tolerance codes
# (speculator / daytrader) fold into 성장형 so the disclosed set stays a
# literal 3. Taglines drop any future-return implication ("큰 변동성에서만
# 큰 수익" etc.) — each bucket carries one neutral, observational line.
#
# PERSONA_LABELS / PERSONA_TAGLINES above are retained UNCHANGED for any
# internal / non-surface consumer; SURFACE_* is additive.
# ─────────────────────────────────────────────────────────────────────

PERSONA_TO_SURFACE: dict[str, str] = {
    "growth":     "growth",
    "value":      "growth",
    "speculator": "growth",
    "daytrader":  "growth",
    "balanced":   "balanced",
    "quant":      "balanced",
    "beginner":   "balanced",
    "income":     "income",
}

SURFACE_LABELS = {
    "growth":   "성장형",
    "balanced": "균형형",
    "income":   "수익형",
}

SURFACE_TAGLINES = {
    "growth":   "변동을 감수하며 자산 성장을 지향하는 흐름.",
    "balanced": "한쪽으로 치우치지 않는 일관된 흐름.",
    "income":   "꾸준한 현금흐름을 중심에 두는 흐름.",
}


def surface_label(persona_code: str) -> str:
    """Map any 8-code persona → its 3-bucket disclosed Korean label."""
    bucket = PERSONA_TO_SURFACE.get(persona_code, "balanced")
    return SURFACE_LABELS[bucket]


def surface_tagline(persona_code: str) -> str:
    """Map any 8-code persona → its 3-bucket disclosed tagline."""
    bucket = PERSONA_TO_SURFACE.get(persona_code, "balanced")
    return SURFACE_TAGLINES[bucket]

# ``profile_type`` column values currently observed in the wild
# (InvestmentProfile stores both the legacy 4-tier values and the
# questionnaire V2 persona codes).
DECLARED_TO_PERSONA: dict[str, str] = {
    # Legacy 4-tier (models/investment_profile.py PROFILE_PRESETS)
    "conservative":        "income",
    "balanced":            "balanced",
    "growth":              "growth",
    "aggressive":          "speculator",
    # Questionnaire V2 (questionnaire.py PROFILE_PRESETS_V2)
    "momentum_rider":      "growth",
    "value_hunter":        "value",
    "risk_managed_growth": "balanced",
    "passive_index_hugger": "income",
    "macro_rotator":       "quant",
    "swing_trader":        "speculator",
    "aggressive_scalper":  "daytrader",
    "steady_accumulator":  "beginner",
    # Already canonical persona codes — identity map so new writes
    # survive the resolver untouched.
    "value":      "value",
    "income":     "income",
    "quant":      "quant",
    "speculator": "speculator",
    "daytrader":  "daytrader",
    "beginner":   "beginner",
}


# ─────────────────────────────────────────────────────────────────────
# Persona centroids on the 3-D behavioural vector
# (holding_period_norm, turnover_norm, sector_tilt_norm).
# Hand-tuned from the persona spec; every coordinate in [0, 1].
# ─────────────────────────────────────────────────────────────────────

PERSONA_CENTROIDS: dict[str, tuple[float, float, float]] = {
    # very long hold, very low turnover, moderate tilt → Beginner / Income
    "beginner":   (0.85, 0.05, 0.55),
    "income":     (0.85, 0.10, 0.45),
    # long hold, low turnover, high diversification → Value
    "value":      (0.75, 0.12, 0.70),
    # medium-long hold, low turnover, high diversification → Balanced
    "balanced":   (0.55, 0.15, 0.85),
    # medium hold, medium turnover, concentrated → Growth
    "growth":     (0.45, 0.30, 0.45),
    # medium hold, medium turnover, high diversification → Quant
    "quant":      (0.40, 0.35, 0.80),
    # short hold, high turnover, concentrated → Speculator
    "speculator": (0.15, 0.70, 0.35),
    # intraday, very high turnover, very concentrated → Daytrader
    "daytrader":  (0.02, 0.95, 0.25),
}

# Legal sector fallback — when Position.ticker has no sector on file
# we bucket to "UNKNOWN". HHI still computes cleanly; a fully-unknown
# portfolio collapses sector_tilt to 0 (the right answer — no signal).
_UNKNOWN_SECTOR = "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────

def compute_persona_response(user_id: int, now: datetime | None = None) -> dict:
    """Return the full ``PersonaResponse`` payload for ``user_id``.

    Shape matches frontend ``PersonaResponse`` in
    ``frontend/src/lib/cfo/hooks.ts`` exactly.
    """
    now = _utc_now() if now is None else now
    profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
    declared_code = _resolve_declared(profile)
    declared_score = _declared_score(profile)

    trades = _fetch_trades(user_id)
    positions = _fetch_positions(user_id)
    sector_map = _sector_map_from_positions(positions)

    observed = {
        f"window_{d}d": _observed_for_window(trades, sector_map, d, now)
        for d in (30, 60, 90)
    }

    sparkline = _sparkline(trades, sector_map, now, weeks=12)
    drift = _drift(declared_code, declared_score, observed["window_30d"])

    return {
        "declared": {
            # `persona` stays the 8-code for engine grouping; the user-
            # facing label/tagline collapse to the 3 disclosed buckets
            # (§101 — never name a short-horizon persona).
            "persona": declared_code,
            "label": surface_label(declared_code),
            "tagline": surface_tagline(declared_code),
            "score": int(declared_score),
        },
        "observed": observed,
        "sparkline": sparkline,
        "last_computed_at": now.isoformat(),
        "drift": int(drift),
    }


# ─────────────────────────────────────────────────────────────────────
# Declared persona resolver
# ─────────────────────────────────────────────────────────────────────

def _resolve_declared(profile: InvestmentProfile | None) -> str:
    if profile is None:
        return "balanced"
    code = DECLARED_TO_PERSONA.get((profile.profile_type or "").lower(), "balanced")
    return code if code in PERSONA_CODES else "balanced"


def _declared_score(profile: InvestmentProfile | None) -> float:
    """Derive a 0-100 confidence score for the declared persona.

    We reuse ``risk_tolerance`` (1-10) as a proxy since it's the only
    onboarding answer with linear semantics. If missing → 60 (neutral).
    """
    if profile is None or profile.risk_tolerance is None:
        return 60.0
    rt = max(1, min(10, int(profile.risk_tolerance)))
    # Map 1..10 → ~35..95 so the displayed score never feels like a failure.
    return 25.0 + rt * 7.0


# ─────────────────────────────────────────────────────────────────────
# Trade + Position loaders
# ─────────────────────────────────────────────────────────────────────

def _fetch_trades(user_id: int) -> list[TradeHistory]:
    return (
        TradeHistory.query
        .filter_by(user_id=user_id)
        .order_by(TradeHistory.traded_at.asc())
        .all()
    )


def _fetch_positions(user_id: int) -> list[Position]:
    return Position.query.filter_by(user_id=user_id).all()


def _sector_map_from_positions(positions: Iterable[Position]) -> dict[str, str]:
    """Approximate a ticker → sector map without hitting external APIs.

    Position model has no sector column; we ship with ``UNKNOWN`` and let
    the HHI collapse cleanly. A future enhancement can plug in
    ``services/us_stock_registry`` + ``kr_stock_registry`` here — this
    function is the single injection point.
    """
    mapping: dict[str, str] = {}
    for p in positions:
        mapping[p.ticker.upper()] = _UNKNOWN_SECTOR
    try:
        from services.kr_stock_registry import get_sector as _kr_sector  # type: ignore
    except Exception:  # pragma: no cover — registry optional
        _kr_sector = None
    if _kr_sector is not None:
        for ticker in list(mapping.keys()):
            try:
                sec = _kr_sector(ticker)
                if sec:
                    mapping[ticker] = sec
            except Exception:
                logger.debug("silent-fallback: _sector_map_from_positions", exc_info=True)
                pass
    return mapping


# ─────────────────────────────────────────────────────────────────────
# Observed persona per window
# ─────────────────────────────────────────────────────────────────────

def _observed_for_window(
    trades: list[TradeHistory],
    sector_map: dict[str, str],
    window_days: int,
    now: datetime,
) -> dict:
    """Classify behaviour in the last ``window_days`` into a persona + score."""
    cutoff = now - timedelta(days=window_days)
    window_trades = [t for t in trades if t.traded_at and t.traded_at >= cutoff]

    # Empty window → neutral balanced, low confidence.
    if not window_trades:
        return {
            "date": (now - timedelta(days=window_days)).date().isoformat(),
            "persona": "balanced",
            "score": 0,
        }

    vec = _behaviour_vector(window_trades, sector_map, window_days)
    persona, similarity = _nearest_centroid(vec)

    # similarity ∈ [−1, 1]; remap to 0..100 with a light floor so sparse
    # data still plots above zero.
    score = max(0.0, min(100.0, (similarity + 1.0) * 50.0))

    return {
        "date": now.date().isoformat(),
        "persona": persona,
        "score": int(round(score)),
    }


def _behaviour_vector(
    trades: list[TradeHistory],
    sector_map: dict[str, str],
    window_days: int,
) -> tuple[float, float, float]:
    # 1) avg holding period — pair each SELL with the earliest open BUY
    #    on the same ticker (FIFO). Unmatched positions contribute 0.
    holding_days = _avg_holding_period(trades)
    holding_norm = _norm_log(holding_days, floor=1.0, ceil=180.0)

    # 2) turnover — trades per calendar day in the window
    per_day = len(trades) / max(window_days, 1)
    turnover_norm = _norm_log(per_day, floor=0.02, ceil=1.0)

    # 3) sector tilt — 1 - HHI of shares-weighted sector exposure
    sector_norm = _sector_diversification(trades, sector_map)

    return (holding_norm, turnover_norm, sector_norm)


def _avg_holding_period(trades: list[TradeHistory]) -> float:
    """FIFO-match BUY/SELL pairs per ticker; return mean hold in days.

    Implementation delegates to :func:`fifo_util.fifo_match_closed_trades`
    so all four legacy copies of this loop now produce identical results.
    """
    pairs = fifo_match_closed_trades(trades)
    if pairs:
        return sum(p.hold_days for p in pairs) / len(pairs)
    # Fallback: average elapsed time of still-open positions. The util
    # picks the latest ``traded_at`` as the reference (deterministic);
    # only an empty trade list lands on ``utcnow``.
    elapsed = fifo_open_position_ages(trades)
    if not elapsed:
        return 0.0
    return sum(elapsed) / len(elapsed)


def _sector_diversification(
    trades: list[TradeHistory],
    sector_map: dict[str, str],
) -> float:
    """1 - HHI on traded-volume weighted sector exposure, in [0, 1]."""
    volume_by_sector: dict[str, float] = {}
    for t in trades:
        sector = sector_map.get((t.ticker or "").upper(), _UNKNOWN_SECTOR)
        amount = abs(float(t.total_value or 0.0)) or abs(float(t.shares or 0.0))
        if amount <= 0:
            continue
        volume_by_sector[sector] = volume_by_sector.get(sector, 0.0) + amount
    return to_diversity_score(sector_hhi(volume_by_sector))


def _nearest_centroid(vec: tuple[float, float, float]) -> tuple[str, float]:
    """Return (persona, cosine_similarity) to the nearest centroid."""
    best = ("balanced", -1.0)
    for persona, centroid in PERSONA_CENTROIDS.items():
        sim = _cosine(vec, centroid)
        if sim > best[1]:
            best = (persona, sim)
    return best


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _norm_log(value: float, *, floor: float, ceil: float) -> float:
    """Log-normalise ``value`` into [0, 1] between ``floor`` and ``ceil``.

    Uses log-scale because holding period and turnover span 2+ decades.
    """
    if value <= floor or ceil <= floor:
        return 0.0
    if value >= ceil:
        return 1.0
    return math.log(value / floor) / math.log(ceil / floor)


# ─────────────────────────────────────────────────────────────────────
# Sparkline + drift
# ─────────────────────────────────────────────────────────────────────

def _sparkline(
    trades: list[TradeHistory],
    sector_map: dict[str, str],
    now: datetime,
    weeks: int,
) -> list[dict]:
    """Weekly observed-persona scores for the last ``weeks`` weeks."""
    if not trades:
        return []
    out: list[dict] = []
    for i in range(weeks):
        # Each week's window ends on (now - i*7d), with a 30d lookback
        # so the score is not dominated by sparse single-trade weeks.
        end = now - timedelta(days=7 * i)
        start = end - timedelta(days=30)
        window = [t for t in trades if t.traded_at and start <= t.traded_at < end]
        if not window:
            continue
        vec = _behaviour_vector(window, sector_map, 30)
        _persona, sim = _nearest_centroid(vec)
        score = max(0.0, min(100.0, (sim + 1.0) * 50.0))
        out.append({
            "week": end.date().isoformat(),
            "score": int(round(score)),
        })
    # Oldest first, newest last.
    out.reverse()
    return out


def _drift(declared_code: str, declared_score: float, observed_30d: dict) -> float:
    observed_score = float(observed_30d.get("score") or 0)
    observed_persona = observed_30d.get("persona")
    # When observed has no data, drift is 0 — avoid false alarms on
    # brand-new users.
    if observed_score <= 0:
        return 0.0
    # Penalise large score gaps AND persona mismatches.
    gap = abs(float(declared_score) - observed_score)
    if observed_persona != declared_code:
        gap = min(100.0, gap + 15.0)
    return max(0.0, min(100.0, gap))


# ``_utc_now`` is now an alias for the canonical implementation in
# :mod:`services.profile.common_util`. Kept here for the (small number
# of) external imports that reference the symbol directly.
__all__ = [
    "compute_persona_response",
    "PERSONA_CODES",
    "PERSONA_LABELS",
    "PERSONA_TAGLINES",
    "PERSONA_TO_SURFACE",
    "SURFACE_LABELS",
    "SURFACE_TAGLINES",
    "surface_label",
    "surface_tagline",
    "DECLARED_TO_PERSONA",
    "PERSONA_CENTROIDS",
]
