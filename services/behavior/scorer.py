# DEPRECATED 2026-05-30: AI 점수화 폐기(DECISIONS). 크론·API 비활성. 물리 컬럼
# drop 은 prod self-heal 함정 때문에 careful 마이그레이션으로 후속. 거울/export/
# persona benchmark 호환 위해 모델 보존.
"""Weekly behavioural-score computation — Feature 7.

Five sub-scores (each 0-100), weighted into one ``overall_score`` per
ISO week (Mon-Sun, ``week_ending`` = Sunday). All numbers are
*observational*; the natural-language ``notes`` text is filtered
through the canonical forbidden-terms blocklist before persistence.

Sub-scores
----------
1. ``holding_discipline``  — average days held vs. the user's persona's
   typical holding period. Closer to (or above) the persona target ⇒
   higher score.
2. ``loss_cut``            — average days from open to a losing close
   (FIFO-matched). Faster cuts ⇒ higher score.
3. ``position_sizing``     — single largest position as a share of
   portfolio value. Smaller concentration ⇒ higher score.
4. ``fomo_resistance``     — fraction of buys that fired the day after a
   ≥5% intraday move on the same ticker. Lower ⇒ higher score.
5. ``reflection_rate``     — share of trades that had a PreTradeReflection
   tied to them, weighted by rationale length. Higher ⇒ higher score.

Weighting rationale — equal across the five for now (0.20 each). The
weights are exposed as a module constant so tests + cron can reason
about them; tuning is a future product call.

Legal stance
------------
- All five sub-scores describe what *was* done, never what *should be*
  done.
- ``persona_avg`` only surfaces when the same-persona group has at
  least ``MIN_GROUP_SIZE`` users (we read ``persona_group_stats`` —
  same legal floor used elsewhere).
- The free-text ``notes`` is generated, scrubbed by ``safe_scrub``,
  and asserted clean against ``services.legal.forbidden_terms``
  before being saved.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from extensions import db
from models import (
    BehavioralScore,
    InvestmentProfile,
    Position,
    PreTradeReflection,
    SUB_SCORE_KEYS,
    TradeHistory,
)
from services import fx_service
from services.legal.forbidden_terms import (
    contains_forbidden_term,
)
from services.legal_filter import safe_scrub
from services.profile.fifo_util import (
    fifo_match_closed_trades,
    fifo_open_position_ages,
)

logger = logging.getLogger(__name__)


# Equal weights across the 5 sub-scores. Sum to 1.0.
WEIGHTS = {k: 0.20 for k in SUB_SCORE_KEYS}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


# Persona → "expected average holding period in days" used as the
# anchor for ``holding_discipline``. Numbers are intentionally broad
# — closer-than-half ⇒ score 100, more than 2x off ⇒ score 0, linear
# in between. Source: services.profile.persona_analytics intent.
PERSONA_HOLDING_DAYS = {
    "growth":     90.0,
    "value":     180.0,
    "balanced":   60.0,
    "income":    180.0,
    "quant":      30.0,
    "speculator": 14.0,
    "daytrader":   1.0,
    "beginner":   30.0,
}

# Big-move threshold for FOMO scoring (% intraday move on the buy day).
FOMO_THRESHOLD_PCT = 5.0

# Aspirational rationale length used as the upper bound for
# reflection_rate's "depth" component.
RATIONALE_TARGET_CHARS = 200

# Anchor for sizing scoring — concentration up to this share of portfolio
# is "perfect", scaling linearly to 0 at 1.0 (everything in one name).
SIZING_TARGET_SHARE = 0.10


# ────────────────────────────────────────────────────────────────────
# Public surface
# ────────────────────────────────────────────────────────────────────

def compute_weekly_score(
    user_id: int,
    week_ending: date | None = None,
    *,
    persist: bool = True,
) -> dict:
    """Compute one weekly score for a single user.

    Parameters
    ----------
    user_id : int
        Owning user.
    week_ending : date | None
        Sunday (inclusive) of the target week. Defaults to the most
        recent Sunday <= today.
    persist : bool
        When ``True`` (default), upsert a row in ``behavioral_scores``.
        Tests pass ``False`` to inspect without writing.

    Returns
    -------
    dict — see ``BehavioralScore.to_dict()``.
    """
    end = week_ending or _last_sunday(_utc_today())
    start = end - timedelta(days=6)
    week_start_dt = datetime.combine(start, time.min)
    week_end_dt = datetime.combine(end, time.max)

    trades = _trades_in_window(user_id, week_start_dt, week_end_dt)
    # All trades up to end-of-week — used for holding-period scoring,
    # which needs both legs of a round trip even when the buy is older.
    all_trades = _trades_through(user_id, week_end_dt)

    persona = _resolve_persona(user_id)

    sub = {
        "holding_discipline": _holding_discipline_subscore(all_trades, persona),
        "loss_cut": _loss_cut_subscore(all_trades),
        "position_sizing": _position_sizing_subscore(user_id),
        "fomo_resistance": _fomo_resistance_subscore(trades),
        "reflection_rate": _reflection_rate_subscore(
            user_id, week_start_dt, week_end_dt, trades
        ),
    }

    overall = _overall_weighted_average(sub)
    persona_avg = _persona_avg_with_floor(persona)
    notes = _observational_note(sub, persona, persona_avg)

    if persist:
        _upsert(
            user_id=user_id,
            week_ending=end,
            overall=overall,
            sub_scores=sub,
            persona_avg=persona_avg,
            notes=notes,
            trade_count=len(trades),
        )

    return {
        "user_id": user_id,
        "week_ending": end.isoformat(),
        "overall_score": overall,
        "sub_scores": sub,
        "persona_avg": persona_avg,
        "notes": notes,
        "trade_count": len(trades),
    }


def run_weekly_for_all_users(week_ending: date | None = None) -> dict:
    """Cron entry-point — score every user with at least one trade in the week.

    Returns a ``{processed, errors}`` summary so the scheduler log line
    is self-describing.
    """
    end = week_ending or _last_sunday(_utc_today())
    start = end - timedelta(days=6)
    week_start_dt = datetime.combine(start, time.min)
    week_end_dt = datetime.combine(end, time.max)

    user_ids = _active_user_ids(week_start_dt, week_end_dt)
    processed = 0
    errors = 0
    for uid in user_ids:
        try:
            compute_weekly_score(uid, end, persist=True)
            processed += 1
        except Exception as exc:
            errors += 1
            logger.error(
                "behavioral_score: failed for user %s — %s", uid, exc
            )
    return {"processed": processed, "errors": errors, "week_ending": end.isoformat()}


# ────────────────────────────────────────────────────────────────────
# Sub-score kernels
# ────────────────────────────────────────────────────────────────────

def _holding_discipline_subscore(
    trades: list[TradeHistory], persona: str
) -> float:
    """Score by deviation of avg-hold from the persona's target.

    No closed round trips ⇒ fall back to open-position ages. No data at
    all ⇒ 50 (neutral) so a brand-new user doesn't start with a 0.
    """
    if not trades:
        return 50.0

    target = PERSONA_HOLDING_DAYS.get(persona, 60.0)
    pairs = fifo_match_closed_trades(trades)
    if pairs:
        avg = sum(p.hold_days for p in pairs) / len(pairs)
    else:
        ages = fifo_open_position_ages(trades)
        if not ages:
            return 50.0
        avg = sum(ages) / len(ages)

    if avg <= 0 or target <= 0:
        return 50.0
    # Linear: |log2(avg/target)| < 1 ⇒ 100..0
    # Above target → score = 100; below target → linear decay; well above
    # 2x → still 100 (over-disciplined isn't penalised).
    if avg >= target:
        return 100.0
    if avg >= target * 0.5:
        return 50.0 + 50.0 * (avg - target * 0.5) / (target * 0.5)
    return max(0.0, 50.0 * avg / (target * 0.5))


def _loss_cut_subscore(trades: list[TradeHistory]) -> float:
    """Average days held on losing closes — faster cut ⇒ higher score.

    Empty → 50 (neutral).  Day-trader-fast (<=1 day) → 100.  > 30 days →
    0.  Linear in between.
    """
    if not trades:
        return 50.0
    pairs = fifo_match_closed_trades(trades)
    losing = [
        p for p in pairs
        if p.sell_pnl is not None and float(p.sell_pnl) < 0.0
    ]
    if not losing:
        # No losses this period — that's not a sin, but we also can't
        # measure cut speed. Stay neutral.
        return 50.0
    avg_days = sum(p.hold_days for p in losing) / len(losing)
    if avg_days <= 1.0:
        return 100.0
    if avg_days >= 30.0:
        return 0.0
    return max(0.0, 100.0 * (1.0 - (avg_days - 1.0) / 29.0))


def _position_sizing_subscore(user_id: int) -> float:
    """Single-largest holding as % of portfolio value.

    Empty → 50 (no exposure to score).
    Concentration <= ``SIZING_TARGET_SHARE`` (10%) → 100.
    Concentration = 1.0 → 0.
    """
    positions = Position.query.filter_by(user_id=user_id).all()
    if not positions:
        return 50.0
    values = []
    for p in positions:
        # Cost basis normalised to KRW. A raw ``shares * avg_cost`` sum mixes
        # ₩ (.KS/.KQ) and $ holdings into one denominator — a ₩ figure dwarfs a
        # $ one, so the largest-share concentration was systematically wrong for
        # mixed portfolios (and propagated into persona-cohort medians via
        # group_benchmark). Shared with concentration_mirror through
        # fx_service.cost_basis_krw — FX-consistency guard, Pattern 7.
        v = fx_service.cost_basis_krw(p)
        if v is not None and v > 0:
            values.append(v)
    total = sum(values)
    if total <= 0:
        return 50.0
    largest = max(values)
    share = largest / total
    if share <= SIZING_TARGET_SHARE:
        return 100.0
    if share >= 1.0:
        return 0.0
    return max(0.0, 100.0 * (1.0 - (share - SIZING_TARGET_SHARE) / (1.0 - SIZING_TARGET_SHARE)))


def _fomo_resistance_subscore(trades: list[TradeHistory]) -> float:
    """Fewer buys-after-a-big-move ⇒ higher score.

    For each BUY in the window we look at the same-day ``pnl_pct`` /
    proxy from realtime data. We don't have an intraday tape in the
    DB, so we approximate "big move" as: the trade was inside a day
    when the same ticker had |pnl_pct| ≥ 5% on a SELL row in the same
    window (best signal we have without bringing in a price feed).
    Empty BUY count → 50 (neutral).
    """
    buys = [t for t in trades if (t.action or "").upper() == "BUY"]
    if not buys:
        return 50.0
    # Build a per-(date, ticker) "big move" set from ALL trades —
    # capturing pnl_pct on closes as a proxy for intraday spike days.
    big_days: set[tuple[str, str]] = set()
    for t in trades:
        if not t.traded_at:
            continue
        try:
            move = abs(float(t.pnl_pct or 0.0))
        except (TypeError, ValueError):
            move = 0.0
        if move >= FOMO_THRESHOLD_PCT:
            key = (t.traded_at.date().isoformat(), (t.ticker or "").upper())
            big_days.add(key)
    fomo = 0
    for b in buys:
        if not b.traded_at:
            continue
        key = (b.traded_at.date().isoformat(), (b.ticker or "").upper())
        if key in big_days:
            fomo += 1
    rate = fomo / len(buys)
    return max(0.0, min(100.0, 100.0 * (1.0 - rate)))


def _reflection_rate_subscore(
    user_id: int,
    week_start_dt: datetime,
    week_end_dt: datetime,
    trades: list[TradeHistory],
) -> float:
    """How often the user used Pre-Trade Friction this week, weighted by depth.

    Score = 100 * min(1, reflections_used / max(trades, 1)) * depth_factor

    where depth_factor = average rationale length / RATIONALE_TARGET_CHARS,
    clamped to [0, 1]. No reflections → 0.
    """
    refls = (
        PreTradeReflection.query
        .filter(
            PreTradeReflection.user_id == user_id,
            PreTradeReflection.cooldown_started_at >= week_start_dt,
            PreTradeReflection.cooldown_started_at <= week_end_dt,
        )
        .all()
    )
    if not refls:
        return 0.0
    used = len(refls)
    trade_count = max(len(trades), 1)
    coverage = min(1.0, used / trade_count)
    avg_len = sum(len(r.rationale or "") for r in refls) / used
    depth = max(0.0, min(1.0, avg_len / RATIONALE_TARGET_CHARS))
    return 100.0 * coverage * depth


# ────────────────────────────────────────────────────────────────────
# Aggregation + observational note
# ────────────────────────────────────────────────────────────────────

def _overall_weighted_average(sub: dict) -> float:
    total = 0.0
    for k, w in WEIGHTS.items():
        total += float(sub.get(k, 0.0)) * w
    return round(total, 2)


def _observational_note(
    sub: dict,
    persona: str,
    persona_avg: dict | None,
) -> str:
    """Return a single observational sentence describing the week.

    The string is scrubbed by ``safe_scrub`` then asserted free of any
    forbidden directive term before being returned. We never use
    advisory verbs ("should", "consider", "recommend") here — only
    "관찰됨" / "기록됨" framing.
    """
    # Identify the highest sub-score and frame it observationally.
    if not sub:
        return ""
    top_key, top_val = max(sub.items(), key=lambda kv: kv[1])
    label = {
        "holding_discipline": "보유기간 일관성",
        "loss_cut":           "손절 속도",
        "position_sizing":    "포지션 집중도 관리",
        "fomo_resistance":    "변동 후 매수 빈도",
        "reflection_rate":    "사전 reflection 사용률",
    }.get(top_key, top_key)

    note = f"이번 주 가장 높은 지표: {label} {round(top_val, 1)}/100 — 관찰됨."
    if persona_avg and isinstance(persona_avg, dict):
        avg_v = persona_avg.get(top_key)
        if isinstance(avg_v, (int, float)):
            note += f" 동일 페르소나 그룹 평균 {round(float(avg_v), 1)}/100 (n>=20)."

    note = safe_scrub(note, context="behavior.scorer.note") or ""
    # Belt-and-suspenders: assert no forbidden term survived. If one does
    # we drop the note rather than ship it (compliance > UX).
    if contains_forbidden_term(note):
        logger.warning(
            "behavioral_score note tripped forbidden-term filter; dropping"
        )
        return ""
    return note


# ────────────────────────────────────────────────────────────────────
# Persona-average lookup with MIN_GROUP_SIZE floor
# ────────────────────────────────────────────────────────────────────

def _persona_avg_with_floor(persona: str) -> dict | None:
    """Return same-persona average sub-scores, or ``None`` when suppressed.

    We re-use the existing ``persona_group_stats`` table — that read
    path already enforces ``MIN_GROUP_SIZE`` and returns ``None``
    when the group is too small. When that table doesn't yet contain
    behavioural-score aggregates the function returns ``None``
    (the API surface treats that as "comparison not available").
    """
    try:
        from services.profile.group_benchmark import get_persona_stats
    except Exception:
        logger.debug("silent-fallback: _persona_avg_with_floor", exc_info=True)
        return None
    try:
        stats = get_persona_stats(persona, 90)
    except Exception:
        logger.debug("silent-fallback: _persona_avg_with_floor", exc_info=True)
        return None
    if not stats:
        return None
    # We only echo the keys we actually compute, so a downstream
    # consumer never sees a partial row.
    metrics = stats.get("metrics") if isinstance(stats, dict) else None
    if not isinstance(metrics, dict):
        return None
    avg = {}
    for k in SUB_SCORE_KEYS:
        v = metrics.get(k)
        if isinstance(v, (int, float)):
            avg[k] = float(v)
    return avg or None


# ────────────────────────────────────────────────────────────────────
# DB / time helpers
# ────────────────────────────────────────────────────────────────────

def _trades_in_window(
    user_id: int, start_dt: datetime, end_dt: datetime
) -> list[TradeHistory]:
    return (
        TradeHistory.query
        .filter(
            TradeHistory.user_id == user_id,
            TradeHistory.traded_at >= start_dt,
            TradeHistory.traded_at <= end_dt,
        )
        .order_by(TradeHistory.traded_at.asc(), TradeHistory.id.asc())
        .all()
    )


def _trades_through(user_id: int, end_dt: datetime) -> list[TradeHistory]:
    return (
        TradeHistory.query
        .filter(
            TradeHistory.user_id == user_id,
            TradeHistory.traded_at <= end_dt,
        )
        .order_by(TradeHistory.traded_at.asc(), TradeHistory.id.asc())
        .all()
    )


def _active_user_ids(start_dt: datetime, end_dt: datetime) -> list[int]:
    rows = (
        db.session.query(TradeHistory.user_id)
        .filter(
            TradeHistory.traded_at >= start_dt,
            TradeHistory.traded_at <= end_dt,
        )
        .distinct()
        .all()
    )
    return [int(r[0]) for r in rows if r[0] is not None]


def _resolve_persona(user_id: int) -> str:
    prof = InvestmentProfile.query.filter_by(user_id=user_id).first()
    if not prof:
        return "balanced"
    # Resolve through the shared SoT resolver so V2 questionnaire tokens
    # (passive_index_hugger, steady_accumulator, …) map to a canonical persona
    # instead of silently falling back to "balanced" — those tokens are not
    # PERSONA_HOLDING_DAYS keys themselves. Keeps behaviour scoring on the same
    # persona as the PDF/peer-benchmark surfaces. (local import: no cycle)
    from services.artifacts.persona_resolver import resolve_persona
    persona = resolve_persona(prof)
    return persona if persona in PERSONA_HOLDING_DAYS else "balanced"


def _last_sunday(today: date) -> date:
    """Return the most recent Sunday on or before ``today``.

    Python's ``weekday()``: Monday=0 … Sunday=6.
    """
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


# ────────────────────────────────────────────────────────────────────
# Persistence
# ────────────────────────────────────────────────────────────────────

def _upsert(
    *,
    user_id: int,
    week_ending: date,
    overall: float,
    sub_scores: dict,
    persona_avg: dict | None,
    notes: str | None,
    trade_count: int,
) -> None:
    existing = (
        BehavioralScore.query
        .filter_by(user_id=user_id, week_ending=week_ending)
        .first()
    )
    sub_json = json.dumps(sub_scores, ensure_ascii=False)
    avg_json = json.dumps(persona_avg, ensure_ascii=False) if persona_avg else None
    if existing:
        existing.overall_score = Decimal(str(overall))
        existing.sub_scores = sub_json
        existing.persona_avg = avg_json
        existing.notes = notes
        existing.trade_count = int(trade_count or 0)
    else:
        row = BehavioralScore(
            user_id=user_id,
            week_ending=week_ending,
            overall_score=Decimal(str(overall)),
            sub_scores=sub_json,
            persona_avg=avg_json,
            notes=notes,
            trade_count=int(trade_count or 0),
        )
        db.session.add(row)
    db.session.commit()


__all__ = [
    "compute_weekly_score",
    "run_weekly_for_all_users",
    "WEIGHTS",
    "PERSONA_HOLDING_DAYS",
    "FOMO_THRESHOLD_PCT",
    "RATIONALE_TARGET_CHARS",
    "SIZING_TARGET_SHARE",
]
