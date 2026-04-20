"""Artifacts API — Weekly Investor Memo, Monthly Brag Card, + future artefact classes.

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
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file
from flask_login import current_user

from extensions import db
from models import Artifact
from services.artifacts.monthly_brag_service import MonthlyBragService
from services.artifacts.weekly_memo_service import WeeklyMemoService
from services.name_resolver import resolve_stock_name

from .decorators import api_auth, require_tier

artifacts_bp = Blueprint("artifacts", __name__, url_prefix="/api/artifacts")


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
    "morning_brief":     ("application/pdf", "pdf"),
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
        return None
    # Fall-through: try to parse as ISO date ("2026-01-01")
    try:
        return datetime.fromisoformat(since)
    except ValueError:
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
        return jsonify({"error": "limit must be an integer"}), 400
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
        return jsonify({"error": "Artifact not found"}), 404

    return jsonify({
        "ok":       True,
        "id":       artefact.id,
        "type":     artefact.type,
        "title":    artefact.title,
        "data":     artefact.data_json or {},
        "has_file": bool(artefact.pdf_path),
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
        return jsonify({"error": "Artifact not found"}), 404

    meta = _ARTIFACT_DOWNLOAD_META.get(artefact.type)
    if not meta:
        return jsonify({
            "error": f"Download not supported for type={artefact.type}",
            "code":  "TYPE_NOT_DOWNLOADABLE",
        }), 415
    mimetype, ext = meta

    if not artefact.pdf_path:
        return jsonify({
            "error": "File unavailable for this artifact",
            "code":  "FILE_NOT_RENDERED",
        }), 410

    file_path = Path(artefact.pdf_path)
    if not file_path.exists():
        return jsonify({
            "error": "File missing on disk",
            "code":  "FILE_MISSING",
        }), 410

    # Mark opened on first successful download — same convention as the
    # per-type endpoints above.
    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return send_file(
        str(file_path),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{artefact.type}_{artefact.id}.{ext}",
    )


@artifacts_bp.route("/<int:artifact_id>/read", methods=["POST"])
@api_auth
def artifacts_mark_read(artifact_id: int):
    """Mark an artifact as read. Owner-only. Idempotent."""
    artefact = db.session.get(Artifact, artifact_id)
    if not artefact or artefact.user_id != current_user.id:
        return jsonify({"error": "Artifact not found"}), 404

    if not artefact.opened_at:
        artefact.opened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.warning(
                "markRead failed for artefact %s: %s", artifact_id, exc,
            )
            return jsonify({"error": "Could not mark as read"}), 500

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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({
        "ok":   True,
        "data": data,
        "html": html,
    })


@artifacts_bp.route("/weekly-memo/download/<int:memo_id>", methods=["GET"])
@api_auth
@require_tier("pro")
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
        return jsonify({"error": "Memo not found"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this memo",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def weekly_memo_trigger():
    """Manual trigger for the Sunday cron. Admin-only.

    Gated in layers:
      1. `DEV_LOGIN_SECRET` env must be set (i.e. dev/staging).
      2. Caller must pass `X-Admin-Secret` header equal to it.
    This keeps the route effectively 404 in prod (where we leave
    `DEV_LOGIN_SECRET` unset — same convention as routes/dev_auth.py).
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_date")
    target_date = None
    if target_str:
        try:
            target_date = date.fromisoformat(target_str)
        except ValueError:
            return jsonify({"error": "invalid target_date (expected YYYY-MM-DD)"}), 400

    try:
        summary = WeeklyMemoService().run_weekly(target_date=target_date)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("weekly memo manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


# ── Monthly Brag Card ────────────────────────────────────────────────────────

@artifacts_bp.route("/monthly-brag/preview", methods=["POST", "GET"])
@api_auth
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
            return jsonify({"error": "invalid month (expected YYYY-MM-DD)"}), 400

    anon_override = body.get("anonymous")
    if anon_override is not None and not isinstance(anon_override, bool):
        return jsonify({"error": "anonymous must be a boolean"}), 400

    try:
        svc = MonthlyBragService()
        data = svc.generate_for_user(
            current_user.id, month=month_date,
            anonymous=anon_override,
        )
        png_bytes = svc.render_png(data)
    except Exception as exc:
        current_app.logger.error("monthly brag preview failed: %s", exc)
        return jsonify({"error": f"Preview failed: {exc}"}), 500

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
        return jsonify({"error": "Brag card not found"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PNG unavailable for this brag card",
            "code":  "PNG_NOT_RENDERED",
        }), 410

    png_file = Path(artefact.pdf_path)
    if not png_file.exists():
        return jsonify({
            "error": "PNG file missing on disk",
            "code":  "PNG_FILE_MISSING",
        }), 410

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
        return jsonify({"error": "Brag card not found"}), 404

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
        "og:image":        f"{share_domain}/api/artifacts/monthly-brag/download/{artefact.id}",
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
@api_auth
def monthly_brag_trigger():
    """Manual trigger for the monthly cron. Admin-only.

    Same gating layers as `/weekly-memo/trigger`:
      1. `DEV_LOGIN_SECRET` env must be set (i.e. dev/staging).
      2. Caller must pass `X-Admin-Secret` header equal to it.
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(str(target_str))
        except ValueError:
            return jsonify({
                "error": "invalid target_month (expected YYYY-MM-DD)",
            }), 400

    try:
        summary = MonthlyBragService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("monthly brag manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
            return jsonify({"error": "invalid month (expected YYYY-MM-DD)"}), 400

    anon_override = body.get("anonymous")
    if anon_override is not None and not isinstance(anon_override, bool):
        return jsonify({"error": "anonymous must be a boolean"}), 400

    try:
        svc = BragCardService()
        data = svc.generate_for_user(
            current_user.id, month=month_date, anonymous=anon_override,
        )
        html = svc.render_html(data)
        png_bytes = svc.render_png(html)
    except Exception as exc:
        current_app.logger.error("brag card preview failed: %s", exc)
        return jsonify({"error": f"Preview failed: {exc}"}), 500

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
        return jsonify({"error": "Brag card not found"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PNG unavailable for this brag card",
            "code":  "PNG_NOT_RENDERED",
        }), 410

    png_file = Path(artefact.pdf_path)
    if not png_file.exists():
        return jsonify({
            "error": "PNG file missing on disk",
            "code":  "PNG_FILE_MISSING",
        }), 410

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


@artifacts_bp.route("/brag-card/share/<string:share_token>", methods=["GET"])
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
        return jsonify({"error": "Invalid share token"}), 404

    artefact = (
        Artifact.query
        .filter_by(type="brag_card", share_token=share_token)
        .first()
    )
    if not artefact:
        return jsonify({"error": "Card not found"}), 404

    data = dict(artefact.data_json or {})
    data.setdefault("share_token", share_token)

    # Render card HTML. We intentionally render the *card* (not the email)
    # so mobile users see the polished 9:16 image layout.
    svc = BragCardService()
    html = svc.render_html(data)

    # Inject OG meta so crawlers unfurl correctly. Hack: inject into <head>.
    share_url = svc.get_share_url(artefact.id)
    png_endpoint = (f"{request.host_url.rstrip('/')}"
                    f"/api/artifacts/brag-card/download/{artefact.id}")
    ret = data.get("return_pct")
    ret_str = "—" if ret is None else (f"+{ret:.1f}%" if ret >= 0
                                       else f"{ret:.1f}%")
    og_block = (
        f'<meta property="og:title" content="{data.get("month_label","")} '
        f'{ret_str} — PivoxQuant">'
        f'<meta property="og:description" content="월간 브래그 카드 — '
        f'AI + Quant 리서치 툴">'
        f'<meta property="og:image" content="{png_endpoint}">'
        f'<meta property="og:url" content="{share_url}">'
        f'<meta name="twitter:card" content="summary_large_image">'
    )
    if "</head>" in html:
        html = html.replace("</head>", f"{og_block}</head>", 1)

    resp = Response(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@artifacts_bp.route("/brag-card/trigger", methods=["POST"])
@api_auth
def brag_card_trigger():
    """Manual trigger for the monthly cron. Admin-only (DEV_LOGIN_SECRET)."""
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(str(target_str))
        except ValueError:
            return jsonify({
                "error": "invalid target_month (expected YYYY-MM-DD)",
            }), 400

    try:
        summary = BragCardService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("brag card manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


@artifacts_bp.route("/brag-card/privacy", methods=["POST"])
@api_auth
def brag_card_privacy():
    """Toggle anonymous mode for brag cards.

    Body: { "privacy_mode": true|false }
    Sets `current_user.privacy_mode`. Future brag cards generated for
    this user will mask ticker names as "A 종목".
    """
    body = request.get_json(silent=True) or {}
    val = body.get("privacy_mode")
    if not isinstance(val, bool):
        return jsonify({"error": "privacy_mode must be a boolean"}), 400

    try:
        setattr(current_user, "privacy_mode", val)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(
            "privacy toggle failed for user %s: %s", current_user.id, exc,
        )
        return jsonify({"error": "Could not update privacy flag"}), 500

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
        return jsonify({"error": "hours must be an integer"}), 400
    hours = max(1, min(hours, 336))

    svc = EarningsPrebriefService()
    try:
        all_rows = svc.get_upcoming_earnings(hours=hours)
    except Exception as exc:
        current_app.logger.error("earnings upcoming fetch failed: %s", exc)
        return jsonify({"error": f"Upcoming fetch failed: {exc}"}), 500

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
        return jsonify({"error": "invalid ticker"}), 400

    svc = EarningsPrebriefService()
    try:
        data = svc.generate_for_user(current_user.id, ticker)
    except ValueError as exc:
        # user_id lookup failed — shouldn't happen post-auth but defend
        current_app.logger.warning("prebrief preview value error: %s", exc)
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        current_app.logger.error("prebrief preview failed: %s", exc)
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    if data is None:
        return jsonify({
            "error": "No upcoming earnings found for this ticker",
            "code":  "NO_UPCOMING_EARNINGS",
        }), 404

    try:
        html = svc.render_email_html(data)
    except Exception as exc:
        current_app.logger.warning("prebrief email render failed: %s", exc)
        html = ""

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/earnings-prebrief/download/<int:brief_id>", methods=["GET"])
@api_auth
@require_tier("pro")
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
        return jsonify({"error": "Pre-Brief not found"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this pre-brief",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def earnings_prebrief_trigger():
    """Manual trigger for the 15-min scan. Admin-only.

    Gated (identical pattern to the weekly / monthly triggers):
      1. `DEV_LOGIN_SECRET` env must be set (i.e. dev/staging).
      2. Caller must pass `X-Admin-Secret` header equal to it.

    Body (optional): { "send": false } to preview without emailing.
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    send = body.get("send", True)
    if not isinstance(send, bool):
        return jsonify({"error": "send must be a boolean"}), 400

    try:
        summary = EarningsPrebriefService().run_scan(send=send)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("prebrief manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


# ═══════ KPI DASHBOARD (Pro+) ═══════
# Daily 08:00 KST 5-metric email. Short HTML, no PDF. See
# services/artifacts/kpi_dashboard_service.py for KPI definitions.

from services.artifacts.kpi_dashboard_service import (  # noqa: E402
    KPIDashboardService,
)


@artifacts_bp.route("/kpi-dashboard/preview", methods=["GET"])
@api_auth
@require_tier("pro")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/kpi-dashboard/trigger", methods=["POST"])
@api_auth
def kpi_dashboard_trigger():
    """Manual trigger for the daily KPI cron. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set.
      2. Caller must pass `X-Admin-Secret` header equal to it.
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_date")
    target_date = None
    if target_str:
        try:
            target_date = date.fromisoformat(target_str)
        except ValueError:
            return jsonify({"error": "invalid target_date (expected YYYY-MM-DD)"}), 400

    try:
        summary = KPIDashboardService().run_daily(target_date=target_date)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("kpi dashboard manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
@require_tier("premium")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/self-audit/download", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": "No Self Audit available yet",
                        "code": "NO_AUDIT"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this audit",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def self_audit_trigger():
    """Manual trigger for the quarterly cron. Admin-only.

    Gating — identical to weekly_memo/trigger.
    Body (optional): { "quarter_end": "2026-03-31" } to pin the audit
    window. Defaults to today (which maps to whichever quarter the
    `_quarter_bounds` helper resolves).
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    qe_str = body.get("quarter_end")
    quarter_end = None
    if qe_str:
        try:
            quarter_end = date.fromisoformat(qe_str)
        except ValueError:
            return jsonify({"error": "invalid quarter_end (expected YYYY-MM-DD)"}), 400

    try:
        summary = SelfAuditService().run_quarterly(quarter_end=quarter_end)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("self audit manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
        return jsonify({"error": f"Pending fetch failed: {exc}"}), 500

    return jsonify({"ok": True, "count": len(pending), "pending": pending})


@artifacts_bp.route("/dd-checklist/submit", methods=["POST"])
@api_auth
@require_tier("pro")
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
        return jsonify({"error": "position_id must be an integer"}), 400

    bool_fields = ("financials_checked", "moat_checked", "management_checked",
                   "valuation_checked", "risks_checked")
    for f in bool_fields:
        if not isinstance(body.get(f), bool):
            return jsonify({"error": f"{f} must be a boolean"}), 400

    note = body.get("note")
    if note is not None and not isinstance(note, str):
        return jsonify({"error": "note must be a string"}), 400
    if isinstance(note, str) and len(note) > 500:
        return jsonify({"error": "note exceeds 500 characters"}), 400

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
        return jsonify({"error": str(exc)}), 404
    except PermissionError:
        return jsonify({"error": "Position does not belong to you"}), 403
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("dd submit failed for user %s: %s",
                                 current_user.id, exc)
        return jsonify({"error": f"Submit failed: {exc}"}), 500

    return jsonify({"ok": True, "dd_check": row.to_dict()})


@artifacts_bp.route("/dd-checklist/trigger", methods=["POST"])
@api_auth
def dd_checklist_trigger():
    """Manual trigger for the T+3 cron. Admin-only. Same gating as
    weekly_memo/trigger."""
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    try:
        summary = DDChecklistService().run_daily()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("dd manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
@require_tier("pro")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/burn-rate/download", methods=["GET"])
@api_auth
@require_tier("pro")
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
        return jsonify({"error": "No Burn Rate report available yet",
                        "code": "NO_REPORT"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this report",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def burn_rate_trigger():
    """Manual trigger for the monthly cron. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set.
      2. Caller must pass `X-Admin-Secret` header equal to it.
    Body (optional): { "target_month": "2026-04-01" } to pin the run
    date (used by `_prev_month_bounds` to back-out the prior month).
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(target_str)
        except ValueError:
            return jsonify({"error": "invalid target_month (expected YYYY-MM-DD)"}), 400

    try:
        summary = BurnRateService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("burn_rate manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


# ═══════ CREDIT RATING SELF-ASSESSMENT (Pro+) ═══════
# Monthly 15th 09:00 KST — 1-page HTML email with portfolio self-rating.

from services.artifacts.credit_rating_service import (  # noqa: E402
    CreditRatingService,
)


@artifacts_bp.route("/credit-rating/preview", methods=["GET"])
@api_auth
@require_tier("pro")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/credit-rating/trigger", methods=["POST"])
@api_auth
def credit_rating_trigger():
    """Manual trigger for the monthly cron. Admin-only. Same gating as
    weekly_memo/trigger."""
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    as_of_str = body.get("as_of")
    as_of = None
    if as_of_str:
        try:
            as_of = date.fromisoformat(as_of_str)
        except ValueError:
            return jsonify({"error": "invalid as_of (expected YYYY-MM-DD)"}), 400

    try:
        summary = CreditRatingService().run_monthly(as_of=as_of)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("credit_rating manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


# ═══════ DIVIDEND INCOME STATEMENT (Premium) ═══════
# Monthly 3-page PDF fired 1st of month 10:00 KST. See
# services/artifacts/dividend_income_service.py.

from services.artifacts.dividend_income_service import (  # noqa: E402
    DividendIncomeService,
)


@artifacts_bp.route("/dividend-income/preview", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/dividend-income/download", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": "No Dividend Statement available yet",
                        "code": "NO_STATEMENT"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this statement",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def dividend_income_trigger():
    """Manual trigger for the monthly dividend cron. Admin-only
    (DEV_LOGIN_SECRET + X-Admin-Secret header — same pattern as the
    weekly_memo/trigger)."""
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(target_str)
        except ValueError:
            return jsonify({"error": "invalid target_month (expected YYYY-MM-DD)"}), 400

    try:
        summary = DividendIncomeService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("dividend_income manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

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
        return jsonify({"error": "No Finance Report available yet",
                        "code": "NO_REPORT"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this report",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def monthly_finance_trigger():
    """Manual trigger for the monthly finance cron. Admin-only."""
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_str = body.get("target_month")
    target_month = None
    if target_str:
        try:
            target_month = date.fromisoformat(target_str)
        except ValueError:
            return jsonify({"error": "invalid target_month (expected YYYY-MM-DD)"}), 400

    try:
        summary = MonthlyFinanceService().run_monthly(target_month=target_month)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("monthly_finance manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


# ═══════ RISK BOARD MEETING DECK (Premium) ═══════
# Monthly 8-page PDF (day 15 09:30 KST) + event-driven VIX spike edition.
# See services/artifacts/risk_board_service.py for the 7-layer contract.

from services.artifacts.risk_board_service import (  # noqa: E402
    RiskBoardService,
)


@artifacts_bp.route("/risk-board/preview", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/risk-board/download", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": "No Risk Board deck available yet",
                        "code": "NO_DECK"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this deck",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def risk_board_trigger():
    """Manual trigger for the Risk Board deck. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set.
      2. Caller must pass `X-Admin-Secret` header equal to it.

    Body (optional): { "trigger": "monthly" | "vix_spike" }.
    Default: "monthly". `vix_spike` bypasses the threshold check and
    fires a deck to every Premium user (for QA).
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    trigger = (body.get("trigger") or "monthly").strip().lower()
    if trigger not in ("monthly", "vix_spike"):
        return jsonify({"error": "trigger must be 'monthly' or 'vix_spike'"}), 400

    svc = RiskBoardService()
    try:
        if trigger == "monthly":
            summary = svc.run_monthly()
        else:
            # Force-fire path: fan out to every premium user regardless of
            # the persistent VIX state. Useful for QA; protected by admin
            # secret above.
            from models import User as _User
            paid = (
                _User.query
                .filter(_User.subscription_tier.in_(["premium", "elite"]))
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
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


# ═══════ PORTFOLIO SEGMENT REPORT (Premium) ═══════
# Quarterly 4-page PDF (1/7, 4/7, 7/7, 10/7 @ 10:00 KST). Sector / Region /
# Style breakdown — see services/artifacts/portfolio_segment_service.py.

from services.artifacts.portfolio_segment_service import (  # noqa: E402
    PortfolioSegmentService,
)


@artifacts_bp.route("/portfolio-segment/preview", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/portfolio-segment/download", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": "No Portfolio Segment report available yet",
                        "code": "NO_REPORT"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this report",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def portfolio_segment_trigger():
    """Manual trigger for the quarterly cron. Admin-only.

    Gating — identical to weekly_memo/trigger.
    Body (optional): { "quarter_end": "2026-03-31" } to pin the audit
    window. Defaults to today (which the `_quarter_bounds` helper maps
    to whichever quarter just closed).
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    qe_str = body.get("quarter_end")
    quarter_end = None
    if qe_str:
        try:
            quarter_end = date.fromisoformat(qe_str)
        except ValueError:
            return jsonify({
                "error": "invalid quarter_end (expected YYYY-MM-DD)",
            }), 400

    try:
        summary = PortfolioSegmentService().run_quarterly(quarter_end=quarter_end)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("portfolio_segment manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
        return jsonify({"error": "cash_amount is required"}), 400
    if scenarios is None:
        return jsonify({"error": "scenarios is required"}), 400

    svc = CapitalAllocationService()
    try:
        data = svc.calculate_for_user(
            current_user.id,
            cash_amount=cash_amount,
            scenarios=scenarios,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.error("capital_allocation calc failed: %s", exc)
        return jsonify({"error": f"Calculation failed: {exc}"}), 500

    try:
        pdf_bytes = svc.render_pdf(data)
        artefact = svc.persist(current_user.id, data, pdf_bytes)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("capital_allocation persist failed: %s", exc)
        return jsonify({"error": f"Persist failed: {exc}"}), 500

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
        return jsonify({"error": "Calculation not found"}), 404

    svc = CapitalAllocationService()
    try:
        html = svc.render_html(artefact.data_json or {})
    except Exception as exc:
        current_app.logger.error("capital_allocation preview render failed: %s", exc)
        return jsonify({"error": f"Render failed: {exc}"}), 500

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
        return jsonify({"error": "Calculation not found"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this calculation",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def capital_allocation_reminder_trigger():
    """Admin-only manual trigger for the quarterly reminder email.

    Note: this ONLY sends reminder emails. It never runs calculations
    autonomously — that's deliberate for the legal posture.
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    try:
        summary = CapitalAllocationService().send_quarterly_reminder()
    except Exception as exc:
        current_app.logger.error("capital_allocation reminder failed: %s", exc)
        return jsonify({"error": f"Reminder run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})


# ═══════ INSIDER TRANSACTION MIRROR (Premium, weekly) ═══════
# Weekly 3-page PDF (Mon 09:00 KST). SEC Form 4 + DART insider feed —
# strictly factual. See services/artifacts/insider_mirror_service.py.

from services.artifacts.insider_mirror_service import (  # noqa: E402
    InsiderMirrorService,
)


@artifacts_bp.route("/insider-mirror/preview", methods=["GET"])
@api_auth
@require_tier("premium")
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
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/insider-mirror/download", methods=["GET"])
@api_auth
@require_tier("premium")
def insider_mirror_download_latest():
    """Stream the caller's most recent Insider Mirror PDF. Owner-only."""
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="insider_mirror")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return jsonify({"error": "No Insider Mirror report available yet",
                        "code": "NO_REPORT"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this report",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def insider_mirror_trigger():
    """Admin-only manual trigger for the weekly insider mirror cron."""
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    anchor_str = body.get("anchor")
    anchor = None
    if anchor_str:
        try:
            anchor = date.fromisoformat(anchor_str)
        except ValueError:
            return jsonify({
                "error": "invalid anchor (expected YYYY-MM-DD)",
            }), 400

    try:
        summary = InsiderMirrorService().run_weekly(anchor=anchor)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("insider_mirror manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
            return jsonify({"error": "invalid year (expected YYYY)"}), 400

    try:
        svc = YearEndLetterService()
        data = svc.generate_for_user(current_user.id, target_year=target_year)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("year_end_letter preview failed: %s", exc)
        return jsonify({"error": f"Preview failed: {exc}"}), 500

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
        return jsonify({"error": "No Year-End Letter available yet",
                        "code": "NO_LETTER"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this letter",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def year_end_letter_trigger():
    """Manual trigger for the annual cron. Admin-only.

    Gating — same convention as weekly_memo/trigger:
      1. `DEV_LOGIN_SECRET` env must be set (dev/staging only).
      2. Caller must pass `X-Admin-Secret` header equal to it.

    Body (optional): { "target_year": 2026 }.
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    target_year = body.get("target_year")
    if target_year is not None:
        try:
            target_year = int(target_year)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid target_year (expected int)"}), 400

    try:
        summary = YearEndLetterService().run_annual(target_year=target_year)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("year_end_letter manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

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
@require_tier("premium")
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
            return jsonify({
                "error": "invalid quarter_end (expected YYYY-MM-DD)",
            }), 400

    try:
        svc = QuarterlySelfReportService()
        data = svc.generate_for_user(current_user.id, quarter_end=quarter_end)
        html = svc.render_html(data)
    except Exception as exc:
        current_app.logger.error("quarterly_self preview failed: %s", exc)
        return jsonify({"error": f"Preview failed: {exc}"}), 500

    return jsonify({"ok": True, "data": data, "html": html})


@artifacts_bp.route("/quarterly-self/download", methods=["GET"])
@api_auth
@require_tier("premium")
def quarterly_self_report_download_latest():
    """Stream the caller's most recent Quarterly Self Report PDF. Owner-only."""
    artefact = (
        Artifact.query
        .filter_by(user_id=current_user.id, type="quarterly_self_report")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    if not artefact:
        return jsonify({"error": "No Quarterly Self Report available yet",
                        "code": "NO_REPORT"}), 404

    if not artefact.pdf_path:
        return jsonify({
            "error": "PDF unavailable for this report",
            "code":  "PDF_NOT_RENDERED",
        }), 410

    pdf_file = Path(artefact.pdf_path)
    if not pdf_file.exists():
        return jsonify({
            "error": "PDF file missing on disk",
            "code":  "PDF_FILE_MISSING",
        }), 410

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
@api_auth
def quarterly_self_report_trigger():
    """Manual trigger for the quarterly cron. Admin-only.

    Body (optional): { "quarter_end": "2026-03-31" }.
    """
    dev_secret = os.environ.get("DEV_LOGIN_SECRET")
    if not dev_secret:
        return jsonify({"error": "Not found"}), 404

    provided = request.headers.get("X-Admin-Secret", "")
    if provided != dev_secret:
        return jsonify({"error": "Admin only"}), 403

    body = request.get_json(silent=True) or {}
    qe_str = body.get("quarter_end")
    quarter_end = None
    if qe_str:
        try:
            quarter_end = date.fromisoformat(qe_str)
        except ValueError:
            return jsonify({
                "error": "invalid quarter_end (expected YYYY-MM-DD)",
            }), 400

    try:
        summary = QuarterlySelfReportService().run_quarterly(
            quarter_end=quarter_end,
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("quarterly_self manual run failed: %s", exc)
        return jsonify({"error": f"Manual run failed: {exc}"}), 500

    return jsonify({"ok": True, "summary": summary})
