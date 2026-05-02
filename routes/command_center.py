"""
Command Center Blueprint — CEO 실시간 에이전트/스킬 활동 모니터링 API.

SSE 스트리밍, 활동 로깅, Obsidian vault 저장을 제공한다.

등록 방법 (routes/__init__.py의 register_blueprints 함수에 추가):
    from .command_center import command_center_bp
    # register_blueprints()의 for 루프에 command_center_bp 추가
"""

import os
import json
import logging
import queue
import threading
from collections import deque
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, Response, send_from_directory
from flask_login import current_user

from security import general_rate_limit
from .decorators import api_auth

logger = logging.getLogger(__name__)


# ── Admin gate (ADMIN_EMAILS env var, same pattern as routes/admin_fmp.py) ───

def _admin_emails() -> set[str]:
    """Parse the ``ADMIN_EMAILS`` env var into a set of lowercased addresses."""
    raw = os.getenv("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _deny_non_admin():
    """Return a 403 JSON response when ``current_user`` is not an admin.

    Returns ``None`` when the user *is* an admin so the route can proceed.
    Mirrors ``routes.admin_fmp._deny_non_admin`` so we fail closed when
    ``ADMIN_EMAILS`` is missing in the environment. Pair with ``@api_auth``
    so unauthenticated callers get 401 (not 403) — surfacing the auth gap
    cleanly while still locking the endpoint to admins.
    """
    admins = _admin_emails()
    if not admins:
        logger.warning("ADMIN_EMAILS not configured — denying command-center route")
        return jsonify({"error": "Admin access not configured"}), 403
    email = (getattr(current_user, "email", "") or "").lower()
    if email not in admins:
        return jsonify({"error": "Forbidden"}), 403
    return None

# ── Blueprint ────────────────────────────────────────────────────────────────

command_center_bp = Blueprint("command_center", __name__)

_FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "frontend", "public"
)


@command_center_bp.route("/command-center")
@api_auth
def serve_command_center():
    denied = _deny_non_admin()
    if denied is not None:
        return denied
    return send_from_directory(_FRONTEND_DIR, "command-center.html")


@command_center_bp.route("/agents")
@api_auth
def serve_agents_preview():
    denied = _deny_non_admin()
    if denied is not None:
        return denied
    return send_from_directory(_FRONTEND_DIR, "agents-preview.html")


# ── In-memory store ──────────────────────────────────────────────────────────

_LOG_MAX = 100
_log_store: deque = deque(maxlen=_LOG_MAX)
_lock = threading.Lock()

# SSE subscriber queues (상한 50: 초과 시 가장 오래된 구독자 제거)
_MAX_SUBSCRIBERS = 50
_subscribers: list[queue.Queue] = []
_sub_lock = threading.Lock()

# ── KST timezone ─────────────────────────────────────────────────────────────

_KST = timezone(timedelta(hours=9))

# ── Obsidian log path ────────────────────────────────────────────────────────

_OBSIDIAN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "obsidian-logs",
)

# ── Department mapping ───────────────────────────────────────────────────────

