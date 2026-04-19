"""Human-in-the-loop escalation — Slack webhook for critical decisions."""
import json
import logging
from datetime import datetime, timezone

import requests
from sqlalchemy import text

from agent_worker.config import (
    SLACK_WEBHOOK_URL,
    ESCALATION_TRIGGERS,
    ESCALATION_RISK_THRESHOLD,
    TARGET_URL,
)

log = logging.getLogger(__name__)


def evaluate_triggers(task: dict, decision: dict) -> dict | None:
    """
    Check if this task+decision matches any escalation trigger.
    Returns the matched trigger dict or None.
    """
    # Explicit trigger type match
    trigger_type = decision.get("trigger_type")
    if trigger_type and trigger_type in ESCALATION_TRIGGERS:
        return {"name": trigger_type, **ESCALATION_TRIGGERS[trigger_type]}

    # Risk score threshold
    risk = task.get("risk_score", 0)
    if risk >= ESCALATION_RISK_THRESHOLD:
        return {
            "name": f"risk_threshold_{risk}",
            "risk": risk,
            "channel": "slack",
        }

    # Low confidence
    confidence = decision.get("confidence", 100)
    if confidence < 70:
        return {
            "name": "agent_confidence_below_70",
            **ESCALATION_TRIGGERS["agent_confidence_below_70"],
        }

    # Retry exhaustion
    if task.get("retry_count", 0) >= 3:
        return {
            "name": "retry_count_exceeds_3",
            **ESCALATION_TRIGGERS["retry_count_exceeds_3"],
        }

    return None


def send_slack(message: str, blocks: list | None = None) -> bool:
    """Send message to Slack webhook. Returns True on success."""
    if not SLACK_WEBHOOK_URL:
        log.error("SLACK_WEBHOOK_URL not configured — cannot escalate")
        return False

    payload = {"text": message}
    if blocks:
        payload["blocks"] = blocks

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.exception("Slack webhook failed: %s", e)
        return False


def escalate_task(db_session, task_id: int, trigger: dict, task: dict, decision: dict) -> bool:
    """
    Mark task as escalated and send Slack notification.
    Task will remain in 'escalated' status until human approves/rejects via admin endpoint.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Update task status
    db_session.execute(
        text(
            """
            UPDATE agent_tasks
            SET status = 'escalated',
                escalated_at = :now
            WHERE id = :task_id
            """
        ),
        {"now": now, "task_id": task_id},
    )
    db_session.commit()

    # Build Slack blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 Agent 승인 필요: {trigger['name']}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Task ID:* `{task_id}`"},
                {"type": "mrkdwn", "text": f"*Agent:* `{task.get('assigned_to', '?')}`"},
                {"type": "mrkdwn", "text": f"*Risk:* `{trigger['risk']}/100`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Type:* `{task.get('type', '?')}`",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*설명:*\n{task.get('description', decision.get('summary', 'N/A'))[:500]}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 승인"},
                    "style": "primary",
                    "url": f"{TARGET_URL}/admin/agent/approve/{task_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 거절"},
                    "style": "danger",
                    "url": f"{TARGET_URL}/admin/agent/reject/{task_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔍 상세"},
                    "url": f"{TARGET_URL}/admin/agent/task/{task_id}",
                },
            ],
        },
    ]

    return send_slack(
        f"🚨 Agent escalation: task {task_id} ({trigger['name']}) — 승인 필요",
        blocks=blocks,
    )


def notify_healthcheck_result(all_ok: bool, results: list[dict]) -> None:
    """Quiet ✅ on success, detailed alert on failure."""
    if all_ok:
        send_slack(f"✅ Daily healthcheck passed ({len(results)} checks @ {TARGET_URL})")
        return

    failed = [r for r in results if not r.get("ok")]
    lines = [f"❌ Healthcheck failed — {len(failed)}/{len(results)} checks down"]
    for r in failed:
        lines.append(f"  • `{r['check']}` → {r.get('reason', 'unknown')}")

    send_slack("\n".join(lines))
