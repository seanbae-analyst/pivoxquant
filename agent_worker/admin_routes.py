"""Admin HTML endpoints for approving/rejecting escalated tasks.

Mount in app.py:
    from agent_worker.admin_routes import admin_agent_bp
    app.register_blueprint(admin_agent_bp)

Capital markets law (Iron Rule #7): no BUY/SELL/추천/조언 anywhere in UI.
Labels are restricted to 승인/거절/상세/중지.

⚠️ MOUNT-TIME SECURITY REQUIREMENTS (Wave G-4 P1-A audit, 2026-05-18):

Before mounting this blueprint in ``routes/__init__.py``, you MUST add
the three guards below. Currently this blueprint is UNMOUNTED — only
``agent_worker.growth_routes`` is registered (behind try/except in
``routes/__init__.py:54-64``). Mounting without these guards = critical
authz/CSRF holes.

  1) CSRF token enforcement on all POST form handlers
     - ``/approve/<task_id>``, ``/reject/<task_id>``, ``/halt``
     - Use ``flask_wtf`` CSRF or ``hmac.compare_digest`` on a
       session-bound token
     - The HTML forms (lines ~265-272, ~363-370) include NO csrf_token
       hidden input — a malicious cross-origin POST while admin is
       logged in can approve/reject any task.

  2) Admin allowlist gate (NOT just ``login_required``)
     - ``flask_login.login_required`` only checks "is a user logged in"
     - Approve/reject paths must additionally verify
       ``current_user.email in services.admin_emails.get_admin_emails()``
     - Otherwise any logged-in Free user could POST to
       ``/admin/agent/approve/<task_id>``.

  3) Audit log row per approve/reject decision
     - admin_email + task_id + decision + timestamp + remote_addr
     - Compliance: regulator may ask "who approved which AI action when"

Tracked external actions (메모리 carry-over):
  - #G4-P1A (this file: CSRF + admin gate + audit log) — defer until
    mount decision
  - #14 PIVOX_BROKER_ENCRYPTION_KEY rotation script (PR #480 G-2 #1)
  - #15 token cache AES-GCM ✅ resolved (PR #485)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone

from flask import Blueprint, abort, jsonify
from flask_login import current_user, login_required
from markupsafe import escape
from sqlalchemy import text

from extensions import db

log = logging.getLogger(__name__)

admin_agent_bp = Blueprint("admin_agent", __name__, url_prefix="/admin/agent")


# 2026-05-17 wave 13 P2 (PR #442): centralized parser; alias kept.
from services.admin_emails import get_admin_emails as _admin_emails  # noqa: E402


def _require_admin():
    """Return None if current user is admin; else a Flask error response."""
    admins = _admin_emails()
    if not admins:
        log.warning("ADMIN_EMAILS not configured — denying all admin requests")
        return jsonify({"error": "Admin access not configured"}), 403
    email = (getattr(current_user, "email", "") or "").lower()
    if email not in admins:
        return jsonify({"error": "Forbidden"}), 403
    return None


def _page(title: str, body: str) -> str:
    """Minimal HTML shell with Tailwind CDN. No trading terminology."""
    safe_title = escape(title)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{safe_title} — PivoxQuant Admin</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
  <div class="max-w-3xl mx-auto p-8">
    <header class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-semibold">{safe_title}</h1>
      <a href="/admin/agent" class="text-sm text-slate-500 hover:underline">PivoxQuant Agent Admin</a>
    </header>
    <main class="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      {body}
    </main>
  </div>
</body>
</html>"""


def _fetch_task(task_id: int) -> dict | None:
    row = db.session.execute(
        text(
            """
            SELECT id, type, status, assigned_to, payload, result, description,
                   parent_task_id, chain_depth, risk_score, escalated_at,
                   approved_by, created_at, completed_at, retry_count, max_retries
            FROM agent_tasks
            WHERE id = :id
            """
        ),
        {"id": task_id},
    ).fetchone()
    if not row:
        return None
    return dict(row._mapping)


