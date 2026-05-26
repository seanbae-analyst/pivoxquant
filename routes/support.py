"""Customer support center (고객문의센터) + support chatbot.

Endpoints (url_prefix ``/api/support``)
---------------------------------------
- POST /inquiries               — file a support ticket (form)
- GET  /inquiries               — list my tickets (summary)
- GET  /inquiries/<iid>         — my ticket detail (IDOR-safe)
- GET  /admin/inquiries         — all tickets (admin only, 404 to others)
- POST /admin/inquiries/<iid>/reply — operator replies (admin only)
- POST /chat                    — support chatbot (all tiers)

Legal posture
-------------
The chatbot NEVER surfaces investment advice — see
``services/support/chatbot.py`` for the 3-layer defense. The /chat path
escalates anything it cannot safely answer to a human Inquiry.

XSS
---
Every user-supplied string that lands in an email HTML body
(subject/body/admin_reply/email_snapshot) is ``html.escape``d — email
clients render HTML and would otherwise execute injected markup.
"""
from __future__ import annotations

import html
import logging
import threading
import time as _time
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user

from extensions import db
from models.inquiry import Inquiry, VALID_CATEGORIES
from routes.decorators import api_auth
from services.admin_emails import get_admin_emails as _admin_emails
from services.error_responses import api_error
from services.email.sender import EmailSender, EmailCategory
from services.support.chatbot import answer_support_question, _is_investment_question

logger = logging.getLogger(__name__)

support_bp = Blueprint("support", __name__, url_prefix="/api/support")


# ── constants ────────────────────────────────────────────────────────────────
_OPEN_INQUIRY_CAP = 10            # user-filed open tickets
_AUTO_ESCALATION_OPEN_CAP = 15    # chatbot auto-filed open tickets (flood guard)
_INQUIRY_COOLDOWN_SECONDS = 30
_CHAT_COOLDOWN_SECONDS = 3
_CHAT_DAILY_CAP = 50
_SUBJECT_MAX = 200
_BODY_MAX = 5000
_CHAT_MSG_MAX = 2000
_HISTORY_MAX_TURNS = 10
_HISTORY_CONTENT_MAX = 1000


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

    return jsonify(inquiry.to_dict(detail=True))


# ── chatbot endpoint ───────────────────────────────────────────────────────────
# Per-user in-memory rate-limit state (single gevent worker). Reset on reboot.
_chat_lock = threading.Lock()
_chat_state: dict[int, dict] = {}  # uid -> {"last": ts, "day": "YYYY-MM-DD", "count": int}


def _chat_rate_limited(uid: int) -> bool:
    now = _time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _chat_lock:
        st = _chat_state.get(uid)
        if st is None:
            _chat_state[uid] = {"last": now, "day": today, "count": 1}
            return False
        if st["day"] != today:
            st["day"] = today
            st["count"] = 0
        if now - st["last"] < _CHAT_COOLDOWN_SECONDS:
            return True
        if st["count"] >= _CHAT_DAILY_CAP:
            return True
        st["last"] = now
        st["count"] += 1
        return False


def _validate_history(history) -> bool:
    if history is None:
        return True
    if not isinstance(history, list):
        return False
    if len(history) > _HISTORY_MAX_TURNS:
        return False
    for turn in history:
        if not isinstance(turn, dict):
            return False
        if turn.get("role") not in ("user", "assistant"):
            return False
        content = turn.get("content")
        if not isinstance(content, str) or len(content) > _HISTORY_CONTENT_MAX:
            return False
    return True


_DEFLECT_INVESTMENT = (
    "투자 관련 질문에는 답변드릴 수 없어요. 시장 데이터 분석은 앱 내 "
    "AI Assistant를 이용해 주세요. 고객지원은 결제·계정·사용법 문의를 "
    "도와드립니다."
)


def _history_summary(history) -> str:
    """Compact 2-3 most-recent turns for the auto-filed ticket body."""
    if not isinstance(history, list) or not history:
        return ""
    recent = history[-3:]
    lines = []
    for turn in recent:
        role = turn.get("role", "")
        content = (turn.get("content") or "")[:300]
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


@support_bp.route("/chat", methods=["POST"])
@api_auth
def support_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message")
    history = data.get("history")

    if not isinstance(message, str) or not (1 <= len(message.strip()) <= _CHAT_MSG_MAX):
        return api_error(
            en="Invalid message.",
            kr="메시지가 유효하지 않습니다.",
            code="INVALID_MESSAGE",
            status=400,
        )
    if not _validate_history(history):
        return api_error(
            en="Invalid message.",
            kr="메시지가 유효하지 않습니다.",
            code="INVALID_MESSAGE",
            status=400,
        )

    if _chat_rate_limited(current_user.id):
        return api_error(
            en="Too many requests.",
            kr="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
            code="RATE_LIMITED",
            status=429,
        )

    # Layer 1: pre-filter investment questions (zero model tokens).
    if _is_investment_question(message):
        return jsonify({
            "reply": _DEFLECT_INVESTMENT,
            "escalated": False,
            "inquiry_id": None,
        })

    result = answer_support_question(message, history)
    if result.get("can_answer"):
        return jsonify({
            "reply": result["answer"],
            "escalated": False,
            "inquiry_id": None,
        })

    # Escalate to a human Inquiry.
    from services.support.chatbot import ai as _ai  # bound singleton
    ai_unavailable = not _ai.available or _ai.client is None

    # Flood guard: cap auto-filed open tickets per user.
    auto_open = Inquiry.query.filter_by(
        user_id=current_user.id, status="open", category="other"
    ).count()
    inquiry_id = None
    if auto_open < _AUTO_ESCALATION_OPEN_CAP:
        summary = _history_summary(history)
        body = "[챗봇 자동 접수]\n\n" + message
        if summary:
            body += "\n\n--- 최근 대화 ---\n" + summary
        inquiry = Inquiry(
            user_id=current_user.id,
            category="other",
            subject=(message.strip()[:60]) or "고객 문의",
            body=body,
            status="open",
            email_snapshot=current_user.email,
            created_at=_now(),
        )
        db.session.add(inquiry)
        db.session.commit()
        inquiry_id = inquiry.id
        _notify_operator(inquiry)

    if inquiry_id is not None:
        reply = (
            f"제가 바로 답변드리기 어려운 문의예요. 상담으로 접수했고 "
            f"담당자가 확인 후 회신드릴게요. (문의 #{inquiry_id}) "
            "내 문의함에서 확인하실 수 있어요."
        )
    else:
        reply = (
            "제가 바로 답변드리기 어려운 문의예요. 처리 대기 중인 문의가 "
            "많아 추가 접수가 어렵습니다. 잠시 후 다시 시도해 주세요."
        )
    if ai_unavailable:
        reply = "지금 자동 답변이 어려워 " + reply

    return jsonify({
        "reply": reply,
        "escalated": inquiry_id is not None,
        "inquiry_id": inquiry_id,
    })
