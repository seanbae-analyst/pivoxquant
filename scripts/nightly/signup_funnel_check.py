#!/usr/bin/env python3
"""가입→OAuth→결제 funnel drop-off 감시 (S1).

목적
----
가입 funnel 의 각 단계 (가입 시도 → OAuth 완료 → 첫 결제) 에서
비정상적인 drop-off 를 감지하여 CEO에게 Slack 알림.

감시 모드
---------
PIVOX_FUNNEL_ALERT_MODE=warn   (default, 첫 7일)
  - metrics dump 만 — 알림 미발송 (false positive 방지)
  - baseline 데이터 수집 단계
PIVOX_FUNNEL_ALERT_MODE=alert
  - 임계치 초과 시 즉시 Slack alert

audit 조건 #1: GitHub Actions 금지 → CC scheduled-task 라우팅.
audit 조건 #5: 첫 7일 warn-only 모드.

스케줄
------
CC scheduled-task: cron ``*/5 * * * *`` (5분 주기).
야간 mute: 00:00-06:00 KST (알림 skip — alert 모드에서도).

임계치 (alert 모드 전용)
-----------------------
- 5분간 신규 가입 0 + 기준치 >2/h → alert (서비스 장애 의심)
- OAuth 성공률 <80% → alert
- 결제 실패율 >10% → alert

추측 라벨
---------
- "가입 시도" = users.created_at 기준 (OAuth start 이벤트 테이블 없음 →
  users row 생성 = 가입 완료로 간주). 실제 OAuth start 대비 완료율은
  audit_log / request_log 없어 추적 불가. carry-over 필요.
- OAuth 성공률: users 중 oauth_provider 설정 + onboarding_completed 비율
  (직접 OAuth 성공 이벤트 테이블 없음).

비용 검증
---------
- DB query only: 0원 추가 비용.
- Slack webhook: 무료.

환경변수
--------
DATABASE_URL             — 필수
SLACK_WEBHOOK_URL        — 없으면 stdout
PIVOX_FUNNEL_ALERT_MODE  — warn | alert (default: warn)
PIVOX_FUNNEL_BASELINE_H  — 기준 시간당 가입 수 (default: 0, 수동 설정 필요)

실행
----
python scripts/nightly/signup_funnel_check.py
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

_SSL_CTX = ssl.create_default_context()
_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _ROOT / "state"
FUNNEL_HISTORY_PATH = STATE_DIR / "signup_funnel_history.json"

# ── 모드 ──────────────────────────────────────────────────────────────────────
ALERT_MODE = os.environ.get("PIVOX_FUNNEL_ALERT_MODE", "warn").lower()
BASELINE_H = float(os.environ.get("PIVOX_FUNNEL_BASELINE_H", "0"))  # 시간당 기준 가입

# ── 임계치 ────────────────────────────────────────────────────────────────────
OAUTH_SUCCESS_MIN_PCT = 80.0   # OAuth 성공률 최소값
PAYMENT_FAIL_MAX_PCT = 10.0    # 결제 실패율 최대값
NIGHT_MUTE_START = 0           # 00:00 KST
NIGHT_MUTE_END = 6             # 06:00 KST


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def _is_night_mute() -> bool:
    hour = _now_kst().hour
    return NIGHT_MUTE_START <= hour < NIGHT_MUTE_END


def post_slack(text: str) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout 출력")
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


# ── DB 쿼리 ───────────────────────────────────────────────────────────────────

def _run_query(db_url: str, sql: str, params: dict | None = None) -> int | None:
    """단일 scalar int 쿼리. 실패 시 None 반환."""
    try:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(sql, params or {})
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else 0
    except ImportError:
        pass

    try:
        from sqlalchemy import create_engine, text  # type: ignore

        engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            result = conn.execute(text(sql)).scalar()
            return result or 0
    except Exception as exc:
        logger.error("DB query error: %s | sql=%s", exc, sql[:80])
        return None


def fetch_funnel_metrics(db_url: str) -> dict:
    """5분 + 1h 윈도우 funnel 메트릭 쿼리.

    추측 라벨:
    - signup_5m: users.created_at 5분 내 (= 완료된 가입, OAuth start 아님)
    - oauth_success_24h: oauth_provider IS NOT NULL 비율 (대리 지표)
    - payment_attempts_24h: 추적 테이블 없어 trade_history 또는 processed_stripe_event 사용
    """
    metrics: dict = {}

    # 가입 5분
    v = _run_query(db_url, "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '5 minutes'")
    metrics["signup_5m"] = v

    # 가입 1시간 (baseline 비교용)
    v = _run_query(db_url, "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '1 hour'")
    metrics["signup_1h"] = v

    # OAuth 성공률 (24h 신규 유저 중 oauth_provider 설정 비율)
    # 추측 라벨: OAuth start → complete 전이율 아님. 완료된 유저 중 비율.
    total_24h = _run_query(
        db_url, "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '24 hours'"
    )
    oauth_24h = _run_query(
        db_url,
        "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '24 hours' AND oauth_provider IS NOT NULL"
    )
    metrics["total_24h"] = total_24h
    metrics["oauth_24h"] = oauth_24h
    if total_24h and total_24h > 0 and oauth_24h is not None:
        metrics["oauth_pct"] = round(oauth_24h / total_24h * 100, 1)
    else:
        metrics["oauth_pct"] = None  # 데이터 없음

    # Stripe 이벤트 (processed_stripe_event 테이블 사용)
    # 추측 라벨: processed_stripe_event.event_type 으로 success/fail 구분.
    # 테이블 존재 여부 미확정 — 없으면 None.
    success_v = _run_query(
        db_url,
        "SELECT COUNT(*) FROM processed_stripe_event WHERE created_at >= NOW() - INTERVAL '24 hours' AND event_type = 'payment_intent.succeeded'"
    )
    fail_v = _run_query(
        db_url,
        "SELECT COUNT(*) FROM processed_stripe_event WHERE created_at >= NOW() - INTERVAL '24 hours' AND event_type = 'payment_intent.payment_failed'"
    )
    metrics["stripe_success_24h"] = success_v
    metrics["stripe_fail_24h"] = fail_v
    if (success_v is not None and fail_v is not None
            and (success_v + fail_v) > 0):
        total_pay = success_v + fail_v
        metrics["payment_fail_pct"] = round(fail_v / total_pay * 100, 1)
    else:
        metrics["payment_fail_pct"] = None

    return metrics


# ── 히스토리 ─────────────────────────────────────────────────────────────────

def load_history() -> list[dict]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not FUNNEL_HISTORY_PATH.exists():
        return []
    try:
        return json.loads(FUNNEL_HISTORY_PATH.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # 최근 2000 레코드만 유지 (5분 * 2000 = ~7일)
    history = history[-2000:]
    FUNNEL_HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=None),
        encoding="utf-8",
    )


# ── alert 로직 ────────────────────────────────────────────────────────────────

def evaluate_alerts(metrics: dict) -> list[str]:
    """임계치 위반 alert 메시지 목록 반환 (alert 모드 전용)."""
    alerts: list[str] = []
    now_str = _now_kst().strftime("%H:%M KST")

    # 가입 0 + baseline >2/h
    s5 = metrics.get("signup_5m")
    if s5 == 0 and BASELINE_H > 2:
        alerts.append(
            f"[{now_str}] 가입 0건 (5분) — 평소 {BASELINE_H:.1f}/h 기준 비정상. 서비스 장애 의심."
        )

    # OAuth 성공률 <80%
    oauth_pct = metrics.get("oauth_pct")
    if oauth_pct is not None and oauth_pct < OAUTH_SUCCESS_MIN_PCT:
        alerts.append(
            f"[{now_str}] OAuth 성공률 {oauth_pct}% < {OAUTH_SUCCESS_MIN_PCT}%. "
            f"24h 가입 {metrics.get('total_24h')}명 중 {metrics.get('oauth_24h')}명만 OAuth 완료."
        )

    # 결제 실패율 >10%
    pay_fail_pct = metrics.get("payment_fail_pct")
    if pay_fail_pct is not None and pay_fail_pct > PAYMENT_FAIL_MAX_PCT:
        alerts.append(
            f"[{now_str}] 결제 실패율 {pay_fail_pct}% > {PAYMENT_FAIL_MAX_PCT}%. "
            f"Stripe 이벤트: 성공 {metrics.get('stripe_success_24h')} / 실패 {metrics.get('stripe_fail_24h')}."
        )

    return alerts


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL 미설정 — funnel check 불가")
        return 1

    now_kst = _now_kst()
    now_str = now_kst.strftime("%Y-%m-%d %H:%M:%S KST")
    logger.info("Funnel check 시작: %s (mode=%s)", now_str, ALERT_MODE)

    try:
        metrics = fetch_funnel_metrics(db_url)
    except Exception as exc:
        logger.exception("fetch_funnel_metrics 예외: %s", exc)
        if not _is_night_mute():
            post_slack(
                f"[PivoxQuant OPS] signup_funnel_check 예외 발생 ({now_str}): {exc}"
            )
        return 1

    # 히스토리 저장 (모드 무관)
    history = load_history()
    history.append({
        "ts": now_kst.isoformat(),
        "mode": ALERT_MODE,
        **{k: v for k, v in metrics.items()},
    })
    save_history(history)

    logger.info("Funnel metrics: %s", metrics)

    # warn 모드: dump 만, alert 미발송
    if ALERT_MODE == "warn":
        logger.info(
            "WARN-ONLY 모드 (baseline 수집 중). "
            "실제 alert은 PIVOX_FUNNEL_ALERT_MODE=alert 로 전환 후 발송."
        )
        return 0

    # alert 모드: 야간 mute 확인
    if _is_night_mute():
        logger.info("야간 mute (00:00-06:00 KST) — alert skip")
        return 0

    alert_msgs = evaluate_alerts(metrics)
    if not alert_msgs:
        logger.info("Funnel check OK — 이상 없음")
        return 0

    for msg in alert_msgs:
        logger.warning("ALERT: %s", msg)
        post_slack(f"[PivoxQuant FUNNEL ALERT] {msg}")

    return len(alert_msgs)


if __name__ == "__main__":
    sys.exit(main())
