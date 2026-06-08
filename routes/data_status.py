"""Data freshness status — public surface for in-app stale banner (Wave G C-CS3).

==============================================================================
Why this exists
==============================================================================
The nightly ``scripts/nightly/ticker_health.py`` cron probes a representative
basket of US + KR tickers via the real ``/api/realtime/price/{ticker}`` route
and writes a JSONL artifact. ``ticker_health_alert.py`` then summarises that
artifact and Slack-alerts when too many tickers are stale.

That signal is operator-facing only — end users never see it. C-CS3 closes
that gap by exposing a minimal *read-only* endpoint that the frontend
``<DataStaleBanner />`` polls every five minutes. When the most-recent
artifact reports an above-threshold stale ratio, the banner surfaces a quiet
notice ("일부 시세 데이터가 지연되고 있어요…") so the user understands why a
price might look frozen.

==============================================================================
Contract (locked — frontend depends on these field names)
==============================================================================
``GET /api/data/stale-status``

    200 OK  {
        "is_stale":         bool,
        "stale_ratio":      float,            # 0.0 - 1.0 (worst market)
        "affected_markets": ["KR" | "US", …], # only markets over threshold
        "updated_at":       "YYYY-MM-DDTHH:MM:SSZ" | null,
        "threshold_pct":    float,            # echo of the rule used
    }

==============================================================================
Graceful-fallback contract
==============================================================================
This endpoint MUST NEVER false-alarm. The whole point of the banner is to
surface *real* degradation; a transient FS hiccup or a missing artifact (cron
just hasn't run yet) must return ``is_stale=false`` with empty
``affected_markets``. The four no-data branches:

  1. Artifact path missing            → is_stale=false (cron hasn't run)
  2. Artifact exists but empty/malformed → is_stale=false (skipped lines logged)
  3. Total probed tickers in market = 0  → is_stale=false (no signal)
  4. OS error reading file            → is_stale=false (logged, no raise)

==============================================================================
Cost / scope
==============================================================================
- Pure file read + count. No DB, no external API, no cache layer needed.
- Reuses ``ticker_health_alert.compute_stale_stats`` so the rule is defined
  in exactly one place; if the operator threshold changes (currently 5 %)
  the user-facing banner moves with it.
- Public endpoint — banner needs to surface even on landing / pre-auth flows
  where the realtime stream is intentionally idle.
"""

# legal-exempt: public feed-health status endpoint, no investment content
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

data_status_bp = Blueprint("data_status", __name__)

# Threshold mirrors ``ticker_health_alert.main``'s default (5 %). Surfaced in
# the response so the frontend doesn't have to hard-code the same constant.
_DEFAULT_STALE_THRESHOLD_PCT = 0.05

# Default path matches scripts/nightly/ticker_health.py's RESULTS_PATH default.
_DEFAULT_RESULTS_PATH = "nightly_artifacts/ticker_health.jsonl"


def _empty_payload(threshold_pct: float) -> dict[str, Any]:
    """Standard 'no data → not stale' shape used by every fallback branch."""
    return {
        "is_stale": False,
        "stale_ratio": 0.0,
        "affected_markets": [],
        "updated_at": None,
        "threshold_pct": threshold_pct,
    }


@data_status_bp.route("/api/data/stale-status", methods=["GET"])
def stale_status():
    """Summarise the latest ticker_health artifact for the in-app banner.

    Public on purpose — the banner is mounted at the (dashboard) layout
    level but also lives in pre-auth flows (landing, beta gate). Returning
    a generic boolean from a public endpoint leaks zero PII.
    """
    threshold_pct = _DEFAULT_STALE_THRESHOLD_PCT

    # Live in-process KR feed health overlays the nightly ticker_health
    # artifact: a mid-session KIS stall flips kr_health().degraded
    # immediately, so the banner surfaces a systemic KR delay before the next
    # nightly artifact would. Self-clears on the next KR success; the banner's
    # own ~5-min poll naturally debounces transient single-poll blips.
    kr_live_degraded = False
    try:
        from services.container import realtime as _rt
        kr_live_degraded = bool(_rt.kr_health().get("degraded"))
    except Exception:
        logger.debug("kr_health overlay in stale-status failed", exc_info=True)

    def _respond(payload: dict[str, Any]):
        if kr_live_degraded:
            payload = dict(payload)
            payload["is_stale"] = True
            markets = list(payload.get("affected_markets") or [])
            if "KR" not in markets:
                markets.append("KR")
            payload["affected_markets"] = markets
        return jsonify(payload)

    results_path = Path(os.environ.get("RESULTS_PATH", _DEFAULT_RESULTS_PATH))

    if not results_path.exists():
        # Cron hasn't run yet (fresh deploy, dev laptop). Don't false-alarm.
        return _respond(_empty_payload(threshold_pct))

    # Import lazily so this blueprint stays import-cheap on cold starts and
    # so a refactor of scripts/nightly/ doesn't break the public surface at
    # import time.
    try:
        from scripts.nightly import ticker_health_alert as _alert
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("ticker_health_alert import failed: %s", exc)
        return _respond(_empty_payload(threshold_pct))

    try:
        rows = _alert._read_artifact(results_path)
    except Exception as exc:  # pragma: no cover — _read_artifact already guards OSError
        logger.warning("ticker_health artifact read failed: %s", exc)
        return _respond(_empty_payload(threshold_pct))

    if not rows:
        return _respond(_empty_payload(threshold_pct))

    # Evaluate KR and US independently so the banner can name the affected
    # region. A KIS outage typically nukes KR alone; an FMP outage nukes US
    # alone — the user wants to know *which* feed is degraded.
    affected: list[str] = []
    worst_ratio = 0.0
    for market in ("KR", "US"):
        try:
            stats = _alert.compute_stale_stats(rows, market)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("compute_stale_stats(%s) failed: %s", market, exc)
            continue
        if stats["total"] == 0:
            continue
        ratio = float(stats["stale_ratio"])
        if ratio > worst_ratio:
            worst_ratio = ratio
        if ratio > threshold_pct:
            affected.append(market)

    # Artifact mtime gives the user a 'as of …' anchor. Falls back to None
    # if stat() fails (e.g. unlinked between exists() and stat()).
    updated_at: str | None
    try:
        mtime = results_path.stat().st_mtime
        updated_at = (
            datetime.fromtimestamp(mtime, tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except OSError:
        updated_at = None

    return _respond({
        "is_stale": bool(affected),
        "stale_ratio": round(worst_ratio, 4),
        "affected_markets": affected,
        "updated_at": updated_at,
        "threshold_pct": threshold_pct,
    })