DEPT_MAP = {
    # bkit agents
    "pm-lead": "PM팀", "pm-discovery": "PM팀", "pm-strategy": "PM팀",
    "pm-research": "PM팀", "pm-prd": "PM팀", "product-manager": "PM팀",
    "qa-lead": "QA팀", "qa-strategist": "QA팀", "qa-test-planner": "QA팀",
    "qa-test-generator": "QA팀", "qa-monitor": "QA팀", "qa-debug-analyst": "QA팀",
    "frontend-architect": "프론트엔드", "code-analyzer": "개발부", "cto-lead": "C-Suite",
    "infra-architect": "인프라팀", "enterprise-expert": "인프라팀",
    "security-architect": "보안팀", "gap-detector": "분석팀",
    "report-generator": "분석팀", "design-validator": "디자인부",
    "bkend-expert": "백엔드",
    # gstack skills
    "/review": "개발부", "/ship": "인프라부", "/qa": "QA부", "/browse": "조사부",
    "/investigate": "조사부", "/health": "오퍼레이션부", "/checkpoint": "인프라부",
    "/design-html": "디자인부", "/design-review": "디자인부",
    "/design-consultation": "디자인부", "/design-shotgun": "디자인부",
    "/autoplan": "기획부", "/benchmark": "QA부", "/canary": "인프라부",
    "/careful": "개발부", "/codex": "개발부", "/cso": "C-Suite",
    "/devex-review": "개발부", "/document-release": "문서부",
    "/freeze": "인프라부", "/unfreeze": "인프라부",
    "/guard": "보안부", "/land-and-deploy": "인프라부", "/learn": "교육",
    "/office-hours": "기획부", "/pair-agent": "개발부",
    "/plan-ceo-review": "C-Suite", "/plan-design-review": "디자인부",
    "/plan-devex-review": "개발부", "/plan-eng-review": "개발부",
    "/qa-only": "QA부", "/retro": "기획부", "/setup-browser-cookies": "개발부",
    "pipeline-guide": "기획부", "starter-guide": "교육",
    "pdca-iterator": "분석팀", "/gstack-upgrade": "인프라부",
    "/open-gstack-browser": "개발부",
    # PivoxQuant departments
    "개발부": "개발부", "QA부": "QA부", "디자인부": "디자인부", "마케팅부": "마케팅부",
    "데이터부": "데이터부", "보안부": "보안부", "법무부": "법무부", "재무부": "재무부",
}

_VALID_STATUSES = {"completed", "in_progress", "waiting"}
_FIELD_MAX_LEN = 500

