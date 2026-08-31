"""Mirror Home — the read-only "거울" landing surface (선언 vs 관찰 + 트윈).

The single composed read for the new Mirror-centric home. It assembles
existing, already-shipped services into one payload so the frontend can
render the "오늘의 거울" hero without four separate round-trips:

  1. Declared persona (3-bucket disclosed label + tagline)   — persona_analytics
  2. Observed persona over 30d (9-dim feature vector)         — persona_classifier_v2
  3. The gap: top dimensions where 관찰 diverges from 선언     — computed here
  4. Drift descriptor (유지 / 이동 중 / 영역 이동 관찰)        — persona_history

Legal posture (mirrors services/artifacts/living_mirror_service.py):
  • NEVER surfaces an 8-code persona (value / speculator / daytrader …).
    Only the 3 disclosed buckets 성장형 / 균형형 / 수익형 via surface_label.
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

from services.profile import (
    classify_persona_multi,
    compute_drift,
    compute_persona_response,
    get_history,
)
from services.profile.persona_analytics import surface_label
from services.profile.persona_classifier_v2 import (
    FEATURE_KEYS,
    FEATURE_LABELS,
    PERSONA_CENTROIDS_V2,
)

from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

mirror_home_bp = Blueprint("mirror_home", __name__, url_prefix="/api/mirror-home")

# Below this many in-window closed trades we render the declared-only "new"
# stage (no observed overlay, no gap) — matches MIN_TRADES_FOR_LIVING_MIRROR
# in services/artifacts/living_mirror_service.py so the two surfaces agree.
_MIN_TRADES_FOR_OBSERVED = 5
_OBSERVED_WINDOW_DAYS = 30
_GAP_TOP_N = 3


def _declared_centroid(code: str) -> list[float]:
    """9-dim shape implied by the declared persona's questionnaire centroid."""
    vec = PERSONA_CENTROIDS_V2.get(code) or PERSONA_CENTROIDS_V2["balanced"]
    return [float(v) for v in vec]


def _gap(declared_vec: list[float], observed_vec: list[float]) -> list[dict]:
    """Top dimensions where 관찰 diverges most from 선언.

    Neutral, factual, directional — never a persona name or a verdict.
    """
    diffs = []
    for i, key in enumerate(FEATURE_KEYS):
        delta = observed_vec[i] - declared_vec[i]
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

    # (1) Declared persona — already collapsed to the 3 disclosed buckets.
    persona = compute_persona_response(user_id)
    declared = persona.get("declared", {})
    declared_code = declared.get("persona", "balanced")
    declared_vec = _declared_centroid(declared_code)

    # (2) Observed persona over 30d → 9-dim feature vector (ordered by FEATURE_KEYS).
    try:
        clf = classify_persona_multi(user_id, window_days=_OBSERVED_WINDOW_DAYS)
    except Exception:  # pragma: no cover — defensive; classifier should degrade
        logger.debug("mirror-home: classify_persona_multi failed", exc_info=True)
        clf = {}
    observed_features = clf.get("features", {}) or {}
    observed_vec = [float(observed_features.get(k, 0.5)) for k in FEATURE_KEYS]
    trade_count = int(clf.get("trade_count", 0) or 0)
    observed_code = clf.get("persona")
    # Gate on closed-trade count only — matches the Living Mirror artifact's
    # 5-trade threshold so the two surfaces agree. (The classifier's own
    # data_sparse flag uses a stricter 10; ANDing it here kept the home in the
    # "new" stage until 10 while the PDF already showed the observed overlay at
    # 5 — a cross-surface contradiction. P2 fix 2026-06-15.)
    has_observed = trade_count >= _MIN_TRADES_FOR_OBSERVED
    stage = "observed" if has_observed else "new"

    # (3) The gap — only meaningful once behaviour is observed.
    gap = _gap(declared_vec, observed_vec) if has_observed else []

    # Observed bucket (3-bucket disclosed label only — never the 8-code).
    observed_label = (
        surface_label(observed_code) if (has_observed and observed_code) else None
    )
    declared_label = declared.get("label")
    bucket_changed = bool(observed_label and observed_label != declared_label)

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
        "declared": {
            "label": declared_label,
            "tagline": declared.get("tagline"),
            "score": declared.get("score"),
        },
        "observed": {
            "label": observed_label,
            "bucket_changed": bucket_changed,
            "trade_count": trade_count,
        },
        "gap": gap,
        "drift": drift,
        "radar": {
            "keys": list(FEATURE_KEYS),
            "labels": [FEATURE_LABELS.get(k, k) for k in FEATURE_KEYS],
            "declared": [round(v, 3) for v in declared_vec],
            "observed": (
                [round(v, 3) for v in observed_vec] if has_observed else None
            ),
        },
    })
