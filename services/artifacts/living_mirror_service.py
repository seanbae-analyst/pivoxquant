"""Living Mirror — persona depth Artifact (선언 → 행동 → 궤적).

The persona capstone of the "User as CFO → AI가 Artifact(PDF) 생성" concept.
A single-page (sometimes two-page) PDF that mirrors the user's *declared*
persona shape, overlays their *observed* behaviour when enough trade data
exists, and narrates the *trajectory* over time when snapshot history is
available.

Legal posture (DECISIONS.md ✅확정 / §101 / 점수화 폐기)
------------------------------------------------------
This artefact is a **factual mirror only**. It never:

  • names a short-horizon persona — the user-facing surface uses the
    3-bucket disclosed labels (성장형 / 균형형 / 수익형) via
    :func:`services.profile.persona_analytics.surface_label`. The 8-code
    engine personas (incl. speculator / daytrader) are used for internal
    centroid math only and are scrubbed out of every surfaced string.
  • shows a score / grade / percentile / "상위 N%" ranking — the 9-dim
    vector is rendered as a radar *shape* (relative geometry) with no
    numeric score printed.
  • diagnoses, treats, scores, or gives advice — the disclaimer states it
    is observational, not 진단·치료·투자자문. No CBT / 치료 / 효능 wording.
  • recommends / 추천 / 조언 / BUY / SELL — zero directive vocabulary.

Three stages (branch on data availability)
------------------------------------------
1. ``new`` (관찰 거래 < ``MIN_TRADES_FOR_LIVING_MIRROR``): render only the
   *declared* radar (the 9-dim shape implied by the questionnaire persona
   centroid) plus an intentional blank section — "행동 데이터가 쌓이면
   여기 채워집니다". Even a 0-trade user gets a meaningful page.

2. ``observed`` (충분한 거래): overlay the *declared* radar (선언) and the
   *observed* radar (관찰, 30d window) on the same axes — the user reads
   the gap between declaration and behaviour as a fact, with no judgement
   and no score.

3. ``trajectory`` (스냅샷 히스토리 ≥ 2): add a neutral time-axis narration
   from :func:`services.profile.persona_history.compute_drift`
   ("유지 관찰" / "이동 중 관찰" / "영역 이동 관찰") plus a sparkline of
   weekly observed scores rendered as a shape, never a ranked number.

``generate_for_user`` is a **pure context builder** — it returns a dict
and performs no I/O beyond the read-only persona pipeline. Rendering and
persistence are separate methods, mirroring the other 17 artefact
services. No APScheduler hook is registered: this artefact is on-demand
only (CEO framing precedes any auto-send).
"""
from __future__ import annotations

import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, TradeHistory, User
from services.legal_filter import detect_prohibited, safe_scrub
from services.profile.persona_analytics import (
    compute_persona_response,
    surface_label,
    surface_tagline,
)
from services.profile.persona_classifier_v2 import (
    FEATURE_KEYS,
    FEATURE_LABELS,
    PERSONA_CENTROIDS_V2,
    classify_persona_multi,
)
from services.profile.persona_history import compute_drift, get_history
from services.artifacts._render import try_import_jinja as _try_import_jinja
from services.artifacts._render import try_import_weasyprint as _try_import_weasyprint

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "living_mirror"
)

# Stage threshold — below this many in-window trades we render the
# declared-only "new" stage with intentional blanks. Deliberately low (5)
# so a lightly-active user still sees the behaviour overlay, but a truly
# brand-new account is not shown an observed shape built from noise.
MIN_TRADES_FOR_LIVING_MIRROR = 5

# Observation window used for the observed radar overlay.
_OBSERVED_WINDOW_DAYS = 30

# History lookback for the trajectory stage.
_HISTORY_DAYS_BACK = 180

ARTIFACT_TYPE = "living_mirror"