def _fetch_decisions(task_id: int) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT id, agent, decision_type, reasoning, confidence,
                   input_tokens, output_tokens, cost_usd, created_at
            FROM agent_decisions
            WHERE task_id = :id
            ORDER BY id ASC
            """
        ),
        {"id": task_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


@admin_agent_bp.route("/approve/<int:task_id>", methods=["GET", "POST"])
@login_required
def approve(task_id: int):
    guard = _require_admin()
    if guard is not None:
        return guard

    task = _fetch_task(task_id)
    if not task:
        abort(404)
    if task["status"] in ("done", "cancelled"):
        return _page(
            "이미 처리된 항목",
            f"<p>Task #{task_id} 은(는) 이미 <b>{escape(task['status'])}</b> 상태입니다.</p>"
            f'<a href="/admin/agent/task/{task_id}" class="text-blue-600 hover:underline">상세 보기</a>',
        )

    db.session.execute(
        text(
            """
            UPDATE agent_tasks
            SET status = 'done',
                approved_by = :approver,
                completed_at = :now
            WHERE id = :id
            """
        ),
        {
            "approver": current_user.email,
            "now": datetime.now(timezone.utc).replace(tzinfo=None),
            "id": task_id,
        },
    )
    db.session.commit()
    log.info("Task %s approved by %s", task_id, current_user.email)

    body = (
        f"<p class='text-green-700 font-medium'>Task #{task_id} 승인 완료.</p>"
        f"<p class='text-slate-600 text-sm mt-2'>처리자: {escape(current_user.email)}</p>"
        f'<a href="/admin/agent/task/{task_id}" class="mt-4 inline-block text-blue-600 hover:underline">상세 보기</a>'
    )
    return _page("승인 완료", body)


@admin_agent_bp.route("/reject/<int:task_id>", methods=["GET", "POST"])
@login_required
def reject(task_id: int):
    guard = _require_admin()
    if guard is not None:
        return guard

    task = _fetch_task(task_id)
    if not task:
        abort(404)
    if task["status"] in ("done", "cancelled"):
        return _page(
            "이미 처리된 항목",
            f"<p>Task #{task_id} 은(는) 이미 <b>{escape(task['status'])}</b> 상태입니다.</p>"
            f'<a href="/admin/agent/task/{task_id}" class="text-blue-600 hover:underline">상세 보기</a>',
        )

    db.session.execute(
        text(
            """
            UPDATE agent_tasks
            SET status = 'cancelled',
                approved_by = :approver,
                completed_at = :now
            WHERE id = :id
            """
        ),
        {
            "approver": current_user.email,
            "now": datetime.now(timezone.utc).replace(tzinfo=None),
            "id": task_id,
        },
    )
    db.session.commit()
    log.info("Task %s rejected by %s", task_id, current_user.email)

    body = (
        f"<p class='text-red-700 font-medium'>Task #{task_id} 거절 처리.</p>"
        f"<p class='text-slate-600 text-sm mt-2'>처리자: {escape(current_user.email)}</p>"
        f'<a href="/admin/agent/task/{task_id}" class="mt-4 inline-block text-blue-600 hover:underline">상세 보기</a>'
    )
    return _page("거절 완료", body)


def _render_task_row(task: dict) -> str:
    payload = task.get("payload")
    result = task.get("result")
    payload_pretty = escape(json.dumps(payload, ensure_ascii=False, indent=2)) if payload else "—"
    result_pretty = escape(json.dumps(result, ensure_ascii=False, indent=2)) if result else "—"
    return f"""
    <section class="space-y-3">
      <div class="grid grid-cols-2 gap-4 text-sm">
        <div><span class="text-slate-500">ID</span><br><code>{task['id']}</code></div>
        <div><span class="text-slate-500">상태</span><br><b>{escape(task['status'])}</b></div>
        <div><span class="text-slate-500">타입</span><br>{escape(task['type'])}</div>
        <div><span class="text-slate-500">담당 agent</span><br>{escape(task.get('assigned_to') or '—')}</div>
        <div><span class="text-slate-500">위험도</span><br>{task['risk_score']}/100</div>
        <div><span class="text-slate-500">체인 깊이</span><br>{task['chain_depth']}</div>
        <div><span class="text-slate-500">재시도</span><br>{task['retry_count']} / {task['max_retries']}</div>
        <div><span class="text-slate-500">처리자</span><br>{escape(task.get('approved_by') or '—')}</div>
      </div>
      <div>
        <div class="text-slate-500 text-sm">설명</div>
        <p class="whitespace-pre-wrap">{escape(task.get('description') or '—')}</p>
      </div>
      <div>
        <div class="text-slate-500 text-sm">payload</div>
        <pre class="bg-slate-100 rounded p-3 text-xs overflow-x-auto">{payload_pretty}</pre>
      </div>
      <div>
        <div class="text-slate-500 text-sm">result</div>
        <pre class="bg-slate-100 rounded p-3 text-xs overflow-x-auto">{result_pretty}</pre>
      </div>
    </section>
    """


def _render_decisions(decisions: list[dict]) -> str:
    if not decisions:
        return "<p class='text-sm text-slate-500 mt-6'>기록된 의사결정 없음</p>"
    rows = []
    for d in decisions:
        reasoning = escape((d.get("reasoning") or "")[:400])
        rows.append(
            f"""
            <tr class="border-t border-slate-200">
              <td class="p-2 font-mono text-xs">{d['id']}</td>
              <td class="p-2">{escape(d['agent'])}</td>
              <td class="p-2">{escape(d['decision_type'])}</td>
              <td class="p-2">{d.get('confidence') or '—'}</td>
              <td class="p-2 text-xs">{reasoning}</td>
              <td class="p-2 text-xs">${d.get('cost_usd') or '0'}</td>
            </tr>
            """
        )
    return f"""
    <h2 class="mt-8 mb-3 text-lg font-medium">의사결정 이력</h2>
    <table class="w-full text-sm border border-slate-200 rounded">
      <thead class="bg-slate-50 text-slate-500">
        <tr>
          <th class="p-2 text-left">#</th>
          <th class="p-2 text-left">agent</th>
          <th class="p-2 text-left">유형</th>
          <th class="p-2 text-left">confidence</th>
          <th class="p-2 text-left">reasoning</th>
          <th class="p-2 text-left">비용</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _render_actions(task: dict) -> str:
    if task["status"] not in ("escalated", "pending", "in_progress"):
        return ""
    return f"""
    <div class="mt-6 flex gap-3">
      <form method="post" action="/admin/agent/approve/{task['id']}">
        <button class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded">승인</button>
      </form>
      <form method="post" action="/admin/agent/reject/{task['id']}">
        <button class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded">거절</button>
      </form>
    </div>
    """


