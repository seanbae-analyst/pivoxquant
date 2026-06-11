"""Artifacts API — Weekly Investor Memo, Monthly Brag Card, + future artefact classes.

2026-05-17 wave 14 P1 (PR #448): every ``jsonify({"error": f"...: {exc}"})``
in this file (38 sites + 4 ``str(exc)`` sites) was scrubbed to drop the
raw exception interpolation. SQLAlchemy IntegrityError /
OperationalError / DataError render with full SQL + parameter values
+ table+column names + pgcode in ``str(exc)``; that text was leaking
to any authenticated caller of preview/manual-run endpoints.
``logger.exception(...)`` still captures the full traceback for ops;
only the response body changed.

2026-05-17 wave B api_error sweep: 142 error sites in this file were
converted from raw ``jsonify({"error": ...})`` to the centralized
``api_error(en=..., kr=..., code=..., status=...)`` helper. Adds
Korean copy + a machine-readable stable ``code`` to every endpoint so
the frontend toast UX and pattern-matching contract stay uniform.
The English ``error`` text is preserved verbatim so existing test
substring assertions in ``tests/test_artifacts_generate_unified.py``
keep passing.

The 2 admin-only ``/_diag/weekly-memo-pipeline`` diagnostic responses
keep the ``{ok, stage, error: dict, stages: ...}`` shape on purpose
— see the docstring on ``diag_weekly_memo_pipeline`` for why.


Endpoints (all under /api/artifacts, all require auth unless noted):

    POST /api/artifacts/weekly-memo/preview              — JSON preview for self
    GET  /api/artifacts/weekly-memo/download/<memo_id>   — PDF stream (owner only)
    GET  /api/artifacts/weekly-memo/history              — last 12 memos
    POST /api/artifacts/weekly-memo/trigger              — admin-only manual run

    POST /api/artifacts/monthly-brag/preview             — PNG + base64 for self
    GET  /api/artifacts/monthly-brag/download/<brag_id>  — PNG stream (owner only)
    GET  /api/artifacts/monthly-brag/share-link/<brag_id>— share URL + OG meta
    POST /api/artifacts/monthly-brag/trigger             — admin-only manual run

Scheduler jobs live in app.py and call the services directly. These
routes exist for (a) in-app preview/download, (b) QA, (c) emergency
manual runs, and (d) the viral share flow.

Security
--------
- All endpoints gated by `@api_auth`. `/trigger` is additionally gated
  to `DEV_LOGIN_SECRET` presence (dev/staging only; prod leaves the
  env var unset so the route 404s effectively).
- `/download/<id>` checks `artefact.user_id == current_user.id` so
  users cannot enumerate other users' artefacts.
"""
from __future__ import annotations

import base64
import hmac
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file
from flask_login import current_user
from markupsafe import escape  # 2026-05-09 (SEC-D): defense-in-depth OG meta escape

from extensions import db
from models import Artifact
from services.artifacts.monthly_brag_service import MonthlyBragService
from services.artifacts.weekly_memo_service import WeeklyMemoService
from services.error_responses import api_error
from services.name_resolver import resolve_stock_name

from .decorators import api_auth, require_tier, _TIER_RANK
from security import artifact_rate_limit, general_rate_limit
import logging

logger = logging.getLogger(__name__)

artifacts_bp = Blueprint("artifacts", __name__, url_prefix="/api/artifacts")


_WEASYPRINT_OK: bool | None = None


def _weasyprint_importable() -> bool:
    """True when WeasyPrint imports in this process (cached per-process).

    Lets the generate route tell apart `render_pdf -> None because the native
    dep is missing` (expected on some envs) from `render failed despite the
    dep being present` (a genuine error to surface, not swallow).
    """
    global _WEASYPRINT_OK
    if _WEASYPRINT_OK is None:
        try:
            from weasyprint import HTML  # type: ignore  # noqa: F401
            _WEASYPRINT_OK = True
        except Exception:
            _WEASYPRINT_OK = False
    return _WEASYPRINT_OK


def _check_cron_admin_secret() -> tuple[Response, int] | None:
    """Cron trigger 인증 — production-safe.

    `ARTIFACT_TRIGGER_SECRET`는 production cron 트리거용 별도 secret.
    `DEV_LOGIN_SECRET`는 dev-login bypass + tier-upgrade 같은 dev/staging 기능용
    (production 미설정 컨벤션). 두 secret 분리로 production cron 작동 + dev
    bypass 미노출 동시 달성.

    Returns:
        None: 인증 통과
        (Response, int): 401/404 응답
    """
    cron_secret = os.environ.get("ARTIFACT_TRIGGER_SECRET")
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")

    # cron secret 우선. 미설정 시 dev_secret로 fallback (dev/staging).
    expected = cron_secret or dev_secret
    if not expected:
        return api_error(en="Not found", kr="찾을 수 없습니다.", code="NOT_FOUND", status=404)

    provided = request.headers.get("X-Admin-Secret", "")
    # 2026-05-08 (Vuln SEC-B): use hmac.compare_digest for constant-time
    # comparison to prevent timing-attack secret recovery. Vanilla `!=`
    # short-circuits on first byte mismatch which leaks secret prefix
    # length over many requests.
    if not hmac.compare_digest(provided, expected):
        return api_error(en="Admin only", kr="관리자 전용입니다.", code="ADMIN_ONLY", status=403)

    return None


# ═══════ UNIFIED ARTIFACTS API ═══════
# Single-URL shape consumed by the frontend (`/api/artifacts/list`,
# `/api/artifacts/<id>/download`, etc). Each call dispatches to the matching
# type-specific handler so that new artefact classes (earnings_prebrief,
# quarterly_review, …) are automatically supported without frontend changes.
#
# The existing per-type routes (`/weekly-memo/*`, `/brag-card/*`,
# `/earnings-prebrief/*`) remain for QA / legacy flows — treat them as
# deprecated aliases. New frontend code should target the unified endpoints.

# Typed → (mimetype, extension) mapping used by the unified download route.
_ARTIFACT_DOWNLOAD_META = {
    "weekly_memo":       ("application/pdf", "pdf"),
    "earnings_prebrief": ("application/pdf", "pdf"),
    "earnings_pre":      ("application/pdf", "pdf"),
    "fomc_playbook":     ("application/pdf", "pdf"),
    "monthly_brag":      ("image/png",       "png"),
    "brag_card":         ("image/png",       "png"),
    "quarterly_review":  ("application/pdf", "pdf"),
    "risk_report":       ("application/pdf", "pdf"),
    "custom":            ("application/pdf", "pdf"),
    # 2026-04-19 — new artefact classes
    "self_audit":        ("application/pdf", "pdf"),
    "kpi_dashboard":     ("text/html",       "html"),
    "dd_checklist":      ("text/html",       "html"),
    "burn_rate":         ("application/pdf", "pdf"),
    "credit_rating":     ("text/html",       "html"),
    # 2026-04-19 — Premium finance reports
    "dividend_income":   ("application/pdf", "pdf"),
    "monthly_finance":   ("application/pdf", "pdf"),
    # 2026-04-19 — Premium risk + segment reports
    "risk_board":        ("application/pdf", "pdf"),
    "portfolio_segment": ("application/pdf", "pdf"),
    # 2026-04-19 — Capital Allocation (on-demand) + Insider Mirror (weekly)
    "capital_allocation": ("application/pdf", "pdf"),
    "insider_mirror":     ("application/pdf", "pdf"),
    # 2026-04-19 — Premium retrospective artefacts (download-only, no share)
    "year_end_letter":        ("application/pdf", "pdf"),
    "quarterly_self_report":  ("application/pdf", "pdf"),
}


def _since_to_cutoff(since: str | None) -> datetime | None:
    """Translate a relative `since` token ('30d', '90d', 'all') into a
    UTC datetime cutoff. Returns None for 'all' / unrecognised values so
    callers can skip the filter."""
    if not since or since == "all":
        return None
    try:
        if since.endswith("d"):
            days = int(since[:-1])
            return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    except ValueError:
        logger.debug("silent-fallback: _since_to_cutoff", exc_info=True)
        return None
    # Fall-through: try to parse as ISO date ("2026-01-01")
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        logger.debug("silent-fallback: Fall-through: try to parse as ISO date ('2026-01-01') | _since_to_cutoff", exc_info=True)
        return None


# ── React preview-shape adapters ─────────────────────────────────────────────
#
# The React /reports/preview/<slug> templates (frontend/src/components/reports/
# templates/*.tsx) consume a camelCase `*Data` interface, while the persisted
# `Artifact.data_json` is the raw snake_case payload from each service's
# `generate_for_user()`. These adapters convert raw → React shape for the LIST
# endpoint's `data_preview` field so the preview shell renders real data
# instead of throwing into render_error.
#
# Invariants:
#   - Read-only over `data_json`; never mutate the persisted blob (Jinja PDF,
#     download routes, and the §101 compliance scanner all read the raw shape).
#   - Honest-empty only: emit "—" / "" for fields the backend does not compute.
#     NEVER fabricate sample numbers (표시광고법 — fake-data ban).
#   - Only register a type here when EVERY field the template dereferences
#     without a guard can be supplied from real `data_json` (or is a `.map()`ed
#     array that is safe to leave empty, or is `?`-optional so an omitted key
#     elides the surface). risk_board and monthly_finance were reduced
#     (option-b, 2026-05-31): their React interfaces dropped the
#     backend-uncomputed fields (risk_board `beta`; monthly_finance
#     P&L/balance-sheet/cash-flow) so the remaining surfaces map 1:1 to real
#     data_json. They are now wired below.

def _kpi_dashboard_preview_shape(data: dict) -> dict:
    """Raw kpi_dashboard `data_json` → React `KpiDashboardData` shape.

    Mirrors frontend/src/components/reports/templates/kpi-dashboard.tsx. Every
    field the template dereferences directly (doc/navEom/ytdReturn/sharpe/
    status/issued + coverMonth?) maps to real backend metrics; the three
    arrays (scorecard/decisions/decisionCards) are accessed via `.map()` and
    are intentionally empty (separate sprint — kept empty, never faked).
    """
    as_of = data.get("as_of")
    as_of_label = str(as_of) if as_of else "—"
    month_label = as_of_label[:7] if as_of_label and as_of_label != "—" else "—"

    def _money(v) -> str:
        try:
            n = float(v)
        except (TypeError, ValueError):
            return "—"
        ccy = data.get("portfolio_ccy") or "USD"
        prefix = "₩" if ccy == "KRW" else "$"
        an = abs(n)
        sign = "−" if n < 0 else ""
        if an >= 1_000_000:
            return f"{sign}{prefix}{an / 1_000_000:.2f}M"
        if an >= 1_000:
            return f"{sign}{prefix}{an / 1_000:.0f}k"
        return f"{sign}{prefix}{an:,.0f}"

    def _pct(v) -> str:
        try:
            return f"{float(v):+.1f}%"
        except (TypeError, ValueError):
            return "—"

    sharpe = data.get("sharpe_annual")
    sharpe_str = f"{float(sharpe):.2f}" if sharpe is not None else "—"

    return {
        "doc":          f"{month_label} · KPI · 01/04",
        "coverMonth":   month_label if month_label != "—" else None,
        "navEom":       _money(data.get("portfolio_value")),
        "navEomDelta":  "",
        "ytdReturn":    _pct(data.get("ytd_return_pct")),
        "ytdDelta":     "",
        "sharpe":       sharpe_str,
        "sharpeDelta":  "",
        "status":       "관찰",
        "statusDelta":  "",
        "issued":       f"Issued · {as_of_label}",
        # Intentionally empty — deferred sprint. Templates `.map()` these so
        # an empty list renders cleanly (no fabricated rows).
        "scorecard":     [],
        "decisions":     [],
        "decisionCards": [],
    }


def _risk_board_preview_shape(data: dict) -> dict:
    """Raw risk_board `data_json` → React `RiskBoardData` shape.

    Mirrors frontend/src/components/reports/templates/risk-board.tsx (option-b
    reduction, 2026-05-31). The React interface was narrowed to the four KPIs
    services/artifacts/risk_board_service.py actually computes —
    var95_pct / sharpe_annual / max_drawdown_pct / vix_current — plus a
    pairwise-correlation proxy derived from sector concentration (the same
    heuristic _to_v3_shape uses). `beta` was DROPPED from the interface because
    the backend never computes a portfolio beta; emitting a hardcoded one would
    be a 표시광고법 fabrication. Honest-empty: every missing metric degrades to
    "—" / OK tone, and pairwiseCorr is omitted entirely when there is no sector
    data (the template elides the card).
    """
    period_label = data.get("period_label") or "—"
    trigger_token = "S" if data.get("trigger") == "vix_spike" else "M"
    week_tag = f"RB-{trigger_token} · {period_label}"
    as_of_stamp = f"As of {period_label}"

    cur = "₩" if data.get("portfolio_ccy") == "KRW" else "$"

    def _heat_var(v):
        if v is None:
            return "green"
        av = abs(float(v))
        if av < 2.0:
            return "green"
        if av < 3.5:
            return "amber"
        return "red"

    def _heat_sharpe(s):
        if s is None:
            return "green"
        if s >= 1.0:
            return "green"
        if s >= 0.5:
            return "amber"
        return "red"

    def _heat_mdd(m):
        if m is None:
            return "green"
        am = abs(float(m))
        if am < 10.0:
            return "green"
        if am < 20.0:
            return "amber"
        return "red"

    def _heat_vix(v):
        if v is None:
            return "green"
        if v < 20.0:
            return "green"
        if v < 25.0:
            return "amber"
        return "red"

    var95 = data.get("var95_pct")
    sharpe = data.get("sharpe_annual")
    mdd = data.get("max_drawdown_pct")
    vix = data.get("vix_current")
    port_value = data.get("portfolio_value")

    # NAV-loss label for the VaR card (₩/$ at 95% × NAV). Only when both exist.
    if var95 is not None and port_value:
        est_loss = abs(float(var95)) / 100.0 * float(port_value)
        var_nav = f"≈{cur}{est_loss:,.0f} NAV"
    else:
        var_nav = "Historical · 3M"

    shape: dict = {
        "weekTag":   week_tag,
        "asOfStamp": as_of_stamp,
        "var95": {
            "value": f"{-abs(float(var95)):.1f}%" if var95 is not None else "—",
            "nav":   var_nav,
            "tone":  _heat_var(var95),
        },
        "maxDD": {
            "value": f"{-abs(float(mdd)):.1f}%" if mdd is not None else "—",
            "limit": "Peak-to-trough",
            "tone":  _heat_mdd(mdd),
        },
        "sharpe": {
            "value":   f"{float(sharpe):.2f}" if sharpe is not None else "—",
            "vsPrior": "Risk-adj. · annual",
            "tone":    _heat_sharpe(sharpe),
        },
        "vix": {
            "value": f"{float(vix):.1f}" if vix is not None else "—",
            "band":  "Volatility regime",
            "tone":  _heat_vix(vix),
        },
    }

    # Pairwise-correlation proxy — only when sector data exists (mirrors the
    # _to_v3_shape heuristic). Omitted otherwise so the template elides the card
    # rather than rendering a fabricated correlation.
    sectors = data.get("sector_breakdown") or []
    if sectors:
        try:
            top_w = float(sectors[0].get("weight_pct") or 0) / 100.0
        except (TypeError, ValueError):
            top_w = 0.0
        corr_value = max(0.0, min(0.95, 0.10 + top_w * 1.10))
        if corr_value >= 0.65:
            verdict = "상위 섹터 비중 집중 — 평균 페어와이즈 상관 관찰 지표."
        elif corr_value >= 0.45:
            verdict = "섹터 비중 상승 — 분산 효과 모니터링 항목."
        else:
            verdict = "섹터 분산 양호 — 평균 페어와이즈 상관 관찰 지표."
        shape["pairwiseCorr"] = {
            "value":   f"{corr_value:.2f}",
            "gauge":   round(corr_value * 100.0, 1),
            "verdict": verdict,
        }

    return shape


