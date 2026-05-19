#!/usr/bin/env python3
"""Wave I L-3 — 통신판매업 신고 D-day 월간 알림 (feature-flagged).

목적
====
PivoxQuant 사업자등록은 발급 완료(459-01-03808, 2026-05-08, 정보통신업)이나
**통신판매업 신고**는 별도 의무이며 미완 상태이다. 전자상거래법 §12 (통신판매업
신고) 미신고 상태에서 Stripe Live 결제(SaaS 월 구독) 활성 시 다음 제재 위험:

- **전자상거래법 §12 + §44** — 통신판매업 신고 의무 위반.
  미신고 영업 시 **3년 이하의 징역 또는 1억원 이하의 벌금** (§44 ② 1호) 또는
  공정거래위원회 시정명령 + 과태료(영업정지 포함, §40~§43).
- **부가가치세법 §10** — 통신판매업이 별도 업태 분류이므로 사업자등록 업태
  추가가 필요할 수 있다 (변호사 Q8 carry-over).

본 스크립트는 **매월 1일 09:00 KST** Slack + 로그로 CEO 에게 신고 완료까지
반복 알림을 보낸다. 신고 완료 후 env ``PIVOX_COMMERCE_REGISTERED=true`` 로
설정하면 즉시 exit 0 (silent skip).

스케줄
======
APScheduler ``CronTrigger(day=1, hour=9, minute=0, timezone='Asia/Seoul')`` 로
``services/scheduler/cron_jobs.py:_job_specs()`` 에 ``ops_commerce_registration``
id 로 등록. macOS crontab fallback 은 ``scripts/cron/run.sh commerce-registration``.

Feature flag
============
``PIVOX_COMMERCE_REGISTERED`` (default ``false``).

- ``true``  → 신고 완료. 알림 발송 즉시 중단. exit 0.
- ``false`` → 미완. 매월 1일 알림 발송.

중복 방지
==========
``state/commerce_registration_reminder.json`` 의 ``last_alerted_at`` 으로
같은 달(YYYY-MM)에 이미 알림 발송했는지 확인. 같은 달이면 즉시 skip
(APScheduler 가 어떤 이유로 같은 cron 을 두 번 fire 해도 1통만 발송).

비용 0원
========
- Slack Incoming Webhook (free tier 무제한)
- 외부 API 호출 없음. 로컬 state 파일만 read/write.
- ``SLACK_WEBHOOK_URL`` 미설정 시 stdout fallback (graceful skip).

환경변수
========
- ``PIVOX_COMMERCE_REGISTERED`` — 'true' / '1' / 'yes' 면 신고 완료 간주. 그 외 false.
- ``SLACK_WEBHOOK_URL``         — 없으면 stdout fallback.

법적 근거
=========
- 전자상거래법 §12 (통신판매업 신고)
- 전자상거래법 §44 ② 1호 (벌칙: 3년 이하 징역 또는 1억원 이하 벌금)
- 정부24 신고 페이지: https://www.gov.kr/ → "통신판매업 신고"
- 공정거래위원회: https://www.ftc.go.kr/ → "통신판매업 신고 안내"

신고 시 필요 자료
==================
1. 사업자등록증 PDF (459-01-03808 발급 완료)
2. 도메인/호스팅 정보 (pivoxquant.com, Vercel/Railway)
3. 결제대행사(PG) 계약서 또는 결제 화면 캡쳐 (Stripe)
4. 구매안전서비스(에스크로) 이용 확인증 — Stripe 의 경우 chargeback 정책 활용 검토 필요

실행
====
``python scripts/nightly/commerce_registration_reminder.py``
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_SSL_CTX = ssl.create_default_context()

# Repo root — scripts/nightly/foo.py → parent.parent.parent
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _REPO_ROOT / "state"
STATE_PATH = STATE_DIR / "commerce_registration_reminder.json"

# KST tzinfo for "same month" comparison (이를 통해 매월 1일 알림이 KST
# 기준으로 1회 발송됨을 보장). Python 3.9+ zoneinfo.
try:
    from zoneinfo import ZoneInfo
    _KST = ZoneInfo("Asia/Seoul")
except ImportError:  # pragma: no cover — Python < 3.9 fallback
    _KST = timezone(timedelta(hours=9))


def _is_registered() -> bool:
    """``PIVOX_COMMERCE_REGISTERED`` truthy check.

    Accepted truthy values (case-insensitive): ``true``, ``1``, ``yes``, ``y``,
    ``on``. Anything else (including empty / unset) → False.
    """
    raw = os.environ.get("PIVOX_COMMERCE_REGISTERED", "").strip().lower()
    return raw in ("true", "1", "yes", "y", "on")


def _now_kst() -> datetime:
    return datetime.now(_KST)


def _month_key(dt: datetime) -> str:
    """YYYY-MM string in KST — used for same-month dedup."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_KST).strftime("%Y-%m")


