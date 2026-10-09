"""Mirror Home — the read-only "거울" landing surface (선언 vs 관찰 + 트윈).

The single composed read for the new Mirror-centric home. It assembles
existing, already-shipped services into one payload so the frontend can
render the "오늘의 거울" hero without four separate round-trips:

  1. Declared shape (the user's own V3 answers, or centroid)  — persona_analytics
  2. Observed persona over 30d (9-dim feature vector)         — persona_classifier_v2
  3. The gap: top dimensions where 관찰 diverges from 선언     — computed here
  4. Drift descriptor (유지 / 이동 중 / 영역 이동 관찰)        — persona_history

Legal posture (mirrors services/artifacts/living_mirror_service.py):
  • NEVER surfaces a persona name — neither an 8-code (value / speculator …)
    nor a 3-bucket label (성장형 / 균형형 / 수익형). CEO 2026-09-29: the
    mirror shows facts, no type labels (CLAUDE.md "유형 라벨·점수는 만들지
    않는다"). The classifier still runs internally (declared centroid, the
    observed feature vector, drift); only its label is no longer exposed.
  • No score / grade / percentile on the radar — raw 0..1 vectors are sent
    for *shape* rendering only; the frontend prints no numbers on them.
  • The "gap" is expressed as neutral behavioural dimensions
    (평균 보유기간 ↑ / 매매 회전율 ↓), never as advice or a directive.
  • @legal_scrub_response is the belt-and-suspenders final filter.

Read-only. No I/O beyond the read-only persona/twin pipelines. Degrades
to stage="new" (declared shape only) for users without enough trades —
exactly like the Living Mirror artifact's stage 1.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from flask_login import current_user

from extensions import db
from models import InvestmentProfile, Position

from services.profile import (
    classify_persona_multi,
    compute_drift,
    compute_persona_response,
    get_history,
)
from services.profile.persona_analytics import _norm_log
from services.profile.questionnaire import declared_ranges
from services.profile.persona_classifier_v2 import (
    FEATURE_KEYS,
    FEATURE_LABELS,
    PERSONA_CENTROIDS_V2,
)

from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

mirror_home_bp = Blueprint("mirror_home", __name__, url_prefix="/api/mirror-home")

# Below this many in-window trades we render the declared-only "new" stage
# (no observed overlay, no gap). "Trades" = every recorded fill, buy AND sell,
# whose traded_at falls in the 30-day window, minus holding-registration rows
# (classify_persona_multi's ``trade_count``) — NOT closed round trips. The
# Living Mirror artifact this threshold was once aligned with has been deleted
# (services/artifacts/ no longer exists), so 5 stands on its own.
_MIN_TRADES_FOR_OBSERVED = 5
_OBSERVED_WINDOW_DAYS = 30
_GAP_TOP_N = 3
# A chip rounds |delta| to whole %p; below 1%p it would read "↑0%p" — noise,
# not a gap. Such axes are dropped from the gap list.
_GAP_MIN_DELTA = 0.01
# Classifier features that are self-reported, not observed from trades.
_NEVER_OBSERVED_AXES = frozenset({"declared_risk"})
# The axis Q3 (declared_positions) is projected onto.
_POSITIONS_AXIS = "ticker_diversity"


def _open_position_count(user_id: int) -> int:
    """Distinct tickers the user currently holds (shares > 0). No prices."""
    try:
        rows = (
            db.session.query(Position.ticker)
            .filter(Position.user_id == user_id, Position.shares > 0)
            .all()
        )
    except Exception:  # pragma: no cover — defensive; must not 500 the home
        logger.debug("mirror-home: positions unreadable", exc_info=True)
        return 0
    return len({(t or "").upper() for (t,) in rows if t})


def _declared_centroid(code: str) -> list[float]:
    """9-dim shape implied by the declared persona's questionnaire centroid."""
    vec = PERSONA_CENTROIDS_V2.get(code) or PERSONA_CENTROIDS_V2["balanced"]
    return [float(v) for v in vec]