# The single canonical disclaimer surfaced on the page. Observational,
# non-advisory, non-diagnostic, non-therapeutic. Kept in sync with the
# shared _disclaimer.html partial's posture (this is the short in-body
# line; the full bilingual legal block is the partial).
LIVING_MIRROR_NOTE = (
    "본 리포트는 사용자가 연동한 계좌의 체결 데이터와 설문 응답을 사실 "
    "그대로 비추는 관찰 기록입니다. 진단·치료·투자자문이 아니며, 점수·"
    "등급·순위를 매기지 않습니다. 모든 해석과 판단은 이용자 본인의 몫입니다."
)


def _storage_dir() -> Path:
    override = os.environ.get("LIVING_MIRROR_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─────────────────────────────────────────────────────────────────────
# Radar geometry — pure SVG point math (WeasyPrint-compatible, no JS).
# ─────────────────────────────────────────────────────────────────────

# Fixed SVG viewbox geometry. The template references the same numbers so
# the axis labels line up; keep them in one place.
RADAR_SIZE = 360.0          # viewbox is RADAR_SIZE x RADAR_SIZE
RADAR_CENTER = RADAR_SIZE / 2.0
RADAR_RADIUS = 132.0        # max ring radius (leaves room for labels)
_RADAR_RINGS = 4            # concentric reference rings


def _axis_angle(i: int, n: int) -> float:
    """Angle (radians) for axis ``i`` of ``n``, starting at 12 o'clock."""
    return (-math.pi / 2.0) + (2.0 * math.pi * i / n)


def _point_on_axis(i: int, n: int, value: float) -> tuple[float, float]:
    """Cartesian SVG point for ``value`` (0..1) along axis ``i``."""
    v = max(0.0, min(1.0, float(value)))
    angle = _axis_angle(i, n)
    r = RADAR_RADIUS * v
    x = RADAR_CENTER + r * math.cos(angle)
    y = RADAR_CENTER + r * math.sin(angle)
    return (round(x, 2), round(y, 2))


def _polygon_points(vector: list[float]) -> str:
    """``"x1,y1 x2,y2 ..."`` SVG points string for a feature vector."""
    n = len(vector)
    pts = [_point_on_axis(i, n, v) for i, v in enumerate(vector)]
    return " ".join(f"{x},{y}" for x, y in pts)


def _ring_points(scale: float, n: int) -> str:
    """Reference-ring polygon at ``scale`` (0..1) of the max radius."""
    pts = [_point_on_axis(i, n, scale) for i in range(n)]
    return " ".join(f"{x},{y}" for x, y in pts)


def _axis_endpoints(n: int) -> list[dict[str, float]]:
    """Spoke lines + label anchor points for each of ``n`` axes."""
    out: list[dict[str, float]] = []
    for i in range(n):
        ex, ey = _point_on_axis(i, n, 1.0)
        # Label sits slightly beyond the outer ring.
        lx, ly = _point_on_axis(i, n, 1.16)
        out.append({"ex": ex, "ey": ey, "lx": lx, "ly": ly})
    return out


def _build_radar(
    *,
    declared_vec: list[float],
    observed_vec: Optional[list[float]],
) -> dict[str, Any]:
    """Assemble all SVG-ready geometry for the radar.

    Returns axis metadata, reference rings, and one or two polygons. No
    numeric scores leak — only normalised [0,1] shape coordinates.
    """
    n = len(declared_vec)
    rings = [
        {"points": _ring_points((r + 1) / _RADAR_RINGS, n)}
        for r in range(_RADAR_RINGS)
    ]
    axes = []
    endpoints = _axis_endpoints(n)
    for i, key in enumerate(FEATURE_KEYS):
        ep = endpoints[i]
        axes.append({
            "key": key,
            "label": FEATURE_LABELS.get(key, key),
            "ex": ep["ex"], "ey": ep["ey"],
            "lx": ep["lx"], "ly": ep["ly"],
            # text-anchor hint so labels don't overrun the page edge.
            "anchor": _label_anchor(ep["lx"]),
        })
    out: dict[str, Any] = {
        "size": RADAR_SIZE,
        "center": RADAR_CENTER,
        "radius": RADAR_RADIUS,
        "rings": rings,
        "axes": axes,
        "declared_points": _polygon_points(declared_vec),
        "observed_points": (
            _polygon_points(observed_vec) if observed_vec is not None else None
        ),
    }
    return out


def _label_anchor(lx: float) -> str:
    if lx < RADAR_CENTER - 8:
        return "end"
    if lx > RADAR_CENTER + 8:
        return "start"
    return "middle"


# ─────────────────────────────────────────────────────────────────────
# Feature-vector helpers
# ─────────────────────────────────────────────────────────────────────

def _declared_vector(declared_code: str) -> list[float]:
    """9-dim centroid for the declared persona, in FEATURE_KEYS order."""
    centroid = PERSONA_CENTROIDS_V2.get(declared_code)
    if centroid is None:
        centroid = PERSONA_CENTROIDS_V2["balanced"]
    return [round(float(c), 4) for c in centroid]


def _observed_vector(features: dict[str, float]) -> list[float]:
    """Observed 9-dim vector from the classifier feature map.

    Missing dimensions fall back to the neutral 0.5 default (identical to
    the classifier) so the polygon is always well-defined.
    """
    return [round(float(features.get(k, 0.5)), 4) for k in FEATURE_KEYS]


def _count_trades(user_id: int) -> int:
    """Total lifetime trade rows for the user (cheap COUNT)."""
    return (
        db.session.query(TradeHistory.id)
        .filter(TradeHistory.user_id == int(user_id))
        .count()
    )


# ─────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────

class LivingMirrorService:
    """On-demand persona-depth mirror PDF (선언 → 행동 → 궤적)."""

    # ---------- main pipeline ------------------------------------------

    def generate_for_user(
        self,
        user_id: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Build the full render context for ``user_id``.

        Pure: reads the persona pipeline + snapshot history, performs no
        writes. Stage is chosen from data availability:

          • ``new``        — declared radar + intentional blanks.
          • ``observed``   — declared vs observed overlay.
          • ``trajectory`` — overlay + neutral drift narration + sparkline.
        """
        when = now or datetime.now(timezone.utc).replace(tzinfo=None)
        user = db.session.get(User, int(user_id))
        if user is None:
            raise ValueError(f"user {user_id} not found")

        # --- persona pipeline (read-only) ------------------------------
        response = compute_persona_response(user_id, now=when)
        declared_code = response["declared"]["persona"]
        declared_label = surface_label(declared_code)
        declared_tagline = surface_tagline(declared_code)

        total_trades = _count_trades(user_id)
        classification = classify_persona_multi(
            user_id, window_days=_OBSERVED_WINDOW_DAYS, now=when,
        )
        in_window_trades = int(classification.get("trade_count") or 0)

        stage = self._resolve_stage(user_id, in_window_trades, when)

        declared_vec = _declared_vector(declared_code)

        # --- observed overlay (stages observed + trajectory) -----------
        observed_vec: Optional[list[float]] = None
        observed_label: Optional[str] = None
        gap_dims: list[dict[str, Any]] = []
        if stage in ("observed", "trajectory"):
            features = classification.get("features") or {}
            observed_vec = _observed_vector(features)
            observed_code = classification.get("persona") or "balanced"
            observed_label = surface_label(observed_code)
            gap_dims = self._gap_dimensions(declared_vec, observed_vec)

        # --- trajectory narration (stage trajectory only) --------------
        trajectory: Optional[dict[str, Any]] = None
        sparkline_path: Optional[str] = None
        if stage == "trajectory":
            history = get_history(user_id, days_back=_HISTORY_DAYS_BACK, now=when)
            drift = compute_drift(history)
            trajectory = self._trajectory_view(drift)
            sparkline_path = self._sparkline_path(response.get("sparkline") or [])

        radar = _build_radar(declared_vec=declared_vec, observed_vec=observed_vec)

        ctx: dict[str, Any] = {
            "artifact_type": ARTIFACT_TYPE,
            "user_id": int(user_id),
            "user_name": user.name or (user.email or "").split("@")[0] or "User",
            "generated_at": when,
            "period_label": when.strftime("%Y.%m.%d"),
            "stage": stage,
            # Surface persona (3-bucket ONLY — never the 8-code).
            "declared_label": declared_label,
            "declared_tagline": declared_tagline,
            "observed_label": observed_label,
            # Radar geometry (relative shape only — no numeric score).
            "radar": radar,
            "has_observed": observed_vec is not None,
            "gap_dimensions": gap_dims,
            # Trajectory (None unless stage == trajectory).
            "trajectory": trajectory,
            "sparkline_path": sparkline_path,
            # Intentional-blank copy for the new stage.
            "blank_prompt": (
                "행동 데이터가 쌓이면 선언과 실제 행동의 형태를 "
                "여기에서 나란히 비춰 드립니다."
            ),
            "trajectory_blank_prompt": (
                "관찰 기록이 더 쌓이면 시간에 따른 형태 변화를 "
                "여기에서 중립적으로 서술합니다."
            ),
            "disclaimer_note": LIVING_MIRROR_NOTE,
            # License placeholder for the shared disclaimer partial.
            "LICENSE_NUMBER": os.environ.get("ADVISORY_LICENSE_NUMBER", ""),
        }
        return ctx

    # ---------- stage resolution ---------------------------------------

    def _resolve_stage(
        self, user_id: int, in_window_trades: int, when: datetime
    ) -> str:
        """Pick new / observed / trajectory from data availability."""
        if in_window_trades < MIN_TRADES_FOR_LIVING_MIRROR:
            return "new"
        # Trajectory requires ≥2 historical snapshots to narrate a move.
        try:
            history = get_history(user_id, days_back=_HISTORY_DAYS_BACK, now=when)
        except Exception:
            logger.debug("living_mirror: get_history failed", exc_info=True)
            history = []
        if len(history) >= 2:
            return "trajectory"
        return "observed"

    # ---------- gap analysis (fact, no judgement) ----------------------

    def _gap_dimensions(
        self, declared_vec: list[float], observed_vec: list[float]
    ) -> list[dict[str, Any]]:
        """Top-3 dimensions where declared and observed shapes differ.

        Purely descriptive: we name the dimension and the *direction* of
        the gap ("선언보다 관찰값이 높음/낮음") — no score, no judgement,
        no "편향" labelling (rational-disposition caveat, JBF 2023).
        """
        rows: list[dict[str, Any]] = []
        for i, key in enumerate(FEATURE_KEYS):
            d = declared_vec[i]
            o = observed_vec[i]
            delta = o - d
            rows.append({
                "key": key,
                "label": FEATURE_LABELS.get(key, key),
                "delta": round(delta, 4),
                "direction": (
                    "관찰값이 더 큼" if delta > 0.0
                    else "관찰값이 더 작음" if delta < 0.0
                    else "선언과 일치"
                ),
            })
        rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
        return rows[:3]

    # ---------- trajectory view ----------------------------------------

    def _trajectory_view(self, drift: dict[str, Any]) -> dict[str, Any]:
        """Map ``compute_drift`` output → surface-safe trajectory view.

        First/last personas are translated through ``surface_label`` so
        the 8-code engine personas never reach the page. The descriptor
        ("유지 관찰" 등) is already observational.
        """
        first_code = drift.get("first_persona")
        last_code = drift.get("last_persona")
        first_label = surface_label(first_code) if first_code else None
        last_label = surface_label(last_code) if last_code else None

        # A surface-level move only counts when the *disclosed bucket*
        # actually changed — two 8-codes that collapse to the same bucket
        # (e.g. growth → value, both 성장형) must read as "유지 관찰".
        moved = bool(first_label and last_label and first_label != last_label)
        if moved:
            narrative = f"{first_label} → {last_label} 영역 이동 관찰"
        else:
            narrative = drift.get("descriptor") or "유지 관찰"

        return {
            "available": bool(drift.get("available")),
            "n_snapshots": int(drift.get("n_snapshots") or 0),
            "first_label": first_label,
            "last_label": last_label,
            "moved": moved,
            "narrative": narrative,
            "descriptor": drift.get("descriptor") or "유지 관찰",
        }

    # ---------- sparkline SVG path (shape only, no axis numbers) --------

    def _sparkline_path(self, sparkline: list[dict[str, Any]]) -> Optional[str]:
        """Build an SVG polyline ``points`` string from weekly scores.

        The score values drive only the *shape* of the line — no numeric
        score is ever printed on the page. Returns ``None`` for <2 points
        (a single dot is not a trajectory).
        """
        pts = [p for p in sparkline if isinstance(p.get("score"), (int, float))]
        if len(pts) < 2:
            return None
        width = 320.0
        height = 56.0
        pad = 4.0
        n = len(pts)
        # Normalise scores to the box height; the absolute value is never
        # shown, only the relative rise/fall of the line.
        vals = [float(p["score"]) for p in pts]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        coords: list[str] = []
        for i, v in enumerate(vals):
            x = pad + (width - 2 * pad) * (i / (n - 1))
            # invert y so higher score sits higher on the page
            y = pad + (height - 2 * pad) * (1.0 - (v - lo) / span)
            coords.append(f"{round(x, 2)},{round(y, 2)}")
        return " ".join(coords)

    # ---------- render -------------------------------------------------

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            html = self._fallback_html(data)
        else:
            try:
                tpl = env.get_template("living_mirror.html")
                html = tpl.render(**data)
            except Exception as exc:
                logger.warning("living_mirror render failed: %s", exc)
                html = self._fallback_html(data)
        scrubbed = safe_scrub(html, context="living_mirror") or html
        prohibited = detect_prohibited(scrubbed)
        if prohibited:
            logger.warning("legal_filter fail: living_mirror (%s)", prohibited)
        return scrubbed

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        try:
            return HTML(string=self.render_pdf_html(data)).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint living_mirror failed: %s", exc)
            return None

    def _jinja_env(self):
        Environment, FileSystemLoader, select_autoescape = _try_import_jinja()
        if Environment is None:
            return None
        try:
            return Environment(
                loader=FileSystemLoader(str(_TEMPLATE_DIR)),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True, lstrip_blocks=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Jinja env build failed: %s", exc)
            return None

    def _fallback_html(self, data: dict[str, Any]) -> str:
        from html import escape
        return (
            "<!doctype html><html><body>"
            f"<h1>Living Mirror — {escape(str(data.get('declared_label', '')))}</h1>"
            f"<p>{escape(str(data.get('disclaimer_note', '')))}</p>"
            "</body></html>"
        )

    # ---------- persist ------------------------------------------------

    def persist(
        self,
        user_id: int,
        data: dict[str, Any],
        pdf_bytes: Optional[bytes],
    ) -> Artifact:
        """UPSERT one Artifact row per (user, type, title)."""
        title = f"Living Mirror — {data.get('period_label', '')}"

        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", title)
                path = base / f"{safe}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning(
                    "living_mirror PDF write failed for user %s: %s",
                    user_id, exc,
                )

        # data_json must be JSON-serialisable — the context carries a
        # datetime; coerce to a stored-safe shape.
        stored = dict(data)
        gen = stored.get("generated_at")
        if isinstance(gen, datetime):
            stored["generated_at"] = gen.isoformat()

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type=ARTIFACT_TYPE, title=title)
            .first()
        )
        if artefact:
            artefact.data_json = stored
            if pdf_path:
                artefact.pdf_path = pdf_path
        else:
            artefact = Artifact(
                user_id=user_id,
                type=ARTIFACT_TYPE,
                title=title,
                data_json=stored,
                pdf_path=pdf_path,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact


__all__ = [
    "LivingMirrorService",
    "ARTIFACT_TYPE",
    "MIN_TRADES_FOR_LIVING_MIRROR",
    "LIVING_MIRROR_NOTE",
]
