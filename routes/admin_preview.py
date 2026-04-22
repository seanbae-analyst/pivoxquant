"""Admin-only Artifact Preview — CEO (배상현) can preview every PDF/email
template rendered with fictional sample data.

Routes (all under /api/admin/artifacts):

    GET /api/admin/artifacts/list
        → catalog metadata for the admin UI grid (no auth-sensitive data)

    GET /api/admin/artifacts/preview/<artifact_type>?format=html|pdf|email|png
        → rendered artefact. Default: html.
        • html  → Content-Type: text/html (browser preview)
        • pdf   → application/pdf (inline if `?download=0`, attachment otherwise)
        • email → text/html (the email body template)
        • png   → image/png (monthly_brag only)

Access control
--------------
Gated by the same ``ADMIN_EMAILS`` env var as ``routes.admin_fmp``. Non-admin
sessions — and unauthenticated requests — receive 404 (we deliberately hide
the route's existence from non-admins rather than 403 to keep the path quiet).

This route NEVER touches the DB or real user data. All renders flow from
``services.artifacts.sample_data`` (fictional portfolio). Safe to hammer.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

from flask import Blueprint, Response, abort, jsonify, request
from flask_login import current_user, login_required

from services.artifacts import sample_data
from services.artifacts.sample_data import CATALOG

logger = logging.getLogger(__name__)

admin_preview_bp = Blueprint("admin_preview", __name__, url_prefix="/api/admin/artifacts")


# ── access control ───────────────────────────────────────────────────────────


def _admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _is_admin() -> bool:
    """True when the current session belongs to an admin email.

    Fails closed: if ``ADMIN_EMAILS`` is unset, no one is admin.
    """
    admins = _admin_emails()
    if not admins:
        return False
    if not getattr(current_user, "is_authenticated", False):
        return False
    email = (getattr(current_user, "email", "") or "").lower()
    return email in admins


def _require_admin_or_404() -> None:
    """Abort with 404 (not 403) for non-admins so the route appears
    to not exist. Spec: '일반 유저는 404'."""
    if not _is_admin():
        abort(404)


# ── render dispatchers ───────────────────────────────────────────────────────
#
# Each service has a slightly different surface. We normalize here so the
# route body stays tidy.


def _render_weekly_memo(fmt: str) -> tuple[bytes | str, str]:
    from services.artifacts.weekly_memo_service import WeeklyMemoService
    svc = WeeklyMemoService()
    data = sample_data.sample_weekly_memo()
    if fmt == "pdf":
        pdf = svc.render_pdf(data)
        if pdf is None:
            # WeasyPrint unavailable — fall back to HTML so the admin sees
            # something useful rather than a 500.
            return svc.render_pdf_html(data), "text/html; charset=utf-8"
        return pdf, "application/pdf"
    if fmt == "email":
        return svc.render_html(data), "text/html; charset=utf-8"
    # html (default) → full PDF html for richer preview
    return svc.render_pdf_html(data), "text/html; charset=utf-8"


def _render_earnings_prebrief(fmt: str) -> tuple[bytes | str, str]:
    from services.artifacts.earnings_prebrief_service import EarningsPreBriefService
    svc = EarningsPreBriefService()
    data = sample_data.sample_earnings_prebrief()
    if fmt == "pdf":
        pdf = svc.render_pdf(data)
        if pdf is None:
            return svc.render_pdf_html(data), "text/html; charset=utf-8"
        return pdf, "application/pdf"
    if fmt == "email":
        return svc.render_email_html(data), "text/html; charset=utf-8"
    return svc.render_pdf_html(data), "text/html; charset=utf-8"


def _render_standard(service_path: str, class_name: str,
                     data_builder: Callable[[], dict[str, Any]],
                     fmt: str) -> tuple[bytes | str, str]:
    """Shared implementation for services exposing `render_html(data)` +
    optional `render_pdf(data)`."""
    mod = __import__(service_path, fromlist=[class_name])
    cls = getattr(mod, class_name)
    svc = cls()
    data = data_builder()
    if fmt == "pdf" and hasattr(svc, "render_pdf"):
        pdf = svc.render_pdf(data)
        if pdf is None:
            return svc.render_html(data), "text/html; charset=utf-8"
        return pdf, "application/pdf"
    return svc.render_html(data), "text/html; charset=utf-8"


def _render_brag_card(fmt: str) -> tuple[bytes | str, str]:
    from services.artifacts.brag_card_service import BragCardService
    svc = BragCardService()
    data = sample_data.sample_brag_card()
    if fmt == "email":
        return svc.render_email_html(data), "text/html; charset=utf-8"
    return svc.render_html(data), "text/html; charset=utf-8"


def _render_monthly_brag(fmt: str) -> tuple[bytes | str, str]:
    from services.artifacts.monthly_brag_service import MonthlyBragService
    svc = MonthlyBragService()
    data = sample_data.sample_monthly_brag()
    if fmt == "email":
        try:
            return svc.render_email_html(data), "text/html; charset=utf-8"
        except Exception as exc:
            logger.debug("monthly_brag email render failed: %s", exc)
            return _fallback_unavailable("monthly_brag email template missing"), "text/html; charset=utf-8"
    # png by default
    png = svc.render_png(data)
    if png is None:
        return _fallback_unavailable("Pillow unavailable — PNG cannot be rendered in this environment"), "text/html; charset=utf-8"
    return png, "image/png"


def _fallback_unavailable(msg: str) -> str:
    return (
        "<!doctype html><html><body style='font-family:sans-serif;padding:32px;"
        "background:#fafafa;color:#374151;'>"
        "<h1 style='color:#b91c1c;'>Preview unavailable</h1>"
        f"<p>{msg}</p></body></html>"
    )


# Registry: artifact type → render fn (fmt) → (body, mimetype)
_RENDER: dict[str, Callable[[str], tuple[bytes | str, str]]] = {
    "weekly_memo":            _render_weekly_memo,
    "earnings_prebrief":      _render_earnings_prebrief,
    "monthly_finance":        lambda fmt: _render_standard(
        "services.artifacts.monthly_finance_service",
        "MonthlyFinanceService",
        sample_data.sample_monthly_finance, fmt),
    "risk_board":             lambda fmt: _render_standard(
        "services.artifacts.risk_board_service",
        "RiskBoardService",
        sample_data.sample_risk_board, fmt),
    "quarterly_self_report":  lambda fmt: _render_standard(
        "services.artifacts.quarterly_self_report_service",
        "QuarterlySelfReportService",
        sample_data.sample_quarterly_self_report, fmt),
    "year_end_letter":        lambda fmt: _render_standard(
        "services.artifacts.year_end_letter_service",
        "YearEndLetterService",
        sample_data.sample_year_end_letter, fmt),
    "capital_allocation":     lambda fmt: _render_standard(
        "services.artifacts.capital_allocation_service",
        "CapitalAllocationService",
        sample_data.sample_capital_allocation, fmt),
    "insider_mirror":         lambda fmt: _render_standard(
        "services.artifacts.insider_mirror_service",
        "InsiderMirrorService",
        sample_data.sample_insider_mirror, fmt),
    "self_audit":             lambda fmt: _render_standard(
        "services.artifacts.self_audit_service",
        "SelfAuditService",
        sample_data.sample_self_audit, fmt),
    "burn_rate":              lambda fmt: _render_standard(
        "services.artifacts.burn_rate_service",
        "BurnRateService",
        sample_data.sample_burn_rate, fmt),
    "credit_rating":          lambda fmt: _render_standard(
        "services.artifacts.credit_rating_service",
        "CreditRatingService",
        sample_data.sample_credit_rating, fmt),
    "dividend_income":        lambda fmt: _render_standard(
        "services.artifacts.dividend_income_service",
        "DividendIncomeService",
        sample_data.sample_dividend_income, fmt),
    "portfolio_segment":      lambda fmt: _render_standard(
        "services.artifacts.portfolio_segment_service",
        "PortfolioSegmentService",
        sample_data.sample_portfolio_segment, fmt),
    "kpi_dashboard":          lambda fmt: _render_standard(
        "services.artifacts.kpi_dashboard_service",
        "KPIDashboardService",
        sample_data.sample_kpi_dashboard, fmt),
    "dd_checklist":           lambda fmt: _render_standard(
        "services.artifacts.dd_checklist_service",
        "DDChecklistService",
        sample_data.sample_dd_checklist, fmt),
    "brag_card":              _render_brag_card,
    "monthly_brag":           _render_monthly_brag,
}


# ── endpoints ────────────────────────────────────────────────────────────────


@admin_preview_bp.route("/list", methods=["GET"])
@login_required
def list_catalog():
    """Return the artifact catalog for the admin preview UI.

    Silent 404 for non-admins so the route appears nonexistent.
    """
    _require_admin_or_404()
    return jsonify({
        "artifacts": CATALOG,
        "count":     len(CATALOG),
    }), 200


@admin_preview_bp.route("/preview/<artifact_type>", methods=["GET"])
@login_required
def preview(artifact_type: str):
    """Render a single artifact with fictional sample data.

    Query params:
        format   — html | pdf | email | png  (default: html)
        download — 1 to force Content-Disposition=attachment, else inline
    """
    _require_admin_or_404()

    fmt = (request.args.get("format") or "html").lower()
    if fmt not in {"html", "pdf", "email", "png"}:
        return jsonify({"error": f"unknown format '{fmt}'"}), 400

    render = _RENDER.get(artifact_type)
    if render is None:
        return jsonify({"error": f"unknown artifact type '{artifact_type}'"}), 404

    try:
        body, mimetype = render(fmt)
    except KeyError as exc:
        return jsonify({"error": f"sample data missing: {exc}"}), 500
    except Exception as exc:
        logger.exception("preview render failed for %s (%s)", artifact_type, fmt)
        return jsonify({"error": f"render failed: {exc}"}), 500

    # Disposition: attachment only when explicitly requested (PDF download).
    headers: dict[str, str] = {
        # Admin-only preview surface — never cache in shared caches.
        "Cache-Control":        "no-store, must-revalidate",
        "X-Robots-Tag":         "noindex, nofollow",
        "X-Content-Type-Options": "nosniff",
    }
    download = request.args.get("download") == "1"
    if download:
        ext = {
            "application/pdf":            "pdf",
            "text/html; charset=utf-8":   "html",
            "image/png":                  "png",
        }.get(mimetype, "bin")
        fname = f"{artifact_type}_preview.{ext}"
        headers["Content-Disposition"] = f'attachment; filename="{fname}"'

    return Response(body, mimetype=mimetype, headers=headers)