def _declared_shape(
    user_id: int, code: str,
) -> tuple[list[float], list[str], str, dict[str, tuple[float, float]]]:
    """The 9-dim "선언" vector and which axes the user actually declared.

    2026-09-06 (questionnaire V3): when the user answered the V3 wizard, the
    declared value on each axis they spoke to comes from THEIR OWN answer
    (``InvestmentProfile.declared_vector_json``), projected onto the observed
    feature scale by ``questionnaire.calculate_profile_v3``. Axes they were
    not asked about fall back to the persona centroid so the radar keeps a
    complete shape — but the gap below is computed only over declared axes,
    because "you said X" is the only honest baseline for "you did Y".

    Pre-V3 rows and skip-path users have no declared vector; the centroid is
    used on every axis, exactly as before, and ``source`` says so.

    The 4th element is the answer's bucket ``{axis: (lo, hi)}`` on the same
    scale (2026-09-29) — the gap is measured against it, not the midpoint.
    """
    vec = _declared_centroid(code)
    try:
        profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
        declared = profile.declared_vector() if profile is not None else {}
        ranges = declared_ranges(profile.onboarding_answers()) if profile is not None else {}
    except Exception:  # pragma: no cover — defensive; a bad row must not 500 the home
        logger.debug("mirror-home: declared vector unreadable", exc_info=True)
        declared, ranges = {}, {}
    axes: list[str] = []
    for i, key in enumerate(FEATURE_KEYS):
        if key in declared:
            vec[i] = float(declared[key])
            axes.append(key)
    ranges = {k: v for k, v in ranges.items() if k in axes}
    return vec, axes, ("self" if axes else "centroid"), ranges


def _gap(
    declared_vec: list[float],
    observed_vec: list[float],
    declared_axes: list[str] | None = None,
    declared_ranges: dict[str, tuple[float, float]] | None = None,
) -> list[dict]:
    """Top dimensions where 관찰 diverges most from 선언.

    Neutral, factual, directional — never a persona name or a verdict.
    When ``declared_axes`` is given, only those axes are compared — a gap
    against a centroid the user never stated is not a gap.

    An axis with a declared range (the answer's bucket) is a gap only when the
    observed value falls OUTSIDE it, and ``delta`` is the distance to the
    nearest edge — 2026-09-29: comparing with the bucket midpoint told a user
    who declared "1~3종목" and holds 1 that they diverged by 20%p.
    """
    ranges = declared_ranges or {}
    diffs = []
    axis_filter = set(declared_axes) if declared_axes else None
    for i, key in enumerate(FEATURE_KEYS):
        if axis_filter is not None and key not in axis_filter:
            continue
        rng = ranges.get(key)
        if rng is not None:
            lo, hi = rng
            o = observed_vec[i]
            delta = o - hi if o > hi else (o - lo if o < lo else 0.0)
        else:
            delta = observed_vec[i] - declared_vec[i]
        if abs(delta) < _GAP_MIN_DELTA:
            continue
        diffs.append((abs(delta), key, delta, declared_vec[i], observed_vec[i]))
    diffs.sort(key=lambda t: t[0], reverse=True)
    out: list[dict] = []
    for _, key, delta, dval, oval in diffs[:_GAP_TOP_N]:
        out.append({
            "key": key,
            "label": FEATURE_LABELS.get(key, key),
            "direction": "up" if delta > 0 else "down",
            "delta": round(delta, 3),
            "declared": round(dval, 3),
            "observed": round(oval, 3),
        })
    return out


