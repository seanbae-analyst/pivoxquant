"""CEO Inbox aggregator service (v57 Phase A).

Single-pane data source that consolidates:
- autopilot_log.md tail (autonomous_done — 자율 처리 완료, 24h)
- SHIP_BLOCKERS.md categories (external_actions — RELEASE-BLOCKER / AT-RISK)
- legal_question_queue.md (변호사 큐 카운트)
- /tmp/ship_blockers_status.json (06:00 cron 결과 인용)
- /tmp/data_integrity_status.json (04:00 cron 결과 인용)
- next APScheduler fire times (계산)

Read-only — no external API calls, no LLM, no DB writes.
Used by routes/inbox.py for /api/inbox GET.
"""
from services.inbox.aggregator import build_inbox_payload

__all__ = ["build_inbox_payload"]
