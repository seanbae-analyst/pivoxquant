#!/usr/bin/env python3
"""
Nightly FX rate staleness check (Wave I Q-1).
=============================================

USD/KRW 캐시가 24시간 이상 stale 상태로 굳어있으면 Slack 알림 + Sentry
capture 를 발송한다.  2026-05-18 v44.8 에서 portfolio equity curve 가
+52,281% 로 폭발한 root cause (KRW raw 합산 → FX 변환 누락) 의 재발을
감지하기 위한 운영 게이트.

동작 흐름
---------
1. ``services.fx_service.last_updated()`` 로 마지막 성공 fetch timestamp 조회.
2. timestamp 가 0 (한 번도 갱신 안 됨) 이거나 현재 시각과의 차이가
   ``STALE_THRESHOLD_SECONDS`` (기본 86400s = 24h) 초과면 stale 판정.
3. stale 이면:
   - Sentry ``capture_message`` (level=warning)
   - Slack webhook POST (SLACK_WEBHOOK_URL env)
   - ``state/fx_staleness_alerted.json`` 에 마지막 알림 타임스탬프 기록
     (DEDUP_HOURS 내 재알림 방지)
4. stale 이 아니면 조용히 exit 0.

Graceful degradation
--------------------
- ``SLACK_WEBHOOK_URL`` 미설정 → log + stdout 출력 (경고만).
- ``SENTRY_DSN`` 미설정 → Sentry skip, 나머지는 정상 실행.
- APScheduler 안에서 실행되는 경우 예외는 caller 에서 잡아야 함
  (raise 하지 않음 — 기존 Wave H cron_jobs 패턴 일치).

Exit codes (standalone 실행 시)
--------------------------------
- 0 — 정상 (fresh 또는 알림 dedup)
- 1 — stale 감지 + Slack 발송 완료
- 2 — 예외 발생 (Sentry capture 후)

비용: 0원 (Slack incoming webhook 무료 + Sentry free tier)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("fx_staleness_check")

# ── 설정 상수 ───────────────────────────────────────────────────────────
# 24시간 초과 = stale (portfolio 폭발 재발 방지 기준)
STALE_THRESHOLD_SECONDS: int = int(
    os.environ.get("PIVOX_FX_STALE_THRESHOLD_SECONDS", "86400")
)
# 같은 stale 이벤트를 6시간 내 재알림하지 않음
DEDUP_HOURS: int = 6

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STATE_DIR = _PROJECT_ROOT / "state"
_STATE_FILE = _STATE_DIR / "fx_staleness_alerted.json"


# ── 헬퍼 ────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as exc:
        logger.warning("fx_staleness_check: state save failed: %s", exc)


def _should_alert(state: dict) -> bool:
    """Dedup: DEDUP_HOURS 내 이미 알림을 보냈으면 skip."""
    last_iso = state.get("last_alert_at")
    if not last_iso:
        return True
    try:
        last_dt = datetime.fromisoformat(last_iso)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        elapsed_hours = (_now_utc() - last_dt).total_seconds() / 3600
        return elapsed_hours >= DEDUP_HOURS
    except Exception:
        return True


def _post_slack(text: str) -> bool:
    """Slack Incoming Webhook POST. SLACK_WEBHOOK_URL 없으면 stdout."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout 출력: %s", text)
        print(f"[FX-STALENESS-ALERT] {text}")
        return False
    try:
        import urllib.request
        payload = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.error("fx_staleness_check: Slack POST failed: %s", exc)
        return False


def _capture_sentry(msg: str) -> None:
    """Sentry capture_message — DSN 없으면 skip."""
    try:
        import sentry_sdk
        sentry_sdk.capture_message(msg, level="warning")
    except Exception:
        pass  # sentry not installed or DSN unset — graceful


# ── 핵심 로직 ────────────────────────────────────────────────────────────

def check_fx_staleness() -> int:
    """
    Returns:
        0 — fresh (no alert needed) or dedup suppressed
        1 — stale alert sent
        2 — exception during check
    """
    try:
        # sys.path에 프로젝트 루트 추가 (standalone 실행 시 필요)
        _root = str(_PROJECT_ROOT)
        if _root not in sys.path:
            sys.path.insert(0, _root)

        from services import fx_service

        last_ts = fx_service.last_updated()
        now_ts = time.time()

        if last_ts == 0.0:
            age_seconds = -1  # never fetched
            age_display = "한 번도 갱신 안 됨 (never fetched)"
            is_stale = True
        else:
            age_seconds = int(now_ts - last_ts)
            age_h = age_seconds // 3600
            age_m = (age_seconds % 3600) // 60
            age_display = f"{age_h}h {age_m}m"
            is_stale = age_seconds > STALE_THRESHOLD_SECONDS

        if not is_stale:
            logger.info(
                "fx_staleness_check: OK — USD/KRW 마지막 갱신 %s, rate=%s",
                age_display,
                fx_service.get_rate(),
            )
            return 0

        state = _load_state()
        if not _should_alert(state):
            logger.info(
                "fx_staleness_check: stale(%s) but dedup suppressed", age_display
            )
            return 0

        # Stale + 알림 발송
        rate = fx_service.get_rate()
        threshold_h = STALE_THRESHOLD_SECONDS // 3600
        msg = (
            f":warning: *[PivoxQuant] FX Rate STALE* — "
            f"USD/KRW 마지막 갱신 *{age_display}* "
            f"(임계값: {threshold_h}h). "
            f"현재 캐시 rate: {rate}. "
            f"portfolio equity curve 왜곡 위험 — "
            f"FMP / exchangerate-api 연결 확인 요망."
        )

        _capture_sentry(f"FX rate stale: age={age_display}, rate={rate}")
        _post_slack(msg)

        state["last_alert_at"] = _now_utc().isoformat()
        state["last_stale_age_seconds"] = age_seconds
        state["last_stale_rate"] = rate
        _save_state(state)

        logger.warning("fx_staleness_check: STALE alert sent (age=%s)", age_display)
        return 1

    except Exception as exc:
        logger.error("fx_staleness_check: unexpected error: %s", exc, exc_info=True)
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        return 2


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    sys.exit(check_fx_staleness())


if __name__ == "__main__":
    main()