def _monthly_finance_preview_shape(data: dict) -> dict:
    """Raw monthly_finance `data_json` → React `MonthlyFinanceData` shape.

    Mirrors frontend/src/components/reports/templates/monthly-finance.tsx
    (option-b reduction, 2026-05-31). The React interface was narrowed to the
    personal cash/cost/tax statement services/artifacts/monthly_finance_service.py
    actually computes (cash / positions_mv / liquidity_ratio / runway_months +
    cost_breakdown / tax_estimate ledgers). The corporate-style P&L, balance
    sheet, cash-flow, NAV-return, alpha and Sharpe surfaces were REMOVED because
    the backend never computes them — a partial shape would still throw on the
    unguarded P&L/BS/CF derefs and reproduce render_error. Honest-empty: missing
    KPIs are omitted (the template elides the card); the ledgers only emit rows
    that carry a real non-zero figure.
    """
    month_label = data.get("month_label") or "—"
    generated = data.get("generated_at") or month_label
    period_end = data.get("period_end") or month_label

    cash = data.get("cash") or {}
    positions_mv = data.get("positions_mv") or {}
    cost_breakdown = data.get("cost_breakdown") or {}
    tax_estimate = data.get("tax_estimate") or {}
    liquidity_ratio = data.get("liquidity_ratio")
    runway_months = data.get("runway_months")

    def _krw(v) -> str:
        try:
            n = float(v)
        except (TypeError, ValueError):
            return "—"
        an = abs(n)
        sign = "−" if n < 0 else ""
        if an >= 1_000_000:
            return f"{sign}₩{an / 1_000_000:.2f}M"
        if an >= 1_000:
            return f"{sign}₩{an / 1_000:.0f}k"
        return f"{sign}₩{an:,.0f}"

    # NAV (KRW) = cash total + positions market value (both KRW-normalized by
    # the service). None when neither is present.
    try:
        nav_total = float(cash.get("total_krw") or 0) + float(positions_mv.get("total_krw") or 0)
    except (TypeError, ValueError):
        nav_total = 0.0
    nav_str = _krw(nav_total) if nav_total else "—"

    try:
        cash_total = float(cash.get("total_krw") or 0)
    except (TypeError, ValueError):
        cash_total = 0.0

    shape: dict = {
        "doc":        f"{month_label} · MF",
        "coverMonth": month_label if month_label != "—" else None,
        "asOf":       str(period_end) if period_end else "",
        "issued":     f"Issued · {generated}",
        "navEom":     nav_str,
    }

    if nav_total:
        shape["navEomKpi"] = {"value": nav_str, "delta": "EOM 합산 (KRW)"}
    if cash_total:
        shape["cashKpi"] = {"value": _krw(cash_total), "delta": "현금 합산"}
    if liquidity_ratio is not None:
        try:
            shape["liquidityKpi"] = {
                "value": f"{float(liquidity_ratio):.2f}",
                "delta": "Cash / (Cash + MV)",
            }
        except (TypeError, ValueError):
            pass
    if runway_months is not None:
        try:
            shape["runwayKpi"] = {
                "value": f"{float(runway_months):.1f}",
                "delta": "현재 burn 기준",
            }
        except (TypeError, ValueError):
            pass

    # Cost ledger — only the real fields the service computes. Each row is
    # emitted only when its figure is non-zero (no fabricated/zero placeholders).
    cost_rows: list[dict] = []
    for label, key, detail in [
        ("Commission (US)", "us_commission_usd", "거래 수수료 추정 (USD)"),
        ("Commission (KR)", "kr_commission_krw", "거래 수수료 추정 (KRW)"),
        ("Transaction Tax (KR)", "kr_transaction_tax_krw", "증권거래세 추정"),
        ("FX Spread", "fx_spread_krw", "환전 스프레드 추정"),
        ("Total Cost", "total_krw", "월간 합계 (KRW)"),
    ]:
        try:
            amt = float(cost_breakdown.get(key) or 0)
        except (TypeError, ValueError):
            amt = 0.0
        if amt:
            is_usd = key.endswith("_usd")
            amt_str = (
                f"${amt:,.2f}" if is_usd else _krw(amt)
            )
            cost_rows.append({"label": label, "amount": amt_str, "detail": detail})
    shape["costRows"] = cost_rows

    # Tax ledger — same honest-non-zero rule.
    tax_rows: list[dict] = []
    for label, key, detail in [
        ("US Capital Gains (est)", "us_capital_gains_krw", "해외주식 양도세 추정"),
        ("Dividend Withholding (est)", "dividend_withholding_krw", "배당 원천징수 추정"),
        ("Total Tax (est)", "total_estimated_krw", "추정 합계 (KRW)"),
    ]:
        try:
            amt = float(tax_estimate.get(key) or 0)
        except (TypeError, ValueError):
            amt = 0.0
        if amt:
            tax_rows.append({"label": label, "amount": _krw(amt), "detail": detail})
    shape["taxRows"] = tax_rows

    return shape


# Registry of type → raw-to-React preview shaper. Add a type ONLY after
# verifying the template renders cleanly with the shape this produces.
_PREVIEW_SHAPERS: dict[str, "callable"] = {
    "kpi_dashboard": _kpi_dashboard_preview_shape,
    "risk_board": _risk_board_preview_shape,
    "monthly_finance": _monthly_finance_preview_shape,
}


def _preview_shape_for(artifact_type: str, data: dict):
    """Return the React-shaped preview dict for `artifact_type`, or None when
    no adapter is registered (caller falls back to the legacy whitelist).
    Per-type try/except isolates a shaper bug to that one row instead of
    failing the whole list response."""
    shaper = _PREVIEW_SHAPERS.get(artifact_type)
    if shaper is None:
        return None
    try:
        return shaper(data or {})
    except Exception:
        logger.warning("preview shape failed for type=%s", artifact_type,
                       exc_info=True)
        return None


@artifacts_bp.route("/list", methods=["GET"])
@api_auth
def artifacts_list():
    """List the current user's artifacts with optional type/since/limit filters.

    Query params:
        type   — "weekly_memo" | "brag_card" | "monthly_brag" |
                 "earnings_prebrief" | ... | "all" (default: all)
        since  — "30d" | "90d" | "all" | ISO date (default: all)
        limit  — integer, bounded [1, 200] (default: 50)

    Returns:
        { ok, artifacts: [...], total, unread_count }
    where `artifacts` is sorted newest-first and `unread_count` counts rows
    with `opened_at IS NULL` for sidebar/badge UIs.
    """
    req_type = (request.args.get("type") or "").strip().lower()
    since = request.args.get("since")
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        return api_error(en="limit must be an integer", kr="limit은 정수여야 합니다.", code="INVALID_LIMIT_TYPE", status=400)
    limit = max(1, min(limit, 200))

    q = Artifact.query.filter(Artifact.user_id == current_user.id)

    if req_type and req_type != "all":
        q = q.filter(Artifact.type == req_type)

    cutoff = _since_to_cutoff(since)
    if cutoff is not None:
        # Prefer sent_at when present (email delivery time); fall back to
        # created_at so rows that were generated but never emailed still
        # show up in the archive.
        q = q.filter(
            db.or_(
                Artifact.sent_at >= cutoff,
                db.and_(Artifact.sent_at.is_(None),
                        Artifact.created_at >= cutoff),
            )
        )

    total = q.count()
    rows = (
        q.order_by(Artifact.created_at.desc())
         .limit(limit)
         .all()
    )

    # Unread count ignores the type/since filter — it's meant for the global
    # sidebar badge, which should reflect *all* unopened reports.
    unread_count = (
        Artifact.query
        .filter(Artifact.user_id == current_user.id,
                Artifact.opened_at.is_(None))
        .count()
    )

    def _as_list_row(a: Artifact) -> dict:
        base = a.to_dict()
        # Surface fields the frontend `Artifact` type expects that aren't
        # on the raw model (best-effort; None when unavailable).
        data = base.get("data") or {}
        base["subtitle"] = data.get("subtitle") or data.get("summary") or None
        base["period_label"] = data.get("month_label") or data.get("week_label")
        # `data_preview` serves two distinct consumers:
        #   1. latest-artifact-card.tsx — reads only `mentioned_tickers`
        #      (graceful [] otherwise), so extra keys are harmless.
        #   2. report-preview-shell.tsx — casts `data_preview` to the
        #      template's `*Data` interface. For React templates whose
        #      interface is camelCase + nested (kpi-dashboard) the raw
        #      snake_case `data_json` does NOT match, so the template
        #      throws and falls back to render_error EmptyState even when
        #      real data exists. `_preview_shape_for` converts the persisted
        #      `data_json` into the React shape WITHOUT mutating `data_json`
        #      (Jinja/download/compliance consumers keep the raw snake_case
        #      blob untouched, and old rows convert at read-time).
        shaped = _preview_shape_for(a.type, data)
        if shaped is not None:
            base["data_preview"] = shaped
        else:
            base["data_preview"] = {
                k: v for k, v in data.items()
                if k in {"return_pct", "summary", "subtitle", "week_label",
                         "month_label", "ticker", "earnings_dt"}
            } or None
        return base

    return jsonify({
        "ok":            True,
        "artifacts":     [_as_list_row(r) for r in rows],
        "total":         total,
        "unread_count":  unread_count,
    })


@artifacts_bp.route("/<int:artifact_id>/preview", methods=["GET"])
@api_auth
def artifacts_preview(artifact_id: int):
    """Return the structured data payload for one artifact. Owner-only.

    Unlike the per-type `/preview` endpoints (which re-generate the artefact
    from scratch for the current user), this endpoint reads the persisted
    `data_json` from the row — so it's cheap and deterministic. Useful for
    the frontend preview modal.
    """
    artefact = db.session.get(Artifact, artifact_id)
    if not artefact or artefact.user_id != current_user.id:
        return api_error(en="Artifact not found", kr="아티팩트를 찾을 수 없습니다.", code="ARTIFACT_NOT_FOUND", status=404)

    return jsonify({
        "ok":       True,
        "id":       artefact.id,
        "type":     artefact.type,
        "title":    artefact.title,
        "data":     artefact.data_json or {},
        # 2026-05-13 (Bug C): use the disk-aware property so Railway
        # ephemeral filesystem can't produce false has_file=True after
        # a redeploy (which previously sent "Open full memo" to /download
        # → 410 → raw JSON in a black tab for brag_card #93).
        "has_file": artefact.has_file,
    })


@artifacts_bp.route("/<int:artifact_id>/download", methods=["GET"])
@api_auth
def artifacts_download(artifact_id: int):
    """Stream the rendered artefact file. Owner-only.

    Polymorphic over all artefact types — picks the right mimetype/
    extension from `_ARTIFACT_DOWNLOAD_META`. 404/410 semantics mirror the
    type-specific handlers so the frontend can render a single error UI.
    """
    artefact = db.session.get(Artifact, artifact_id)
    if not artefact or artefact.user_id != current_user.id:
        return api_error(en="Artifact not found", kr="아티팩트를 찾을 수 없습니다.", code="ARTIFACT_NOT_FOUND", status=404)

    meta = _ARTIFACT_DOWNLOAD_META.get(artefact.type)
    if not meta:
        return api_error(
            en=f"Download not supported for type={artefact.type}",
            kr="이 아티팩트 유형은 다운로드를 지원하지 않습니다.",
            code="TYPE_NOT_DOWNLOADABLE", status=415,
        )
    mimetype, ext = meta

    if not artefact.pdf_path:
        return api_error(
            en="File unavailable for this artifact",
            kr="이 아티팩트의 파일이 아직 준비되지 않았습니다.",
            code="FILE_NOT_RENDERED", status=410,
        )

    file_path = Path(artefact.pdf_path)
    if not file_path.exists():
        return api_error(
            en="File missing on disk",
            kr="파일이 서버에 존재하지 않습니다.",
            code="FILE_MISSING", status=410,
        )

    # Mark opened on first successful download — same convention as the
    # per-type endpoints above.
    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    # 2026-05-02: ?inline=1 lets the "Open full memo" CTA open the PDF
    # in the browser's native viewer instead of forcing a download. The
    # default (no flag) preserves the legacy attachment behaviour for
    # the explicit "Download PDF" link so existing callers don't change.
    inline = request.args.get("inline") in ("1", "true", "yes")
    return send_file(
        str(file_path),
        mimetype=mimetype,
        as_attachment=not inline,
        download_name=f"{artefact.type}_{artefact.id}.{ext}",
    )


@artifacts_bp.route("/<int:artifact_id>/read", methods=["POST"])
@api_auth
@general_rate_limit
def artifacts_mark_read(artifact_id: int):
    """Mark an artifact as read. Owner-only. Idempotent."""
    artefact = db.session.get(Artifact, artifact_id)
    if not artefact or artefact.user_id != current_user.id:
        return api_error(en="Artifact not found", kr="아티팩트를 찾을 수 없습니다.", code="ARTIFACT_NOT_FOUND", status=404)

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.warning(
                "markRead failed for artefact %s: %s", artifact_id, exc,
            )
            return api_error(en="Could not mark as read", kr="읽음 처리에 실패했습니다.", code="MARK_READ_FAILED", status=500)

    return jsonify({
        "ok":         True,
        "id":         artefact.id,
        "opened_at":  artefact.opened_at.isoformat() + "Z"
                      if artefact.opened_at else None,
    })


# ── Weekly Memo ──────────────────────────────────────────────────────────────
# DEPRECATED: prefer `/api/artifacts/list`, `/api/artifacts/<id>/download`,
# `/api/artifacts/<id>/preview`. These per-type routes remain for QA and
# legacy callers only.

@artifacts_bp.route("/weekly-memo/preview", methods=["POST", "GET"])
@api_auth
@require_tier("pro")
@artifact_rate_limit
def weekly_memo_preview():
    """Generate (don't email) a preview memo for the current user.

    Always returns JSON — includes both the structured data and the
    rendered email HTML, so the frontend can render a read-only
    preview without hitting the PDF path.
    """
    try:
        svc = WeeklyMemoService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("weekly memo preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({
        "ok":   True,
        "data": data,
        "html": html,
    })


@artifacts_bp.route("/weekly-memo/download/<int:memo_id>", methods=["GET"])
@api_auth
# Download is owner-scoped, not tier-gated: a user who paid to GENERATE this
# artifact keeps download access after a downgrade (CEO policy 2026-05-28).
# Generation stays Pro-gated upstream; the owner check below is the only gate.
def weekly_memo_download(memo_id: int):
    """Stream the PDF for one memo. Only the owning user may download.

    Returns 404 if memo doesn't exist or isn't owned by current user
    (same code — avoids existence leaks).
    Returns 410 if the memo row exists but no `pdf_path` was rendered
    (WeasyPrint unavailable at generation time).
    """
    artefact = db.session.get(Artifact, memo_id)
    if (not artefact
            or artefact.type != "weekly_memo"
            or artefact.user_id != current_user.id):
        return api_error(en="Memo not found", kr="메모를 찾을 수 없습니다.", code="MEMO_NOT_FOUND", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this memo",
            kr="이 메모의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    # Mark as opened on first successful download
    if not artefact.opened_at:
        from datetime import datetime, timezone
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"weekly_memo_week_{artefact.id}.pdf",
    )


@artifacts_bp.route("/weekly-memo/history", methods=["GET"])
@api_auth
@require_tier("pro")
def weekly_memo_history():
    """Last 12 weeks of memos for the current user (newest first)."""
    cutoff = date.today() - timedelta(weeks=13)
    rows = (
        Artifact.query
        .filter(Artifact.user_id == current_user.id,
                Artifact.type == "weekly_memo",
                Artifact.created_at >= cutoff)
        .order_by(Artifact.created_at.desc())
        .limit(12)
        .all()
    )
    return jsonify({
        "ok":     True,
        "count":  len(rows),
        "memos":  [r.to_dict() for r in rows],
    })


