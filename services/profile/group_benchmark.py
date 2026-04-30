"""Group Benchmark — anonymized aggregate stats per persona.

Feature spec: reports/product/GROUP_BENCHMARK_SPEC_2026-04-24.md
Legal memo:   reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §group-stats

Goal
----
Let a user see how their peer group (users with the same declared /
observed persona) is performing — without ever leaking a single
individual identifier.

Public surface
--------------
    compute_persona_stats(persona, window_days, *, commit=True)
        → PersonaGroupStats row  (or None if no users)
    compute_all_personas(window_days, *, commit=True)
        → list[PersonaGroupStats]
    get_persona_stats(persona, window_days)
        → dict | None  (reads most recent snapshot, enforces MIN_GROUP_SIZE)
    get_all_persona_stats(window_days)
        → dict[persona, dict | None]

Anonymization invariants (tested in tests/test_group_benchmark.py)
-----------------------------------------------------------------
1. No per-user field is ever persisted or returned. Users are bucketed
   by their ``InvestmentProfile.profile_type`` → persona mapping, and
   only *aggregate* metrics leave this module.
2. Tickers are never surfaced — only sector-level buckets (Technology,
   Healthcare, Financial Services, …), which are broad enough to be
   non-identifying.
3. ``MIN_GROUP_SIZE = 20``. Below that, the row is marked
   ``suppressed=True`` and :func:`get_persona_stats` returns ``None``.
4. ``common_mistakes`` uses behavioural labels (Disposition / Herding /
   Anchoring) — never specific trades.

All language stays **observational** (e.g. "관찰된 평균", "peer average")
— no "매매 권유" / "recommendation" / "advice" wording anywhere.
"""
from __future__ import annotations

import json
import logging
import statistics
from collections import Counter
from datetime import datetime, timedelta
from typing import Iterable