def load_state() -> dict:
    """Load reminder state ({} if missing or corrupt)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("state load failed (%s) — starting fresh", exc)
        return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _parse_iso(date_str: str) -> Optional[datetime]:
    """Parse ISO date / datetime → aware UTC datetime. None on failure."""
    if not date_str:
        return None
    try:
        normalized = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def already_alerted_this_month(state: dict, now: Optional[datetime] = None) -> bool:
    """Return True iff state.last_alerted_at falls in the current KST month.

    Same-month dedup defends against APScheduler firing the cron twice (e.g.
    container restart on day 1) and against manual re-runs during testing.
    """
    now = now or _now_kst()
    last_raw = state.get("last_alerted_at", "")
    last_dt = _parse_iso(last_raw)
    if last_dt is None:
        return False
    return _month_key(last_dt) == _month_key(now)


def build_alert_message() -> str:
    """Build the Slack/stdout alert body.

    Includes the legal basis, both filing portals, and the document checklist.
    Kept in this module (not a template file) so the cron has zero filesystem
    dependencies beyond the state file.
    """
    return (
        "[BLOCKER] PivoxQuant 통신판매업 신고 미완료 — 월간 D-day 알림\n"
        "\n"
        "전자상거래법 §12 (통신판매업 신고) 의무. 미신고 상태에서 Stripe Live\n"
        "결제 활성 시 §44 ② 1호 (3년 이하 징역 또는 1억원 이하 벌금) 위험.\n"
        "\n"
        "신고 채널:\n"
        "  1) 정부24 — https://www.gov.kr → '통신판매업 신고'\n"
        "  2) 공정거래위원회 — https://www.ftc.go.kr → '통신판매업 신고'\n"
        "\n"
        "신고 시 필요 자료:\n"
        "  - 사업자등록증 PDF (459-01-03808, 2026-05-08 발급)\n"
        "  - 도메인/호스팅 정보 (pivoxquant.com)\n"
        "  - 결제대행사 계약서 또는 결제 화면 (Stripe)\n"
        "  - 구매안전서비스 이용 확인증 (에스크로 또는 chargeback 정책 검토)\n"
        "\n"
        "신고 완료 후 ~/.pivoxquant-env 에 ``export PIVOX_COMMERCE_REGISTERED=true``\n"
        "추가 → 알림 자동 중단.\n"
        "\n"
        "변호사 Q-S3 (legal_question_queue.md) — §101 면제 트랙 vs 통신판매업\n"
        "신고 'SaaS 월 구독' 자인 가능성 변호사 사인 대기."
    )


def post_slack(text: str) -> bool:
    """Best-effort Slack webhook POST. False on webhook missing or HTTP error."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout fallback")
        print(f"[SLACK-FALLBACK]\n{text}")
        return False
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Slack webhook failed: %s", exc)
        return False


def main() -> int:
    """Entry point — returns process exit code.

    Returns
    -------
    0 — registered (skip), or already alerted this month, or alert sent successfully.
    Non-zero is reserved for future hard-fail cases (none today; we always exit 0
    even on webhook failure because the stdout fallback is itself an audit trail).
    """
    # ── 1. registered short-circuit ────────────────────────────────────────
    if _is_registered():
        logger.info("PIVOX_COMMERCE_REGISTERED=true — 신고 완료, 알림 skip")
        return 0

    # ── 2. same-month dedup ────────────────────────────────────────────────
    state = load_state()
    now = _now_kst()
    if already_alerted_this_month(state, now=now):
        logger.info(
            "이미 %s 월에 알림 발송 완료 (last_alerted_at=%s) — skip",
            _month_key(now), state.get("last_alerted_at"),
        )
        return 0

    # ── 3. dispatch alert ──────────────────────────────────────────────────
    msg = build_alert_message()
    sent = post_slack(msg)
    state["last_alerted_at"] = now.isoformat()
    state["last_alert_delivered_via"] = "slack" if sent else "stdout_fallback"
    save_state(state)
    logger.info(
        "통신판매업 신고 알림 발송: month=%s slack=%s",
        _month_key(now), sent,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