_STATUS_KR = {
    "completed": "완료",
    "in_progress": "진행 중",
    "waiting": "대기",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_kst() -> datetime:
    return datetime.now(_KST)


def _resolve_dept(source: str) -> str:
    """Resolve department from source name via DEPT_MAP. Falls back to '미분류'."""
    return DEPT_MAP.get(source, "미분류")


def _build_entry(source: str, department: str, command: str, status: str) -> dict:
    """Build a log entry dict with timestamp and flow."""
    now = _now_kst()
    return {
        "timestamp": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "source": source,
        "department": department,
        "command": command,
        "status": status,
        "flow": f"CEO -> {department} -> {source}",
    }


def _notify_subscribers(event_data: str) -> None:
    """Push event to all SSE subscribers, removing dead ones."""
    dead: list[queue.Queue] = []

    with _sub_lock:
        for q in _subscribers:
            try:
                q.put_nowait(event_data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            if q in _subscribers:
                _subscribers.remove(q)


def _append_log(entry: dict) -> None:
    """Thread-safe append to deque + notify SSE subscribers."""
    with _lock:
        _log_store.append(entry)

    event_data = json.dumps(entry, ensure_ascii=False)
    _notify_subscribers(event_data)


def _write_obsidian(entry: dict) -> None:
    """Append a log entry to the daily Obsidian markdown file."""
    os.makedirs(_OBSIDIAN_DIR, exist_ok=True)
    filename = f"{entry['date']}-commands.md"
    filepath = os.path.join(_OBSIDIAN_DIR, filename)

    is_new = not os.path.exists(filepath)
    status_kr = _STATUS_KR.get(entry["status"], entry["status"])

    with open(filepath, "a", encoding="utf-8") as f:
        if is_new:
            f.write(f"# Command Log -- {entry['date']}\n\n")
        f.write(f"## {entry['timestamp']}\n")
        f.write(f"- **Flow**: {entry['flow']}\n")
        f.write(f"- **Command**: {entry['command']}\n")
        f.write(f"- **Status**: {status_kr}\n")
        f.write("---\n\n")


# ── POST /api/command-center/log ─────────────────────────────────────────────

@command_center_bp.route("/api/command-center/log", methods=["POST"])
@api_auth
@general_rate_limit
def log_activity():
    """Log an agent/skill activity.

    Body:
        source      — agent name or /skill name (required)
        department  — department name (optional, auto-resolved from source)
        command     — command description (required)
        status      — completed | in_progress | waiting (required)
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    source = (data.get("source") or "").strip()
    command = (data.get("command") or "").strip()
    status = (data.get("status") or "").strip()

    if not source:
        return jsonify({"error": "source is required"}), 400
    if not command:
        return jsonify({"error": "command is required"}), 400
    if status not in _VALID_STATUSES:
        return jsonify({"error": f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}"}), 400

    department = (data.get("department") or "").strip() or _resolve_dept(source)

    for field_name, field_val in [
        ("source", source), ("command", command), ("department", department),
    ]:
        if len(field_val) > _FIELD_MAX_LEN:
            return jsonify({"error": f"{field_name} exceeds max length of {_FIELD_MAX_LEN}"}), 400

    entry = _build_entry(source, department, command, status)
    _append_log(entry)
    _write_obsidian(entry)

    return jsonify({"ok": True, "entry": entry}), 201


# ── GET /api/command-center/stream ───────────────────────────────────────────

@command_center_bp.route("/api/command-center/stream")
@api_auth
def stream():
    """SSE endpoint — pushes new log entries to connected clients."""
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    def _event_stream():
        q: queue.Queue = queue.Queue(maxsize=256)
        with _sub_lock:
            # 구독자 상한 초과 시 가장 오래된 구독자 제거
            while len(_subscribers) >= _MAX_SUBSCRIBERS:
                _subscribers.pop(0)
            _subscribers.append(q)
        try:
            # Send existing entries as initial burst
            with _lock:
                for entry in _log_store:
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"

            # Stream new entries
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    # Heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            logger.debug("silent-fallback: _event_stream", exc_info=True)
            pass
        finally:
            with _sub_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    return Response(
        _event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── GET /api/command-center/stats ────────────────────────────────────────────

@command_center_bp.route("/api/command-center/stats")
@api_auth
def stats():
    """Return current activity statistics."""
    denied = _deny_non_admin()
    if denied is not None:
        return denied
    with _lock:
        entries = list(_log_store)

    counts = {"completed": 0, "in_progress": 0, "waiting": 0}
    for e in entries:
        s = e.get("status")
        if s in counts:
            counts[s] += 1

    total = sum(counts.values())

    return jsonify({
        "ok": True,
        "completed": counts["completed"],
        "inProgress": counts["in_progress"],
        "waiting": counts["waiting"],
        "total": total,
        "agents": 55,
        "skills": 35,
        "commands": total,
    })


# ── POST /api/command-center/dispatch ────────────────────────────────────────

@command_center_bp.route("/api/command-center/dispatch", methods=["POST"])
@api_auth
@general_rate_limit
def dispatch():
    """CEO dispatches a command to an agent or skill.

    Body:
        target  — agent name or /skill name (optional, auto-parsed from command)
        command — command description (required)

    target이 없으면 command 텍스트에서 /스킬명을 자동 파싱한다.
    예: "/review app.py 보안 점검" -> target="/review", command="app.py 보안 점검"
    스킬명이 없으면 target="general"로 기본값 설정.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    target = (data.get("target") or "").strip()
    command = (data.get("command") or "").strip()

    if not command:
        return jsonify({"error": "command is required"}), 400

    for field_name, field_val in [("target", target), ("command", command)]:
        if len(field_val) > _FIELD_MAX_LEN:
            return jsonify({"error": f"{field_name} exceeds max length of {_FIELD_MAX_LEN}"}), 400

    # target이 없으면 command에서 /스킬명 자동 파싱
    if not target:
        if command.startswith("/"):
            parts = command.split(None, 1)
            target = parts[0]
            command = parts[1] if len(parts) > 1 else target
        else:
            target = "general"

    department = _resolve_dept(target)

    entry = _build_entry(target, department, command, "in_progress")
    _append_log(entry)
    _write_obsidian(entry)

    return jsonify({"ok": True, "dispatched": entry}), 201