from extensions import db
from models import (
    InvestmentProfile,
    MIN_GROUP_SIZE,
    PersonaGroupStats,
    Position,
    TradeHistory,
    VALID_PERSONAS,
    VALID_WINDOWS,
)
from services.profile.common_util import is_finite as _finite, utc_now as _utc_now
from services.profile.fifo_util import fifo_match_closed_trades
from services.profile.persona_analytics import DECLARED_TO_PERSONA


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Labels for common mistakes (read-only constants — do NOT localise
# inside the service; the API layer / artifact layer can translate).
# ─────────────────────────────────────────────────────────────────────

MISTAKE_DISPOSITION = "disposition_effect"     # 손실은 오래 들고, 이익은 빨리 판다
MISTAKE_HERDING = "herding"                    # 남이 사면 따라 산다
MISTAKE_ANCHORING = "anchoring"                # 매수가에 집착한다

MISTAKE_LABELS = (MISTAKE_DISPOSITION, MISTAKE_HERDING, MISTAKE_ANCHORING)


# ─────────────────────────────────────────────────────────────────────
# Sector fallback — wide bucketing is a feature here (privacy).
# ─────────────────────────────────────────────────────────────────────

_SECTOR_UNKNOWN = "UNKNOWN"
_TOP_SECTORS_N = 5
_TOP_MISTAKES_N = 3


# ═════════════════════════════════════════════════════════════════════
# Compute — called by cron (scripts/compute_group_stats.py) or on demand
# ═════════════════════════════════════════════════════════════════════

def compute_persona_stats(
    persona: str,
    window_days: int,
    *,
    now: datetime | None = None,
    commit: bool = True,
) -> PersonaGroupStats | None:
    """Compute a single persona × window aggregate and persist it.

    Returns the persisted row, or ``None`` when there are zero users in
    that bucket (we don't write empty rows — saves cron storage).
    """
    if persona not in VALID_PERSONAS:
        raise ValueError(f"Unknown persona: {persona!r}")
    if window_days not in VALID_WINDOWS:
        raise ValueError(f"Unknown window_days: {window_days!r}")

    now = _utc_now() if now is None else now
    cutoff = now - timedelta(days=window_days)

    user_ids = _user_ids_for_persona(persona)
    n_users = len(user_ids)

    # Zero-user bucket → skip entirely. Different from "suppressed" (1..19).
    if n_users == 0:
        return None

    suppressed = n_users < MIN_GROUP_SIZE
    metrics: dict | None = None

    if not suppressed:
        metrics = _aggregate_metrics(user_ids, cutoff, window_days, persona)

    row = PersonaGroupStats(
        persona=persona,
        window_days=window_days,
        computed_at=now,
        n_users=n_users,
        suppressed=suppressed,
        metrics=json.dumps(metrics, ensure_ascii=False) if metrics is not None else None,
    )
    db.session.add(row)
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(
                "group_benchmark.compute_persona_stats commit failed "
                "(persona=%s, window=%s)", persona, window_days,
            )
            raise
    return row


def compute_all_personas(
    window_days: int,
    *,
    now: datetime | None = None,
    commit: bool = True,
) -> list[PersonaGroupStats]:
    """Compute stats for all 8 personas in one transaction."""
    if window_days not in VALID_WINDOWS:
        raise ValueError(f"Unknown window_days: {window_days!r}")
    now = _utc_now() if now is None else now
    out: list[PersonaGroupStats] = []
    for persona in VALID_PERSONAS:
        row = compute_persona_stats(persona, window_days, now=now, commit=False)
        if row is not None:
            out.append(row)
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(
                "group_benchmark.compute_all_personas commit failed (window=%s)",
                window_days,
            )
            raise
    return out


# ═════════════════════════════════════════════════════════════════════
# Read — latest snapshot, enforces MIN_GROUP_SIZE
# ═════════════════════════════════════════════════════════════════════

def get_persona_stats(persona: str, window_days: int) -> dict | None:
    """Return the most recent snapshot for (persona, window), or None.

    Returns ``None`` when:
      - No snapshot has been computed yet, OR
      - The latest snapshot is suppressed (n_users < MIN_GROUP_SIZE).

    This is the legal choke-point — the API layer can simply return 200
    with an explicit ``{"available": false, "reason": "..."}`` body when
    we return None here.
    """
    if persona not in VALID_PERSONAS:
        return None
    if window_days not in VALID_WINDOWS:
        return None

    row = (
        PersonaGroupStats.query
        .filter_by(persona=persona, window_days=window_days)
        .order_by(PersonaGroupStats.computed_at.desc())
        .first()
    )
    if row is None:
        return None
    if row.suppressed or row.n_users < MIN_GROUP_SIZE:
        return None
    return row.to_dict()


def get_all_persona_stats(window_days: int) -> dict[str, dict | None]:
    """Return latest snapshot for every persona. Missing / suppressed → None.

    Shape:
        {"growth": {...} | None, "value": {...}, ...}
    """
    return {p: get_persona_stats(p, window_days) for p in VALID_PERSONAS}


# ═════════════════════════════════════════════════════════════════════
# Internals
# ═════════════════════════════════════════════════════════════════════

def _user_ids_for_persona(persona: str) -> list[int]:
    """Return distinct user_ids whose declared persona maps to ``persona``.

    Uses the DECLARED mapping (``InvestmentProfile.profile_type``
    → persona_code) because it's stable across sessions. Observed
    personas can flip weekly; grouping by declared is both cheaper and
    more defensible privacy-wise.

    SQL pre-filter
    --------------
    Previously this function loaded **every** ``InvestmentProfile`` row
    and filtered in Python — O(N) over the entire user table for each
    of the 8 personas. We now push the filter into SQL via
    ``profile_type.in_(...)``, returning only rows that can possibly
    match. ``DECLARED_TO_PERSONA`` keys are case-folded by the resolver
    so we match on the canonical lower-case form here.
    """
    legacy_types = [
        pt for pt, code in DECLARED_TO_PERSONA.items() if code == persona
    ]
    if not legacy_types:
        return []

    # Case-insensitive equality is platform-dependent; the column is
    # stored exactly as the user submitted it. We expand the IN clause
    # to cover both lower and upper variants seen in the wild — the
    # resolver below still applies as a final guard.
    candidate_values = set(legacy_types)
    candidate_values.update(v.upper() for v in legacy_types)
    candidate_values.update(v.capitalize() for v in legacy_types)

    rows = (
        db.session.query(InvestmentProfile.user_id, InvestmentProfile.profile_type)
        .filter(InvestmentProfile.profile_type.isnot(None))
        .filter(InvestmentProfile.profile_type.in_(candidate_values))
        .all()
    )
    matched: set[int] = set()
    for uid, pt in rows:
        if uid is None or not pt:
            continue
        if DECLARED_TO_PERSONA.get(pt.lower()) == persona:
            matched.add(int(uid))
    return sorted(matched)


def _aggregate_metrics(
    user_ids: list[int],
    cutoff: datetime,
    window_days: int,
    persona: str,
) -> dict:
    """Compute the aggregated metrics payload for a non-suppressed bucket."""
    # Fetch all trade rows for these users in one query (O(1) roundtrip).
    trades: list[TradeHistory] = (
        TradeHistory.query
        .filter(TradeHistory.user_id.in_(user_ids))
        .filter(TradeHistory.traded_at >= cutoff)
        .all()
    )

    # Group trades by user for per-user metrics.
    by_user: dict[int, list[TradeHistory]] = {}
    for t in trades:
        by_user.setdefault(int(t.user_id), []).append(t)

    per_user_cagr: list[float] = []
    per_user_sharpe: list[float] = []
    per_user_holding: list[float] = []
    per_user_win_rate: list[float] = []
    per_user_max_dd: list[float] = []
    mistake_counter: Counter = Counter()

    for uid, u_trades in by_user.items():
        pnls = _realised_pnls(u_trades)
        if pnls:
            per_user_cagr.append(_cagr_from_pnls(pnls, window_days))
            per_user_sharpe.append(_sharpe_from_pnls(pnls))
            per_user_win_rate.append(_win_rate(pnls))
            per_user_max_dd.append(_max_drawdown_pct(pnls))
        hp = _avg_holding_days(u_trades)
        if hp is not None:
            per_user_holding.append(hp)
        # Common mistakes — at most one vote per user per label to avoid
        # a single heavy trader dominating the top-3.
        for m in _user_mistakes(u_trades):
            mistake_counter[m] += 1

    sectors = _sector_distribution(user_ids)

    # Comparison-to-all — computed once per window across the whole
    # user base. ``_all_users_baseline`` memoizes the result with a 1h
    # TTL, so ``compute_all_personas`` runs the full scan once per
    # window even though it touches all 8 persona buckets.
    all_users_stats = _all_users_baseline(cutoff, window_days)

    # Behavioural sub-score medians — F7 persona_avg surface.
    # ``services.behavior.scorer._persona_avg_with_floor`` reads these
    # five keys from the metrics dict; without them every behavioural
    # score response returns ``persona_avg = None``. We compute the
    # weekly score per user (no persistence) and aggregate medians.
    sub_score_medians = _aggregate_behavioral_sub_scores(user_ids)
    metrics: dict = {
        "avg_cagr": _safe_median(per_user_cagr),
        "avg_sharpe": _safe_median(per_user_sharpe),
        "median_holding_days": _safe_median(per_user_holding),
        "win_rate": _safe_median(per_user_win_rate),
        "max_drawdown_avg": _safe_median(per_user_max_dd),
        "most_held_sectors": sectors[:_TOP_SECTORS_N],
        "common_mistakes": [
            {"label": label, "count": count}
            for label, count in mistake_counter.most_common(_TOP_MISTAKES_N)
        ],
        "comparison_to_all": {
            "avg_cagr_all": all_users_stats.get("avg_cagr"),
            "avg_sharpe_all": all_users_stats.get("avg_sharpe"),
            "median_holding_days_all": all_users_stats.get("median_holding_days"),
        },
        # Narrative framing — keeps downstream artifacts legally safe.
        "framing": "observational_peer_summary",
        "persona": persona,
        "window_days": window_days,
    }
    metrics.update(sub_score_medians)
    return metrics


def _aggregate_behavioral_sub_scores(user_ids: list[int]) -> dict[str, float]:
    """Compute median behavioural sub-scores across the persona group.

    Returns the 5 SUB_SCORE_KEYS as float medians (0-100). Empty when
    no user produced a usable score — caller treats that as
    "comparison not available". Lazy-imported to avoid circular
    dependency with ``services.behavior.scorer``.
    """
    if not user_ids:
        return {}
    try:
        from services.behavior.scorer import compute_weekly_score
        from models import SUB_SCORE_KEYS
    except Exception:
        return {}

    buckets: dict[str, list[float]] = {k: [] for k in SUB_SCORE_KEYS}
    for uid in user_ids:
        try:
            row = compute_weekly_score(uid, persist=False)
        except Exception:
            continue
        sub = row.get("sub_scores") if isinstance(row, dict) else None
        if not isinstance(sub, dict):
            continue
        for k in SUB_SCORE_KEYS:
            v = sub.get(k)
            if isinstance(v, (int, float)) and _finite(float(v)):
                buckets[k].append(float(v))

    out: dict[str, float] = {}
    for k, vals in buckets.items():
        if vals:
            out[k] = round(float(statistics.median(vals)), 2)
    return out


# ─────────────────────────────────────────────────────────────────────
# Per-user metric helpers
# ─────────────────────────────────────────────────────────────────────

def _realised_pnls(trades: list[TradeHistory]) -> list[float]:
    """Return pnl_pct for every SELL row (already stored on the model)."""
    out: list[float] = []
    for t in trades:
        if (t.action or "").upper() != "SELL":
            continue
        try:
            pct = float(t.pnl_pct or 0.0)
        except (TypeError, ValueError):
            continue
        if _finite(pct):
            out.append(pct)
    return out


def _cagr_from_pnls(pnls: list[float], window_days: int) -> float:
    """Approximate CAGR from a list of trade-level percent returns.

    We compound the trade returns (treating each SELL as a closed
    round-trip), then annualise over ``window_days``. This is NOT a
    portfolio-weighted CAGR — it's a reasonable proxy when we don't
    track per-user equity curves server-side.
    """
    if not pnls or window_days <= 0:
        return 0.0
    product = 1.0
    for p in pnls:
        product *= (1.0 + (p / 100.0))
    if product <= 0:
        return -99.0  # cap to avoid math domain errors on the log path
    years = window_days / 365.0
    if years <= 0:
        return 0.0
    try:
        cagr = (product ** (1.0 / years)) - 1.0
    except (ValueError, OverflowError):
        return 0.0
    return round(float(cagr * 100.0), 2) if _finite(cagr) else 0.0


def _sharpe_from_pnls(pnls: list[float]) -> float:
    """Per-trade Sharpe proxy: mean / stdev. Risk-free = 0."""
    if len(pnls) < 2:
        return 0.0
    try:
        mean = statistics.fmean(pnls)
        stdev = statistics.pstdev(pnls)
    except statistics.StatisticsError:
        return 0.0
    if stdev <= 1e-9:
        return 0.0
    return round(float(mean / stdev), 2)


def _win_rate(pnls: list[float]) -> float:
    if not pnls:
        return 0.0
    wins = sum(1 for p in pnls if p > 0)
    return round(100.0 * wins / len(pnls), 2)


def _max_drawdown_pct(pnls: list[float]) -> float:
    """Peak-to-trough on a compounded equity curve of the trade-level pnls."""
    if not pnls:
        return 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for p in pnls:
        equity *= (1.0 + (p / 100.0))
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
    return round(float(max_dd * 100.0), 2)


def _avg_holding_days(trades: list[TradeHistory]) -> float | None:
    """FIFO-match BUY/SELL per ticker. Returns None when no round trips.

    Delegates to :mod:`fifo_util` so this aggregator agrees with the
    per-user persona analytics pipeline byte-for-byte.
    """
    pairs = fifo_match_closed_trades(trades)
    if not pairs:
        return None
    mean = sum(p.hold_days for p in pairs) / len(pairs)
    return round(float(mean), 1)


def _user_mistakes(trades: list[TradeHistory]) -> set[str]:
    """Detect behavioural anti-patterns in a user's window.

    Kept deliberately simple so the cron stays O(n). The mistakes are
    labels only — we never store which trades triggered them.
    """
    mistakes: set[str] = set()
    sells = [t for t in trades if (t.action or "").upper() == "SELL"]
    if not sells:
        return mistakes

    # Disposition: avg hold on winners much shorter than on losers.
    # Group FIFO-matched pairs by their SELL (sell_time + ticker) so we
    # can attribute each SELL's stored ``pnl_pct`` to the right slice.
    pairs = fifo_match_closed_trades(trades)
    holds_by_sell: dict[tuple[str, datetime], list[float]] = {}
    for p in pairs:
        holds_by_sell.setdefault((p.ticker, p.sell_time), []).append(p.hold_days)

    win_holds: list[float] = []
    loss_holds: list[float] = []
    for sell in (t for t in trades if (t.action or "").upper() == "SELL"):
        if not sell.traded_at or not sell.ticker:
            continue
        slice_holds = holds_by_sell.get((sell.ticker.upper(), sell.traded_at))
        if not slice_holds:
            continue
        avg_hold = sum(slice_holds) / len(slice_holds)
        try:
            pct = float(sell.pnl_pct or 0.0)
        except (TypeError, ValueError):
            pct = 0.0
        if pct > 0:
            win_holds.append(avg_hold)
        elif pct < 0:
            loss_holds.append(avg_hold)

    if win_holds and loss_holds:
        avg_win = sum(win_holds) / len(win_holds)
        avg_loss = sum(loss_holds) / len(loss_holds)
        if avg_loss >= (avg_win * 1.5) and avg_win >= 0:
            mistakes.add(MISTAKE_DISPOSITION)

    # Herding: many BUY rows clustered in the same trading-day bucket
    # across different tickers. Proxy: >=3 BUYs on >=2 tickers in a
    # single day.
    by_day: dict[str, set[str]] = {}
    for t in trades:
        if (t.action or "").upper() != "BUY" or not t.traded_at or not t.ticker:
            continue
        day = t.traded_at.date().isoformat()
        by_day.setdefault(day, set()).add(t.ticker.upper())
    herding_days = sum(1 for tickers in by_day.values() if len(tickers) >= 2)
    if herding_days >= 3:
        mistakes.add(MISTAKE_HERDING)

    # Anchoring: repeated trades on the same ticker within tight price
    # bands — 3+ SELLs on the same ticker with pnl_pct < 0 and small
    # spread between prices.
    sells_by_ticker: dict[str, list[TradeHistory]] = {}
    for t in sells:
        if t.ticker:
            sells_by_ticker.setdefault(t.ticker.upper(), []).append(t)
    for ticker, tlist in sells_by_ticker.items():
        negatives = [t for t in tlist if (t.pnl_pct or 0.0) < 0]
        if len(negatives) >= 3:
            mistakes.add(MISTAKE_ANCHORING)
            break

    return mistakes


# ─────────────────────────────────────────────────────────────────────
# Sector distribution (anonymized — only sector labels)
# ─────────────────────────────────────────────────────────────────────

def _sector_distribution(user_ids: list[int]) -> list[dict]:
    """Top sectors held across the persona group.

    We use ``Position.ticker`` with a best-effort sector lookup. Tickers
    are NEVER surfaced — only the sector aggregate count (rounded share).
    """
    positions: list[Position] = (
        Position.query
        .filter(Position.user_id.in_(user_ids))
        .all()
    )
    counter: Counter = Counter()
    for p in positions:
        sector = _ticker_to_sector(p.ticker or "")
        counter[sector] += 1
    total = sum(counter.values()) or 1
    out = [
        {
            "sector": sector,
            "share": round(100.0 * count / total, 1),
        }
        for sector, count in counter.most_common()
    ]
    # Drop UNKNOWN from the published list unless it's the only bucket —
    # keeps the UI clean without hiding a fully-unknown portfolio.
    named = [row for row in out if row["sector"] != _SECTOR_UNKNOWN]
    return named if named else out


def _ticker_to_sector(ticker: str) -> str:
    """Best-effort sector resolution. Degrades cleanly to UNKNOWN.

    Importing the KR registry lazily — it's optional in local dev and we
    don't want a missing registry to crash the cron.
    """
    t = (ticker or "").upper().strip()
    if not t:
        return _SECTOR_UNKNOWN
    try:
        from services.kr_stock_registry import get_sector as _kr_sector  # type: ignore
    except Exception:
        _kr_sector = None  # type: ignore[assignment]
    if _kr_sector is not None:
        try:
            sec = _kr_sector(t)
            if sec:
                return str(sec)
        except Exception:
            pass
    return _SECTOR_UNKNOWN


# ─────────────────────────────────────────────────────────────────────
# All-users baseline (for comparison_to_all block)
# ─────────────────────────────────────────────────────────────────────
#
# Module-level memoization: ``compute_all_personas`` previously called
# this function 8× per window with identical arguments, but the
# original "cached on session identity" comment was aspirational — no
# cache existed. The full TradeHistory scan reran every time. We now
# memoize on ``window_days`` with a short TTL.

_BASELINE_CACHE_TTL = timedelta(hours=1)
# window_days → (computed_at, baseline_dict)
_baseline_cache: dict[int, tuple[datetime, dict]] = {}


def _baseline_cache_clear() -> None:
    """Drop the in-memory baseline cache (used by tests)."""
    _baseline_cache.clear()


def _all_users_baseline(cutoff: datetime, window_days: int) -> dict:
    """Compute aggregate baseline across EVERY user with trades.

    This is the denominator for the "you vs. everyone" comparison. We
    don't gate on MIN_GROUP_SIZE here because the all-users bucket is
    effectively always > 20 in production — and if it isn't, suppression
    for individual personas already protects the user.

    Caching
    -------
    Memoized at module scope keyed on ``window_days`` with a 1-hour
    TTL. ``compute_all_personas(window_days)`` previously triggered 8
    full ``TradeHistory`` scans (one per persona) for identical input;
    this drops it to 1. The cache is intentionally process-local (no
    Redis) so a deploy or process restart guarantees a fresh recompute.
    """
    now = _utc_now()
    cached = _baseline_cache.get(window_days)
    if cached is not None:
        computed_at, baseline = cached
        if (now - computed_at) < _BASELINE_CACHE_TTL:
            return baseline

    all_trades: list[TradeHistory] = (
        TradeHistory.query
        .filter(TradeHistory.traded_at >= cutoff)
        .all()
    )
    if not all_trades:
        result: dict = {}
        _baseline_cache[window_days] = (now, result)
        return result
    by_user: dict[int, list[TradeHistory]] = {}
    for t in all_trades:
        by_user.setdefault(int(t.user_id), []).append(t)

    cagrs: list[float] = []
    sharpes: list[float] = []
    holdings: list[float] = []
    for uid, u_trades in by_user.items():
        pnls = _realised_pnls(u_trades)
        if pnls:
            cagrs.append(_cagr_from_pnls(pnls, window_days))
            sharpes.append(_sharpe_from_pnls(pnls))
        hp = _avg_holding_days(u_trades)
        if hp is not None:
            holdings.append(hp)
    result = {
        "avg_cagr": _safe_median(cagrs),
        "avg_sharpe": _safe_median(sharpes),
        "median_holding_days": _safe_median(holdings),
    }
    _baseline_cache[window_days] = (now, result)
    return result


# ─────────────────────────────────────────────────────────────────────
# Small utilities
# ─────────────────────────────────────────────────────────────────────

def _safe_median(values: Iterable[float]) -> float:
    """Median over the finite subset of ``values``; ``0.0`` when empty.

    ``_finite`` and ``_utc_now`` are imported from
    :mod:`services.profile.common_util` (see top of file) — the previous
    local copies were removed to keep semantics identical across the
    profile package.
    """
    vs = [float(v) for v in values if _finite(v)]
    if not vs:
        return 0.0
    return round(float(statistics.median(vs)), 2)