@mirror_home_bp.route("", methods=["GET"])
@api_auth
@legal_scrub_response
def get_mirror_home():
    """Composed read for the Mirror home. Read-only; never raises on sparse data."""
    user_id = int(current_user.id)

    # (1) Declared persona code — internal only (centroid fallback). Its label
    # and tagline are not exposed (2026-09-29).
    persona = compute_persona_response(user_id)
    declared = persona.get("declared", {})
    declared_code = declared.get("persona", "balanced")
    declared_vec, declared_axes, declared_source, declared_rngs = _declared_shape(
        user_id, declared_code,
    )

    # (2) Observed persona over 30d → 9-dim feature vector (ordered by FEATURE_KEYS).
    try:
        clf = classify_persona_multi(user_id, window_days=_OBSERVED_WINDOW_DAYS)
    except Exception:  # pragma: no cover — defensive; classifier should degrade
        logger.debug("mirror-home: classify_persona_multi failed", exc_info=True)
        clf = {}
    observed_features = clf.get("features", {}) or {}
    observed_vec = [float(observed_features.get(k, 0.5)) for k in FEATURE_KEYS]
    # Which axes the classifier actually measured. Below its own evidence
    # thresholds (e.g. holding period, sector diversity, hold variance and
    # loss-cut discipline need 10 trades in the window) it leaves the 0.5
    # "no evidence" default in ``features`` and says so in ``present``.
    # 2026-09-10: this route used to ignore that mask, so a user with 6 buys
    # was shown "평균 보유기간 ↓40%p" against a number that was never computed.
    # A payload without the mask (older callers / test doubles) counts as fully
    # measured, which is what the route assumed before.
    present = clf.get("present")
    if isinstance(present, dict) and present:
        measured_axes = [k for k in FEATURE_KEYS if present.get(k)]
    else:
        measured_axes = list(FEATURE_KEYS)
    # 2026-09-29: ``declared_risk`` is never observed behaviour — the
    # classifier reads it from ``profile.risk_tolerance``, which onboarding
    # writes from the same Q4 answer as the declared vector. Comparing it with
    # the declaration is the answer against itself (delta≈0 → "↑0%p" chip and
    # an inflated 정합도 on the client). It is not a measured axis here.
    measured_axes = [k for k in measured_axes if k not in _NEVER_OBSERVED_AXES]
    # 2026-09-29: Q3 ("보통 몇 종목을 동시에 들고 있나요?") is about HOLDINGS,
    # but the classifier's ticker_diversity counts distinct tickers TRADED in
    # the window — a buy-and-hold user with 20 names who traded 2 got a false
    # top gap. For the mirror, the observed side of this axis is the open
    # position count on the declared scale (_norm_log(n, 1, 25), see
    # questionnaire.DECLARED_VECTOR_MAP). The classifier's own feature is left
    # alone — it also drives persona classification, where "traded" is meant.
    # No open positions → not measured (holdings may simply not be imported).
    measured = set(measured_axes)
    n_open = _open_position_count(user_id)
    if n_open > 0:
        observed_vec[FEATURE_KEYS.index(_POSITIONS_AXIS)] = _norm_log(
            float(n_open), floor=1.0, ceil=25.0,
        )
        measured.add(_POSITIONS_AXIS)
    else:
        measured.discard(_POSITIONS_AXIS)
    measured_axes = [k for k in FEATURE_KEYS if k in measured]
    trade_count = int(clf.get("trade_count", 0) or 0)
    # Gate on the in-window fill count only (buys + sells, registration rows
    # excluded — see _MIN_TRADES_FOR_OBSERVED; not closed round trips). (The
    # classifier's own data_sparse flag uses a stricter 10; ANDing it here
    # kept the home in the "new" stage until 10 while the then-existing PDF
    # showed the observed overlay at 5 — P2 fix 2026-06-15.)
    has_observed = trade_count >= _MIN_TRADES_FOR_OBSERVED
    stage = "observed" if has_observed else "new"

    # (3) The gap — only meaningful once behaviour is observed.
    gap: list[dict] = []
    if has_observed:
        comparable_axes = [
            k for k in (declared_axes or FEATURE_KEYS) if k in measured_axes
        ]
        # An empty list must not reach _gap: it treats a falsy filter as
        # "compare every axis", which would reintroduce the unmeasured ones.
        if comparable_axes:
            gap = _gap(declared_vec, observed_vec, comparable_axes, declared_rngs)

    # (4) Drift descriptor — needs ≥2 persona snapshots; optional bonus framing.
    drift = {"available": False, "descriptor": None}
    try:
        snapshots = get_history(user_id, days_back=180)
        dr = compute_drift(snapshots)
        drift = {
            "available": bool(dr.get("available")),
            "descriptor": dr.get("descriptor"),
        }
    except Exception:  # pragma: no cover — defensive
        logger.debug("mirror-home: drift unavailable", exc_info=True)

    return jsonify({
        "ok": True,
        "stage": stage,
        # 2026-09-29: declared.label / declared.tagline / observed.label /
        # observed.bucket_changed removed — they carried 3-bucket type labels
        # the mirror no longer shows. The headline is built from ``gap``.
        "declared": {
            # "self" = axes come from the user's own V3 answers;
            # "centroid" = persona-centroid fallback (pre-V3 / skipped).
            "source": declared_source,
        },
        "observed": {
            "trade_count": trade_count,
        },
        "gap": gap,
        "drift": drift,
        "radar": {
            "keys": list(FEATURE_KEYS),
            "labels": [FEATURE_LABELS.get(k, k) for k in FEATURE_KEYS],
            "declared": [round(v, 3) for v in declared_vec],
            "declared_axes": declared_axes,
            "observed": (
                [round(v, 3) for v in observed_vec] if has_observed else None
            ),
            # Axes with real evidence behind ``observed``. The others still
            # carry the classifier's 0.5 default so the vector stays 9 long;
            # the client must not present them as measurements.
            "observed_axes": measured_axes if has_observed else [],
        },
    })
