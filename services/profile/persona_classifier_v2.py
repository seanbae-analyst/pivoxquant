"""Multi-dimensional persona classifier (v2) — cross-signal scoring.

Motivation
----------
The v1 :mod:`services.profile.persona_analytics` module classifies users on
a single, trade-history-only 3-D vector (holding_period, turnover,
sector_tilt) and picks the nearest of 8 persona centroids. That is
Toss-level. Renaissance-level requires **cross-signal** evidence:

    1.  Trade mechanics      — holding period, turnover, ticker/sector diversity
    2.  Intra-trade patterns — hold-time variance, loss-cut discipline
    3.  Declared preferences — InvestmentProfile.risk_tolerance, horizon
    4.  Self-report          — WeeklyPulse confidence mean / variance
    5.  Engagement           — ArtifactFeedback useful-rate

This module fuses all five into a 9-dim behavioural vector, compares to
8 persona centroids, emits a **confidence score** (how unambiguous the
classification is), and produces an **explainability breakdown** (which
features pushed toward the assigned persona).

Backward compatibility
----------------------
v1 ``compute_persona_response`` is untouched — the module is additive.
``classify_persona_multi`` returns a dict; a ``compat_observed_for_window``
helper is **not** exposed because tests for v1 assert v1 shape and v2
adds a new ``persona-detail`` route rather than replacing the old one.

Legal language
--------------
Every explanation string speaks of *observation* ("관찰됨"), never
*recommendation* or *advice*. Persona codes are the existing 8 — no new
names are introduced.

Persona taxonomy
----------------
Identical to v1 ``persona_analytics.PERSONA_CODES`` — the frontend label
map + tagline dictionary is reused unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from flask import g, has_request_context

from models import (
    ArtifactFeedback,
    InvestmentProfile,
    Position,
    TradeHistory,
    WeeklyPulse,
)

from .common_util import utc_now as _utc_now
from .fifo_util import fifo_match_closed_trades
from .persona_analytics import (
    PERSONA_CODES,
    PERSONA_LABELS,
    PERSONA_TAGLINES,
    _avg_holding_period,
    _fetch_positions,
    _fetch_trades,
    _norm_log,
    _resolve_declared,
    _sector_diversification,
    _sector_map_from_positions,
)


# ─────────────────────────────────────────────────────────────────────
# Feature dimensions
# ─────────────────────────────────────────────────────────────────────
# All features in [0, 1]. Name → (display_label, default_when_missing)
# The order here is load-bearing — centroids below must match it.

FEATURE_KEYS: tuple[str, ...] = (
    "holding_period",       # D1  long → 1.0
    "turnover",             # D2  intraday → 1.0
    "sector_diversity",     # D3  fully-spread → 1.0
    "ticker_diversity",     # D4  many distinct names → 1.0
    "hold_variance",        # D5  CV of hold times (impulsive → 1.0)
    "loss_cut_discipline",  # D6  quick to cut losers → 1.0
    "declared_risk",        # D7  aggressive stance → 1.0
    "conviction_stability", # D8  steady confidence → 1.0
    "feedback_engagement",  # D9  uses artifacts actively → 1.0
)

FEATURE_LABELS: dict[str, str] = {
    "holding_period":       "평균 보유기간",
    "turnover":             "매매 회전율",
    "sector_diversity":     "섹터 분산",
    "ticker_diversity":     "종목 다양성",
    "hold_variance":        "보유기간 편차",
    "loss_cut_discipline":  "손절 규율",
    "declared_risk":        "선언한 위험 감내",
    "conviction_stability": "확신 안정성",
    "feedback_engagement":  "피드백 반응도",
}

# Missing-feature defaults keep the vector well-defined even for brand-new
# users. 0.5 = "no evidence either way" — neutral.
FEATURE_DEFAULTS: dict[str, float] = {k: 0.5 for k in FEATURE_KEYS}


# ─────────────────────────────────────────────────────────────────────
# Persona centroids — 9-D vectors in the order of FEATURE_KEYS.
# Hand-tuned from the spec in reports/product/PERSONA_SPEC_2026-04-23.md
# Every coordinate in [0, 1].
# ─────────────────────────────────────────────────────────────────────

PERSONA_CENTROIDS_V2: dict[str, tuple[float, ...]] = {
    # key              H_pd  turn  sec_d tik_d hold_v  loss_d risk_  conv_  fb_eng
    "beginner":       (0.85, 0.05, 0.55, 0.30, 0.20,  0.30,  0.20, 0.45, 0.30),
    "income":         (0.88, 0.10, 0.45, 0.55, 0.15,  0.45,  0.25, 0.75, 0.55),
    "value":          (0.78, 0.12, 0.70, 0.70, 0.25,  0.55,  0.45, 0.80, 0.55),
    "balanced":       (0.55, 0.15, 0.85, 0.80, 0.30,  0.60,  0.50, 0.70, 0.60),
    "growth":         (0.48, 0.30, 0.45, 0.55, 0.45,  0.55,  0.75, 0.65, 0.60),
    "quant":          (0.40, 0.35, 0.80, 0.85, 0.25,  0.85,  0.60, 0.85, 0.70),
    "speculator":     (0.18, 0.70, 0.35, 0.40, 0.70,  0.40,  0.90, 0.35, 0.40),
    "daytrader":      (0.05, 0.95, 0.25, 0.35, 0.80,  0.75,  0.85, 0.50, 0.45),
}

# Per-feature weight into the cosine. Trade mechanics dominate
# (it's the hardest-to-lie-about signal); self-report is weakest.
#
# ⚠️ D9 ``feedback_engagement`` is weighted 0.0 — the axis is structurally
# uncomputable, not merely sparse (2026-09-02).
#
# It is derived from ``ArtifactFeedback`` rows, which require an
# ``artifact_id``; the artefact tree was deleted on 2026-08-31 (47a5e8f3) and
# nothing creates artefacts any more, so ``_fetch_feedback`` returns [] for
# every user, forever. That left the axis pinned at its 0.5 "no evidence"
# default while the eight persona centroids spread D9 across 0.30 (beginner)
# to 0.70 (quant) — so a constant 0.5 was not neutral. It applied a permanent
# distance penalty to the personas furthest from 0.5 and an equally permanent
# advantage to those nearest it, biasing classification *against* `beginner`
# — the persona most new closed-beta users should land on.
#
# Weight 0.0 removes it from both places that consume these weights:
#   * ``_weighted_distance`` — the term contributes 0 to `total` AND 0 to
#     `norm`, so the axis drops out of the distance entirely (not merely
#     shrinks).
#   * ``_confidence_from_ranking`` — `total_w` no longer counts a slot that
#     `present_w` could never fill, so evidence_ratio can reach 1.0 again.
#     Before this, no user could exceed 0.45/8.00 = 5.6% short of full
#     evidence, i.e. confidence was silently capped.
#
# The key, label and centroid values are deliberately KEPT so the 9-D
# centroid table stays intact and the axis is revivable. **If artefact
# feedback ever returns, restore this weight to 0.45** — and only then.
FEATURE_WEIGHTS: dict[str, float] = {
    "holding_period":       1.25,
    "turnover":             1.25,
    "sector_diversity":     1.00,
    "ticker_diversity":     0.90,
    "hold_variance":        0.90,
    "loss_cut_discipline":  1.00,
    "declared_risk":        0.70,
    "conviction_stability": 0.55,
    "feedback_engagement":  0.00,  # dormant — see note above
}


# Minimum number of trades for the observed-trade dimensions to count.
# Below this we still score the user but flag ``data_sparse`` so the
# frontend can render a "더 많은 거래가 필요합니다" tooltip.
MIN_TRADES_FOR_OBSERVATION = 10
MIN_PULSE_ROWS_FOR_CONVICTION = 2


# ─────────────────────────────────────────────────────────────────────
# Feature extraction
# ─────────────────────────────────────────────────────────────────────

@dataclass
class _FeatureBundle:
    """Feature values + the per-feature 'have evidence?' mask.

    ``present`` is 1 when we had enough data to compute the feature, 0
    otherwise. Downstream confidence calculations consume this mask so
    a user with 4 features present and 5 at default doesn't look
    certain.
    """
    values: dict[str, float]
    present: dict[str, int]


def _extract_features(
    user_id: int,
    trades: list[TradeHistory],
    positions: list[Position],
    profile: InvestmentProfile | None,
    window_days: int,
    now: datetime,
) -> _FeatureBundle:
    values = dict(FEATURE_DEFAULTS)
    present = {k: 0 for k in FEATURE_KEYS}

    # ── window trades ─────────────────────────────────────────────
    cutoff = now - timedelta(days=window_days)
    window_trades = [t for t in trades if t.traded_at and t.traded_at >= cutoff]
    trade_count = len(window_trades)
    sector_map = _sector_map_from_positions(positions)

    # D1 holding_period — reuse v1 kernel
    if trade_count >= MIN_TRADES_FOR_OBSERVATION:
        hp_days = _avg_holding_period(window_trades)
        values["holding_period"] = _norm_log(hp_days, floor=1.0, ceil=180.0)
        present["holding_period"] = 1

    # D2 turnover — trades per day, log-normalised
    if trade_count > 0:
        per_day = trade_count / max(window_days, 1)
        values["turnover"] = _norm_log(per_day, floor=0.02, ceil=1.0)
        present["turnover"] = 1

    # D3 sector_diversity — 1 - HHI on traded volume
    if trade_count >= MIN_TRADES_FOR_OBSERVATION:
        values["sector_diversity"] = _sector_diversification(window_trades, sector_map)
        present["sector_diversity"] = 1

    # D4 ticker_diversity — unique-ticker count, log-normalised vs 25
    if trade_count > 0:
        distinct = {(t.ticker or "").upper() for t in window_trades if t.ticker}
        values["ticker_diversity"] = _norm_log(float(len(distinct)), floor=1.0, ceil=25.0)
        present["ticker_diversity"] = 1

    # D5 hold_variance — coefficient of variation on realized hold times
    if trade_count >= MIN_TRADES_FOR_OBSERVATION:
        cv = _hold_time_cv(window_trades)
        if cv is not None:
            # CV ∈ [0, ~2]. 0 = consistent hold lengths (patient), 1.5+ = chaotic (impulsive)
            values["hold_variance"] = max(0.0, min(1.0, cv / 1.5))
            present["hold_variance"] = 1

    # D6 loss_cut_discipline — quick on losers vs winners (inverted disposition effect)
    if trade_count >= MIN_TRADES_FOR_OBSERVATION:
        disc = _loss_cut_discipline(window_trades)
        if disc is not None:
            values["loss_cut_discipline"] = disc
            present["loss_cut_discipline"] = 1

    # D7 declared_risk — InvestmentProfile.risk_tolerance 1..10
    if profile is not None and profile.risk_tolerance is not None:
        rt = max(1, min(10, int(profile.risk_tolerance)))
        values["declared_risk"] = (rt - 1) / 9.0
        present["declared_risk"] = 1

    # D8 conviction_stability — mean confidence and low variance from WeeklyPulse
    pulse_rows = _fetch_pulse(user_id, now, window_days * 2)
    if len(pulse_rows) >= MIN_PULSE_ROWS_FOR_CONVICTION:
        conv = _conviction_stability(pulse_rows)
        values["conviction_stability"] = conv
        present["conviction_stability"] = 1

    # D9 feedback_engagement — fraction of feedback rows marked "useful"
    fb_rows = _fetch_feedback(user_id, now, window_days * 2)
    if fb_rows:
        useful = sum(1 for r in fb_rows if r.vote == "useful")
        # Baseline ratio of 0.5 when any signal exists; scale with volume.
        ratio = useful / max(1, len(fb_rows))
        volume_weight = min(1.0, len(fb_rows) / 10.0)  # 10+ votes = full weight
        values["feedback_engagement"] = 0.5 * (1 - volume_weight) + ratio * volume_weight
        present["feedback_engagement"] = 1

    return _FeatureBundle(values=values, present=present)


def _hold_time_cv(trades: list[TradeHistory]) -> float | None:
    """Coefficient of variation over FIFO-matched realized hold days.

    Delegates to :mod:`fifo_util` so the pairing semantics match the
    other three callers exactly. Returns ``None`` when fewer than 3
    closed pairs exist (CV is unstable below that count) or when the
    mean hold collapses to ~0 (degenerate intraday-only sample).
    """
    holds = [p.hold_days for p in fifo_match_closed_trades(trades)]
    if len(holds) < 3:
        return None
    mean = sum(holds) / len(holds)
    if mean <= 1e-9:
        return None
    var = sum((h - mean) ** 2 for h in holds) / len(holds)
    return math.sqrt(var) / mean


def _loss_cut_discipline(trades: list[TradeHistory]) -> float | None:
    """Return 1.0 when losers are cut faster than winners held.

    Uses per-SELL pnl sign (via ``pnl`` column if populated, else via
    FIFO-matched price comparison). The metric:

        discipline = 1 - clip((mean_hold_loss / mean_hold_win), 0, 2) / 2

    Cuts losers in ~half the time of winners → discipline ≈ 0.75+.
    Rides losers, takes profits early (classic disposition) → < 0.5.
    """
    # Stored pnl is the primary win/loss signal; fall back to derived
    # buy_px vs sell_px when pnl is missing or zero.
    win_holds: list[float] = []
    loss_holds: list[float] = []
    for pair in fifo_match_closed_trades(trades):
        is_win = (
            (pair.sell_pnl > 0)
            if abs(pair.sell_pnl) > 1e-9
            else (pair.sell_price > pair.buy_price)
        )
        (win_holds if is_win else loss_holds).append(pair.hold_days)

    if not win_holds or not loss_holds:
        return None
    mean_win = sum(win_holds) / len(win_holds)
    mean_loss = sum(loss_holds) / len(loss_holds)
    if mean_win <= 1e-9:
        return None
    ratio = mean_loss / mean_win
    # ratio < 1.0 → good discipline; > 1.0 → rides losers
    clipped = max(0.0, min(2.0, ratio))
    return max(0.0, min(1.0, 1.0 - clipped / 2.0))


def _fetch_pulse(user_id: int, now: datetime, lookback_days: int) -> list[WeeklyPulse]:
    cutoff = now - timedelta(days=lookback_days)
    return (
        WeeklyPulse.query
        .filter(WeeklyPulse.user_id == user_id)
        .filter(WeeklyPulse.submitted_at >= cutoff)
        .order_by(WeeklyPulse.submitted_at.asc())
        .all()
    )


def _fetch_feedback(user_id: int, now: datetime, lookback_days: int) -> list[ArtifactFeedback]:
    cutoff = now - timedelta(days=lookback_days)
    return (
        ArtifactFeedback.query
        .filter(ArtifactFeedback.user_id == user_id)
        .filter(ArtifactFeedback.created_at >= cutoff)
        .all()
    )


def _conviction_stability(rows: list[WeeklyPulse]) -> float:
    """Mean(confidence/5) - (stdev/max_stdev). Steady high confidence → 1.0."""
    vals = [max(1, min(5, int(r.confidence or 3))) for r in rows]
    if not vals:
        return 0.5
    mean = sum(vals) / len(vals)
    normalised_mean = (mean - 1.0) / 4.0  # 1..5 → 0..1
    if len(vals) < 2:
        return max(0.0, min(1.0, normalised_mean))
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    stdev = math.sqrt(var)
    # Max stdev for vals in 1..5 around mean=3 is 2.0; cap there.
    volatility_penalty = min(1.0, stdev / 2.0)
    return max(0.0, min(1.0, normalised_mean - 0.4 * volatility_penalty))


# ─────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────

def _weighted_distance(vec: dict[str, float], centroid_vec: tuple[float, ...]) -> float:
    """Weighted Euclidean distance over the 9-D feature space."""
    total = 0.0
    norm = 0.0
    for key, centroid in zip(FEATURE_KEYS, centroid_vec):
        w = FEATURE_WEIGHTS[key]
        total += w * (vec[key] - centroid) ** 2
        norm += w
    if norm == 0:
        return float("inf")
    return math.sqrt(total / norm)


def _similarity_ranking(vec: dict[str, float]) -> list[tuple[str, float]]:
    """Return all personas ranked by similarity (higher = closer).

    Similarity = 1 / (1 + weighted_distance). In the unit hypercube this
    sits in (0, 1].
    """
    out = []
    for persona, centroid in PERSONA_CENTROIDS_V2.items():
        d = _weighted_distance(vec, centroid)
        sim = 1.0 / (1.0 + d)
        out.append((persona, sim))
    out.sort(key=lambda p: p[1], reverse=True)
    return out


def _confidence_from_ranking(
    ranking: list[tuple[str, float]],
    present: dict[str, int],
) -> float:
    """Confidence = top-1 margin × evidence-ratio, mapped to 0..100.

    margin         = sim(best) - sim(2nd best)   [usually 0.00..0.15]
    evidence_ratio = sum(weights_present) / sum(weights_all)
    score          = 50 + 200*margin + 50*(evidence_ratio - 1.0)
    """
    if len(ranking) < 2:
        return 50.0
    best_sim = ranking[0][1]
    second_sim = ranking[1][1]
    margin = max(0.0, best_sim - second_sim)

    total_w = sum(FEATURE_WEIGHTS.values())
    present_w = sum(FEATURE_WEIGHTS[k] for k in FEATURE_KEYS if present.get(k))
    evidence_ratio = present_w / total_w if total_w > 0 else 0.0

    # 1.0 margin never happens — typical margin ~ 0.02..0.12. Scale aggressively.
    margin_score = min(1.0, margin * 12.0)  # 0..1
    # Blend:
    raw = 0.35 + 0.5 * margin_score + 0.4 * (evidence_ratio - 0.5)
    return max(0.0, min(1.0, raw)) * 100.0


def _breakdown(vec: dict[str, float], best_persona: str) -> list[dict]:
    """Per-feature contribution: closer to centroid = higher contribution.

    Zero-weight axes are omitted. A weight of 0 means the axis took no part
    in choosing this persona (see the FEATURE_WEIGHTS note on D9), so listing
    it would present a number the classification never used — the breakdown
    is meant to answer "why this persona", and a 0-weight row answers nothing.
    """
    centroid = PERSONA_CENTROIDS_V2[best_persona]
    rows: list[dict] = []
    for key, cz in zip(FEATURE_KEYS, centroid):
        if FEATURE_WEIGHTS[key] == 0:
            continue
        dist = abs(vec[key] - cz)
        # Raw "closeness" ∈ [0, 1]. Weight-scaled contribution.
        closeness = 1.0 - min(1.0, dist)
        rows.append({
            "feature": key,
            "label": FEATURE_LABELS[key],
            "value": round(vec[key], 3),
            "centroid": round(cz, 3),
            "closeness": round(closeness, 3),
            "weight": FEATURE_WEIGHTS[key],
        })
    rows.sort(key=lambda r: r["closeness"] * r["weight"], reverse=True)
    return rows


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

# ``flask.g`` cache key. Stored as ``g._persona_classify_cache``;
# cleared automatically at the end of every request.
_REQUEST_CACHE_ATTR = "_persona_classify_cache"


def _request_cache_get(key: tuple[int, int]) -> dict | None:
    """Return cached classification for ``(user_id, window_days)`` if any.

    Returns ``None`` outside of a Flask request context (e.g. cron jobs)
    so the caller still computes fresh — this avoids leaking state
    across cron iterations.
    """
    if not has_request_context():
        return None
    cache = getattr(g, _REQUEST_CACHE_ATTR, None)
    if not isinstance(cache, dict):
        return None
    return cache.get(key)


def _request_cache_set(key: tuple[int, int], value: dict) -> None:
    if not has_request_context():
        return
    cache = getattr(g, _REQUEST_CACHE_ATTR, None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(g, _REQUEST_CACHE_ATTR, cache)
    cache[key] = value


def classify_persona_multi(
    user_id: int,
    window_days: int = 90,
    now: datetime | None = None,
) -> dict:
    """Classify a user on the 9-D feature vector.

    Per-request memoization
    -----------------------
    Within a single Flask request the result is cached on ``flask.g``
    keyed by ``(user_id, window_days)``. This is critical because both
    :func:`get_persona_confidence` and
    :func:`explain_persona_classification` previously re-ran the full
    DB-heavy pipeline for the same user — a single endpoint could end
    up hitting the trades / positions / pulse / feedback tables 3 times.

    Cache is bypassed when:
      * No Flask request context (cron / CLI calls always recompute).
      * Caller passes an explicit ``now`` (forces a deterministic
        recompute, used by tests).

    Returns
    -------
    {
        "persona": "quant",
        "label":   "Quant CFO",
        "tagline": "감이 아닌 검증된 엣지.",
        "confidence": 72,     # 0..100
        "window_days": 90,
        "data_sparse": False, # True when trade_count < MIN_TRADES_FOR_OBSERVATION
        "trade_count": 23,
        "features": {...},    # raw feature values
        "present":  {...},    # which features had evidence (1/0)
        "ranking": [
            {"persona": "quant", "similarity": 0.87},
            {"persona": "balanced", "similarity": 0.81},
            ...
        ],
        "breakdown": [...],   # per-feature contributions to the winning persona
        "declared_persona": "growth",
        "last_computed_at": "2026-04-24T...",
    }
    """
    if now is None:
        cached = _request_cache_get((int(user_id), int(window_days)))
        if cached is not None:
            return cached
    now = _utc_now() if now is None else now

    trades = _fetch_trades(user_id)
    positions = _fetch_positions(user_id)
    profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
    declared = _resolve_declared(profile)

    bundle = _extract_features(user_id, trades, positions, profile, window_days, now)
    ranking = _similarity_ranking(bundle.values)
    best_persona, _best_sim = ranking[0]

    # If we have no observed trade evidence at all, lean on declared persona
    # to avoid mis-labelling a brand-new account based on pure defaults.
    trade_count = sum(1 for t in trades if t.traded_at and t.traded_at >= now - timedelta(days=window_days))
    if trade_count < 3 and declared in PERSONA_CODES:
        best_persona = declared

    confidence = _confidence_from_ranking(ranking, bundle.present)
    data_sparse = trade_count < MIN_TRADES_FOR_OBSERVATION

    payload = {
        "persona":          best_persona,
        "label":            PERSONA_LABELS[best_persona],
        "tagline":          PERSONA_TAGLINES[best_persona],
        "confidence":       int(round(confidence)),
        "window_days":      window_days,
        "data_sparse":      bool(data_sparse),
        "trade_count":      int(trade_count),
        "features":         {k: round(v, 3) for k, v in bundle.values.items()},
        "present":          dict(bundle.present),
        "ranking": [
            {"persona": p, "similarity": round(s, 4)}
            for p, s in ranking
        ],
        "breakdown":        _breakdown(bundle.values, best_persona),
        "declared_persona": declared,
        "last_computed_at": now.isoformat(),
    }
    # Only cache classifications keyed off the implicit clock — caller-
    # supplied ``now`` is reserved for deterministic test paths and
    # must not leak into the per-request cache.
    _request_cache_set((int(user_id), int(window_days)), payload)
    return payload


def get_persona_confidence(user_id: int, window_days: int = 90) -> int:
    """Scalar 0..100 confidence — convenience wrapper."""
    return classify_persona_multi(user_id, window_days=window_days)["confidence"]


def explain_persona_classification(user_id: int, window_days: int = 90) -> dict:
    """Return ``{"persona", "breakdown", "features"}`` only.

    Intended for UI tooltips — strips the fatter fields of the full
    classification payload.
    """
    full = classify_persona_multi(user_id, window_days=window_days)
    return {
        "persona":    full["persona"],
        "label":      full["label"],
        "confidence": full["confidence"],
        "breakdown":  full["breakdown"],
        "features":   full["features"],
    }


# ─────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────
#
# ``_utc_now`` is now imported from :mod:`services.profile.common_util`
# (see top of file). The previous local copy is removed to keep the
# clock semantics identical across the profile package.


__all__ = [
    "classify_persona_multi",
    "get_persona_confidence",
    "explain_persona_classification",
    "FEATURE_KEYS",
    "FEATURE_LABELS",
    "FEATURE_WEIGHTS",
    "PERSONA_CENTROIDS_V2",
]
