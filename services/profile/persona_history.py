"""persona_history — PersonaSnapshot persistence + Evolution Timeline.

Backs Feature 3 (snapshot persistence) and Feature 4 (drift / timeline).
The four public functions form the read/write contract between the
weekly cron, the API layer, and the future "Evolution Timeline" UI:

    take_snapshot(user_id, window_days=90, now=None) -> PersonaSnapshot | None
    get_history(user_id, days_back=180)              -> list[dict]
    compute_drift(snapshots: list[dict])             -> dict
    detect_significant_drift(user_id, threshold=0.25)-> dict | None

Legal posture
-------------
Every textual field surfaced by these helpers is **observational** —
"관찰됨", "이동 중", "유지", "변화 관찰". No "추천" / "조언" /
"recommendation" / "advice" wording, anywhere on this read or write
path. The frontend is contractually bound to the same vocabulary; the
``DRIFT_DISCLAIMER`` constant below is the canonical legal footer that
endpoints append to every drift response.

Idempotence
-----------
``take_snapshot`` swallows ``IntegrityError`` from the
``UNIQUE(user_id, computed_at)`` constraint — the second of two
concurrent writes (cron + manual trigger inside the same second) is a
no-op rather than a 500. Returns ``None`` in that case.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import PersonaSnapshot, TradeHistory
from services.profile.common_util import utc_now as _utc_now
from services.profile.persona_classifier_v2 import (
    FEATURE_KEYS,
    classify_persona_multi,
)


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Public legal text — observational only.
# ─────────────────────────────────────────────────────────────────────
DRIFT_DISCLAIMER = (
    "본 결과는 사용자의 과거 거래/설문 데이터에 기반한 행동 패턴 관찰 "
    "기록이며, 투자 추천이나 조언이 아닙니다."
)

# Observation vocabulary — every drift message MUST come from this set.
_DRIFT_DESCRIPTORS = {
    "stable": "유지 관찰",
    "moving": "이동 중 관찰",
    "transition": "영역 이동 관찰",
}

# Default observation window for ``detect_significant_drift``.
_DEFAULT_DRIFT_WINDOW_DAYS = 28  # ~4 weeks

# An "active" user — eligible for the weekly cron snapshot — is one
# whose most recent TradeHistory is within the lookback. We use trade
# activity as a proxy for engagement because the User model has no
# ``last_login`` column (see HANDOVER + models/user.py). Onboarded users
# with no trades are skipped: the classifier would just return defaults
# for every dimension, polluting the historical series.
_ACTIVE_USER_TRADE_LOOKBACK_DAYS = 90


# ═════════════════════════════════════════════════════════════════════
# take_snapshot — write path
# ═════════════════════════════════════════════════════════════════════

def take_snapshot(
    user_id: int,
    window_days: int = 90,
    now: datetime | None = None,
) -> PersonaSnapshot | None:
    """Compute a fresh classification and persist it.

    Returns the persisted :class:`PersonaSnapshot` row, or ``None`` if
    the row could not be inserted (UNIQUE collision against an existing
    snapshot at the same ``computed_at`` second).

    The caller is expected to be inside a Flask app context — callers
    include the weekly cron, the admin trigger endpoint and tests.
    """
    when = _utc_now() if now is None else now
    payload = classify_persona_multi(
        user_id, window_days=window_days, now=when,
    )

    row = PersonaSnapshot(
        user_id=int(user_id),
        # Mirror the classifier's own clock — the response payload's
        # ``last_computed_at`` is the canonical one.
        computed_at=_parse_iso(payload.get("last_computed_at")) or when,
        persona=str(payload.get("persona") or "balanced"),
        confidence=int(payload.get("confidence") or 0),
        features=json.dumps(payload.get("features") or {},
                            ensure_ascii=False),
        present_mask=json.dumps(payload.get("present") or {},
                                ensure_ascii=False),
        ranking=json.dumps(payload.get("ranking") or [],
                           ensure_ascii=False),
        breakdown=json.dumps(payload.get("breakdown") or [],
                             ensure_ascii=False),
        declared_persona=payload.get("declared_persona"),
        trade_count=int(payload.get("trade_count") or 0),
        window_days=int(payload.get("window_days") or window_days),
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        # UNIQUE(user_id, computed_at) collision — the cron coalesced
        # with a manual trigger. Treat as success-equivalent no-op.
        db.session.rollback()
        logger.info(
            "persona_history.take_snapshot: UNIQUE collision skipped "
            "(user_id=%s, computed_at=%s)",
            user_id, row.computed_at,
        )
        return None
    return row


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        out = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if out.tzinfo is not None:
            out = out.astimezone(out.tzinfo).replace(tzinfo=None)
        return out
    except (ValueError, TypeError):
        logger.debug("silent-fallback: _parse_iso", exc_info=True)
        return None


# ═════════════════════════════════════════════════════════════════════
# get_history — read path (oldest → newest)
# ═════════════════════════════════════════════════════════════════════

def get_history(
    user_id: int,
    days_back: int = 180,
    now: datetime | None = None,
) -> list[dict]:
    """Return the user's persona snapshots, oldest → newest.

    Bounded scan: we never return more than 365 days of history (older
    rows are still kept for audit but the timeline UI doesn't need them).

    Empty list when the user has no snapshots — *never* raises. This is
    a graceful-degradation contract the frontend SWR layer relies on.

    ``now`` overrides the clock the ``days_back`` cutoff is measured from,
    matching the convention already used by :func:`record_snapshot` and
    :func:`compute_drift` in this module. Callers that already resolved a
    reference time (LivingMirrorService takes ``now=`` and threads it
    through every other query) must pass it here too — otherwise this one
    query silently reads the wall clock and the caller's result stops
    being a pure function of its inputs. Added 2026-08-30 after exactly
    that: ``_resolve_stage`` accepted ``when`` but dropped it here, so
    fixed-clock tests decayed into failures once real time drifted past
    the window.
    """
    days_back = max(1, min(365, int(days_back)))
    cutoff = (_utc_now() if now is None else now) - timedelta(days=days_back)
    rows = (
        PersonaSnapshot.query
        .filter(PersonaSnapshot.user_id == int(user_id))
        .filter(PersonaSnapshot.computed_at >= cutoff)
        .order_by(PersonaSnapshot.computed_at.asc())
        .all()
    )
    return [r.to_dict() for r in rows]


# ═════════════════════════════════════════════════════════════════════
# compute_drift — pure function over a snapshot series
# ═════════════════════════════════════════════════════════════════════

def compute_drift(snapshots: list[dict]) -> dict:
    """Summarise persona/feature drift over a series of snapshots.

    ``snapshots`` is the output of :func:`get_history` — a list of dicts
    ordered oldest → newest. Returns a dict shaped:

        {
            "available": bool,
            "n_snapshots": int,
            "first_at": iso | None,
            "last_at":  iso | None,
            "first_persona": str | None,
            "last_persona":  str | None,
            "feature_distance": float,         # weighted L2, 0..~1
            "transitions": [                   # adjacent persona changes
                {"from": "...", "to": "...", "at": iso},
                ...
            ],
            "dominant_changes": [              # |Δfeature| desc, top 3
                {"feature": "...", "delta": +0.18, "first": 0.42, "last": 0.60},
                ...
            ],
            "descriptor": "유지 관찰" | "이동 중 관찰" | "영역 이동 관찰",
            "disclaimer": DRIFT_DISCLAIMER,
        }
    """
    if not snapshots:
        return {
            "available": False,
            "n_snapshots": 0,
            "first_at": None,
            "last_at": None,
            "first_persona": None,
            "last_persona": None,
            "feature_distance": 0.0,
            "transitions": [],
            "dominant_changes": [],
            "descriptor": _DRIFT_DESCRIPTORS["stable"],
            "disclaimer": DRIFT_DISCLAIMER,
        }
    first = snapshots[0]
    last = snapshots[-1]

    # Persona transitions — adjacent pairs only, so we list each
    # individual move in chronological order. (A→B→A surfaces twice.)
    transitions: list[dict] = []
    for prev, curr in zip(snapshots, snapshots[1:]):
        p_persona = prev.get("persona")
        c_persona = curr.get("persona")
        if p_persona and c_persona and p_persona != c_persona:
            transitions.append({
                "from": p_persona,
                "to": c_persona,
                "at": curr.get("computed_at"),
            })

    # Feature distance — Euclidean over the 9-D feature vector. Both
    # snapshots may be missing dimensions; fall back to neutral 0.5
    # (the same default the classifier uses).
    f0 = first.get("features") or {}
    f1 = last.get("features") or {}
    sq = 0.0
    for k in FEATURE_KEYS:
        a = float(f0.get(k, 0.5))
        b = float(f1.get(k, 0.5))
        sq += (b - a) ** 2
    distance = math.sqrt(sq / max(1, len(FEATURE_KEYS)))

    # Dominant feature changes — biggest absolute deltas.
    deltas: list[dict] = []
    for k in FEATURE_KEYS:
        a = float(f0.get(k, 0.5))
        b = float(f1.get(k, 0.5))
        deltas.append({
            "feature": k,
            "delta": round(b - a, 4),
            "first": round(a, 4),
            "last": round(b, 4),
        })
    deltas.sort(key=lambda d: abs(d["delta"]), reverse=True)
    dominant = deltas[:3]

    # Descriptor — observational only.
    if first.get("persona") != last.get("persona"):
        descriptor = _DRIFT_DESCRIPTORS["transition"]
    elif distance >= 0.10:
        descriptor = _DRIFT_DESCRIPTORS["moving"]
    else:
        descriptor = _DRIFT_DESCRIPTORS["stable"]

    return {
        "available": True,
        "n_snapshots": len(snapshots),
        "first_at": first.get("computed_at"),
        "last_at": last.get("computed_at"),
        "first_persona": first.get("persona"),
        "last_persona": last.get("persona"),
        "feature_distance": round(distance, 4),
        "transitions": transitions,
        "dominant_changes": dominant,
        "descriptor": descriptor,
        "disclaimer": DRIFT_DISCLAIMER,
    }


# ═════════════════════════════════════════════════════════════════════
# detect_significant_drift — recent-window monitor
# ═════════════════════════════════════════════════════════════════════

def detect_significant_drift(
    user_id: int,
    threshold: float = 0.25,
    window_days: int = _DEFAULT_DRIFT_WINDOW_DAYS,
) -> dict | None:
    """Return a drift summary if a 4-week change exceeds ``threshold``.

    "Significant" means either:
      * the persona label changed between the oldest and newest
        snapshot in the window, OR
      * the weighted feature distance exceeds ``threshold``.

    Returns ``None`` when:
      * the user has fewer than 2 snapshots in the window (not enough
        signal to claim drift), OR
      * the change is below threshold (steady state).

    ``threshold`` is in the same units as
    :func:`compute_drift`'s ``feature_distance`` — the per-feature RMS
    of changes in [0, 1]. 0.25 is roughly "a quarter of one feature
    flipped end-to-end", a deliberately conservative bar.
    """
    cutoff_days = max(7, int(window_days))
    snapshots = get_history(user_id, days_back=cutoff_days)
    if len(snapshots) < 2:
        return None

    drift = compute_drift(snapshots)
    persona_changed = drift["first_persona"] != drift["last_persona"]
    distance_exceeded = drift["feature_distance"] >= float(threshold)

    if not (persona_changed or distance_exceeded):
        return None

    # Build a single-line, observational message for the UI banner.
    if persona_changed:
        message = (
            f"{drift['first_persona']} → {drift['last_persona']} "
            "영역 이동 관찰"
        )
    else:
        message = "행동 패턴 이동 중 관찰"

    return {
        "user_id": int(user_id),
        "window_days": cutoff_days,
        "threshold": float(threshold),
        "feature_distance": drift["feature_distance"],
        "persona_changed": bool(persona_changed),
        "first_persona": drift["first_persona"],
        "last_persona": drift["last_persona"],
        "transitions": drift["transitions"],
        "dominant_changes": drift["dominant_changes"],
        "message": message,
        "descriptor": drift["descriptor"],
        "disclaimer": DRIFT_DISCLAIMER,
    }


# ═════════════════════════════════════════════════════════════════════
# Cron support — yield active user ids
# ═════════════════════════════════════════════════════════════════════

def iter_active_user_ids(
    lookback_days: int = _ACTIVE_USER_TRADE_LOOKBACK_DAYS,
    now: datetime | None = None,
) -> Iterable[int]:
    """Yield ``user_id`` for every user with a TradeHistory row in window.

    The User model has no ``last_login`` column (see ``models/user.py``)
    so we use trade activity as the engagement proxy. Returns a unique,
    deterministic list — duplicates collapsed.
    """
    when = _utc_now() if now is None else now
    cutoff = when - timedelta(days=max(1, int(lookback_days)))
    rows = (
        db.session.query(TradeHistory.user_id)
        .filter(TradeHistory.traded_at >= cutoff)
        .distinct()
        .all()
    )
    seen: set[int] = set()
    for (uid,) in rows:
        if uid is None:
            continue
        uid_int = int(uid)
        if uid_int in seen:
            continue
        seen.add(uid_int)
        yield uid_int


def run_weekly_snapshots(
    window_days: int = 90,
    now: datetime | None = None,
) -> dict:
    """APScheduler entry point — snapshot every active user.

    Returns a summary dict suitable for the scheduler log line. Per-user
    failures are caught and logged individually so a single bad row
    can't block the rest of the cron — same pattern as every other
    weekly job in :mod:`app`.
    """
    when = _utc_now() if now is None else now
    n_attempted = 0
    n_written = 0
    n_skipped_dup = 0
    n_failed = 0
    for user_id in iter_active_user_ids(now=when):
        n_attempted += 1
        try:
            row = take_snapshot(user_id, window_days=window_days, now=when)
            if row is None:
                n_skipped_dup += 1
            else:
                n_written += 1
        except Exception:
            n_failed += 1
            logger.exception(
                "persona_history.run_weekly_snapshots: failed for user_id=%s",
                user_id,
            )
    return {
        "attempted": n_attempted,
        "written": n_written,
        "skipped_dup": n_skipped_dup,
        "failed": n_failed,
        "window_days": int(window_days),
        "computed_at": when.isoformat(),
    }


__all__ = [
    "DRIFT_DISCLAIMER",
    "take_snapshot",
    "get_history",
    "compute_drift",
    "detect_significant_drift",
    "iter_active_user_ids",
    "run_weekly_snapshots",
]
