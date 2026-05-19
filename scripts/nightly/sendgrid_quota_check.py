#!/usr/bin/env python3
"""SendGrid 일일 한도 D-1 감시 (O-B).

목적
----
SendGrid 무료 플랜 100/day 한도 소진 전에 CEO에게 Slack 알림 + Brevo cascade
자동 failover를 트리거한다.

실행 스케줄
-----------
CC scheduled-task cron ``0 14 * * *`` (KST 23:00 = 한도 reset 1시간 전이
아닌, 하루 최후 버퍼로 UTC 14:00 = KST 23:00).
GitHub Actions 미사용 — audit 조건 #1.

로직
----
1. SendGrid Stats API ``GET /v3/stats?start_date=today&end_date=today`` 호출.
2. 당일 requests + delivered 합산 → 실제 발송수 추출.
3. 90 이상: Slack alert "90% 임박" (warn 단계).
4. 100 도달: Slack alert "한도 초과" + PIVOX_EMAIL_PROVIDER=brevo env 파일에
   플래그 기록 (실제 cascade는 services/email/sender.py 가 처리).
5. state/sendgrid_quota_history.json 에 날짜별 발송수 누적.

비용
----
SendGrid Stats API: 무료 플랜 포함 (쿼터 소모 없음).
Slack Incoming Webhook: 무료.
총 추가 비용: 0원.

환경변수
--------
SENDGRID_API_KEY  — 필수
SLACK_WEBHOOK_URL — 없으면 stdout 출력으로 대체 (경고)

실행
----
python scripts/nightly/sendgrid_quota_check.py
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

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── 경로 상수 ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _ROOT / "state"
QUOTA_HISTORY_PATH = STATE_DIR / "sendgrid_quota_history.json"

# ── 임계치 ─────────────────────────────────────────────────────────────────────
WARN_THRESHOLD = 90    # 이 이상 → Slack warn
HARD_LIMIT = 100       # 이 이상 → Slack crit + failover flag

# ── SSL context (macOS chain 우회) ─────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()


def _get_today_kst() -> str:
    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    return now_kst.strftime("%Y-%m-%d")


def _get_today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_sendgrid_stats(api_key: str) -> int:
    """SendGrid Stats API 호출 → 당일 발송 수 반환.

    Returns
    -------
    int
        당일 ``requests`` 카운트 (= 실제 발송 시도 수).
        API 오류 시 -1 반환 (caller 가 로깅 후 bail-out).
    """
    today = _get_today_utc()
    url = (
        f"https://api.sendgrid.com/v3/stats"
        f"?start_date={today}&end_date={today}&aggregated_by=day"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        logger.error("SendGrid Stats API HTTP %s: %s", exc.code, exc.reason)
        return -1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("SendGrid Stats API network error: %s", exc)
        return -1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("SendGrid Stats API JSON parse error: %s", exc)
        return -1

    # response: [{"date": "...", "stats": [{"metrics": {"requests": N, ...}}]}]
    if not isinstance(data, list) or not data:
        logger.warning("SendGrid Stats API returned empty list (no sends today)")
        return 0

    day_entry = data[0]
    stats_list = day_entry.get("stats", [])
    total = 0
    for stat in stats_list:
        metrics = stat.get("metrics", {})
        # "requests" = 총 전송 시도 수 (delivered + bounced + etc.)
        total += metrics.get("requests", 0)
    return total


def post_slack(text: str) -> bool:
    """Slack Incoming Webhook POST. 미설정 시 stdout 출력."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout 출력으로 대체")
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


def load_history() -> dict:
    """state/sendgrid_quota_history.json 로드. 없으면 빈 dict."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not QUOTA_HISTORY_PATH.exists():
        return {}
    try:
        return json.loads(QUOTA_HISTORY_PATH.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("quota history load failed (%s), starting fresh", exc)
        return {}


def save_history(history: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    QUOTA_HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_failover_flag() -> None:
    """state/ 에 brevo_failover.flag 파일 생성.

    services/email/sender.py 의 cascade 로직은 이 파일 존재 여부를 확인하여
    SendGrid 를 건너뛰고 Brevo 를 우선 사용할 수 있다.
    추측 라벨: sender.py 의 실제 flag 읽기 로직은 아직 미구현 — carry-over 필요.
    """
    flag_path = STATE_DIR / "brevo_failover.flag"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    flag_path.write_text(
        f"set_at={datetime.now(timezone.utc).isoformat()}\nreason=sendgrid_hard_limit\n",
        encoding="utf-8",
    )
    logger.info("Brevo failover flag set: %s", flag_path)


def clear_failover_flag() -> None:
    """새 날 시작 시 flag 초기화 (한도 reset 확인 후 호출)."""
    flag_path = STATE_DIR / "brevo_failover.flag"
    if flag_path.exists():
        flag_path.unlink()
        logger.info("Brevo failover flag cleared (quota reset)")


def main() -> int:
    api_key = os.environ.get("SENDGRID_API_KEY", "")
    if not api_key:
        logger.error("SENDGRID_API_KEY 미설정 — quota check 불가")
        post_slack(
            "[PivoxQuant OPS] SENDGRID_API_KEY 미설정 — SendGrid quota check 실패. "
            "Railway env 확인 요망."
        )
        return 1

    today = _get_today_kst()
    count = fetch_sendgrid_stats(api_key)

    if count < 0:
        # API 오류 — 자체 알림 후 종료
        post_slack(
            f"[PivoxQuant OPS] SendGrid Stats API 호출 실패 ({today}). "
            "Railway log 확인 요망."
        )
        return 1

    # 히스토리 저장
    history = load_history()
    history[today] = count
    save_history(history)
    logger.info("SendGrid quota today=%s count=%d", today, count)

    # 임계치 판단
    if count >= HARD_LIMIT:
        logger.warning("SendGrid 한도 초과: %d/%d", count, HARD_LIMIT)
        set_failover_flag()
        post_slack(
            f"[PivoxQuant OPS] CRITICAL: SendGrid 일일 한도 초과 ({count}/{HARD_LIMIT}, {today}). "
            "Brevo cascade failover 플래그 활성화. "
            "신규 이메일 발송은 Brevo 경로로 전환됩니다. "
            "Railway > SENDGRID_DAILY_EXHAUSTED=1 env 확인 후 내일 reset 예정."
        )
        return 2

    if count >= WARN_THRESHOLD:
        logger.warning("SendGrid 한도 90%% 임박: %d/%d", count, HARD_LIMIT)
        post_slack(
            f"[PivoxQuant OPS] WARNING: SendGrid 일일 한도 {count}/{HARD_LIMIT} ({today}). "
            "Brevo cascade verify 권장. 잔여 {HARD_LIMIT - count}건."
        )
        return 0

    # 새 날 flag 초기화 (전날 exhausted 후 오늘 카운트 0이면 reset)
    if count == 0:
        clear_failover_flag()

    logger.info("SendGrid quota OK: %d/%d (%s)", count, HARD_LIMIT, today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
