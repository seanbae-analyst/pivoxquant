#!/usr/bin/env python3
"""Credentials rotation D-7 alert (S8) + FMP plan expiry (Wave I E-1).

목적
----
SendGrid API key / KIS App Key·Secret 의 권장 회전 주기 종료
D-7 시점에 Slack 으로 알림을 보낸다. 회전 누락으로 인한 인증·발송 사고를 방지.

Wave I E-1: FMP Starter $29 구독 만료도 같은 메커니즘으로 D-30 / D-7 시점에
알림. 만료일은 ``FMP_PLAN_EXPIRY`` env (ISO date) 로 사용자가 직접 주입
(파이낸셜모델링프렙 dashboard 에 명시적 expiry 표시가 없어 사용자 입력 모델).

스케줄
------
crontab ``0 10 * * *`` (KST 10:00 daily). GitHub Actions 미사용 (billing 결제 차단).

회전 정책
---------
- SENDGRID_API_KEY    : 180일 권장 (만료 개념 없음 → 권장 회전)
- KIS_APP_KEY/SECRET  : 365일 (KIS dashboard 기준)
- FMP_PLAN            : ``FMP_PLAN_EXPIRY`` env 의 ISO date (D-30 + D-7 alert).

state 파일
----------
``state/credentials_expiry.json`` — 각 credential 의 마지막 회전 일자 + 마지막
알림 timestamp. 중복 알림 방지 (24h dedup).

비용
----
Slack Incoming Webhook 만 사용 — 0원. 외부 API 호출 없음 (로컬 정책 + state 파일만).

graceful skip
-------------
SLACK_WEBHOOK_URL 미설정 시 stdout fallback. exit 0 유지.
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _ROOT / "state"
STATE_PATH = STATE_DIR / "credentials_expiry.json"

# Default warn threshold (D-7) — Slack alert when within this many days of expiry.
WARN_DAYS = 7
# Dedup window — don't re-alert within this many hours after a prior alert.
DEDUP_HOURS = 24
# FMP plan uses a wider warn window (D-30) because Stripe-style subscriptions
# need at least 2-3 weeks lead time to switch payment methods / migrate plan.
FMP_PLAN_WARN_DAYS = 30

_SSL_CTX = ssl.create_default_context()


@dataclass(frozen=True)
class CredentialPolicy:
    name: str           # state key
    label: str          # human label for alert
    rotation_days: int  # rotation cadence (ignored when absolute_expiry_env set)
    default_last_rotated: str  # ISO date — used if state missing
    rotation_instructions: str
    # When set, the script reads this env var as the **absolute expiry date**
    # (ISO ``YYYY-MM-DD``) instead of computing ``last_rotated + rotation_days``.
    # Used for FMP plan and similar subscription-based credentials where the
    # provider exposes a hard expiry rather than a recommended rotation cadence.
    # ``warn_days`` overrides ``WARN_DAYS`` for the alert window (FMP needs D-30).
    absolute_expiry_env: str | None = None
    warn_days: int | None = None


# 회전 정책 catalog. last rotation 기본값은 메모리/세션 노트에서 가져온 ground truth.
POLICIES: list[CredentialPolicy] = [
    CredentialPolicy(
        name="sendgrid_api_key",
        label="SENDGRID_API_KEY",
        rotation_days=180,
        default_last_rotated="2026-05-18",  # v45 email infra 셋업
        rotation_instructions=(
            "SendGrid dashboard → Settings → API Keys → Create + Revoke 기존. "
            "Railway / .pivoxquant-env / Vercel env 3곳 갱신."
        ),
    ),
    CredentialPolicy(
        name="kis_app_credentials",
        label="KIS_APP_KEY / KIS_APP_SECRET",
        rotation_days=365,
        default_last_rotated="2026-04-19",  # OAuth 정상화 시점 (현재 사용 중인 키)
        rotation_instructions=(
            "한국투자증권 OpenAPI → MyPage → 앱키 재발급. Railway env 2곳 "
            "(KIS_APP_KEY / KIS_APP_SECRET) 동시 갱신. .kis_token_cache.json 자동 무효화."
        ),
    ),
    # Wave I E-1: FMP Starter $29/mo subscription. Expiry exposed via env
    # (사용자가 결제 영수증 받은 후 ``~/.pivoxquant-env`` 에 직접 등록).
    CredentialPolicy(
        name="fmp_plan",
        label="FMP Starter plan ($29/mo)",
        rotation_days=0,  # ignored when absolute_expiry_env set
        default_last_rotated="2026-01-01",  # ignored when env set; required for dataclass
        rotation_instructions=(
            "financialmodelingprep.com → Dashboard → Subscription. "
            "결제 카드 만료 / 잔액 부족 시 갱신 실패 → 402 cascade (Discover / "
            "Earnings / Risk 페이지 모두 죽음). ``~/.pivoxquant-env`` 에 "
            "``export FMP_PLAN_EXPIRY=YYYY-MM-DD`` 갱신 필수."
        ),
        absolute_expiry_env="FMP_PLAN_EXPIRY",
        warn_days=FMP_PLAN_WARN_DAYS,
    ),
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_state() -> dict:
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
    """Parse ISO date / datetime string into aware UTC datetime."""
    if not date_str:
        return None
    try:
        # date-only path
        if len(date_str) == 10:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # full ISO path (handle trailing Z)
        normalized = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _effective_warn_days(policy: CredentialPolicy) -> int:
    """Per-policy warn window override (FMP plan = 30, default = 7)."""
    return policy.warn_days if policy.warn_days is not None else WARN_DAYS


def days_until_expiry(policy: CredentialPolicy, state: dict) -> Optional[int]:
    """Compute days remaining until rotation/expiry. None on parse failure.

    Two modes:
    - **Rotation cadence**: ``last_rotated + rotation_days`` (default).
    - **Absolute expiry**: ``absolute_expiry_env`` env var holds the raw
      ISO date.  Used for subscription-style credentials (FMP plan) where
      the provider publishes a hard expiry rather than a recommended
      rotation cadence.  Env-missing → return None (graceful skip).
    """
    # Absolute-expiry branch.
    if policy.absolute_expiry_env:
        raw = os.environ.get(policy.absolute_expiry_env, "")
        expiry = _parse_iso(raw)
        if expiry is None:
            return None
        delta = expiry - _now_utc()
        return int(delta.total_seconds() // 86400)

    # Rotation-cadence branch.
    entry = state.get(policy.name, {}) or {}
    last_rotated_raw = entry.get("last_rotated") or policy.default_last_rotated
    last_rotated = _parse_iso(last_rotated_raw)
    if last_rotated is None:
        return None
    due = last_rotated + timedelta(days=policy.rotation_days)
    delta = due - _now_utc()
    # round toward zero — partial day still counted as same day
    return int(delta.total_seconds() // 86400)


def should_alert(policy: CredentialPolicy, state: dict, days_left: int) -> bool:
    """Alert when within the policy's warn window and we haven't alerted in
    the dedup window.  Always alerts when overdue (days_left <= 0), still
    respecting dedup.

    Per-policy ``warn_days`` overrides the global ``WARN_DAYS`` — e.g. FMP
    plan uses D-30 because subscription migration needs more lead time.
    """
    if days_left > _effective_warn_days(policy):
        return False
    entry = state.get(policy.name, {}) or {}
    last_alert = _parse_iso(entry.get("last_alert_at", ""))
    if last_alert is None:
        return True
    return _now_utc() - last_alert >= timedelta(hours=DEDUP_HOURS)


def post_slack(text: str) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout fallback")
        print(f"[SLACK-FALLBACK] {text}")
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


def format_alert(policy: CredentialPolicy, days_left: int) -> str:
    if days_left <= 0:
        urgency = f"OVERDUE by {-days_left}d"
        emoji = "[CRIT]"
    else:
        urgency = f"D-{days_left}"
        emoji = "[WARN]"
    return (
        f"{emoji} PivoxQuant credential rotation {urgency}: {policy.label}\n"
        f"권장 회전 주기: {policy.rotation_days}d. "
        f"조치: {policy.rotation_instructions}"
    )


def main() -> int:
    state = load_state()
    alerts_sent = 0
    rc = 0

    for policy in POLICIES:
        days_left = days_until_expiry(policy, state)
        if days_left is None:
            logger.warning("policy=%s — last_rotated 파싱 실패, skip", policy.name)
            continue
        logger.info(
            "policy=%s days_left=%d threshold=D-%d",
            policy.name, days_left, WARN_DAYS,
        )

        if not should_alert(policy, state, days_left):
            continue

        msg = format_alert(policy, days_left)
        sent = post_slack(msg)
        # Persist alert timestamp regardless of webhook success — we logged it.
        entry = state.setdefault(policy.name, {})
        entry.setdefault("last_rotated", policy.default_last_rotated)
        entry["last_alert_at"] = _now_utc().isoformat()
        entry["last_alert_days_left"] = days_left
        alerts_sent += 1
        if not sent:
            # stdout fallback still counts as audit trail. exit 0 (graceful).
            pass
        if days_left <= 0:
            rc = max(rc, 2)  # overdue → meaningful non-zero
        elif rc == 0:
            rc = 0  # warn-only exits 0 (no auto-action)

    save_state(state)
    logger.info("credentials check complete: alerts_sent=%d", alerts_sent)
    return rc


if __name__ == "__main__":
    sys.exit(main())