@admin_agent_bp.route("/task/<int:task_id>")
@login_required
def task_detail(task_id: int):
    guard = _require_admin()
    if guard is not None:
        return guard

    task = _fetch_task(task_id)
    if not task:
        abort(404)
    decisions = _fetch_decisions(task_id)

    body = _render_task_row(task) + _render_actions(task) + _render_decisions(decisions)
    return _page(f"Task #{task_id} 상세", body)


@admin_agent_bp.route("/halt", methods=["POST"])
@login_required
def halt():
    guard = _require_admin()
    if guard is not None:
        return guard

    today = date.today()
    db.session.execute(
        text(
            """
            INSERT INTO agent_budget (date, halted) VALUES (:today, TRUE)
            ON CONFLICT (date) DO UPDATE SET halted = TRUE
            """
        ),
        {"today": today},
    )
    db.session.commit()
    log.warning("Budget halted by %s", current_user.email)
    return _page(
        "오늘 중지됨",
        f"<p class='text-amber-700 font-medium'>Agent worker: 오늘({today}) 예산 사용 중지.</p>"
        f"<p class='text-slate-600 text-sm mt-2'>처리자: {escape(current_user.email)}</p>",
    )


@admin_agent_bp.route("/")
@login_required
def index():
    guard = _require_admin()
    if guard is not None:
        return guard

    rows = db.session.execute(
        text(
            """
            SELECT id, type, status, assigned_to, risk_score, created_at
            FROM agent_tasks
            ORDER BY id DESC
            LIMIT 50
            """
        )
    ).fetchall()

    tr = []
    for r in rows:
        tr.append(
            f"<tr class='border-t border-slate-200'>"
            f"<td class='p-2 font-mono text-xs'><a class='text-blue-600 hover:underline' href='/admin/agent/task/{r.id}'>{r.id}</a></td>"
            f"<td class='p-2'>{escape(r.type)}</td>"
            f"<td class='p-2'>{escape(r.status)}</td>"
            f"<td class='p-2'>{escape(r.assigned_to or '—')}</td>"
            f"<td class='p-2'>{r.risk_score}</td>"
            f"<td class='p-2 text-xs'>{r.created_at}</td>"
            f"</tr>"
        )
    body = (
        "<p class='text-sm text-slate-500 mb-4'>최근 50건</p>"
        "<table class='w-full text-sm border border-slate-200 rounded'>"
        "<thead class='bg-slate-50 text-slate-500'><tr>"
        "<th class='p-2 text-left'>#</th>"
        "<th class='p-2 text-left'>타입</th>"
        "<th class='p-2 text-left'>상태</th>"
        "<th class='p-2 text-left'>agent</th>"
        "<th class='p-2 text-left'>위험도</th>"
        "<th class='p-2 text-left'>생성</th>"
        f"</tr></thead><tbody>{''.join(tr)}</tbody></table>"
        "<form method='post' action='/admin/agent/halt' class='mt-6'>"
        "<button class='bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded'>오늘 중지</button>"
        "</form>"
    )
    return _page("Agent Worker 관리", body)