@artifacts_bp.route("/weekly-memo/trigger", methods=["POST"])
@artifact_rate_limit
def weekly_memo_trigger():
    """Manual trigger for the Sunday cron. Admin-only.

    Gated in layers:
      1. `DEV_LOGIN_SECRET` env must be set (i.e. dev/staging).
      2. Caller must pass `X-Admin-Secret` header equal to it.
    This keeps the route effectively 404 in prod (where we leave
    `DEV_LOGIN_SECRET` unset — same convention as routes/dev_auth.py).
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_date")
    target_date = None
    if target_str:
        try:
            target_date = date.fromisoformat(target_str)
        except ValueError:
            return api_error(en="invalid target_date (expected YYYY-MM-DD)", kr="target_date 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_TARGET_DATE", status=400)

    try:
        summary = WeeklyMemoService().run_weekly(target_date=target_date)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("weekly memo manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ── Monthly Brag Card ────────────────────────────────────────────────────────

@artifacts_bp.route("/monthly-brag/preview", methods=["POST", "GET"])
@api_auth
@artifact_rate_limit
def monthly_brag_preview():
    """Generate (don't email) a preview brag card for the current user.

    Returns:
        { ok, data, png_base64 }
    where png_base64 is `None` when Pillow is unavailable so the caller
    can degrade to a data-only preview.

    Body is optional; when provided it may contain:
        { "month": "2026-03-01", "anonymous": true }
    to override the target month and anonymous flag (useful for QA).
    """
    body = request.get_json(silent=True) or {}
    month_date = None
    month_str = body.get("month")
    if month_str:
        try:
            month_date = date.fromisoformat(str(month_str))
        except ValueError:
            return api_error(en="invalid month (expected YYYY-MM-DD)", kr="month 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_MONTH", status=400)

    anon_override = body.get("anonymous")
    if anon_override is not None and not isinstance(anon_override, bool):
        return api_error(en="anonymous must be a boolean", kr="anonymous는 boolean이어야 합니다.", code="ANONYMOUS_BOOL_REQUIRED", status=400)

    try:
        svc = MonthlyBragService()
        data = svc.generate_for_user(
            current_user.id, month=month_date,
            anonymous=anon_override,
        )
        png_bytes = svc.render_png(data)
    except Exception as exc:
        current_app.logger.error("monthly brag preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    png_b64 = base64.b64encode(png_bytes).decode("ascii") if png_bytes else None
    return jsonify({
        "ok":         True,
        "data":       data,
        "png_base64": png_b64,
    })


@artifacts_bp.route("/monthly-brag/download/<int:brag_id>", methods=["GET"])
@api_auth
def monthly_brag_download(brag_id: int):
    """Stream the PNG for one brag card. Only the owning user may download.

    - 404 when the row doesn't exist, isn't a monthly_brag, or belongs
      to another user (same code — avoids existence leaks).
    - 410 when the row exists but no PNG was written (Pillow unavailable
      at generation time).
    """
    artefact = db.session.get(Artifact, brag_id)
    if (not artefact
            or artefact.type != "monthly_brag"
            or artefact.user_id != current_user.id):
        return api_error(en="Brag card not found", kr="자랑 카드를 찾을 수 없습니다.", code="BRAG_NOT_FOUND", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PNG unavailable for this brag card",
            kr="이 자랑 카드의 PNG가 아직 준비되지 않았습니다.",
            code="PNG_NOT_RENDERED", status=410,
        )

    png_file = Path(artefact.pdf_path)
    if not png_file.exists():
        return api_error(
            en="PNG file missing on disk",
            kr="PNG 파일이 서버에 존재하지 않습니다.",
            code="PNG_FILE_MISSING", status=410,
        )

    # Mark as opened on first successful download — same convention as
    # the weekly memo route.
    if not artefact.opened_at:
        from datetime import datetime, timezone
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return send_file(
        str(png_file),
        mimetype="image/png",
        as_attachment=True,
        download_name=f"pivoxquant_brag_{artefact.id}.png",
    )


@artifacts_bp.route("/monthly-brag/og-image/<int:brag_id>", methods=["GET"])
@general_rate_limit
def monthly_brag_og_image(brag_id: int):
    """PUBLIC image-serve for OG meta + social link unfurling.

    Wave G-3 Bug #4 (2026-05-18): the ``share-link`` endpoint hands the
    frontend an ``og:image`` URL that crawlers (Kakao / Twitter /
    Instagram) hit with no session cookie. The legacy URL pointed at
    ``/monthly-brag/download/<id>`` which is ``@api_auth`` → 401 →
    broken unfurl. Routing crawlers here instead.

    monthly_brag rows do not carry a ``share_token`` (only ``brag_card``
    does), so this endpoint requires an HMAC-signed ``?sig=`` token bound
    to the requested ``brag_id`` (minted by the owner-authed share-link
    route). This closes integer-ID enumeration — the PNG embeds the
    user's real name + monthly return (PIPA §29), so a bare ``brag_id``
    must not be enough to fetch it. Crawlers receive the signed URL from
    the share landing page, so unfurls still work.

    * 403 — missing or invalid signature (enumeration attempt).
    * 404 — row doesn't exist or isn't monthly_brag.
    * 410 — row exists but no PNG rendered (Pillow unavailable).
    """
    from services.brag_og_token import verify_og_token
    if not verify_og_token(request.args.get("sig", ""), brag_id):
        return api_error(en="Invalid or missing share signature",
                         kr="잘못되었거나 누락된 공유 서명입니다.",
                         code="BRAG_SIG_INVALID", status=403)

    artefact = db.session.get(Artifact, brag_id)
    if not artefact or artefact.type != "monthly_brag":
        return api_error(en="Brag card not found",
                         kr="자랑 카드를 찾을 수 없습니다.",
                         code="BRAG_NOT_FOUND", status=404)

    if not artefact.has_file:
        return api_error(
            en="PNG unavailable for this brag card",
            kr="이 자랑 카드의 PNG가 아직 준비되지 않았습니다.",
            code="PNG_NOT_RENDERED", status=410,
        )

    resp = send_file(
        artefact.pdf_path,
        mimetype="image/png",
        max_age=86400,
    )
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@artifacts_bp.route("/monthly-brag/share-link/<int:brag_id>", methods=["GET"])
@api_auth
def monthly_brag_share_link(brag_id: int):
    """Return a short share URL + OG meta for one brag card.

    Used by the frontend share drawer (Kakao / Instagram / X) — the link
    carries the user's referral code so downstream signups attribute
    correctly. The OG meta block is rendered into a redirect landing
    page (`pivoxquant.com/r/<code>?brag=<id>`) by the frontend.
    """
    artefact = db.session.get(Artifact, brag_id)
    if (not artefact
            or artefact.type != "monthly_brag"
            or artefact.user_id != current_user.id):
        return api_error(en="Brag card not found", kr="자랑 카드를 찾을 수 없습니다.", code="BRAG_NOT_FOUND", status=404)

    from services.brag_og_token import make_og_token

    data = artefact.data_json or {}
    referral = data.get("referral_code") or ""
    if not referral:
        # Fallback — read/create from UserReferral so legacy rows still
        # produce a valid share link.
        try:
            from models import UserReferral
            referral = UserReferral.get_or_create(current_user.id).referral_code
        except Exception as exc:
            current_app.logger.warning(
                "share-link referral backfill failed for brag %s: %s",
                brag_id, exc,
            )

    share_domain = os.environ.get(
        "MONTHLY_BRAG_SHARE_DOMAIN", "pivoxquant.com"
    )
    share_url = (f"https://{share_domain}/r/{referral}?brag={artefact.id}"
                 if referral else f"https://{share_domain}")

    month_label = data.get("month_label") or ""
    return_pct = data.get("return_pct")
    if return_pct is None:
        ret_str = "—"
    else:
        sign = "+" if return_pct >= 0 else ""
        ret_str = f"{sign}{return_pct:.1f}%"

    og = {
        "og:title":        f"{month_label} {ret_str} — PivoxQuant",
        "og:description":  "월간 브래그 카드 — AI + Quant 리서치 툴",
        # Wave G-3 Bug #4 (2026-05-18): https:// prefix + route to the
        # PUBLIC og-image endpoint (above) — /download/<id> is @api_auth
        # and crawlers were 401'ing → broken card unfurl.
        # The ``?sig=`` HMAC token (minted here by the owner) is what the
        # public og-image route verifies to block ID enumeration.
        "og:image":        f"https://{share_domain}/api/artifacts/monthly-brag/og-image/{artefact.id}?sig={make_og_token(artefact.id)}",
        "og:url":          share_url,
        "twitter:card":    "summary_large_image",
    }

    return jsonify({
        "ok":        True,
        "brag_id":   artefact.id,
        "share_url": share_url,
        "referral":  referral,
        "og":        og,
    })


@artifacts_bp.route("/monthly-brag/trigger", methods=["POST"])
@artifact_rate_limit
def monthly_brag_trigger():
    """Manual trigger for the monthly cron. Admin-only.

    Same gating layers as `/weekly-memo/trigger`:
      1. `DEV_LOGIN_SECRET` env must be set (i.e. dev/staging).
      2. Caller must pass `X-Admin-Secret` header equal to it.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(str(target_str))
        except ValueError:
            return api_error(
                en="invalid target_month (expected YYYY-MM-DD)",
                kr="target_month 형식이 잘못되었습니다 (YYYY-MM-DD).",
                code="INVALID_TARGET_MONTH", status=400,
            )

    try:
        summary = MonthlyBragService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("monthly brag manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ BRAG CARD ═══════
# MVP #2 — 9:16 Instagram Story PNG, emailed 1st of each month 09:00 KST to
# every user (Free+). Routes here are independent of the legacy `/monthly-brag`
# endpoints above; the two coexist because the underlying services use
# different renderers (Pillow vs Playwright + HTML).
#
# Public share route (`/brag-card/share/<token>`) intentionally does NOT
# require auth — it serves the HTML directly with OG meta for Kakao /
# Instagram / Twitter link-unfurling.

from services.artifacts.brag_card_service import BragCardService  # noqa: E402


@artifacts_bp.route("/brag-card/preview", methods=["GET", "POST"])
@api_auth
@artifact_rate_limit
def brag_card_preview():
    """Generate (don't email) a preview brag card PNG for the current user.

    Accepts an optional body:
        { "month": "2026-03-01", "anonymous": true }
    to override the target month and privacy mode.

    Returns:
        { ok, data, png_base64, html }
    `png_base64` is None when Playwright is unavailable — frontend can
    still render the HTML preview via an <iframe srcdoc>.
    """
    body = request.get_json(silent=True) or {}
    month_date = None
    month_str = body.get("month")
    if month_str:
        try:
            month_date = date.fromisoformat(str(month_str))
        except ValueError:
            return api_error(en="invalid month (expected YYYY-MM-DD)", kr="month 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_MONTH", status=400)

    anon_override = body.get("anonymous")
    if anon_override is not None and not isinstance(anon_override, bool):
        return api_error(en="anonymous must be a boolean", kr="anonymous는 boolean이어야 합니다.", code="ANONYMOUS_BOOL_REQUIRED", status=400)

    try:
        svc = BragCardService()
        data = svc.generate_for_user(
            current_user.id, month=month_date, anonymous=anon_override,
        )
        html = svc.render_html(data)
        png_bytes = svc.render_png(html)
    except Exception as exc:
        current_app.logger.error("brag card preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    png_b64 = base64.b64encode(png_bytes).decode("ascii") if png_bytes else None
    return jsonify({
        "ok":         True,
        "data":       data,
        "png_base64": png_b64,
        "html":       html,
    })


@artifacts_bp.route("/brag-card/download/<int:card_id>", methods=["GET"])
@api_auth
def brag_card_download(card_id: int):
    """Stream the PNG for one brag card. Owner-only.

    - 404 when the row doesn't exist, isn't a `brag_card`, or belongs to
      another user (same code avoids existence leaks).
    - 410 when the row exists but no PNG was rendered (Playwright
      unavailable at generation time).
    """
    artefact = db.session.get(Artifact, card_id)
    if (not artefact
            or artefact.type != "brag_card"
            or artefact.user_id != current_user.id):
        return api_error(en="Brag card not found", kr="자랑 카드를 찾을 수 없습니다.", code="BRAG_NOT_FOUND", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PNG unavailable for this brag card",
            kr="이 자랑 카드의 PNG가 아직 준비되지 않았습니다.",
            code="PNG_NOT_RENDERED", status=410,
        )

    png_file = Path(artefact.pdf_path)
    if not png_file.exists():
        return api_error(
            en="PNG file missing on disk",
            kr="PNG 파일이 서버에 존재하지 않습니다.",
            code="PNG_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        from datetime import datetime, timezone
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return send_file(
        str(png_file),
        mimetype="image/png",
        as_attachment=True,
        download_name=f"pivoxquant_brag_{artefact.id}.png",
    )


@artifacts_bp.route("/brag-card/share/<string:share_token>/image", methods=["GET"])
@general_rate_limit
def brag_card_share_image(share_token: str):
    """PUBLIC image-serve for OG meta + social link unfurling.

    Wave G-3 Bug #1 (2026-05-18) P0 SHIP-BLOCKER: previously the
    ``og:image`` URL on the share landing pointed to
    ``/api/artifacts/brag-card/download/<id>`` which is gated by
    ``@api_auth``. Kakao / Twitter / Instagram crawlers never carry a
    session cookie, so the crawler got 401 and the unfurled card
    rendered with no image — viral loop completely broken.

    Security model:
      * The ``share_token`` itself is the secret. ``_generate_share_token``
        returns ``secrets.token_urlsafe(24)[:32]`` ≈ 192 bits of entropy,
        so enumeration is infeasible (matches the existing
        ``brag_card_share`` HTML route, which is already public).
      * Returns 404 when the row doesn't exist or isn't a brag card
        (same code — avoids existence leaks).
      * Returns 410 when the row exists but no PNG file was rendered
        (Playwright unavailable at generation time).
      * ``Cache-Control: public, max-age=86400`` since the PNG is
        immutable per share_token and CDNs / crawlers benefit from
        aggressive caching.
    """
    if not share_token or len(share_token) < 16:
        return api_error(en="Invalid share token",
                         kr="유효하지 않은 공유 토큰입니다.",
                         code="INVALID_SHARE_TOKEN", status=404)

    artefact = (
        Artifact.query
        .filter_by(type="brag_card", share_token=share_token)
        .first()
    )
    # Public-visibility gate (matches GET /api/card/<token> in routes/growth).
    # Every brag card defaults to private (is_public=False, migration 045);
    # the owner must explicitly opt in via POST /api/card/<token>/visibility.
    # Same 404 for "not found" and "not public" so a leaked / internally-minted
    # share_token can never expose a card the user toggled private (PIPA §29).
    if not artefact or not bool(getattr(artefact, "is_public", False)):
        return api_error(en="Card not found",
                         kr="카드를 찾을 수 없습니다.",
                         code="CARD_NOT_FOUND", status=404)

    if not artefact.has_file:
        return api_error(
            en="PNG unavailable for this brag card",
            kr="이 자랑 카드의 PNG가 아직 준비되지 않았습니다.",
            code="PNG_NOT_RENDERED", status=410,
        )

    resp = send_file(
        artefact.pdf_path,
        mimetype="image/png",
        max_age=86400,
    )
    # send_file's default is private, max-age — override for crawlers.
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@artifacts_bp.route("/brag-card/share/<string:share_token>", methods=["GET"])
@general_rate_limit
def brag_card_share(share_token: str):
    """PUBLIC — return the rendered HTML card for a given share token.

    No auth: this route is the landing page for anyone who clicks a
    shared Instagram/Kakao/Twitter link. The HTML includes OG meta so
    social crawlers unfurl the card image cleanly.

    Security notes:
      * The token is a 32-char urlsafe secret, so enumeration is
        practically infeasible.
      * Responses are Cache-Control: public (short TTL) since the
        content is inherently public by virtue of the share action.
    """
    if not share_token or len(share_token) < 16:
        return api_error(en="Invalid share token", kr="유효하지 않은 공유 토큰입니다.", code="INVALID_SHARE_TOKEN", status=404)

    artefact = (
        Artifact.query
        .filter_by(type="brag_card", share_token=share_token)
        .first()
    )
    # Public-visibility gate (matches GET /api/card/<token> in routes/growth).
    # Default-private (migration 045); owner must opt in via the visibility
    # toggle. Same 404 for "not found" and "not public" — never leak the
    # existence of a card the user kept private (PIPA §29).
    if not artefact or not bool(getattr(artefact, "is_public", False)):
        return api_error(en="Card not found", kr="카드를 찾을 수 없습니다.", code="CARD_NOT_FOUND", status=404)

    data = dict(artefact.data_json or {})
    data.setdefault("share_token", share_token)

    # Render card HTML. We intentionally render the *card* (not the email)
    # so mobile users see the polished 9:16 image layout.
    svc = BragCardService()
    html = svc.render_html(data)

    # Inject OG meta so crawlers unfurl correctly. Hack: inject into <head>.
    share_url = svc.get_share_url(artefact.id)
    # Wave G-3 Bug #1 (2026-05-18): point at the PUBLIC image-serve route
    # (above) not /download/<id> which is @api_auth — crawlers carry no
    # session and were getting 401 → broken card unfurl → viral loop dead.
    png_endpoint = (f"{request.host_url.rstrip('/')}"
                    f"/api/artifacts/brag-card/share/{share_token}/image")
    ret = data.get("return_pct")
    ret_str = "—" if ret is None else (f"+{ret:.1f}%" if ret >= 0
                                       else f"{ret:.1f}%")
    # 2026-05-09 (SEC-D): every interpolated value is run through
    # ``markupsafe.escape`` before being injected into the HTML. Today the
    # values are server-derived (``month_label`` from the artefact row,
    # ``ret_str`` from a ``%.1f`` format, the URLs from ``request.host_url``
    # / our share helper) so direct XSS is not currently possible. This is
    # defense-in-depth — if a future change ever wires a user-customizable
    # field (e.g. a referral nickname) into one of these slots the worm-scale
    # risk is already neutralised.
    og_block = (
        f'<meta property="og:title" content="{escape(data.get("month_label",""))} '
        f'{escape(ret_str)} — PivoxQuant">'
        f'<meta property="og:description" content="월간 브래그 카드 — '
        f'AI + Quant 리서치 툴">'
        f'<meta property="og:image" content="{escape(png_endpoint)}">'
        f'<meta property="og:url" content="{escape(share_url)}">'
        f'<meta name="twitter:card" content="summary_large_image">'
    )
    if "</head>" in html:
        html = html.replace("</head>", f"{og_block}</head>", 1)

    resp = Response(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@artifacts_bp.route("/brag-card/trigger", methods=["POST"])
@artifact_rate_limit
def brag_card_trigger():
    """Manual trigger for the monthly cron. Admin-only (DEV_LOGIN_SECRET)."""
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(str(target_str))
        except ValueError:
            return api_error(
                en="invalid target_month (expected YYYY-MM-DD)",
                kr="target_month 형식이 잘못되었습니다 (YYYY-MM-DD).",
                code="INVALID_TARGET_MONTH", status=400,
            )

    try:
        summary = BragCardService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("brag card manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


@artifacts_bp.route("/brag-card/privacy", methods=["POST"])
@api_auth
@artifact_rate_limit
def brag_card_privacy():
    """Toggle anonymous mode for brag cards.

    Body: { "privacy_mode": true|false }
    Sets `current_user.privacy_mode`. Future brag cards generated for
    this user will mask ticker names as "A 종목".
    """
    body = request.get_json(silent=True) or {}
    val = body.get("privacy_mode")
    if not isinstance(val, bool):
        return api_error(en="privacy_mode must be a boolean", kr="privacy_mode는 boolean이어야 합니다.", code="PRIVACY_BOOL_REQUIRED", status=400)

    try:
        setattr(current_user, "privacy_mode", val)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            "privacy toggle failed for user %s: %s", current_user.id, exc,
        )
        return api_error(en="Could not update privacy flag", kr="개인정보 설정을 변경하지 못했습니다.", code="PRIVACY_UPDATE_FAILED", status=500)

    return jsonify({"ok": True, "privacy_mode": val})


# ═══════ EARNINGS PRE-BRIEF ═══════
# MVP #3 — 30-min pre-announcement 2-page PDF + urgent Warm Gold email + web
# push, for every user with a position in a ticker whose earnings fire in
# ~30 minutes. The scheduler in app.py calls EarningsPrebriefService.run_scan
# every 15 minutes; these routes exist for (a) in-app "upcoming earnings"
# widgets, (b) on-demand preview by a user for their own position, (c)
# downloading the archived PDF, and (d) admin-only manual triggers.
#
# Distinct from the `/earnings_pre` legacy artefact type — MVP #3 persists
# under `type="earnings_prebrief"` and is polymorphic over the shared
# `artifacts` table so no migration is required on the Artifact model.

from services.artifacts.earnings_prebrief_service import (  # noqa: E402
    EarningsPrebriefService,
)


@artifacts_bp.route("/earnings-prebrief/upcoming", methods=["GET"])
@api_auth
@require_tier("pro")
def earnings_prebrief_upcoming():
    """List the current user's positions whose earnings fall within the
    requested window (default: this week, i.e. 168h).

    Query params:
        hours — integer, bounded [1, 336]. Defaults to 168 (7 days).

    Security: filters to the caller's own positions only.
    """
    try:
        hours = int(request.args.get("hours", "168"))
    except ValueError:
        return api_error(en="hours must be an integer", kr="hours는 정수여야 합니다.", code="INVALID_HOURS", status=400)
    hours = max(1, min(hours, 336))

    svc = EarningsPrebriefService()
    try:
        all_rows = svc.get_upcoming_earnings(hours=hours)
    except Exception as exc:
        current_app.logger.error("earnings upcoming fetch failed: %s", exc)
        return api_error(en="Upcoming fetch failed (internal error)", kr="예정된 일정을 불러오는 데 실패했습니다.", code="UPCOMING_FETCH_FAILED", status=500)

    # Scope to the caller — the underlying method returns across all Pro+
    # users for the scheduler path.
    mine = [
        {
            "ticker":       r["ticker"],
            "name":         resolve_stock_name(r["ticker"]) or r["ticker"],
            "earnings_dt":  r["earnings_dt"].isoformat() + "Z",
            "shares":       r["shares"],
            "avg_cost":     r["avg_cost"],
        }
        for r in all_rows
        if r["user_id"] == current_user.id
    ]
    return jsonify({
        "ok":       True,
        "count":    len(mine),
        "hours":    hours,
        "upcoming": mine,
    })


@artifacts_bp.route("/earnings-prebrief/preview/<string:ticker>", methods=["GET"])
@api_auth
@require_tier("pro")
def earnings_prebrief_preview(ticker: str):
    """Generate (don't email) a preview prebrief for the calling user
    and the given ticker. Intended for the in-app preview pane.

    Returns:
        { ok, data, html }          — on success
        { error, code }             — when no upcoming earnings / no position
    """
    ticker = (ticker or "").upper().strip()
    if not ticker or len(ticker) > 12:
        return api_error(en="invalid ticker", kr="유효하지 않은 종목입니다.", code="INVALID_TICKER", status=400)

    svc = EarningsPrebriefService()
    try:
        data = svc.generate_for_user(current_user.id, ticker)
    except ValueError as exc:
        # user_id lookup failed — shouldn't happen post-auth but defend
        current_app.logger.warning("prebrief preview value error: %s", exc)
        return api_error(en="Bad request", kr="잘못된 요청입니다.", code="BAD_REQUEST_404", status=404)
    except Exception as exc:
        current_app.logger.error("prebrief preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    if data is None:
        return api_error(
            en="No upcoming earnings found for this ticker",
            kr="이 종목의 예정된 실적 발표를 찾을 수 없습니다.",
            code="NO_UPCOMING_EARNINGS", status=404,
        )

    try:
        html = svc.render_email_html(data)
    except Exception as exc:
        current_app.logger.warning("prebrief email render failed: %s", exc)
        html = ""

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/earnings-prebrief/download/<int:brief_id>", methods=["GET"])
@api_auth
# Owner-scoped download (not tier-gated) — keeps access after a downgrade.
# Generation stays Pro-gated; the owner check below is the gate. (CEO 2026-05-28)
def earnings_prebrief_download(brief_id: int):
    """Stream the 2-page PDF for a persisted prebrief. Owner-only.

    404 when the row doesn't exist, isn't a prebrief, or belongs to a
    different user (same code — avoids existence leaks).
    410 when no PDF was rendered (WeasyPrint unavailable at generation
    time) so the caller can degrade to HTML.
    """
    artefact = db.session.get(Artifact, brief_id)
    if (not artefact
            or artefact.type != "earnings_prebrief"
            or artefact.user_id != current_user.id):
        return api_error(en="Pre-Brief not found", kr="실적 프리브리프를 찾을 수 없습니다.", code="PREBRIEF_NOT_FOUND", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this pre-brief",
            kr="이 프리브리프의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        from datetime import datetime, timezone
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    ticker = (artefact.data_json or {}).get("ticker", "prebrief")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"prebrief_{ticker}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/earnings-prebrief/trigger", methods=["POST"])
@artifact_rate_limit
def earnings_prebrief_trigger():
    """Manual trigger for the 15-min scan. Admin-only.

    Gated (identical pattern to the weekly / monthly triggers):
      1. `DEV_LOGIN_SECRET` env must be set (i.e. dev/staging).
      2. Caller must pass `X-Admin-Secret` header equal to it.

    Body (optional): { "send": false } to preview without emailing.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    send = body.get("send", True)
    if not isinstance(send, bool):
        return api_error(en="send must be a boolean", kr="send는 boolean이어야 합니다.", code="SEND_BOOL_REQUIRED", status=400)

    try:
        summary = EarningsPrebriefService().run_scan(send=send)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("prebrief manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ KPI DASHBOARD (Pro+) ═══════
# Daily 08:00 KST 5-metric email. Short HTML, no PDF. See
# services/artifacts/kpi_dashboard_service.py for KPI definitions.

from services.artifacts.kpi_dashboard_service import (  # noqa: E402
    KPIDashboardService,
)


@artifacts_bp.route("/kpi-dashboard/preview", methods=["GET"])
@api_auth
@require_tier("premium")
def kpi_dashboard_preview():
    """Generate (don't email) the current KPI snapshot for the caller.

    Returns:
        { ok, data, html }
    `data` is the raw 5-metric payload; `html` is the rendered email
    body so the frontend preview pane can render it as-is.
    """
    try:
        svc = KPIDashboardService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("kpi dashboard preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/kpi-dashboard/trigger", methods=["POST"])
@artifact_rate_limit
def kpi_dashboard_trigger():
    """Manual trigger for the daily KPI cron. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set.
      2. Caller must pass `X-Admin-Secret` header equal to it.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_date")
    target_date = None
    if target_str:
        try:
            target_date = date.fromisoformat(target_str)
        except ValueError:
            return api_error(en="invalid target_date (expected YYYY-MM-DD)", kr="target_date 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_TARGET_DATE", status=400)

    try:
        summary = KPIDashboardService().run_daily(target_date=target_date)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("kpi dashboard manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ SELF AUDIT (Premium) ═══════
# Quarterly 4-page PDF of decision-quality for premium users. Fired
# 1/7, 4/7, 7/7, 10/7 at 08:00 KST. No AI judgement in the scores —
# Haiku only contributes a 1-paragraph pattern summary. See
# services/artifacts/self_audit_service.py for methodology.

from services.artifacts.self_audit_service import (  # noqa: E402
    SelfAuditService,
)


@artifacts_bp.route("/self-audit/preview", methods=["GET"])
@api_auth
@require_tier("pro")
def self_audit_preview():
    """Generate (don't email) a preview Self Audit for the caller.

    Returns:
        { ok, data, html }
    """
    try:
        svc = SelfAuditService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("self audit preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/self-audit/download", methods=["GET"])
@api_auth
# Owner-scoped download (not tier-gated) — a downgraded Premium user keeps
# access to audits they generated while paying. Generation stays Premium-gated;
# the user_id filter below is the gate. (CEO policy 2026-05-28)
def self_audit_download_latest():
    """Stream the most recent Self Audit PDF for the caller.

    Unlike `/weekly-memo/download/<id>` this route auto-resolves to the
    latest audit row so the frontend can link `download` directly
    without tracking artefact IDs. Owner-only.

    404 — no audit exists yet. 410 — audit row exists but no PDF was
    rendered (WeasyPrint unavailable at generation time).
    """
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="self_audit")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Self Audit available yet", kr="아직 사용 가능한 자가 진단이 없습니다.", code="NO_AUDIT", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this audit",
            kr="이 자가 진단의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    quarter = (artefact.data_json or {}).get("quarter_label", "quarter")
    safe_q = quarter.replace(" ", "_")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"self_audit_{safe_q}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/self-audit/trigger", methods=["POST"])
@artifact_rate_limit
def self_audit_trigger():
    """Manual trigger for the quarterly cron. Admin-only.

    Gating — identical to weekly_memo/trigger.
    Body (optional): { "quarter_end": "2026-03-31" } to pin the audit
    window. Defaults to today (which maps to whichever quarter the
    `_quarter_bounds` helper resolves).
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    qe_str = body.get("quarter_end")
    quarter_end = None
    if qe_str:
        try:
            quarter_end = date.fromisoformat(qe_str)
        except ValueError:
            return api_error(en="invalid quarter_end (expected YYYY-MM-DD)", kr="quarter_end 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_QUARTER_END", status=400)

    try:
        summary = SelfAuditService().run_quarterly(quarter_end=quarter_end)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("self audit manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ DUE-DILIGENCE CHECKLIST (Pro+) ═══════
# T+3 post-entry prompt. Legal-safe: recorded AFTER the user has already
# bought. No AI judgement — only Y/N answers from the user. See
# services/artifacts/dd_checklist_service.py.

from services.artifacts.dd_checklist_service import (  # noqa: E402
    DDChecklistService,
)


@artifacts_bp.route("/dd-checklist/pending", methods=["GET"])
@api_auth
@require_tier("pro")
def dd_checklist_pending():
    """List the caller's positions that are T+3 or older and still
    unchecked (i.e. no PositionDDCheck row yet).

    Returns:
        { ok, pending: [...] }
    """
    try:
        svc = DDChecklistService()
        pending = svc.pending_for_user(current_user.id)
    except Exception as exc:
        current_app.logger.error("dd pending fetch failed: %s", exc)
        return api_error(en="Pending fetch failed (internal error)", kr="대기 중 항목 조회에 실패했습니다.", code="PENDING_FETCH_FAILED", status=500)

    return jsonify({"ok": True, "count": len(pending), "pending": pending})


@artifacts_bp.route("/dd-checklist/submit", methods=["POST"])
@api_auth
@require_tier("pro")
@artifact_rate_limit
def dd_checklist_submit():
    """Record the user's 5-item Y/N review for one position.

    Body:
        {
          "position_id":         int,
          "financials_checked":  bool,
          "moat_checked":        bool,
          "management_checked":  bool,
          "valuation_checked":   bool,
          "risks_checked":       bool,
          "note":                str (optional, max 500 chars)
        }

    Returns the persisted row (to_dict()). Idempotent via UNIQUE
    `position_id` — subsequent submits update the existing row.
    """
    body = request.get_json(silent=True) or {}

    # Input validation — type + presence
    try:
        position_id = int(body.get("position_id"))
    except (TypeError, ValueError):
        return api_error(en="position_id must be an integer", kr="position_id는 정수여야 합니다.", code="POSITION_ID_REQUIRED", status=400)

    bool_fields = ("financials_checked", "moat_checked", "management_checked",
                   "valuation_checked", "risks_checked")
    for f in bool_fields:
        if not isinstance(body.get(f), bool):
            return api_error(en=f"{f} must be a boolean", kr=f"{f}는 boolean이어야 합니다.", code="BOOL_FIELD_REQUIRED", status=400)

    note = body.get("note")
    if note is not None and not isinstance(note, str):
        return api_error(en="note must be a string", kr="note는 문자열이어야 합니다.", code="NOTE_STRING_REQUIRED", status=400)
    if isinstance(note, str) and len(note) > 500:
        return api_error(en="note exceeds 500 characters", kr="note는 500자를 초과할 수 없습니다.", code="NOTE_TOO_LONG", status=400)

    svc = DDChecklistService()
    try:
        row = svc.submit(
            user_id=current_user.id,
            position_id=position_id,
            financials=body["financials_checked"],
            moat=body["moat_checked"],
            management=body["management_checked"],
            valuation=body["valuation_checked"],
            risks=body["risks_checked"],
            note=note,
        )
    except LookupError as exc:
        return api_error(en="Bad request", kr="잘못된 요청입니다.", code="BAD_REQUEST_404", status=404)
    except PermissionError:
        return api_error(en="Position does not belong to you", kr="해당 포지션은 본인의 포지션이 아닙니다.", code="POSITION_NOT_OWNER", status=403)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("dd submit failed for user %s: %s",
                                 current_user.id, exc)
        return api_error(en="Submit failed (internal error)", kr="제출에 실패했습니다.", code="SUBMIT_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "dd_check": row.to_dict()})


@artifacts_bp.route("/dd-checklist/trigger", methods=["POST"])
@artifact_rate_limit
def dd_checklist_trigger():
    """Manual trigger for the T+3 cron. Admin-only. Same gating as
    weekly_memo/trigger."""
    err = _check_cron_admin_secret()
    if err:
        return err

    try:
        summary = DDChecklistService().run_daily()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("dd manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ BURN RATE REPORT (Pro+) ═══════
# Monthly 1st 09:00 KST — 1-page PDF aggregating last month's commission,
# transaction tax, expected CGT, FX spread, slippage estimate. See
# services/artifacts/burn_rate_service.py for the calculation contract.

from services.artifacts.burn_rate_service import (  # noqa: E402
    BurnRateService,
)


@artifacts_bp.route("/burn-rate/preview", methods=["GET"])
@api_auth
@require_tier("premium")
def burn_rate_preview():
    """Generate (don't email) a preview Burn Rate for the caller.

    Returns:
        { ok, data, html }
    Mirrors the /self-audit/preview contract so the frontend preview pane
    can treat these two polymorphically.
    """
    try:
        svc = BurnRateService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("burn_rate preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/burn-rate/download", methods=["GET"])
@api_auth
@require_tier("premium")
def burn_rate_download_latest():
    """Stream the most recent Burn Rate PDF for the caller. Owner-only.

    Same semantics as /self-audit/download — resolves to the latest row
    so the frontend can deep-link to `download` without tracking IDs.
    """
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="burn_rate")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Burn Rate report available yet", kr="아직 사용 가능한 번레이트 리포트가 없습니다.", code="NO_REPORT", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this report",
            kr="이 리포트의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    period = (artefact.data_json or {}).get("period_label", "period")
    safe_p = period.replace(" ", "_")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"burn_rate_{safe_p}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/burn-rate/trigger", methods=["POST"])
@artifact_rate_limit
def burn_rate_trigger():
    """Manual trigger for the monthly cron. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set.
      2. Caller must pass `X-Admin-Secret` header equal to it.
    Body (optional): { "target_month": "2026-04-01" } to pin the run
    date (used by `_prev_month_bounds` to back-out the prior month).
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(target_str)
        except ValueError:
            return api_error(en="invalid target_month (expected YYYY-MM-DD)", kr="target_month 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_TARGET_MONTH", status=400)

    try:
        summary = BurnRateService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("burn_rate manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ CREDIT RATING SELF-ASSESSMENT (Pro+) ═══════
# Monthly 15th 09:00 KST — 1-page HTML email with portfolio self-rating.

from services.artifacts.credit_rating_service import (  # noqa: E402
    CreditRatingService,
)


@artifacts_bp.route("/credit-rating/preview", methods=["GET"])
@api_auth
@require_tier("premium")
def credit_rating_preview():
    """Generate (don't email) a preview Credit Rating for the caller.

    Returns:
        { ok, data, html }
    """
    try:
        svc = CreditRatingService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("credit_rating preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/credit-rating/trigger", methods=["POST"])
@artifact_rate_limit
def credit_rating_trigger():
    """Manual trigger for the monthly cron. Admin-only. Same gating as
    weekly_memo/trigger."""
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    as_of_str = body.get("as_of")
    as_of = None
    if as_of_str:
        try:
            as_of = date.fromisoformat(as_of_str)
        except ValueError:
            return api_error(en="invalid as_of (expected YYYY-MM-DD)", kr="as_of 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_AS_OF", status=400)

    try:
        summary = CreditRatingService().run_monthly(as_of=as_of)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("credit_rating manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ DIVIDEND INCOME STATEMENT (Premium) ═══════
# Monthly 3-page PDF fired 1st of month 10:00 KST. See
# services/artifacts/dividend_income_service.py.

from services.artifacts.dividend_income_service import (  # noqa: E402
    DividendIncomeService,
)


@artifacts_bp.route("/dividend-income/preview", methods=["GET"])
@api_auth
@require_tier("pro")
def dividend_income_preview():
    """Generate (don't email) a preview dividend statement for the caller.

    Returns: { ok, data, html }
    """
    try:
        svc = DividendIncomeService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("dividend_income preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/dividend-income/download", methods=["GET"])
@api_auth
@require_tier("pro")
def dividend_income_download_latest():
    """Stream the most recent Dividend Statement PDF for the caller.

    Auto-resolves to the newest `dividend_income` row so the frontend
    can link `download` without tracking IDs. Owner-only.

    404 — no statement exists yet. 410 — row exists but no PDF rendered
    (WeasyPrint unavailable at generation time).
    """
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="dividend_income")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Dividend Statement available yet", kr="아직 사용 가능한 배당 명세서가 없습니다.", code="NO_STATEMENT", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this statement",
            kr="이 명세서의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    month = (artefact.data_json or {}).get("month_label", "month")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"dividend_{month}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/dividend-income/trigger", methods=["POST"])
@artifact_rate_limit
def dividend_income_trigger():
    """Manual trigger for the monthly dividend cron. Admin-only
    (DEV_LOGIN_SECRET + X-Admin-Secret header — same pattern as the
    weekly_memo/trigger)."""
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(target_str)
        except ValueError:
            return api_error(en="invalid target_month (expected YYYY-MM-DD)", kr="target_month 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_TARGET_MONTH", status=400)

    try:
        summary = DividendIncomeService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("dividend_income manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ MONTHLY FINANCE REPORT (Premium) ═══════
# Cash Runway + Cost/Tax Ledger + Watch Items, 6-page PDF fired 1st of
# month 11:00 KST. See services/artifacts/monthly_finance_service.py.

from services.artifacts.monthly_finance_service import (  # noqa: E402
    MonthlyFinanceService,
)


@artifacts_bp.route("/monthly-finance/preview", methods=["GET"])
@api_auth
@require_tier("premium")
def monthly_finance_preview():
    """Generate (don't email) a preview finance report for the caller.

    Returns: { ok, data, html }
    """
    try:
        svc = MonthlyFinanceService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("monthly_finance preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/monthly-finance/download", methods=["GET"])
@api_auth
@require_tier("premium")
def monthly_finance_download_latest():
    """Stream the most recent Monthly Finance Report PDF for the caller.

    Auto-resolves to the newest `monthly_finance` row. Owner-only.

    404 — no report exists yet. 410 — row exists but no PDF rendered.
    """
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="monthly_finance")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Finance Report available yet", kr="아직 사용 가능한 재무 리포트가 없습니다.", code="NO_REPORT", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this report",
            kr="이 리포트의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    month = (artefact.data_json or {}).get("month_label", "month")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"finance_{month}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/monthly-finance/trigger", methods=["POST"])
@artifact_rate_limit
def monthly_finance_trigger():
    """Manual trigger for the monthly finance cron. Admin-only."""
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(target_str)
        except ValueError:
            return api_error(en="invalid target_month (expected YYYY-MM-DD)", kr="target_month 형식이 잘못되었습니다 (YYYY-MM-DD).", code="INVALID_TARGET_MONTH", status=400)

    try:
        summary = MonthlyFinanceService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("monthly_finance manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ RISK BOARD MEETING DECK (Premium) ═══════
# Monthly 8-page PDF (day 15 09:30 KST) + event-driven VIX spike edition.
# See services/artifacts/risk_board_service.py for the 7-layer contract.

from services.artifacts.risk_board_service import (  # noqa: E402
    RiskBoardService,
)


@artifacts_bp.route("/risk-board/preview", methods=["GET"])
@api_auth
@require_tier("pro")
def risk_board_preview():
    """Generate (don't email) a preview Risk Board deck for the caller.

    Returns:
        { ok, data, html }
    `data` is the raw 8-page payload; `html` is the rendered PDF-source
    HTML so the frontend preview pane can render it directly.
    """
    try:
        svc = RiskBoardService()
        data = svc.generate_for_user(current_user.id, trigger="monthly")
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("risk_board preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/risk-board/download", methods=["GET"])
@api_auth
@require_tier("pro")
def risk_board_download_latest():
    """Stream the caller's most recent Risk Board PDF. Owner-only.

    404 — no deck generated yet. 410 — row exists but no PDF rendered
    (WeasyPrint unavailable at generation time).
    """
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="risk_board")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Risk Board deck available yet", kr="아직 사용 가능한 리스크 보드가 없습니다.", code="NO_DECK", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this deck",
            kr="이 덱의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    label = (artefact.data_json or {}).get("period_label", "deck")
    safe = label.replace(" ", "_").replace("·", "").replace("/", "-")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"risk_board_{safe}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/risk-board/trigger", methods=["POST"])
@artifact_rate_limit
def risk_board_trigger():
    """Manual trigger for the Risk Board deck. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set.
      2. Caller must pass `X-Admin-Secret` header equal to it.

    Body (optional): { "trigger": "monthly" | "vix_spike" }.
    Default: "monthly". `vix_spike` bypasses the threshold check and
    fires a deck to every Premium user (for QA).
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    trigger = (body.get("trigger") or "monthly").strip().lower()
    if trigger not in ("monthly", "vix_spike"):
        return api_error(en="trigger must be 'monthly' or 'vix_spike'", kr="trigger는 'monthly' 또는 'vix_spike' 여야 합니다.", code="TRIGGER_INVALID", status=400)

    svc = RiskBoardService()
    try:
        if trigger == "monthly":
            summary = svc.run_monthly()
        else:
            # Force-fire path: fan out to every premium user regardless of
            # the persistent VIX state. Useful for QA; protected by admin
            # secret above.
            from models import User as _User
            # Use the canonical shared set (services/artifacts/_tiers.py) — the
            # same one RiskBoardService.run_monthly() filters on. The old literal
            # ["premium", "elite"] had two bugs: "elite" is not a real tier so it
            # matched nobody, and premium_plus / founding_lifetime (the highest-
            # paying cohorts) were excluded — exactly the drift _tiers.py exists
            # to prevent.
            # 2026-06-10 B2 tier alignment: Risk Board is sold as a PRO artifact
            # on the pricing page — the cron service moved to PRO_AND_UP, so the
            # force-fire fan-out must match (one tier truth per artifact).
            from services.artifacts._tiers import PAID_TIERS_PRO_AND_UP
            paid = (
                _User.query
                .filter(_User.subscription_tier.in_(list(PAID_TIERS_PRO_AND_UP)))
                .all()
            )
            notified = 0
            for u in paid:
                try:
                    r = svc.run_for_user(u, trigger="vix_spike")
                    if r is not None:
                        notified += 1
                except Exception as exc:
                    db.session.rollback()
                    current_app.logger.error(
                        "risk_board spike trigger failed user %s: %s",
                        u.id, exc,
                    )
            summary = {"trigger": "vix_spike",
                       "attempted": len(paid),
                       "notified": notified}
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("risk_board manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ PORTFOLIO SEGMENT REPORT (Premium) ═══════
# Quarterly 4-page PDF (1/7, 4/7, 7/7, 10/7 @ 10:00 KST). Sector / Region /
# Style breakdown — see services/artifacts/portfolio_segment_service.py.

from services.artifacts.portfolio_segment_service import (  # noqa: E402
    PortfolioSegmentService,
)


@artifacts_bp.route("/portfolio-segment/preview", methods=["GET"])
@api_auth
@require_tier("pro")
def portfolio_segment_preview():
    """Generate (don't email) a preview Portfolio Segment report for the caller.

    Returns:
        { ok, data, html }
    """
    try:
        svc = PortfolioSegmentService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("portfolio_segment preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/portfolio-segment/download", methods=["GET"])
@api_auth
@require_tier("pro")
def portfolio_segment_download_latest():
    """Stream the caller's most recent Portfolio Segment PDF. Owner-only.

    404 — no report generated yet. 410 — row exists but no PDF rendered.
    """
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="portfolio_segment")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Portfolio Segment report available yet", kr="아직 사용 가능한 포트폴리오 세그먼트 리포트가 없습니다.", code="NO_REPORT", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this report",
            kr="이 리포트의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    quarter = (artefact.data_json or {}).get("quarter_label", "quarter")
    safe_q = quarter.replace(" ", "_")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"portfolio_segment_{safe_q}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/portfolio-segment/trigger", methods=["POST"])
@artifact_rate_limit
def portfolio_segment_trigger():
    """Manual trigger for the quarterly cron. Admin-only.

    Gating — identical to weekly_memo/trigger.
    Body (optional): { "quarter_end": "2026-03-31" } to pin the audit
    window. Defaults to today (which the `_quarter_bounds` helper maps
    to whichever quarter just closed).
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    qe_str = body.get("quarter_end")
    quarter_end = None
    if qe_str:
        try:
            quarter_end = date.fromisoformat(qe_str)
        except ValueError:
            return api_error(
                en="invalid quarter_end (expected YYYY-MM-DD)",
                kr="quarter_end 형식이 잘못되었습니다 (YYYY-MM-DD).",
                code="INVALID_QUARTER_END", status=400,
            )

    try:
        summary = PortfolioSegmentService().run_quarterly(quarter_end=quarter_end)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("portfolio_segment manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ CAPITAL ALLOCATION CALCULATOR (Premium, on-demand) ═══════
# Premium-only What-If calculator. Frontend POSTs {cash_amount, scenarios[]}
# and gets back a calc_id + preview data. Follow-up GETs render the PDF
# from the persisted Artifact row. Quarterly scheduler sends a reminder
# email only — never fires a calculation autonomously.

from services.artifacts.capital_allocation_service import (  # noqa: E402
    CapitalAllocationService,
)


@artifacts_bp.route("/capital-allocation/calculate", methods=["POST"])
@api_auth
@require_tier("premium")
@artifact_rate_limit
def capital_allocation_calculate():
    """Run the What-If calculator with up to 4 caller-supplied scenarios.

    Body:
        {
          "cash_amount": 1000000,
          "scenarios": [
            {"type": "diversify_existing", "params": {}},
            {"type": "new_ticker",         "params": {"ticker": "NVDA"}},
            {"type": "cash",               "params": {}},
            {"type": "dividend_etf",       "params": {"ticker": "SCHD"}}
          ]
        }

    Returns:
        { ok, calc_id, data }
    """
    body = request.get_json(silent=True) or {}
    cash_amount = body.get("cash_amount")
    scenarios = body.get("scenarios")

    if cash_amount is None:
        return api_error(en="cash_amount is required", kr="cash_amount가 필요합니다.", code="CASH_AMOUNT_REQUIRED", status=400)
    if scenarios is None:
        return api_error(en="scenarios is required", kr="scenarios가 필요합니다.", code="SCENARIOS_REQUIRED", status=400)

    svc = CapitalAllocationService()
    try:
        data = svc.calculate_for_user(
            current_user.id,
            cash_amount=cash_amount,
            scenarios=scenarios,
        )
    except ValueError as exc:
        return api_error(en="Bad request", kr="잘못된 요청입니다.", code="BAD_REQUEST_400", status=400)
    except Exception as exc:
        current_app.logger.error("capital_allocation calc failed: %s", exc)
        return api_error(en="Calculation failed (internal error)", kr="계산에 실패했습니다.", code="CALCULATION_INTERNAL_ERROR", status=500)

    try:
        pdf_bytes = svc.render_pdf(data)
        artefact = svc.persist(current_user.id, data, pdf_bytes)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("capital_allocation persist failed: %s", exc)
        return api_error(en="Persist failed (internal error)", kr="저장에 실패했습니다.", code="PERSIST_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "calc_id": artefact.id, "data": data})


@artifacts_bp.route("/capital-allocation/preview/<int:calc_id>",
                    methods=["GET"])
@api_auth
@require_tier("premium")
def capital_allocation_preview(calc_id: int):
    """Return the persisted calculation payload (+ rendered HTML). Owner-only."""
    artefact = db.session.get(Artifact, calc_id)
    if (artefact is None or artefact.user_id != current_user.id
            or artefact.type != "capital_allocation"):
        return api_error(en="Calculation not found", kr="계산을 찾을 수 없습니다.", code="CALCULATION_NOT_FOUND", status=404)

    svc = CapitalAllocationService()
    try:
        html = svc.render_html(artefact.data_json or {})
    except Exception as exc:
        current_app.logger.error("capital_allocation preview render failed: %s", exc)
        return api_error(en="Render failed (internal error)", kr="렌더링에 실패했습니다.", code="RENDER_INTERNAL_ERROR", status=500)

    return jsonify({
        "ok":   True,
        "id":   artefact.id,
        "data": artefact.data_json or {},
        "html": html,
    })


@artifacts_bp.route("/capital-allocation/download/<int:calc_id>",
                    methods=["GET"])
@api_auth
@require_tier("premium")
def capital_allocation_download(calc_id: int):
    """Stream the calculator's persisted PDF. Owner-only."""
    artefact = db.session.get(Artifact, calc_id)
    if (artefact is None or artefact.user_id != current_user.id
            or artefact.type != "capital_allocation"):
        return api_error(en="Calculation not found", kr="계산을 찾을 수 없습니다.", code="CALCULATION_NOT_FOUND", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this calculation",
            kr="이 계산의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    token = (artefact.data_json or {}).get("calc_token", "calc")
    safe = str(token).replace(" ", "_")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"capital_allocation_{safe}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/capital-allocation/reminder-trigger", methods=["POST"])
@artifact_rate_limit
def capital_allocation_reminder_trigger():
    """Admin-only manual trigger for the quarterly reminder email.

    Note: this ONLY sends reminder emails. It never runs calculations
    autonomously — that's deliberate for the legal posture.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    try:
        summary = CapitalAllocationService().send_quarterly_reminder()
    except Exception as exc:
        current_app.logger.error("capital_allocation reminder failed: %s", exc)
        return api_error(en="Reminder run failed (internal error)", kr="리마인더 실행에 실패했습니다.", code="REMINDER_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ INSIDER TRANSACTION MIRROR (Premium, weekly) ═══════
# Weekly 3-page PDF (Mon 09:00 KST). SEC Form 4 + DART insider feed —
# strictly factual. See services/artifacts/insider_mirror_service.py.

from services.artifacts.insider_mirror_service import (  # noqa: E402
    InsiderMirrorService,
)


@artifacts_bp.route("/insider-mirror/preview", methods=["GET"])
@api_auth
@require_tier("pro")
def insider_mirror_preview():
    """Generate (don't email) a preview Insider Mirror for the caller.

    Returns { ok, data, html }. The html string is the same source that
    WeasyPrint renders into the weekly PDF so the frontend can surface
    an in-app preview.
    """
    try:
        svc = InsiderMirrorService()
        data = svc.generate_for_user(current_user.id)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("insider_mirror preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/insider-mirror/download", methods=["GET"])
@api_auth
@require_tier("pro")
def insider_mirror_download_latest():
    """Stream the caller's most recent Insider Mirror PDF. Owner-only."""
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="insider_mirror")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Insider Mirror report available yet", kr="아직 사용 가능한 내부자 미러 리포트가 없습니다.", code="NO_REPORT", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this report",
            kr="이 리포트의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    period = (artefact.data_json or {}).get("period_label", "week")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", period) if period else "week"
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"insider_mirror_{safe}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/insider-mirror/trigger", methods=["POST"])
@artifact_rate_limit
def insider_mirror_trigger():
    """Admin-only manual trigger for the weekly insider mirror cron."""
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    anchor_str = body.get("anchor")
    anchor = None
    if anchor_str:
        try:
            anchor = date.fromisoformat(anchor_str)
        except ValueError:
            return api_error(
                en="invalid anchor (expected YYYY-MM-DD)",
                kr="anchor 형식이 잘못되었습니다 (YYYY-MM-DD).",
                code="INVALID_ANCHOR", status=400,
            )

    try:
        summary = InsiderMirrorService().run_weekly(anchor=anchor)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("insider_mirror manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ YEAR-END INVESTOR LETTER (Premium, annual) ═══════
# Download-only surface — no share link, no OG card, no public landing.
# Cron target: 12/31 10:00 KST (app.py :: year_end_letter_annual).
#
# Note on legal posture: this block was added 2026-04-19 as part of the
# explicit legal-safety design. Every endpoint below is owner-bound and
# tier-gated; the public share surface that *other* artefact classes
# expose (monthly_brag_share) is intentionally absent here.

from services.artifacts.year_end_letter_service import (  # noqa: E402
    YearEndLetterService,
)


@artifacts_bp.route("/year-end-letter/preview", methods=["GET"])
@api_auth
@require_tier("premium")
def year_end_letter_preview():
    """Generate (don't email) a preview Year-End Letter for the caller.

    Returns:
        { ok, data, html }
    Query param `year` (optional, YYYY) overrides the target year —
    handy for QA / admin demos.
    """
    year_str = request.args.get("year")
    target_year: int | None = None
    if year_str:
        try:
            target_year = int(year_str)
        except ValueError:
            return api_error(en="invalid year (expected YYYY)", kr="year 형식이 잘못되었습니다 (YYYY).", code="INVALID_YEAR", status=400)

    try:
        svc = YearEndLetterService()
        data = svc.generate_for_user(current_user.id, target_year=target_year)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("year_end_letter preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/year-end-letter/download", methods=["GET"])
@api_auth
@require_tier("premium")
def year_end_letter_download_latest():
    """Stream the caller's most recent Year-End Letter PDF. Owner-only.

    404 — no letter generated yet. 410 — row exists but no PDF rendered
    (WeasyPrint unavailable at generation time).
    """
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="year_end_letter")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Year-End Letter available yet", kr="아직 사용 가능한 연말 레터가 없습니다.", code="NO_LETTER", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this letter",
            kr="이 레터의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    year_val = (artefact.data_json or {}).get("year", "year")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"year_end_letter_{year_val}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/year-end-letter/trigger", methods=["POST"])
@artifact_rate_limit
def year_end_letter_trigger():
    """Manual trigger for the annual cron. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set (dev/staging only).
      2. Caller must pass `X-Admin-Secret` header equal to it.

    Body (optional): { "target_year": 2026 }.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    target_year = body.get("target_year")
    if target_year is not None:
        try:
            target_year = int(target_year)
        except (TypeError, ValueError):
            return api_error(en="invalid target_year (expected int)", kr="target_year 형식이 잘못되었습니다 (정수).", code="INVALID_TARGET_YEAR", status=400)

    try:
        summary = YearEndLetterService().run_annual(target_year=target_year)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("year_end_letter manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════ QUARTERLY SELF REPORT (Premium, quarterly) ═══════
# 15-page Self 10-K + Thesis Reality Check. Absorbs the old Self Audit
# (still importable via SelfAuditService for Part 2 reuse). Download-only
# surface — no share links. Cron target: month=1,4,7,10 day=7 10:00 KST
# (see app.py :: quarterly_self_report).

from services.artifacts.quarterly_self_report_service import (  # noqa: E402
    QuarterlySelfReportService,
)


@artifacts_bp.route("/quarterly-self/preview", methods=["GET"])
@api_auth
@require_tier("pro")
def quarterly_self_report_preview():
    """Generate (don't email) a preview Quarterly Self Report for the caller.

    Returns:
        { ok, data, html }
    Query param `quarter_end` (YYYY-MM-DD) pins the audit window;
    otherwise the service resolves to "today's" quarter.
    """
    qe_str = request.args.get("quarter_end")
    quarter_end: date | None = None
    if qe_str:
        try:
            quarter_end = date.fromisoformat(qe_str)
        except ValueError:
            return api_error(
                en="invalid quarter_end (expected YYYY-MM-DD)",
                kr="quarter_end 형식이 잘못되었습니다 (YYYY-MM-DD).",
                code="INVALID_QUARTER_END", status=400,
            )

    try:
        svc = QuarterlySelfReportService()
        data = svc.generate_for_user(current_user.id, quarter_end=quarter_end)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("quarterly_self preview failed: %s", exc)
        return api_error(en="Preview failed (internal error)", kr="미리보기 생성에 실패했습니다.", code="PREVIEW_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/quarterly-self/download", methods=["GET"])
@api_auth
@require_tier("pro")
def quarterly_self_report_download_latest():
    """Stream the caller's most recent Quarterly Self Report PDF. Owner-only."""
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="quarterly_self_report")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return api_error(en="No Quarterly Self Report available yet", kr="아직 사용 가능한 분기 자가 리포트가 없습니다.", code="NO_REPORT", status=404)

    if not artefact.pdf_path:
        return api_error(
            en="PDF unavailable for this report",
            kr="이 리포트의 PDF가 아직 준비되지 않았습니다.",
            code="PDF_NOT_RENDERED", status=410,
        )

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(
            en="PDF file missing on disk",
            kr="PDF 파일이 서버에 존재하지 않습니다.",
            code="PDF_FILE_MISSING", status=410,
        )

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    quarter = (artefact.data_json or {}).get("quarter_label", "quarter")
    safe_q = quarter.replace(" ", "_")
    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"quarterly_self_{safe_q}_{artefact.id}.pdf",
    )


@artifacts_bp.route("/quarterly-self/trigger", methods=["POST"])
@artifact_rate_limit
def quarterly_self_report_trigger():
    """Manual trigger for the quarterly cron. Admin-only.

    Body (optional): { "quarter_end": "2026-03-31" }.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    qe_str = body.get("quarter_end")
    quarter_end = None
    if qe_str:
        try:
            quarter_end = date.fromisoformat(qe_str)
        except ValueError:
            return api_error(
                en="invalid quarter_end (expected YYYY-MM-DD)",
                kr="quarter_end 형식이 잘못되었습니다 (YYYY-MM-DD).",
                code="INVALID_QUARTER_END", status=400,
            )

    try:
        summary = QuarterlySelfReportService().run_quarterly(
            quarter_end=quarter_end,
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("quarterly_self manual run failed: %s", exc)
        return api_error(en="Manual run failed (internal error)", kr="수동 실행에 실패했습니다.", code="MANUAL_RUN_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "summary": summary})


# ═══════════════════════════════════════════════════════════════════════════
#  UNIFIED /generate ENDPOINT  (Wave 1 — frontend v2 contract)
# ═══════════════════════════════════════════════════════════════════════════
#
#  Single entry point for the frontend "Generate" button. Dispatches to the
#  matching artefact service by `type`. Replaces the per-type preview/trigger
#  endpoints for the unified UX (those routes remain for legacy/QA flows).
#
#  Response contract (always 200 unless input is malformed):
#      {
#          "status":     "ready" | "empty" | "interactive",
#          "type":       <slug>,
#          "artifact_id": <int|null>,
#          "data":       <payload dict | null>,
#          "reason":     <empty-state code | null>,
#          "message":    <human-readable | null>,
#      }
#
#  Empty states are NOT errors. New users with no positions / no trades get
#  `status="empty"` so the frontend can render an EmptyState UI prompting the
#  first action. Three "interactive" types (pre_trade_checklist, dd_checklist,
#  capital_allocation) are workflow artifacts driven by user input — calling
#  /generate for them returns `status="interactive"` plus a `redirect` hint.
# ═══════════════════════════════════════════════════════════════════════════

# Import the remaining service classes lazily-at-module-level so the dispatch
# table can resolve them by reference. Each import already exists above as a
# late `noqa: E402` block; we re-bind here to keep the dispatch table
# self-contained and grep-able. Imports are no-ops if the symbol already
# exists in the module namespace.
from services.artifacts.brag_card_service import BragCardService  # noqa: E402,F811
from services.artifacts.burn_rate_service import BurnRateService  # noqa: E402,F811
from services.artifacts.credit_rating_service import CreditRatingService  # noqa: E402,F811
from services.artifacts.dividend_income_service import DividendIncomeService  # noqa: E402,F811
from services.artifacts.earnings_prebrief_service import (  # noqa: E402,F811
    EarningsPreBriefService,
)
from services.artifacts.insider_mirror_service import InsiderMirrorService  # noqa: E402,F811
from services.artifacts.kpi_dashboard_service import KPIDashboardService  # noqa: E402,F811
from services.artifacts.monthly_finance_service import MonthlyFinanceService  # noqa: E402,F811
from services.artifacts.portfolio_segment_service import (  # noqa: E402,F811
    PortfolioSegmentService,
)
from services.artifacts.quarterly_self_report_service import (  # noqa: E402,F811
    QuarterlySelfReportService,
)
from services.artifacts.risk_board_service import RiskBoardService  # noqa: E402,F811
from services.artifacts.self_audit_service import SelfAuditService  # noqa: E402,F811
from services.artifacts.sp500_backtest_service import SP500BacktestService  # noqa: E402
from services.artifacts.year_end_letter_service import YearEndLetterService  # noqa: E402,F811


# Dispatch table: type → (ServiceClass, generator-method, artifact-db-type).
# `artifact-db-type` is the value persisted on `Artifact.type` so /list and
# /<id>/download routes round-trip cleanly. None ⇒ this artefact is not
# persisted via /generate (interactive types).
_ARTIFACT_DISPATCH: dict[str, tuple] = {
    "weekly_memo":           (WeeklyMemoService,           "generate_for_user", "weekly_memo"),
    "brag_card":             (BragCardService,             "generate_for_user", "brag_card"),
    "monthly_brag":          (MonthlyBragService,          "generate_for_user", "monthly_brag"),
    "earnings_prebrief":     (EarningsPreBriefService,     "generate_for_user", "earnings_prebrief"),
    "self_audit":            (SelfAuditService,            "generate_for_user", "self_audit"),
    "risk_board":            (RiskBoardService,            "generate_for_user", "risk_board"),
    "year_end_letter":       (YearEndLetterService,        "generate_for_user", "year_end_letter"),
    "quarterly_self_report": (QuarterlySelfReportService,  "generate_for_user", "quarterly_self_report"),
    "kpi_dashboard":         (KPIDashboardService,         "generate_for_user", "kpi_dashboard"),
    "dividend_income":       (DividendIncomeService,       "generate_for_user", "dividend_income"),
    "monthly_finance":       (MonthlyFinanceService,       "generate_for_user", "monthly_finance"),
    "burn_rate":             (BurnRateService,             "generate_for_user", "burn_rate"),
    "capital_allocation":    None,   # interactive — POST /capital-allocation/calculate
    "credit_rating":         (CreditRatingService,         "generate_for_user", "credit_rating"),
    "insider_mirror":        (InsiderMirrorService,        "generate_for_user", "insider_mirror"),
    "portfolio_segment":     (PortfolioSegmentService,     "generate_for_user", "portfolio_segment"),
    "pre_trade_checklist":   None,   # interactive — POST /pre-trade/start
    "dd_checklist":          None,   # interactive — POST /dd-checklist/submit
    # Universal observation record (not per-user attribution). Persona only
    # tints the eyebrow; numbers come from docs/BACKTEST_RESULTS.md.
    "sp500_backtest":        (SP500BacktestService,        "generate_for_user", "sp500_backtest"),
}

# Minimum tier per artifact type — MUST mirror the @require_tier on each
# artifact's individual Flask route. The unified /generate endpoint dispatches
# straight into generate_for_user() (which does NOT self-gate), so without this
# map a free user could POST {"type":"weekly_memo"} and receive a paid artifact
# (tier bypass / revenue leak). Types absent here are intentionally free
# (brag_card / monthly_brag = viral; sp500_backtest = universal observation).
# 2026-06-11 B2 tier alignment: tiers follow the PRICING PAGE
# (frontend/src/app/pricing/page.tsx) — locked by
# tests/test_artifact_tier_alignment.py.
_ARTIFACT_MIN_TIER: dict[str, str] = {
    "weekly_memo": "pro",
    "earnings_prebrief": "pro",
    "kpi_dashboard": "premium",
    "burn_rate": "premium",
    "credit_rating": "premium",
    "dd_checklist": "pro",
    "self_audit": "pro",
    "risk_board": "pro",
    "year_end_letter": "premium",
    "quarterly_self_report": "pro",
    "dividend_income": "pro",
    "monthly_finance": "premium",
    "capital_allocation": "premium",
    "insider_mirror": "pro",
    "portfolio_segment": "pro",
}

# Legacy request aliases — normalised to a canonical dispatch key BEFORE the
# dispatch/tier/empty/persist pipeline, so gating and the persisted
# Artifact.type always use the canonical slug. NOT part of _ARTIFACT_MIN_TIER
# (the tier-alignment gate test pins that map 1:1 to the pricing page).
#
# risk_report → risk_board (2026-06-11): the reports-v2 "Risk Note" tile
# shipped posting type="risk_report" against a service that never existed
# (SPEC §4 documented it as a GAP → guaranteed 400). The tile now requests
# "risk_board" — the existing deck already carries the advertised VaR /
# drawdown / tail-risk / sector-concentration content. This alias keeps
# already-open tabs working through the deploy window.
_ARTIFACT_TYPE_ALIASES: dict[str, str] = {
    "risk_report": "risk_board",
}

# Interactive types — frontend redirects to a dedicated UI instead of
# generating from the unified button. Map → redirect path so the response
# can hint the frontend without hard-coding URLs there.
_INTERACTIVE_REDIRECTS: dict[str, str] = {
    "capital_allocation":  "/api/artifacts/capital-allocation/calculate",
    "pre_trade_checklist": "/api/pre-trade/start",
    "dd_checklist":        "/api/artifacts/dd-checklist/pending",
}

# Per-type empty-state heuristics. These do NOT modify service code — they
# inspect either the explicit `is_empty` flag (brag_card, monthly_brag) or
# fall back to a pre-flight check on the user's data. Returning the standard
# `(reason, message)` tuple lets the route shape one EmptyState response.
def _empty_check(user_id: int, artifact_type: str,
                 data: dict | None) -> tuple[str, str] | None:
    """Return (reason, message) when the artefact has no real content.

    None ⇒ data is renderable. Reasons are stable enums for frontend
    EmptyState UI dispatch (do NOT translate them server-side; the
    frontend i18n layer owns the user-facing copy).
    """
    # Lazy imports — keep the route module importable even when the
    # broader app context is half-loaded (test collection time, etc).
    from models import Position, TradeHistory

    # 1) Service-level explicit flag wins. brag_card / monthly_brag set
    #    only `is_empty=True` → legacy default of "no_trades".
    #    The 5 §101-grey services (earnings_prebrief, year_end_letter,
    #    credit_rating, insider_mirror, pre_trade_checklist) additionally
    #    set `empty_reason` ("not_in_portfolio" / "no_positions" /
    #    "no_upcoming_earnings") which we surface verbatim so the
    #    frontend EmptyState UI can branch.
    if isinstance(data, dict) and data.get("is_empty") is True:
        explicit_reason = data.get("empty_reason")
        if isinstance(explicit_reason, str) and explicit_reason:
            return (explicit_reason, str(data.get("message") or explicit_reason))
        return ("no_trades", "first_trade_needed")

    # 2) Per-type prerequisite checks — covers services that don't mark
    #    `is_empty` but produce a hollow payload when the user has no
    #    portfolio yet.
    needs_positions = {
        "weekly_memo", "risk_board", "credit_rating", "insider_mirror",
        "portfolio_segment", "kpi_dashboard", "dividend_income",
        "year_end_letter",
    }
    needs_trades = {
        "self_audit", "quarterly_self_report", "monthly_finance",
        "burn_rate",
    }

    if artifact_type in needs_positions:
        try:
            n = Position.query.filter_by(user_id=user_id).count()
        except Exception:
            n = 0
        if n == 0:
            return ("no_positions", "first_position_needed")

    if artifact_type in needs_trades:
        try:
            n = TradeHistory.query.filter_by(user_id=user_id).count()
        except Exception:
            n = 0
        if n == 0:
            return ("no_trades", "first_trade_needed")

    return None


def _persist_generated(user_id: int, db_type: str,
                       data: dict, pdf_bytes: bytes | None) -> Artifact:
    """UPSERT a row into `artifacts` matching the per-service title shape.

    Title scheme is intentionally loose — the unique constraint is
    (user_id, type, title) so a re-generate within the same period
    overwrites instead of duplicating. Each service's own title format
    (e.g. "Week 17 Investor Memo — 2026-04-29") is used when present in
    the data payload; otherwise we fall back to a date-stamped slug.
    """
    title = (
        data.get("title")
        or data.get("month_label_long")
        or data.get("month_label")
        or data.get("week_label")
        or data.get("period_label")
        or f"{db_type} — {date.today().isoformat()}"
    )
    title = str(title)[:200]

    pdf_path: str | None = None
    if pdf_bytes:
        try:
            base = Path(current_app.instance_path) / "artifacts" / str(user_id)
            base.mkdir(parents=True, exist_ok=True)
            stamp = date.today().isoformat()
            path = base / f"{db_type}_{stamp}.pdf"
            path.write_bytes(pdf_bytes)
            pdf_path = str(path)
        except Exception as exc:
            current_app.logger.warning(
                "PDF write failed (user=%s type=%s): %s", user_id, db_type, exc
            )

    row = (
        Artifact.query
        .filter_by(user_id=user_id, type=db_type, title=title)
        .first()
    )
    if row:
        row.data_json = data
        if pdf_path:
            row.pdf_path = pdf_path
    else:
        row = Artifact(
            user_id=user_id,
            type=db_type,
            title=title,
            data_json=data,
            pdf_path=pdf_path,
        )
        db.session.add(row)
    db.session.commit()
    return row


@artifacts_bp.route("/generate", methods=["POST"])
@api_auth
@artifact_rate_limit
def artifacts_generate():
    """Unified Generate endpoint — frontend "Generate" button.

    Body (JSON):
        {
            "type":   <one of 17 artefact slugs>,    # required
            "params": { ...optional kwargs... }       # optional
        }

    Allowed `params` keys (passed through to `generate_for_user`):
        - target_date / month / target_month / as_of / quarter_end /
          target_year / anchor   →  ISO date string ("YYYY-MM-DD")
        - ticker                 →  string (earnings_prebrief only)
        - anonymous              →  bool   (brag_card / monthly_brag)
        - target_year            →  int    (year_end_letter)

    Response (always JSON; HTTP 200 unless input is malformed):
        {
            "status":      "ready" | "empty" | "interactive",
            "type":        <slug>,
            "artifact_id": <int|null>,
            "data":        <payload|null>,
            "reason":      <enum|null>,
            "message":     <code|null>,
            "redirect":    <path|null>,    # interactive types only
        }
    """
    body = request.get_json(silent=True) or {}
    artifact_type = (body.get("type") or "").strip().lower()
    # Canonicalise legacy aliases first — every later stage (dispatch, tier
    # gate, empty checks, persistence, response echo) sees the real type.
    artifact_type = _ARTIFACT_TYPE_ALIASES.get(artifact_type, artifact_type)
    params = body.get("params") or {}

    if not isinstance(params, dict):
        return api_error(en="params must be a JSON object", kr="params는 JSON 객체여야 합니다.", code="PARAMS_OBJECT_REQUIRED", status=400)

    if not artifact_type:
        return api_error(en="type is required", kr="type이 필요합니다.", code="TYPE_REQUIRED", status=400)

    if artifact_type not in _ARTIFACT_DISPATCH:
        return api_error(
            en=f"unknown artifact type: {artifact_type}",
            kr=f"알 수 없는 아티팩트 유형: {artifact_type}",
            code="UNKNOWN_ARTIFACT_TYPE", status=400,
            allowed=sorted(_ARTIFACT_DISPATCH.keys()),
        )

    # ── Interactive artefacts — short-circuit with a redirect hint ──────
    entry = _ARTIFACT_DISPATCH[artifact_type]
    if entry is None:
        return jsonify({
            "status":      "interactive",
            "type":        artifact_type,
            "artifact_id": None,
            "data":        None,
            "reason":      "interactive_workflow",
            "message":     f"{artifact_type}_requires_user_input",
            "redirect":    _INTERACTIVE_REDIRECTS.get(artifact_type),
        })

    service_cls, method_name, db_type = entry

    # ── Translate JSON params → kwargs the per-service method accepts ───
    kwargs: dict = {}
    date_keys = {
        "target_date", "month", "target_month", "as_of",
        "quarter_end", "anchor",
    }
    for key in date_keys:
        raw = params.get(key)
        if raw is None:
            continue
        try:
            kwargs[key] = date.fromisoformat(str(raw))
        except ValueError:
            return api_error(
                en=f"invalid {key} (expected YYYY-MM-DD)",
                kr=f"{key} 형식이 잘못되었습니다 (YYYY-MM-DD).",
                code="INVALID_DATE_FIELD", status=400,
            )

    if "target_year" in params:
        try:
            kwargs["target_year"] = int(params["target_year"])
        except (TypeError, ValueError):
            return api_error(en="target_year must be an integer", kr="target_year는 정수여야 합니다.", code="TARGET_YEAR_INT_REQUIRED", status=400)

    if "anonymous" in params:
        if not isinstance(params["anonymous"], bool):
            return api_error(en="anonymous must be a boolean", kr="anonymous는 boolean이어야 합니다.", code="ANONYMOUS_BOOL_REQUIRED", status=400)
        kwargs["anonymous"] = params["anonymous"]

    # earnings_prebrief is the one positional-required arg in the table —
    # ticker is required, all the rest is optional kwargs.
    positional: list = []
    if artifact_type == "earnings_prebrief":
        ticker = (params.get("ticker") or "").strip().upper()
        if not ticker:
            return api_error(
                en="earnings_prebrief requires params.ticker",
                kr="earnings_prebrief는 params.ticker가 필요합니다.",
                code="EARNINGS_TICKER_REQUIRED", status=400,
            )
        positional.append(ticker)

    # ── Tier gate — mirror the @require_tier on each artifact's own route ──
    # generate_for_user() does not self-gate, so without this a free user could
    # POST {"type":"weekly_memo"} and receive a paid artifact (tier bypass).
    # Placed after param validation + the interactive short-circuit (so 400s
    # and redirect hints behave for everyone) but before any generation work.
    required_tier = _ARTIFACT_MIN_TIER.get(artifact_type)
    if required_tier:
        user_tier = (
            getattr(current_user, "effective_tier", None)
            or getattr(current_user, "subscription_tier", "free")
            or "free"
        )
        if _TIER_RANK.get(user_tier, 0) < _TIER_RANK.get(required_tier, 0):
            return jsonify({
                "error": "Upgrade required",
                "required_tier": required_tier,
                "code": "UPGRADE_REQUIRED",
            }), 403

    # ── Cheap pre-flight empty check — avoids spinning up the heavy
    #    pipeline for a brand-new user. The service is still called
    #    *after* the check is None, so service-internal `is_empty`
    #    payloads remain authoritative.
    pre_empty = _empty_check(current_user.id, artifact_type, data=None)
    if pre_empty is not None:
        reason, message = pre_empty
        return jsonify({
            "status":      "empty",
            "type":        artifact_type,
            "artifact_id": None,
            "data":        None,
            "reason":      reason,
            "message":     message,
            "redirect":    None,
        })

    # ── Generate ────────────────────────────────────────────────────────
    try:
        svc = service_cls()
        method = getattr(svc, method_name)
        data = method(current_user.id, *positional, **kwargs)
    except ValueError as exc:
        # `generate_for_user` raises ValueError for "user not found" —
        # surface as 400 not 500.
        return api_error(en="Bad request", kr="잘못된 요청입니다.", code="BAD_REQUEST_400", status=400)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception(
            "artifacts.generate failed (user=%s type=%s): %s",
            current_user.id, artifact_type, exc,
        )
        # 2026-05-17 wave 14 P1: drop raw exc from response body — see
        # the bulk scrub note above. logger.exception already logged
        # full traceback for ops.
        return api_error(
            en="Generation failed (internal error)",
            kr="아티팩트 생성에 실패했습니다.",
            code="GENERATION_INTERNAL_ERROR", status=500,
            type=artifact_type,
        )

    # ── Service-internal empty signal (e.g. brag_card.is_empty) ────────
    post_empty = _empty_check(current_user.id, artifact_type, data=data)
    if post_empty is not None:
        reason, message = post_empty
        return jsonify({
            "status":      "empty",
            "type":        artifact_type,
            "artifact_id": None,
            "data":        data,
            "reason":      reason,
            "message":     message,
            "redirect":    None,
        })

    # ── Render PDF where supported ──────────────────────────────────────
    # H2: render_pdf returning None must NOT be silently reported as a clean
    # "ready". We distinguish three outcomes so the caller never shows a
    # "complete" with a missing attachment without knowing why:
    #   - "ok"          → bytes produced, attachment present
    #   - "unavailable" → WeasyPrint native dep missing (data still valid,
    #                     viewable on-screen; expected on some envs)
    #   - "render_failed" → dep present but rendering raised/returned None
    #                       (a genuine failure — surfaced, not swallowed)
    #   - "not_applicable" → artefact does not produce a PDF (e.g. brag_card)
    pdf_bytes: bytes | None = None
    render_pdf = getattr(svc, "render_pdf", None)
    if not callable(render_pdf):
        pdf_status = "not_applicable"
        pdf_error: str | None = None
    else:
        weasy_ok = _weasyprint_importable()
        try:
            pdf_bytes = render_pdf(data)
        except Exception as exc:
            # render_pdf is expected to swallow internally; this catches the
            # rare case it does not.
            pdf_bytes = None
            current_app.logger.warning(
                "render_pdf raised (user=%s type=%s): %s",
                current_user.id, artifact_type, exc,
            )
        if pdf_bytes:
            pdf_status = "ok"
            pdf_error = None
        elif not weasy_ok:
            pdf_status = "unavailable"
            pdf_error = None
            current_app.logger.info(
                "render_pdf produced no bytes — WeasyPrint unavailable "
                "(user=%s type=%s)", current_user.id, artifact_type,
            )
        else:
            # Dep is present but no bytes came back → genuine render failure.
            pdf_status = "render_failed"
            pdf_error = "PDF rendering failed — attachment unavailable."
            current_app.logger.error(
                "render_pdf returned no bytes despite WeasyPrint present "
                "(user=%s type=%s)", current_user.id, artifact_type,
            )

    # ── Persist ─────────────────────────────────────────────────────────
    try:
        row = _persist_generated(current_user.id, db_type, data, pdf_bytes)
        artifact_id = row.id
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            "artifact persist failed (user=%s type=%s): %s",
            current_user.id, artifact_type, exc,
        )
        artifact_id = None

    return jsonify({
        "status":        "ready",
        "type":          artifact_type,
        "artifact_id":   artifact_id,
        "data":          data,
        "pdf_available": pdf_bytes is not None,
        "pdf_status":    pdf_status,
        "reason":        None,
        "message":       pdf_error,
        "redirect":      None,
    })


# ═══════ DIAGNOSTICS ═══════
# Production-safe diagnostic endpoint to confirm whether the WeasyPrint
# pipeline (used by /weekly-memo and ~12 other PDF artifacts) is actually
# functional inside the Railway container. The response body itself carries
# the diagnostic — no need to grep Railway logs.
#
# Triggered by HANDOVER 2026-04-29 §결함 #5: PDF 첨부 누락. The DIAG log
# lines added in commit b7bf589 were not visible to the user, so we surface
# the same information through a callable endpoint.

@artifacts_bp.route("/_diag/weasyprint", methods=["GET", "POST"])
@general_rate_limit
def diag_weasyprint():
    """Probe the WeasyPrint pipeline end-to-end and return the result inline.

    Gates: same as cron triggers — admin secret only.

    Probes (each independent, all reported even if one fails):
      1. import_weasyprint   — `from weasyprint import HTML`
      2. render_minimal_pdf  — `HTML(string="<h1>Hi</h1>").write_pdf()`
      3. render_korean_pdf   — same with a Korean character (Noto CJK check)
      4. render_template_pdf — actual weekly_memo template against fake data
      5. fonts_available     — fontconfig list of CJK fonts (best-effort)

    Each probe captures both `ok` (bool) and the exception class+message
    on failure. Native traceback omitted by default to keep the response
    JSON-safe; pass `?traceback=1` to include it.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    import sys
    import traceback as tb_mod

    include_tb = request.args.get("traceback") in ("1", "true", "yes")

    def _probe(fn):
        try:
            return {"ok": True, "result": fn()}
        except BaseException as exc:
            payload = {
                "ok":        False,
                "error_cls": type(exc).__name__,
                "error_msg": str(exc),
            }
            if include_tb:
                payload["traceback"] = tb_mod.format_exc()
            return payload

    # 1. import
    def _import():
        from weasyprint import HTML  # type: ignore  # noqa: F401 — import-test
        import weasyprint  # type: ignore
        return {
            "weasyprint_version": getattr(weasyprint, "__version__", "?"),
            "module_path":        getattr(weasyprint, "__file__", "?"),
        }
    probe_import = _probe(_import)

    # 2. minimal render (only attempted if import succeeded)
    def _minimal():
        from weasyprint import HTML  # type: ignore
        pdf = HTML(string="<!doctype html><html><body><h1>Hi</h1></body></html>").write_pdf()
        return {"bytes": len(pdf or b""), "starts_with_pdf_magic": (pdf or b"")[:4] == b"%PDF"}
    probe_minimal = _probe(_minimal) if probe_import.get("ok") else {
        "ok": False, "skipped": True, "reason": "import failed",
    }

    # 3. Korean glyph render (catches missing Noto CJK)
    def _korean():
        from weasyprint import HTML  # type: ignore
        pdf = HTML(string="<!doctype html><html><body><h1>주간 메모</h1></body></html>").write_pdf()
        return {"bytes": len(pdf or b"")}
    probe_korean = _probe(_korean) if probe_import.get("ok") else {
        "ok": False, "skipped": True, "reason": "import failed",
    }

    # 4. real weekly_memo template (catches template / asset path issues)
    def _template():
        svc = WeeklyMemoService()
        # Build a minimal valid `data` dict the template expects. We don't
        # touch the DB — purely a render path check.
        fake = {
            "user_name":        "Diag User",
            "week_number":      0,
            "week_label":       "Diag Week",
            "weekly_return_pct": 0.0,
            "top_movers_up":     [],
            "top_movers_down":   [],
            "positions":         [],
            "kpis":              {},
            "subtitle":          "diagnostic",
            "summary":           "diagnostic",
            "disclaimer":        "diagnostic — not for distribution",
        }
        pdf = svc.render_pdf(fake)
        return {
            "bytes":               len(pdf or b"") if pdf else 0,
            "render_pdf_returned": "bytes" if pdf else "None",
        }
    probe_template = _probe(_template) if probe_import.get("ok") else {
        "ok": False, "skipped": True, "reason": "import failed",
    }

    # 5. Font availability via fontconfig (best-effort; fc-list may not exist)
    def _fonts():
        import shutil as _shutil
        import subprocess as _sp
        if not _shutil.which("fc-list"):
            return {"fc_list_available": False}
        out = _sp.run(["fc-list", ":lang=ko", "family"],
                      capture_output=True, text=True, timeout=5)
        families = sorted({ln.strip() for ln in out.stdout.splitlines() if ln.strip()})
        return {
            "fc_list_available": True,
            "ko_font_count":     len(families),
            "ko_font_families":  families[:20],  # cap to avoid huge payload
        }
    probe_fonts = _probe(_fonts)

    return jsonify({
        "ok":      probe_import.get("ok") and probe_template.get("ok"),
        "python":  sys.version.split()[0],
        "platform": sys.platform,
        "probes": {
            "import_weasyprint":   probe_import,
            "render_minimal_pdf":  probe_minimal,
            "render_korean_pdf":   probe_korean,
            "render_template_pdf": probe_template,
            "fonts_available":     probe_fonts,
        },
    })


@artifacts_bp.route("/_diag/weekly-memo-pipeline", methods=["GET", "POST"])
@general_rate_limit
def diag_weekly_memo_pipeline():
    """End-to-end diagnostic for the weekly-memo pipeline using REAL user data.

    Why: /_diag/weasyprint already proved WeasyPrint + template render with
    fake data. If users still get emails without PDF attachments, the bug is
    in the live pipeline (generate_for_user → render_pdf → send_email).
    This endpoint runs the same path against an actual paid user but does
    NOT send email, and surfaces every intermediate result.

    Gates: admin secret only.

    Query/body:
        user_id   — int (optional). When omitted, picks the first paid user.

    Returns each stage with bytes/keys/error so the bug is pinpointable
    from a single curl response.

    Note (2026-05-17 wave B api_error sweep): the diagnostic responses
    below intentionally KEEP the `{ok, stage, error, stages, ...}` shape
    instead of routing through ``api_error()``. They are admin-only and
    the ``error`` field holds a structured dict (``_err_dict(exc)``) or
    progress narrative — not a user-facing message. ``api_error()``
    forces ``error`` to be a string, which would lose the per-stage
    exception class/traceback that makes this endpoint useful. Frontend
    never consumes these routes.
    """
    err = _check_cron_admin_secret()
    if err:
        return err

    import traceback as tb_mod
    from models import User, Position
    from services.artifacts.weekly_memo_service import (
        WeeklyMemoService, _PAID_TIERS,
    )

    # SEC-F fix (2026-05-09 release-prep audit): the admin-secret gate above
    # is intact (PR #150 hmac.compare_digest), but unconditionally returning
    # full backend tracebacks in HTTP bodies is a defense-in-depth violation.
    # If the secret ever leaks (Sentry capture of an admin curl, Railway env
    # screenshot, log forwarding misconfig), every stack trace exposes file
    # paths, function names, and SQLAlchemy schema hints in one round-trip.
    # Mirror the /_diag/weasyprint endpoint pattern: gate traceback behind
    # ?traceback=1, default to {cls, msg-clamped} only.
    include_tb = request.args.get("traceback") in ("1", "true", "yes")

    def _err_dict(exc):
        d = {"cls": type(exc).__name__, "msg": str(exc)[:200]}
        if include_tb:
            d["traceback"] = tb_mod.format_exc()
        return d

    body = request.get_json(silent=True) or {}
    user_id_arg = body.get("user_id") or request.args.get("user_id")
    try:
        user_id_int = int(user_id_arg) if user_id_arg is not None else None
    except (TypeError, ValueError):
        return api_error(en="user_id must be int", kr="user_id는 정수여야 합니다.", code="INVALID_USER_ID", status=400)

    # ── 1. pick user ────────────────────────────────────────────────────
    if user_id_int is not None:
        user = db.session.get(User, user_id_int)
        if not user:
            return api_error(en=f"user {user_id_int} not found", kr=f"사용자 {user_id_int}를 찾을 수 없습니다.", code="USER_NOT_FOUND", status=404)
        pick_reason = "explicit"
    else:
        user = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .first()
        )
        if not user:
            return jsonify({
                "ok": False,
                "stage": "pick_user",
                "error": "no paid user exists (free-tier users skipped by run_weekly)",
                "paid_tiers": list(_PAID_TIERS),
            })
        pick_reason = "first paid user"

    user_info = {
        "id":                user.id,
        "email":             user.email,
        "subscription_tier": user.subscription_tier,
        "pick_reason":       pick_reason,
    }

    # ── 2. positions count ──────────────────────────────────────────────
    pos_count = Position.query.filter_by(user_id=user.id).count()
    if pos_count == 0:
        return jsonify({
            "ok":     False,
            "stage":  "positions_check",
            "user":   user_info,
            "reason": "user has 0 positions — run_for_user returns None early "
                      "(line 992-995). No memo is generated.",
            "fix":    "Add at least one Position row for this user, or pass "
                      "user_id of a user with positions.",
        })

    svc = WeeklyMemoService()
    stages = {"positions_count": pos_count}

    # ── 3. generate_for_user ────────────────────────────────────────────
    try:
        data = svc.generate_for_user(user.id)
        stages["generate_for_user"] = {
            "ok":      True,
            "keys":    sorted(list(data.keys())) if isinstance(data, dict) else None,
            "type":    type(data).__name__,
        }
    except Exception as exc:
        return jsonify({
            "ok":     False,
            "stage":  "generate_for_user",
            "user":   user_info,
            "stages": stages,
            "error":  _err_dict(exc),
        })

    # ── 4. render_pdf (the actual production path) ──────────────────────
    pdf_bytes = None
    render_error = None
    try:
        pdf_bytes = svc.render_pdf(data)
    except Exception as exc:
        render_error = _err_dict(exc)

    if pdf_bytes is None:
        # render_pdf swallows exceptions and returns None on failure (see
        # weekly_memo_service.py:824-826). Re-execute the inner steps with
        # exceptions exposed so we know WHY None was returned.
        deeper = {}
        try:
            from services.artifacts.weekly_memo_service import (
                _try_import_weasyprint,
            )
            HTML = _try_import_weasyprint()
            deeper["weasyprint_imported"] = HTML is not None
            if HTML is not None:
                try:
                    html_str = svc.render_pdf_html(data)
                    deeper["pdf_html_chars"] = len(html_str)
                    deeper["pdf_html_starts_with_doctype"] = (
                        html_str.lstrip().lower().startswith("<!doctype")
                        or html_str.lstrip().lower().startswith("<html")
                    )
                    try:
                        pdf2 = HTML(string=html_str).write_pdf()
                        deeper["direct_write_pdf_bytes"] = len(pdf2 or b"")
                    except Exception as exc:
                        deeper["direct_write_pdf_error"] = _err_dict(exc)
                except Exception as exc:
                    deeper["render_pdf_html_error"] = _err_dict(exc)
        except Exception as exc:
            deeper["bootstrap_error"] = str(exc)

        return jsonify({
            "ok":             False,
            "stage":          "render_pdf",
            "user":           user_info,
            "stages":         stages,
            "render_pdf_returned_None": True,
            "outer_exception": render_error,  # may be None — render_pdf catches internally
            "deep_probe":     deeper,
            "interpretation": "render_pdf returned None for this user. Check "
                              "deep_probe.{render_pdf_html_error|direct_write_pdf_error} "
                              "for the underlying exception.",
        })

    # ── 5. success path ─────────────────────────────────────────────────
    return jsonify({
        "ok":     True,
        "user":   user_info,
        "stages": stages,
        "render_pdf": {
            "bytes":              len(pdf_bytes),
            "starts_with_pdf_magic": pdf_bytes[:4] == b"%PDF",
        },
        "interpretation": "render_pdf produced bytes. If emails still ship "
                          "without an attachment, the bug is downstream "
                          "(send_email or SendGrid delivery).",
    })


# ═══════ STATS / ARCHIVE — server-side aggregation ═══════
# Frontend hooks (lib/hooks.ts:802 useArtifactStats, useArtifactArchive)
# previously fell back to client-side derivation when these endpoints
# 404'd. Adding the server-side path so the network log stops showing
# 404s and the dashboard can render before all artifacts are downloaded.

@artifacts_bp.route("/stats", methods=["GET"])
@api_auth
def artifacts_stats():
    """Aggregate stats for /reports v2 hero. Mirrors `deriveArtifactStats`
    in lib/hooks.ts so the frontend can prefer server-side numbers when
    available and silently fall back when not.

    Returns:
        {
          total, countYtd, countMemos, countBriefs, countBragCards,
          byType: {<type>: <count>, ...},
          nextScheduled: null,                  # populated when scheduler exposes it
          latestIndexedAt: ISO-8601 | null,
        }
    """
    rows = (
        Artifact.query
        .filter_by(user_id=current_user.id)
        .all()
    )
    year_start = datetime(datetime.now(timezone.utc).year, 1, 1)
    by_type: dict[str, int] = {}
    count_ytd = 0
    latest: datetime | None = None
    for a in rows:
        by_type[a.type] = by_type.get(a.type, 0) + 1
        sent_at = a.sent_at
        if sent_at:
            if sent_at >= year_start:
                count_ytd += 1
            if latest is None or sent_at > latest:
                latest = sent_at
    return jsonify({
        "total":           len(rows),
        "countYtd":        count_ytd,
        "countMemos":      by_type.get("weekly_memo", 0),
        "countBriefs":     by_type.get("earnings_prebrief", 0),
        # 2026-05-02: include both monthly_brag (auto monthly digest) and
        # brag_card (one-off cards) — /reports counter previously dropped
        # brag_card rows so /home (total) and /reports (brag count)
        # disagreed by N.
        "countBragCards":  by_type.get("monthly_brag", 0) + by_type.get("brag_card", 0),
        "byType":          by_type,
        "nextScheduled":   None,
        "latestIndexedAt": latest.isoformat() if latest else None,
    })


@artifacts_bp.route("/by-month", methods=["GET"])
@api_auth
def artifacts_by_month():
    """Server-side groupby for the year timeline. Frontend falls back to
    `deriveArchiveMonths(artifacts)` when this 404s — the response shape
    matches `ArtifactArchiveMonth` in lib/hooks.ts.

    Query:
        month — "YYYY-MM" required.

    Returns:
        { month, artifacts: [...], count }
    """
    month_str = (request.args.get("month") or "").strip()
    try:
        year, mon = (int(p) for p in month_str.split("-", 1))
        start = datetime(year, mon, 1)
        end = datetime(year + (1 if mon == 12 else 0),
                       1 if mon == 12 else mon + 1, 1)
    except (ValueError, TypeError):
        return api_error(en="month must be YYYY-MM", kr="month는 YYYY-MM 형식이어야 합니다.", code="INVALID_MONTH_FORMAT", status=400)

    rows = (
        Artifact.query
        .filter(Artifact.user_id == current_user.id,
                Artifact.sent_at >= start,
                Artifact.sent_at < end)
        .order_by(Artifact.sent_at.desc())
        .all()
    )
    return jsonify({
        "month":     month_str,
        "artifacts": [r.to_dict() for r in rows],
        "count":     len(rows),
    })


# ════════════════════════════════════════════════════════════════════════════
# Living Mirror — persona capstone (선언 → 행동 → 궤적), on-demand only.
#
# On-demand only: no APScheduler hook is registered for this artefact. The
# CEO framing precedes any auto-send, so generation always requires an
# explicit authenticated user action. ``@require_tier("premium")`` opens to
# all authenticated users during the free launch (LAUNCH_FREE_ALL_TIERS →
# effective_tier="premium"; see models/user.py), and re-gates automatically
# when the Stage-1 paywall flag flips — no code change here.
# ════════════════════════════════════════════════════════════════════════════
from services.artifacts.living_mirror_service import (  # noqa: E402
    LivingMirrorService,
)


@artifacts_bp.route("/living-mirror/generate", methods=["POST"])
@api_auth
@require_tier("premium")
@artifact_rate_limit
def living_mirror_generate():
    """Build + persist the caller's Living Mirror. Returns { ok, id, data }."""
    svc = LivingMirrorService()
    try:
        data = svc.generate_for_user(current_user.id)
    except ValueError:
        return api_error(en="Bad request", kr="잘못된 요청입니다.",
                         code="BAD_REQUEST_400", status=400)
    except Exception as exc:
        current_app.logger.error("living_mirror generate failed: %s", exc)
        return api_error(en="Generation failed (internal error)",
                         kr="생성에 실패했습니다.",
                         code="GENERATION_INTERNAL_ERROR", status=500)

    try:
        pdf_bytes = svc.render_pdf(data)
        artefact = svc.persist(current_user.id, data, pdf_bytes)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("living_mirror persist failed: %s", exc)
        return api_error(en="Persist failed (internal error)",
                         kr="저장에 실패했습니다.",
                         code="PERSIST_INTERNAL_ERROR", status=500)

    return jsonify({"ok": True, "id": artefact.id, "data": artefact.data_json or {}})


@artifacts_bp.route("/living-mirror/preview/<int:artifact_id>", methods=["GET"])
@api_auth
@require_tier("premium")
def living_mirror_preview(artifact_id: int):
    """Return the persisted payload + rendered HTML. Owner-only."""
    artefact = db.session.get(Artifact, artifact_id)
    if (artefact is None or artefact.user_id != current_user.id
            or artefact.type != "living_mirror"):
        return api_error(en="Mirror not found", kr="리포트를 찾을 수 없습니다.",
                         code="MIRROR_NOT_FOUND", status=404)

    svc = LivingMirrorService()
    try:
        html = svc.render_html(artefact.data_json or {})
    except Exception as exc:
        current_app.logger.error("living_mirror preview render failed: %s", exc)
        return api_error(en="Render failed (internal error)",
                         kr="렌더링에 실패했습니다.",
                         code="RENDER_INTERNAL_ERROR", status=500)

    return jsonify({
        "ok":   True,
        "id":   artefact.id,
        "data": artefact.data_json or {},
        "html": html,
    })


@artifacts_bp.route("/living-mirror/download/<int:artifact_id>", methods=["GET"])
@api_auth
@require_tier("premium")
def living_mirror_download(artifact_id: int):
    """Stream the persisted Living Mirror PDF. Owner-only."""
    artefact = db.session.get(Artifact, artifact_id)
    if (artefact is None or artefact.user_id != current_user.id
            or artefact.type != "living_mirror"):
        return api_error(en="Mirror not found", kr="리포트를 찾을 수 없습니다.",
                         code="MIRROR_NOT_FOUND", status=404)

    if not artefact.pdf_path:
        return api_error(en="PDF unavailable for this report",
                         kr="이 리포트의 PDF가 아직 준비되지 않았습니다.",
                         code="PDF_NOT_RENDERED", status=410)

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return api_error(en="PDF file missing on disk",
                         kr="PDF 파일이 서버에 존재하지 않습니다.",
                         code="PDF_FILE_MISSING", status=410)

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return send_file(
        str(pdf_file),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"living_mirror_{artefact.id}.pdf",
    )
