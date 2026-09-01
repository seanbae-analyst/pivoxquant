"""Customer support center (고객문의센터).

Endpoints (url_prefix ``/api/support``)
---------------------------------------
- POST /inquiries               — file a support ticket (form)
- GET  /inquiries               — list my tickets (summary)
- GET  /inquiries/<iid>         — my ticket detail (IDOR-safe)
- GET  /admin/inquiries         — all tickets (admin only, 404 to others)
- POST /admin/inquiries/<iid>/reply — operator replies (admin only)

2026-09-01 — the support chatbot (``POST /chat``) was removed. It was the
only live consumer of ``ANTHROPIC_API_KEY``, so the key is gone from the
deploy config too. Support is now a single honest path: the user files an
inquiry and a human answers it. Nothing auto-escalates any more, which also
retires the flood guard that existed only for chatbot-filed tickets.

legal posture
-------------
# legal-exempt: 이 파일의 모든 응답은 사람이 쓴 문의·답변을 그대로 돌려주는
경로다. 생성된 시장 콘텐츠가 아니므로 legal_scrub_response 대상이 아니다.
스크럽 데코레이터는 원래 제거된 /chat (모델 생성 응답) 에만 붙어 있었고,
문의 경로에는 붙은 적이 없다 — exempt 는 기존 동작을 그대로 유지한다.
⚠️ 운영자 답변(admin_reply)까지 스크럽할지는 별도 정책 결정이다. 붙이면
동작 변경이므로 여기서 임의로 바꾸지 않았다.

XSS
---
Every user-supplied string that lands in an email HTML body
(subject/body/admin_reply/email_snapshot) is ``html.escape``d — email
clients render HTML and would otherwise execute injected markup.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user

from extensions import db
from models.inquiry import Inquiry, VALID_CATEGORIES
from routes.decorators import api_auth
from services.admin_emails import get_admin_emails as _admin_emails
from services.error_responses import api_error
from services.email.sender import EmailSender, EmailCategory

logger = logging.getLogger(__name__)

support_bp = Blueprint("support", __name__, url_prefix="/api/support")


# ── constants ────────────────────────────────────────────────────────────────
_OPEN_INQUIRY_CAP = 10            # user-filed open tickets
_INQUIRY_COOLDOWN_SECONDS = 30
_SUBJECT_MAX = 200
_BODY_MAX = 5000


# ── helpers ──────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_admin() -> bool:
    admins = _admin_emails()
    if not admins:
        return False
    if not getattr(current_user, "is_authenticated", False):
        return False
    email = (getattr(current_user, "email", "") or "").lower()
    return email in admins


def _require_admin_or_404() -> None:
    if not _is_admin():
        abort(404)


def _confirmation_html(inquiry: Inquiry) -> str:
    subj = html.escape(inquiry.subject or "")
    body = html.escape(inquiry.body or "")
    return (
        "<div style=\"font-family:sans-serif;line-height:1.6;color:#1a1a1a\">"
        "<h2 style=\"margin:0 0 12px\">문의가 접수되었습니다</h2>"
        f"<p>문의 번호 <strong>#{inquiry.id}</strong> 로 접수되었습니다. "
        "담당자가 확인 후 회신드리겠습니다.</p>"
        f"<p><strong>제목:</strong> {subj}</p>"
        f"<p><strong>내용:</strong><br>{body}</p>"
        "<hr><p style=\"font-size:12px;color:#888\">PivoxQuant 고객지원</p>"
        "</div>"
    )


def _reply_html(inquiry: Inquiry) -> str:
    subj = html.escape(inquiry.subject or "")
    reply = html.escape(inquiry.admin_reply or "")
    return (
        "<div style=\"font-family:sans-serif;line-height:1.6;color:#1a1a1a\">"
        "<h2 style=\"margin:0 0 12px\">문의에 대한 답변입니다</h2>"
        f"<p>문의 번호 <strong>#{inquiry.id}</strong></p>"
        f"<p><strong>제목:</strong> {subj}</p>"
        f"<p><strong>답변:</strong><br>{reply}</p>"
        "<hr><p style=\"font-size:12px;color:#888\">PivoxQuant 고객지원</p>"
        "</div>"
    )


def _notify_operator(inquiry: Inquiry) -> None:
    """Best-effort alert to the operator inbox. Never raises."""
    try:
        from services.email import sendgrid_provider
    except Exception:  # pragma: no cover
        return
    admins = _admin_emails()
    operator = next(iter(sorted(admins)), None) if admins else None
    if not operator:
        operator = "support@pivoxquant.com"
    subj = html.escape(inquiry.subject or "")
    body = html.escape(inquiry.body or "")
    snapshot = html.escape(inquiry.email_snapshot or "")
    cat = html.escape(inquiry.category or "")
    htmlbody = (
        "<div style=\"font-family:sans-serif\">"
        f"<p><strong>새 문의 #{inquiry.id}</strong> ({cat})</p>"
        f"<p>From: {snapshot} (user_id={inquiry.user_id})</p>"
        f"<p>제목: {subj}</p>"
        f"<p>내용:<br>{body}</p>"
        "</div>"
    )
    try:
        sendgrid_provider.send(
            operator,
            subject=f"[PivoxQuant 문의 #{inquiry.id}] {inquiry.subject or ''}"[:200],
            html_body=htmlbody,
            categories=("support", "inquiry"),
        )
    except Exception as exc:  # pragma: no cover
        logger.info("operator notify best-effort failed: %s", exc)


def _send_user_email(user, *, subject: str, html_body: str, ctx: str) -> None:
    """Best-effort transactional email to the user. Never raises."""
    try:
        EmailSender().send(
            user,
            subject=subject,
            html_body=html_body,
            from_env_var="SUPPORT_FROM_EMAIL",
            from_default="support@pivoxquant.com",
            email_category=EmailCategory.TRANSACTIONAL,
        )
    except Exception as exc:  # pragma: no cover
        logger.info("support user email best-effort failed (%s): %s", ctx, exc)


# ── inquiry endpoints ─────────────────────────────────────────────────────────
@support_bp.route("/inquiries", methods=["POST"])
@api_auth
def create_inquiry():
    data = request.get_json(silent=True) or {}
    category = data.get("category")
    subject = data.get("subject")
    body = data.get("body")

    if category not in VALID_CATEGORIES:
        return api_error(
            en="Invalid category.",
            kr="유효하지 않은 문의 유형입니다.",
            code="INVALID_CATEGORY",
            status=400,
        )
    if not isinstance(subject, str) or not (1 <= len(subject.strip()) <= _SUBJECT_MAX):
        return api_error(
            en="Subject must be 1-200 characters.",
            kr="제목은 1~200자여야 합니다.",
            code="INVALID_SUBJECT",
            status=400,
        )
    if not isinstance(body, str) or not (1 <= len(body.strip()) <= _BODY_MAX):
        return api_error(
            en="Body must be 1-5000 characters.",
            kr="내용은 1~5000자여야 합니다.",
            code="INVALID_BODY",
            status=400,
        )

    # rate limit: open ticket cap + recent cooldown.
    open_count = Inquiry.query.filter_by(
        user_id=current_user.id, status="open"
    ).count()
    if open_count >= _OPEN_INQUIRY_CAP:
        return api_error(
            en="Too many open inquiries.",
            kr="처리 대기 중인 문의가 너무 많습니다.",
            code="RATE_LIMITED",
            status=429,
        )
    last = (
        Inquiry.query.filter_by(user_id=current_user.id)
        .order_by(Inquiry.created_at.desc())
        .first()
    )
    if last and last.created_at:
        elapsed = (_now() - last.created_at).total_seconds()
        if elapsed < _INQUIRY_COOLDOWN_SECONDS:
            return api_error(
                en="Please wait before submitting another inquiry.",
                kr="잠시 후 다시 문의해 주세요.",
                code="RATE_LIMITED",
                status=429,
            )

    inquiry = Inquiry(
        user_id=current_user.id,
        category=category,
        subject=subject.strip(),
        body=body.strip(),
        status="open",
        email_snapshot=current_user.email,
        created_at=_now(),
    )
    db.session.add(inquiry)
    db.session.commit()

    # Side effects are best-effort — never roll back the saved ticket.
    _notify_operator(inquiry)
    _send_user_email(
        current_user,
        subject=f"[PivoxQuant] 문의가 접수되었습니다 (#{inquiry.id})",
        html_body=_confirmation_html(inquiry),
        ctx="confirmation",
    )

    return jsonify({
        "id": inquiry.id,
        "status": inquiry.status,
        "created_at": inquiry.created_at.isoformat(),
    }), 201


@support_bp.route("/inquiries", methods=["GET"])
@api_auth
def list_inquiries():
    rows = (
        Inquiry.query.filter_by(user_id=current_user.id)
        .order_by(Inquiry.created_at.desc())
        .all()
    )
    return jsonify({"inquiries": [r.to_dict() for r in rows]})


@support_bp.route("/inquiries/<int:iid>", methods=["GET"])
@api_auth
def get_inquiry(iid: int):
    inquiry = db.session.get(Inquiry, iid)
    if inquiry is None or inquiry.user_id != current_user.id:
        return api_error(
            en="Inquiry not found.",
            kr="문의를 찾을 수 없습니다.",
            code="INQUIRY_NOT_FOUND",
            status=404,
        )
    return jsonify(inquiry.to_dict(detail=True))


# ── admin endpoints ───────────────────────────────────────────────────────────
@support_bp.route("/admin/inquiries", methods=["GET"])
@api_auth
def admin_list_inquiries():
    _require_admin_or_404()
    q = Inquiry.query
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(Inquiry.created_at.desc()).all()
    out = []
    for r in rows:
        d = r.to_dict(detail=True)
        d["user_id"] = r.user_id
        d["email_snapshot"] = r.email_snapshot
        out.append(d)
    return jsonify({"inquiries": out})


@support_bp.route("/admin/inquiries/<int:iid>/reply", methods=["POST"])
@api_auth
def admin_reply_inquiry(iid: int):
    _require_admin_or_404()
    inquiry = db.session.get(Inquiry, iid)
    if inquiry is None:
        return api_error(
            en="Inquiry not found.",
            kr="문의를 찾을 수 없습니다.",
            code="INQUIRY_NOT_FOUND",
            status=404,
        )
    data = request.get_json(silent=True) or {}
    reply = data.get("reply")
    if not isinstance(reply, str) or not (1 <= len(reply.strip()) <= _BODY_MAX):
        return api_error(
            en="Reply must be 1-5000 characters.",
            kr="답변은 1~5000자여야 합니다.",
            code="INVALID_REPLY",
            status=400,
        )

    inquiry.admin_reply = reply.strip()
    inquiry.status = "answered"
    inquiry.answered_at = _now()
    db.session.commit()

    # Reply email to the ticket owner (transactional).
    user = getattr(inquiry, "user", None)
    if user is not None:
        _send_user_email(
            user,
            subject=f"[PivoxQuant] 문의에 답변드립니다 (#{inquiry.id})",
            html_body=_reply_html(inquiry),
            ctx="reply",
        )

    # Mirror admin_list_inquiries shape (detail + user_id + email_snapshot) so
    # the frontend SupportAdminInquiry contract holds — the operator console
    # consumes the same row shape from both list and reply responses.
    d = inquiry.to_dict(detail=True)
    d["user_id"] = inquiry.user_id
    d["email_snapshot"] = inquiry.email_snapshot
    return jsonify(d)
